#!/usr/bin/env bash
# ==============================================================================
# atualizacao.sh — Atualiza o sistema em produção
# ==============================================================================
#
# Uso (no VPS, dentro da pasta do projeto):
#
#   ./atualizacao.sh              atualiza para a última versão da main
#   ./atualizacao.sh --sim        não pede confirmação
#   ./atualizacao.sh --forcar     reconstrói mesmo sem commits novos
#   ./atualizacao.sh --voltar     volta para a versão anterior à última atualização
#   ./atualizacao.sh --ajuda
#
# ------------------------------------------------------------------------------
# A ORDEM DAS ETAPAS É PROPOSITAL
#
# Tudo que pode falhar acontece ANTES de trocar o container que está no ar:
#
#   1. conferências           → nada foi tocado
#   2. git pull               → só arquivos no disco mudaram
#   3. build da imagem        → o container antigo continua atendendo
#   4. checagem de migrations → idem
#   5. backup do banco        → idem (só se houver migração pendente)
#   6. migrate                → idem — o site antigo segue no ar
#   7. collectstatic          → idem (não apaga os estáticos antigos)
#   8. troca do container     → só aqui o usuário passa a ver a versão nova
#   9. health check           → se falhar, volta sozinho quando for seguro
#
# Se algo falhar nas etapas 2 a 7, o script devolve o código à versão anterior
# e o sistema que está no ar não percebe nada.
# ------------------------------------------------------------------------------
#
# POR QUE TUDO ESTÁ DENTRO DE main()
#
# O próprio git pull pode alterar este arquivo enquanto ele roda. O bash lê
# scripts aos poucos, então uma mudança no meio da execução faria ele continuar
# lendo o arquivo novo a partir de uma posição do antigo — e executar lixo.
# Envolvendo tudo numa função, o bash carrega o script inteiro antes de começar.
# ==============================================================================

