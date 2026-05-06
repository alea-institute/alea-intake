"""Tests for the practice-area YAML loader and registry."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.services.intake.practice_areas import (
    PracticeArea,
    PracticeAreaConfigError,
    PracticeAreaRegistry,
    load_practice_areas,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_YAML = textwrap.dedent(
    """
    id: personal_injury
    display_name: Personal Injury
    welcome_message_consumer: |
      Welcome (consumer).
    welcome_message_professional: |
      Welcome (professional).
    system_prompt: |
      You are a legal intake assistant.
    key_topics:
      - Incident facts
      - Injuries
    disclaimer: null
    """
).strip()


def _write(dir_: Path, name: str, body: str) -> Path:
    p = dir_ / name
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Bundled config (the real PI seed must always load)
# ---------------------------------------------------------------------------


def test_load_bundled_personal_injury_config() -> None:
    """The shipped PI YAML file must load and expose the expected id."""
    bundled_dir = (
        Path(__file__).resolve().parent.parent
        / "app"
        / "services"
        / "intake"
        / "practice_areas"
        / "configs"
    )

    registry = load_practice_areas(bundled_dir)
    ids = [a.id for a in registry.list_all()]
    assert ids == ["personal_injury"], ids

    pi = registry.get("personal_injury")
    assert pi is not None
    assert pi.display_name == "Personal Injury"
    assert pi.welcome_message_consumer.strip()
    assert pi.welcome_message_professional.strip()
    assert pi.system_prompt.strip()
    assert len(pi.key_topics) >= 5


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_loads_single_yaml(tmp_path: Path) -> None:
    _write(tmp_path, "pi.yaml", _VALID_YAML)

    registry = load_practice_areas(tmp_path)

    assert isinstance(registry, PracticeAreaRegistry)
    assert len(registry) == 1
    assert "personal_injury" in registry
    area = registry.get("personal_injury")
    assert isinstance(area, PracticeArea)
    assert area.disclaimer is None
    assert area.key_topics == ["Incident facts", "Injuries"]


def test_list_all_sorted_by_display_name(tmp_path: Path) -> None:
    _write(tmp_path, "pi.yaml", _VALID_YAML)
    _write(
        tmp_path,
        "fam.yaml",
        _VALID_YAML.replace("id: personal_injury", "id: family_law").replace(
            "display_name: Personal Injury", "display_name: Family Law"
        ),
    )

    registry = load_practice_areas(tmp_path)
    names = [a.display_name for a in registry.list_all()]
    assert names == ["Family Law", "Personal Injury"]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_missing_required_field_raises(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace(
        "system_prompt: |\n  You are a legal intake assistant.\n", ""
    )
    bad_path = _write(tmp_path, "bad.yaml", bad)

    with pytest.raises(PracticeAreaConfigError) as exc:
        load_practice_areas(tmp_path)

    msg = str(exc.value)
    assert str(bad_path) in msg
    assert "system_prompt" in msg


def test_invalid_id_format_raises(tmp_path: Path) -> None:
    bad = _VALID_YAML.replace("id: personal_injury", "id: Personal-Injury!")
    bad_path = _write(tmp_path, "bad_id.yaml", bad)

    with pytest.raises(PracticeAreaConfigError) as exc:
        load_practice_areas(tmp_path)

    msg = str(exc.value)
    assert str(bad_path) in msg
    assert "slug" in msg.lower() or "id" in msg.lower()


def test_duplicate_id_raises_with_both_paths(tmp_path: Path) -> None:
    p1 = _write(tmp_path, "a.yaml", _VALID_YAML)
    p2 = _write(tmp_path, "b.yaml", _VALID_YAML)

    with pytest.raises(PracticeAreaConfigError) as exc:
        load_practice_areas(tmp_path)

    msg = str(exc.value)
    assert str(p1) in msg
    assert str(p2) in msg
    assert "personal_injury" in msg


def test_invalid_yaml_syntax_raises(tmp_path: Path) -> None:
    bad_path = _write(tmp_path, "broken.yaml", "id: personal_injury\n  : : :\n")

    with pytest.raises(PracticeAreaConfigError) as exc:
        load_practice_areas(tmp_path)

    assert str(bad_path) in str(exc.value)


def test_empty_file_raises(tmp_path: Path) -> None:
    bad_path = _write(tmp_path, "empty.yaml", "")

    with pytest.raises(PracticeAreaConfigError) as exc:
        load_practice_areas(tmp_path)

    assert str(bad_path) in str(exc.value)


def test_non_mapping_top_level_raises(tmp_path: Path) -> None:
    bad_path = _write(tmp_path, "list.yaml", "- a\n- b\n")

    with pytest.raises(PracticeAreaConfigError) as exc:
        load_practice_areas(tmp_path)

    assert str(bad_path) in str(exc.value)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_directory_returns_empty_registry(tmp_path: Path) -> None:
    registry = load_practice_areas(tmp_path)
    assert isinstance(registry, PracticeAreaRegistry)
    assert len(registry) == 0
    assert registry.list_all() == []


def test_missing_directory_returns_empty_registry(tmp_path: Path) -> None:
    registry = load_practice_areas(tmp_path / "does_not_exist")
    assert len(registry) == 0


def test_non_yaml_files_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "pi.yaml", _VALID_YAML)
    _write(tmp_path, "README.md", "# notes\n")
    _write(tmp_path, "junk.txt", "ignore me")

    registry = load_practice_areas(tmp_path)
    assert len(registry) == 1
    assert "personal_injury" in registry


def test_registry_register_rejects_duplicate() -> None:
    reg = PracticeAreaRegistry()
    area = PracticeArea(
        id="personal_injury",
        display_name="PI",
        welcome_message_consumer="hi",
        welcome_message_professional="hi pro",
        system_prompt="be helpful",
        key_topics=["a"],
    )
    reg.register(area)
    with pytest.raises(ValueError):
        reg.register(area)
