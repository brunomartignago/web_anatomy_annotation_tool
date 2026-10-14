import copy
from pathlib import Path

import pytest

from annotool.taxonomy import TaxonomyError, load_taxonomy, parse_taxonomy

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_UI_YAML = REPO_ROOT / "taxonomies" / "web-ui.yaml"

MINIMAL = {
    "id": "mini",
    "version": "1.0",
    "name": "Minimal taxonomy",
    "attributes": [
        {
            "id": "Form",
            "hotkey": "f",
            "options": [
                {"value": "Typo", "key": "t"},
                {"value": "Image", "key": "i"},
                {"value": "Space", "key": "s", "status": "proposed"},
            ],
        },
        {
            "id": "Function",
            "hotkey": "n",
            "options": [
                {"value": "Text", "key": "t"},
                {"value": "Link", "key": "l"},
            ],
        },
    ],
    "presets": [
        {"key": "1", "labels": {"Form": "Typo", "Function": "Text"}},
    ],
}


def minimal():
    return copy.deepcopy(MINIMAL)


def errors_of(data) -> list[str]:
    with pytest.raises(TaxonomyError) as exc_info:
        parse_taxonomy(data)
    return exc_info.value.errors


# ── The real taxonomy ────────────────────────────────────────────────────────


def test_web_ui_yaml_loads():
    tax = load_taxonomy(WEB_UI_YAML)
    assert tax.id == "web-ui"
    assert [a.id for a in tax.attributes] == ["Form", "Function", "Component", "Taxonomy"]
    assert len(tax.presets) == 9


def test_web_ui_active_and_proposed_options():
    section = load_taxonomy(WEB_UI_YAML).attribute("Taxonomy")
    assert [o.value for o in section.proposed_options] == ["Column 5", "Overlay"]
    assert len(section.active_options) == 12  # the 12 values the v2 tool offered
    assert "Column 5" not in section.active_values


def test_attribute_label_defaults_to_id():
    tax = load_taxonomy(WEB_UI_YAML)
    assert tax.attribute("Form").label == "Form"
    assert tax.attribute("Taxonomy").label == "Template section"


def test_unknown_attribute_lookup_raises_key_error():
    tax = parse_taxonomy(minimal())
    with pytest.raises(KeyError):
        tax.attribute("Colour")


# ── Acceptance: duplicate keys and unknown preset values ─────────────────────


def test_duplicate_option_key_in_attribute_is_rejected():
    data = minimal()
    data["attributes"][0]["options"][1]["key"] = "t"  # Image now clashes with Typo
    errors = errors_of(data)
    assert any("Form" in e and "duplicate key 't'" in e for e in errors)


def test_same_key_in_different_attributes_is_allowed():
    # Typo (Form) and Text (Function) both use "t" in MINIMAL.
    parse_taxonomy(minimal())


def test_preset_with_unknown_value_is_rejected():
    data = minimal()
    data["presets"][0]["labels"]["Function"] = "Heading"
    errors = errors_of(data)
    assert any("preset '1'" in e and "'Heading'" in e and "Function" in e for e in errors)


def test_preset_with_unknown_attribute_is_rejected():
    data = minimal()
    data["presets"][0]["labels"]["Colour"] = "Red"
    errors = errors_of(data)
    assert any("preset '1'" in e and "unknown attribute 'Colour'" in e for e in errors)


def test_preset_with_proposed_value_is_rejected():
    data = minimal()
    data["presets"][0]["labels"]["Form"] = "Space"
    errors = errors_of(data)
    assert any("preset '1'" in e and "proposed" in e for e in errors)


# ── Other structural checks ──────────────────────────────────────────────────


def test_duplicate_option_value_is_rejected():
    data = minimal()
    data["attributes"][1]["options"].append({"value": "Text", "key": "x"})
    errors = errors_of(data)
    assert any("Function" in e and "duplicate value 'Text'" in e for e in errors)


def test_duplicate_attribute_id_and_hotkey_are_rejected():
    data = minimal()
    data["attributes"][1]["id"] = "Form"
    data["attributes"][1]["hotkey"] = "f"
    errors = errors_of(data)
    assert any("duplicate attribute id 'Form'" in e for e in errors)
    assert any("duplicate attribute hotkey 'f'" in e for e in errors)


def test_duplicate_preset_key_is_rejected():
    data = minimal()
    data["presets"].append({"key": "1", "labels": {"Form": "Image"}})
    errors = errors_of(data)
    assert any("duplicate preset key '1'" in e for e in errors)


def test_all_problems_are_reported_together():
    data = minimal()
    data["attributes"][0]["options"][1]["key"] = "t"
    data["presets"][0]["labels"]["Function"] = "Heading"
    assert len(errors_of(data)) == 2


@pytest.mark.parametrize(
    "option",
    [
        {"value": "Image", "key": 0},  # unquoted number in YAML
        {"value": False, "key": "i"},  # YAML turns a bare `No` into a boolean
        {"value": "Image", "key": "im"},  # mnemonic must be one keystroke
        {"value": "Image", "key": "i", "status": "draft"},
        {"value": "Image", "key": "i", "stauts": "proposed"},  # typo'd field name
    ],
)
def test_malformed_option_is_rejected(option):
    data = minimal()
    data["attributes"][0]["options"][1] = option
    assert errors_of(data)


def test_load_reports_file_and_yaml_errors(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: [unclosed", encoding="utf-8")
    with pytest.raises(TaxonomyError):
        load_taxonomy(bad)
    with pytest.raises(TaxonomyError):
        load_taxonomy(tmp_path / "missing.yaml")