main() {
    set -Eeuo pipefail

    # ── Configuração ─────────────────────────────────────────────────────────
    local PROJETO
    PROJETO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

    local BRANCH="main"
    local PORTA_APP="${PORTA_APP:-8080}"
    local URL_SAUDE="http://127.0.0.1:${PORTA_APP}/login/"
    local DIR_BACKUP="${DIR_BACKUP:-$HOME/backups/rebanho}"
    local MANTER_BACKUPS=10
    local HISTORICO="$DIR_BACKUP/historico_atualizacoes.log"
    local UID_STATIC="100" GID_STATIC="101"

    local PERGUNTAR=1 FORCAR=0 VOLTAR=0
    for arg in "$@"; do
        case "$arg" in
            --sim|-y)     PERGUNTAR=0 ;;
            --forcar)     FORCAR=1 ;;
            --voltar)     VOLTAR=1 ;;
            --ajuda|-h)   sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; return 0 ;;
            *)            erro "Opção desconhecida: $arg (use --ajuda)"; return 2 ;;
        esac
    done

    cd "$PROJETO"

    # ── Log de tudo que aparece na tela ──────────────────────────────────────
    mkdir -p "$PROJETO/logs" "$DIR_BACKUP"
    local LOG="$PROJETO/logs/atualizacao_$(date +%Y%m%d_%H%M%S).log"
    exec > >(tee -a "$LOG") 2>&1

    # ── Uma atualização por vez ──────────────────────────────────────────────
    exec 9>"/tmp/rebanho_atualizacao.lock"
    if ! flock -n 9; then
        erro "Já existe uma atualização em andamento. Aguarde ela terminar."
        return 1
    fi

    local INICIO=$SECONDS
    titulo "ATUALIZAÇÃO — Gestão de Rebanhos   $(date '+%d/%m/%Y %H:%M:%S')"
    info "Projeto: $PROJETO"
    info "Log:     $LOG"

    # ── Estado compartilhado com as rotinas de reversão ──────────────────────
    VERSAO_ANTERIOR=""
    IMAGEM_CONSTRUIDA=0
    MIGRACOES_APLICADAS=0
    CONTAINER_TROCADO=0
    ARQUIVO_BACKUP=""

    trap 'falha_inesperada $LINENO' ERR

    # ════════════════════════════════════════════════════════════════════════
    etapa 1 "Conferências"
    # ════════════════════════════════════════════════════════════════════════
    conferir_ferramentas
    detectar_compose
    ler_env

    if [ "$VOLTAR" -eq 1 ]; then
        voltar_versao
        return $?
    fi

    if ! git diff --quiet || ! git diff --cached --quiet; then
        erro "Há arquivos versionados modificados diretamente no servidor:"
        git status --short --untracked-files=no | sed 's/^/      /'
        erro "Atualizar agora descartaria essas mudanças. Resolva antes:"
        erro "  git stash    (guardar)   ou   git checkout -- .   (descartar)"
        return 1
    fi
    ok "Nenhuma alteração local pendente"

    # ════════════════════════════════════════════════════════════════════════
    etapa 2 "Buscando a versão nova"
    # ════════════════════════════════════════════════════════════════════════
    git fetch --quiet origin "$BRANCH"
    VERSAO_ANTERIOR="$(git rev-parse HEAD)"
    local VERSAO_NOVA
    VERSAO_NOVA="$(git rev-parse "origin/$BRANCH")"

    if [ "$VERSAO_ANTERIOR" = "$VERSAO_NOVA" ] && [ "$FORCAR" -eq 0 ]; then
        ok "O sistema já está na versão mais recente: $(git log -1 --format='%h %s')"
        info "Para reconstruir mesmo assim: ./atualizacao.sh --forcar"
        return 0
    fi

    if ! git merge-base --is-ancestor "$VERSAO_ANTERIOR" "$VERSAO_NOVA"; then
        erro "O código do servidor divergiu do GitHub (há commits aqui que não estão lá)."
        erro "Não vou sobrescrever. Investigue com: git log --oneline origin/$BRANCH..HEAD"
        return 1
    fi

    if [ "$VERSAO_ANTERIOR" != "$VERSAO_NOVA" ]; then
        info "Versão atual: $(git log -1 --format='%h %s' "$VERSAO_ANTERIOR")"
        info "Chegando:"
        git log --format='      %h  %s  (%an, %ar)' "$VERSAO_ANTERIOR..$VERSAO_NOVA"
        echo
        if git diff --name-only "$VERSAO_ANTERIOR" "$VERSAO_NOVA" | grep -q '/migrations/'; then
            aviso "Esta atualização contém MIGRAÇÕES de banco de dados."
        fi
    fi

    if [ "$PERGUNTAR" -eq 1 ]; then
        confirmar "Aplicar esta atualização em PRODUÇÃO?" || { info "Cancelado. Nada foi alterado."; return 0; }
    fi

    git merge --ff-only --quiet "$VERSAO_NOVA"
    ok "Código atualizado para $(git log -1 --format='%h %s')"

    # ════════════════════════════════════════════════════════════════════════
    etapa 3 "Construindo a imagem (o sistema atual continua no ar)"
    # ════════════════════════════════════════════════════════════════════════
    if ! $COMPOSE build web; then
        erro "O build falhou."
        reverter_codigo
        return 1
    fi
    IMAGEM_CONSTRUIDA=1
    ok "Imagem construída"

    # ════════════════════════════════════════════════════════════════════════
    etapa 4 "Conferindo as migrações"
    # ════════════════════════════════════════════════════════════════════════
    local SAIDA_MM
    if ! SAIDA_MM="$($COMPOSE run --rm --no-deps web python manage.py makemigrations --check --dry-run 2>&1)"; then
        echo "$SAIDA_MM" | tail -20 | sed 's/^/      /'
        erro "Há alterações nos models SEM migração correspondente."
        erro "Rode 'python manage.py makemigrations' no seu computador, faça commit e push."
        reverter_codigo
        return 1
    fi
    ok "Todas as alterações de model têm migração"

    local PLANO
    PLANO="$($COMPOSE run --rm --no-deps web python manage.py migrate --plan 2>&1)" || {
        erro "Não foi possível consultar as migrações pendentes:"
        echo "$PLANO" | tail -20
        reverter_codigo
        return 1
    }

    local PENDENTES=0
    if ! echo "$PLANO" | grep -q "No planned migration operations"; then
        PENDENTES=1
        aviso "Migrações que serão aplicadas:"
        echo "$PLANO" | grep -vE '^\s*$|^Planned operations' | sed 's/^/      /'
    else
        ok "Nenhuma migração pendente"
    fi

    # ════════════════════════════════════════════════════════════════════════
    etapa 5 "Backup do banco de dados"
    # ════════════════════════════════════════════════════════════════════════
    if [ "$PENDENTES" -eq 1 ]; then
        if ! fazer_backup; then
            erro "Sem backup válido, as migrações NÃO serão aplicadas."
            reverter_codigo
            return 1
        fi
    else
        info "Sem migrações pendentes — backup dispensado"
    fi

    # ════════════════════════════════════════════════════════════════════════
    etapa 6 "Aplicando migrações (o sistema atual continua no ar)"
    # ════════════════════════════════════════════════════════════════════════
    if [ "$PENDENTES" -eq 1 ]; then
        if ! $COMPOSE run --rm --no-deps web python manage.py migrate --noinput; then
            erro "A migração falhou. O sistema antigo continua no ar."
            erro "Backup feito antes da tentativa: $ARQUIVO_BACKUP"
            erro "Migrações do PostgreSQL são transacionais: a que falhou foi desfeita,"
            erro "mas as anteriores da mesma leva podem ter sido gravadas."
            reverter_codigo
            return 1
        fi
        MIGRACOES_APLICADAS=1
        ok "Migrações aplicadas"
    else
        info "Nada a migrar"
    fi

    # ════════════════════════════════════════════════════════════════════════
    etapa 7 "Arquivos estáticos"
    # ════════════════════════════════════════════════════════════════════════
    # Sem --clear: os arquivos antigos continuam disponíveis para o container
    # antigo, que ainda está atendendo. Apagar agora quebraria o CSS/JS de quem
    # está usando o sistema neste instante.
    if [ -d "$PROJETO/staticfiles" ]; then
        local DONO
        DONO="$(stat -c '%u:%g' "$PROJETO/staticfiles")"
        if [ "$DONO" != "$UID_STATIC:$GID_STATIC" ]; then
            info "Ajustando dono de staticfiles/ (pode pedir a senha do sudo)"
            sudo chown -R "$UID_STATIC:$GID_STATIC" "$PROJETO/staticfiles"
        fi
    fi
    # O collectstatic roda num container descartável. Ele só tem efeito se
    # /app/staticfiles for um volume compartilhado com o container web; sem
    # isso, os arquivos gerados somem junto com o container temporário.
    if ! $COMPOSE config 2>/dev/null | grep -q '/app/staticfiles'; then
        aviso "staticfiles não parece ser um volume no docker-compose.yml."
        aviso "Se CSS/JS novos não aparecerem, confira os 'volumes' do serviço web."
    fi
    if ! $COMPOSE run --rm --no-deps web python manage.py collectstatic --noinput >/dev/null; then
        erro "collectstatic falhou."
        reverter_codigo
        return 1
    fi
    ok "Estáticos coletados"

    # ════════════════════════════════════════════════════════════════════════
    etapa 8 "Colocando a versão nova no ar"
    # ════════════════════════════════════════════════════════════════════════
    $COMPOSE up -d --no-deps web
    CONTAINER_TROCADO=1
    # Registra a transição AGORA, e não só no sucesso: se o health check
    # falhar depois de migrar, o --voltar precisa saber de onde veio.
    printf '%s  %s -> %s  backup=%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" \
        "$VERSAO_ANTERIOR" "$(git rev-parse HEAD)" "${ARQUIVO_BACKUP:--}" >> "$HISTORICO"
    ok "Container web recriado"

    # ════════════════════════════════════════════════════════════════════════
    etapa 9 "Verificando se o sistema respondeu"
    # ════════════════════════════════════════════════════════════════════════
    if ! verificar_saude; then
        erro "A versão nova não respondeu."
        $COMPOSE logs --tail=60 web || true
        if [ "$MIGRACOES_APLICADAS" -eq 0 ]; then
            aviso "Nenhuma migração foi aplicada — é seguro voltar. Revertendo..."
            reverter_codigo
            $COMPOSE up -d --no-deps web
            if verificar_saude; then
                ok "Versão anterior restaurada e respondendo."
            else
                erro "A versão anterior também não respondeu. Intervenção manual necessária."
            fi
        else
            erro "Migrações JÁ foram aplicadas, então NÃO voltei o código sozinho:"
            erro "o código antigo pode não funcionar com o banco novo."
            erro "Opções:"
            erro "  • corrigir e rodar ./atualizacao.sh de novo"
            erro "  • ./atualizacao.sh --voltar   (se as migrações forem só adições)"
            erro "  • restaurar o backup: $ARQUIVO_BACKUP"
        fi
        return 1
    fi
    ok "Sistema respondendo em $URL_SAUDE"

    # ── Finalização ──────────────────────────────────────────────────────────
    if $COMPOSE ps --services 2>/dev/null | grep -qx celery; then
        $COMPOSE restart celery >/dev/null && ok "Celery reiniciado"
    fi

    if $COMPOSE exec -T web python manage.py help verificar_financeiro >/dev/null 2>&1; then
        info "Conferindo a integridade do financeiro..."
        $COMPOSE exec -T web python manage.py verificar_financeiro \
            || aviso "O verificar_financeiro apontou inconsistências — veja acima."
    fi

    docker image prune -f >/dev/null 2>&1 || true

    trap - ERR
    titulo "ATUALIZAÇÃO CONCLUÍDA em $((SECONDS - INICIO))s"
    info "De:   $(git log -1 --format='%h %s' "$VERSAO_ANTERIOR")"
    info "Para: $(git log -1 --format='%h %s')"
    [ -n "$ARQUIVO_BACKUP" ] && info "Backup: $ARQUIVO_BACKUP"
    info "Log:  $LOG"
}

