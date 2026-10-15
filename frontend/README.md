# annotool frontend

The annotator UI: Vite + React + TypeScript, with zustand + immer for state. Requires Node 22.12+ and pnpm.

```bash
pnpm install
pnpm dev          # UI on http://localhost:5173, forwards /api to `annotool serve` on :8000
pnpm test         # Vitest
pnpm lint         # ESLint
pnpm build        # dist/, which `annotool serve` serves on its own
pnpm gen:types    # regenerate src/api/annotation.ts from schema/annotation.v1.schema.json
```

For development, run the backend in a second terminal: `cd ../backend; uv run annotool serve --project <name> --no-open`.

`src/api/annotation.ts` is generated. Never edit it by hand: change the JSON Schema and run `pnpm gen:types` (CI checks they match).
