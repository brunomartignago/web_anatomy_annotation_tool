"""Project and page folder I/O.

Layout (git-ignored): data/projects/<project>/project.yaml and pages/<page_id>/.
"""

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_FILE = "project.yaml"
_NAME = re.compile(r"^[a-z0-9_\-]+$")


def project_dir(data_dir: Path, name: str) -> Path:
    if not _NAME.match(name):
        raise ValueError(f"project name {name!r} may only use a-z, 0-9, '_' and '-'")
    return Path(data_dir) / "projects" / name


def page_dir(data_dir: Path, project: str, page_id: str) -> Path:
    return project_dir(data_dir, project) / "pages" / page_id


def ensure_project(
    data_dir: Path, name: str, *, taxonomy: str = "web-ui", sources: list[str] | None = None
) -> Path:
    """Create the project folder and `project.yaml` if they don't exist yet."""
    folder = project_dir(data_dir, name)
    config = folder / PROJECT_FILE
    if not config.exists():
        folder.mkdir(parents=True, exist_ok=True)
        data = {
            "name": name,
            "taxonomy": taxonomy,
            "sources": sources or [],
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return folder


def write_json_atomic(path: Path, data: Any) -> None:
    """Write JSON so readers never see a half-written file: temp file, then os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
