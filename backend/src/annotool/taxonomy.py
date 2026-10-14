"""Load and validate a taxonomy YAML (e.g. `taxonomies/web-ui.yaml`).

The YAML is the single source of truth for labels, keyboard mnemonics and
presets. Loading checks its structure with pydantic, then runs cross-field
checks (unique values and keys, presets that reference real options) and
reports every problem at once, so a contributor can fix the file in one pass.
"""

from collections import Counter
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    ValidationError,
    model_validator,
)


class TaxonomyError(ValueError):
    """The taxonomy file is missing, unreadable or invalid. `errors` lists every problem."""

    def __init__(self, errors: list[str], source: str = "taxonomy"):
        self.errors = errors
        super().__init__(f"{source} is invalid:\n" + "\n".join(f"  - {e}" for e in errors))


class _Model(BaseModel):
    # Reject unknown fields so a typo like `stauts:` fails loudly instead of being ignored.
    model_config = ConfigDict(extra="forbid")


class Option(_Model):
    value: StrictStr = Field(min_length=1)
    key: StrictStr = Field(min_length=1, max_length=1)  # one keystroke in the UI
    status: Literal["active", "proposed"] = "active"
    note: StrictStr | None = None

    @property
    def is_active(self) -> bool:
        return self.status == "active"


class Attribute(_Model):
    id: StrictStr = Field(min_length=1)
    label: StrictStr
    hotkey: StrictStr = Field(min_length=1, max_length=1)
    question: StrictStr | None = None
    options: list[Option] = Field(min_length=1)
    inherit_from_parent: StrictBool = False
    computed_by_rules: StrictBool = False

    @model_validator(mode="before")
    @classmethod
    def _label_defaults_to_id(cls, data: Any) -> Any:
        if isinstance(data, dict) and "label" not in data:
            data = {**data, "label": data.get("id")}
        return data

    @property
    def active_options(self) -> list[Option]:
        return [o for o in self.options if o.is_active]

    @property
    def proposed_options(self) -> list[Option]:
        return [o for o in self.options if not o.is_active]

    @property
    def active_values(self) -> list[str]:
        return [o.value for o in self.active_options]

    def option(self, value: str) -> Option:
        for o in self.options:
            if o.value == value:
                return o
        raise KeyError(f"{self.id} has no option {value!r}")


class Preset(_Model):
    key: StrictStr = Field(min_length=1, max_length=1)
    labels: dict[StrictStr, StrictStr] = Field(min_length=1)


class Taxonomy(_Model):
    id: StrictStr = Field(min_length=1)
    version: StrictStr = Field(min_length=1)
    name: StrictStr
    description: StrictStr | None = None
    attributes: list[Attribute] = Field(min_length=1)
    presets: list[Preset] = []
    # Suggester settings (sections, dom_hints). Parsed by the suggesters themselves (Phase 4).
    rules: dict[str, Any] = {}

    def attribute(self, attribute_id: str) -> Attribute:
        for a in self.attributes:
            if a.id == attribute_id:
                return a
        raise KeyError(f"taxonomy {self.id!r} has no attribute {attribute_id!r}")


def _duplicates(items: list[str]) -> list[str]:
    return [item for item, count in Counter(items).items() if count > 1]


def _check(tax: Taxonomy) -> list[str]:
    errors: list[str] = []

    for attr_id in _duplicates([a.id for a in tax.attributes]):
        errors.append(f"duplicate attribute id {attr_id!r}")
    for hotkey in _duplicates([a.hotkey for a in tax.attributes]):
        owners = ", ".join(a.id for a in tax.attributes if a.hotkey == hotkey)
        errors.append(f"duplicate attribute hotkey {hotkey!r} ({owners})")

    for attr in tax.attributes:
        for value in _duplicates([o.value for o in attr.options]):
            errors.append(f"attribute {attr.id!r}: duplicate value {value!r}")
        for key in _duplicates([o.key for o in attr.options]):
            owners = ", ".join(o.value for o in attr.options if o.key == key)
            errors.append(f"attribute {attr.id!r}: duplicate key {key!r} ({owners})")

    for key in _duplicates([p.key for p in tax.presets]):
        errors.append(f"duplicate preset key {key!r}")

    attributes = {a.id: a for a in tax.attributes}
    for preset in tax.presets:
        for attr_id, value in preset.labels.items():
            attr = attributes.get(attr_id)
            if attr is None:
                errors.append(f"preset {preset.key!r}: unknown attribute {attr_id!r}")
                continue
            try:
                option = attr.option(value)
            except KeyError:
                errors.append(f"preset {preset.key!r}: {attr_id} value {value!r} is not an option")
                continue
            if not option.is_active:
                errors.append(
                    f"preset {preset.key!r}: {attr_id} value {value!r} is proposed, not active"
                )

    return errors


def _format_validation_error(exc: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(part) for part in err['loc']) or '(root)'}: {err['msg']}"
        for err in exc.errors()
    ]


def parse_taxonomy(data: Any, source: str = "taxonomy") -> Taxonomy:
    """Validate already-loaded YAML data. Raises TaxonomyError listing every problem."""
    try:
        tax = Taxonomy.model_validate(data)
    except ValidationError as exc:
        raise TaxonomyError(_format_validation_error(exc), source) from exc
    errors = _check(tax)
    if errors:
        raise TaxonomyError(errors, source)
    return tax


def load_taxonomy(path: Path) -> Taxonomy:
    """Read and validate a taxonomy YAML file."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TaxonomyError([f"cannot read file: {exc}"], str(path)) from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TaxonomyError([f"not valid YAML: {exc}"], str(path)) from exc
    return parse_taxonomy(data, source=str(path))
