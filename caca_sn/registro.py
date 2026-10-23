"""Log estruturado (uma linha JSON por evento) e, opcionalmente, Sentry para
saber quando uma rodada agendada falhou.

Com structlog instalado (dependência declarada) é ele quem monta e emite os
eventos; sem ele, o logging padrão grava as mesmas linhas JSON, para a rodada
agendada nunca quebrar por falta de pacote."""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
from typing import Any


def _carregar(nome: str) -> Any:
    try:
        return importlib.import_module(nome)
    except ImportError:  # pragma: no cover - caminho sem a dependência
        return None


structlog: Any = _carregar("structlog")

NOME = "cacasn"
_configurado = False
# biblioteca quieta até alguém chamar configurar()
logging.getLogger(NOME).addHandler(logging.NullHandler())


class _Json(logging.Formatter):
    """Formato do caminho sem structlog: o mesmo JSON que o structlog produz."""

    def format(self, record: logging.LogRecord) -> str:
        dados = {
            "event": record.getMessage(),
            "level": record.levelname.lower(),
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            **getattr(record, "campos", {}),
        }
        return json.dumps(dados, ensure_ascii=False)


def configurar(arquivo: str | None) -> None:
    """Liga o log em JSON (arquivo + stderr) e o Sentry se SENTRY_DSN existir."""
    global _configurado
    if _configurado:
        return
    _configurado = True
    base = logging.getLogger(NOME)
    base.setLevel(logging.INFO)
    base.propagate = False
    saidas: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if arquivo:
        saidas.append(logging.FileHandler(arquivo, encoding="utf-8"))
    formato = logging.Formatter("%(message)s") if structlog is not None else _Json()
    for h in saidas:
        h.setFormatter(formato)
        base.addHandler(h)
    if structlog is not None:
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="%Y-%m-%dT%H:%M:%S", utc=False),
                structlog.processors.JSONRenderer(ensure_ascii=False),
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    dsn = os.environ.get("SENTRY_DSN")
    if dsn:
        sentry_sdk = _carregar("sentry_sdk")
        if sentry_sdk is not None:
            sentry_sdk.init(dsn=dsn, traces_sample_rate=0)
        else:
            obter().warning("sentry_indisponivel", motivo="SENTRY_DSN definido mas sentry-sdk não está instalado")


class _Padrao:
    """log.info("evento", campo=valor) sobre o logging padrão."""

    def __init__(self) -> None:
        self._base = logging.getLogger(NOME)

    def info(self, evento: str, **campos: Any) -> None:
        self._base.info(evento, extra={"campos": campos})

    def warning(self, evento: str, **campos: Any) -> None:
        self._base.warning(evento, extra={"campos": campos})

    def error(self, evento: str, **campos: Any) -> None:
        self._base.error(evento, extra={"campos": campos})


def obter() -> Any:
    """O logger: structlog quando instalado, senão o equivalente sobre logging."""
    return structlog.get_logger(NOME) if structlog is not None else _Padrao()
