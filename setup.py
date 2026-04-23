from __future__ import annotations

from pathlib import Path

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext


class OptionalBuildExt(build_ext):
    def run(self):
        try:
            super().run()
        except Exception:
            self.announce("native fastpath build skipped", level=3)

    def build_extension(self, ext):
        try:
            super().build_extension(ext)
        except Exception:
            self.announce(f"native extension skipped: {ext.name}", level=3)


ext_modules = [
    Extension(
        "ionmesh_runtime._native._kernels",
        sources=[str(Path("src") / "ionmesh_runtime" / "_native" / "_kernels.c")],
        optional=True,
    )
]

setup(ext_modules=ext_modules, cmdclass={"build_ext": OptionalBuildExt})
