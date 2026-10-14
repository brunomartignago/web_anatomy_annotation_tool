# annotool

An open-source tool for **annotating web page screenshots with a multi-axis UI taxonomy**. Every visible element gets one value on each of three axes, **Form** (what it looks like), **Function** (what it does) and **Component** (what it belongs to), and sits in a **template section** (Header, Columns, Panels, Footer…). Stacking many annotated pages reveals the recurring structures (archetypes) behind web layouts.

It is built for the research described at <https://brunomartignago.github.io/pages/research1.html>.

<!-- TODO (roadmap 7.4): replace with a short demo GIF -->
> 🎬 *Demo GIF coming soon.*

## Status

**Early rewrite.** The original tkinter tool lives in [`legacy/`](legacy/) and still works. The new version is a local web app: a Python backend for capture, rules and suggestions, and a browser frontend for annotating. It aims to cut the effort from at least 5 actions per box to about 1.5 by using boxes captured from the page's DOM, rule-based section detection, one-key presets and label inheritance.

See the [roadmap](docs/ROADMAP.md) for what's done and what's next.

## Quick start

```bash
git clone https://github.com/brunomartignago/web_anatomy_annotation_tool.git
cd web_anatomy_annotation_tool
```

### Today: the legacy tool

Requires Python 3.11+ and Pillow. It currently runs on **Windows only** (it uses a Windows-specific window call, see [AUDIT #9](docs/AUDIT.md)).

```bash
pip install pillow
python legacy/annotation_tool_v2.py
```

Open a screenshot with Ctrl+O, draw boxes with D, and label them in the left panel. Annotations autosave next to the image as `<image>.autosave.json`.

### The new tool (in progress)

Capturing pages works today. Requires [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync
uv run playwright install chromium
uv run annotool capture ../examples/urls.csv --project demo
```

Each page lands in `data/projects/demo/pages/<page id>/` as `page.png` plus `meta.json`. Pages that show a bot check, region block or error page instead of the real site get `"blocked": true` with the reasons. Recapture them later with `--retry-blocked`.

Many sites block automated browsers. For those, use **assisted capture**: a visible browser opens each blocked page, you handle whatever it asks for (choose a country, tick "I'm not a robot"), then press Enter in the terminal and the tool captures that page. `s` skips a page, `q` stops. The tool never solves these checks itself.

```bash
uv run annotool capture ../examples/urls.csv --project demo --retry-blocked --assist --browser msedge
```

`--browser chrome` or `--browser msedge` uses the browser installed on your computer instead of Playwright's bundled Chromium. To dismiss cookie banners before the screenshot, list the button selectors in `data/projects/demo/project.yaml`, preferably the "Reject all" ones:

```yaml
consent_clicks:
  - "#onetrust-reject-all-handler"
```

The annotation UI (`annotool serve`) comes in Phase 2 of the [roadmap](docs/ROADMAP.md).

## How it's organized

| Path | What it is |
|---|---|
| [`taxonomies/web-ui.yaml`](taxonomies/web-ui.yaml) | **Source of truth** for labels, keyboard mnemonics, presets and suggestion rules |
| [`schema/annotation.v1.schema.json`](schema/annotation.v1.schema.json) | The annotation file format, shared by backend and frontend |
| [`docs/`](docs/) | [Architecture](docs/ARCHITECTURE.md), [taxonomy](docs/TAXONOMY.md), [audit of the legacy code](docs/AUDIT.md), [roadmap](docs/ROADMAP.md) |
| [`examples/urls.csv`](examples/urls.csv) | Seed list of 90 public websites by category |
| [`legacy/`](legacy/) | The original tkinter tool, kept for reference |

## Data policy

This repository publishes **annotations, URL lists and the capture script**, but **not screenshots** of third-party websites. Those pages belong to their owners. To reproduce a dataset, capture the pages yourself from the URL list. Captured data lives in `data/`, which is git-ignored.

## Contributing

Contributions are welcome, especially new taxonomy classes, exporters and suggesters. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Bruno Martignago
