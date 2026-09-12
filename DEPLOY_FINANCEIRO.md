# Runbook — Subir o módulo financeiro para produção

Esta release é diferente das anteriores por um motivo: **inclui uma migração que
reescreve dados históricos** — importa todas as vendas já cadastradas para o novo
módulo financeiro. O `atualizacao.sh` já faz backup antes de migrar e só troca a
versão no ar se tudo passar; este guia cobre o que fazer antes, durante e depois.

---

## 1. Primeira vez: trazer o próprio script

O `atualizacao.sh` chega junto com o código. Na primeira vez ele ainda não existe
no servidor, então o primeiro pull é manual:

```bash
ssh deploy@<ip-do-vps>
cd ~/Rebanho

git status                 # precisa estar limpo
git pull --ff-only origin main
chmod +x atualizacao.sh
```

Ainda **não** rode o script — primeiro, o ensaio da seção 2.

---

## 2. Opcional, mas recomendado: ensaiar num clone do banco

O script protege o banco com backup, mas o backfill nunca rodou contra os seus
dados reais. Ensaiar num clone mostra os números antes de eles valerem.

```bash
cd ~/Rebanho
# Troque pelos valores do .env.prod
export PGPASSWORD='<DB_PASSWORD>'
H=127.0.0.1; P=<DB_PORT>; U=<DB_USER>; DB=<DB_NAME>

pg_dump -h $H -p $P -U $U -Fc -f /tmp/ensaio.dump $DB
createdb -h $H -p $P -U $U livestock_ensaio
pg_restore -h $H -p $P -U $U -d livestock_ensaio --no-owner /tmp/ensaio.dump

docker compose --env-file .env.prod build web
docker compose --env-file .env.prod run --rm --no-deps -e DB_NAME=livestock_ensaio \
  web python manage.py migrate
docker compose --env-file .env.prod run --rm --no-deps -e DB_NAME=livestock_ensaio \
  web python manage.py verificar_financeiro

dropdb -h $H -p $P -U $U livestock_ensaio && rm /tmp/ensaio.dump
```

Se os números da seção 3 fizerem sentido, siga para a atualização de verdade.

---

## 2.1 Atualizar

Como o `git pull` da seção 1 já trouxe o código, o script acharia que não há nada
novo. Por isso, **só nesta primeira vez**, use `--forcar`:

```bash
./atualizacao.sh --forcar
```

Ele vai detectar as migrações do financeiro, fazer e validar o backup, migrar e
só então colocar a versão nova no ar. Nas próximas atualizações, basta
`./atualizacao.sh`.

> Se o seu `pg_dump` for mais antigo que o servidor PostgreSQL, rode os comandos
> via `docker run --rm --network host -e PGPASSWORD postgres:17-alpine ...`.

---

## 3. O que ler na saída do backfill

Durante a etapa `[6/9]`, a migração imprime um resumo assim:

```
[BACKFILL FINANCEIRO] Vendas importadas: 412 | com valor (viraram dívida): 180 |
sem valor (a completar): 232 | canceladas (sem efeito no saldo): 0 |
preço ilegível: 0 | sem cliente (ignoradas): 0 | já importadas antes: 0
```

| Número | Quando se preocupar |
|--------|---------------------|
| **Vendas importadas** | Se for 0 ou muito menor que o total de vendas do sistema |
| **sem valor** | Esperado ser alto — são as vendas antigas cadastradas sem preço |
| **preço ilegível** | Se for maior que 0, investigue antes de seguir usando |
| **sem cliente** | Se for maior que 0, os IDs aparecem logo abaixo no log |

Ao final, o script roda `verificar_financeiro` sozinho. O esperado é
**"Tudo certo. Nenhuma inconsistência encontrada."**

---

## 4. Conferir o sistema no ar

Antes de atualizar, anote os números de um **Relatório por Fazenda** de um mês
passado. Depois, em https://rebanho.ferzion.com.br:

- [ ] **Ocorrências → Venda** abre a lista, com o histórico importado
- [ ] Uma venda antiga que tinha preço aparece com o valor certo
- [ ] **Relatórios → Saldos dos Clientes** mostra as dívidas importadas
- [ ] **Relatórios → Fluxo Financeiro** abre no mês atual
- [ ] **Ocorrências → Pagamentos** abre, e o cadastro funciona
- [ ] O **Relatório por Fazenda** anotado continua com os mesmos números
- [ ] A **Ficha de Controle Manual** continua gerando o PDF

Teste de ponta a ponta, com um cliente de teste:

1. Venda com 2 lotes do mesmo tipo de animal → confira a baixa no estoque
2. O cliente fica negativo em Saldos
3. Pagamento maior que a dívida → o saldo vira positivo
4. Apague a venda → animais voltam ao estoque, débito some
5. A venda apagada aparece em **Auditoria → Ver registros financeiros apagados**

---

## 5. Se der errado

| Situação | O que o script já fez | O que fazer |
|----------|----------------------|-------------|
| Falhou nas etapas 1 a 7 | Devolveu o código; o sistema antigo nunca saiu do ar | Ler o log, corrigir, rodar de novo |
| Falhou no health check, **sem** migração | Voltou sozinho para a versão anterior | Ler o log, corrigir, rodar de novo |
| Falhou no health check, **com** migração | Nada — de propósito | Ver abaixo |

As migrações do financeiro **só criam tabelas novas** — nenhuma tabela existente
foi alterada. Por isso, nesta release, voltar o código é seguro:

```bash
./atualizacao.sh --voltar
```

Para desfazer também as tabelas e o backfill (apaga só as vendas que a migração
criou, nunca um `AnimalMovement`):

```bash
docker compose --env-file .env.prod run --rm --no-deps web python manage.py migrate finance zero
```

Último recurso, restaurar o backup (perde o que foi cadastrado depois dele) — o
caminho do arquivo aparece no final da execução e em
`~/backups/rebanho/historico_atualizacoes.log`. Veja a seção
*Restaurar um backup* no README.

---

## Depois que estabilizar

O backfill deixou muitas vendas **sem valor**. Elas não entram no saldo de
ninguém até serem completadas: **Ocorrências → Venda**, marque *"Somente vendas
sem valor informado"*, e edite as que valem a pena. Ao salvar com preço, a dívida
entra no saldo do cliente automaticamente.
