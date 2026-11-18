"""Optional Cursor MCP server — offline tools, no API keys required."""

from __future__ import annotations

import json
from pathlib import Path


def _require_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "MCP extra missing. pip install 'dup-content-engine[mcp]' "
            "or: pip install mcp"
        ) from exc
    return FastMCP


def build_server():
    FastMCP = _require_mcp()
    from content_engine import __version__
    from content_engine.hook_score import score_script
    from content_engine.pipeline import DEFAULT_FIXTURE, PACKAGE_ROOT, load_script
    from content_engine.script_writer import write_topic_script

    mcp = FastMCP("dup-content-engine")

    @mcp.tool()
    def doctor() -> str:
        """Toolchain / version snapshot (no secrets)."""
        from content_engine.caption_burn import find_font
        from content_engine.ffmpeg_util import ffmpeg_bin
        from content_engine.voice import resolve_provider

        return json.dumps(
            {
                "version": __version__,
                "ffmpeg": ffmpeg_bin(),
                "font": str(find_font()) if find_font() else None,
                "tts_provider": resolve_provider(),
                "note": "ALLOW ≠ growth; keys are optional and added later",
            },
            indent=2,
        )

    @mcp.tool()
    def score_fixture() -> str:
        """Hook heuristic for the demo fixture script."""
        script = load_script(DEFAULT_FIXTURE)
        return json.dumps(score_script(script), indent=2)

    @mcp.tool()
    def write_offline_script(topic: str) -> str:
        """Write an offline topic script under out/mcp/ (no LLM key)."""
        out = PACKAGE_ROOT / "out" / "mcp" / "script.json"
        script, source = write_topic_script(topic, out, prefer_llm=False)
        return json.dumps(
            {"source": source, "script": str(out), "title": script.title},
            indent=2,
        )

    @mcp.tool()
    def list_out_packs() -> str:
        """List verified_pack_*.json under out/ (evidence on disk)."""
        root = PACKAGE_ROOT / "out"
        packs = sorted(root.rglob("verified_pack_*.json"))
        return json.dumps(
            {"count": len(packs), "packs": [str(p) for p in packs[-20:]]},
            indent=2,
        )

    return mcp


def main() -> None:
    server = build_server()
    server.run()


if __name__ == "__main__":
    main()
