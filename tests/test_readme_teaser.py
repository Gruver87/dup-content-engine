from pathlib import Path

from content_engine.readme_teaser import readme_to_script, teaser_meta

ROOT = Path(__file__).resolve().parents[1]


def test_readme_to_script_from_engine_readme(tmp_path: Path):
    src = ROOT / "README.md"
    script = readme_to_script(src, target_sec=30.0, project_name="DUP Content Engine")
    assert len(script.scenes) == 5
    assert all(s.text for s in script.scenes)
    meta = teaser_meta(script, 30.0)
    # Sized for ~25–40s offline bed (gate window is 8–59)
    assert 15.0 <= meta["approx_offline_sec"] <= 45.0


def test_readme_to_script_minimal(tmp_path: Path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Acme Tools — start here\n\n"
        "One-command onboarding for agents.\n\n"
        "```bash\nclone → make bootstrap\n```\n\n"
        "## Honesty\n\n- Bootstrap PASS ≠ soak claim\n",
        encoding="utf-8",
    )
    script = readme_to_script(readme, target_sec=30.0)
    assert "Acme" in script.title or "Acme" in script.scenes[0].text
    assert script.scenes[3].id == "trust"
