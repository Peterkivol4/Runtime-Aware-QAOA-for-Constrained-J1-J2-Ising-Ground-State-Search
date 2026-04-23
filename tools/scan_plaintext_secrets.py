from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

PAT = re.compile(r"(?:secret|token|private|nonce|credential|passwd|password)", re.IGNORECASE)


def _names(target):
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        out = []
        for item in target.elts:
            out.extend(_names(item))
        return out
    return []


def _is_plain_secret_literal(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)) and bool(node.value)


def scan(path: Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_plain_secret_literal(node.value):
            for target in node.targets:
                for name in _names(target):
                    if PAT.search(name):
                        hits.append((node.lineno, name))
        elif isinstance(node, ast.AnnAssign) and _is_plain_secret_literal(node.value):
            for name in _names(node.target):
                if PAT.search(name):
                    hits.append((node.lineno, name))
    return hits


def main(argv: list[str]) -> int:
    roots = [Path(arg) for arg in argv] if argv else [Path('src')]
    bad = []
    for root in roots:
        for py in root.rglob('*.py'):
            bad.extend((py, line, name) for line, name in scan(py))
    for py, line, name in bad:
        print(f"{py}:{line}: plaintext secret-like literal assigned to {name}")
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