# ==============================================================================
# ROTINAS
# ==============================================================================

conferir_ferramentas() {
    local falta=0
    for cmd in git docker curl flock; do
        command -v "$cmd" >/dev/null 2>&1 || { erro "Comando ausente: $cmd"; falta=1; }
    done
    [ -d "$PROJETO/.git" ] || { erro "$PROJETO não é um repositório git."; falta=1; }
    [ "$falta" -eq 0 ] || exit 1
    ok "Ferramentas disponíveis"
}

detectar_compose() {
    local arquivo="$PROJETO/docker-compose.yml"
    [ -f "$arquivo" ] || { erro "docker-compose.yml não encontrado em $PROJETO"; exit 1; }

    ENV_FILE=""
    for candidato in .env.prod .env; do
        if [ -f "$PROJETO/$candidato" ]; then ENV_FILE="$PROJETO/$candidato"; break; fi
    done
    [ -n "$ENV_FILE" ] || { erro "Nenhum .env.prod ou .env encontrado em $PROJETO"; exit 1; }

    if docker compose version >/dev/null 2>&1; then
        COMPOSE="docker compose -f $arquivo --env-file $ENV_FILE"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE="docker-compose -f $arquivo --env-file $ENV_FILE"
    else
        erro "Nem 'docker compose' nem 'docker-compose' estão disponíveis."; exit 1
    fi
    ok "Compose: $(basename "$arquivo") + $(basename "$ENV_FILE")"
}

