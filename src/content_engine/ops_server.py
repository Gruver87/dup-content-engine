"""Local HTTP ops console — localhost only control room."""

from __future__ import annotations

import json
import mimetypes
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from content_engine import ops_api
from content_engine.pipeline import PACKAGE_ROOT

STATIC = Path(__file__).resolve().parent / "static" / "ops_console.html"


class OpsHandler(BaseHTTPRequestHandler):
    server_version = "DUPOps/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter
        pass

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-Webhook-Token, Authorization",
        )

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def _bytes(self, code: int, data: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path in {"/", "/index.html"}:
            if not STATIC.is_file():
                self._json(500, {"ok": False, "error": f"UI missing: {STATIC}"})
                return
            self._bytes(200, STATIC.read_bytes(), "text/html; charset=utf-8")
            return

        if path == "/api/snapshot":
            self._json(200, ops_api.snapshot())
            return
        if path == "/api/doctor":
            self._json(200, ops_api.doctor_info())
            return
        if path == "/api/studio":
            self._json(200, ops_api.action_studio_catalog())
            return
        if path == "/api/characters":
            self._json(200, ops_api.action_characters_catalog())
            return
        if path == "/api/media/list":
            self._json(200, ops_api.action_media_list())
            return
        if path == "/api/timeline":
            self._json(200, ops_api.action_timeline_get())
            return
        if path == "/api/montage/prefs":
            self._json(200, ops_api.action_montage_prefs())
            return
        if path == "/api/hook-packs":
            self._json(200, ops_api.action_hook_packs({"action": "catalog", "language": "ru"}))
            return
        if path == "/api/project":
            self._json(200, ops_api.action_project_load())
            return
        if path == "/api/library":
            self._json(200, ops_api.list_library())
            return
        if path == "/api/collections":
            self._json(200, ops_api.action_collections({"action": "catalog"}))
            return
        if path == "/api/schedule":
            self._json(200, ops_api.action_schedule({"action": "load"}))
            return
        if path == "/api/inbox":
            self._json(200, ops_api.list_inbox())
            return
        if path in {"/api/webhook/inbox", "/api/webhook"}:
            self._json(200, ops_api.webhook_inbox_help())
            return
        if path.startswith("/api/job/"):
            jid = path.split("/api/job/", 1)[1].strip("/")
            self._json(200, ops_api.get_job(jid))
            return
        if path == "/api/media":
            rel = unquote((qs.get("path") or [""])[0])
            f = ops_api.resolve_media(rel)
            if not f:
                self._json(404, {"ok": False, "error": "not found or outside allowlist"})
                return
            ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self._cors()
            self.end_headers()
            self.wfile.write(data)
            return

        self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            body = self._read_json()
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "invalid JSON"})
            return

        try:
            if path == "/api/demo":
                fixture = body.get("fixture")
                jid = ops_api.action_demo(
                    offline_tts=bool(body.get("offline_tts")),
                    fixture=str(fixture) if fixture else None,
                )
                self._json(200, {"ok": True, "job_id": jid})
                return
            if path == "/api/run":
                jid = ops_api.action_run_script(
                    script_path=body.get("script_path"),
                    script_body=body.get("script") if isinstance(body.get("script"), dict) else None,
                    offline_tts=bool(body.get("offline_tts")),
                )
                self._json(200, {"ok": True, "job_id": jid})
                return
            if path == "/api/write-script":
                self._json(
                    200,
                    ops_api.action_write_script(
                        topic=str(body.get("topic") or ""),
                        language=str(body.get("language") or "ru"),
                        offline=bool(body.get("offline", True)),
                    ),
                )
                return
            if path == "/api/inbox/upload":
                script = body.get("script")
                if script is None and body.get("text"):
                    script = json.loads(str(body["text"]))
                self._json(
                    200,
                    ops_api.save_inbox_script(script, name=body.get("name")),
                )
                return
            if path in {"/api/webhook/inbox", "/api/webhook"}:
                hdrs = {k: v for k, v in self.headers.items()}
                approve = body.get("approve") if isinstance(body, dict) else None
                if "approve" in qs:
                    approve = str(qs.get("approve", [""])[0]).lower() in {
                        "1",
                        "true",
                        "yes",
                        "on",
                    }
                result = ops_api.receive_inbox_webhook(
                    body if body else None,
                    headers=hdrs,
                    approve=approve if approve is not None else None,
                )
                code = 200 if result.get("ok") else 401 if "token" in str(result.get("error") or "") else 400
                self._json(code, result)
                return
            if path == "/api/inbox/process":
                jid = ops_api.action_process_inbox(
                    offline_tts=bool(body.get("offline_tts")),
                    limit=int(body.get("limit") or 5),
                    require_approve=bool(body.get("require_approve")),
                )
                self._json(200, {"ok": True, "job_id": jid})
                return
            if path == "/api/inbox/approve":
                self._json(200, ops_api.action_inbox_approve(body if body else None))
                return
            if path == "/api/cut":
                self._json(200, ops_api.action_transcript_cut(body if body else None))
                return
            if path == "/api/inbox/fixture":
                self._json(200, ops_api.copy_fixture_to_inbox(str(body.get("name") or "")))
                return
            if path == "/api/ready":
                self._json(200, ops_api.action_ready())
                return
            if path == "/api/finish":
                self._json(200, ops_api.action_finish())
                return
            if path == "/api/export":
                self._json(200, ops_api.action_export())
                return
            if path == "/api/ideas":
                self._json(
                    200,
                    ops_api.action_ideas(
                        language=str(body.get("language") or "ru"),
                        offline=bool(body.get("offline", True)),
                    ),
                )
                return
            if path == "/api/hook-packs":
                self._json(200, ops_api.action_hook_packs(body if body else None))
                return
            if path == "/api/styles":
                self._json(200, ops_api.action_styles())
                return
            if path == "/api/status":
                self._json(200, ops_api.action_status())
                return
            if path == "/api/score":
                self._json(200, ops_api.action_score())
                return
            if path == "/api/chapters":
                self._json(200, ops_api.action_chapters())
                return
            if path == "/api/icon":
                self._json(200, ops_api.action_icon())
                return
            if path == "/api/normalize":
                self._json(200, ops_api.action_normalize())
                return
            if path == "/api/jobs":
                self._json(200, ops_api.action_jobs())
                return
            if path == "/api/studio":
                self._json(200, ops_api.action_studio_prefs(body if body else None))
                return
            if path == "/api/characters":
                self._json(200, ops_api.action_characters_prefs(body if body else None))
                return
            if path == "/api/media/upload":
                import base64

                raw = base64.b64decode(str(body.get("b64") or ""))
                self._json(
                    200,
                    ops_api.action_media_upload(
                        str(body.get("filename") or "upload.bin"), raw
                    ),
                )
                return
            if path == "/api/media/import":
                self._json(
                    200,
                    ops_api.action_media_import_url(
                        str(body.get("url") or ""),
                        allow_network=bool(body.get("allow_network", True)),
                    ),
                )
                return
            if path == "/api/media/trim":
                self._json(200, ops_api.action_media_trim(body))
                return
            if path == "/api/media/concat":
                self._json(200, ops_api.action_media_concat(body))
                return
            if path == "/api/media/image-clip":
                self._json(200, ops_api.action_media_image_clip(body))
                return
            if path == "/api/media/delete":
                self._json(200, ops_api.action_media_delete(body))
                return
            if path == "/api/timeline":
                self._json(200, ops_api.action_timeline_save(body))
                return
            if path == "/api/timeline/render":
                jid = ops_api.action_timeline_render(body)
                self._json(200, {"ok": True, "job_id": jid})
                return
            if path == "/api/project/save":
                self._json(200, ops_api.action_project_save(body))
                return
            if path == "/api/project/load":
                self._json(200, ops_api.action_project_load())
                return
            if path == "/api/montage/prefs":
                self._json(200, ops_api.action_montage_prefs(body if body else None))
                return
            if path == "/api/montage/export":
                self._json(200, ops_api.action_montage_export())
                return
            if path == "/api/montage/thumb":
                self._json(200, ops_api.action_montage_thumb(body if body else None))
                return
            if path == "/api/montage/send":
                self._json(200, ops_api.action_montage_send(body))
                return
            if path == "/api/collections":
                self._json(200, ops_api.action_collections(body if body else None))
                return
            if path == "/api/schedule":
                self._json(200, ops_api.action_schedule(body if body else None))
                return
            if path == "/api/open":
                self._json(200, ops_api.action_open_path(str(body.get("which") or "")))
                return
            if path == "/api/upload/asset":
                # {filename, b64, kind}
                import base64

                raw = base64.b64decode(str(body.get("b64") or ""))
                # dual-write: assets/ + library/
                row = ops_api.save_asset(
                    str(body.get("filename") or "upload.bin"),
                    raw,
                    kind=str(body.get("kind") or "media"),
                )
                try:
                    lib = ops_api.action_media_upload(
                        str(body.get("filename") or "upload.bin"), raw
                    )
                    row["library"] = lib
                except Exception:  # noqa: BLE001
                    pass
                self._json(200, row)
                return
        except Exception as exc:  # noqa: BLE001
            self._json(
                500,
                {
                    "ok": False,
                    "error": str(exc),
                    "trace": traceback.format_exc()[-1200:],
                },
            )
            return

        self._json(404, {"ok": False, "error": "not found"})


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("ops console binds localhost only")
    httpd = ThreadingHTTPServer((host, port), OpsHandler)
    url = f"http://{host}:{port}/"
    print(f"DUP Ops Console → {url}")
    print(f"package={PACKAGE_ROOT}")
    print("honesty: ALLOW ≠ growth · local evidence only")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nconsole stopped")
    finally:
        httpd.server_close()
