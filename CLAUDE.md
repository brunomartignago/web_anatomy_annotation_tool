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
cd frontend; pnpm install; pnpm dev; pnpm test; pnpm gen:types
uv run annotool serve --project demo      # backend + built frontend
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
- GitHub: `origin` = https://github.com/brunomartignago/web_anatomy_annotation_tool (public). The repo name differs from the package/CLI name `annotool`, and that's intentional. Push to `main` after each committed roadmap item.
<!-- Claude Code: append dated, one-line learnings here -->
