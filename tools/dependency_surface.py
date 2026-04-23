from __future__ import annotations

import ast
import json
from pathlib import Path

RUNTIME = ["numpy", "scipy", "scikit-learn", "pandas", "matplotlib"]
DEV = ["pytest", "pytest-cov", "ruff", "build"]
OPTIONAL = ["qiskit", "qiskit-aer", "qiskit-ibm-runtime", "mlflow", "torch"]


def _imports(src: Path) -> list[str]:
    found: set[str] = set()
    for path in src.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
    return sorted(found)


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    src = repo / "src"
    payload = {
        "imports": _imports(src),
        "runtime_requirements": RUNTIME,
        "dev_requirements": DEV,
        "optional_integrations": OPTIONAL,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
