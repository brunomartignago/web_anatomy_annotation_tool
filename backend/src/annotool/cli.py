"""Command-line entry point: `annotool capture | serve | migrate | export | stats`.

Commands are added by later roadmap items.
"""

import json
import re
import shutil
from pathlib import Path
from typing import Annotated, Literal

import typer

from annotool import __version__

app = typer.Typer(
    name="annotool",
    help="Annotate web page screenshots with a multi-axis UI taxonomy.",
    no_args_is_help=True,
)

DEFAULT_TAXONOMY = Path("taxonomies") / "web-ui.yaml"

Browser = Literal["chromium", "chrome", "msedge"]


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"annotool {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", help="Show the version and exit.", callback=_print_version, is_eager=True
        ),
    ] = False,
) -> None:
    """Annotate web page screenshots with a multi-axis UI taxonomy."""


def _fail(message: str) -> typer.Exit:
    typer.echo(f"Error: {message}", err=True)
    return typer.Exit(code=1)


def _find_repo_root() -> Path | None:
    """The folder holding `taxonomies/web-ui.yaml`: the current one or a parent (e.g. backend/)."""
    for folder in [Path.cwd(), *Path.cwd().parents]:
        if (folder / DEFAULT_TAXONOMY).is_file():
            return folder
    return None


def _find_default_taxonomy() -> Path | None:
    root = _find_repo_root()
    return root / DEFAULT_TAXONOMY if root else None


def _page_id_from_image(image: Path) -> str:
    """`edition_cnn_com_full.png` -> `edition_cnn_com`."""
    stem = re.sub(r"_full$", "", image.stem.lower())
    return re.sub(r"[^a-z0-9_\-]+", "_", stem).strip("_") or "page"


@app.command()
def migrate(
    legacy_files: Annotated[
        list[Path],
        typer.Argument(
            exists=True,
            dir_okay=False,
            help="Legacy JSON file(s) for ONE screenshot (e.g. the json/ file and the autosave).",
        ),
    ],
    image: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="The screenshot these boxes belong to."),
    ],
    out: Annotated[
        Path,
        typer.Option(file_okay=False, help="Page folder to write page.png and annotations.json."),
    ],
    meta: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="Legacy capture metadata JSON."),
    ] = None,
    taxonomy: Annotated[
        Path | None, typer.Option(help="Taxonomy YAML. Default: taxonomies/web-ui.yaml.")
    ] = None,
    page_id: Annotated[
        str | None, typer.Option(help="Default: the image name without '_full'.")
    ] = None,
    tz_offset: Annotated[
        str, typer.Option(help="UTC offset of the legacy capture timestamps.")
    ] = "-03:00",
    force: Annotated[bool, typer.Option(help="Overwrite an existing annotations.json.")] = False,
) -> None:
    """Convert legacy tkinter annotations (v1/v2) to a schema v1 page folder."""
    from annotool.images import image_size
    from annotool.io.migrations.legacy_v0 import (
        LegacyMigrationError,
        migrate_legacy,
        parse_offset,
    )
    from annotool.project import write_json_atomic
    from annotool.taxonomy import TaxonomyError, load_taxonomy

    target = out / "annotations.json"
    if target.exists() and not force:
        raise _fail(f"{target} already exists. Use --force to overwrite it.")

    taxonomy_path = taxonomy or _find_default_taxonomy()
    if taxonomy_path is None:
        raise _fail("no taxonomy found. Pass --taxonomy <path to web-ui.yaml>.")

    try:
        tax = load_taxonomy(taxonomy_path)
        tz = parse_offset(tz_offset)
        width, height = image_size(image)
        files = [json.loads(p.read_text(encoding="utf-8")) for p in legacy_files]
        meta_data = json.loads(meta.read_text(encoding="utf-8")) if meta else None
        page = migrate_legacy(
            files,
            page_id=page_id or _page_id_from_image(image),
            image="page.png",
            width=width,
            height=height,
            taxonomy=tax,
            meta=meta_data,
            tz=tz,
        )
    except (LegacyMigrationError, TaxonomyError, ValueError, OSError) as exc:
        raise _fail(str(exc)) from exc

    out.mkdir(parents=True, exist_ok=True)
    if force or not (out / "page.png").exists():
        shutil.copyfile(image, out / "page.png")
    write_json_atomic(target, page.to_json_dict())

    accepted = sum(a.status == "accepted" for a in page.annotations)
    count = len(page.annotations)
    typer.echo(
        f"{page.page.id}: {count} box{'' if count == 1 else 'es'} "
        f"({accepted} accepted, {count - accepted} suggested) "
        f"from {page.history.migrated_from} -> {target}"
    )


