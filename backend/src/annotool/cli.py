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
        bool, typer.Option(help="Recapture pages that already have annotations.json.")
    ] = False,
    retry_blocked: Annotated[
        bool,
        typer.Option(help="Only capture pages that were blocked or failed last time."),
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

    Pages showing a bot wall, error page or blank screen are flagged `blocked` in
    meta.json. Consent banners are dismissed with project.yaml › consent_clicks.
    """
    from annotool.capture.browser import META_NAME, Capturer, CaptureSettings
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
    try:
        settings = CaptureSettings(
            headless=not assist, channel=None if browser == "chromium" else browser
        )
        capturer = Capturer(settings).__enter__()
    except Exception as exc:
        raise _fail(
            f"can't start Chromium ({exc}). Run: uv run playwright install chromium"
        ) from exc
    try:
        for n, entry in enumerate(entries, start=1):
            prefix = f"[{n}/{len(entries)}] {entry.page_id}"
            folder = page_dir(data_dir, project, entry.page_id)
            if (folder / "annotations.json").exists() and not force:
                typer.echo(f"{prefix}: skipped (has annotations.json; use --force to recapture)")
                continue
            if retry_blocked and not _was_blocked_or_failed(folder / META_NAME):
                continue
            try:
                meta = capturer.capture(
                    entry,
                    folder,
                    consent_clicks=consent_clicks,
                    before_capture=_ask_person(prefix) if assist else None,
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
        f"{len(failed)} failed -> {project_dir(data_dir, project)}"
    )
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