# Lê só as variáveis de banco do .env, sem 'source': valores de produção podem
# conter caracteres que o shell interpretaria (senhas com $, !, espaço...).
ler_env() {
    local chave valor
    DB_NAME="" DB_USER="" DB_PASSWORD="" DB_HOST="" DB_PORT=""
    while IFS='=' read -r chave valor || [ -n "$chave" ]; do
        chave="${chave//[[:space:]]/}"
        chave="${chave#export}"
        case "$chave" in DB_NAME|DB_USER|DB_PASSWORD|DB_HOST|DB_PORT) ;; *) continue ;; esac
        valor="${valor%$'\r'}"
        valor="${valor#\"}"; valor="${valor%\"}"
        valor="${valor#\'}"; valor="${valor%\'}"
        printf -v "$chave" '%s' "$valor"
    done < "$ENV_FILE"
    DB_PORT="${DB_PORT:-5432}"
}

fazer_backup() {
    if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ]; then
        erro "DB_NAME/DB_USER não encontrados em $(basename "$ENV_FILE")."
        return 1
    fi

    # DB_HOST costuma apontar para o host visto de DENTRO do container
    # (host.docker.internal). Daqui de fora, o banco está em 127.0.0.1.
    local host="$DB_HOST"
    case "$host" in ""|host.docker.internal|db|postgres) host="127.0.0.1" ;; esac

    ARQUIVO_BACKUP="$DIR_BACKUP/rebanho_$(date +%Y%m%d_%H%M%S).dump"
    info "Gerando backup de $DB_NAME em $host:$DB_PORT ..."

    local feito=0
    if command -v pg_dump >/dev/null 2>&1; then
        if PGPASSWORD="$DB_PASSWORD" pg_dump -h "$host" -p "$DB_PORT" -U "$DB_USER" \
               -Fc -f "$ARQUIVO_BACKUP" "$DB_NAME" 2>/tmp/rebanho_pgdump.err; then
            feito=1
        else
            aviso "pg_dump do servidor falhou ($(head -1 /tmp/rebanho_pgdump.err)). Tentando via Docker..."
        fi
    fi

    # Sem pg_dump no servidor, ou com versão mais antiga que a do banco:
    # usa um cliente recente num container descartável.
    if [ "$feito" -eq 0 ]; then
        if docker run --rm --network host \
               -e PGPASSWORD="$DB_PASSWORD" \
               -v "$DIR_BACKUP:/backup" \
               postgres:17-alpine \
               pg_dump -h "$host" -p "$DB_PORT" -U "$DB_USER" -Fc \
               -f "/backup/$(basename "$ARQUIVO_BACKUP")" "$DB_NAME"; then
            feito=1
        fi
    fi

    if [ "$feito" -eq 0 ] || [ ! -s "$ARQUIVO_BACKUP" ]; then
        erro "O backup não foi gerado."
        rm -f "$ARQUIVO_BACKUP"
        ARQUIVO_BACKUP=""
        return 1
    fi

    # Um arquivo existir não prova que ele restaura: confere o índice do dump.
    if ! docker run --rm -v "$DIR_BACKUP:/backup" postgres:17-alpine \
            pg_restore --list "/backup/$(basename "$ARQUIVO_BACKUP")" >/dev/null 2>&1; then
        erro "O arquivo de backup está corrompido."
        return 1
    fi

    ok "Backup válido: $ARQUIVO_BACKUP ($(du -h "$ARQUIVO_BACKUP" | cut -f1))"

    # Mantém só os mais recentes
    ls -1t "$DIR_BACKUP"/rebanho_*.dump 2>/dev/null | tail -n +$((MANTER_BACKUPS + 1)) | xargs -r rm -f
}

