# =============================================================
# scripts/deploy_prod.sh
# Executado pelo GitHub Actions via SSH a cada push na main
# =============================================================

set -e

PROJECT_DIR="/var/www/docker-instances/Rebanho"
LOG_FILE="$PROJECT_DIR/logs/deploy.log"

mkdir -p "$PROJECT_DIR/logs"

log() {
    echo "$1" | tee -a "$LOG_FILE"
}

log "========================================"
log "  DEPLOY — Gestão de Rebanhos"
log "  $(date '+%d/%m/%Y %H:%M:%S')"
log "========================================"

cd "$PROJECT_DIR"

# ── 1. Atualizar código ──────────────────────────────────────
log "📦 Atualizando código..."
git fetch origin main
git reset --hard origin/main
log "   Commit: $(git log -1 --pretty='%h — %s')"

# ── 2. Garantir gunicorn no requirements ────────────────────
sed -i 's/^# gunicorn/gunicorn/' requirements.txt

# ── 3. Build da nova imagem ──────────────────────────────────
log "🔨 Construindo imagem Docker..."
docker compose build web

# ── 4. Subir container web ───────────────────────────────────
log "♻️  Reiniciando container web..."
docker compose up -d --no-deps web

# ── 5. Health check com retry ────────────────────────────────
log "⏳ Aguardando Gunicorn inicializar..."

TENTATIVAS=0
MAX=12
OK=0

while [ $TENTATIVAS -lt $MAX ]; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:8080/login/ 2>/dev/null) || HTTP_CODE="000"
    TENTATIVAS=$((TENTATIVAS + 1))

    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
        log "✅ Gunicorn OK! (HTTP $HTTP_CODE após ${TENTATIVAS}x)"
        OK=1
        break
    fi

    log "   Tentativa $TENTATIVAS/$MAX — HTTP '$HTTP_CODE' — aguardando 5s..."
    sleep 5
done

if [ $OK -eq 0 ]; then
    log "❌ ERRO: Gunicorn não respondeu após $((MAX * 5))s"
    log "--- Log do container ---"
    docker compose logs web --tail=40
    exit 1
fi

# ── 6. Reiniciar Celery ──────────────────────────────────────
log "🔄 Reiniciando Celery..."
docker compose restart celery

# ── 7. Status final ──────────────────────────────────────────
log ""
log "📊 Status dos containers:"
docker compose ps

log ""
log "========================================"
log "  ✅ Deploy finalizado com sucesso!"
log "  🌐 https://rebanho.ferzion.com.br"
