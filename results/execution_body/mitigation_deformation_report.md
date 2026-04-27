# Mitigation Deformation Report

Mitigation is evaluated as a physical transformation, not merely an energy-number improvement.

Potential false-correction cases: `zne_linear` improved energy error while worsening correlation error.

| mitigation_policy | mitigation_shift | mitigation_instability | energy_error_vs_ideal_qaoa | magnetization_error | correlation_error | observed_phase_label |
| --- | --- | --- | --- | --- | --- | --- |
| none | None | None | 2.46971 | 0.0371094 | 0.38703 | invalid_sector_dominated |
| readout | -0.00451787 | 0.000786798 | 2.57017 | 0.00280156 | 0.399235 | invalid_sector_dominated |
| zne_linear | -0.0209961 | 0.0349121 | 2.44871 | 0.0244954 | 0.394006 | invalid_sector_dominated |
