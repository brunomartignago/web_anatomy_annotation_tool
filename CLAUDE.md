# CLAUDE.md

## What this project is
An open-source tool for **annotating web page screenshots with a multi-axis UI taxonomy** (Form × Function × Component × Template section), built for Bruno Martignago's research on visual patterns in web pages (<https://brunomartignago.github.io/pages/research1.html>). The goal of this rewrite is to:
1. **Cut actions per box** from at least 5 (draw + 4 picks) to about 1.5, using DOM-captured boxes, rule-based section detection, presets and inheritance.
2. **Restructure the code** so others can contribute on GitHub.
3. **Automate the research outputs** (summarized templates, archetype stacks) that are currently built by hand.

Owner: Bruno (designer and researcher, comfortable with Python, works on **Windows**). Explain trade-offs in plain language, and ask before making 🟡 decisions.

## Read these before any task
- `docs/ROADMAP.md`: the ordered task list. **Work on one item per session/PR** and tick it off when done.
- `docs/ARCHITECTURE.md`: target layout, decisions, suggestion pipeline, interaction model.
- `docs/AUDIT.md`: what's wrong with the legacy code and data (numbered; reference these numbers in commits).
- `docs/TAXONOMY.md` and `taxonomies/web-ui.yaml`: the domain. **The YAML is the single source of truth for labels.**
- `schema/annotation.v1.schema.json`: the file format contract.

## Current state
- The legacy tkinter app lives in `legacy/` (after task 0.1). The newest version is `legacy/annotation_tool_v2.py`. Read it to understand the expected UX, but **don't modify it**.
- Real data is in `data/` (git-ignored): 88 screenshots and 224 labeled boxes, mostly on CNN.

## Stack
- Backend: Python ≥3.11, **uv**, FastAPI, pydantic v2, typer, Playwright, Pillow, ruff, pytest.
- Frontend: Vite + React + TypeScript, **pnpm**, zustand + immer, ESLint, Vitest.
- No database. One JSON file per page, written atomically (write temp file, then `os.replace`).

## Commands (fill in as they become real)
```powershell
cd backend; uv sync; uv run pytest; uv run ruff check .; uv run annotool --help
uv run playwright install chromium        # first time, for capture
uv run annotool capture ../examples/urls.csv --project <name>   # or pass URLs directly
uv run annotool capture ../examples/urls.csv --project <name> --retry-blocked --assist --browser msedge
uv run annotool debug-dom ../data/projects/<name>/pages/<page_id>   # writes debug-dom.png
uv run annotool migrate <legacy.json>... --image <png> --out <page folder> --meta <meta.json>
cd frontend; pnpm install; pnpm dev; pnpm test; pnpm lint; pnpm build; pnpm gen:types
uv run annotool serve --project legacy    # backend + built frontend (frontend/dist)
```

## Non-negotiable rules
- **Never commit screenshots, `data/`, or any third-party site images.** Small JSON fixtures in `backend/tests/fixtures/` are fine.
- **Taxonomy values are research data.** Never rename or remove a value in the YAML without a migration in `backend/src/annotool/io/migrations/` plus a taxonomy `version` bump.
- **Schema changes** bump `schema_version`, add a migration, and regenerate the TS types in the same PR.
- **Suggestions never overwrite a human label.** Every box and label carries `source`, `status`, and (when suggested) `confidence`.
- Coordinates are image pixels `[x, y, w, h]` with a **top-left** origin everywhere inside the app. Only exporters convert.
- Use `pathlib` and no hardcoded absolute paths. Everything must work in Windows PowerShell **and** on macOS/Linux (no `root.state('zoomed')`-style platform calls).
- Large images: never load a full screenshot into the browser. Use the strip endpoint.
- Keep keyboard shortcuts generated from the YAML. Don't hardcode label names in the frontend.

## How to work
1. Start each roadmap item in **plan mode**. Restate the acceptance criteria (✅ lines) and list the files you'll touch.
2. Write tests first for geometry, rules, migrations and exporters. They're pure functions and easy to test.
3. Keep PRs small. If an item grows, split it in the roadmap instead of expanding scope.
4. At a 🟡 DECIDE marker, stop and ask Bruno with a recommendation.
5. End each session by ticking the roadmap box and noting anything surprising under "Notes" below.

## Glossary
Form, Function, Component: the element axes. *Taxonomy* (attribute name) means the template section. Section: a template block (Header, Column 1…). Panel/Menu: narrow first or last columns (Menu if ≥50% links). Summarized template: sections packed into a 24:25 rectangle. Archetype/incidence: the recurring structure and its variations. Preset: a one-key Form·Function·Component combo. Suggester: a module that proposes boxes or labels (dom, rule, prior, model, llm).