@app.command()
def capture(
    sources: Annotated[
        list[str],
        typer.Argument(
            help="URLs (https://...) and/or URL-list CSV files, e.g. examples/urls.csv."
        ),
    ],
    project: Annotated[str, typer.Option(help="Project name (folder under data/projects/).")],
    data_dir: Annotated[
        Path | None, typer.Option(file_okay=False, help="Default: data/ in the repo root.")
    ] = None,
    force: Annotated[
        bool,
        typer.Option(help="Recapture everything, even pages that already have annotations.json."),
    ] = False,
    retry_blocked: Annotated[
        bool,
        typer.Option(help="Also recapture pages that were flagged blocked last time."),
    ] = False,
    recapture: Annotated[
        bool,
        typer.Option(help="Recapture pages that already have a capture (default: skip them)."),
    ] = False,
    delay: Annotated[
        float, typer.Option(min=0, help="Seconds between two pages on the same site.")
    ] = 5.0,
    obey_robots: Annotated[
        bool,
        typer.Option(help="Skip pages robots.txt disallows (default: capture and warn)."),
    ] = False,
    browser: Annotated[
        Browser,
        typer.Option(
            help="chromium = Playwright's bundled build; chrome / msedge = the one installed "
            "here (use one of these for --assist if the bundled build won't open a window)."
        ),
    ] = "chromium",
    assist: Annotated[
        bool,
        typer.Option(
            help="Open a visible browser and wait for you to handle each page's check "
            "(country, 'I'm not a robot'...) before capturing. Usually with --retry-blocked."
        ),
    ] = False,
) -> None:
    """Take full-page screenshots (1920x1080 viewport) and write page.png + meta.json.

    Re-running resumes: pages that already have a capture are skipped. Pages showing a bot
    wall, error page or blank screen are flagged `blocked` in meta.json. Consent banners are
    dismissed with project.yaml › consent_clicks. Requests identify the project in their user
    agent, wait `--delay` seconds between pages of one site, and check robots.txt.
    """
    from annotool.capture.browser import META_NAME, Capturer, CaptureSettings
    from annotool.capture.polite import HostThrottle, RobotsChecker, fetch_robots
    from annotool.capture.urls import UrlListError, entries_from_sources
    from annotool.project import ensure_project, load_project_config, page_dir, project_dir

    notes: list[str] = []
    try:
        entries = entries_from_sources(sources, notes=notes)
    except (UrlListError, OSError) as exc:
        raise _fail(str(exc)) from exc
    for note in notes:
        typer.echo(f"Note: {note}")
    if data_dir is None:
        root = _find_repo_root()
        if root is None:
            raise _fail("can't find the repo's data/ folder. Pass --data-dir.")
        data_dir = root / "data"
    try:
        ensure_project(data_dir, project, sources=sources)
        consent_clicks = load_project_config(data_dir, project).get("consent_clicks") or []
    except ValueError as exc:
        raise _fail(str(exc)) from exc

    captured: list[str] = []
    blocked: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    already = 0
    try:
        settings = CaptureSettings(
            headless=not assist, channel=None if browser == "chromium" else browser
        )
        capturer = Capturer(settings).__enter__()
    except Exception as exc:
        raise _fail(
            f"can't start Chromium ({exc}). Run: uv run playwright install chromium"
        ) from exc
    throttle = HostThrottle(delay)
    robots = RobotsChecker(fetch=lambda url: fetch_robots(url, capturer.user_agent))
    try:
        for n, entry in enumerate(entries, start=1):
            prefix = f"[{n}/{len(entries)}] {entry.page_id}"
            folder = page_dir(data_dir, project, entry.page_id)
            if (folder / "annotations.json").exists() and not force:
                typer.echo(f"{prefix}: skipped (has annotations.json; use --force to recapture)")
                continue
            meta_path = folder / META_NAME
            if meta_path.exists() and not (force or recapture):
                if not (retry_blocked and _was_blocked_or_failed(meta_path)):
                    already += 1  # resume: this page already has a capture
                    continue
            robots_allowed = robots.allows(entry.url)
            if robots_allowed is False and obey_robots:
                skipped.append(entry.page_id)
                typer.echo(f"{prefix}: skipped (disallowed by robots.txt)")
                continue
            throttle.wait(entry.url)
            try:
                meta = capturer.capture(
                    entry,
                    folder,
                    consent_clicks=consent_clicks,
                    before_capture=_ask_person(prefix) if assist else None,
                    robots_allowed=robots_allowed,
                )
            except _StopBatch:
                typer.echo(f"{prefix}: stopped; later pages were not captured")
                break
            except Exception as exc:  # one bad page must not stop the batch
                failed.append(entry.page_id)
                typer.echo(f"{prefix}: failed: {str(exc).splitlines()[0]}")
                continue
            if meta is None:
                skipped.append(entry.page_id)
                typer.echo(f"{prefix}: skipped")
                continue
            captured.append(entry.page_id)
            status = f"{meta.width}x{meta.height} px in {meta.duration_s:.1f}s"
            if meta.blocked:
                blocked.append(entry.page_id)
                status = f"BLOCKED ({'; '.join(meta.blocked_reasons)})"
            typer.echo(f"{prefix}: {status}")
            for warning in meta.warnings:
                typer.echo(f"{prefix}: warning: {warning}")
    finally:
        capturer.__exit__(None, None, None)

    typer.echo(
        f"Done: {len(captured)} captured, {len(blocked)} blocked, {len(skipped)} skipped, "
        f"{len(failed)} failed, {already} already captured -> {project_dir(data_dir, project)}"
    )
    if already:
        typer.echo("(already captured pages were left as they are; use --recapture to redo them)")
    if blocked:
        typer.echo(f"Blocked: {', '.join(blocked)} (retry later with --retry-blocked)")
    if failed:
        typer.echo(f"Failed: {', '.join(failed)}")
        raise typer.Exit(code=1)


