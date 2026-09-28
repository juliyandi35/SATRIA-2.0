from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from services.ai_service import interpreting_images
from services.email_service import send_email_tool
from services.news_service import search_web

if TYPE_CHECKING:
    from satria.data_service import DataRepository


PROJECT_ROOT = Path(__file__).resolve().parent
CHECKPOINT_PATH = PROJECT_ROOT / "checkpoints.db"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
SUPPORTED_MODELS = (
    "granite4.2:3b",
    "ornith-1.5:9b",
    "gemma4:12b",
    "muse-glimmer",
)
_MODEL_CACHE: tuple[float, list[str]] = (0.0, [])
_MODEL_CACHE_LOCK = threading.Lock()
_MEMORY_LOCK = threading.RLock()
_ACTIVE_REPOSITORY: "DataRepository | None" = None


def bind_repository(repository: "DataRepository") -> None:
    """Give the AI tool layer a live reference to the app's active dataset repository."""
    global _ACTIVE_REPOSITORY
    _ACTIVE_REPOSITORY = repository


def load_system_prompt(base_dir: str | Path = PROJECT_ROOT) -> str:
    prompt_dir = Path(base_dir) / "prompts"
    prompt_parts = []
    if prompt_dir.is_dir():
        for prompt_path in sorted(prompt_dir.glob("*.txt")):
            prompt_parts.append(prompt_path.read_text(encoding="utf-8"))
    prompt = "\n\n".join(prompt_parts) or (
        "You are SATRIA, a local defense readiness intelligence assistant. "
        "Never invent operational metrics. "
        "Always reply in formal Bahasa Indonesia, regardless of the language of the user's message."
    )
    return prompt.replace("{directory_path}", str(Path(base_dir).resolve()))


SYSTEM_PROMPT = load_system_prompt()


def _checkpoint_db() -> sqlite3.Connection:
    """Open a checkpoint connection whose 'with' block commits/rolls back but never closes it
    (sqlite3's own context-manager behavior) - callers must close it themselves."""
    return sqlite3.connect(CHECKPOINT_PATH)


def _init_memory() -> None:
    connection = _checkpoint_db()
    try:
        with _MEMORY_LOCK, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS satria_chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    model TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_satria_chat_thread "
                "ON satria_chat_messages(thread_id, id)"
            )
    finally:
        connection.close()


_init_memory()


def _safe_project_path(value: str, *, must_exist: bool = True) -> Path:
    path_value = Path(value)
    candidate = (PROJECT_ROOT / path_value).resolve() if not path_value.is_absolute() else path_value.resolve()
    if candidate != PROJECT_ROOT and PROJECT_ROOT not in candidate.parents:
        raise PermissionError("Akses di luar direktori proyek SATRIA ditolak.")
    if must_exist and not candidate.exists():
        raise FileNotFoundError("Path tidak ditemukan di proyek SATRIA.")
    return candidate


def list_directory(path: str = ".") -> str:
    """List files inside the SATRIA project boundary."""
    directory = _safe_project_path(path)
    if not directory.is_dir():
        raise ValueError("Path bukan direktori.")
    entries = []
    for item in sorted(directory.iterdir(), key=lambda value: (not value.is_dir(), value.name.casefold()))[:250]:
        entries.append({"name": item.name, "type": "directory" if item.is_dir() else "file"})
    relative = directory.relative_to(PROJECT_ROOT)
    return json.dumps({"path": str(relative) if str(relative) else ".", "entries": entries}, ensure_ascii=False)


def read_file(file_path: str) -> str:
    """Read a bounded text file inside the SATRIA project."""
    path = _safe_project_path(file_path)
    if not path.is_file():
        raise ValueError("Path bukan berkas.")
    allowed = {".txt", ".md", ".csv", ".json", ".py", ".html", ".css", ".js", ".ts", ".tsx"}
    if path.suffix.lower() not in allowed:
        raise PermissionError("Jenis berkas ini tidak dapat dibaca oleh asisten.")
    if path.stat().st_size > 512_000:
        raise ValueError("Berkas terlalu besar untuk dibaca langsung.")
    for encoding in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Encoding berkas tidak didukung.")


