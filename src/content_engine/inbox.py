"""Local inbox queue — drop script.json files, render offline (no keys)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_engine.journal import append_job
from content_engine.pipeline import PACKAGE_ROOT, run_pipeline


DEFAULT_INBOX = PACKAGE_ROOT / "inbox"


def approve_dir(inbox_dir: Path | None = None) -> Path:
    root = inbox_dir or DEFAULT_INBOX
    d = root / "approved"
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_approved(script_path: Path, *, inbox_dir: Path | None = None) -> bool:
    """True if inbox/approved/<stem>.ok or <name>.ok exists (Telegram-style gate, local)."""
    approved = approve_dir(inbox_dir)
    stem_ok = approved / f"{script_path.stem}.ok"
    name_ok = approved / f"{script_path.name}.ok"
    return stem_ok.is_file() or name_ok.is_file()


def approve_script(name: str, *, inbox_dir: Path | None = None) -> dict[str, Any]:
    """Mark a pending inbox script as approved for process (local gate)."""
    root = inbox_dir or DEFAULT_INBOX
    root.mkdir(parents=True, exist_ok=True)
    raw = (name or "").strip()
    if not raw:
        return {"ok": False, "error": "name required"}
    cand = root / Path(raw).name
    if not cand.is_file():
        # allow approving by stem match
        matches = list(root.glob(f"{Path(raw).stem}*.json"))
        cand = matches[0] if matches else cand
    if not cand.is_file():
        return {"ok": False, "error": f"pending script not found: {raw}"}
    marker = approve_dir(root) / f"{cand.stem}.ok"
    marker.write_text(
        json.dumps(
            {
                "script": cand.name,
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "honesty": (
                    "Local approve gate — stand-in for Telegram remote approve. "
                    "Not a Telegram Bot API claim unless TELEGRAM_BOT_TOKEN wired later."
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "script": cand.name,
        "marker": str(marker),
        "rel": f"inbox/approved/{marker.name}",
    }


def list_approve_state(*, inbox_dir: Path | None = None) -> dict[str, Any]:
    root = inbox_dir or DEFAULT_INBOX
    root.mkdir(parents=True, exist_ok=True)
    pending = sorted([p.name for p in root.glob("*.json") if p.is_file()])
    approved = []
    waiting = []
    for name in pending:
        p = root / name
        if is_approved(p, inbox_dir=root):
            approved.append(name)
        else:
            waiting.append(name)
    return {
        "ok": True,
        "pending": pending,
        "approved": approved,
        "waiting_approve": waiting,
        "require_approve": True,
        "honesty": (
            "Inbox process skips scripts without inbox/approved/<stem>.ok "
            "(local Telegram-style approve). Not remote Bot API."
        ),
    }


def process_inbox(
    inbox_dir: Path | None = None,
    *,
    out_dir: Path | None = None,
    offline_tts: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
    finish: bool = True,
    require_approve: bool = False,
) -> dict[str, Any]:
    """
    Process *.json scripts in inbox/.
    Success → inbox/done/; fail → inbox/refuse/; evidence under out/inbox/.
    On ALLOW (+finish): local copy+bundle+ready — no auto-post.
    When require_approve: only scripts with inbox/approved/<stem>.ok run
    (local Telegram-style gate; default off for CI/fixture compatibility).
    """
    root = inbox_dir or DEFAULT_INBOX
    root.mkdir(parents=True, exist_ok=True)
    done = root / "done"
    refuse = root / "refuse"
    done.mkdir(exist_ok=True)
    refuse.mkdir(exist_ok=True)
    approve_dir(root)
    dest_out = out_dir or (PACKAGE_ROOT / "out" / "inbox")
    dest_out.mkdir(parents=True, exist_ok=True)

    scripts = sorted(
        [p for p in root.glob("*.json") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )
    skipped_unapproved: list[str] = []
    if require_approve:
        runnable = []
        for p in scripts:
            if is_approved(p, inbox_dir=root):
                runnable.append(p)
            else:
                skipped_unapproved.append(p.name)
        scripts = runnable
    if limit is not None:
        scripts = scripts[: max(0, limit)]

    results: list[dict[str, Any]] = []
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "pending": [str(p.name) for p in scripts],
            "skipped_unapproved": skipped_unapproved,
            "count": len(scripts),
            "inbox": str(root),
            "require_approve": require_approve,
        }

    allow_n = 0
    for script_path in scripts:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_out = dest_out / f"{stamp}_{script_path.stem}"
        try:
            report = run_pipeline(
                script_path,
                work_dir=PACKAGE_ROOT / "workspace",
                out_dir=run_out,
                allow_network_tts=not offline_tts,
            )
            finish_info = None
            if finish and report.ok and report.output_mp4 and report.pack_path:
                from content_engine.finish_kit import finish_allow_run

                # Script already moved below — finish uses rendered .script.json sibling
                sib = Path(report.output_mp4).with_suffix(".script.json")
                finish_info = finish_allow_run(
                    Path(report.output_mp4),
                    Path(report.pack_path),
                    script_path=sib if sib.is_file() else None,
                    ship_dir=run_out / "ship",
                )
            row = {
                "script": script_path.name,
                "ok": report.ok,
                "out": str(run_out),
                "pack": report.pack_path,
                "mp4": report.output_mp4,
                "detail": report.gate.detail if report.gate else "",
                "finish": finish_info,
            }
            target_dir = done if report.ok else refuse
            shutil.move(str(script_path), str(target_dir / f"{stamp}_{script_path.name}"))
            # consume approve marker
            for marker in (
                approve_dir(root) / f"{script_path.stem}.ok",
                approve_dir(root) / f"{script_path.name}.ok",
            ):
                marker.unlink(missing_ok=True)
            if report.ok:
                allow_n += 1
            append_job(
                {
                    "event": "inbox_allow" if report.ok else "inbox_refuse",
                    "script": script_path.name,
                    "out": str(run_out),
                }
            )
        except Exception as exc:  # noqa: BLE001
            row = {"script": script_path.name, "ok": False, "error": str(exc)}
            try:
                shutil.move(
                    str(script_path),
                    str(refuse / f"{stamp}_{script_path.name}"),
                )
            except OSError:
                pass
            append_job({"event": "inbox_error", "script": script_path.name, "error": str(exc)})
        results.append(row)

    summary = {
        "ok": True,
        "inbox": str(root),
        "processed": len(results),
        "allow_count": allow_n,
        "skipped_unapproved": skipped_unapproved,
        "require_approve": require_approve,
        "results": results,
        "honesty": (
            "Inbox queue is local render only — ALLOW ≠ growth; no auto-post. "
            "Approve gate: inbox/approved/<stem>.ok (local Telegram-style)."
        ),
    }
    (dest_out / "INBOX_LAST.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
