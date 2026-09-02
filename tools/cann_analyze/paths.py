from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    env = os.environ.get("CANN_ANALYZE_HOME")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    for candidate in (here.parents[2], Path.cwd(), *Path.cwd().parents):
        if (candidate / "catalogs" / "repos.json").is_file():
            return candidate
    return here.parents[2]


def catalogs_dir() -> Path:
    return project_root() / "catalogs"


def data_dir() -> Path:
    env = os.environ.get("CANN_ANALYZE_DATA")
    if env:
        return Path(env).expanduser().resolve()
    path = project_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def index_path() -> Path:
    path = data_dir() / "indexes"
    path.mkdir(parents=True, exist_ok=True)
    return path / "sites.sqlite"


def skills_dir() -> Path:
    return project_root() / "skills"


def mirrors_dir() -> Path:
    path = data_dir() / "mirrors"
    path.mkdir(parents=True, exist_ok=True)
    return path
