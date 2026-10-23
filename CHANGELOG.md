# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões em [SemVer](https://semver.org/lang/pt-BR/).

## [0.4.0] - 2026-10-23

### Adicionado
- Fonte Rubin (LSST) via o broker Fink (`--fonte ztf|rubin|ambas`), com nota própria medida contra o TNS
  (AUC 0.895 numa metade de teste), recortes, curva de luz e links para o portal do Fink.
- Fração do brilho que é nova (diferença contra referência) na nota do Rubin.
- Checagem no VSX (variáveis conhecidas) e, para o Rubin, no histórico do ZTF, para os candidatos do topo.
- Vigilância do fluxo do Rubin: avisa uma vez quando os alertas voltam (parados desde 14/07/2026).

### Corrigido
- O Fink responde 500 a datas em MJD: a busca usa ISO.

## [0.3.0] - 2026-10-23

### Adicionado
- Pacote `caca_sn` (`python -m caca_sn`, comando `cacasn`); `cacasn.py` continua como lançador.
- Log estruturado em JSON (structlog; cai no `logging` padrão se não estiver instalado) e Sentry opcional via `SENTRY_DSN`.
- Credenciais do TNS também por variáveis de ambiente (`TNS_BOT_ID`, `TNS_BOT_NAME`, `TNS_API_KEY`).
- CI (testes em 3.9 e 3.12, ruff, mypy, pip-audit, build do Docker), release por tag, Dependabot, `uv.lock`.
- Dockerfile, devcontainer, `.env.example`, CONTRIBUTING.

### Corrigido
- Objeto sem coordenada derrubava o relatório inteiro; agora é descartado.

## [0.2.0] - 2026-10-23

### Adicionado
- Classificador 2025 (beta) da ALeRCE e histórico de detecções na nota (AUC 0.96 contra o que foi reportado ao TNS).
- Alarme `--avisar` para candidato fora do TNS com nota ≥ 18.
- Testes offline com as APIs simuladas.

### Corrigido
- Travava sem salvar quando um candidato só tinha detecções negativas.
- "Subindo de brilho" comparava filtros diferentes.
- Gaia fora do ar era tratado como "não é estrela".
- `distnr = -999` (sem fonte) virava "no centro de uma fonte".
- Gravação de JSON atômica; novas tentativas com espera crescente; User-Agent identificado.

## [0.1.0] - 2026-10-22

### Adicionado
- Primeira versão: candidatos da ALeRCE, recortes, curva de brilho, checagem Gaia e TNS, `report.html`.
