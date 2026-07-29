"""Testes: anti-look-ahead (Donchian/ADX), sanidade e backtest."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import backtest_strategy, buy_and_hold  # noqa: E402
from indicators import adx, compute_all  # noqa: E402
from signals import STRATEGIES, compute_signals  # noqa: E402


def synthetic(n=900, seed=11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0004, 0.02, n)
    close = 100 * np.exp(np.cumsum(ret))
    high = close * (1 + np.abs(rng.normal(0, 0.012, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.012, n)))
    vol = rng.integers(1_000_000, 5_000_000, n).astype(float)
    idx = pd.bdate_range("2017-01-02", periods=n)
    return pd.DataFrame({"open": close, "high": high, "low": low,
                         "close": close, "volume": vol}, index=idx)


def test_adx_bounds():
    df = synthetic()
    a, p, m = adx(df["high"], df["low"], df["close"], 14)
    a = a.dropna()
    assert (a >= 0).all() and (a <= 100).all()


def test_donchian_excludes_today():
    """O canal de 20d deve usar só dias anteriores: dch_high20[t] = max(high[t-20:t])."""
    df = synthetic()
    ind = compute_all(df)
    h = df["high"].to_numpy()
    for t in (300, 500, 800):
        expected = float(np.max(h[t - 20:t]))          # exclui o dia t
        assert abs(float(ind["dch_high20"].iloc[t]) - expected) < 1e-9


def test_no_lookahead_signals():
    """Sinal em T só usa dados até T: truncar em T não muda o sinal em T."""
    df = synthetic()
    full = compute_signals(compute_all(df))
    for cut in (400, 600, 899):
        cutd = compute_signals(compute_all(df.iloc[: cut + 1]))
        for k in STRATEGIES:
            assert bool(full[k].iloc[cut]) == bool(cutd[k].iloc[cut]), \
                f"{k} muda em T={cut} ao truncar -> look-ahead!"


def test_backtest_consistency():
    ind = compute_all(synthetic())
    sig = compute_signals(ind)
    for k in STRATEGIES:
        bt = backtest_strategy(ind, sig[k])
        for t in bt["trades"]:
            assert t["exit_date"] >= t["entry_date"]
            assert t["days"] >= 1
        m = bt["metrics"]
        assert m["n_trades"] == len(bt["trades"])
        assert 0.0 <= m["win_rate"] <= 100.0
        if m["payoff"] is not None:
            assert m["payoff"] >= 0.0


def test_backtest_no_trades_safe():
    ind = compute_all(synthetic())
    empty = pd.Series(False, index=ind.index)
    bt = backtest_strategy(ind, empty)
    assert bt["metrics"]["n_trades"] == 0
    assert bt["metrics"]["total_return"] == 0.0
    assert bt["metrics"]["payoff"] is None


def test_buy_and_hold():
    ind = compute_all(synthetic())
    bh = buy_and_hold(ind)
    assert bh["max_drawdown"] <= 0.0
