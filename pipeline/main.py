"""Pipeline completo: baixa dados, calcula indicadores/sinais de rompimento,
roda os backtests e gera o painel único autocontido em docs/index.html."""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from backtest import backtest_strategy, buy_and_hold
from data import load_ohlcv, read_tickers
from indicators import compute_all
from signals import (STRATEGIES, STRATEGY_COMBO, STRATEGY_LABELS,
                     STRATEGY_SHORT, all_combos, combo_key, combo_signal)

HERE = Path(__file__).resolve().parent.parent
DOCS = HERE / "docs"
TEMPLATE = HERE / "templates" / "painel.template.html"

NEAR_PCT = 0.03  # "na iminência de romper": a até 3% da máxima de 20 dias
log = logging.getLogger("pipeline")


def _rs(s: pd.Series, nd: int = 2) -> list:
    return [None if pd.isna(v) else round(float(v), nd) for v in s.to_numpy()]


def _rsi_int(s: pd.Series) -> list:
    return [None if pd.isna(v) else int(round(float(v))) for v in s.to_numpy()]


def process_ticker(ticker: str, start: str, end: str, use_cache: bool):
    df = load_ohlcv(ticker, start, end, use_cache=use_cache)
    if df is None or len(df) < 260:  # precisa aquecer 52 semanas
        log.warning("Pulando %s (dados insuficientes).", ticker)
        return None, None

    ind = compute_all(df)
    dates = [d.strftime("%Y-%m-%d") for d in ind.index]
    bh = buy_and_hold(ind)

    # pré-calcula TODAS as 24 combinações (base × volume × SMA200 × ADX), em
    # precisão cheia. O painel só seleciona a combinação -> statline, Comparativo
    # e tabela ficam sempre consistentes (sem recalcular no navegador).
    combos = {}
    for c in all_combos():
        s = combo_signal(ind, c)
        bt = backtest_strategy(ind, s)
        combos[combo_key(c["base"], c["vol"], c["sma"], c["adx"])] = dict(
            m=bt["metrics"], trades=bt["trades"], active=bool(s.iloc[-1]),
        )

    def pkey(k):
        cc = STRATEGY_COMBO[k]
        return combo_key(cc.get("base", "20d"), cc.get("vol", "off"),
                         cc.get("sma", False), cc.get("adx", False))
    active = {k: combos[pkey(k)]["active"] for k in STRATEGIES}
    returns = {k: combos[pkey(k)]["m"]["total_return"] for k in STRATEGIES}

    panel = dict(
        dates=dates,
        close=_rs(ind["close"], 2),
        dch_high20=_rs(ind["dch_high20"], 2),
        dch_low20=_rs(ind["dch_low20"], 2),
        dch_low10=_rs(ind["dch_low10"], 2),
        high52w=_rs(ind["high52w"], 2),
        sma200=_rs(ind["sma200"], 2),
        volume=_rsi_int(ind["volume"]),
        vol_avg20=_rsi_int(ind["vol_avg20"]),
        vol_ratio=_rs(ind["vol_ratio"], 2),
        adx=_rs(ind["adx"], 1),
        plus_di=_rs(ind["plus_di"], 1),
        minus_di=_rs(ind["minus_di"], 1),
        combos=combos,
        buy_hold=bh,
    )

    # screening de hoje
    price = float(ind["close"].iloc[-1])
    dhi = float(ind["dch_high20"].iloc[-1]) if pd.notna(ind["dch_high20"].iloc[-1]) else None
    dist = None if not dhi else round((dhi / price - 1.0) * 100.0, 2)  # % p/ romper
    near = bool(dhi and price < dhi and (dhi - price) / dhi <= NEAR_PCT)
    screen = dict(
        ticker=ticker, name=ticker.replace(".SA", ""),
        last_price=round(price, 2), last_date=dates[-1],
        buy_hold_return=bh["total_return"],
        vol_ratio=(None if pd.isna(ind["vol_ratio"].iloc[-1]) else round(float(ind["vol_ratio"].iloc[-1]), 2)),
        adx=(None if pd.isna(ind["adx"].iloc[-1]) else round(float(ind["adx"].iloc[-1]), 1)),
        dist_high=dist, near=near,
        active=active, returns=returns,
    )
    return panel, screen


def build_site(payload: dict) -> None:
    tpl = TEMPLATE.read_text()
    data = json.dumps(payload).replace("</", "<\\/")
    (DOCS / "index.html").write_text(tpl.replace("__DATA__", data))
    kb = len((DOCS / "index.html").read_text().encode()) / 1024
    log.info("Painel escrito em docs/index.html (%.0f KB)", kb)


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    end_default = datetime.today().strftime("%Y-%m-%d")
    start_default = (datetime.today() - timedelta(days=365 * 10 + 5)).strftime("%Y-%m-%d")

    p = argparse.ArgumentParser(description="Pipeline de rompimentos com volume.")
    p.add_argument("--tickers", default=str(HERE / "tickers.txt"))
    p.add_argument("--start", default=start_default)
    p.add_argument("--end", default=end_default)
    p.add_argument("--no-cache", action="store_true")
    args = p.parse_args(argv)

    tickers = read_tickers(args.tickers)
    log.info("Tickers: %s", ", ".join(tickers))
    log.info("Período: %s a %s", args.start, args.end)

    data, screen_rows, order = {}, [], []
    for ticker in tickers:
        log.info("Processando %s ...", ticker)
        panel, screen = process_ticker(ticker, args.start, args.end,
                                       use_cache=not args.no_cache)
        if panel is None:
            continue
        data[ticker] = panel
        screen_rows.append(screen)
        order.append(ticker)

    payload = dict(
        meta=dict(
            start=args.start, end=args.end,
            generated=datetime.today().strftime("%Y-%m-%d %H:%M"),
            near_pct=NEAR_PCT * 100,
            strategies=[dict(key=k, label=STRATEGY_LABELS[k], short=STRATEGY_SHORT[k],
                             combo=STRATEGY_COMBO[k],
                             ckey=combo_key(STRATEGY_COMBO[k].get("base", "20d"),
                                            STRATEGY_COMBO[k].get("vol", "off"),
                                            STRATEGY_COMBO[k].get("sma", False),
                                            STRATEGY_COMBO[k].get("adx", False)))
                        for k in STRATEGIES],
        ),
        tickers=order,
        data=data,
        screen=screen_rows,
    )
    build_site(payload)
    log.info("Pronto. %d tickers no painel.", len(order))


if __name__ == "__main__":
    main()
