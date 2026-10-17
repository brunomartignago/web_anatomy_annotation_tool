# Templates, archetypes and incidences: plan

**Goal:** take the research method past the classification step and into the tool:

1. When a page is annotated, generate its **summarized template**.
2. Select any set of summarized templates and build the **archetype** and its **incidences** from them.
3. Reshape the app around a **workflow**, so people choose how they want to work and have a dedicated place for templates and studies.

This replaces roadmap items **5.3 and 5.4**. It also takes over the "information share" part of **5.5**. It doesn't depend on Phase 4: section boxes already exist (3.4a), and the 4.3 rule suggester only makes them faster to get later.

Source of the method: <https://brunomartignago.github.io/pages/research1.html> (Template, Summarized template, Archetype, Incidence).

---

## 1. What the research says vs what the tool must decide

The research defines the concepts and the manual steps. Several steps were done by eye in Figma/XD, so the tool needs explicit rules for them. Each rule below is either taken straight from the research (📖) or a proposed default for Bruno to confirm (🟡).

| Step | Research (📖) | Tool rule |
|---|---|---|
| Template | 📖 The page reduced to blocks of its sections: Header, Sub-header, Footer, Columns, Panels/Menus. **Overlay is excluded.** | Use section boxes (`kind=section`). If a page has none, derive them from element `Taxonomy` labels (§3.1). |
| Panels vs Menus | 📖 "For template purposes, panels and menus are treated the same." | Both render and compare as **Panel**. The original label is kept in the data. |
| Summarized template | 📖 Sections clustered **without blank spacing** inside a **24:25** rectangle, so pages of any length become comparable. Fig. 19 says section proportions are illustrative. | 🟡 Exact layout algorithm with 3 height modes (§3.2). |
| Archetype | 📖 Black summarized templates, each at **100%/N opacity**, stacked. "The stronger the line, the more the structure is repeated." | Faithful opacity stack, plus a computed edge-frequency map and a median "archetype geometry" (§4.3). |
| Outliers | 📖 Removing them "may be a good idea": "instances of radical difference that happened a single time." | 🟡 Flag singletons that are far from every other incidence. They're excluded only if the user says so (§4.4). |
| Incidence | 📖 Any variation that can be derived from an archetype. Test 2: item list had **1**, item detail **2** (two columns vs one column + right panel), and cart **4** (sub-header yes/no × panels/columns in the top half). | 🟡 An incidence is a distinct **structural signature** (§4.1). Differences are described in plain words (§4.2). |
| Information share | 📖 Information is everything that isn't blank space. Block areas are summed and compared with the page area. Reported per page type (median 29.19%, and type shares 42.38 / 33.13 / 24.49%). | 🟡 Report both **sum** (as in the research) and **union** (no double count of nested boxes) (§3.4). |
| Grouping | 📖 Everything is computed **per page type** (home, item list, item detail, cart…), often along one flow. | `page.page_type` (already in schema v1) plus a project-level page-type list. Studies group by it. |

The **validation target** is that, given the Test 2 pages with sections annotated, the tool should report 1 / 2 / 4 incidences for item list / item detail / cart (task T13).

---

## 2. Workflow: how the app changes

### 2.1 Workspaces
The app becomes four workspaces, chosen from a left rail and kept in the URL (`?view=…&page=…&study=…`) so a view can be linked and reloaded.

```
┌──┬──────────────────────────────────────────────────────────────────┐
│▣ │ PAGES       filters: type ▾  stage ▾  site ▾        [Set type…]   │
│✎ │ ┌────────┬─────────────┬───────────┬─────────┬──────────────────┐ │
│▦ │ │ page   │ type        │ stage     │ boxes   │ template         │ │
│◫ │ │ cnn    │ home        │ ●●●○ Rev. │ 210     │ ✓ v1 structural  │ │
│  │ │ adobe  │ —           │ ●○○○ Sect.│ 12      │ —                │ │
└──┴─┴────────┴─────────────┴───────────┴─────────┴──────────────────┘
 ▣ Pages   ✎ Annotate (today's app)   ▦ Templates   ◫ Studies
```

