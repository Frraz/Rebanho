# ==============================================================================
# Dockerfile — Gestão de Rebanhos (Produção)
# ==============================================================================

FROM python:3.12-slim

# Variáveis de ambiente do Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Diretório de trabalho
WORKDIR /app

# Dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PostgreSQL client (psycopg2)
    libpq-dev \
    gcc \
    # curl para healthcheck
    curl \
    # WeasyPrint (PDF)
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar código-fonte
COPY . .

# Criar diretórios necessários
RUN mkdir -p /app/logs /app/staticfiles /app/media

# Usuário não-root (segurança)
RUN addgroup --system django && adduser --system --ingroup django django
RUN chown -R django:django /app
USER django

# Porta exposta pelo Gunicorn
EXPOSE 8000