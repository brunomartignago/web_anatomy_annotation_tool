# Roadmap

Each `- [ ]` item is sized for **one Claude Code session and one PR**. Do them in order inside a phase. Phases 4 and 5 can run in parallel once Phase 2 is done. Tick the box in the same PR that completes the item.

Decisions only Bruno can make are marked **🟡 DECIDE**. Claude Code should stop and ask when it reaches one.

---

## Phase 0: Repo foundation (no behavior change)

- [x] **0.1 Initialize the repo**
  - Run `git init`, move the legacy `*.py` files to `legacy/`, and add the root `.gitignore` (already provided). Delete `claude_code/`, `labels/` and `csv/`. Move `websites/public_websites_for_dataset.csv` to `examples/urls.csv`.
  - Move `images/`, `json/` and the autosaves to `data/legacy/`, which is git-ignored.
  - ✅ `git status` shows no PNGs and nothing under `data/`. `python legacy/annotation_tool_v2.py` still launches.
- [x] **0.2 Write the README, LICENSE and CONTRIBUTING files**
  - The README covers what it is, a link to the research page, a GIF placeholder, quick start, and the roadmap link. CONTRIBUTING explains how to propose a taxonomy class (edit the YAML and open a "taxonomy-proposal" issue).
  - 🟡 DECIDE: license. MIT is simplest. Apache-2.0 adds a patent grant. Also pick a project name (working name: `annotool`).
  - 🟡 DECIDE: dataset policy. Recommendation: publish annotations, URLs and the capture script, but **not** screenshots of third-party sites.
- [x] **0.3 Set up the backend skeleton**
  - `backend/pyproject.toml` (uv, Python ≥3.11, ruff, pytest, pydantic v2, typer, pyyaml). Provide an empty `annotool` CLI with `--version`.
  - ✅ `uv run annotool --version` and `uv run pytest` pass on Windows PowerShell.
- [x] **0.4 Add the taxonomy loader**
  - `taxonomy.py` loads `taxonomies/web-ui.yaml` and validates unique values, unique keys per attribute, and that presets reference existing values. It also returns active vs proposed options.
  - ✅ Tests cover the duplicate-key and unknown-preset-value error cases.
- [x] **0.5 Add the schema and models**
  - `models.py` mirrors `schema/annotation.v1.schema.json`. Add a test that validates model output against the JSON Schema.
- [x] **0.6 Add the legacy migration**
  - `annotool migrate <legacy.json> --image <png> --out <page folder>` converts v1 and v2 files to schema v1. It normalizes inverted coords (30 boxes in the CNN file), converts `[x0,y0,x1,y1]` to `[x,y,w,h]`, drops `expanded` and `Area`, sets `source: legacy` and `status: accepted` (or `suggested` if incomplete), assigns ULIDs, and reads image size from the PNG.
  - ✅ All 6 legacy files in `data/legacy/` migrate and validate. Box counts are unchanged (224). Committed fixtures are copies of the migrated JSON only.
- [x] **0.7 Add CI**
  - `.github/workflows/ci.yml` runs ruff and pytest on Ubuntu and Windows.

## Phase 1: Capture v2 (Playwright)

- [x] **1.1 Full-page capture**
  - `annotool capture examples/urls.csv --project <name>` uses Playwright Chromium at a 1920×1080 viewport. It scrolls to trigger lazy loading, then takes one screenshot with `full_page=True` (no stitching). It writes `page.png` and `meta.json` into a page folder, with the page id taken from the hostname plus an optional path slug.
  - ✅ The Adobe and CNN captures have no repeated sticky headers. The metadata file name matches the PNG.
- [ ] **1.2 Detect blocked and consent pages**
  - Flag pages with a tiny file size, near-uniform color, height equal to one viewport, or known consent/captcha selectors as `meta.blocked = true` with a reason. Add `--retry-blocked`, and accept an optional cookie-banner click list in `project.yaml`.
  - ✅ Running against the old list flags most of: bestbuy, homedepot, tesla, crunchyroll, hotels, amazon, loc.gov.
