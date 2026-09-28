from __future__ import annotations

import base64
import json
import mimetypes
import urllib.request
from pathlib import Path


def interpreting_images(
    image_path: str,
    instruction: str = "Jelaskan isi gambar ini secara rinci.",
    *,
    project_root: Path | None = None,
) -> str:
    """Analyze a local image with the configured local Ollama vision model."""
    path = Path(image_path).expanduser().resolve()
    if project_root is not None:
        root = project_root.resolve()
        if path != root and root not in path.parents:
            raise PermissionError("Gambar berada di luar direktori proyek SATRIA.")
    if not path.is_file():
        raise FileNotFoundError("Berkas gambar tidak ditemukan.")
    if path.stat().st_size > 12 * 1024 * 1024:
        raise ValueError("Ukuran gambar melebihi batas 12 MB.")
    mime_type = mimetypes.guess_type(path.name)[0]
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError("Berkas bukan format gambar yang didukung.")

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    request_payload = json.dumps(
        {
            "model": "gemma4:12b",
            "stream": False,
            "messages": [{"role": "user", "content": instruction, "images": [encoded]}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=request_payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))
    return str(result.get("message", {}).get("content", ""))
