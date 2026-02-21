#!/usr/bin/env bash
# ==============================================================================
# check_deploy.sh — Checklist de pré-deploy
# Uso: chmod +x check_deploy.sh && ./check_deploy.sh
# ==============================================================================

# SEM set -e: ((VAR++)) retorna exit code 1 quando o valor é 0, abortando o script.
# Usamos PASS=$((PASS + 1)) em vez disso e controlamos erros manualmente.
set -uo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

PASS=0; FAIL=0; WARN=0

ok()      { echo -e "  ${GREEN}✓${NC} $1"; PASS=$((PASS + 1)); }
fail()    { echo -e "  ${RED}✗${NC} $1"; FAIL=$((FAIL + 1)); }
warn()    { echo -e "  ${YELLOW}⚠${NC} $1"; WARN=$((WARN + 1)); }
info()    { echo -e "  ${CYAN}→${NC} $1"; }
section() { echo -e "\n${BOLD}━━━ $1 ━━━${NC}"; }

# ==============================================================================
section "1. Ferramentas necessárias"
# ==============================================================================

for tool in docker curl python3; do
  if command -v "$tool" &>/dev/null; then
    ok "$tool encontrado: $(command -v $tool)"
  else
    fail "$tool NÃO encontrado — instale antes de continuar"
  fi
done

DC=""
if docker compose version &>/dev/null 2>&1; then
  ok "docker compose (plugin moderno) encontrado"
  DC="docker compose"
elif command -v docker-compose &>/dev/null 2>&1; then
  ok "docker-compose (legado) encontrado"
  DC="docker-compose"
else
  fail "docker compose NÃO encontrado"
  echo -e "\n${RED}Abortando: Docker Compose é obrigatório.${NC}"
  exit 1
fi

DOCKER_VERSION=$(docker version --format '{{.Server.Version}}' 2>/dev/null || true)
if [ -n "$DOCKER_VERSION" ]; then
  info "Docker Engine rodando: v$DOCKER_VERSION"
else
  fail "Docker daemon não está rodando — inicie o Docker Desktop ou: sudo systemctl start docker"
  echo -e "\n${RED}Abortando: Docker deve estar rodando.${NC}"
  exit 1
fi

info "Usando compose: $DC"

# ==============================================================================
section "2. Arquivos obrigatórios"
# ==============================================================================

for f in "Dockerfile" "docker-compose.yml" ".env.prod" "requirements.txt" "manage.py" "config/settings.py" "config/wsgi.py"; do
  if [ -f "$f" ]; then
    ok "$f existe"
  else
    fail "$f NÃO encontrado"
  fi
done

if [ -f ".dockerignore" ]; then
  ok ".dockerignore existe"
else
  warn ".dockerignore não encontrado — build pode ser mais lento"
fi

# ==============================================================================
section "3. Segurança do .env.prod"
# ==============================================================================

if [ -f ".gitignore" ]; then
  if grep -q "\.env\.prod" .gitignore 2>/dev/null; then
    ok ".env.prod está no .gitignore"
  else
    fail ".env.prod NÃO está no .gitignore — risco de vazar segredos!"
  fi
else
  warn ".gitignore não encontrado"
fi

if [ -f ".env.prod" ]; then
  grep -q "^DEBUG=False" .env.prod 2>/dev/null \
    && ok ".env.prod tem DEBUG=False" \
    || fail ".env.prod não tem DEBUG=False"

  grep -q "django-insecure" .env.prod 2>/dev/null \
    && fail ".env.prod usa SECRET_KEY insegura (django-insecure-...)" \
    || ok ".env.prod tem SECRET_KEY customizada"

  grep -q "^ALLOWED_HOSTS=\*" .env.prod 2>/dev/null \
    && fail "ALLOWED_HOSTS=* detectado — defina os hosts corretos!" \
    || ok "ALLOWED_HOSTS não usa wildcard *"

  grep -q "^CSRF_TRUSTED_ORIGINS=" .env.prod 2>/dev/null \
    && ok "CSRF_TRUSTED_ORIGINS configurado" \
    || warn "CSRF_TRUSTED_ORIGINS não encontrado no .env.prod"
else
  fail ".env.prod não existe"
fi

# ==============================================================================
section "4. Build da imagem Docker"
# ==============================================================================

info "Construindo imagem (pode demorar na primeira vez)..."
BUILD_OUTPUT=$($DC build 2>&1)
BUILD_EXIT=$?

if [ $BUILD_EXIT -eq 0 ]; then
  ok "Build concluído com sucesso"
else
  fail "Build falhou — últimas linhas do erro:"
  echo "$BUILD_OUTPUT" | tail -20 | sed 's/^/    /'
  echo -e "\n${RED}Abortando: corrija o erro de build.${NC}"
  exit 1
fi

IMAGE_SIZE=$(docker images rebanho_web:latest --format "{{.Size}}" 2>/dev/null || true)
[ -n "$IMAGE_SIZE" ] && info "Tamanho da imagem: $IMAGE_SIZE"

# ==============================================================================
section "5. Subindo containers"
# ==============================================================================

info "Parando containers antigos (se existirem)..."
$DC down 2>/dev/null || true

info "Iniciando todos os serviços..."
$DC --env-file .env.prod up -d 2>&1 | tail -8

info "Aguardando inicialização (60s)..."
sleep 60

# ==============================================================================
section "6. Status dos containers"
# ==============================================================================

