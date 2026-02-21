# ==============================================================================
# Dockerfile — Gestão de Rebanhos
# Multi-stage build: menor imagem final, sem ferramentas de build em produção
# ==============================================================================

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependências de sistema necessárias apenas para compilar extensões C
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python em ambiente isolado (não polui a imagem final)
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# CORREÇÃO 1: comentários NÃO podem ficar dentro de um bloco ENV —
# o Docker interpreta o # como parte do valor da variável e corrompe o PATH.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/home/django/.local/bin:$PATH"

WORKDIR /app

# CORREÇÃO 2: comentários NÃO podem ficar dentro de um bloco RUN apt-get —
# o shell passa o # para o apt como nome de pacote e o comando falha.
# Dependências de runtime (sem gcc, sem headers de compilação)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    && rm -rf /var/lib/apt/lists/*

# Copia wheels compiladas no stage anterior e instala sem compilar nada
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
    && rm -rf /wheels

# Cria usuário não-root antes de copiar o projeto
RUN addgroup --system django \
    && adduser --system --ingroup django --no-create-home django

# Copia código-fonte (aproveita cache do Docker se requirements não mudou)
COPY --chown=django:django . .

# CORREÇÃO 3: criar /tmp/gunicorn com dono django.
# O Gunicorn (rodando como não-root) precisa criar um socket de controle em
# /tmp para comunicação entre master e workers. Sem esse diretório gravável:
# "[Errno 13] Control server error: Permission denied"
RUN mkdir -p /app/logs /app/staticfiles /app/media /tmp/gunicorn \
    && chown -R django:django /app/logs /app/staticfiles /app/media /tmp/gunicorn

USER django

EXPOSE 8000

# Healthcheck nativo do Docker: verifica se a aplicação está respondendo
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/login/ || exit 1