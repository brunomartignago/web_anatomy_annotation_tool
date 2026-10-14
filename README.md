# annotool

An open-source tool for **annotating web page screenshots with a multi-axis UI taxonomy**. Every visible element gets one value on each of three axes, **Form** (what it looks like), **Function** (what it does) and **Component** (what it belongs to), and sits in a **template section** (Header, Columns, Panels, Footer…). Stacking many annotated pages reveals the recurring structures (archetypes) behind web layouts.

It is built for the research described at <https://brunomartignago.github.io/pages/research1.html>.

<!-- TODO (roadmap 7.4): replace with a short demo GIF -->
> 🎬 *Demo GIF coming soon.*

## Status

**Early rewrite.** The original tkinter tool lives in [`legacy/`](legacy/) and still works. The new version is a local web app: a Python backend for capture, rules and suggestions, and a browser frontend for annotating. It aims to cut the effort from at least 5 actions per box to about 1.5 by using boxes captured from the page's DOM, rule-based section detection, one-key presets and label inheritance.

See the [roadmap](docs/ROADMAP.md) for what's done and what's next.

## Quick start

### Today: the legacy tool

Requires Python 3.11+ and Pillow. It currently runs on **Windows only** (it uses a Windows-specific window call, see [AUDIT #9](docs/AUDIT.md)).

```bash
pip install pillow
python legacy/annotation_tool_v2.py
```

Open a screenshot with Ctrl+O, draw boxes with D, and label them in the left panel. Annotations autosave next to the image as `<image>.autosave.json`.

### Planned: the new tool

These commands will work as the roadmap progresses (Phase 0–2):

```bash
cd backend
uv sync
uv run playwright install chromium
uv run annotool capture ../examples/urls.csv --project demo
uv run annotool serve --project demo
```

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
