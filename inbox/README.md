# Inbox queue (offline)

Drop `*.json` scripts here, then:

```bash
python -m content_engine inbox --dry-run
python -m content_engine inbox --limit 1
```

- Success → `done/`
- Gate refuse / errors → `refuse/`
- Artifacts → `out/inbox/`

No API keys. No auto-post. ALLOW ≠ growth.
