"""The suggester protocol and the merge policy (docs/ARCHITECTURE.md › suggestion pipeline).

A suggester looks at a page and returns proposals: add a box, or label an existing one.
`merge` folds one suggester's proposals into the page, and `run_suggesters` runs several in
a fixed order (dom → rule → prior), each seeing the result of the ones before it.

Merge policy:
- A label a person gave is never overwritten. That covers the sources `human`, `preset`,
  `legacy` (labeled by hand in v2), `inherited` (from a section a person labeled), and any
  value whose source isn't recorded.
- Between suggesters, higher confidence wins; a tie goes to the later suggester. A label
  without a confidence counts as 0.
- A proposed box that overlaps an existing box of the same kind (IoU ≥ MATCH_IOU) labels
  that box instead, so running the suggesters again adds nothing. A box matching one the
  person rejected is not proposed again, and rejected boxes are never relabeled.
- Only active taxonomy values are accepted; anything else is dropped and reported.
- New boxes are `status: suggested`. A box a person already reviewed keeps its status:
  `label_sources` shows which of its labels are still unreviewed suggestions.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ValidationError

from annotool.ids import new_ulid
from annotool.models import Annotation, BBox, DomRef, Kind, PageFile
from annotool.taxonomy import Taxonomy

# Sources a suggester may use as its id (`human`, `legacy` are not suggesters).
SUGGESTER_SOURCES = ("dom", "rule", "prior", "model", "llm")
# Boxes overlapping at least this much (intersection over union) are the same box.
MATCH_IOU = 0.9


@dataclass(frozen=True)
class AddBox:
    """Propose a new box (or, if it matches an existing box, labels for that box)."""

    bbox: tuple[float, float, float, float]
    kind: Kind = "element"
    labels: Mapping[str, str] = field(default_factory=dict)
    confidence: Mapping[str, float] = field(default_factory=dict)
    dom: DomRef | None = None


@dataclass(frozen=True)
class LabelBox:
    """Propose labels for a box that is already on the page."""

    box_id: str
    labels: Mapping[str, str]
    confidence: Mapping[str, float] = field(default_factory=dict)


Proposal = AddBox | LabelBox


@dataclass(frozen=True)
class SuggestContext:
    """What a suggester gets: the page as merged so far, the taxonomy, and the page folder
    (dom.json, meta.json, page.png), which is None for pages that only exist in memory."""

    page: PageFile
    taxonomy: Taxonomy
    folder: Path | None = None


class Suggester(Protocol):
    id: str  # one of SUGGESTER_SOURCES; recorded as the box / label source

    def suggest(self, context: SuggestContext) -> Sequence[Proposal]: ...


class MergeReport(BaseModel):
    """What one suggester did to one page."""

    suggester: str
    boxes_added: int = 0
    boxes_matched: int = 0  # proposed boxes that turned out to be existing ones
    labels_set: int = 0
    kept_human: int = 0  # proposals that would have overwritten a person's label
    kept_better: int = 0  # proposals with less confidence than the current suggestion
    skipped_rejected: int = 0
    dropped: list[str] = []  # invalid proposals, with the reason
    error: str | None = None  # the suggester crashed; the page is unchanged by it
    changed: bool = False


def iou(a: BBox | tuple[float, ...], b: BBox | tuple[float, ...]) -> float:
    """Intersection over union of two [x, y, w, h] boxes."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _problem(taxonomy: Taxonomy, attr_id: str, value: str) -> str | None:
    attribute = next((a for a in taxonomy.attributes if a.id == attr_id), None)
    if attribute is None:
        return f"unknown attribute {attr_id!r}"
    option = next((o for o in attribute.options if o.value == value), None)
    if option is None:
        return f"{attr_id} value {value!r} is not an option"
    if not option.is_active:
        return f"{attr_id} value {value!r} is proposed, not active"
    return None