def query_defense_data(query: str) -> str:
    """Execute one SELECT-only query against the optional defense MySQL database."""
    statement = query.strip()
    if not re.match(r"^SELECT\b", statement, flags=re.IGNORECASE):
        raise PermissionError("Hanya kueri SELECT yang diizinkan.")
    if ";" in statement.rstrip(";") or re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|GRANT|REVOKE|CALL|INTO\s+(OUTFILE|DUMPFILE))\b",
        statement,
        flags=re.IGNORECASE,
    ):
        raise PermissionError("Kueri mengandung operasi yang tidak diizinkan.")
    try:
        import mysql.connector
    except ImportError as exc:
        raise RuntimeError("Konektor MySQL belum terpasang.") from exc

    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "satu_data_pertahanan"),
        collation="utf8mb4_unicode_ci",
        connection_timeout=5,
    )
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(statement)
            records = cursor.fetchmany(500)
            return json.dumps(records, ensure_ascii=False, default=str)
        finally:
            cursor.close()
    finally:
        connection.close()


def analyze_spatial_risk(region_data: list[dict[str, Any]], eps: float = 150.0, min_samples: int = 3) -> str:
    """Run the same real Haversine DBSCAN analysis used by the API."""
    import pandas as pd

    from satria.analytics_service import spatial_clusters

    frame = pd.DataFrame(region_data)
    required = {"id", "unit", "location", "lat", "lon", "readiness", "status"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Data spasial membutuhkan kolom: {', '.join(sorted(required))}")
    result = spatial_clusters(frame, epsilon_km=float(eps), min_samples=int(min_samples))
    return json.dumps(result, ensure_ascii=False)


def send_full_report_email(recipient_email: str) -> str:
    """Build a full PDF intelligence report from the active dataset and email it to recipient_email."""
    if _ACTIVE_REPOSITORY is None or not _ACTIVE_REPOSITORY.loaded:
        raise ValueError("Belum ada dataset aktif untuk dilaporkan.")
    from services.report_service import build_full_report_pdf

    pdf_bytes = build_full_report_pdf(_ACTIVE_REPOSITORY)
    return send_email_tool(
        recipient_email,
        "SATRIA 2.0 - Laporan Lengkap",
        "Laporan lengkap kesiapan pertahanan terlampir dalam format PDF.",
        attachment=(pdf_bytes, "laporan-satria.pdf"),
    )


def list_ollama_models(force: bool = False) -> list[str]:
    global _MODEL_CACHE
    with _MODEL_CACHE_LOCK:
        timestamp, models = _MODEL_CACHE
        if not force and models and time.monotonic() - timestamp < 10:
            return models.copy()
        request = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(request, timeout=3) as response:
            result = json.loads(response.read().decode("utf-8"))
        models = [str(item.get("name", "")) for item in result.get("models", []) if item.get("name")]
        _MODEL_CACHE = (time.monotonic(), models)
        return models.copy()


def resolve_model(requested_model: str) -> str:
    if requested_model not in SUPPORTED_MODELS:
        raise ValueError("Model tidak termasuk dalam daftar model SATRIA.")
    installed = list_ollama_models()
    candidates = [requested_model]
    if ":" not in requested_model:
        candidates.append(f"{requested_model}:latest")
    match = next((candidate for candidate in candidates if candidate in installed), None)
    if match is None:
        raise RuntimeError("Model tidak tersedia di Ollama lokal.")
    return match


def model_status() -> list[dict[str, Any]]:
    try:
        installed = list_ollama_models(force=True)
        ollama_online = True
    except Exception:
        installed = []
        ollama_online = False
    result = []
    for model in SUPPORTED_MODELS:
        candidates = [model, f"{model}:latest"] if ":" not in model else [model]
        resolved = next((candidate for candidate in candidates if candidate in installed), None)
        result.append(
            {
                "name": model,
                "provider": "Ollama Local",
                "available": resolved is not None,
                "resolved_name": resolved,
                "ollama_online": ollama_online,
            }
        )
    return result


def _history(thread_id: str, limit: int = 12) -> list[dict[str, str]]:
    connection = _checkpoint_db()
    try:
        with _MEMORY_LOCK, connection:
            rows = connection.execute(
                "SELECT role, content FROM satria_chat_messages WHERE thread_id = ? ORDER BY id DESC LIMIT ?",
                (thread_id, limit),
            ).fetchall()
    finally:
        connection.close()
    return [{"role": role, "content": content} for role, content in reversed(rows)]


def _remember(thread_id: str, role: str, content: str, model: str) -> None:
    connection = _checkpoint_db()
    try:
        with _MEMORY_LOCK, connection:
            connection.execute(
                "INSERT INTO satria_chat_messages(thread_id, role, content, model, created_at) VALUES (?, ?, ?, ?, ?)",
                (thread_id, role, content, model, datetime.now(timezone.utc).isoformat()),
            )
    finally:
        connection.close()


def clear_session(thread_id: str) -> int:
    connection = _checkpoint_db()
    try:
        with _MEMORY_LOCK, connection:
            cursor = connection.execute("DELETE FROM satria_chat_messages WHERE thread_id = ?", (thread_id,))
            return int(cursor.rowcount)
    finally:
        connection.close()


def _tool_schemas(include_external: bool) -> list[dict[str, Any]]:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "List files inside the SATRIA project only.",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a small text file inside the SATRIA project only.",
                "parameters": {
                    "type": "object",
                    "properties": {"file_path": {"type": "string"}},
                    "required": ["file_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_defense_data",
                "description": "Run one SELECT-only query against the configured defense database.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        },
    ]
    if include_external:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Search the public web for current public information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "max_results": {"type": "integer", "minimum": 1, "maximum": 5},
                        },
                        "required": ["query"],
                    },
                },
            }
        )
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "send_full_report_email",
                    "description": (
                        "Build a full PDF intelligence report from the active dataset and email it "
                        "to the given recipient address."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {"recipient_email": {"type": "string"}},
                        "required": ["recipient_email"],
                    },
                },
            }
        )
    return tools


