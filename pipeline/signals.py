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

# cada preset expresso como combinação de filtros (usado pelo painel interativo)
STRATEGY_COMBO = {
    "s1": {"base": "20d"},
    "s2": {"base": "20d", "vol": "1.5"},
    "s3": {"base": "20d", "vol": "2"},
    "s4": {"base": "52w", "vol": "1.5"},
    "s5": {"base": "20d", "vol": "1.5", "sma": True},
    "s6": {"base": "20d", "vol": "1.5", "adx": True},
}

VOL_STRONG = 1.5  # confirmação por volume
VOL_VERY_STRONG = 2.0


def _breakout_event(close: pd.Series, level: pd.Series) -> pd.Series:
    """Primeiro dia em que o fechamento supera `level` (rompimento)."""
    above = close > level
    return above & ~above.shift(1, fill_value=False)


BASES = ["20d", "52w"]
VOLS = ["off", "1.5", "2"]


def combo_key(base: str, vol: str, sma: bool, adx: bool) -> str:
    return f"{base}|{vol}|{1 if sma else 0}|{1 if adx else 0}"


def all_combos() -> list[dict]:
    """As 24 combinações possíveis de filtros (base × volume × SMA200 × ADX)."""
    out = []
    for base in BASES:
        for vol in VOLS:
            for sma in (False, True):
                for adx in (False, True):
                    out.append(dict(base=base, vol=vol, sma=sma, adx=adx))
    return out


def combo_signal(df: pd.DataFrame, c: dict) -> pd.Series:
    """Sinal de compra para uma combinação de filtros qualquer."""
    close = df["close"]
    level = df["high52w"] if c.get("base") == "52w" else df["dch_high20"]
    ev = _breakout_event(close, level)
    if c.get("vol") == "1.5":
        ev = ev & (df["vol_ratio"] >= VOL_STRONG)
    elif c.get("vol") == "2":
        ev = ev & (df["vol_ratio"] >= VOL_VERY_STRONG)
    if c.get("sma"):
        ev = ev & (close > df["sma200"])
    if c.get("adx"):
        ev = ev & (df["adx"] > 25.0)
    return ev.fillna(False).astype(bool)


def compute_signals(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Os 6 presets, expressos como combinações de filtros."""
    return {k: combo_signal(df, STRATEGY_COMBO[k]) for k in STRATEGIES}
