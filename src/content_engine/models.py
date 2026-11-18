"""Typed artifacts for the content pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _flatten_scene_dict(d: dict[str, Any], idx: int) -> list[dict[str, Any]]:
    """Expand optional lines[] into one scene per spoken beat (voice↔caption sync)."""
    lines = d.get("lines")
    if not isinstance(lines, list) or not lines:
        return [d]
    base_id = str(d.get("id") or f"scene_{idx:02d}")
    base_vq = str(d.get("visual_query") or d.get("visual_query_en") or "abstract")
    out: list[dict[str, Any]] = []
    for j, line in enumerate(lines):
        if isinstance(line, str):
            line = {"text": line}
        if not isinstance(line, dict):
            continue
        out.append(
            {
                "id": str(line.get("id") or f"{base_id}_L{j}"),
                "text": str(line.get("text") or "").strip(),
                "visual_query": str(
                    line.get("visual_query") or line.get("visual_query_en") or base_vq
                ).strip(),
                "emotion": line.get("emotion", d.get("emotion")),
                "speaker": line.get("speaker", d.get("speaker")),
                "gender": line.get("gender", d.get("gender")),
                "voice": line.get("voice", d.get("voice")),
                "character_style": line.get("character_style", d.get("character_style")),
                "look": line.get("look", d.get("look")),
                "avatar_id": line.get("avatar_id", d.get("avatar_id")),
            }
        )
    return out or [d]


@dataclass
class Scene:
    id: str
    text: str
    visual_query: str
    emotion: str | None = None
    speaker: str | None = None
    gender: str | None = None
    voice: str | None = None
    character_style: str | None = None
    look: str | None = None
    avatar_id: str | None = None

    @staticmethod
    def from_dict(d: dict[str, Any], idx: int) -> Scene:
        return Scene(
            id=str(d.get("id") or f"scene_{idx:02d}"),
            text=str(d.get("text") or "").strip(),
            visual_query=str(
                d.get("visual_query") or d.get("visual_query_en") or "abstract"
            ).strip(),
            emotion=(str(d["emotion"]).strip() if d.get("emotion") else None),
            speaker=(str(d["speaker"]).strip() if d.get("speaker") else None),
            gender=(str(d["gender"]).strip().lower() if d.get("gender") else None),
            voice=(str(d["voice"]).strip() if d.get("voice") else None),
            character_style=(
                str(d["character_style"]).strip().lower() if d.get("character_style") else None
            ),
            look=(str(d["look"]).strip() if d.get("look") else None),
            avatar_id=(str(d["avatar_id"]).strip() if d.get("avatar_id") else None),
        )

    def to_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "id": self.id,
            "text": self.text,
            "visual_query": self.visual_query,
        }
        if self.emotion:
            row["emotion"] = self.emotion
        if self.speaker:
            row["speaker"] = self.speaker
        if self.gender:
            row["gender"] = self.gender
        if self.voice:
            row["voice"] = self.voice
        if self.character_style:
            row["character_style"] = self.character_style
        if self.look:
            row["look"] = self.look
        if self.avatar_id:
            row["avatar_id"] = self.avatar_id
        return row


@dataclass
class Script:
    schema: str
    title: str
    description: str
    tags: list[str]
    language: str
    aspect: str
    scenes: list[Scene]
    visual_style: str | None = None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Script:
        scenes_raw = d.get("scenes") or []
        if not isinstance(scenes_raw, list) or not scenes_raw:
            raise ValueError("script.scenes must be a non-empty list")
        flat: list[dict[str, Any]] = []
        for i, s in enumerate(scenes_raw):
            if not isinstance(s, dict):
                raise ValueError(f"scene[{i}] must be an object")
            flat.extend(_flatten_scene_dict(s, i))
        scenes = [Scene.from_dict(s, i) for i, s in enumerate(flat)]
        for s in scenes:
            if not s.text:
                raise ValueError(f"scene {s.id} has empty text")
        vs = d.get("visual_style") or d.get("character_style")
        return Script(
            schema=str(d.get("schema") or "dup.content_script.v1"),
            title=str(d.get("title") or "untitled").strip(),
            description=str(d.get("description") or "").strip(),
            tags=[str(t) for t in (d.get("tags") or [])],
            language=str(d.get("language") or "en"),
            aspect=str(d.get("aspect") or "9:16"),
            scenes=scenes,
            visual_style=(str(vs).strip().lower() if vs else None),
        )

    def to_dict(self) -> dict[str, Any]:
        row = {
            "schema": self.schema,
            "title": self.title,
            "description": self.description,
            "tags": list(self.tags),
            "language": self.language,
            "aspect": self.aspect,
            "scenes": [s.to_dict() for s in self.scenes],
        }
        if self.visual_style:
            row["visual_style"] = self.visual_style
        return row


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
