# Как самому прогнать тесты и полный запуск

Нужен Python 3.11+. **API-ключи не нужны.**

## Windows (рекомендуется)

Из папки `dup-content-engine`:

```powershell
# 1) Быстро — только unit-тесты
.\scripts\test_me.ps1 -Quick

# 2) Полный офлайн-прогон (doctor → demo → dry-runs → day scripts)
.\scripts\test_me.ps1

# 3) Чуть быстрее полного (без day/series)
.\scripts\test_me.ps1 -SkipSeries

# 4) Боевой day-render одного ролика (дольше)
.\scripts\test_day_render.ps1
```

Или старый verify:

```powershell
.\scripts\verify.ps1
```

## Unix / Git Bash

```bash
bash scripts/test_me.sh --quick
bash scripts/test_me.sh
bash scripts/test_me.sh --skip-series
```

## Что должно получиться

| Артефакт | Где |
|----------|-----|
| Unit tests | `pytest` → все зелёные |
| Demo mp4 + pack | `out/demo/*.mp4`, `verified_pack_*.json` |
| SRT / thumb | `out/demo/*.srt`, `*.thumb.jpg` |
| Preview | `out/demo/preview.html` |
| Calendar | `out/calendar/CALENDAR.md` |
| A/B report | `out/series/*/AB_REPORT.html` |
| Copy / ship / icon | `out/copy/`, `out/ship/`, `out/brand/icon_1024.png` |
| Chapters / RU script | `out/chapters/`, `out/scripts/ru_demo.json` |
| Inbox | `inbox/` + `inbox --dry-run` |

В конце скрипт печатает **`TEST_ME_OK`**.

## Честность

- `ALLOW` = прошёл media/policy gate  
- Это **не** рост аудитории и не soak  
- Publish-команды в `test_me` идут только с `--dry-run` (ключи потом)
