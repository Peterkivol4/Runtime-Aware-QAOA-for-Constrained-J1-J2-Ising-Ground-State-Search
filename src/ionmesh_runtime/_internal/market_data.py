from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .optional_deps import load_pandas

from .constants import DEFAULT_MARKET_TEMPLATE


@dataclass
class MarketWindow:
    returns: pd.DataFrame
    mean_returns: np.ndarray
    covariance: np.ndarray
    tickers: list[str]
    metadata: dict[str, Any]


def _coerce_wide_prices(frame: pd.DataFrame, date_column: str = "date") -> pd.DataFrame:
    pd = load_pandas()
    frame = frame.copy()
    if date_column in frame.columns:
        frame[date_column] = pd.to_datetime(frame[date_column])
        frame = frame.sort_values(date_column).set_index(date_column)
    if "ticker" in frame.columns and "close" in frame.columns:
        if date_column not in frame.columns:
            raise ValueError("Long-format market CSVs must contain a date column.")
        frame = (
            frame.assign(**{date_column: pd.to_datetime(frame[date_column])})
            .pivot_table(index=date_column, columns="ticker", values="close", aggfunc="last")
            .sort_index()
        )
    numeric = frame.apply(pd.to_numeric, errors="coerce")
    numeric = numeric.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if numeric.shape[1] < 2:
        raise ValueError("Market data must contain at least two asset columns.")
    return numeric


def load_market_prices(path: str | Path, *, date_column: str = "date") -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Market data CSV not found: {path}")
    pd = load_pandas()
    frame = pd.read_csv(path)
    return _coerce_wide_prices(frame, date_column=date_column)


def compute_returns(price_frame: pd.DataFrame) -> pd.DataFrame:
    returns = price_frame.pct_change().replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if returns.empty:
        raise ValueError("Computed return frame is empty; provide longer price history.")
    return returns


def sample_market_window(
    price_frame: pd.DataFrame,
    *,
    n_assets: int,
    window: int = 60,
    window_index: int | None = None,
    seed: int = 42,
    annualization: int = 252,
) -> MarketWindow:
    returns = compute_returns(price_frame)
    if window_index is None:
        window_index = len(returns)
    if window_index <= 0 or window_index > len(returns):
        raise ValueError("window_index must fall inside the available return history.")
    start = max(0, window_index - window)
    window_returns = returns.iloc[start:window_index].copy()
    if len(window_returns) < max(10, min(window, 10)):
        raise ValueError("Not enough rows in the selected market window.")

    rng = np.random.default_rng(seed)
    columns = list(window_returns.columns)
    if n_assets > len(columns):
        raise ValueError(f"Requested n_assets={n_assets} but CSV only provides {len(columns)} series.")

    column_scores = [(col, float(window_returns[col].isna().mean())) for col in columns]
    ordered = [col for col, _ in sorted(column_scores, key=lambda item: (item[1], item[0]))]
    if len(ordered) > n_assets:
        head = ordered[: max(n_assets * 2, n_assets)]
        chosen = list(rng.choice(head, size=n_assets, replace=False))
        chosen.sort()
    else:
        chosen = ordered

    selected = window_returns[chosen].dropna(how="any")
    if selected.empty:
        raise ValueError("Selected market window is empty after dropping missing values.")

    mu = selected.mean().to_numpy(dtype=float) * annualization
    sigma = selected.cov().to_numpy(dtype=float) * annualization
    sigma = 0.5 * (sigma + sigma.T) + 1e-6 * np.eye(len(chosen))
    metadata = {
        "source": "market_csv",
        "window_rows": int(len(selected)),
        "window_start": str(selected.index[0]),
        "window_end": str(selected.index[-1]),
        "tickers": chosen,
        "annualization": int(annualization),
    }
    return MarketWindow(returns=selected, mean_returns=mu, covariance=sigma, tickers=chosen, metadata=metadata)


def build_template_market_csv(
    output_path: str | Path,
    *,
    periods: int = DEFAULT_MARKET_TEMPLATE['periods'],
    seed: int = DEFAULT_MARKET_TEMPLATE['seed'],
) -> Path:
    pd = load_pandas()
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=periods, freq="B")
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "XOM", "JNJ", "PG"]
    prices = {}
    for idx, ticker in enumerate(tickers):
        drift = 0.0002 + 0.00005 * idx
        vol = 0.01 + 0.001 * (idx % 3)
        innovations = rng.normal(drift, vol, size=periods)
        path = 100 * np.exp(np.cumsum(innovations))
        prices[ticker] = path
    frame = pd.DataFrame({"date": dates, **prices})
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    return output

__all__ = [
    'MarketWindow',
    'load_market_prices',
    'compute_returns',
    'sample_market_window',
    'build_template_market_csv',
]
