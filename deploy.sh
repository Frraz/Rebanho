#!/bin/bash
# ==============================================================================
# deploy.sh — Script de deploy para rebanho.ferzion.com.br
#
# Uso:
#   chmod +x deploy.sh
#   ./deploy.sh           → deploy completo (primeira vez)
#   ./deploy.sh update    → atualiza a aplicação (código novo)
#   ./deploy.sh ssl       → emite/renova certificado SSL
#   ./deploy.sh logs      → mostra logs em tempo real
# ==============================================================================

set -e  # Para em caso de erro

DOMAIN="rebanho.ferzion.com.br"
EMAIL="ferzion.dev@gmail.com"
COMPOSE="docker compose"

# ── Cores para output ────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERRO]${NC} $1"; exit 1; }

# ── Verificações iniciais ────────────────────────────────────────────────────
check_requirements() {
    command -v docker >/dev/null 2>&1 || error "Docker não instalado."
    command -v docker compose >/dev/null 2>&1 || error "Docker Compose não instalado."
    [ -f ".env.prod" ] || error "Arquivo .env.prod não encontrado."
    info "Requisitos verificados ✓"
}

# ── Deploy completo (primeira vez) ───────────────────────────────────────────
deploy_full() {
    info "=== DEPLOY COMPLETO ==="

    info "1/6 — Parando containers antigos..."
    $COMPOSE down --remove-orphans 2>/dev/null || true

    info "2/6 — Construindo imagem..."
    $COMPOSE build --no-cache

    info "3/6 — Iniciando Redis..."
    $COMPOSE up -d redis
    sleep 3

    info "4/6 — Iniciando aplicação (migrate + collectstatic)..."
    $COMPOSE up -d web
    sleep 10

    info "5/6 — Verificando health..."
    for i in {1..10}; do
        if $COMPOSE exec web curl -sf http://localhost:8000/login/ > /dev/null 2>&1; then
            info "Aplicação respondendo ✓"
            break
        fi
        warning "Aguardando aplicação... ($i/10)"
        sleep 5
    done

    info "6/6 — Iniciando Nginx e Celery..."
    $COMPOSE up -d nginx celery

    info "=== Deploy concluído! ==="
    info "Acesse temporariamente via HTTP: http://$DOMAIN"
    warning "Execute './deploy.sh ssl' para ativar HTTPS"
}

# ── Atualização de código ────────────────────────────────────────────────────
deploy_update() {
    info "=== ATUALIZAÇÃO ==="

    info "1/4 — Fazendo pull do código..."
    git pull origin main

    info "2/4 — Reconstruindo imagem..."
    $COMPOSE build web

    info "3/4 — Reiniciando com zero downtime..."
    $COMPOSE up -d --no-deps web celery

    info "4/4 — Aguardando estabilização..."
    sleep 10
    $COMPOSE ps

    info "=== Atualização concluída! ==="
}

# ── SSL com Let's Encrypt ────────────────────────────────────────────────────
setup_ssl() {
    info "=== CONFIGURAÇÃO SSL ==="

    # Nginx precisa estar rodando sem HTTPS primeiro
    # Usamos config temporária que aceita HTTP para o desafio do certbot
    info "1/3 — Emitindo certificado para $DOMAIN..."
    $COMPOSE --profile ssl run --rm certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        -d "$DOMAIN" \
        -d "www.$DOMAIN"

    info "2/3 — Recarregando Nginx com SSL..."
    $COMPOSE exec nginx nginx -s reload

    info "3/3 — Configurando renovação automática (cron)..."
    (crontab -l 2>/dev/null; echo "0 12 * * * cd $(pwd) && docker compose --profile ssl run --rm certbot renew --quiet && docker compose exec nginx nginx -s reload") | crontab -

    info "=== SSL configurado! ==="
    info "Acesse: https://$DOMAIN"
}

# ── Logs ─────────────────────────────────────────────────────────────────────
show_logs() {
    info "Logs em tempo real (Ctrl+C para sair)..."
    $COMPOSE logs -f --tail=50 web nginx celery
}

# ── Status ───────────────────────────────────────────────────────────────────
show_status() {
    info "=== STATUS DOS CONTAINERS ==="
    $COMPOSE ps
    echo ""
    info "=== USO DE RECURSOS ==="
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
}

# ── Backup do banco ──────────────────────────────────────────────────────────
backup_db() {
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="backup_${TIMESTAMP}.sql"
    info "Gerando backup: $BACKUP_FILE"

    # Carrega variáveis do .env.prod
    source <(grep -E '^DB_' .env.prod | sed 's/^/export /')

    PGPASSWORD="$DB_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -f "$BACKUP_FILE"

    info "Backup salvo: $BACKUP_FILE"
}

# ── Main ─────────────────────────────────────────────────────────────────────
check_requirements

case "${1:-full}" in
    full)    deploy_full   ;;
    update)  deploy_update ;;
    ssl)     setup_ssl     ;;
    logs)    show_logs     ;;
    status)  show_status   ;;
    backup)  backup_db     ;;
    *)
        echo "Uso: $0 {full|update|ssl|logs|status|backup}"
        exit 1
        ;;
esac