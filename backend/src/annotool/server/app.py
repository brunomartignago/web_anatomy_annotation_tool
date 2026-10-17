"""FastAPI app: the REST API plus, once `frontend/` is built, the annotator UI.

Everything runs locally (`annotool serve` binds to 127.0.0.1); there are no accounts.
"""

from collections.abc import Sequence
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from annotool import __version__
from annotool import suggest as suggest_package
from annotool.project import project_dir
from annotool.server.routes import router
from annotool.server.store import PageStore
from annotool.suggest.base import Suggester
from annotool.taxonomy import load_taxonomy

_NO_FRONTEND = """<!doctype html>
<meta charset="utf-8"><title>annotool</title>
<body style="font-family: system-ui, sans-serif; max-width: 40rem; margin: 3rem auto">
<h1>annotool API is running</h1>
<p>Serving project <b>{project}</b>. The annotator UI isn't built yet
(<code>cd frontend; pnpm install; pnpm build</code>, roadmap 2.2+).</p>
<p>Try the API at <a href="/docs">/docs</a>.</p>
</body>
"""


def create_app(
    data_dir: Path,
    project: str,
    taxonomy_path: Path,
    frontend_dir: Path | None = None,
    suggesters: Sequence[Suggester] | None = None,
) -> FastAPI:
    """The app for one served project. Raises ValueError if the project doesn't exist.

    `suggesters` defaults to the registry in `annotool.suggest` (tests pass their own)."""
    folder = project_dir(data_dir, project)
    if not folder.is_dir():
        raise ValueError(f"no project {project!r} in {Path(data_dir) / 'projects'}")
    taxonomy = load_taxonomy(taxonomy_path)

    app = FastAPI(title="annotool", version=__version__)
    app.state.project = project
    app.state.taxonomy = taxonomy
    app.state.store = PageStore(data_dir, taxonomy)
    app.state.suggesters = list(
        suggest_package.default_suggesters(taxonomy) if suggesters is None else suggesters
    )
    app.include_router(router)

    if frontend_dir is not None and (frontend_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    else:

        @app.get("/", include_in_schema=False)
        def no_frontend() -> HTMLResponse:
            return HTMLResponse(_NO_FRONTEND.format(project=project))

    return app
