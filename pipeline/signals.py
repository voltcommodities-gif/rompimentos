"""Os 6 sinais de COMPRA por rompimento.

O rompimento é o EVENTO (primeiro dia em que o fechamento supera o canal), não
um estado — assim não dispara todo dia enquanto o preço fica acima. Como o canal
exclui o dia atual, o sinal em T usa apenas dados até T: sem look-ahead.
"""
from __future__ import annotations

import pandas as pd

STRATEGIES = ["s1", "s2", "s3", "s4", "s5", "s6"]

STRATEGY_LABELS = {
    "s1": "Rompimento puro (20d)",
    "s2": "20d + volume 1,5×",
    "s3": "20d + volume 2×",
    "s4": "52 semanas + volume 1,5×",
    "s5": "20d + volume 1,5× + SMA200",
    "s6": "20d + volume 1,5× + ADX>25",
}

# rótulos curtos para os botões
STRATEGY_SHORT = {
    "s1": "Puro 20d",
    "s2": "+Vol 1,5×",
    "s3": "+Vol 2×",
    "s4": "52 sem.",
    "s5": "+SMA200",
    "s6": "+ADX>25",
}

VOL_STRONG = 1.5  # confirmação por volume
VOL_VERY_STRONG = 2.0


def _breakout_event(close: pd.Series, level: pd.Series) -> pd.Series:
    """Primeiro dia em que o fechamento supera `level` (rompimento)."""
    above = close > level
    return above & ~above.shift(1, fill_value=False)


def compute_signals(df: pd.DataFrame) -> dict[str, pd.Series]:
    close = df["close"]
    vr = df["vol_ratio"]
    ev20 = _breakout_event(close, df["dch_high20"])
    ev52 = _breakout_event(close, df["high52w"])

    vol15 = vr >= VOL_STRONG
    vol20 = vr >= VOL_VERY_STRONG
    trend = close > df["sma200"]
    strong_adx = df["adx"] > 25.0

    sig = {
        "s1": ev20,                                  # rompimento puro (controle)
        "s2": ev20 & vol15,                          # + volume 1,5×
        "s3": ev20 & vol20,                          # + volume 2×
        "s4": ev52 & vol15,                          # nova máx. 52s + volume
        "s5": ev20 & vol15 & trend,                  # + volume + tendência
        "s6": ev20 & vol15 & strong_adx,             # + volume + ADX
    }
    # NaN nos indicadores (aquecimento) -> sem sinal
    return {k: v.fillna(False).astype(bool) for k, v in sig.items()}
