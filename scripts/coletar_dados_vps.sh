#!/usr/bin/env bash
# Coleta os valores dos secrets do GitHub. Rode no VPS.
# Nao imprime nenhuma chave privada.

linha() { printf '%s\n' "------------------------------------------------------------"; }

linha
echo "  VALORES PARA OS SECRETS DO GITHUB"
linha
echo

# ---------- VPS_HOST ----------
echo "[VPS_HOST] IP publico deste servidor"
IP=""
if command -v curl >/dev/null 2>&1; then
    IP=$(curl -s --max-time 10 https://api.ipify.org 2>/dev/null)
elif command -v wget >/dev/null 2>&1; then
    IP=$(wget -qO- --timeout=10 https://api.ipify.org 2>/dev/null)
fi
if [ -n "$IP" ]; then
    echo "    -> $IP"
else
    echo "    (nao foi possivel consultar; use o IP do painel da Hostinger)"
fi
echo
echo "    IPs das interfaces locais:"
if command -v ip >/dev/null 2>&1; then
    ip -4 -o addr show 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | grep -v '^127\.' | sed 's/^/      /'
else
    hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | sed 's/^/      /'
fi
echo

# ---------- VPS_USER ----------
echo "[VPS_USER] usuario atual"
echo "    -> $(id -un)"
echo

# ---------- Diretorio do projeto ----------
echo "[PROJETO] onde o codigo realmente esta"
for d in /var/www/docker-instances/Rebanho "$HOME/Rebanho"; do
    if [ -d "$d" ]; then
        printf '    EXISTE      %s\n' "$d"
        if [ -L "$d" ]; then
            printf '                symlink -> %s\n' "$(readlink -f "$d")"
        fi
        if [ -f "$d/docker-compose.yml" ]; then
            printf '                tem docker-compose.yml\n'
        else
            printf '                SEM docker-compose.yml\n'
        fi
        if [ -d "$d/.git" ]; then
            printf '                git: %s\n' "$(git -C "$d" log -1 --oneline 2>/dev/null || echo '?')"
        fi
    else
        printf '    nao existe  %s\n' "$d"
    fi
done
echo

# ---------- Chaves autorizadas ----------
echo "[SSH] chaves autorizadas para $(id -un)"
AK="$HOME/.ssh/authorized_keys"
if [ -f "$AK" ]; then
    # grep -c sai com codigo 1 quando nao acha nada; sem o "|| true" o
    # shell imprimiria o zero do grep E o do fallback.
    TOTAL=$(grep -cE '^(ssh-|ecdsa-|sk-)' "$AK" 2>/dev/null || true)
    echo "    ${TOTAL:-0} chave(s) cadastrada(s):"
    # Mostra so o tipo e o comentario - nunca o material da chave
    awk '/^(ssh-|ecdsa-|sk-)/ { c = ($3 != "" ? $3 : "(sem comentario)"); print "      " $1 "  " c }' "$AK"
    echo
    echo "    permissoes:"
    printf '      %s  %s\n' "$(stat -c '%a' "$HOME/.ssh" 2>/dev/null)" "$HOME/.ssh   (esperado 700)"
    printf '      %s  %s\n' "$(stat -c '%a' "$AK" 2>/dev/null)" "$AK   (esperado 600)"
else
    echo "    $AK NAO EXISTE"
fi
echo

# ---------- Config do sshd ----------
echo "[SSHD] configuracao efetiva"
if sudo -n true 2>/dev/null; then
    sudo sshd -T 2>/dev/null \
      | grep -E '^(port|pubkeyauthentication|passwordauthentication|permitrootlogin|allowusers|allowgroups)' \
      | sed 's/^/      /'
else
    echo "      (precisa de sudo com senha - rode: sudo sshd -T | grep -E 'port|pubkey|password')"
fi
echo
linha
echo "  Lembrete: a chave PRIVADA nunca deve ser colada em chat algum."
linha
