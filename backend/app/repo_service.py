import hashlib
import shutil
from pathlib import Path

from git import Repo as GitRepo

SCRATCH_DIR = Path(__file__).resolve().parent.parent / ".scratch" / "repos"

DEFAULT_IGNORED_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", ".scratch"}


def repo_slug(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def clone_repo(url: str) -> Path:
    """Clone (or reuse an existing clone of) a repo URL into the scratch dir."""
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    dest = SCRATCH_DIR / repo_slug(url)

    if dest.exists():
        shutil.rmtree(dest)

    GitRepo.clone_from(url, dest, depth=1)
    return dest


def list_files(root: Path) -> list[str]:
    """Return relative file paths under root, skipping ignored directories."""
    files = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in DEFAULT_IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        files.append(str(path.relative_to(root)))
    return sorted(files)
