# Screening de Rompimentos com Volume (Donchian · ADX)

Ferramenta de **estudo** que baixa 10 anos de dados de ações, detecta
**rompimentos** de preço (canais de Donchian), testa se **volume**, **tendência**
(SMA200) e **força de tendência** (ADX) melhoram o rompimento puro, e publica tudo
num **painel web** (GitHub Pages) — um painel por ação, com abas por ativo,
comparativo das estratégias, screening e tema claro/escuro.

> ⚠️ **Aviso:** ferramenta de estudo, **não** é recomendação de investimento.
> Rentabilidade passada não garante retorno futuro.

---

## O que ele calcula

Indicadores (em pandas puro, sem TA-Lib):

- **Canal de Donchian de 20 dias** — máxima e mínima dos 20 dias **anteriores**
  (exclui o dia atual, para não ter look-ahead)
- **Máxima de 52 semanas** (252 pregões, também excluindo o dia atual)
- **Volume médio de 20 dias** e a **razão** volume do dia / média
- **SMA 200** (filtro de tendência)
- **ADX de 14** com **+DI** e **−DI** (método de Wilder)
- **Largura de consolidação** (canal 20d) para achar lateralizações estreitas

Seis sinais de **compra** (a estratégia 1 é o grupo de **controle**):

| # | Estratégia | Regra |
|---|------------|-------|
| 1 | `s1` Rompimento puro | fechamento rompe a máxima dos 20 dias anteriores |
| 2 | `s2` + volume 1,5× | sinal 1 **e** volume ≥ 1,5× a média de 20d |
| 3 | `s3` + volume 2× | sinal 1 **e** volume ≥ 2× a média |
| 4 | `s4` 52 semanas | nova máxima de 52 semanas **e** volume ≥ 1,5× |
| 5 | `s5` + SMA200 | sinal 2 **e** preço > SMA200 (tendência de alta) |
| 6 | `s6` + ADX>25 | sinal 2 **e** ADX > 25 (mercado em tendência) |

Backtest por estratégia (sem sobreposição de trades):

- **Entrada:** no fechamento do dia do rompimento.
- **Saída** (o que vier primeiro): fechamento **abaixo da mínima dos 10 dias**
  (canal de Donchian de saída) **ou** stop-loss de **8%**.
- **Métricas:** nº de trades, taxa de acerto, retorno médio/trade, **payoff**
  (ganho médio ÷ perda média), retorno total, drawdown máximo, tempo médio em
  dias, e o **buy & hold** do mesmo período.

O painel traz um **Comparativo** lado a lado das 6 estratégias, destacando em
verde/vermelho se cada filtro **melhorou** ou **piorou** vs. o rompimento puro —
essa é a pergunta central do estudo.

Sem look-ahead: todo sinal em T usa apenas dados até T (há teste automatizado que
verifica isso por invariância à truncagem da série).

---

## Estrutura

```
rompimentos-volume/
├── pipeline/            # código Python
│   ├── data.py          # download + cache (yfinance -> parquet, preços ajustados)
│   ├── indicators.py    # Donchian, volume, ADX, SMA
│   ├── signals.py       # os 6 sinais de rompimento
│   ├── backtest.py      # backtest + métricas (payoff, tempo médio) + buy&hold
│   ├── main.py          # orquestra e gera docs/index.html
│   └── tests/           # pytest (anti-look-ahead + sanidade)
├── templates/
│   └── painel.template.html   # template do painel (placeholder __DATA__)
├── docs/index.html      # painel único autocontido, publicado (GitHub Pages)
├── tickers.txt          # lista de ativos
└── requirements.txt     # versões fixadas
```

---

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Rodar o pipeline (atualizar os dados)

```bash
python pipeline/main.py
```

Baixa os dados (cache em `cache/`), calcula tudo e **regrava `docs/index.html`** —
um painel único autocontido, com os dados embutidos (sem CDN). Opções:

```bash
python pipeline/main.py --no-cache          # ignora o cache e rebaixa do Yahoo
python pipeline/main.py --start 2015-01-01 --end 2025-01-01
```

Testes: `python -m pytest pipeline/tests -q`

## Ver localmente

Basta abrir `docs/index.html` no navegador. Ou servir:
`cd docs && python -m http.server 8000`

## Publicar no GitHub Pages

1. Suba o repositório para o GitHub (branch `main`).
2. **Settings → Pages → Source: Deploy from a branch → Branch `main` / pasta `/docs`**.
3. Em ~1 min o site fica em `https://<usuário>.github.io/<repositório>/`.

Depois de rodar o pipeline, faça `git commit` do `docs/index.html` e `git push` —
o Pages republica sozinho.

## Adicionar novos tickers

Edite `tickers.txt` (um por linha; `.SA` para papéis da B3) e rode o pipeline.
Tickers inexistentes ou com histórico curto são ignorados com aviso no log.

---

## Glossário rápido

- **Canal de Donchian:** a maior máxima e a menor mínima de um número de dias. Um
  **rompimento** de 20 dias é o preço fechar acima da maior máxima dos 20 dias
  anteriores — ou seja, fazer uma **nova máxima**. É a base das estratégias
  "seguidoras de tendência" (a clássica regra das 4 semanas).
- **Razão de volume:** volume do dia ÷ volume médio de 20 dias. Um rompimento com
  razão **≥ 1,5×** significa que a alta veio com **participação/força** acima do
  normal — a ideia é que rompimentos com volume "furam" melhor a resistência.
- **ADX (+DI / −DI):** mede a **força** de uma tendência (não a direção), de 0 a
  100. **Acima de 25** costuma indicar tendência forte; abaixo, mercado de lado.
  **+DI** acima de **−DI** indica pressão compradora dominante.
