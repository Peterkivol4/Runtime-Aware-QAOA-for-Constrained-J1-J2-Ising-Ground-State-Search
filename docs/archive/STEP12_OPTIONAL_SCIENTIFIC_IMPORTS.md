Step 12 tightens the remaining scientific optional-dependency surface.

Changes:
- matplotlib/pandas access in plotting is now lazy and routed through optional_deps
- scipy Sobol sampling and sklearn Gaussian-process tooling in optimization are now lazy-loaded
- import-time failures for optional scientific stacks now surface at point-of-use instead of during module import

Reduced-scope baseline:
- full py_compile over src/ and tools passed
- run_smoke_test() still returned the same result bundle as Step 11
