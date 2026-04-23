from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .optional_deps import load_pandas

from .config import RunDeck


UTILITY_FRONTIER_COLUMNS = [
    'method',
    'family',
    'lattice_type',
    'approximation_ratio',
    'valid_ratio',
    'runtime_seconds',
    'total_shots',
    'utility_score',
    'pareto_efficient',
    'decision_class',
    'dominates_any',
]


@dataclass
class ExecutionRecommendation:
    recommended_method: str
    recommended_family: str
    recommendation: str
    rationale: list[str]
    expected_approximation_ratio: float
    expected_valid_ratio: float
    expected_runtime_seconds: float
    expected_total_shots: float
    utility_score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "recommended_method": self.recommended_method,
            "recommended_family": self.recommended_family,
            "recommendation": self.recommendation,
            "rationale": self.rationale,
            "expected_approximation_ratio": self.expected_approximation_ratio,
            "expected_valid_ratio": self.expected_valid_ratio,
            "expected_runtime_seconds": self.expected_runtime_seconds,
            "expected_total_shots": self.expected_total_shots,
            "utility_score": self.utility_score,
        }


def _normalized_utility(frame: pd.DataFrame, cfg: RunDeck) -> pd.Series:
    ratio = frame['approximation_ratio'].clip(lower=1e-9)
    quality = 1.0 / ratio
    rt = frame['runtime_seconds'] / max(frame['runtime_seconds'].median(), 1e-9)
    shots = frame['total_shots'] / max(frame['total_shots'].replace(0, np.nan).median(skipna=True) or 1.0, 1e-9)
    cost = cfg.decision_runtime_weight * rt.fillna(0.0) + cfg.decision_shot_weight * shots.fillna(0.0)
    return quality / (1.0 + cost)


def _physics_labeled_frame(summary_df: pd.DataFrame) -> pd.DataFrame:
    frame = summary_df.copy()
    if "regime" in frame.columns and "lattice_type" not in frame.columns:
        frame["lattice_type"] = frame["regime"]
    if "n_assets" in frame.columns and "n_spins" not in frame.columns:
        frame["n_spins"] = frame["n_assets"]
    return frame


def compute_utility_frontier(summary_df: pd.DataFrame, cfg: RunDeck) -> pd.DataFrame:
    pd = load_pandas()
    frame = _physics_labeled_frame(summary_df)
    if frame.empty:
        return pd.DataFrame(columns=UTILITY_FRONTIER_COLUMNS)

    frame['utility_score'] = _normalized_utility(frame, cfg)
    frame['pareto_efficient'] = False
    frame['dominates_any'] = False

    for idx, row in frame.iterrows():
        dominated = (
            (frame['approximation_ratio'] <= row['approximation_ratio'])
            & (frame['runtime_seconds'] <= row['runtime_seconds'])
            & (frame['total_shots'] <= row['total_shots'])
            & (
                (frame['approximation_ratio'] < row['approximation_ratio'])
                | (frame['runtime_seconds'] < row['runtime_seconds'])
                | (frame['total_shots'] < row['total_shots'])
            )
        ).any()
        frame.loc[idx, 'pareto_efficient'] = not dominated

        dominates_any = (
            (frame['approximation_ratio'] >= row['approximation_ratio'])
            & (frame['runtime_seconds'] >= row['runtime_seconds'])
            & (frame['total_shots'] >= row['total_shots'])
            & (
                (frame['approximation_ratio'] > row['approximation_ratio'])
                | (frame['runtime_seconds'] > row['runtime_seconds'])
                | (frame['total_shots'] > row['total_shots'])
            )
        ).any()
        frame.loc[idx, 'dominates_any'] = bool(dominates_any)

    frame['decision_class'] = np.where(frame['family'] == 'classical_baseline', 'classical', 'quantum')
    return frame.sort_values(['utility_score', 'approximation_ratio'], ascending=[False, True])


def build_execution_recommendation(summary_df: pd.DataFrame, cfg: RunDeck) -> ExecutionRecommendation:
    frontier = compute_utility_frontier(summary_df, cfg)
    if frontier.empty:
        return ExecutionRecommendation(
            'none', 'none', 'insufficient_data', ['No summary rows available.'], np.nan, np.nan, np.nan, np.nan, np.nan
        )

    winner = frontier.iloc[0]
    notes = [
        f"Top utility score={winner['utility_score']:.4f} with approximation_ratio={winner['approximation_ratio']:.4f}.",
        f"Expected runtime={winner['runtime_seconds']:.4f}s and shots={winner['total_shots']:.1f}.",
    ]
    rec = 'run_quantum' if winner['family'] == 'qaoa' else 'run_classical'

    if winner['family'] == 'qaoa' and winner.get('mitigation_label', 'none') != 'none':
        notes.append(f"Quantum utility is highest with mitigation bundle {winner['mitigation_label']}.")
    if winner['family'] == 'classical_baseline':
        notes.append('Classical baseline wins on cost-normalized utility for this window.')

    return ExecutionRecommendation(
        recommended_method=str(winner['method']),
        recommended_family=str(winner['family']),
        recommendation=rec,
        rationale=notes,
        expected_approximation_ratio=float(winner['approximation_ratio']),
        expected_valid_ratio=float(winner.get('valid_ratio', np.nan)),
        expected_runtime_seconds=float(winner.get('runtime_seconds', np.nan)),
        expected_total_shots=float(winner.get('total_shots', np.nan)),
        utility_score=float(winner['utility_score']),
    )


def build_decision_report(summary_df: pd.DataFrame, cfg: RunDeck) -> dict[str, Any]:
    frontier = compute_utility_frontier(summary_df, cfg)
    rec = build_execution_recommendation(summary_df, cfg)
    if frontier.empty:
        return {
            'recommendation': rec.as_dict(),
            'utility_frontier': [],
            'lattice_type_rollup': [],
            'quantum_favorable_windows': [],
            'classical_favorable_windows': [],
        }

    rollup = (
        frontier.groupby(['lattice_type', 'family', 'method'], as_index=False)
        .agg(
            mean_utility=('utility_score', 'mean'),
            mean_ratio=('approximation_ratio', 'mean'),
            mean_shots=('total_shots', 'mean'),
            mean_runtime=('runtime_seconds', 'mean'),
        )
        .sort_values(['lattice_type', 'mean_utility'], ascending=[True, False])
    )
    cutoff = frontier['utility_score'].quantile(0.75) if not frontier.empty else np.nan
    q_windows = frontier[(frontier['family'] == 'qaoa') & (frontier['utility_score'] >= cutoff)]
    c_windows = frontier[(frontier['family'] == 'classical_baseline') & (frontier['utility_score'] >= cutoff)]
    return {
        'recommendation': rec.as_dict(),
        'utility_frontier': frontier[[c for c in frontier.columns if c != 'trace']].to_dict(orient='records'),
        'lattice_type_rollup': rollup.to_dict(orient='records'),
        'quantum_favorable_windows': q_windows.head(10).to_dict(orient='records'),
        'classical_favorable_windows': c_windows.head(10).to_dict(orient='records'),
    }


AdvisorRecommendation = ExecutionRecommendation
build_advisor_recommendation = build_execution_recommendation

__all__ = [
    'ExecutionRecommendation',
    'AdvisorRecommendation',
    'UTILITY_FRONTIER_COLUMNS',
    'compute_utility_frontier',
    'build_execution_recommendation',
    'build_advisor_recommendation',
    'build_decision_report',
]
