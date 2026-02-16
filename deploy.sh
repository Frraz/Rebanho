#!/bin/bash
# ==============================================================================
# deploy.sh — Deploy para rebanho.ferzion.com.br
# Usa Nginx do SISTEMA (não container) + Gunicorn Docker na porta 8080
# ==============================================================================

set -e

DOMAIN="rebanho.ferzion.com.br"
EMAIL="ferzion.dev@gmail.com"
COMPOSE="docker compose"
PROJECT_DIR="/var/www/docker-instances/Rebanho"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERRO]${NC} $1"; exit 1; }

check_requirements() {
    command -v docker >/dev/null 2>&1    || error "Docker não instalado."
    command -v docker compose >/dev/null || error "Docker Compose não instalado."
    [ -f ".env.prod" ]                   || error ".env.prod não encontrado."
    info "Requisitos verificados ✓"
}

# ── Deploy completo ──────────────────────────────────────────────────────────
deploy_full() {
    info "=== DEPLOY COMPLETO ==="

    info "1/5 — Parando containers antigos..."
    $COMPOSE down --remove-orphans 2>/dev/null || true

    info "2/5 — Construindo imagem..."
    $COMPOSE build --no-cache

    info "3/5 — Iniciando Redis..."
    $COMPOSE up -d redis
    sleep 3

    info "4/5 — Iniciando aplicação..."
    $COMPOSE up -d web celery

    info "5/5 — Aguardando Gunicorn na porta 8080..."
    for i in {1..15}; do
        if curl -sf http://127.0.0.1:8080/login/ > /dev/null 2>&1; then
            info "Gunicorn respondendo na porta 8080 ✓"
            break
        fi
        warning "Aguardando... ($i/15)"
        sleep 5
    done

    info "=== Containers rodando ==="
    $COMPOSE ps

    echo ""
    warning "Próximos passos:"
    echo "  1. ./deploy.sh nginx-setup   → instala virtual host no Nginx"
    echo "  2. ./deploy.sh ssl           → emite certificado SSL"
    echo "  3. docker compose exec web python manage.py createsuperuser"
}

# ── Instalar virtual host no Nginx do sistema ────────────────────────────────
nginx_setup() {
    info "=== CONFIGURANDO NGINX DO SISTEMA ==="

    SITE_FILE="/etc/nginx/sites-available/$DOMAIN"
    SITE_LINK="/etc/nginx/sites-enabled/$DOMAIN"

    # Copia o arquivo de configuração
    [ -f "nginx-rebanho-site" ] || error "Arquivo nginx-rebanho-site não encontrado."

    sudo cp nginx-rebanho-site "$SITE_FILE"
    info "Virtual host copiado para $SITE_FILE ✓"

    # Cria diretórios para certbot (antes do SSL)
    sudo mkdir -p /var/www/certbot

    # Versão temporária sem SSL para validação do certbot
    sudo tee "$SITE_FILE" > /dev/null << NGINX_TMP
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias $PROJECT_DIR/staticfiles/;
    }
}
NGINX_TMP

    # Ativa o site
    if [ ! -L "$SITE_LINK" ]; then
        sudo ln -s "$SITE_FILE" "$SITE_LINK"
        info "Site habilitado ✓"
    fi

    sudo nginx -t && sudo systemctl reload nginx
    info "Nginx recarregado ✓"
    info "Acesse temporariamente: http://$DOMAIN"
    info "Execute './deploy.sh ssl' para ativar HTTPS"
}

# ── Emitir SSL com certbot ───────────────────────────────────────────────────
setup_ssl() {
    info "=== CONFIGURAÇÃO SSL ==="

    # Verifica se certbot está instalado
    command -v certbot >/dev/null 2>&1 || {
        info "Instalando certbot..."
        sudo apt-get update -qq
        sudo apt-get install -y certbot python3-certbot-nginx
    }

    info "1/3 — Emitindo certificado para $DOMAIN..."
    sudo certbot --nginx \
        -d "$DOMAIN" \
        -d "www.$DOMAIN" \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        --redirect

    info "2/3 — Instalando config HTTPS completa..."
    sudo cp nginx-rebanho-site "/etc/nginx/sites-available/$DOMAIN"
    sudo nginx -t && sudo systemctl reload nginx

    info "3/3 — Configurando renovação automática..."
    (crontab -l 2>/dev/null; echo "0 12 * * * certbot renew --quiet && systemctl reload nginx") \
        | sort -u | crontab -

    info "=== SSL configurado! ==="
    info "Acesse: https://$DOMAIN"
}

# ── Atualização de código ────────────────────────────────────────────────────
deploy_update() {
    info "=== ATUALIZAÇÃO ==="
    git pull origin main
    $COMPOSE build web
    $COMPOSE up -d --no-deps web celery
    sleep 8
    $COMPOSE ps
    info "=== Atualização concluída! ==="
}

# ── Utilitários ──────────────────────────────────────────────────────────────
show_logs()   { $COMPOSE logs -f --tail=50 web celery; }
show_status() { $COMPOSE ps; echo ""; docker stats --no-stream; }

backup_db() {
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    source <(grep -E '^DB_' .env.prod | sed 's/^/export /')
    PGPASSWORD="$DB_PASSWORD" pg_dump \
        -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -f "backup_${TIMESTAMP}.sql"
    info "Backup: backup_${TIMESTAMP}.sql"
}

# ── Main ─────────────────────────────────────────────────────────────────────
check_requirements

case "${1:-full}" in
    full)        deploy_full   ;;
    update)      deploy_update ;;
    nginx-setup) nginx_setup   ;;
    ssl)         setup_ssl     ;;
    logs)        show_logs     ;;
    status)      show_status   ;;
    backup)      backup_db     ;;
    *)
        echo "Uso: $0 {full|update|nginx-setup|ssl|logs|status|backup}"
        exit 1 ;;
esac