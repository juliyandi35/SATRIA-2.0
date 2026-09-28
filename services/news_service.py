from __future__ import annotations


def search_web(query: str, max_results: int = 3) -> str:
    """Search the web when the optional DDGS integration is installed and enabled."""
    try:
        from ddgs import DDGS
    except ImportError as exc:
        raise RuntimeError("Integrasi pencarian eksternal belum terpasang.") from exc

    max_results = max(1, min(int(max_results), 5))
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    if not results:
        return f"Tidak ada hasil pencarian untuk: {query}"
    return "\n\n".join(
        f"[{index}] {item.get('title', 'Tanpa judul')}\n"
        f"Ringkasan: {item.get('body', 'Tidak tersedia')}\n"
        f"Sumber: {item.get('href', 'Tidak tersedia')}"
        for index, item in enumerate(results, start=1)
    )