- **Pages:** every page in the project with its type, stage, counts and template status. Bulk-select to set the page type or generate templates.
- **Annotate:** the current shell, plus a per-page **stepper** (§2.3) and a "Generate template" action when the page is ready.
- **Templates:** a grid of summarized templates, with a detail view comparing each one to its screenshot (§2.4).
- **Studies:** select templates, then see the stack, the archetype, the incidences and the metrics (§2.5).

### 2.2 Project workflow setup ("how do you want to work?")
This appears when a project has no `workflow:` block in `project.yaml`, and later as Project settings. It asks three things and writes the answers to `project.yaml`:

1. **Goal**
   - *Template study (sections only)*: draw only section boxes (Header, Columns, Panels, Footer). This is the fastest path to archetypes: about 5 boxes per page, so a 30-page study takes about an hour. Information share isn't available unless elements are labeled too.
   - *Full taxonomy (elements + sections)*: today's workflow, with sections required for templates.
   - *Element dataset (elements only)*: for exporters and training. Templates are derived from element `Taxonomy` labels (lower quality, flagged as *derived*).
2. **Page types** used in this project, in flow order. Defaults come from the research: home, item list, item detail, cart, checkout, article, user page.
3. **Summary defaults**: height mode, and whether to close horizontal gaps (§3.2). These can be overridden per study.

```yaml
# project.yaml (new keys)
workflow:
  goal: template_study        # template_study | full | elements
  page_types: [home, item list, item detail, cart]
  summarize: { height_mode: structural, close_horizontal_gaps: true }
```

The goal changes what "done" means for a page, what the progress panel counts, the default draw tool (section draw mode for *template_study*), and which stepper steps appear.

### 2.3 Page stages (stepper in Annotate and the Pages list)
`Capture → Sections → Elements → Review → Template`. A step is skipped when the goal doesn't need it. Each stage is computed by the server from the page files and is never stored by hand:

