"""REST routes under /api.

Page ids are unique only inside a project, so `/api/pages/{id}` uses the project given to
`annotool serve --project`, unless the request passes `?project=<name>`.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from annotool.models import PageFile
from annotool.server.store import (
    IMAGE_NAME,
    InvalidPage,
    PageNotFound,
    PageStore,
    PageSummary,
    Progress,
    ProjectSummary,
    StaleWrite,
    page_progress,
)
from annotool.server.tiles import STRIP_HEIGHT, StripCache

router = APIRouter(prefix="/api")

ProjectParam = Annotated[
    str | None, Query(description="Default: the project the server was started with.")
]


class ProjectsResponse(BaseModel):
    current: str
    projects: list[ProjectSummary]


class StripInfo(BaseModel):
    height: int  # rows per strip; the last strip is shorter
    count: int


class PageResponse(BaseModel):
    project: str
    etag: str  # send back in If-Match when saving
    annotations: PageFile
    meta: dict[str, Any] | None = None  # meta.json from capture, if any
    has_dom: bool
    strips: StripInfo


class SaveResponse(BaseModel):
    etag: str
    progress: Progress


def _store(request: Request) -> PageStore:
    return request.app.state.store


def _project(request: Request, project: str | None) -> str:
    return project or request.app.state.project


def _not_found(exc: PageNotFound) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/taxonomy")
def get_taxonomy(request: Request) -> dict[str, Any]:
    """The taxonomy YAML as JSON: attributes, options, keys, presets and rules."""
    return request.app.state.taxonomy.model_dump(mode="json")


@router.get("/projects")
def list_projects(request: Request) -> ProjectsResponse:
    return ProjectsResponse(current=request.app.state.project, projects=_store(request).projects())


@router.get("/projects/{project}/pages")
def list_pages(request: Request, project: str) -> list[PageSummary]:
    """Every captured or annotated page, sorted by id, with its progress counts."""
    try:
        return _store(request).list_pages(project)
    except PageNotFound as exc:
        raise _not_found(exc) from exc


@router.get("/pages/{page_id}", response_model=PageResponse, response_model_exclude_none=True)
def get_page(request: Request, response: Response, page_id: str, project: ProjectParam = None):
    """The page's annotations (empty for a page never saved), its capture metadata and
    how many strips its screenshot has. The ETag header guards the next save."""
    name = _project(request, project)
    try:
        loaded = _store(request).load(name, page_id)
    except PageNotFound as exc:
        raise _not_found(exc) from exc
    image = loaded.folder / IMAGE_NAME
    count = StripCache(loaded.folder, IMAGE_NAME).count() if image.exists() else 0
    response.headers["ETag"] = loaded.etag
    response.headers["Cache-Control"] = "no-store"
    return PageResponse(
        project=name,
        etag=loaded.etag,
        annotations=loaded.page,
        meta=loaded.meta,
        has_dom=loaded.has_dom,
        strips=StripInfo(height=STRIP_HEIGHT, count=count),
    )


@router.put(
    "/pages/{page_id}/annotations",
    responses={
        412: {"description": "The file changed since it was loaded; reload and merge."},
        428: {"description": "If-Match header missing."},
    },
)
def save_annotations(
    request: Request,
    response: Response,
    page_id: str,
    page: PageFile,
    if_match: Annotated[str | None, Header()] = None,
    project: ProjectParam = None,
) -> SaveResponse:
    """Replace annotations.json (atomic write). Send the ETag from the last load or save."""
    if not if_match:
        raise HTTPException(status_code=428, detail="send the page's ETag in If-Match")
    store = _store(request)
    try:
        etag = store.save(_project(request, project), page_id, page, if_match=if_match)
    except PageNotFound as exc:
        raise _not_found(exc) from exc
    except InvalidPage as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    except StaleWrite as exc:
        return JSONResponse(
            status_code=412,
            content={"detail": str(exc), "etag": exc.current_etag},
            headers={"ETag": exc.current_etag},
        )
    response.headers["ETag"] = etag
    return SaveResponse(etag=etag, progress=page_progress(page, store.attribute_ids))


@router.get(
    "/pages/{page_id}/strips/{n}.webp",
    response_class=FileResponse,
    responses={200: {"content": {"image/webp": {}}}, 304: {"description": "Not modified."}},
)
def get_strip(
    request: Request,
    page_id: str,
    n: int,
    project: ProjectParam = None,
    if_none_match: Annotated[str | None, Header()] = None,
):
    """Rows n*2048 … (n+1)*2048 of the screenshot as WebP. Cut and cached on first use."""
    try:
        folder = _store(request).page_folder(_project(request, project), page_id)
        cache = StripCache(folder, IMAGE_NAME)
        etag = f'"{cache.version()}-{n}"'
    except (PageNotFound, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=f"no screenshot for page {page_id!r}") from exc
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if if_none_match and etag in [t.strip().removeprefix("W/") for t in if_none_match.split(",")]:
        return Response(status_code=304, headers=headers)
    try:
        path = cache.path(n)
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type="image/webp", headers=headers)
