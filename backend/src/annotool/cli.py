"""Command-line entry point: `annotool capture | serve | migrate | export | stats`.

Commands are added by later roadmap items.
"""

import json
import re
import shutil
from pathlib import Path
from typing import Annotated

import typer

from annotool import __version__

app = typer.Typer(
    name="annotool",
    help="Annotate web page screenshots with a multi-axis UI taxonomy.",
    no_args_is_help=True,
)

DEFAULT_TAXONOMY = Path("taxonomies") / "web-ui.yaml"


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
) -> None:
    """Take full-page screenshots (1920x1080 viewport) and write page.png + meta.json."""
    from annotool.capture.browser import Capturer
    from annotool.capture.urls import UrlListError, entries_from_sources
    from annotool.project import ensure_project, page_dir

    try:
        entries = entries_from_sources(sources)
    except (UrlListError, OSError) as exc:
        raise _fail(str(exc)) from exc
    if data_dir is None:
        root = _find_repo_root()
        if root is None:
            raise _fail("can't find the repo's data/ folder. Pass --data-dir.")
        data_dir = root / "data"
    try:
        ensure_project(data_dir, project, sources=sources)
    except ValueError as exc:
        raise _fail(str(exc)) from exc

    failed: list[str] = []
    try:
        capturer = Capturer().__enter__()
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
            try:
                meta = capturer.capture(entry, folder)
            except Exception as exc:  # one bad page must not stop the batch
                failed.append(entry.page_id)
                typer.echo(f"{prefix}: failed: {str(exc).splitlines()[0]}")
                continue
            typer.echo(f"{prefix}: {meta.width}x{meta.height} px in {meta.duration_s:.1f}s")
            if meta.http_status and meta.http_status >= 400:
                # Usually a bot wall or "Access Denied" page. Roadmap 1.2 flags these properly.
                typer.echo(f"{prefix}: warning: HTTP {meta.http_status} ({meta.title})")
    finally:
        capturer.__exit__(None, None, None)

    typer.echo(f"Done: {len(entries) - len(failed)} of {len(entries)} pages -> {data_dir}")
    if failed:
        typer.echo(f"{len(failed)} failed: {', '.join(failed)}")
        raise typer.Exit(code=1)
