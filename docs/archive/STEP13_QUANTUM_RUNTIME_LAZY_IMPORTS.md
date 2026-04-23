Step 13 — quantum/runtime optional dependency lazy-loading

What changed:
- qiskit and qiskit-aer imports in the quantum runner path are now loaded only when the Aer or Runtime path is actually used
- qiskit fake-backend and Runtime V2 imports in runtime support are now loaded only when backend-calibration or live-runtime paths are used
- local proxy mode no longer pulls those optional packages into module import time

Baseline:
- py_compile passed for src/ and tools/
- reduced smoke baseline unchanged
