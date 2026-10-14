# Kickoff prompts for Claude Code

Open Claude Code in the repo root (the folder that contains `CLAUDE.md`). Paste one prompt per session. Start each session in plan mode (Shift+Tab twice), review the plan, then let it run.

---

### First session: orientation (no code changes)
```
Read CLAUDE.md and everything in docs/, then skim legacy/annotation_tool_v2.py
(or ./annotation_tool_v2.py if task 0.1 isn't done yet) and taxonomies/web-ui.yaml.
Don't change anything yet. Tell me:
1) anything in the roadmap you think is mis-ordered, missing or too big for one PR,
2) any conflict between the YAML, the JSON Schema and the legacy data,
3) the exact plan for task 0.1.
```

### Any roadmap item
```
Do roadmap item <N.N> from docs/ROADMAP.md.
Restate its ✅ acceptance criteria, list the files you'll touch, and write tests first
where the logic is pure. Stop and ask me at any 🟡 DECIDE. When done: run the tests,
tick the box in ROADMAP.md, add a one-line note to CLAUDE.md › Notes, and give me a
commit message that references the AUDIT item numbers it fixes.
```

### Task 0.6: legacy migration (worth a dedicated prompt)
```
Do roadmap 0.6. The legacy files are in data/legacy/. Before writing the migration,
print a table per file: box count, complete count, inverted boxes, unknown label values
(compared with taxonomies/web-ui.yaml). Then write io/migrations/legacy_v0.py + tests.
Verify: 224 boxes in, 224 out, all validate against schema/annotation.v1.schema.json.
```

### Task 1.3: DOM extraction (the foundation of the "intelligence")
```
Do roadmap 1.3. Capture these 3 pages into a project called "probe":
https://www.wikipedia.org, https://stackoverflow.com, https://edition.cnn.com.
Then generate the debug overlay for each and show me the PNG paths. I want to
check alignment myself before we build suggesters on top of it.
```

### Task 4.2: measuring the DOM suggester
```
Do roadmap 4.2. Use the migrated CNN page as ground truth. Report box recall at IoU≥0.5,
precision, and per-attribute accuracy for Form/Function/Component, plus a confusion
table for Function. Put the numbers in docs/EVAL.md and propose the 3 dom_hints
changes with the biggest expected gain. Don't apply them without asking me.
```

### When something feels off
```
Stop. Summarize what you've changed so far, what's uncommitted, and what's failing.
Don't fix anything yet.
```
