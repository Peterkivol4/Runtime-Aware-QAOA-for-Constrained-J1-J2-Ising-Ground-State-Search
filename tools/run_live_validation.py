from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from spinmesh_runtime.cli import build_parser, deck_from_args
from spinmesh_runtime.live_validation import run_live_validation_suite, save_live_validation_report
from spinmesh_runtime.tracking import json_dumps_clean


def _parse_int_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.split(",") if part.strip())


def main() -> None:
    parser = build_parser()
    parser.description = "Run live repeatability, Aer parity, and a small appendix sweep for the J1-J2 Ising benchmark."
    parser.add_argument("--live-repeats", type=int, default=2)
    parser.add_argument("--aer-repeats", type=int, default=2)
    parser.add_argument("--appendix-n-spins", type=str, default="4,6")
    parser.add_argument("--appendix-shot-budgets", type=str, default="32,64")
    parser.add_argument("--appendix-seeds", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    cfg = deck_from_args(args)
    appendix_n_spins = _parse_int_tuple(args.appendix_n_spins)
    appendix_shot_budgets = _parse_int_tuple(args.appendix_shot_budgets)
    output_prefix = Path(args.output_prefix)

    if args.dry_run:
        payload = {
            "mode": "dry_run",
            "runtime_mode": cfg.runtime_mode,
            "runtime_backend": cfg.runtime_backend,
            "runtime_execution_mode": cfg.runtime_execution_mode,
            "live_repeats": args.live_repeats,
            "aer_repeats": args.aer_repeats,
            "appendix_n_spins": appendix_n_spins,
            "appendix_shot_budgets": appendix_shot_budgets,
            "appendix_seeds": args.appendix_seeds,
            "planned_report_json": str(output_prefix.with_suffix(".json")),
            "planned_report_md": str(output_prefix.with_suffix(".md")),
            "planned_snapshot_json": str(output_prefix.with_name(f"{output_prefix.name}_backend_snapshot").with_suffix(".json")),
        }
        print(json_dumps_clean(payload, indent=2))
        return

    result = run_live_validation_suite(
        cfg,
        live_repeats=args.live_repeats,
        aer_repeats=args.aer_repeats,
        appendix_n_spins=appendix_n_spins,
        appendix_shot_budgets=appendix_shot_budgets,
        appendix_seeds=args.appendix_seeds,
    )
    json_path, md_path, snapshot_path = save_live_validation_report(result, output_prefix)
    payload = {
        "report_json": str(json_path),
        "report_md": str(md_path),
        "backend_snapshot_json": None if snapshot_path is None else str(snapshot_path),
        "preflight_passed": result.get("preflight", {}).get("passed"),
        "hardware_repeat_count": result.get("repeatability", {}).get("hardware_summary", {}).get("count"),
        "appendix_cell_count": result.get("appendix_sweep", {}).get("summary", {}).get("cell_count"),
    }
    print(json_dumps_clean(payload, indent=2))


if __name__ == "__main__":
    main()
