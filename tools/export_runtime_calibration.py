from __future__ import annotations

import argparse
from pathlib import Path

from spinmesh_runtime.runtime_support import RuntimeSamplerFactory, runtime_status


def main() -> None:
    parser = argparse.ArgumentParser(description='Export an IBM Runtime backend calibration snapshot to JSON.')
    parser.add_argument('--backend', required=True, help='IBM backend name, for example ibm_kyiv.')
    parser.add_argument('--output', required=True, help='Output JSON path.')
    args = parser.parse_args()

    status = runtime_status()
    if not status.available:
        raise SystemExit(status.message)

    from qiskit_ibm_runtime import QiskitRuntimeService

    service = QiskitRuntimeService()
    path = RuntimeSamplerFactory.save_calibration_snapshot(service, args.backend, Path(args.output))
    print(path)


if __name__ == '__main__':
    main()
