"""Backtest por estratégia de rompimento, sem sobreposição de trades.

- Entrada: no FECHAMENTO do dia do sinal.
- Saída (o que vier primeiro):
    * fechamento < mínima dos 10 dias anteriores (canal de Donchian de saída)
    * stop-loss de 8%
    * fim dos dados
- Retorno diário mark-to-market só acumula enquanto posicionado (sem look-ahead).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

STOP_LOSS = 0.08  # 8%


def _max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1.0).min())


def backtest_strategy(df: pd.DataFrame, signals: pd.Series) -> dict:
    close = df["close"].to_numpy(dtype=float)
    exit_level = df["dch_low10"].to_numpy(dtype=float)  # mínima 10d (exclui hoje)
    vr = df["vol_ratio"].to_numpy(dtype=float)
    dates = df.index
    sig = signals.to_numpy()
    n = len(close)

    trades: list[dict] = []
    in_pos = np.zeros(n, dtype=bool)
    buy_idx: list[int] = []
    sell_idx: list[int] = []

    i = 0
    while i < n:
        if not sig[i]:
            i += 1
            continue
        entry_price = close[i]
        stop_price = entry_price * (1.0 - STOP_LOSS)
        exit_idx, reason = None, None
        j = i + 1
        while j < n:
            if close[j] <= stop_price:
                exit_idx, reason = j, "stop 8%"
                break
            lvl = exit_level[j]
            if np.isfinite(lvl) and close[j] < lvl:
                exit_idx, reason = j, "saída Donchian 10d"
                break
            j += 1
        if exit_idx is None:
            exit_idx, reason = n - 1, "fim"

        ret = close[exit_idx] / entry_price - 1.0
        in_pos[i + 1:exit_idx + 1] = True
        buy_idx.append(int(i))
        sell_idx.append(int(exit_idx))
        trades.append(dict(
            ei=int(i), xi=int(exit_idx),           # índices p/ marcadores no gráfico
            entry_date=dates[i].strftime("%Y-%m-%d"),
            entry_price=round(entry_price, 2),
            exit_date=dates[exit_idx].strftime("%Y-%m-%d"),
            exit_price=round(close[exit_idx], 2),
            return_pct=round(ret * 100.0, 2),
            days=int(exit_idx - i),
            reason=reason,
            vr=(None if not np.isfinite(vr[i]) else round(float(vr[i]), 2)),
        ))
        i = exit_idx + 1

    # equity diário mark-to-market
    daily_ret = np.zeros(n)
    px_ret = np.diff(close) / close[:-1]
    daily_ret[1:] = np.where(in_pos[1:], px_ret, 0.0)
    equity = np.cumprod(1.0 + daily_ret)

    rets = np.array([t["return_pct"] / 100.0 for t in trades])
    n_trades = len(trades)
    if n_trades > 0:
        wins = rets[rets > 0]
        losses = rets[rets < 0]
        win_rate = float((rets > 0).mean())
        avg_return = float(rets.mean())
        avg_days = float(np.mean([t["days"] for t in trades]))
        avg_win = float(wins.mean()) if wins.size else 0.0
        avg_loss = float(losses.mean()) if losses.size else 0.0
        payoff = (abs(avg_win / avg_loss) if avg_loss != 0 else None)
    else:
        win_rate = avg_return = avg_days = 0.0
        payoff = None

    metrics = dict(
        n_trades=n_trades,
        win_rate=round(win_rate * 100.0, 1),
        avg_return=round(avg_return * 100.0, 2),
        payoff=(None if payoff is None else round(payoff, 2)),
        total_return=round((float(equity[-1]) - 1.0) * 100.0, 2),
        max_drawdown=round(_max_drawdown(equity) * 100.0, 2),
        avg_days=round(avg_days, 0),
    )
    inpos_str = "".join("1" if x else "0" for x in in_pos)
    return dict(trades=trades, metrics=metrics,
                buys=buy_idx, sells=sell_idx, inpos=inpos_str)


def buy_and_hold(df: pd.DataFrame) -> dict:
    close = df["close"].to_numpy(dtype=float)
    if len(close) < 2:
        return dict(total_return=0.0, max_drawdown=0.0)
    return dict(
        total_return=round((close[-1] / close[0] - 1.0) * 100.0, 2),
        max_drawdown=round(_max_drawdown(close) * 100.0, 2),
    )
