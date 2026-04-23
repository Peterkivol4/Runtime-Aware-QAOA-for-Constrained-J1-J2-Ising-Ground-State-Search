from __future__ import annotations

import argparse
from spinmesh_runtime.tracking import json_dumps_clean

from spinmesh_runtime.calibration_snapshot import compare_snapshot_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two backend calibration snapshots and emit a drift report.")
    parser.add_argument("left")
    parser.add_argument("right")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    report = compare_snapshot_files(args.left, args.right, output_path=args.output)
    print(json_dumps_clean(report, indent=2))


if __name__ == "__main__":
    main()
