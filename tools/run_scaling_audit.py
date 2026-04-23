from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import argparse

from spinmesh_runtime.scaling_audit import run_scaling_audit, save_scaling_audit_report
from spinmesh_runtime.tracking import json_dumps_clean


def _parse_int_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.split(",") if part.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a lightweight scaling audit across spin-system sizes.")
    parser.add_argument("--runtime-mode", choices=("local_proxy", "aer"), default="local_proxy")
    parser.add_argument("--n-spins", type=str, default="4,6,8,10,12")
    parser.add_argument("--budget-ratio", type=float, default=0.5)
    parser.add_argument("--base-shots", type=int, default=32)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-prefix", type=str, default=str(REPO_ROOT / "results" / "scaling_audit" / "scaling_audit_local_proxy"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n_spins_values = _parse_int_tuple(args.n_spins)
    output_prefix = Path(args.output_prefix)
    if args.dry_run:
        print(
            json_dumps_clean(
                {
                    "mode": "dry_run",
                    "runtime_mode": args.runtime_mode,
                    "n_spins": n_spins_values,
                    "budget_ratio": args.budget_ratio,
                    "base_shots": args.base_shots,
                    "depth": args.depth,
                    "seed": args.seed,
                    "planned_report_json": str(output_prefix.with_suffix(".json")),
                    "planned_report_md": str(output_prefix.with_suffix(".md")),
                },
                indent=2,
            )
        )
        return

    result = run_scaling_audit(
        runtime_mode=args.runtime_mode,
        n_spins_values=n_spins_values,
        budget_ratio=args.budget_ratio,
        base_shots=args.base_shots,
        depth=args.depth,
        seed=args.seed,
    )
    json_path, md_path = save_scaling_audit_report(result, output_prefix)
    print(
        json_dumps_clean(
            {
                "report_json": str(json_path),
                "report_md": str(md_path),
                "max_completed_n_spins": result.get("assessment", {}).get("max_completed_n_spins"),
                "applicable_for_tested_scale": result.get("assessment", {}).get("applicable_for_tested_scale"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