verificar_saude() {
    local tentativa codigo
    sleep 5
    for tentativa in $(seq 1 12); do
        codigo="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$URL_SAUDE" || true)"
        case "$codigo" in
            200|301|302) return 0 ;;
        esac
        info "  tentativa $tentativa/12 — HTTP ${codigo:-sem resposta}"
        sleep 5
    done
    return 1
}

reverter_codigo() {
    if [ -z "$VERSAO_ANTERIOR" ]; then return 0; fi
    aviso "Devolvendo o código para $(git log -1 --format='%h %s' "$VERSAO_ANTERIOR")"
    git reset --hard --quiet "$VERSAO_ANTERIOR"
    if [ "$IMAGEM_CONSTRUIDA" -eq 1 ]; then
        # A imagem 'web' já foi sobrescrita pela versão nova. Sem reconstruir,
        # um restart futuro do servidor subiria a versão que acabou de falhar.
        info "Reconstruindo a imagem da versão anterior..."
        $COMPOSE build web >/dev/null || erro "Falha ao reconstruir a imagem anterior."
    fi
    if [ "$CONTAINER_TROCADO" -eq 1 ]; then
        ok "Código revertido."
    else
        ok "Código revertido. O container no ar não foi alterado."
    fi
}

voltar_versao() {
    if [ ! -s "$HISTORICO" ]; then
        erro "Não há histórico de atualizações para voltar."
        return 1
    fi

    local linha anterior atual backup
    atual="$(git rev-parse HEAD)"
    # Formato: DATA HORA ANTERIOR -> NOVA backup=ARQUIVO
    # Procura a atualização que colocou no ar a versão atual. Linhas do próprio
    # --voltar são ignoradas, para que voltar duas vezes siga recuando em vez
    # de oscilar entre as duas últimas versões.
    linha="$(grep -v '(voltar)' "$HISTORICO" | awk -v h="$atual" '$5 == h' | tail -1)"
    if [ -z "$linha" ]; then
        erro "Não há registro de qual versão estava no ar antes de $(git log -1 --format='%h' "$atual")."
        erro "Volte manualmente: git reset --hard <commit> && ./atualizacao.sh --forcar"
        return 1
    fi
    anterior="$(echo "$linha" | awk '{print $3}')"
    backup="$(echo "$linha" | sed -n 's/.*backup=\([^ ]*\).*/\1/p')"

    titulo "VOLTAR PARA A VERSÃO ANTERIOR"
    info "Atual:    $(git log -1 --format='%h %s' "$atual")"
    info "Voltar a: $(git log -1 --format='%h %s' "$anterior")"

    if git diff --name-only "$anterior" "$atual" | grep -q '/migrations/'; then
        aviso "Entre essas versões houve MIGRAÇÕES. O código vai voltar, o banco NÃO."
        aviso "Isso é seguro quando as migrações só criaram tabelas/colunas novas."
        [ "$backup" != "-" ] && aviso "Se precisar do banco anterior, o backup é: $backup"
    fi

    if [ "$PERGUNTAR" -eq 1 ]; then
        confirmar "Voltar o sistema em PRODUÇÃO para a versão anterior?" || { info "Cancelado."; return 0; }
    fi

    VERSAO_ANTERIOR="$atual"
    git reset --hard --quiet "$anterior"
    $COMPOSE build web
    $COMPOSE up -d --no-deps web

    if verificar_saude; then
        printf '%s  %s -> %s  backup=-  (voltar)\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$atual" "$anterior" >> "$HISTORICO"
        ok "Sistema de volta em $(git log -1 --format='%h %s')"
        aviso "O servidor agora está ATRÁS da main. Um novo ./atualizacao.sh traria a versão de volta."
    else
        erro "A versão anterior não respondeu. Veja: $COMPOSE logs --tail=100 web"
        return 1
    fi
}

