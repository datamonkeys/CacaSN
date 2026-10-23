# CacaSN

[![ci](https://github.com/louisperner/CacaSN/actions/workflows/ci.yml/badge.svg)](https://github.com/louisperner/CacaSN/actions/workflows/ci.yml)

Supernova hunter for the public ZTF alert stream (via the [ALeRCE](https://alerce.science) broker),
with a check against the [Transient Name Server](https://www.wis-tns.org) so you only look at what
nobody has reported yet. *Português abaixo.*

## Install and run

    uv sync                         # or: pip install .
    uv run cacasn                   # candidates first detected in the last 3 days
    uv run cacasn --dias 1          # only the freshest
    uv run cacasn --avisar          # alert for an unreported candidate with score >= 18
    open report.html

`python -m caca_sn` and `python3 cacasn.py` do the same. Python 3.9+; the only runtime dependency is
`structlog` (without it the program still runs, logging through the standard library).

With Docker:

    docker build -t cacasn .
    docker run --rm --env-file .env -v "$PWD/saida:/saida" cacasn --dias 2   # results land in ./saida

Each run writes `resultados.json`, `report.html` and one JSON line per event to `cacasn.log`, next to
the program or in `$CACASN_SAIDA` if set.
The desktop alert uses macOS `osascript`; elsewhere it goes to the log. Set `SENTRY_DSN`
(and `pip install ".[sentry]"`) to get scheduled-run failures in Sentry.

For each candidate the report shows the science · reference · difference stamps, the light curve,
a score, the reasons behind it, and whether the position is already on TNS.

## Score

Up: SN probability from ALeRCE's stamp classifier and from its 2025 (beta) classifier, `drb`
(real/bogus network), detection on 2+ nights (an asteroid doesn't come back to the same spot),
both g and r filters, brightening within one filter.
Down: AGN probability (2025 classifier), single detection, "stellar" per ALeRCE, a Gaia star with
significant parallax or proper motion within 1.5" (a variable star), and a long detection history
at that position (an old source that varies, not a new explosion).

Measured on 97 candidates from 2026-10-13 to 23, 42 of which professional teams reported to TNS:

| Ranking by | AUC vs. "reported to TNS" |
|---|---|
| ALeRCE stamp classifier SN probability | 0.71 |
| ALeRCE 2025 (beta) classifier SN probability | 0.79 |
| CacaSN score | **0.96** |

The top 15 were all on TNS. Unreported candidates with high scores were AGN or variables on a
pre-existing source.

## TNS access (to check and to report)

1. Create an account at https://www.wis-tns.org (free; requests are reviewed by hand).
2. Create a bot at https://www.wis-tns.org/bots/edit and tick *Create new API key*.
3. Either set `TNS_BOT_ID`, `TNS_BOT_NAME`, `TNS_API_KEY` (see `.env.example`), or save `tns.json`
   next to `cacasn.py` (gitignored):

        {"bot_id": 12345, "bot_name": "your_bot_name", "api_key": "..."}

TNS allows 10 cone searches per minute; CacaSN does one every 6.5 s and honours the `429` reset header.
So the TNS check sets the pace: ~100 candidates take ~11 minutes, 500 take ~55. Without `tns.json`
the run takes seconds (and every candidate shows "TNS não consultado").

To report: TNS → *Submit → AT report*, with RA/Dec, date and magnitude of the first detection
(all in the report) and ZTF as the source of the data. Professional bots report clear ZTF supernovae
within hours, so speed matters: schedule `--avisar` every few hours.

## Development

    uv sync --all-extras
    uv run python -m unittest discover -s tests -t .   # offline, every API mocked
    uv run ruff check . && uv run mypy

Code layout: `caca_sn/avaliacao.py` (candidates and score), `catalogos.py` (Gaia, TNS),
`relatorio.py`, `alertas.py`, `rede.py` (HTTP with retries, atomic writes), `registro.py` (logging),
`cli.py`. See `CONTRIBUTING.md` and `CHANGELOG.md`.

`experimentos/fonte_previa.py` is an experiment (does a pre-existing source in the reference separate
reported from unreported? It didn't, AUC ~0.5); it needs `pip install ".[experimentos]"`.

---

## Português

Caçador de supernovas nos alertas públicos do ZTF via ALeRCE, conferindo no TNS o que já foi
reportado. Só biblioteca padrão do Python; o aviso usa notificação do macOS (em outros sistemas, imprime).

- `uv run cacasn [--dias 3] [--prob 0.5] [--avisar]` (ou `python3 cacasn.py`) gera `report.html`.
- Para consultar e reportar no TNS: crie conta e um bot; use as variáveis do `.env.example` ou `tns.json`.
- Quem reporta primeiro ao TNS fica como descobridor. Os robôs profissionais reportam as supernovas
  claras do ZTF em horas — a chance está em rodar com frequência e julgar os recortes.

## License

MIT — see `LICENSE`.
