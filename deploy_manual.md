# 🐄 Gestão de Rebanhos — Manual de Deploy em Produção

> **VPS Zerada → Sistema Online** | Django + Gunicorn + PostgreSQL + Redis + Docker + Nginx + SSL

---

## Índice

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Pré-requisitos](#2-pré-requisitos)
3. [Configuração Inicial da VPS](#3-configuração-inicial-da-vps)
4. [Instalar Dependências do Sistema](#4-instalar-dependências-do-sistema)
5. [Configurar PostgreSQL](#5-configurar-postgresql)
6. [Clonar e Configurar o Projeto](#6-clonar-e-configurar-o-projeto)
7. [Configurar Docker Compose](#7-configurar-docker-compose)
8. [Configurar Nginx](#8-configurar-nginx)
9. [Configurar SSL com Let's Encrypt](#9-configurar-ssl-com-lets-encrypt)
10. [Primeiro Acesso](#10-primeiro-acesso)
11. [Manutenção e Operação](#11-manutenção-e-operação)
12. [Resolução de Problemas](#12-resolução-de-problemas)
13. [Checklist de Deploy](#13-checklist-de-deploy)

---

## 1. Visão Geral da Arquitetura

```
Internet (HTTPS 443)
       │
┌──────▼──────────────────────────────────┐
│  Nginx (sistema)  portas 80 / 443       │
│  - Redirect HTTP → HTTPS                │
│  - SSL Let's Encrypt (auto-renovação)   │
│  - Serve /static/ e /media/ direto      │
└──────┬──────────────────────────────────┘
       │ proxy_pass 127.0.0.1:8080
┌──────▼──────────────────────────────────┐
│  Docker: rebanho_web                    │
│  - Django 4.2 + Gunicorn (3 workers)    │
│  - porta 127.0.0.1:8080 (só local)      │
└──────┬────────────────┬─────────────────┘
       │                │
┌──────▼──────┐  ┌──────▼──────────────────┐
│  rebanho_   │  │  PostgreSQL (host)       │
│  redis      │  │  porta 5432              │
│  (Docker)   │  │  banco: livestock_db     │
└─────────────┘  └─────────────────────────┘
┌─────────────────────────────────────────┐
│  Docker: rebanho_celery                 │
│  - Workers assíncronos (Celery)         │
└─────────────────────────────────────────┘
```

### Por que PostgreSQL no host (fora do Docker)?

- Melhor performance de I/O
- Backups nativos com `pg_dump` sem complexidade extra
- Persistência independente do ciclo de vida dos containers
- Compatível com outros projetos no mesmo servidor

### Requisitos mínimos de hardware

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| CPU     | 1 vCPU | 2 vCPU      |
| RAM     | 1 GB   | 2 GB        |
| Disco   | 10 GB  | 20 GB SSD   |
| OS      | Ubuntu 22.04 LTS | Ubuntu 22.04 ou 24.04 LTS |
| Rede    | IP público estático | IP público estático |

---

## 2. Pré-requisitos

> ⚠️ **Antes de começar**, verifique os itens abaixo.

### 2.1 DNS configurado

O domínio precisa estar apontando para o IP da VPS com pelo menos **30 minutos de antecedência**. O certbot (SSL) falhará se o DNS não estiver propagado.

```bash
# Verificar propagação do DNS (execute na sua máquina local)
nslookup rebanho.seudominio.com.br

# Deve retornar o IP da sua VPS
```

### 2.2 Acesso SSH à VPS

```bash
# Conectar como root
ssh root@SEU_IP_DA_VPS

# Ou com usuário existente
ssh usuario@SEU_IP_DA_VPS
```

### 2.3 Repositório GitHub acessível

O código deve estar em um repositório GitHub. Se for privado, você precisará de um **Personal Access Token** ou **Deploy Key**.

---

## 3. Configuração Inicial da VPS

### 3.1 Atualizar o sistema

```bash
apt update && apt upgrade -y

# Instalar utilitários essenciais
apt install -y curl wget git nano unzip htop
```

### 3.2 Criar usuário de deploy (recomendado)

Evite usar o root para operações cotidianas:

```bash
# Criar usuário "deploy"
adduser deploy

# Adicionar ao grupo sudo
usermod -aG sudo deploy

# Trocar para o usuário deploy
su - deploy

# Verificar sudo
sudo whoami  # deve retornar: root
```

### 3.3 Configurar firewall (UFW)

> ⚠️ **Execute o `allow ssh` ANTES de habilitar o UFW.** Caso contrário, você perderá o acesso à VPS.

```bash
# Permitir SSH primeiro (OBRIGATÓRIO)
sudo ufw allow ssh

# Permitir HTTP e HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Habilitar firewall
sudo ufw enable

# Verificar status
sudo ufw status verbose
```

---

## 4. Instalar Dependências do Sistema

### 4.1 Docker e Docker Compose

```bash
# Instalar dependências
sudo apt install -y ca-certificates curl gnupg lsb-release

# Adicionar chave GPG oficial do Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Adicionar repositório oficial
echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker Engine + Compose
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

# Adicionar usuário ao grupo docker (evita usar sudo a cada comando)
sudo usermod -aG docker deploy

# IMPORTANTE: fazer logout e login novamente para aplicar o grupo
exit
ssh deploy@SEU_IP

# Verificar instalação
docker --version
docker compose version
```

### 4.2 PostgreSQL (no host, fora do Docker)

```bash
# Instalar PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Verificar status
sudo systemctl status postgresql

# Habilitar início automático
sudo systemctl enable postgresql

# Verificar versão
psql --version
```

### 4.3 Nginx

```bash
# Instalar Nginx
sudo apt install -y nginx

# Habilitar e iniciar
sudo systemctl enable nginx
sudo systemctl start nginx

# Verificar versão
nginx -v
```

### 4.4 Certbot (SSL)

```bash
# Instalar certbot com plugin nginx
sudo apt install -y certbot python3-certbot-nginx

# Verificar instalação
certbot --version
```

---

## 5. Configurar PostgreSQL

### 5.1 Criar banco de dados e usuário

```bash
# Acessar o PostgreSQL como superusuário
sudo -u postgres psql
```

Dentro do prompt `psql`, execute:

```sql
CREATE USER livestock_user WITH PASSWORD 'SUA_SENHA_AQUI';
CREATE DATABASE livestock_db OWNER livestock_user;
GRANT ALL PRIVILEGES ON DATABASE livestock_db TO livestock_user;
\q
```

Testar a conexão:

```bash
psql -h 127.0.0.1 -U livestock_user -d livestock_db -c "\l"
# Informe a senha quando solicitado
```

### 5.2 Liberar acesso para os containers Docker

Os containers Docker usam a faixa de IP `172.17.0.0/16`. O PostgreSQL precisa aceitar conexões dessa rede.

```bash
# Descobrir o caminho do pg_hba.conf
sudo -u postgres psql -c "SHOW hba_file;"

# Editar o arquivo (caminho típico no Ubuntu 22.04)
sudo nano /etc/postgresql/14/main/pg_hba.conf
```

Adicione esta linha **no final do arquivo**:

```
# Permite acesso do Docker ao banco livestock
host  livestock_db  livestock_user  172.17.0.0/16  scram-sha-256
```

Salve e reinicie o PostgreSQL:

```bash
sudo systemctl restart postgresql

# Verificar que está ouvindo
sudo ss -tlnp | grep 5432
```

> ℹ️ **Nota:** Em servidores com múltiplos projetos Docker (como n8n, outros apps), pode haver uma linha mais ampla como `host all all 172.17.0.0/16 scram-sha-256`. Nesse caso, não precisa adicionar uma linha específica.

---

## 6. Clonar e Configurar o Projeto

### 6.1 Criar estrutura de diretórios

```bash
# Criar diretório padrão para projetos Docker
sudo mkdir -p /var/www/docker-instances
sudo chown deploy:deploy /var/www/docker-instances
cd /var/www/docker-instances
```

### 6.2 Clonar o repositório

```bash
# Repositório público
git clone https://github.com/Frraz/Rebanho
cd Rebanho

# Para repositório PRIVADO, use token:
# git clone https://SEU_TOKEN@github.com/Frraz/Rebanho

# Verificar estrutura
ls -la
```

### 6.3 Criar o arquivo `.env.prod`

> ⚠️ **Este arquivo NUNCA deve ser commitado no Git.** Verifique se `.env.prod` está no `.gitignore`.

```bash
nano .env.prod
```

Cole e preencha o conteúdo abaixo:

```env
# ==============================================================
# .env.prod — Variáveis de Ambiente de PRODUÇÃO
# NUNCA commite este arquivo no Git!
# ==============================================================

# Django
DEBUG=False
ALLOWED_HOSTS=rebanho.seudominio.com.br,www.rebanho.seudominio.com.br

# Gerar com:
# python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY=GERE_UMA_CHAVE_SECRETA_AQUI

# Banco de dados (PostgreSQL no host)
DB_NAME=livestock_db
DB_USER=livestock_user
DB_PASSWORD=SUA_SENHA_DO_BANCO
DB_HOST=host.docker.internal
DB_PORT=5432

# Redis (container Docker)
REDIS_URL=redis://redis:6379/1
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# E-mail (Gmail com App Password)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu.email@gmail.com
EMAIL_HOST_PASSWORD=GMAIL_APP_PASSWORD_AQUI
DEFAULT_FROM_EMAIL=Gestão de Rebanhos <seu.email@gmail.com>

# Segurança
CSRF_TRUSTED_ORIGINS=https://rebanho.seudominio.com.br
```

### 6.4 Gerar a SECRET_KEY

```bash
# Gerar uma chave aleatória segura
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Cole o resultado no .env.prod na variável SECRET_KEY
```

### 6.5 Verificar o `requirements.txt`

O `gunicorn` precisa estar presente e **sem comentário**:

```bash
# Verificar
grep gunicorn requirements.txt

# Se estiver comentado (com #), descomentar:
sed -i 's/# gunicorn/gunicorn/' requirements.txt

# Confirmar
grep gunicorn requirements.txt
# Deve mostrar: gunicorn>=21.2.0  # WSGI server
```

### 6.6 Criar diretórios necessários

```bash
# Criar diretórios para arquivos estáticos e mídia
mkdir -p staticfiles media

# Dar permissão de escrita para o container
sudo chmod 777 staticfiles media
```

### 6.7 Verificar o `docker-compose.yml`

Certifique-se de que o arquivo contém os pontos críticos:

```bash
cat docker-compose.yml
```

Pontos obrigatórios a verificar:

- `extra_hosts: ["host.docker.internal:host-gateway"]` nos serviços `web` e `celery`
- Porta mapeada como `"127.0.0.1:8080:8000"` (apenas local)
- Volumes `./staticfiles` e `./media` como bind mounts

Conteúdo correto do `docker-compose.yml`:

```yaml
services:

  web:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: rebanho_web
    restart: unless-stopped
    env_file: .env.prod
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ./staticfiles:/app/staticfiles
      - ./media:/app/media
      - logs_volume:/app/logs
    ports:
      - "127.0.0.1:8080:8000"
    depends_on:
      - redis
    networks:
      - rebanho_net
    command: sh -c "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120 --access-logfile /app/logs/gunicorn_access.log --error-logfile /app/logs/gunicorn_error.log"

  celery:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: rebanho_celery
    restart: unless-stopped
    env_file: .env.prod
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - logs_volume:/app/logs
    depends_on:
      - redis
    networks:
      - rebanho_net
    command: celery -A config worker --loglevel=info --concurrency=2 --logfile=/app/logs/celery.log

  redis:
    image: redis:7-alpine
    container_name: rebanho_redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    networks:
      - rebanho_net
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

volumes:
  redis_data:
  logs_volume:

networks:
  rebanho_net:
    driver: bridge
```

---

## 7. Configurar Docker Compose

### 7.1 Construir e iniciar os containers

```bash
# Construir as imagens Docker
docker compose build

# Iniciar todos os serviços em background
docker compose up -d

# Acompanhar os logs em tempo real
docker compose logs -f web
# Aguarde aparecer: "Booting worker with pid: XX"
# Pode levar 30-60 segundos
```

### 7.2 Verificar status dos containers

```bash
# Ver status de todos os containers
docker compose ps

# Resultado esperado:
# NAME             STATUS    PORTS
# rebanho_web      Up        127.0.0.1:8080->8000/tcp
# rebanho_celery   Up        8000/tcp
# rebanho_redis    Up        6379/tcp

# Testar se o Gunicorn está respondendo
curl -I http://127.0.0.1:8080/login/
# Deve retornar: HTTP/1.1 200 OK ou 301
```

> ⚠️ **Container em Restarting (127)?** Veja a [Seção 12](#12-resolução-de-problemas).

---

## 8. Configurar Nginx

### 8.1 Criar o virtual host (versão HTTP inicial)

```bash
sudo nano /etc/nginx/sites-available/rebanho.seudominio.com.br
```

Cole a configuração abaixo (versão HTTP, antes do SSL):

```nginx
server {
    listen 80;
    server_name rebanho.seudominio.com.br www.rebanho.seudominio.com.br;

    # Desafio Let's Encrypt
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Arquivos estáticos (servidos direto pelo Nginx — sem passar pelo Django)
    location /static/ {
        alias /var/www/docker-instances/Rebanho/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location /media/ {
        alias /var/www/docker-instances/Rebanho/media/;
        expires 7d;
        access_log off;
    }

    # Proxy para Gunicorn (Docker porta 8080)
    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_redirect     off;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
        proxy_buffer_size        128k;
        proxy_buffers            4 256k;
        proxy_busy_buffers_size  256k;
    }

    location = /favicon.ico { access_log off; log_not_found off; }
}
```

### 8.2 Ativar o site

```bash
# Criar pasta para o certbot
sudo mkdir -p /var/www/certbot

# Criar symlink para ativar o site
sudo ln -s /etc/nginx/sites-available/rebanho.seudominio.com.br \
           /etc/nginx/sites-enabled/rebanho.seudominio.com.br

# Desativar o site default (em VPS zerada)
sudo rm -f /etc/nginx/sites-enabled/default

# Testar configuração
sudo nginx -t
# Deve retornar: configuration file test is successful

# Recarregar Nginx
sudo systemctl reload nginx

# Testar acesso HTTP
curl -I http://rebanho.seudominio.com.br/login/
# Deve retornar: HTTP/1.1 200 OK
```

---

## 9. Configurar SSL com Let's Encrypt

### 9.1 Emitir certificado SSL

```bash
# Emitir certificado (substitua domínio e e-mail)
sudo certbot --nginx \
    -d rebanho.seudominio.com.br \
    --email seu.email@gmail.com \
    --agree-tos \
    --no-eff-email \
    --redirect
```

O certbot irá automaticamente:
1. Verificar que o domínio aponta para este servidor
2. Emitir o certificado SSL gratuito
3. Atualizar o virtual host com os blocos SSL
4. Configurar redirect HTTP → HTTPS automático

### 9.2 Corrigir configuração HTTPS do Django

Após o certbot atualizar o Nginx, verifique se o `settings.py` está correto para evitar loop de redirects:

```bash
# No servidor, verificar o settings.py
grep -n "SECURE_SSL\|PROXY_SSL" config/settings.py
```

Deve conter (dentro do bloco `if not DEBUG:`):

```python
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False  # O Nginx já faz o redirect HTTP→HTTPS
```

Se precisou alterar o `settings.py`, reconstrua:

```bash
docker compose build web
docker compose up -d --no-deps web
```

### 9.3 Verificar SSL

```bash
# Testar HTTPS
curl -I https://rebanho.seudominio.com.br/login/
# Deve retornar: HTTP/1.1 200 OK

# Ver detalhes do certificado emitido
sudo certbot certificates

# Testar renovação automática (simulação)
sudo certbot renew --dry-run
```

### 9.4 Renovação automática

O certbot configura um timer systemd automaticamente. Verifique:

```bash
sudo systemctl status certbot.timer
```

Se não estiver ativo, adicione ao crontab:

```bash
sudo crontab -e
# Adicionar:
0 12 * * * certbot renew --quiet && systemctl reload nginx
```

---

## 10. Primeiro Acesso

### 10.1 Criar superusuário

```bash
docker compose exec web python manage.py createsuperuser
# Username: admin (ou nome de sua preferência)
# Email: seu.email@gmail.com
# Password: (mínimo 8 caracteres)
```

### 10.2 Verificar migrações

```bash
# Verificar se há migrações pendentes
docker compose exec web python manage.py showmigrations

# Criar migrações se houver models alterados
docker compose exec web python manage.py makemigrations

# Aplicar
docker compose exec web python manage.py migrate
```

### 10.3 Acessar o sistema

| URL | Destino |
|-----|---------|
| `https://rebanho.seudominio.com.br` | Sistema principal |
| `https://rebanho.seudominio.com.br/login/` | Tela de login |
| `https://rebanho.seudominio.com.br/admin/` | Admin Django |

---

## 11. Manutenção e Operação

### 11.1 Comandos do dia a dia

```bash
# Status dos containers
docker compose ps

# Logs em tempo real
docker compose logs -f web
docker compose logs -f celery

# Reiniciar só a aplicação (sem derrubar Redis)
docker compose restart web

# Parar tudo
docker compose down

# Iniciar tudo
docker compose up -d

# Shell Django interativo
docker compose exec web python manage.py shell

# Status do Nginx
sudo systemctl status nginx

# Recarregar Nginx (sem interrupção)
sudo systemctl reload nginx

# Estatísticas dos containers
docker stats --no-stream
```

### 11.2 Atualizar código (novo deploy)

```bash
cd /var/www/docker-instances/Rebanho

# Baixar alterações do repositório
git pull origin main

# Reconstruir a imagem com o novo código
docker compose build web

# Reiniciar apenas o container web
docker compose up -d --no-deps web

# Acompanhar inicialização
docker compose logs -f web
```

### 11.3 Backup do banco de dados

```bash
# Backup manual
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
sudo -u postgres pg_dump livestock_db | gzip > backup_${TIMESTAMP}.sql.gz

# Restaurar backup
gunzip -c backup_20260101_120000.sql.gz | sudo -u postgres psql livestock_db
```

**Automatizar backup diário:**

```bash
sudo crontab -e
# Adicionar (backup às 3h da manhã):
0 3 * * * sudo -u postgres pg_dump livestock_db | gzip > /backups/livestock_$(date +\%Y\%m\%d).sql.gz

# Criar diretório de backups
sudo mkdir -p /backups
```

### 11.4 Monitoramento

```bash
# Uso de CPU e RAM
htop

# Uso de disco
df -h

# Tamanho do banco de dados
sudo -u postgres psql -c "\l+"

# Logs de erro do Nginx
sudo tail -50 /var/log/nginx/error.log

# Logs de acesso do Gunicorn
docker compose exec web tail -50 /app/logs/gunicorn_access.log
```

---

## 12. Resolução de Problemas

### `502 Bad Gateway`

O container web está fora do ar:

```bash
docker compose ps
docker compose logs web --tail=30

# Reiniciar
docker compose restart web
```

---

### `ERR_TOO_MANY_REDIRECTS`

O Django está redirecionando para HTTPS sem reconhecer que já está em HTTPS. No `config/settings.py`, dentro do bloco `if not DEBUG:`:

```python
# Deve ter ESTAS DUAS LINHAS:
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False  # Nginx já faz o redirect
```

Após corrigir:

```bash
docker compose build web
docker compose up -d --no-deps web
```

---

### `gunicorn: not found` (container em Restarting 127)

```bash
# Verificar requirements.txt
grep gunicorn requirements.txt

# Descomentar se necessário
sed -i 's/# gunicorn/gunicorn/' requirements.txt

# Reconstruir com --no-cache
docker compose build --no-cache web
docker compose up -d --no-deps web
```

---

### Erro de autenticação PostgreSQL

```bash
# Verificar usuários existentes
sudo -u postgres psql -c "\du"

# Se o usuário não existir, criar
sudo -u postgres psql << 'SQL'
CREATE USER livestock_user WITH PASSWORD 'SUA_SENHA';
CREATE DATABASE livestock_db OWNER livestock_user;
GRANT ALL PRIVILEGES ON DATABASE livestock_db TO livestock_user;
SQL

# Se a senha estiver errada, redefinir
sudo -u postgres psql -c "ALTER USER livestock_user PASSWORD 'NOVA_SENHA';"

# Verificar pg_hba.conf
sudo grep livestock /etc/postgresql/14/main/pg_hba.conf

# Reiniciar PostgreSQL
sudo systemctl restart postgresql
```

---

### `host.docker.internal` não resolve (Linux)

No Linux, o `host.docker.internal` não é configurado automaticamente. O `docker-compose.yml` precisa ter:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Se estiver faltando, adicione nos serviços `web` e `celery` e faça rebuild.

---

### Certificado SSL não emite

```bash
# Verificar se o domínio aponta para este IP
nslookup rebanho.seudominio.com.br

# Verificar se a porta 80 está acessível
sudo ss -tlnp | grep :80

# Ver log detalhado do certbot
sudo cat /var/log/letsencrypt/letsencrypt.log

# Testar com modo verbose
sudo certbot --nginx -d rebanho.seudominio.com.br -v
```

---

### Arquivos estáticos não carregam (CSS/JS sem estilo)

```bash
# Verificar se staticfiles está populado
ls -la staticfiles/

# Se vazio, coletar novamente
docker compose exec web python manage.py collectstatic --noinput

# Verificar permissões
sudo chmod 755 staticfiles/

# Testar nginx
sudo nginx -t && sudo systemctl reload nginx
```

---

### Nginx: erro `unknown directive "http2"`

Ocorre no Nginx 1.24 (Ubuntu). Substitua:

```nginx
# ❌ Errado (Nginx 1.25+)
listen 443 ssl;
http2 on;

# ✅ Correto (Nginx 1.24)
listen 443 ssl http2;
```

---

## 13. Checklist de Deploy

Use esta lista para garantir que nenhum passo foi esquecido:

### Infraestrutura
- [ ] VPS com Ubuntu 22.04 LTS criada
- [ ] IP público estático configurado
- [ ] DNS do domínio apontando para o IP da VPS
- [ ] DNS propagado (testar com `nslookup`)
- [ ] Acesso SSH funcionando

### Sistema Operacional
- [ ] `apt update && apt upgrade` executado
- [ ] Usuário `deploy` criado com sudo
- [ ] UFW configurado (ssh, 80, 443)
- [ ] Docker instalado e funcionando
- [ ] Usuário `deploy` no grupo `docker` (logout/login após)
- [ ] PostgreSQL instalado e rodando
- [ ] Nginx instalado e rodando
- [ ] Certbot instalado

### Banco de Dados
- [ ] Usuário `livestock_user` criado
- [ ] Banco `livestock_db` criado
- [ ] `pg_hba.conf` com `172.17.0.0/16` liberado
- [ ] PostgreSQL reiniciado após alteração do `pg_hba.conf`
- [ ] Conexão testada com `psql -h 127.0.0.1 -U livestock_user -d livestock_db`

### Aplicação
- [ ] Repositório clonado em `/var/www/docker-instances/Rebanho`
- [ ] `.env.prod` criado com todos os valores preenchidos
- [ ] `SECRET_KEY` gerada e configurada
- [ ] `gunicorn` descomentado no `requirements.txt`
- [ ] Diretórios `staticfiles/` e `media/` criados com permissão
- [ ] `docker compose build` executado sem erros
- [ ] `docker compose up -d` executado
- [ ] Todos os containers com status `Up`
- [ ] Gunicorn respondendo em `127.0.0.1:8080` (`curl -I http://127.0.0.1:8080/login/`)

### Nginx e SSL
- [ ] Virtual host criado em `sites-available`
- [ ] Symlink criado em `sites-enabled`
- [ ] `sudo nginx -t` sem erros
- [ ] Site respondendo em HTTP (`curl -I http://seudominio.com.br`)
- [ ] Certificado SSL emitido com certbot
- [ ] Site respondendo em HTTPS com `200 OK`
- [ ] Redirect HTTP → HTTPS funcionando
- [ ] `SECURE_PROXY_SSL_HEADER` configurado no `settings.py`
- [ ] Sem loop de redirect (`ERR_TOO_MANY_REDIRECTS`)

### Sistema Funcionando
- [ ] Superusuário Django criado
- [ ] Login na interface web funcionando
- [ ] CSS e JavaScript carregando (página com estilo)
- [ ] Logo aparecendo corretamente
- [ ] Backup automático configurado no crontab

---

> **Sistema online em:** `https://rebanho.seudominio.com.br`
>
> Desenvolvido por **Warley Ferraz** — [GitHub](https://github.com/Frraz) | [LinkedIn](https://www.linkedin.com/in/warley-ferraz-almeida-280a55185/)