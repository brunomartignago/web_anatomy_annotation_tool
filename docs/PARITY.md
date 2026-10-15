# Parity with the legacy v2 tool (roadmap 2.6)

Every feature of `legacy/annotation_tool_v2.py` (its docstring, toolbar, key bindings and
mouse handlers) and where it lives in the new annotator. **✅** = works the same or better ·
**➡️** = intentionally replaced (with the reason) · **⏭** = coming in a later roadmap item.

Checked against the code on 2026-10-15. Every ✅ row is covered by a frontend test, except
native browser scrolling (wheel, Shift+wheel), which needs no code of ours.

## Tools and selection

| v2 | New annotator | |
|---|---|---|
| `D` draw mode, `S` select mode, toolbar toggle | Same keys, plus **Draw** / **Select** buttons in the toolbar. Draw is the default, as in v2. | ✅ |
| Drag to draw; boxes under 4 px ignored | Same (4 page px). Coordinates are normalized and clamped to the page. | ✅ |
| Click selects the **smallest** box under the cursor | Same hit test (`editor/geometry.ts › hitTest`). | ✅ |
| Shift+click adds/removes | Same. | ✅ |
| Rubber-band drag selects boxes it touches; Shift adds | Same. | ✅ |
| Click on an already selected box keeps a multi-selection ("allow drag in future") | Replaced: a click selects just that box; Shift+click keeps the others. Moving boxes isn't in v2 either; it's a later feature. | ➡️ |
| `Escape` deselects / cancels a draw | Same (cancels a drag in progress first). | ✅ |
| `Delete` / `X` deletes the selection; toolbar Delete | Same, plus `Backspace` and a toolbar **Delete** button. | ✅ |
| `Ctrl+Z` undo, `Ctrl+Shift+Z` redo, toolbar buttons, 60 steps | Same, plus `Ctrl+Y`; 200 steps stored as immer patches. The first undo now always does something (AUDIT #8). | ✅ |
| `Tab` / `Shift+Tab`: next / previous unannotated box, wrapping, scrolls to it | Same (`panels/labels.ts › nextIncomplete`); rejected boxes are skipped. **Trade-off:** like v2, Tab no longer moves keyboard focus between buttons; keyboard access to every label arrives in 3.1. | ✅ |

## Labeling

| v2 | New annotator | |
|---|---|---|
| Inline label panel, one group per attribute, applies to all selected boxes | Same, built from `web-ui.yaml` (no hardcoded labels). Each click is one undo step. | ✅ |
| Panel title "N boxes selected"; each group shows its value, `—` or `mixed` | Same, plus a count per value for mixed selections. | ✅ |
| Clicking a value always sets it; no way to remove a value | Same, plus a per-attribute **×** to clear it. Clicking the value already set does nothing, so confirming can't delete. | ✅ |
| `1`–`9` quick-pick in the "focused" group, auto-advancing (focus was invisible and went stale, AUDIT #1, #2) | Replaced by 3.1 (attribute hotkeys `f n c t` + one-letter mnemonics for **every** option) and 3.2 (presets `1`–`9`). Until then, labels are applied with the mouse. | ⏭ |
| `Enter` confirm, arrow keys between options (documented, never implemented, AUDIT #3) | Not needed: a click applies immediately. Keyboard picking is 3.1. | ➡️ |

## Box list and progress

| v2 | New annotator | |
|---|---|---|
| Selection list with All / Empty / Partial / Done filters | Same filters, with counts. | ✅ |
| List row: colored dot, `#n`, area in px², chips `F:Typo C:—`… | Dot, number and the labels in taxonomy order (or "unlabeled"). Area dropped: it's derivable from the box (AUDIT #10). | ✅ |
| Clicking a row selects it (Shift toggles) and scrolls the canvas to it | Same; the box is centered. The list also follows selections made on the canvas. | ✅ |
| Progress per attribute (%) and "n / N complete" | Same, live, as counts and bars; rejected boxes don't count. | ✅ |
| Box colors: empty red, partial yellow, complete green, selected blue | Same palette. | ✅ |
| Index number drawn inside each box | Drawn just above the box so it doesn't cover text. | ✅ |

## Canvas

| v2 | New annotator | |
|---|---|---|
| `+` / `-` and toolbar zoom, `Ctrl`+wheel zoom | Same, plus toolbar **−** / **+**; wheel zoom keeps the point under the cursor still. | ✅ |
| `Ctrl+0` "reset": fit the whole image to the screen | Fits the page **width** (toolbar **Fit**). Pages are up to 91,086 px tall, so fitting the height would make them unreadable. | ➡️ |
| Zoom range 5 %–1000 %, full image resized on every step (AUDIT #11) | 20 %–400 %, lazy 2048-px strips: 60 fps and under 150 MB on the 91,086 px page (2.3). The minimum keeps memory bounded. | ➡️ |
| Wheel scroll, `Shift`+wheel horizontal, Linux buttons 4/5 | Native browser scrolling. | ✅ |
| Middle-drag pan | Same, plus `Space`+drag. | ✅ |
| Status bar: cursor `x:… y:…` in image px | Same (page px), in the status bar. | ✅ |
| Status bar: mode hints | Status bar shows the tool, selection count and save state; buttons have tooltips with their keys. | ✅ |
| Window maximized with `root.state('zoomed')` (Windows only, AUDIT #9) | It's a browser tab. | ➡️ |

## Files

| v2 | New annotator | |
|---|---|---|
| `Ctrl+O` load image via a file dialog; one image at a time (AUDIT #4) | Replaced by projects: `annotool serve --project <name>` lists every captured page; `]` / `[` move through them. | ➡️ |
| `Ctrl+Shift+O` load annotations; image not checked against the JSON (AUDIT #5) | Replaced: each page folder holds its own `page.png` + `annotations.json`, loaded together. Legacy files are converted once with `annotool migrate`. | ➡️ |
| `Ctrl+S` "Save as" dialog every time (AUDIT #6) | `Ctrl+S` saves immediately (no dialog); normally unnecessary because of autosave. | ✅ |
| Autosave next to the image after each edit, but not after undo (AUDIT #7); restore prompt on load | Autosave 800 ms after any change **including undo/redo**, with an ETag so a file changed elsewhere is never overwritten. No restore prompt needed. Leaving a page saves it; closing the tab with unsaved edits asks first. | ✅ |
| Saved file: `selections` with `coords`, `Area`, `expanded`, list-position ids (AUDIT #10, #14, #15) | Schema v1 `annotations.json`: ULID ids, `[x, y, w, h]`, sources and statuses, taxonomy version. | ➡️ |

## Not carried over

Nothing from v2 is dropped without a replacement. The one temporary gap is **keyboard
labeling** (v2's `1`–`9`), which returns, extended to every option, in roadmap 3.1–3.2.
