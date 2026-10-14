# Audit of the current tool (October 2026)

This is a snapshot of the legacy code and data before the rewrite. Every item has a matching task in `ROADMAP.md`. The legacy files move to `legacy/` in Phase 0 and are kept as a reference, not maintained.

## What exists

| File | What it does | Notes |
|---|---|---|
| `annotation_tool_v2.py` (1,029 lines) | Tkinter annotator with a keyboard-first workflow, an inline label panel, multi-select, a filtered list, a progress dashboard, undo/redo and autosave | The current tool. Feature parity target for Phase 2. |
| `annotation_tool.py` (856 lines) | v1 annotator with popup label menus | Superseded. Its saved data has defects (see below). |
| `page_capture.py` | Selenium: opens URLs from CSV, scrolls, takes viewport screenshots, stitches them together, writes metadata | Replaced by the Playwright capture in Phase 1. |
| `json_converter.py` | JSON → YOLO txt (class 0 only) + classifier CSV with numeric labels | Replaced by exporters in Phase 5. |
| `websites/public_websites_for_dataset.csv` | Category and URL list | Keep it as the seed list for `examples/`. |
| `images/screenshots/*.png` (88) + `images/metadata/*.json` | Captured pages | About 400 MB. **Never commit.** |
| `json/*.json`, `*.autosave.json` | Annotations | 224 boxes total: 206 on CNN, the rest on Adobe, Khan Academy and Stack Overflow. |
| `labels/`, `csv/` | Old converter output | Disposable. |
| `claude_code/.claude/settings.local.json` | Stray Claude Code settings that only allow a Figma tool | Delete. Claude Code settings belong in `.claude/` at the repo root. |

## Data facts (used to design the new workflow)

- 218 of the 224 boxes are fully labeled.
- **The top 3 Form·Function·Component combos cover about 68% of complete boxes:** Typo·Text·Blank (65), Image·Link·Blank (46) and Typo·Heading·Blank (37). That is why number keys become one-keystroke presets.
- Taxonomy is almost always the section the box sits in (Column 0 175, Header 26, Footer 15). That is why it should be inherited from section boxes, not typed per element.
- Component is "Blank" 77% of the time, and "Menu" mostly appears on links inside navigation. It can be inherited from the parent box or suggested from the DOM.
- Screenshot heights range from 893 px to **91,086 px** (Unsplash, 99 MB). Any UI must render in tiles or strips.
- At least 7 captures are suspiciously small files, probably blocked, blank or consent-wall pages: bestbuy 7 KB, crunchyroll 21 KB, homedepot 21 KB, tesla 22 KB, loc.gov 37 KB, hotels 40 KB and amazon 45 KB. Several others are exactly one viewport tall (893 px).

## Bugs and limits in v2 (`annotation_tool_v2.py`)

### Workflow and keyboard
1. **Number quick-pick only reaches options 1–9.** Function options 10–13 (Ad, Tag, **Heading**, Illustration) and Taxonomy 10–12 (Right Panel, Left Menu, Right Menu) can't be reached from the keyboard. Heading is 20% of all labeled Functions.
2. **The quick-pick focus is invisible and goes stale.** `_focused_attr` auto-advances after each pick but is reset only by Tab or Escape. It is not reset after drawing a new box or clicking one, so pressing `2` can set the wrong attribute. Nothing on screen shows which group is focused.
3. The docstring promises "Arrow keys → move between options" and "Enter → confirm", but neither is implemented.
4. There's one image at a time, opened through a file dialog (Ctrl+O). There's no page queue and no "next page".
5. Load Annotations doesn't load the matching image, and the image path isn't validated against the JSON's `image` field.
6. Save opens a "Save as" dialog every time, even though autosave already writes to disk.

### Correctness
7. Undo and redo don't trigger autosave, so an undo is lost if the app closes.
8. The history starts with a duplicate snapshot (`_push_history` in `__init__` and again before the first edit), so the first undo does nothing visible.
9. `root.state('zoomed')` works only on Windows. It raises an error on macOS and Linux, which blocks contributors on those systems.
10. The saved JSON has no image width/height, source URL, schema version or taxonomy version. `Area` is stored, but it can be derived from the box.

### Performance
11. Every zoom step resizes the **full** image with LANCZOS. On the Unsplash page that is about 175 M pixels (about 700 MB in RGBA) per keypress.
12. `_refresh_list` destroys and rebuilds every list widget on every edit. `_update_progress` calls `update_idletasks()` inside a loop.

## Data defects in legacy files

13. **v1 data has inverted boxes.** In `json/edition_cnn_com_full.json`, 30 of 206 boxes have y0 > y1 because v1 didn't sort coordinates. `json_converter.py` turns these into negative heights. The migration must normalize them.
14. v1 files carry UI state (`"expanded": false`) inside the data.
15. Box ids are list positions, so deleting a box renumbers all the boxes after it.

## Capture script (`page_capture.py`)

16. `chrome_options.headless = True` is ignored by Selenium 4, so it doesn't run headless. The correct option is `--headless=new`.
17. Stitching viewport screenshots **repeats sticky and fixed headers** in every segment. The last segment overlaps the one before it because it isn't cropped. This corrupts the geometry the research depends on.
18. The metadata says `screenshot_file: www_adobe_com.png`, but the file is `www_adobe_com_full.png`.
19. There's no detection of blocked or consent pages and no retry. Failures are printed and then lost.
20. It parses the DOM with BeautifulSoup only to count tags, then throws the DOM away. **The live DOM is the most valuable signal for automating classification.** Phase 1 keeps it.

## Converter (`json_converter.py`)

21. It looks for images in `images/`, but they're in `images/screenshots/`, so it fails on current data.
22. It raises `KeyError` on any box with an empty label.
23. The YOLO export writes class 0 for everything, so the taxonomy is lost.
24. Paths are hardcoded to `C:/Users/bruno/...`. The same is true in `page_capture.py`.

## Taxonomy mismatches between the theory and the tool (decisions for Bruno)

- **Columns:** the theory allows Column 0–5, but the tool stops at Column 4. `Column 5` is in `web-ui.yaml` as `proposed`.
- **Overlay:** it's a section in the theory but missing from the tool. It's also `proposed`.
- **Panel vs Menu:** the theory treats them as the same for templates but distinguishes them by link ratio (≥50%). With rules this can be *computed*, so annotators shouldn't have to choose.
- **Coordinates:** the theory and the Test 2 export describe Position X/Y at the **bottom-left** corner, but the tool stores top-left. Schema v1 stores top-left pixels, and the research CSV exporter converts.
