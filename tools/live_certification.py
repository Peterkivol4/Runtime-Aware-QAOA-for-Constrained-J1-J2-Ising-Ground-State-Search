from __future__ import annotations

import argparse
from spinmesh_runtime.tracking import json_dumps_clean
from pathlib import Path

from spinmesh_runtime.cli import deck_from_args, build_parser
from spinmesh_runtime.live_certification import run_live_certification_check, save_certification_report


def main() -> None:
    parser = build_parser()
    parser.description = "Run the live IBM hardware certification preflight for the runtime-aware QAOA repo."
    args = parser.parse_args()
    cfg = deck_from_args(args)
    result = run_live_certification_check(cfg, backend_name=cfg.runtime_backend)
    prefix = Path(f"{cfg.output_prefix}_live_cert_report")
    json_path, md_path = save_certification_report(result, prefix)
    print(json_dumps_clean({"report_json": str(json_path), "report_md": str(md_path), **result.as_dict()}, indent=2))


if __name__ == "__main__":
    main()
