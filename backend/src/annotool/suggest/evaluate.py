"""How good are the suggestions? Compare suggested boxes with hand-made ones (roadmap 4.2).

Ground truth is the person's own work: element boxes made by hand (`human`) or in v2
(`legacy`) that are accepted or edited. Boxes that started as suggestions are left out,
even when accepted, because the suggester shaped them.

Boxes are matched one to one, best overlap first, when IoU ≥ MATCH_IOU. Then:
- recall = matched / hand-made boxes, precision = matched / suggested boxes;
- per attribute, over matched pairs where the person gave a value:
  accuracy = right / suggested a value, coverage = suggested a value / labeled;
- a confusion table counts (person's value, suggested value) pairs.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from annotool.models import Annotation
from annotool.suggest.base import iou

MATCH_IOU = 0.5
TRUTH_SOURCES = ("human", "legacy")


def ground_truth(boxes: Sequence[Annotation]) -> list[Annotation]:
    return [
        b
        for b in boxes
        if b.kind == "element" and b.status in ("accepted", "edited") and b.source in TRUTH_SOURCES
    ]


def _ratio(n: int, d: int) -> float | None:
    return n / d if d else None


@dataclass
class AttributeEval:
    labeled: int = 0  # matched pairs where the person gave a value
    suggested: int = 0  # …and the suggestion has one too
    correct: int = 0  # …and they agree

    @property
    def accuracy(self) -> float | None:
        return _ratio(self.correct, self.suggested)

    @property
    def coverage(self) -> float | None:
        return _ratio(self.suggested, self.labeled)


@dataclass
class PageEval:
    truth: int = 0
    proposed: int = 0
    matched: int = 0
    pairs: list[tuple[str, str]] = field(default_factory=list)  # (truth id, suggestion id)
    attributes: dict[str, AttributeEval] = field(default_factory=dict)
    confusion: dict[str, Counter] = field(default_factory=dict)  # attr -> (truth, suggested)

    @property
    def recall(self) -> float | None:
        return _ratio(self.matched, self.truth)

    @property
    def precision(self) -> float | None:
        return _ratio(self.matched, self.proposed)


def evaluate(
    truth: Sequence[Annotation], proposed: Sequence[Annotation], attribute_ids: Sequence[str]
) -> PageEval:
    candidates = sorted(
        (
            (iou(t.bbox, p.bbox), ti, pi)
            for ti, t in enumerate(truth)
            for pi, p in enumerate(proposed)
        ),
        key=lambda c: -c[0],
    )
    used_t: set[int] = set()
    used_p: set[int] = set()
    result = PageEval(
        truth=len(truth),
        proposed=len(proposed),
        attributes={a: AttributeEval() for a in attribute_ids},
        confusion={a: Counter() for a in attribute_ids},
    )
    for overlap, ti, pi in candidates:
        if overlap < MATCH_IOU:
            break
        if ti in used_t or pi in used_p:
            continue
        used_t.add(ti)
        used_p.add(pi)
        t, p = truth[ti], proposed[pi]
        result.pairs.append((t.id, p.id))
        for attr in attribute_ids:
            wanted = t.labels.get(attr)
            if wanted is None:
                continue
            got = p.labels.get(attr)
            stats = result.attributes[attr]
            stats.labeled += 1
            result.confusion[attr][(wanted, got)] += 1
            if got is not None:
                stats.suggested += 1
                stats.correct += got == wanted
    result.matched = len(result.pairs)
    return result


def summarize(results: Sequence[PageEval]) -> PageEval:
    """All pages together (sums, so big pages weigh more)."""
    total = PageEval()
    for r in results:
        total.truth += r.truth
        total.proposed += r.proposed
        total.matched += r.matched
        total.pairs += r.pairs
        for attr, stats in r.attributes.items():
            mine = total.attributes.setdefault(attr, AttributeEval())
            mine.labeled += stats.labeled
            mine.suggested += stats.suggested
            mine.correct += stats.correct
        for attr, counts in r.confusion.items():
            total.confusion.setdefault(attr, Counter()).update(counts)
    return total


def fraction(n: int, d: int) -> str:
    return f"{n}/{d} ({round(100 * n / d)}%)" if d else f"{n}/{d} (—)"


def markdown(title: str, result: PageEval, attribute_ids: Sequence[str]) -> str:
    lines = [
        f"### {title}",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Box recall (IoU ≥ {MATCH_IOU}) | {fraction(result.matched, result.truth)} |",
        f"| Box precision | {fraction(result.matched, result.proposed)} |",
        "",
        "| Attribute | Accuracy | Coverage |",
        "|---|---|---|",
    ]
    for attr in attribute_ids:
        s = result.attributes.get(attr, AttributeEval())
        lines.append(
            f"| {attr} | {fraction(s.correct, s.suggested)} | {fraction(s.suggested, s.labeled)} |"
        )
    return "\n".join(lines)


def confusion_markdown(attr: str, result: PageEval) -> str:
    counts = result.confusion.get(attr) or Counter()
    lines = [f"| {attr}: by hand | Suggested | Boxes |", "|---|---|---|"]
    for (wanted, got), n in counts.most_common():
        lines.append(f"| {wanted} | {got or '—'} | {n} |")
    return "\n".join(lines)