def _dispatch_tool(name: str, arguments: dict[str, Any], include_external: bool) -> str:
    local_tools: dict[str, Callable[..., str]] = {
        "list_directory": list_directory,
        "read_file": read_file,
        "query_defense_data": query_defense_data,
    }
    if include_external:
        local_tools["search_web"] = search_web
        local_tools["send_full_report_email"] = send_full_report_email
    tool = local_tools.get(name)
    if tool is None:
        return "Tool tidak diizinkan dalam mode eksekusi saat ini."
    try:
        return str(tool(**arguments))[:40_000]
    except Exception as exc:
        return f"Tool gagal: {exc}"


def _ollama_chat(model: str, messages: list[dict[str, Any]], include_external: bool) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.25},
        "tools": _tool_schemas(include_external),
    }
    request = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))


def ask_satria(
    user_query: str,
    active_unit: str = "National",
    selected_region: str = "All",
    dashboard_context: dict[str, Any] | None = None,
    session_id: str = "1",
    local_exec: bool = True,
    ai_model: str = "granite4.2:3b",
) -> str:
    """Answer with the selected local Ollama model and persistent SQLite history."""
    query = user_query.strip()
    if not query:
        raise ValueError("Pesan kosong. Berikan instruksi intelijen.")
    if len(query) > 8_000:
        raise ValueError("Pesan melebihi batas 8.000 karakter.")
    thread_id = re.sub(r"[^A-Za-z0-9_.:-]", "_", str(session_id))[:120] or "satria-session"
    model = resolve_model(ai_model)
    context = dashboard_context or {}
    serialized_context = json.dumps(context, ensure_ascii=False, default=str)[:24_000]
    current_prompt = (
        f"Konteks aplikasi aktif (JSON, sumber analitik otoritatif):\n{serialized_context}\n\n"
        f"Unit aktif: {active_unit}\nWilayah aktif: {selected_region}\n"
        f"Pertanyaan pengguna: {query}"
    )
    include_external = not bool(local_exec)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *_history(thread_id),
        {"role": "user", "content": current_prompt},
    ]

    result = _ollama_chat(model, messages, include_external)
    assistant_message = result.get("message", {})
    tool_calls = assistant_message.get("tool_calls", [])
    if tool_calls:
        messages.append(assistant_message)
        for call in tool_calls[:3]:
            function = call.get("function", {})
            name = str(function.get("name", ""))
            arguments = function.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}
            messages.append(
                {
                    "role": "tool",
                    "tool_name": name,
                    "content": _dispatch_tool(name, arguments, include_external),
                }
            )
        result = _ollama_chat(model, messages, include_external)
        assistant_message = result.get("message", {})

    response = str(assistant_message.get("content", "")).strip()
    if not response:
        raise RuntimeError("Model tidak menghasilkan respons teks.")
    _remember(thread_id, "user", query, model)
    _remember(thread_id, "assistant", response, model)
    return response
