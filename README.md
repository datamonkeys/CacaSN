# CacaSN

Supernova hunter for the public ZTF alert stream (via the [ALeRCE](https://alerce.science) broker),
with a check against the [Transient Name Server](https://www.wis-tns.org) so you only look at what
nobody has reported yet. *Português abaixo.*

    python3 cacasn.py              # candidates first detected in the last 3 days
    python3 cacasn.py --dias 1     # only the freshest
    python3 cacasn.py --avisar     # desktop alert for an unreported candidate with score >= 18
    open report.html

`cacasn.py` uses only the Python standard library (3.9+). The macOS notification uses `osascript`;
on other systems the alert is printed instead.

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
3. Save it as `tns.json` next to `cacasn.py` (gitignored):

        {"bot_id": 12345, "bot_name": "your_bot_name", "api_key": "..."}

TNS allows 10 cone searches per minute; CacaSN does one every 6.5 s and honours the `429` reset header.
So the TNS check sets the pace: ~100 candidates take ~11 minutes, 500 take ~55. Without `tns.json`
the run takes seconds (and every candidate shows "TNS não consultado").

To report: TNS → *Submit → AT report*, with RA/Dec, date and magnitude of the first detection
(all in the report) and ZTF as the source of the data. Professional bots report clear ZTF supernovae
within hours, so speed matters: schedule `--avisar` every few hours.

## Tests

    python3 -m unittest discover -s testes -p "test_*.py"   # offline, APIs mocked

`testes/fonte_previa.py` is an experiment (does a pre-existing source in the reference separate
reported from unreported? It didn't, AUC ~0.5). It needs `numpy`/`scipy` (`requirements.txt`) and a
`resultados.json` from a previous run.

Each run appends one line to `cacasn.log`.

---

## Português

Caçador de supernovas nos alertas públicos do ZTF via ALeRCE, conferindo no TNS o que já foi
reportado. Só biblioteca padrão do Python; o aviso usa notificação do macOS (em outros sistemas, imprime).

- `python3 cacasn.py [--dias 3] [--prob 0.5] [--avisar]` gera `report.html`.
- Para consultar e reportar no TNS: crie conta e um bot, salve `tns.json` (formato acima).
- Quem reporta primeiro ao TNS fica como descobridor. Os robôs profissionais reportam as supernovas
  claras do ZTF em horas — a chance está em rodar com frequência e julgar os recortes.

## License

MIT — see `LICENSE`.
