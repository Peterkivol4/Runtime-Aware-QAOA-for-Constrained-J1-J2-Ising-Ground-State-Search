from __future__ import annotations

from pathlib import Path

from .optional_deps import load_matplotlib_pyplot, load_pandas


__all__ = [
    'plot_approximation_gap_vs_evaluations',
    'plot_success_probability_vs_noise',
    'plot_valid_ratio_vs_depth',
    'plot_valid_sector_ratio_vs_spins',
    'plot_energy_gap_vs_j2_ratio',
    'plot_mitigation_gain_vs_shot_budget',
    'plot_qaoa_optimizer_sample_efficiency',
    'plot_performance_profile',
]


def _save(fig, path: Path) -> None:
    plt = load_matplotlib_pyplot()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_approximation_gap_vs_evaluations(trace_df, output_path: Path) -> None:
    plt = load_matplotlib_pyplot()
    load_pandas()
    fig, ax = plt.subplots(figsize=(9, 5))
    grouped = trace_df.groupby(["method", "evaluation"]).approximation_gap.mean().reset_index()
    for method, chunk in grouped.groupby("method"):
        ax.plot(chunk["evaluation"], chunk["approximation_gap"], marker="o", linewidth=1.5, label=method)
    ax.set_title("Approximation gap vs evaluations")
    ax.set_xlabel("Evaluation")
    ax.set_ylabel("Mean approximation gap")
    ax.grid(alpha=0.3)
    ax.legend()
    _save(fig, output_path)


def plot_success_probability_vs_noise(summary_df, output_path: Path) -> None:
    plt = load_matplotlib_pyplot()
    load_pandas()
    fig, ax = plt.subplots(figsize=(9, 5))
    grouped = summary_df.groupby(["method", "noise_level"]).success.mean().reset_index()
    for method, chunk in grouped.groupby("method"):
        ax.plot(chunk["noise_level"], chunk["success"], marker="o", linewidth=1.5, label=method)
    ax.set_title("Success probability vs noise level")
    ax.set_xlabel("Noise level")
    ax.set_ylabel("Success probability")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(alpha=0.3)
    ax.legend()
    _save(fig, output_path)


def plot_valid_ratio_vs_depth(summary_df, output_path: Path) -> None:
    plt = load_matplotlib_pyplot()
    load_pandas()
    fig, ax = plt.subplots(figsize=(9, 5))
    grouped = summary_df.groupby(["method", "depth"]).valid_ratio.mean().reset_index()
    for method, chunk in grouped.groupby("method"):
        ax.plot(chunk["depth"], chunk["valid_ratio"], marker="o", linewidth=1.5, label=method)
    ax.set_title("Valid ratio vs depth")
    ax.set_xlabel("Depth")
    ax.set_ylabel("Mean valid ratio")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(alpha=0.3)
    ax.legend()
    _save(fig, output_path)


def plot_valid_sector_ratio_vs_spins(summary_df, output_path: Path) -> None:
    plt = load_matplotlib_pyplot()
    load_pandas()
    spin_col = "n_spins" if "n_spins" in summary_df.columns else "n_assets" if "n_assets" in summary_df.columns else None
    if spin_col is None:
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    grouped = summary_df.groupby(["method", spin_col]).valid_ratio.mean().reset_index()
    for method, chunk in grouped.groupby("method"):
        ax.plot(chunk[spin_col], chunk["valid_ratio"], marker="o", linewidth=1.5, label=method)
    ax.set_title("Valid-sector ratio vs system size")
    ax.set_xlabel("Number of spins")
    ax.set_ylabel("Mean valid-sector ratio")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(alpha=0.3)
    ax.legend()
    _save(fig, output_path)


plot_valid_ratio_vs_assets = plot_valid_sector_ratio_vs_spins


def plot_energy_gap_vs_j2_ratio(summary_df, output_path: Path) -> None:
    plt = load_matplotlib_pyplot()
    load_pandas()
    if "j2_ratio" not in summary_df.columns:
        return
    qaoa = summary_df[summary_df["family"] == "qaoa"].copy()
    if qaoa.empty:
        return
    grouped = qaoa.groupby(["method", "j2_ratio"]).approximation_gap.mean().reset_index()
    fig, ax = plt.subplots(figsize=(9, 5))
    for method, chunk in grouped.groupby("method"):
        chunk = chunk.sort_values("j2_ratio")
        ax.plot(chunk["j2_ratio"], chunk["approximation_gap"], marker="o", linewidth=1.5, label=method)
    ax.axvline(0.5, color="gray", linestyle="--", alpha=0.6, label="max frustration")
    ax.set_title("Approximation gap vs J2/J1 ratio")
    ax.set_xlabel("J2/J1 ratio")
    ax.set_ylabel("Mean approximation gap")
    ax.grid(alpha=0.3)
    ax.legend()
    _save(fig, output_path)


def plot_mitigation_gain_vs_shot_budget(summary_df, output_path: Path) -> None:
    plt = load_matplotlib_pyplot()
    load_pandas()
    fig, ax = plt.subplots(figsize=(9, 5))
    qaoa_only = summary_df[summary_df["family"] == "qaoa"]
    grouped = qaoa_only.groupby(["mitigation_label", "shot_budget"]).approximation_gap.mean().reset_index()
    for label, chunk in grouped.groupby("mitigation_label"):
        ax.plot(chunk["shot_budget"], chunk["approximation_gap"], marker="o", linewidth=1.5, label=label)
    ax.set_title("Mitigation cost-quality view")
    ax.set_xlabel("Shot budget")
    ax.set_ylabel("Mean approximation gap")
    ax.grid(alpha=0.3)
    ax.legend()
    _save(fig, output_path)


def plot_qaoa_optimizer_sample_efficiency(trace_df, output_path: Path) -> None:
    plt = load_matplotlib_pyplot()
    load_pandas()
    fig, ax = plt.subplots(figsize=(9, 5))
    qaoa = trace_df[trace_df["family"] == "qaoa"]
    grouped = qaoa.groupby(["method", "evaluation"]).best_energy.mean().reset_index()
    for method, chunk in grouped.groupby("method"):
        ax.plot(chunk["evaluation"], chunk["best_energy"], marker="o", linewidth=1.5, label=method)
    ax.set_title("QAOA tuner sample efficiency")
    ax.set_xlabel("Evaluation")
    ax.set_ylabel("Mean best feasible energy")
    ax.grid(alpha=0.3)
    ax.legend()
    _save(fig, output_path)


def plot_performance_profile(profile_df, output_path: Path) -> None:
    plt = load_matplotlib_pyplot()
    load_pandas()
    if profile_df.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    for method, chunk in profile_df.groupby("method"):
        chunk = chunk.sort_values("tau")
        ax.plot(chunk["tau"], chunk["rho"], linewidth=1.8, label=method)
    ax.set_title("Dolan-Moré performance profile")
    ax.set_xlabel("Performance ratio tau")
    ax.set_ylabel("rho_s(tau)")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(alpha=0.3)
    ax.legend()
    _save(fig, output_path)
