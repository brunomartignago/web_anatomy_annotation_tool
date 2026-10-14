# Contributing to annotool

Thanks for helping. You can contribute without writing code: proposing a taxonomy class, reporting a confusing label or sharing an annotated page are all useful.

## Proposing a taxonomy class

The labels live in one file, [`taxonomies/web-ui.yaml`](taxonomies/web-ui.yaml). The UI, keyboard shortcuts, presets and exporters are all generated from it, so a new class needs no code changes. Read [`docs/TAXONOMY.md`](docs/TAXONOMY.md) first for what each axis means.

1. **Open an issue** titled `Taxonomy proposal: <value>` with the `taxonomy-proposal` label. Include:
   - the new value and which axis it belongs to (Form, Function, Component or Template section);
   - 2–3 screenshots of real examples (crop them to the element);
   - why the existing values don't fit.
2. **If it's accepted, open a pull request** that adds the option to the YAML with `status: proposed` and a `key` that is unique within its attribute:
   ```yaml
   - { value: Video player, key: p, status: proposed }
   ```
   Proposed options stay hidden in the UI until the maintainer switches them to `active`.

**Never rename or remove an existing value.** Option values are research data and appear verbatim in every saved annotation. A rename or removal needs a migration in `backend/src/annotool/io/migrations/` and a `version` bump in the YAML, so discuss it in an issue first.

## Contributing code

The work is planned in [`docs/ROADMAP.md`](docs/ROADMAP.md). Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design.

- **One roadmap item per pull request.** If an item turns out bigger than expected, propose splitting it in the roadmap rather than growing the PR.
- **Write tests first** for pure logic: geometry, rules, migrations and exporters.
- **Run the checks** before opening a PR (once the backend exists, roadmap 0.3):
  ```bash
  cd backend
  uv run ruff check .
  uv run pytest
  ```
- **Keep it cross-platform.** Use `pathlib`, no hardcoded absolute paths, and nothing that only works on one OS. The code must run in Windows PowerShell and on macOS/Linux.

### Rules that protect the data

- **Never commit screenshots, `data/`, or any third-party site images.** Small JSON fixtures in `backend/tests/fixtures/` are fine.
- **Schema changes** bump `schema_version`, add a migration, and regenerate the TypeScript types in the same PR.
- **Suggestions never overwrite a human label.** Every box and label carries `source`, `status` and, when suggested, `confidence`.
- **Coordinates** are image pixels `[x, y, w, h]` with a top-left origin everywhere inside the app. Only exporters convert to other conventions.
- **Don't hardcode label names** in the frontend. Read them from the taxonomy YAML.

## Reporting bugs

Open an issue with what you did, what you expected and what happened. Include your OS and, if it's about a specific page, its URL rather than a screenshot of a third-party site.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
