FROM python:3.12-slim

# uv gestiona el entorno a partir de pyproject.toml + uv.lock (versiones exactas).
COPY --from=ghcr.io/astral-sh/uv:0.12.20 /uv /uvx /bin/

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

# Primero solo las dependencias, para que la capa se reutilice mientras el
# lock no cambie.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY data/ ./data/

ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--listar"]