## Notes
- 0.1: `labels/` and `csv/` were kept in `data/legacy/converter-output/` instead of deleted (`labels/linkedin.txt` is the only trace of a LinkedIn annotation). CNN and Adobe each have two legacy files (`json/` + autosave) with no shared boxes, so 0.6 must merge them. Stitched PNG heights are padded to multiples of 893 px.
- 0.2: Decided MIT, name `annotool`, and publish annotations + URLs + capture script but no screenshots. The README avoids absolute GitHub URLs because the GitHub account/repo path isn't set yet (the schema `$id` assumes `brunomartignago/annotool`).
- 0.3: uv was installed via winget (0.13.1); open a new terminal if `uv` isn't on PATH. `.gitattributes` forces LF in the working copy. With Click ≥8.2, running a `no_args_is_help` command with no args exits with code 2, so test `--help` instead.
- 0.4: The taxonomy loader uses strict strings, so YAML gotchas (unquoted `key: 0`, a bare `No` value parsed as a boolean) fail loudly. Presets may only use `active` values. `rules` is kept as a raw dict until the Phase 4 suggesters parse it.
- 0.5: `json-schema-to-typescript` ignores `prefixItems`, so `bbox` also declares `"items": {"type": "number"}`. That doesn't change which files validate, so Bruno chose to keep `schema_version` 1.0. The "bump on schema change" rule is for changes to what files are accepted. Timestamps must carry a timezone (`AwareDatetime`), so 0.6 must add an offset to the naive legacy `timestamp` values. `test_models.py` fails if the models and the schema drift apart.
- 0.6: Migrated pages live in `data/projects/legacy/pages/<id>/`: CNN 210 boxes, Adobe 12, Khan 1, Stack Overflow 1, for 224 total (218 accepted, 6 suggested). Each page's json/ and autosave files were merged, timestamps got −03:00, and one CNN box was clamped by 0.5 px. Legacy PNG heights are padded stitches (AUDIT #17), so don't trust normalized y on these pages. Pillow's decompression-bomb guard is off in `images.py` (screenshots are trusted and very tall).
- 0.7: CI (`.github/workflows/ci.yml`) runs on Python 3.11, the minimum we support, with `uv sync --locked`, so commit `backend/uv.lock` whenever dependencies change or CI fails. Add a frontend job once `frontend/` exists.
- 1.1: Adobe (Akamai, 403) and Stack Overflow (Cloudflare) block headless Chromium. We don't evade bot walls: 1.2 flags them, and `capture` already warns on HTTP ≥ 400. CNN, MDN and the Guardian capture with sticky headers once. Scroll with `behavior: 'instant'` and wait for `scrollY === 0`, because pages with `scroll-behavior: smooth` (MDN) otherwise draw sticky headers mid-page. Guardian images stay grey placeholders (lazy-load/consent). Revisit in 1.2/1.4. Playwright's sync API allows one instance per thread, so CLI browser tests live in their own module.
- 1.2: On the 89-URL list (Adobe was listed twice), headless Chromium gets about half: 41 blocked and 2 failed with HTTP/2 errors (washingtonpost, hotels). Every true block had a strong signal, so small file and one-viewport-tall only warn, because Google's minimal homepage has both. Block-page wording ("choose a country", "complete the verification") counts only on pages ≤ 1.5 viewports tall. Twitch and 500px are real but one viewport tall: Twitch scrolls inside its own panel, so `full_page` can't see past the first screen (open problem). Amazon now serves its real page.
- 1.2b: `--assist` passes a pause hook to `Capturer.capture`, which waits for the person and then captures the same page. `http_status` comes from the Navigation Timing API, so a passed check reports the real page's 200, not the first 403. On Bruno's PC, Playwright's bundled *headed* Chromium won't start (Windows side-by-side error, assembly 156.0.8078.4 missing, even after `--force` reinstall); headless works, so use `--browser msedge` or `--browser chrome` for `--assist`. Headed windows reserve 15 px for a scrollbar (1905 px pages), so launch always passes `--hide-scrollbars`. The manual ✅ (`--retry-blocked --assist` on `old-list`) is Bruno's to run.
- 1.3: `dom.json` is extracted at the same moment as the screenshot (scrolled to the top), so `fixed`, `sticky`, `100vh` and bottom-fixed elements line up within 2 px. A test checks this against pixels. Playwright's `full_page` doesn't resize the viewport, so `vh` units stay at 1080. Elements are clipped by scrolling/overflow ancestors (MDN's sidebar showed boxes for entries scrolled out of view); `<html>`/`<body>` overflow is ignored because it scrolls the window. Boxes *covered* by other elements (e.g. under a sticky filter) are still included, and removing them is 4.2's job. Not yet included: shadow DOM content and iframes (ads, embeds). Watch out in PowerShell: variable names ignore case, so `$P` and `$p` are the same variable.
- 1.4: The user agent is the browser's own plus `annotool/<version> (+repo URL)`. On the 89-URL list the block count stayed at 41, so identifying ourselves costs nothing. Capture resumes by default (pages with a `meta.json` are skipped); `--retry-blocked` adds blocked pages, `--recapture` redoes all, `--force` also redoes annotated ones. robots.txt uses our own RFC 9309 matcher (longest match, `*`, `$`), because `urllib.robotparser` wrongly disallowed google.com (it turns `Disallow: /?` into `/`) and quora.com (it ignores `Allow: /$`). Real `Disallow: /` for generic bots: reuters, imdb, academia, netflix, disneyplus, yelp. Kayak redirects mid-scroll ("Execution context was destroyed"), so capture re-runs the scroll pass on the new document (up to 3 tries).
- 2.1: Page ids are only unique inside a project, so `/api/pages/{id}` uses the `serve --project` one unless the request passes `?project=`. A save needs `If-Match` (428 if missing, 412 plus the current ETag if stale; a never-saved page's ETag is `"empty"`), and its labels must be taxonomy values (proposed ones are allowed). "Complete" means all 4 attributes are labeled, even on section boxes; revisit in 3.4. A PNG can't be decoded from the middle, so the first strip request cuts every strip in one pass (CNN: 2.2 s, 7 MB PNG → 1.4 MB of WebP). The cache is stamped with page.png's size and mtime. Starlette 1.x's TestClient wants the `httpx2` package, not `httpx`.
- 2.2: Node upgraded to 24 LTS and pnpm 12 installed via winget (Vite 8 / Vitest 5 need Node ≥ 20.19). The create-vite template now ships oxlint, which was swapped for ESLint as the stack says. Server response types in `src/api/types.ts` are hand-written mirrors of `server/routes.py` and `store.py`; only `src/api/annotation.ts` is generated, and CI fails if it's stale. The app shell lists the served project's pages; checked end to end with `annotool serve --project legacy`. A leftover `python` server from the 2.1 session was holding port 8765 (not stopped). New shells need PATH refreshed after winget installs.
- 2.3: The canvas uses native scrolling over a zoom-sized "world"; only strips within 800 screen px of the view are mounted, and boxes are filtered to the view. MIN_ZOOM is 0.2 so at most about 10 strips are decoded. Measured on the 91,086 px Unsplash legacy page (project `stress`, git-ignored) with Playwright: 60 fps (p95 17.8 ms, no frame > 50 ms) and a 146 MB peak across all Chromium processes, under the 500 MB budget. The first strip request cuts all 45 strips (28 s for Unsplash, one-off). Index tags cover the first characters inside a box, so consider moving them outside in 2.5. The browser pane can show a black canvas when the app window is in the background; trust Playwright screenshots. The unauthenticated GitHub API allows 60 requests/hour: check CI once (or read github.com/…/actions in the browser pane), don't poll every 20 s.
- 2.4: Edits go through `editor/history.ts` (immer `produceWithPatches`, 200 steps). `docVersion` bumps on every change including undo/redo, and autosave (`editor/autosave.ts`, 800 ms) saves while `docVersion !== savedVersion`, so undo is saved (AUDIT #7). Saves send `If-Match`; on 412 the store stays in `conflict`, further edits don't resume autosave, and a banner offers "Reload page". Switching pages calls `saveNow()` first. New boxes are `source: human`, `status: accepted`, with a ULID and `created_at`. Draw is the default tool (as in v2). Hit testing picks the smallest box. Checked end to end on `stress`: draw → saved, undo → saved, external edit → conflict and nothing overwritten.
- 2.5: The label panel, progress bars and box list are built only from the taxonomy (proposed options hidden unless already used). Labeling sets `label_sources: human` and `updated_at`; a relabeled non-human or suggested box becomes `status: edited`. Clicking the value already set is a no-op, and removing a label is the per-attribute × button. Click-to-remove was tried and dropped: confirming a label deleted it. Index tags now sit above boxes. `]`/`[` move through pages. UI checks that label must use a throwaway copy of a page; never label `data/projects/legacy` in tests. Testing-library: user-event types a literal `[` as `[[`.
- 2.6: `docs/PARITY.md` maps every v2 feature (docstring, toolbar, bindings, mouse handlers) to the new tool. Added for parity: Tab / Shift+Tab next/previous unlabeled box (like v2, Tab no longer moves focus), Ctrl+S save now (blocks the browser dialog), cursor x/y readout (written to the DOM, no re-render), and a toolbar (Draw/Select, Undo/Redo, Delete, zoom, Fit). The only temporary gap is keyboard labeling (v2's 1–9), which is 3.1–3.2. Pushing cancels the previous CI run on main (`cancel-in-progress`).
- 3.1: `keyboard/keymap.ts` builds label shortcuts from the taxonomy (attribute `hotkey`, then option `key`), and `useLabelKeys` listens in the capture phase so picker letters beat app keys (`d` in the Function picker = Dropdown). App-reserved keys (`d s x ? [ ] + = - _ space`, digits for 3.2 presets) can't be attribute hotkeys; conflicts disable that hotkey and show a banner. The ✅ test reads the real YAML through `src/test/webUi.ts`, which applies the server's defaults (`label` = id, option `status` = active); raw YAML lacks them. Tests have their own `tsconfig.test.json` (Node types), keeping Node globals out of app code. Gave buttons explicit `aria-label`s because jsdom counts `aria-hidden` key hints in names. Fixed a layout bug where box-list rows slid under the filters (the inspector now scrolls; the list keeps an 18rem minimum).
- GitHub: `origin` = https://github.com/brunomartignago/web_anatomy_annotation_tool (public). The repo name differs from the package/CLI name `annotool`, and that's intentional. Push to `main` after each committed roadmap item.
<!-- Claude Code: append dated, one-line learnings here -->
