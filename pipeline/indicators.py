"""Indicadores de rompimento em pandas puro (sem TA-Lib).

Todos os canais/máximas usados como REFERÊNCIA de rompimento excluem o dia
atual (via .shift(1)) — isso evita look-ahead: o rompimento de hoje é comparado
com a máxima/mínima dos dias ANTERIORES.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def donchian(high: pd.Series, low: pd.Series, window: int) -> tuple[pd.Series, pd.Series]:
    """Canal de Donchian excluindo o dia atual: (máxima, mínima) dos `window`
    dias anteriores."""
    hi = high.rolling(window).max().shift(1)
    lo = low.rolling(window).min().shift(1)
    return hi, lo


def rolling_high(high: pd.Series, window: int) -> pd.Series:
    """Máxima dos `window` dias anteriores (exclui o dia atual)."""
    return high.rolling(window).max().shift(1)


def volume_ratio(volume: pd.Series, window: int = 20) -> tuple[pd.Series, pd.Series]:
    """Volume médio dos `window` dias ANTERIORES e razão volume_do_dia / média.

    A média exclui o dia atual (.shift(1)), pela mesma lógica do canal de
    Donchian: assim o pico de volume que estamos tentando detectar não é diluído
    na sua própria média de referência."""
    avg = volume.rolling(window).mean().shift(1)
    ratio = volume / avg.replace(0.0, np.nan)
    return avg, ratio


def sma(close: pd.Series, window: int = 200) -> pd.Series:
    return close.rolling(window).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """ADX de Wilder com +DI e −DI.

    Retorna (adx, plus_di, minus_di). Usa suavização exponencial de Wilder
    (alpha = 1/period), equivalente ao RMA.
    """
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    a = 1.0 / period
    atr = tr.ewm(alpha=a, adjust=False, min_periods=period).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=a, adjust=False, min_periods=period).mean() / atr
    minus_di = 100.0 * minus_dm.ewm(alpha=a, adjust=False, min_periods=period).mean() / atr

    di_sum = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    adx_line = dx.ewm(alpha=a, adjust=False, min_periods=period).mean()
    return adx_line, plus_di, minus_di


def consolidation_width(dch_high: pd.Series, dch_low: pd.Series) -> pd.Series:
    """Largura da consolidação: (máx − mín) / mín do canal de 20 dias.
    Valores baixos = lateralização estreita (mola comprimida)."""
    return (dch_high - dch_low) / dch_low.replace(0.0, np.nan)


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """Anexa todos os indicadores de rompimento ao OHLCV."""
    out = df.copy()
    out["dch_high20"], out["dch_low20"] = donchian(out["high"], out["low"], 20)
    _, out["dch_low10"] = donchian(out["high"], out["low"], 10)  # canal de saída
    out["high52w"] = rolling_high(out["high"], 252)
    out["vol_avg20"], out["vol_ratio"] = volume_ratio(out["volume"], 20)
    out["sma200"] = sma(out["close"], 200)
    out["adx"], out["plus_di"], out["minus_di"] = adx(out["high"], out["low"], out["close"], 14)
    out["cons_width"] = consolidation_width(out["dch_high20"], out["dch_low20"])
    return out
