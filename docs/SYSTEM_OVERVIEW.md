# System Overview

```mermaid
flowchart LR
    A["Spin-Lattice Instance"] --> B["Ising/QUBO Problem Builder"]
    B --> C["Classical Baselines"]
    B --> D["QAOA Optimizers"]
    D --> E["Estimator / Objective Phase"]
    D --> F["Sampler / Final Readout"]
    E --> G["Shot Governor"]
    F --> G
    G --> H["Runtime Modes / Session Manager"]
    H --> I["Tracker / SQLite WAL"]
    I --> J["Findings Report"]
    I --> K["Decision Layer / Utility Frontier"]
    H --> L["Live Validation Harness"]
    H --> M["Calibration Drift Study"]
```

The repository is a **runtime-aware benchmarking engine for constrained frustrated-spin search**. It builds spin-lattice instances, evaluates classical and quantum solvers under matched accounting rules, and emits reproducible artifact bundles for study and review.