class _Merger:
    def __init__(self, source: str, taxonomy: Taxonomy, now: datetime, report: MergeReport):
        self.source = source
        self.taxonomy = taxonomy
        self.now = now
        self.report = report

    def valid_labels(self, where: str, labels: Mapping[str, str]) -> dict[str, str]:
        valid = {}
        for attr_id, value in labels.items():
            problem = _problem(self.taxonomy, attr_id, value)
            if problem:
                self.report.dropped.append(f"{where}: {problem}")
            else:
                valid[attr_id] = value
        return valid

    def label(self, box: Annotation, labels: Mapping[str, str], confidence: Mapping[str, float]):
        """Apply proposed labels to an existing box. Returns True if anything changed."""
        changed = False
        for attr_id, value in self.valid_labels(box.id, labels).items():
            current = box.labels.get(attr_id)
            if current == value:
                continue
            if current is not None:
                current_source = (box.label_sources or {}).get(attr_id)
                if current_source not in SUGGESTER_SOURCES:
                    self.report.kept_human += 1
                    continue
                if confidence.get(attr_id, 0.0) < (box.confidence or {}).get(attr_id, 0.0):
                    self.report.kept_better += 1
                    continue
            box.labels[attr_id] = value
            box.label_sources = {**(box.label_sources or {}), attr_id: self.source}
            scores = {k: v for k, v in (box.confidence or {}).items() if k != attr_id}
            if attr_id in confidence:
                scores[attr_id] = confidence[attr_id]
            box.confidence = scores or None
            self.report.labels_set += 1
            changed = True
        return changed

    def new_box(self, proposal: AddBox) -> Annotation | None:
        labels = self.valid_labels("new box", proposal.labels)
        try:
            box = Annotation(
                id=new_ulid(),
                kind=proposal.kind,
                bbox=proposal.bbox,
                labels=labels,
                source=self.source,
                status="suggested",
                label_sources={a: self.source for a in labels} or None,
                confidence={a: c for a, c in proposal.confidence.items() if a in labels} or None,
                dom=proposal.dom,
                created_at=self.now,
            )
        except ValidationError as exc:
            self.report.dropped.append(f"new box {proposal.bbox}: {exc.errors()[0]['msg']}")
            return None
        self.report.boxes_added += 1
        self.report.labels_set += len(labels)
        return box


def merge(
    page: PageFile,
    proposals: Sequence[Proposal],
    source: str,
    taxonomy: Taxonomy,
    now: datetime,
) -> tuple[PageFile, MergeReport]:
    """Fold one suggester's proposals into the page. The input page is not modified; if
    nothing changes, it is returned as it is."""
    report = MergeReport(suggester=source)
    merger = _Merger(source, taxonomy, now, report)
    boxes = [b.model_copy(deep=True) for b in page.annotations]
    by_id = {b.id: b for b in boxes}
    changed = False

    for proposal in proposals:
        if isinstance(proposal, LabelBox):
            box = by_id.get(proposal.box_id)
            if box is None:
                report.dropped.append(f"no box {proposal.box_id!r} on this page")
            elif box.status == "rejected":
                report.skipped_rejected += 1
            elif merger.label(box, proposal.labels, proposal.confidence):
                box.updated_at = now
                changed = True
            continue

        same_kind = [b for b in boxes if b.kind == proposal.kind]
        match = max(same_kind, key=lambda b: iou(b.bbox, proposal.bbox), default=None)
        if match is not None and iou(match.bbox, proposal.bbox) >= MATCH_IOU:
            if match.status == "rejected":
                report.skipped_rejected += 1
                continue
            report.boxes_matched += 1
            touched = merger.label(match, proposal.labels, proposal.confidence)
            if match.dom is None and proposal.dom is not None:
                match.dom = proposal.dom
                touched = True
            if touched:
                match.updated_at = now
                changed = True
            continue

        box = merger.new_box(proposal)
        if box is not None:
            boxes.append(box)
            by_id[box.id] = box
            changed = True

    report.changed = changed
    return (page.model_copy(update={"annotations": boxes}) if changed else page), report


def run_suggesters(
    page: PageFile,
    suggesters: Sequence[Suggester],
    *,
    taxonomy: Taxonomy,
    folder: Path | None = None,
    now: datetime | None = None,
) -> tuple[PageFile, list[MergeReport]]:
    """Run the suggesters in order, merging each one's proposals before the next runs.
    A suggester that fails is reported and skipped; the others still run."""
    now = now or datetime.now(UTC)
    reports: list[MergeReport] = []
    for suggester in suggesters:
        source = str(getattr(suggester, "id", "?"))
        if source not in SUGGESTER_SOURCES:
            reports.append(
                MergeReport(
                    suggester=source,
                    error=f"{source!r} is not a suggester source ({', '.join(SUGGESTER_SOURCES)})",
                )
            )
            continue
        try:
            context = SuggestContext(page=page, taxonomy=taxonomy, folder=folder)
            proposals = list(suggester.suggest(context))
            page, report = merge(page, proposals, source, taxonomy, now)
        except Exception as exc:  # one broken suggester must not stop the others
            report = MergeReport(suggester=source, error=f"{type(exc).__name__}: {exc}")
        reports.append(report)
    return page, reports