falha_inesperada() {
    trap - ERR
    erro "Erro inesperado na linha $1 do script."
    reverter_codigo || true
    erro "Log completo: ${LOG:-(sem log)}"
    exit 1
}

confirmar() {
    local resposta
    if [ ! -t 0 ]; then
        erro "Sem terminal para confirmar. Use --sim para rodar sem perguntas."
        return 1
    fi
    read -r -p "$(printf '\n\033[1;33m%s [s/N] \033[0m' "$1")" resposta
    [[ "$resposta" =~ ^[sS]$ ]]
}

# ── Saída formatada ─────────────────────────────────────────────────────────
if [ -t 1 ]; then
    C_OK=$'\033[0;32m' C_ERRO=$'\033[0;31m' C_AVISO=$'\033[1;33m' C_INFO=$'\033[0;36m' C_B=$'\033[1m' C_N=$'\033[0m'
else
    C_OK="" C_ERRO="" C_AVISO="" C_INFO="" C_B="" C_N=""
fi
titulo() { printf '\n%s══════════════════════════════════════════════════════════\n  %s\n══════════════════════════════════════════════════════════%s\n' "$C_B" "$1" "$C_N"; }
etapa()  { printf '\n%s[%s/9] %s%s\n' "$C_B" "$1" "$2" "$C_N"; }
ok()     { printf '  %s✓%s %s\n' "$C_OK" "$C_N" "$1"; }
erro()   { printf '  %s✗ %s%s\n' "$C_ERRO" "$1" "$C_N"; }
aviso()  { printf '  %s⚠ %s%s\n' "$C_AVISO" "$1" "$C_N"; }
info()   { printf '  %s→%s %s\n' "$C_INFO" "$C_N" "$1"; }

main "$@"; exit $?
