# Runbook — Subir o módulo financeiro para produção

Guia de uma vez só, para esta release específica. Ela é diferente das anteriores
por um motivo: **inclui uma migração que reescreve dados históricos** (importa
todas as vendas já cadastradas para o novo módulo financeiro).

---

## Antes de começar, três coisas que você precisa saber

**1. O deploy é automático e roda as migrações sozinho.**
`.github/workflows/deploy.yml` dispara em todo push na `main` e executa
`manage.py migrate --noinput` no passo 6 de 9. Não há confirmação manual.

**2. Não existe rollback automático.**
O health check acontece no passo *depois* das migrações. Se ele falhar, o
pipeline reporta erro — mas o banco **já foi migrado** e o site fica no ar
quebrado. Voltar é trabalho manual (ver a última seção).

**3. Você não precisa dar `git pull` no VPS.**
O próprio pipeline faz `git reset --hard origin/main` no servidor. Um pull
manual só criaria divergência. O acesso SSH nesta release serve para
*validar* e *conferir*, não para atualizar o código.

---

## Fase 0 — Enviar a branch (não deploya nada)

O workflow só dispara na `main`. Enviar a branch de trabalho é seguro e já
deixa o código no GitHub.

```bash
git push -u origin feature/financeiro
```

---

## Fase 1 — Validar num clone do banco de produção

Esta é a fase que não pode ser pulada. Tudo acontece no VPS, **sem tocar no
banco de produção**.

### 1.1 Backup

```bash
ssh <seu-usuario>@<ip-do-vps>
cd /var/www/docker-instances/Rebanho

# Os valores reais estão no .env.prod
source .env.prod

mkdir -p ~/backups
BACKUP=~/backups/rebanho_$(date +%Y%m%d_%H%M%S).dump

PGPASSWORD="$DB_PASSWORD" pg_dump \
  -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
  -Fc -f "$BACKUP" "$DB_NAME"

ls -lh "$BACKUP"
```

Confira que o arquivo tem tamanho compatível com a base. Um dump de poucos KB
significa que algo deu errado — **não siga adiante**.

### 1.2 Restaurar numa base de teste

```bash
PGPASSWORD="$DB_PASSWORD" createdb \
  -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" livestock_teste

PGPASSWORD="$DB_PASSWORD" pg_restore \
  -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
  -d livestock_teste --no-owner --no-privileges "$BACKUP"
```

### 1.3 Rodar a migração contra a base de teste

```bash
cd /var/www/docker-instances/Rebanho

# Traz o código novo SEM mexer na main nem no que está rodando
git fetch origin
git worktree add /tmp/rebanho-teste origin/feature/financeiro
cd /tmp/rebanho-teste

# Roda dentro de um container descartável, apontando para a base de teste
docker compose -f /var/www/docker-instances/Rebanho/docker-compose.yml \
  --env-file /var/www/docker-instances/Rebanho/.env.prod \
  run --rm \
  -e DB_NAME=livestock_teste \
  -v /tmp/rebanho-teste:/app \
  web python manage.py migrate
```

**Leia com atenção a saída.** O backfill imprime um resumo assim:

```
[BACKFILL FINANCEIRO] Vendas importadas: 412 | com valor (viraram dívida): 180 |
sem valor (a completar): 232 | canceladas (sem efeito no saldo): 0 |
preço ilegível: 0 | sem cliente (ignoradas): 0 | já importadas antes: 0
```

O que conferir:

| Número | O que significa | Quando se preocupar |
|--------|-----------------|---------------------|
| **Vendas importadas** | Deve bater com o total de vendas do sistema | Se for 0 ou muito menor que o esperado |
| **com valor** | Viraram dívida no saldo dos clientes | — |
| **sem valor** | Vendas antigas sem preço; ficam editáveis | Esperado ser alto, você já sabia disso |
| **preço ilegível** | Tinha algo escrito que não deu para ler | Se for > 0, me avise antes de seguir |
| **sem cliente** | Vendas órfãs, ignoradas | Se for > 0, os IDs aparecem no log |

### 1.4 Conferir a integridade

```bash
docker compose -f /var/www/docker-instances/Rebanho/docker-compose.yml \
  --env-file /var/www/docker-instances/Rebanho/.env.prod \
  run --rm -e DB_NAME=livestock_teste -v /tmp/rebanho-teste:/app \
  web python manage.py verificar_financeiro
```

O esperado é **"Tudo certo. Nenhuma inconsistência encontrada."**

### 1.5 Rodar a suíte de testes

```bash
docker compose -f /var/www/docker-instances/Rebanho/docker-compose.yml \
  --env-file /var/www/docker-instances/Rebanho/.env.prod \
  run --rm -v /tmp/rebanho-teste:/app web pytest
```

### 1.6 Conferir que a migração escrita à mão bate com os modelos

