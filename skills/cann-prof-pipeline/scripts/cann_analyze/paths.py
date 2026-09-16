from __future__ import annotations

import os
import shutil
from pathlib import Path


def project_root() -> Path:
    env = os.environ.get("CANN_ANALYZE_HOME")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    for candidate in (here.parent, here.parents[1], here.parents[2], Path.cwd(), *Path.cwd().parents):
        if (candidate / "catalogs" / "repos.json").is_file():
            return candidate
    return here.parents[1]


def catalogs_dir() -> Path:
    return project_root() / "catalogs"


def data_dir() -> Path:
    env = os.environ.get("CANN_ANALYZE_DATA")
    if env:
        return Path(env).expanduser().resolve()
    path = project_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def bundled_index_path() -> Path:
    return catalogs_dir() / "baseline" / "sites.sqlite"


def overlay_index_path() -> Path:
    path = data_dir() / "indexes"
    path.mkdir(parents=True, exist_ok=True)
    return path / "sites.sqlite"


def index_path(*, write: bool = False) -> Path:
    """Writable overlay in data/indexes; locate falls back to shipped catalogs/baseline."""
    overlay = overlay_index_path()
    bundled = bundled_index_path()
    if write:
        if not overlay.is_file() and bundled.is_file():
            shutil.copy2(bundled, overlay)
        return overlay
    if overlay.is_file():
        return overlay
    if bundled.is_file():
        return bundled
    return overlay


def skills_dir() -> Path:
    return project_root() / "skills"


def mirrors_dir() -> Path:
    path = data_dir() / "mirrors"
    path.mkdir(parents=True, exist_ok=True)
    return path