- [ ] **1.3 DOM extraction**
  - `dom_extract.js` produces `dom.json`: visible elements with a document-space bbox, tag, role, aria-label, input type, href presence, text length, font size/weight, background-image flag, position (static/fixed/sticky) and parent index. Use the same Playwright session as the screenshot so the coordinates match.
  - ✅ An overlay debug image (`annotool debug-dom <page>`) shows the DOM boxes aligned with the screenshot within 2 px.
- [ ] **1.4 Politeness**
  - Add a per-host delay, a user-agent string that identifies the project, a robots.txt check (warn, don't block), and resume support that skips already-captured pages.

## Phase 2: Web annotator with v2 parity

- [ ] **2.1 Server**
  - Build FastAPI with these routes: `GET /api/taxonomy`, `GET /api/projects`, `GET /api/projects/{p}/pages` (with progress counts), `GET /api/pages/{id}`, `PUT /api/pages/{id}/annotations` (atomic write plus ETag to block stale overwrites), and `GET /api/pages/{id}/strips/{n}.webp` (2048-px strips, cached).
  - Add `annotool serve --project <name>` to open the browser.
- [ ] **2.2 Frontend scaffold**
  - Set up Vite, React, TS, pnpm, ESLint, Vitest, zustand and immer. Generate types from the JSON Schema with `json-schema-to-typescript` as a `pnpm gen:types` script.
- [ ] **2.3 Canvas**
  - Build a stage that lazy-loads strips in view, with zoom (Ctrl+wheel, `+`/`-`, Ctrl+0 to fit width) and pan (middle-drag or Space+drag). Boxes are colored by completeness (empty, partial, complete, selected) with small index tags.
  - ✅ The 91,086-px Unsplash page scrolls smoothly and uses less than 500 MB of browser memory.
- [ ] **2.4 Tools**
  - Draw (D), select (S), shift-click multi-select, rubber-band select, Delete/X, and smallest-box-wins hit testing. Undo/redo with Ctrl+Z / Ctrl+Shift+Z uses immer patches. Autosave is debounced at 800 ms, including after undo.
- [ ] **2.5 Panels**
  - Build the label panel from the taxonomy (showing mixed values for multi-select), a box list with All/Empty/Partial/Done filters, a progress bar per attribute, and a page queue with `]` / `[`.
- [ ] **2.6 Parity check**
  - Walk through every feature in the legacy v2 docstring and confirm it works or is intentionally replaced. Document the result in the PR.

## Phase 3: Fewer clicks

- [ ] **3.1 Keymap from YAML**
  - Attribute hotkeys (`f` `n` `c` `t`) open a picker for that attribute, and the option mnemonic sets it. The focused attribute is always visible. A cheat-sheet overlay opens with `?`.
  - ✅ Every option, including Heading and Right Menu, takes at most 2 keystrokes.
- [ ] **3.2 Presets**
  - `1`–`9` apply the YAML presets to all selected boxes, and the presets are shown in the panel.
- [ ] **3.3 Command palette**
  - `/` opens fuzzy search across all values and presets (for example, "hea" → Heading).
- [ ] **3.4 Sections and inheritance**
  - Add a "section" draw mode (Shift+D). `kind=section` boxes carry Taxonomy. Elements inside inherit Taxonomy (and Component from `kind=component` boxes) with `label_sources: inherited`. Moving or resizing a section updates its children. An explicit human label always wins over inheritance.
- [ ] **3.5 Sticky labels / paint mode**
  - Pick a preset, then each click on a box applies it. Esc exits.
- [ ] **3.6 Select similar**
  - Shortcut Shift+A selects boxes with the same DOM signature (tag + role + class stem) or, failing that, the same size within 4 px in the same row or column.
- [ ] **3.7 Effort metrics**
  - Count actions per page in `history.actions` and show "actions per box" in the progress panel. This is the main KPI.

## Phase 4: Intelligence v1 (DOM + rules + priors)

- [ ] **4.1 Suggester framework**
  - Add the `suggest/base.py` protocol, merge policy (never overwrite human labels) and `POST /api/pages/{id}/suggest`. Add a "Suggest" button and `annotool suggest <project>` for batch runs.
- [ ] **4.2 DOM suggester**
  - Turn `dom.json` into boxes and labels using `dom_hints`. Remove noise: drop boxes under 6×6 px or fully covered by others, and collapse wrappers that have one child and the same bbox.
  - ✅ On 5 hand-labeled pages: report box recall (IoU ≥ 0.5) and per-attribute accuracy in `docs/EVAL.md`.
- [ ] **4.3 Rule suggester**
  - Implement the section, column, panel and menu rules from `web-ui.yaml › rules.sections` in `geometry.py` and `suggest/rules.py`, with unit tests on synthetic layouts (1-col, 2-col + left panel, 3-col + right menu, header/sub-header/footer).
- [ ] **4.4 Prior suggester**
  - Build co-occurrence tables from accepted boxes in the project. Fill in missing attributes and re-rank the presets per project.
- [ ] **4.5 Review mode**
  - Suggested boxes are drawn dashed. Enter accepts the box and moves to the next one. Tab moves to the next lowest-confidence box. Backspace rejects. A filter shows only suggestions. Exports skip `suggested` and `rejected` boxes by default.

## Phase 5: Research outputs (automates steps 4–7 of the method)

- [ ] **5.1 Research CSV exporter**
  - Columns: page, page_type, section, form, function, component, width, height, x, y (bottom-left origin, as in Test 2), plus normalized versions (÷ page width/height).
- [ ] **5.2 YOLO and COCO exporters**
  - Classes come from the taxonomy (choose which attribute, or the combined label). Include a train/val split by page.
- [ ] **5.3 Summarized templates**
  - Render each page's sections, collapsing blank space, into the 24:25 rectangle described in the research, as SVG and PNG.
- [ ] **5.4 Archetype stacking**
  - Overlay the summarized templates of N pages at 100/N % opacity, with an option to drop outliers, grouped by page type. This replaces the manual Figma/XD stacking.
- [ ] **5.5 Stats**
  - `annotool stats` and an in-app page show label distributions, information share per page type and actions-per-box trends.

## Phase 6: Learning (later, once there are more than about 50 fully labeled pages)

- [ ] 6.1 Train a YOLO detector for "element" boxes on pages where the DOM fails (canvas/image-heavy sites).
- [ ] 6.2 Train a crop classifier per attribute that uses DOM features plus pixels.
- [ ] 6.3 Active learning: prioritize pages where the model is least confident.
- [ ] 6.4 Optional vision-LLM suggester plug-in, off by default and bring-your-own-key. 🟡 DECIDE: which provider or providers.

## Phase 7: Community

- [ ] 7.1 Add issue templates and 5–10 `good first issue` items (for example, a new `dom_hint`, a new exporter, or keyboard cheat-sheet polish).
- [ ] 7.2 Document custom taxonomies: write a second example YAML (for example, a mobile-app taxonomy) to prove the system is taxonomy-agnostic.
- [ ] 7.3 Build a GitHub Pages demo: the frontend with a read-only demo project loaded from static JSON.
- [ ] 7.4 Add a short demo GIF to the README and link the repo from the research page.

---

### Open decisions (🟡) collected
1. ~~License (MIT or Apache-2.0) and project name.~~ Decided in 0.2: **MIT**, name **annotool**.
2. ~~Dataset publishing policy: annotations + URLs only (recommended) or screenshots too.~~ Decided in 0.2: **annotations, URLs and the capture script only, no screenshots**.
3. Add `Column 5` and `Overlay` to the active taxonomy? Both are in the theory but weren't in the v2 tool.
4. Keep Left/Right Panel vs Menu as separate labels, or compute Menu from the link ratio and show it read-only?
5. Vision-LLM provider for Phase 6.4, if any.