| Stage | Done when |
|---|---|
| Capture | `page.png` exists and `meta.blocked` is not true |
| Sections | ≥1 section box, every section box has a Taxonomy value, no section overlaps another by >10% (warning otherwise) |
| Elements | every element box is complete (today's definition) |
| Review | no `suggested` boxes left (only matters once Phase 4 exists) |
| Template | `template.json` exists and is up to date with the current annotations |

When a page reaches the step before Template, Annotate shows a banner: **"Page ready — Generate template (G)"**. Generating opens a side panel with the summarized template next to the canvas. This is the first flow you asked for. Check the keymap for conflicts before taking `g`.

### 2.4 Templates workspace
```
┌ filters: type ▾ site ▾ status ▾   mode: [structural|proportional|equal]   [Generate all stale] ┐
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                                                          │
│ │▀▀▀▀▀▀│ │▀▀▀▀▀▀│ │▀▀▀▀▀▀│ │▀▀▀▀▀▀│   each card: thumbnail (24:25), page id, type, signature,│
│ │▌ ███ │ │███ ▐ │ │██████│ │▌ ██ ▐│   badges: derived · stale · warnings                     │
│ │▄▄▄▄▄▄│ │▄▄▄▄▄▄│ │▄▄▄▄▄▄│ │▄▄▄▄▄▄│                                                          │
│ └──────┘ └──────┘ └──────┘ └──────┘   multi-select → [New study from selection]              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
Detail: screenshot with section overlay (left) ↔ summarized template (right), hover links blocks
across the two; the 3 height modes side by side; warnings with "fix in Annotate" links.
```

### 2.5 Studies workspace
```
┌ Study: "E-commerce purchase flow" ─ 30 pages ─ group by: page type ▾ ───────── [Run] [Export ▾] ┐
│ [item list] [item detail] [cart]                                                               │
│ ┌──────────────── stack ─────────────┐  INCIDENCES                       METRICS               │
│ │  opacity 1/N · edges ◐ · fills ◐    │  ● A  H/P|C/F        7 pages 70%   pages        10       │
│ │  ░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░    │  ○ B  H/C|C/F        3 pages       incidences    2       │
│ │  ░░▓▓   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░    │     vs A: Left Panel → Column 1    dominant     70%      │
│ │  ...                               │  ⚠ outlier: zappos (single, far)  info share  33.1% med. │
│ │  [stack] [archetype] [edges heat]   │     [include] [exclude]                                │
│ └─────────────────────────────────────┘  hover an incidence → highlight its pages in the stack   │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Stack**: the faithful method (black, 100/N % each).
- **Archetype**: median boundaries of the dominant incidence, with shaded ranges.
- **Edges heat**: how often each line repeats ("strong lines").

A study is reproducible: running it saves a snapshot of the exact templates and parameters it used.

---

## 3. Per-page computations (backend, pure functions)

New package: `backend/src/annotool/templates/`, containing `sections.py`, `summarize.py`, `signature.py`, `render.py`, `metrics.py`, `stack.py`, `incidences.py` and `study.py`.

### 3.1 Resolve section blocks: `sections.py`
- **Explicit:** use non-rejected `kind=section` boxes that have a Taxonomy value. Ignore nested sections (a section inside another), but report them as a warning.
- **Derived** (no section boxes, e.g. legacy CNN): group element boxes by `Taxonomy` value, then split each group into vertical clusters wherever the gap between consecutive boxes exceeds `derive_gap_px` (default 120 px). Without the split, one block would run from the hero to the footer, because legacy data labels most body content "Column 0". Each cluster's union bbox becomes a block with `derived: true`.
- Drop `Overlay` (📖) and `proposed` values that are inactive.
- Normalize the role: Left Panel and Left Menu become **Panel L**, Right Panel and Right Menu become **Panel R**, Column 0–5 become **Column**, and Header, Sub-header and Footer keep their names. Keep `label` for display.
- Return the blocks plus a **readiness report**: no sections, unlabeled sections, overlaps >10%, elements outside every section (count), derived or not, and legacy padded height (CLAUDE.md note 0.6). The UI shows these warnings, and they never block generation.

### 3.2 Summarize: `summarize.py` (algorithm `summarize/v1`)
Input: blocks and the page width W. Output: blocks in a **24 × 25 unit** frame (origin top-left).

1. **Bands.** Header blocks form one band, Sub-header one band and Footer one band. Body blocks are grouped into bands by vertical overlap: two blocks share a band when they overlap by ≥50% of the shorter block's height. Band order is Header, Sub-header, body bands top to bottom, then Footer.
2. **Remove vertical blank space.** Bands are stacked flush. Gaps between bands are dropped (📖 "without blank spacing").
3. **Widths inside a band.** Order blocks by x.
   - `close_horizontal_gaps: true` (default): width = wᵢ / Σw × 24.
   - `false`: x and w are scaled by 24 / W, so the gaps stay.

   Blocks are stretched to their band's full height, because the template shows structure.
4. **Band heights**, set by `height_mode`. 🟡 Pick the default. Proposal: **structural**, because stacking needs comparable outlines.
   - `proportional`: hᵦ' = hᵦ / Σh × 25 (real heights after gap removal). Faithful, but a 100 px header on a 20,000 px page becomes a 0.1-unit sliver.
   - `structural`: fixed heights for Header 2.5, Sub-header 1.25 and Footer 2.5 when present. Body bands share the rest in proportion to their real heights, with a minimum of 1 unit each.
   - `equal`: every band gets the same height. Pure structure.
5. `collapse_repeated_bands` (default true): consecutive body bands with the same block sequence merge into one. 🟡 With no blank space between them, two stacked single-column blocks read as one.
6. Round to 0.01 units. Each output block keeps `role`, `label`, `band`, `index_in_band` and `source_ids` (the annotation ids).

All parameters live in `project.yaml › workflow.summarize`, and a study can override them. Record the algorithm version and the parameters in every output.

### 3.3 Signature: `signature.py`
Write a template as band tokens: `H`, `S`, `F`, and body bands as the block roles joined left to right, using `C` for Column and `P` for Panel, e.g. `P|C|C`. Examples:
- `H/P|C/F` (header, then a left panel and a column, then the footer)
- `H/S/C|C/C/F`

This is the key two templates are compared by. It's cheap, explainable and matches how Test 2 described its incidences.

### 3.4 Page metrics: `metrics.py`
- `info_share_sum` = Σ element areas / (W × H). This is the research definition, and nested boxes count twice.
- `info_share_union` = area of the union of element boxes / (W × H). 🟡 Proposal: show union as the main number and keep sum for comparison with Tests 1–2.
- Info share per section (elements by `parent_id` or containment), the band count and the block count.
- Elements counted: `kind=element` with `status` accepted or edited. If the goal is *template_study* and there are no elements, the metric is `null`, not 0.

### 3.5 Render and store: `render.py`
- `template.svg`: blocks as black rects with a 1-unit grid option and role labels (on/off). The viewBox is `0 0 24 25`, so it imports cleanly into Figma.
- `pages/<id>/template.json` (schema `template.v1`): page id, page_type, algorithm and parameters, `source_etag` (the annotations ETag it was built from), signature, blocks, metrics, readiness warnings and `derived`. It's a **cache**: it's stale when `source_etag` ≠ the current ETag, and it can be regenerated at any time.

---

## 4. Study computations

### 4.1 Incidences: `incidences.py`
- Group the study's templates by page type (or no grouping), then by **signature**. Each distinct signature is an **incidence** with its pages and count. The most frequent one is the **dominant incidence**. A tie is broken alphabetically by signature and shown as "tied" in the UI, because a tie is itself a finding.
- Optional `merge_similar` (off by default): merge incidences whose stacks overlap ≥ `iou_merge` (0.9) in raster IoU. Use it when tiny differences split incidences that aren't meaningfully different.

### 4.2 Differences in plain words
Align each incidence's band sequence to the dominant one with a band-level edit distance (insert, delete, substitute; substitution cost 1, or 0.5 when only one block changes role). Turn the result into text such as:
- "adds a Sub-header"
- "body band 1: Column 2 → Right Panel"
- "one column fewer in body band 2"

These sentences are the incidence descriptions that Test 2 wrote by hand.

### 4.3 Stack and archetype: `stack.py`
- **Faithful stack (SVG):** every template's blocks as black rects with `fill-opacity = 1/N`, plus an outline stroke at the same opacity. This is exactly the manual method.
- **Edge frequency (raster):** draw each template's block outlines onto a 240 × 250 grid (10 px per unit, 1 px lines, Pillow or numpy). Accumulate and divide by N. The result is a 0–1 map of how often each line repeats ("strong lines"), rendered as a heat overlay. Repeat with fills for coverage.
- **Archetype geometry:** for the dominant incidence, take the **median** of each band boundary (y) and each block boundary inside a band (x) across its pages. Also take min–max (or IQR) ranges. Render the medians as solid lines and the ranges as translucent bands. This is a clean, citable figure of "the" archetype.

### 4.4 Outliers
An incidence is flagged as an **outlier** when it has exactly one page **and** its edit distance to every other incidence is ≥ `outlier_distance` (default 2). This turns 📖 "radical difference that happened a single time" into a rule.

🟡 Flagged outliers stay **included** until the user excludes them. Each exclusion is recorded in the study, so the final figures say what was left out.

### 4.5 Study metrics
For each group:
- N pages and the number of incidences
- the dominant incidence and its share
- information share median, mean and SD (from §3.4)
- each type's **share of all information collected** (Σ info area for the type ÷ Σ across all types), comparable with Test 2's 42.38 / 33.13 / 24.49%

### 4.6 Storage: `study.py`
```
data/projects/<p>/studies/<slug>/
├─ study.json      definition: name, page ids, group_by, parameter overrides, exclusions, notes
├─ result.json     snapshot: the exact templates used (copied), incidences, diffs, metrics, versions
└─ figures/        stack.svg · archetype.svg · edges.png · per-incidence stack SVGs
```
`study.v1` and `study-result.v1` get their own JSON Schemas. Generate the TS types the same way as `annotation.ts`. Running a study always overwrites `result.json` and `figures/`. The definition is only changed by the user.

---

## 5. API and CLI

```
GET  /api/projects/{p}/workflow               PUT  same (writes project.yaml › workflow)
PUT  /api/pages/{id}/page-type                POST /api/projects/{p}/page-type  (bulk: ids + type)
GET  /api/pages/{id}/stage                    stage + readiness warnings
GET  /api/pages/{id}/template?mode=…          from cache if fresh, else computed (not saved)
POST /api/pages/{id}/template                 compute + save template.json (+ svg)
GET  /api/projects/{p}/templates              list: id, type, signature, stale, warnings, thumb URL
GET  /api/pages/{id}/template.svg
GET  /api/projects/{p}/studies                POST same (create)
GET  /api/studies/{slug}?project=…            PUT same (edit definition)   DELETE same
POST /api/studies/{slug}/run?project=…        → result.json
GET  /api/studies/{slug}/figures/{name}
```
```
annotool template <project> [--page ID] [--mode structural] [--stale-only]
annotool study new <project> <slug> --pages a,b,c | --type "cart"
annotool study run <project> <slug>
annotool study export <project> <slug> --out <folder>     # figures + CSV + methods.md
```
Setting the page type changes `page.page_type` in `annotations.json` through the same ETag-protected save as everything else. It counts as an action in `history.actions`.

---

## 6. Tasks (one session / PR each, in order)

- [ ] **T0 Fold this plan into the roadmap and confirm decisions**
  - Replace 5.3 and 5.4 with the T items in `docs/ROADMAP.md`, and move "information share" out of 5.5. Then go through the 🟡 list in §7 with Bruno and record his answers here.
  - Docs only. No code.
- [ ] **T1 Page types and workflow config**
  - Add `workflow:` to `project.yaml` with load and validation, and GET/PUT `/workflow`. Add single and bulk page-type endpoints (page types must be in the project list), show page type in the page list, and filter by it.
  - ✅ Tests cover: an unknown type is rejected; a bulk set writes every page and respects ETags (412 on a stale page doesn't block the others, and it is reported).
- [ ] **T2 Section resolver and readiness**
  - Write `templates/sections.py` (§3.1) and `GET /stage`.
  - ✅ Synthetic tests cover: explicit sections, nested sections warned, overlap warning, Overlay dropped, Panel/Menu normalized, and the derived split on gaps. On the CNN legacy fixture, the derived Column 0 splits into more than one block and the report flags the padded height.
- [ ] **T3 Summarize v1**
  - Write `summarize.py` and `signature.py` (§3.2–3.3), the `template.v1` schema and models, and generated TS types.
  - ✅ Golden tests on synthetic layouts:
    - 1-col
    - 2-col + left panel
    - 3-col + right menu (gives `P`)
    - header/sub-header/footer
    - two body bands
    - repeated bands collapsing

    Each layout is checked in all 3 height modes. In every case the outputs fill exactly 24 × 25 with no gaps or overlaps, using a property test with random layouts.
- [ ] **T4 Template render, cache, API and CLI**
  - Write `render.py`, `template.json` with `source_etag`, the template endpoints and `annotool template`.
  - ✅ Editing a page marks its template stale. Regenerating clears that. The SVG opens in a browser and in Figma at 24:25.
- [ ] **T5 Page metrics**
  - Write `metrics.py` (§3.4), stored in `template.json`.
  - ✅ Hand-computed fixtures cover sum vs union with nested boxes, null in *template_study* with no elements, and per-section shares that add up to the page total (union).
- [ ] **T6a App shell and workspaces**
  - Add the left rail, URL state (`?view=`), and the Pages workspace (table, filters, bulk page type, bulk generate). Annotate stays as it is inside the new shell.
  - ✅ Every existing test still passes. Reloading keeps the view, page and study. `]`/`[` still work in Annotate.
- [ ] **T6b Workflow setup and the stage stepper**
  - Add the setup screen (§2.2), the stepper in Annotate (§2.3), the default draw tool and progress counting by goal, and the "Page ready — Generate template" banner with its side panel.
  - ✅ In *template_study*, a page with only labeled sections reaches the Template stage. In *full*, it doesn't until its elements are complete.
- [ ] **T7 Templates workspace**
  - Build the grid, filters, mode toggle, detail view (screenshot ↔ template with hover-linked blocks, 3 modes side by side), warnings with links to Annotate, and "New study from selection" (§2.4).
- [ ] **T8 Incidences and differences**
  - Write `incidences.py` (§4.1–4.2, 4.4).
  - ✅ A synthetic study that reproduces Test 2's *shapes* gives:
    - item list: 10 identical pages → 1 incidence
    - item detail: 2-col vs 1-col + right panel → 2 incidences, diff "Column 2 → Right Panel"
    - cart: sub-header yes/no × panel/column in the top band → 4 incidences

    The outlier rule is covered by a test.
- [ ] **T9 Stack and archetype geometry**
  - Write `stack.py` (§4.3): the faithful SVG, the edge and coverage rasters, and the median archetype with ranges.
  - ✅ With N identical templates, edge frequency is 1.0 on every edge and 0 elsewhere. With 2 different ones, shared edges are 1.0 and the others 0.5. The median of an odd set equals its middle template.
- [ ] **T10 Studies backend**
  - Write `study.py`, the study schemas, CRUD and run endpoints, and the `annotool study` CLI (§4.5–4.6, §5).
  - ✅ A run saves a snapshot: editing a page afterwards doesn't change `result.json` until the next run, and the result lists which templates were stale at run time.
- [ ] **T11 Studies workspace**
  - Build creation from a selection or a page type, group tabs, the stack view (opacity, edges, fills), archetype and heat toggles, the incidence list with hover highlight, outlier include/exclude, and the metrics panel (§2.5).
- [ ] **T12 Study export**
  - `annotool study export` and an Export menu produce the SVG/PNG figures, `pages.csv` (page, type, signature, incidence, info shares), `incidences.csv`, and `methods.md`. The methods file is an auto-written paragraph stating the algorithm version, parameters, N, exclusions and date, ready to paste into a write-up.
- [ ] **T13 Validate against Test 2** 🟡 needs Bruno's Test 2 material (the 30 pages and his notes)
  - Recreate the section boxes for the 30 pages (screenshots, or the XD blocks if they can be exported). Run one study grouped by page type and compare with the published results: incidences 1 / 2 / 4, info share median ≈29%, and type shares ≈42 / 33 / 24%. Record the comparison in `docs/EVAL.md`. Differences are findings, not bugs: explain which rule causes each one.

**Order note:** T1–T5 are backend only and can run back to back. T6a should land before T7 and T11. T8–T10 can start after T3, in parallel with the UI work.

---

## 7. Decisions for Bruno (🟡)

1. **Height mode default:** structural (proposed), proportional or equal. If structural, are Header 2.5, Sub-header 1.25 and Footer 2.5 units right?
2. **Horizontal gaps:** close them (proposed) or keep real proportions including gaps?
3. **Repeated bands:** merge consecutive identical body bands (proposed)?
4. **Incidence definition:** exact structural signature (proposed), with optional geometric merging, or geometric clustering from the start?
5. **Outliers:** flag singletons with distance ≥2, kept until excluded by hand (proposed), or excluded automatically?
6. **Information share:** show union as the main number with sum alongside (proposed), or sum only, as in the research?
7. **Workflow goals:** are *template study*, *full* and *element dataset* the right three? Should the goal be per project (proposed) or per page?
8. **Page types:** is the default list home, item list, item detail, cart, checkout, article, user page right? Should "flow" (an ordered sequence of page types) be its own concept now, or later?

---

## 8. Kickoff prompts

**Start of this phase**
```
Read docs/TEMPLATES.md fully, then CLAUDE.md › Notes. Do T0: fold the T tasks into
docs/ROADMAP.md (replacing 5.3/5.4 and the info-share part of 5.5), then walk me through
the 8 decisions in §7 one at a time with your recommendation. Record my answers in §7.
No code in this session.
```

**Any T task**
```
Do roadmap item T<N> from docs/TEMPLATES.md (decisions are recorded in §7).
Restate its ✅ criteria, list files you'll touch, write the pure-function tests first.
Stop at any 🟡. When done: tests green, tick the box in both TEMPLATES.md and ROADMAP.md,
add a one-line note to CLAUDE.md › Notes, push.
```

**Before T11 (worth seeing the result before building the UI)**
```
Using the CLI only, build a study from every page in project <name> that has sections,
grouped by page type. Export it and show me the figure paths and incidences.csv. I want
to look at the stack and the diff wording before we build the Studies workspace.
```