for service in rebanho_db rebanho_redis rebanho_web rebanho_celery; do
  RUNNING=$(docker inspect --format='{{.State.Running}}' "$service" 2>/dev/null || echo "false")
  STATUS=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}sem-healthcheck{{end}}' "$service" 2>/dev/null || echo "nao-encontrado")

  if [ "$RUNNING" = "true" ]; then
    case "$STATUS" in
      healthy)         ok "$service — rodando e saudável" ;;
      sem-healthcheck) warn "$service — rodando (sem healthcheck)" ;;
      starting)        warn "$service — ainda inicializando" ;;
      *)               fail "$service — estado: $STATUS" ;;
    esac
  else
    fail "$service — NÃO está rodando"
    docker logs "$service" --tail=5 2>/dev/null | sed 's/^/    /' || true
  fi
done

# ==============================================================================
section "7. Conectividade"
# ==============================================================================

info "Testando HTTP em localhost:8080/login/ ..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 http://localhost:8080/login/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
  ok "Web respondeu com HTTP $HTTP_CODE"
else
  fail "Web não respondeu (HTTP $HTTP_CODE) — veja: $DC logs web --tail=30"
fi

info "Testando Redis..."
REDIS_PING=$($DC exec -T redis redis-cli ping 2>/dev/null || echo "")
echo "$REDIS_PING" | grep -q "PONG" && ok "Redis respondeu PONG" || fail "Redis não respondeu"

info "Testando PostgreSQL..."
PG_READY=$($DC exec -T db pg_isready -U livestock_user -d livestock_db 2>/dev/null || echo "")
echo "$PG_READY" | grep -q "accepting" && ok "PostgreSQL aceitando conexões" || fail "PostgreSQL não disponível"

# ==============================================================================
section "8. Django — Migrations"
# ==============================================================================

info "Verificando migrations pendentes..."
MIGRATIONS=$($DC exec -T web python manage.py showmigrations --plan 2>/dev/null || echo "ERRO")

if echo "$MIGRATIONS" | grep -q "ERRO"; then
  fail "Não foi possível verificar migrations — veja: $DC logs web --tail=30"
else
  PENDING=$(echo "$MIGRATIONS" | grep "\[ \]" | wc -l | tr -d " \n")
  if [ "${PENDING:-0}" = "0" ]; then
    ok "Nenhuma migration pendente"
  else
    warn "$PENDING migration(s) pendente(s) — rode: $DC exec web python manage.py migrate"
  fi
fi

# ==============================================================================
section "9. Arquivos estáticos"
# ==============================================================================

info "Verificando arquivos estáticos..."
STATIC_COUNT=$($DC exec -T web find /app/staticfiles -type f 2>/dev/null | wc -l || echo "0")
STATIC_COUNT=$(echo "$STATIC_COUNT" | tr -d ' \n')
[ "$STATIC_COUNT" -gt "0" ] 2>/dev/null \
  && ok "$STATIC_COUNT arquivo(s) estático(s) coletado(s)" \
  || warn "Nenhum estático encontrado — rode collectstatic se necessário"

# ==============================================================================
section "10. Celery worker"
# ==============================================================================

CELERY_RUNNING=$(docker inspect --format='{{.State.Running}}' rebanho_celery 2>/dev/null || echo "false")
if [ "$CELERY_RUNNING" = "true" ]; then
  ok "Container Celery rodando"
  info "Testando ping no worker (aguarde 10s)..."
  CELERY_PING=$($DC exec -T celery celery -A config inspect ping --timeout 10 2>/dev/null || echo "falhou")
  echo "$CELERY_PING" | grep -qi "pong\|ok" \
    && ok "Worker Celery respondeu ao ping" \
    || warn "Worker não respondeu ao ping (pode ainda estar iniciando)"
else
  fail "Container Celery não está rodando"
fi

# ==============================================================================
section "11. Logs recentes do Web"
# ==============================================================================

info "Últimas 15 linhas do container web:"
$DC logs --tail=15 web 2>/dev/null | sed 's/^/    /' || true

# ==============================================================================
section "Resultado Final"
# ==============================================================================

TOTAL=$((PASS + FAIL + WARN))
echo ""
echo -e "${BOLD}Total: $TOTAL verificações${NC}"
echo -e "  ${GREEN}✓ Passou:  $PASS${NC}"
echo -e "  ${YELLOW}⚠ Avisos:  $WARN${NC}"
echo -e "  ${RED}✗ Falhou:  $FAIL${NC}"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}${BOLD}🚀 Tudo OK! Pronto para o deploy em produção.${NC}"
  echo ""
  echo "  Próximos passos:"
  echo "    1. git add . && git commit -m 'chore: producao pronta'"
  echo "    2. git push origin main"
  echo "    3. GitHub Actions fará o deploy automático na VPS."
  echo ""
else
  echo -e "${RED}${BOLD}❌ Corrija os erros acima antes de fazer o deploy.${NC}"
  echo ""
  echo "  Comandos úteis:"
  echo "    Logs em tempo real:   $DC logs -f web"
  echo "    Restartar tudo:       $DC down && $DC --env-file .env.prod up -d"
  echo "    Entrar no container:  $DC exec web bash"
  echo "    Rodar migrations:     $DC exec web python manage.py migrate"
  echo "    Coletar estáticos:    $DC exec web python manage.py collectstatic --noinput"
  echo ""
  exit 1
fi