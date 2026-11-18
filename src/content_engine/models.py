"""Typed artifacts for the content pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Scene:
    id: str
    text: str
    visual_query: str

    @staticmethod
    def from_dict(d: dict[str, Any], idx: int) -> Scene:
        return Scene(
            id=str(d.get("id") or f"scene_{idx:02d}"),
            text=str(d.get("text") or "").strip(),
            visual_query=str(d.get("visual_query") or d.get("visual_query_en") or "abstract").strip(),
        )


@dataclass
class Script:
    schema: str
    title: str
    description: str
    tags: list[str]
    language: str
    aspect: str
    scenes: list[Scene]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Script:
        scenes_raw = d.get("scenes") or []
        if not isinstance(scenes_raw, list) or not scenes_raw:
            raise ValueError("script.scenes must be a non-empty list")
        scenes = [Scene.from_dict(s, i) for i, s in enumerate(scenes_raw)]
        for s in scenes:
            if not s.text:
                raise ValueError(f"scene {s.id} has empty text")
        return Script(
            schema=str(d.get("schema") or "dup.content_script.v1"),
            title=str(d.get("title") or "untitled").strip(),
            description=str(d.get("description") or "").strip(),
            tags=[str(t) for t in (d.get("tags") or [])],
            language=str(d.get("language") or "en"),
            aspect=str(d.get("aspect") or "9:16"),
            scenes=scenes,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "title": self.title,
            "description": self.description,
            "tags": list(self.tags),
            "language": self.language,
            "aspect": self.aspect,
            "scenes": [asdict(s) for s in self.scenes],
        }


@dataclass
class SceneTiming:
    id: str
    duration_sec: float
    audio_path: str
    clip_path: str | None = None


@dataclass
class GateResult:
    ok: bool
    allowed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "allowed": self.allowed,
            "detail": self.detail,
            "checks": list(self.checks),
        }


@dataclass
class RunReport:
    run_id: str
    ok: bool
    output_mp4: str | None
    pack_path: str | None
    gate: GateResult
    timings: list[SceneTiming] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "ok": self.ok,
            "output_mp4": self.output_mp4,
            "pack_path": self.pack_path,
            "gate": self.gate.to_dict(),
            "timings": [asdict(t) for t in self.timings],
            "notes": list(self.notes),
        }