class _StopBatch(Exception):
    """The person typed `q` during assisted capture."""


def _ask_person(prefix: str):
    """Pause hook for --assist: the person handles the page, then answers in the terminal."""

    def ask(page) -> bool:
        typer.echo(
            f"{prefix}: open in the browser window. Handle anything the page asks for there "
            "(country, 'I'm not a robot', banners), then press Enter here to capture. "
            "s = skip, q = quit."
        )
        answer = typer.prompt("", default="", show_default=False, prompt_suffix="> ")
        answer = answer.strip().lower()
        if answer == "q":
            raise _StopBatch
        return answer != "s"

    return ask


def _was_blocked_or_failed(meta_path: Path) -> bool:
    """True if the last capture was blocked, or there is no successful capture yet."""
    try:
        return bool(json.loads(meta_path.read_text(encoding="utf-8")).get("blocked"))
    except (OSError, ValueError):
        return True


@app.command("debug-dom")
def debug_dom(
    page: Annotated[
        Path,
        typer.Argument(
            file_okay=False,
            help="Page folder, e.g. data/projects/probe/pages/edition_cnn_com",
        ),
    ],
) -> None:
    """Draw dom.json boxes on page.png to check they line up (writes debug-dom.png)."""
    from pydantic import ValidationError

    from annotool.capture.browser import IMAGE_NAME
    from annotool.capture.debug import render_dom_overlay
    from annotool.capture.dom import DOM_NAME, DomSnapshot

    dom_path, image_path = page / DOM_NAME, page / IMAGE_NAME
    if not dom_path.exists() or not image_path.exists():
        raise _fail(f"{page} needs {IMAGE_NAME} and {DOM_NAME}; capture the page first.")
    try:
        dom = DomSnapshot.model_validate_json(dom_path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise _fail(f"{dom_path} is not a valid dom.json: {exc}") from exc

    out = page / "debug-dom.png"
    counts = render_dom_overlay(image_path, dom, out)
    summary = ", ".join(f"{n} {kind}" for kind, n in counts.items())
    typer.echo(f"{len(dom.elements)} elements ({summary}) -> {out}")


@app.command()
def suggest(
    project: Annotated[str, typer.Argument(help="Project name (folder under data/projects/).")],
    data_dir: Annotated[
        Path | None, typer.Option(file_okay=False, help="Default: data/ in the repo root.")
    ] = None,
    taxonomy: Annotated[
        Path | None, typer.Option(help="Taxonomy YAML. Default: taxonomies/web-ui.yaml.")
    ] = None,
    page: Annotated[
        list[str] | None, typer.Option(help="Only this page id (repeat for several).")
    ] = None,
    only: Annotated[
        list[str] | None, typer.Option(help="Only this suggester, e.g. dom (repeatable).")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option(help="Report what would change without writing anything.")
    ] = False,
) -> None:
    """Run the suggesters on every page of a project and save their proposals.

    A person's labels are never overwritten, boxes they rejected are not proposed again,
    and running it twice adds nothing new. Blocked captures are skipped.
    """
    from annotool import suggest as suggest_package
    from annotool.server.store import PageNotFound, PageStore, StaleWrite
    from annotool.suggest.base import run_suggesters
    from annotool.taxonomy import TaxonomyError, load_taxonomy

    if data_dir is None:
        root = _find_repo_root()
        if root is None:
            raise _fail("can't find the repo's data/ folder. Pass --data-dir.")
        data_dir = root / "data"
    taxonomy_path = taxonomy or _find_default_taxonomy()
    if taxonomy_path is None:
        raise _fail("no taxonomy found. Pass --taxonomy <path to web-ui.yaml>.")
    try:
        tax = load_taxonomy(taxonomy_path)
    except TaxonomyError as exc:
        raise _fail(str(exc)) from exc

    suggesters = suggest_package.default_suggesters(tax)
    if not suggesters:
        typer.echo(
            "No suggesters are registered yet: the DOM, rule and prior suggesters arrive in "
            "roadmap 4.2-4.4. Nothing to do."
        )
        return
    if only:
        unknown = sorted(set(only) - {s.id for s in suggesters})
        if unknown:
            known = ", ".join(s.id for s in suggesters)
            raise _fail(f"unknown suggester(s) {', '.join(unknown)} (registered: {known})")
        suggesters = [s for s in suggesters if s.id in only]

    store = PageStore(data_dir, tax)
    try:
        summaries = {s.id: s for s in store.list_pages(project)}
    except PageNotFound as exc:
        raise _fail(str(exc)) from exc
    page_ids = page or list(summaries)
    missing = [p for p in page_ids if p not in summaries]
    if missing:
        raise _fail(f"no page(s) {', '.join(missing)} in project {project!r}")

    changed_pages = 0
    failed = False
    for page_id in page_ids:
        if summaries[page_id].blocked:
            typer.echo(f"{page_id}: skipped (blocked capture)")
            continue
        try:
            loaded = store.load(project, page_id)
        except (PageNotFound, ValueError) as exc:
            typer.echo(f"{page_id}: skipped ({str(exc).splitlines()[0]})")
            continue
        result, reports = run_suggesters(
            loaded.page, suggesters, taxonomy=tax, folder=loaded.folder
        )
        parts = []
        for r in reports:
            if r.error:
                failed = True
                parts.append(f"{r.suggester} FAILED: {r.error}")
                continue
            boxes = f"+{r.boxes_added} box{'' if r.boxes_added == 1 else 'es'}"
            labels = f"{r.labels_set} label{'' if r.labels_set == 1 else 's'}"
            kept = f", kept {r.kept_human} of yours" if r.kept_human else ""
            parts.append(f"{r.suggester} {boxes}, {labels}{kept}")
            for problem in r.dropped:
                typer.echo(f"{page_id}: {r.suggester} dropped: {problem}")
        if any(r.changed for r in reports):
            changed_pages += 1
            if not dry_run:
                try:
                    store.save(project, page_id, result, if_match=loaded.etag)
                except StaleWrite:
                    failed = True
                    parts.append("NOT SAVED: the file changed while suggesting")
        typer.echo(f"{page_id}: {'; '.join(parts)}")

    note = " (dry run: nothing written)" if dry_run else ""
    typer.echo(f"Done: {len(page_ids)} pages, {changed_pages} changed{note}")
    if failed:
        raise typer.Exit(code=1)


@app.command()
def serve(
    project: Annotated[str, typer.Option(help="Project to open (folder under data/projects/).")],
    data_dir: Annotated[
        Path | None, typer.Option(file_okay=False, help="Default: data/ in the repo root.")
    ] = None,
    taxonomy: Annotated[
        Path | None, typer.Option(help="Taxonomy YAML. Default: taxonomies/web-ui.yaml.")
    ] = None,
    host: Annotated[
        str, typer.Option(help="Address to listen on. Keep 127.0.0.1: there is no login.")
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65535)] = 8000,
    open_browser: Annotated[
        bool, typer.Option("--open/--no-open", help="Open the annotator in your browser.")
    ] = True,
) -> None:
    """Start the local annotator (API + UI) for one project and open it in the browser."""
    import threading
    import webbrowser

    import uvicorn

    from annotool.server.app import create_app
    from annotool.taxonomy import TaxonomyError

    root = _find_repo_root()
    if data_dir is None:
        if root is None:
            raise _fail("can't find the repo's data/ folder. Pass --data-dir.")
        data_dir = root / "data"
    taxonomy_path = taxonomy or _find_default_taxonomy()
    if taxonomy_path is None:
        raise _fail("no taxonomy found. Pass --taxonomy <path to web-ui.yaml>.")
    frontend = root / "frontend" / "dist" if root else None

    try:
        asgi_app = create_app(data_dir, project, taxonomy_path, frontend_dir=frontend)
    except (TaxonomyError, ValueError) as exc:
        projects = data_dir / "projects"
        names = (
            sorted(p.name for p in projects.iterdir() if p.is_dir()) if projects.is_dir() else []
        )
        hint = f" Projects: {', '.join(names)}." if names else ""
        raise _fail(f"{exc}.{hint}") from exc

    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}"
    typer.echo(f"annotool: serving project {project!r} at {url} (Ctrl+C to stop)")
    if open_browser:
        # uvicorn.run blocks, so open the page once the server has had a moment to start.
        threading.Timer(1.0, webbrowser.open, args=[url]).start()
    uvicorn.run(asgi_app, host=host, port=port, log_level="info")
