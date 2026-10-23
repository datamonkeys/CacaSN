# Rodada do CacaSN em qualquer máquina (Linux):
#   docker build -t cacasn .
#   docker run --rm --env-file .env -v "$PWD/saida:/saida" cacasn --dias 2
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY caca_sn ./caca_sn
RUN uv sync --locked --no-dev --extra sentry
ENV PATH="/app/.venv/bin:$PATH" CACASN_SAIDA=/saida
RUN mkdir -p /saida
ENTRYPOINT ["python", "-m", "caca_sn"]
