from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist_private"
STAGE = OUT / "hqp_runtime_internal"

KEEP = {
    "src",
    "tools",
    "pyproject.toml",
    "README.md",
    "requirements.txt",
    "requirements-dev.txt",
    "LICENSE",
    "MANIFEST.in",
}


def _ignore(_dir: str, names: list[str]) -> set[str]:
    blocked = set()
    for name in names:
        if name == "__pycache__" or name.endswith(".pyc") or name.endswith(".pyo"):
            blocked.add(name)
    return blocked


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    STAGE.mkdir(parents=True, exist_ok=True)

    for name in KEEP:
        src = ROOT / name
        if not src.exists():
            continue
        dst = STAGE / name
        if src.is_dir():
            shutil.copytree(src, dst, ignore=_ignore)
        else:
            shutil.copy2(src, dst)

    shutil.make_archive(str(OUT / "hqp_runtime_internal"), "zip", STAGE)
    print(OUT / "hqp_runtime_internal.zip")


if __name__ == "__main__":
    main()