```bash
docker compose -f /var/www/docker-instances/Rebanho/docker-compose.yml \
  --env-file /var/www/docker-instances/Rebanho/.env.prod \
  run --rm -e DB_NAME=livestock_teste -v /tmp/rebanho-teste:/app \
  web python manage.py makemigrations --check --dry-run
```

Tem que dizer **"No changes detected"**. Se acusar diferença, o deploy vai
falhar no passo 7 — pare aqui e gere a migração que falta.

### 1.7 Conferir que os relatórios antigos não mudaram

Abra o Relatório por Fazenda de um mês passado **no sistema em produção** e
anote os números. Depois do deploy, abra o mesmo relatório e compare. Eles
precisam ser idênticos — a migração não deve mexer em estoque.

### 1.8 Limpar

```bash
git worktree remove /tmp/rebanho-teste
PGPASSWORD="$DB_PASSWORD" dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" livestock_teste
```

---

## Fase 2 — Subir para produção

Só depois de a Fase 1 ter passado limpa.

```bash
# Na sua máquina
git checkout main
git pull origin main          # garante que a main local está em dia
git merge --no-ff feature/financeiro
git push origin main          # ← É AQUI que o deploy dispara
```

Acompanhe em **GitHub → Actions**. O pipeline leva alguns minutos e passa por
9 passos mais o health check.

Escolha um horário de baixo movimento. Se alguém estiver cadastrando algo no
momento do restart, vai ver um erro de conexão.

---

## Fase 3 — Conferir o sistema no ar

Depois do check verde no Actions:

```bash
ssh <seu-usuario>@<ip-do-vps>
cd /var/www/docker-instances/Rebanho

docker compose --env-file .env.prod run --rm web python manage.py verificar_financeiro
docker compose --env-file .env.prod logs --tail=100 web
```

E no navegador, em https://rebanho.ferzion.com.br:

- [ ] **Ocorrências → Venda** abre a lista de vendas, com o histórico importado
- [ ] Uma venda antiga que tinha preço aparece com o valor certo
- [ ] **Relatórios → Saldos** mostra os clientes com as dívidas importadas
- [ ] **Relatórios → Fluxo Financeiro** abre no mês atual
- [ ] **Ocorrências → Pagamentos** abre vazio, e o cadastro funciona
- [ ] **Relatório por Fazenda** de um mês passado bate com o que você anotou em 1.7
- [ ] **Ficha de Controle Manual** continua gerando o PDF

Teste de ponta a ponta, com dados reais pequenos:

1. Cadastre uma venda com 2 lotes, sendo os dois do mesmo tipo de animal
2. Confira a baixa no estoque da fazenda
3. Veja o cliente ficar negativo em Saldos
4. Lance um pagamento maior que a dívida → o saldo vira positivo
5. Apague a venda → os animais voltam ao estoque e o débito some
6. Veja a venda apagada em **Relatórios → Histórico de Exclusões**

---

## Se der errado

O pipeline **não desfaz nada sozinho**. Como as migrações só criam tabelas
novas (nenhuma tabela existente foi alterada), você tem duas saídas:

### Opção A — Voltar só o código (rápido, quase sempre suficiente)

As tabelas novas ficam no banco sem incomodar ninguém: o sistema antigo não
as conhece.

```bash
# Na sua máquina
git revert -m 1 <hash-do-merge>
git push origin main          # dispara um novo deploy com o código anterior
```

### Opção B — Desfazer também as tabelas do financeiro

```bash
ssh <seu-usuario>@<ip-do-vps>
cd /var/www/docker-instances/Rebanho

# Desfaz o backfill (apaga só as vendas com origin='BACKFILL')
# e em seguida as tabelas do app
docker compose --env-file .env.prod run --rm web python manage.py migrate finance zero
```

A migração de backfill tem `reverse` implementado: ela apaga apenas as vendas
que ela mesma criou, e **nunca toca num `AnimalMovement`**. O ledger de estoque
fica intacto.

### Opção C — Restaurar o backup (último recurso)

Só se o banco realmente ficou inconsistente. Perde o que foi cadastrado depois
do dump.

```bash
docker compose --env-file .env.prod stop web celery

PGPASSWORD="$DB_PASSWORD" dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
PGPASSWORD="$DB_PASSWORD" createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
PGPASSWORD="$DB_PASSWORD" pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
  -d "$DB_NAME" --no-owner --no-privileges "$BACKUP"

docker compose --env-file .env.prod start web celery
```

---

## Depois que estabilizar

O backfill deixou muitas vendas **sem valor** (as que foram cadastradas sem
preço). Elas aparecem na lista de vendas marcadas como "sem valor" e não entram
no saldo de ninguém.

Para completá-las aos poucos: **Ocorrências → Venda**, marque o filtro
*"Somente vendas sem valor informado"*, e edite as que valem a pena. Ao salvar
com preço, a dívida entra no saldo do cliente automaticamente.
