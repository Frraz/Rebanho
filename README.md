# 🐄 Gestão de Rebanhos

> Sistema profissional de controle de rebanhos bovinos com rastreabilidade completa, integridade de estoque garantida, controle financeiro por cliente e relatórios gerenciais avançados.

[![Deploy](https://github.com/Frraz/Rebanho/actions/workflows/deploy.yml/badge.svg)](https://github.com/Frraz/Rebanho/actions/workflows/deploy.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-4.2-092E20?style=flat&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-336791?style=flat&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.x-06B6D4?style=flat&logo=tailwindcss&logoColor=white)
![Alpine.js](https://img.shields.io/badge/Alpine.js-3.x-8BC0D0?style=flat&logo=alpinedotjs&logoColor=white)
![HTMX](https://img.shields.io/badge/HTMX-1.9-3D72D7?style=flat)

**🌐 Produção:** [rebanho.ferzion.com.br](https://rebanho.ferzion.com.br)

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Funcionalidades](#-funcionalidades)
- [Arquitetura](#️-arquitetura)
- [Stack Tecnológica](#️-stack-tecnológica)
- [Instalação Local](#-instalação-local)
- [Deploy em Produção](#️-deploy-em-produção)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Regras de Negócio](#-regras-de-negócio)
- [Comandos de Manutenção](#-comandos-de-manutenção)
- [Testes](#-testes)
- [CI/CD](#️-cicd)
- [Segurança](#-segurança)

---

## 🎯 Visão Geral

Sistema web para fazendas que necessitam de **controle rigoroso de rebanho** com rastreabilidade completa de cada animal, desde o nascimento até a saída (venda, abate, morte ou doação) — e, desde a versão atual, **controle financeiro do que cada cliente deve ou tem de crédito**.

A arquitetura garante que o **saldo de animais nunca fique negativo**, todas as operações são **atômicas e auditáveis**, e os relatórios podem ser gerados tanto a partir do estado atual quanto **recalculados pelo histórico completo de movimentações**.

### Diferenciais Técnicos

- **Ledger Pattern** — cada movimentação de estoque é um registro imutável, nunca deletado ou alterado pelo fluxo normal
- **Snapshot + Ledger** — saldo atual em cache para performance, recalculável do zero a qualquer momento
- **Operações Compostas Atômicas** — manejo e mudança de categoria executam múltiplas escritas em uma única transação
- **Extrato financeiro por cliente** — vendas, pagamentos e ajustes num único ledger, com o saldo calculado por agregação (sem snapshot a divergir)
- **Dashboard Dual** — interface minimalista com toggle para painel completo de métricas e gráficos
- **CI/CD com GitHub Actions** — deploy automático a cada push na branch `main`
- **Fluxo de aprovação** — novos cadastros aguardam aprovação de um administrador antes de acessar o sistema

---

## ✨ Funcionalidades

### Dashboard
- **Modo Simples** — boas-vindas, 4 cards de KPIs e atalhos de ação rápida
- **Modo Métricas** (toggle) — painel completo com gráficos interativos, tabela de movimentações recentes e indicadores avançados
- Estado persistido via `localStorage` — sistema lembra o último modo escolhido pelo usuário

### Cadastros

| Módulo | Funcionalidades |
|--------|----------------|
| **Fazendas** | CRUD completo, saldo por categoria sempre visível (mesmo zerado) |
| **Tipos de Animal** | Categorias dinâmicas — novas categorias refletem em todas as fazendas automaticamente via signal |
| **Tipos de Morte** | Lista de motivos para registro de óbitos |
| **Clientes** | Nome, CPF/CNPJ, telefone e endereço — com o **saldo atual** visível na listagem |

### Vendas

Tela própria, com lista das últimas vendas e formulário de **múltiplos lotes**.

| Recurso | Descrição |
|---------|-----------|
| **Vários tipos por venda** | Uma venda pode conter N lotes de animais; o mesmo tipo pode repetir em lotes diferentes, com preços por quilo distintos |
| **Cálculo automático** | `Peso × Preço/kg → Total` calculado ao vivo, mas o Total é **editável** para arredondamentos e valores combinados |
| **Aviso de estoque** | A tela soma as quantidades da mesma categoria e avisa antes de enviar; o servidor é quem recusa de fato, com o saldo travado |
| **Edição e exclusão** | Ambas completas e atômicas — apagar devolve os animais ao estoque e retira o valor do saldo do cliente |
| **Filtros e exportação** | Busca livre, cliente, fazenda, tipo de animal, período (início e fim), situação e "somente sem valor"; imprimir e exportar PDF respeitando os filtros |

### Ocorrências (Saídas de Estoque)

| Tipo | Campos Específicos |
|------|--------------------|
| **Morte** | Tipo de morte obrigatório |
| **Abate** | Peso e observações |
| **Doação** | Cliente/donatário e peso |
| **Pagamentos** | Data, cliente (com busca instantânea), valor, tipo e descrição |

> **Venda** tem tela própria (acima). Editar ou cancelar uma venda pela tela de Ocorrências redireciona para lá — mexer por ali alteraria o estoque e deixaria o saldo do cliente com o valor antigo.

### Movimentações (Entradas e Transferências)

| Tipo | Descrição |
|------|-----------|
| **Nascimento** | Entrada direta por nascimento natural |
| **Desmame** | Transição de bezerros para categoria adulta |
| **Compra** | Entrada de animais adquiridos externamente |
| **Ajuste de Saldo** | Correção de inventário |
| **Manejo** | Transferência entre fazendas (operação atômica composta) |
| **Mudança de Categoria** | Reclassificação do animal (operação atômica composta) |

### Financeiro

| Recurso | Descrição |
|---------|-----------|
| **Saldo do cliente** | Negativo = deve · Zero = quitado · Positivo = tem crédito a favor |
| **Pagamentos** | Podem exceder a dívida ou existir sem dívida nenhuma — o crédito é abatido nas compras seguintes |
| **Ajuste manual** | Crédito ou débito avulso (perdão de dívida, correção de lançamento antigo, acerto fora do sistema), com motivo obrigatório |
| **Histórico de exclusões** | Retrato completo de tudo que for apagado — quem, quando e o que havia ali |

### Relatórios

| Relatório | Conteúdo |
|-----------|----------|
| **Por Fazenda** | Estoque inicial → ocorrências → movimentações → consolidado → estoque final → detalhamentos |
| **Fazendas Reunidas** | Consolidação de todas as fazendas com breakdown individual |
| **Ficha de Controle Manual** | PDF para preenchimento à mão no campo |
| **Fluxo Financeiro** | Todas as movimentações de crédito e débito, abrindo no mês atual. Filtros: período (início e fim), cliente, tipo de animal, fazenda, crédito/débito e origem. Mostra saldo acumulado quando há um cliente filtrado |
| **Saldos dos Clientes** | Um cliente por linha — total comprado, total pago e saldo. Filtro por tipo de saldo |

Todos com **imprimir** (layout otimizado) e **exportar PDF** respeitando os filtros da tela. URLs com parâmetros GET — bookmarkáveis e compartilháveis.

### Autenticação e Acesso
- Login próprio em `/login/` — independente do `/admin/`
- Cadastro de novos usuários com **fluxo de aprovação** por administrador
- Recuperação de senha por e-mail
- Auditoria de ações por usuário (visível apenas para staff)

---

## 🏗️ Arquitetura

### Clean Architecture + DDD Leve

```
┌─────────────────────────────────────────────────────────┐
│                    PRESENTATION                          │
│         Django Templates + HTMX + Alpine.js              │
│              (Views, Forms, URLs)                        │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                    APPLICATION                           │
│               Services (Regras de Negócio)               │
│  MovementService │ TransferService │ SaleService         │
│  PaymentService  │ BalanceService  │ ReportServices      │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                      DOMAIN                              │
│         Value Objects │ Enums │ Domain Rules              │
│      OperationType │ MovementType │ EntryType             │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                  INFRASTRUCTURE                          │
│     Django ORM │ PostgreSQL │ Redis │ Celery              │
│         Models │ Migrations │ Admin                       │
└─────────────────────────────────────────────────────────┘
```

### Padrão Ledger + Snapshot (Estoque)

```
┌──────────────────────────────────────────┐
│         AnimalMovement (Ledger)           │
│                                           │
│  ✓ Fonte absoluta da verdade              │
│  ✓ Imutável no fluxo normal               │
│  ✓ Auditável com data + usuário           │
│  ✓ Metadados JSON por tipo de operação    │
└────────────────────┬─────────────────────┘
                     │ atualiza via service
                     ▼
┌──────────────────────────────────────────┐
│       FarmStockBalance (Snapshot)         │
│                                           │
│  ✓ Saldo atual em cache                   │
│  ✓ Alta performance para leitura          │
│  ✓ Recalculável do ledger a qualquer hora │
│  ✓ CONSTRAINT: current_quantity >= 0      │
└──────────────────────────────────────────┘
```

### Extrato Financeiro (sem snapshot, por decisão)

```
   Venda            Pagamento          Ajuste manual
     │                  │                    │
     │ débito           │ crédito            │ débito ou crédito
     ▼                  ▼                    ▼
┌──────────────────────────────────────────────────────┐
│              FinancialEntry (extrato)                 │
│                                                       │
│  ✓ Origem declarada e coerente (CHECK CONSTRAINT)     │
│  ✓ Valor sempre positivo — o sinal vem da natureza    │
└────────────────────────┬─────────────────────────────┘
                         │ agregação em tempo real
                         ▼
              saldo = Σ créditos − Σ débitos
```

> **Por que não há tabela de saldo do cliente.** Vendas e pagamentos podem ser
> editados e apagados. Um saldo materializado divergiria em silêncio a cada
> edição — o mesmo problema que já obriga o estoque a manter um script de
> reconciliação. Com agregação, o saldo é correto por construção, e os índices
> em `(client, date)` e `(client, entry_type)` mantêm o custo irrelevante no
> volume deste sistema.

### Uma venda, dois mundos

Cada lote de uma venda gera a sua própria baixa no ledger de estoque, e a venda
inteira gera **um** lançamento no extrato do cliente:

```
          Sale (cabeçalho: cliente, fazenda, data)
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
    SaleItem         SaleItem         SaleItem
   (12 bezerros)   (5 novilhas)    (8 bezerros)
        │                │                │
        ▼                ▼                ▼
  AnimalMovement   AnimalMovement   AnimalMovement    ← baixa de estoque
        └────────────────┴────────────────┘
                         │
                         ▼
              FinancialEntry (1 débito)               ← dívida do cliente
```

O `metadata` de cada `AnimalMovement` continua recebendo `peso` e `preco_total`
como texto — é o que mantém o Relatório por Fazenda, o PDF de ocorrências e a
tela de auditoria funcionando sem nenhuma alteração.

### Bounded Contexts (DDD)

| Context | Responsabilidade |
|---------|-----------------|
| `farms` | Fazendas e dados cadastrais |
| `inventory` | Saldo, movimentações e domínio de estoque |
| `operations` | Ocorrências (saídas), cadastros de clientes e tipos de morte |
| `finance` | Vendas, pagamentos, extrato e saldo dos clientes |
| `reporting` | Relatórios gerenciais de estoque |
| `core` | Dashboard, autenticação e auditoria |

### Infraestrutura de Produção

```
Internet (HTTPS 443)
       │
┌──────▼──────────────────────────────────┐
│  Nginx — proxy reverso + SSL             │
│  Let's Encrypt (renovação automática)    │
│  Serve /static/ e /media/ direto         │
└──────┬──────────────────────────────────┘
       │ proxy_pass 127.0.0.1:8080
┌──────▼──────────────────────────────────┐
│  Docker: rebanho_web                     │
│  Django 4.2 + Gunicorn (3 workers)       │
└──────┬──────────────┬────────────────────┘
       │              │
┌──────▼──────┐ ┌─────▼───────────────────┐
│  Redis      │ │  PostgreSQL (host)       │
│  (Docker)   │ │  banco: livestock_db     │
└─────────────┘ └─────────────────────────┘
┌─────────────────────────────────────────┐
│  Docker: rebanho_celery                  │
│  Workers assíncronos (Celery)            │
└─────────────────────────────────────────┘
```

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Versão |
|--------|-----------|--------|
| Backend | Django | 4.2 |
| Linguagem | Python | 3.12 |
| Banco de Dados | PostgreSQL | 14+ |
| Cache / Broker | Redis | 7 |
| Tarefas Assíncronas | Celery | 5.x |
| Histórico de Alterações | django-simple-history | 3.7 |
| PDF (relatórios) | WeasyPrint | 60+ |
| PDF (ocorrências) | ReportLab | 4+ |
| Containerização | Docker + Compose | latest |
| Web Server | Nginx + Gunicorn | 1.24 / 21+ |
| SSL | Let's Encrypt (certbot) | — |
| Frontend | TailwindCSS (CDN) | 3.x |
| Reatividade | Alpine.js | 3.x |
| Interação Server | HTMX | 1.9 |
| Gráficos | Chart.js | 4.4 |
| CI/CD | GitHub Actions | — |

> **Dois geradores de PDF, de propósito.** Os relatórios são HTML → PDF via
> WeasyPrint, o que permite reaproveitar o mesmo layout da tela. O PDF de
> ocorrências é montado programaticamente com ReportLab. Ao mexer em um PDF,
> confira qual dos dois está por trás.

---

## 🚀 Instalação Local

### Pré-requisitos

- Python 3.12+
- PostgreSQL 14+
- Redis 7+
- Dependências de sistema do WeasyPrint (`libpango`, `libcairo`, `libgdk-pixbuf`) — no Ubuntu/Debian: `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0`

### Passo a Passo

```bash
# 1. Clonar o repositório
git clone https://github.com/Frraz/Rebanho
cd Rebanho

# 2. Criar e ativar o ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env com suas configurações locais
```

Conteúdo do `.env` para desenvolvimento:

```env
SECRET_KEY=sua-chave-secreta-local
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=livestock_db
DB_USER=postgres
DB_PASSWORD=sua_senha
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://localhost:6379/1
CELERY_BROKER_URL=redis://localhost:6379/0
TIME_ZONE=America/Sao_Paulo
```

```bash
# 5. Criar banco e aplicar migrations
createdb livestock_db
python manage.py migrate

# 6. Criar superusuário
python manage.py createsuperuser

# 7. Semear as categorias do sistema
python manage.py seed_system_categories

# 8. Coletar arquivos estáticos
python manage.py collectstatic --noinput

# 9. Iniciar servidor
python manage.py runserver
```

Acesse: [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/)

```bash
# Celery (terminal separado — opcional para desenvolvimento)
celery -A config worker -l info
```

---

## 🖥️ Deploy em Produção

O projeto possui um manual completo de deploy em [`deploy_manual.md`](./deploy_manual.md), cobrindo do zero ao sistema online em uma VPS Ubuntu zerada.

### Resumo da infraestrutura

- **VPS** — Ubuntu 22.04 LTS
- **Containerização** — Docker Compose (app + celery + redis)
- **Banco** — PostgreSQL instalado no host (fora do Docker)
- **Web Server** — Nginx como proxy reverso
- **SSL** — Let's Encrypt com renovação automática
- **CI/CD** — GitHub Actions com deploy automático a cada push na `main`

> ⚠️ **`Dockerfile` e `docker-compose.yml` não estão versionados** (ver
> `.gitignore`) — eles vivem apenas no servidor, em
> `/var/www/docker-instances/Rebanho`, junto do `.env.prod`. Um `git clone`
> puro não traz esses arquivos; consulte o manual de deploy para criá-los.

Consulte [`deploy_manual.md`](./deploy_manual.md) para o passo a passo completo incluindo PostgreSQL, Nginx e SSL.

---

## 📁 Estrutura do Projeto

```
rebanho/
│
├── .github/workflows/deploy.yml    # CI/CD — deploy automático
│
├── config/                         # Configurações Django
│   ├── settings.py
│   ├── urls.py
│   └── celery.py
│
├── core/                           # App central
│   ├── views.py                    # Dashboard (simples + métricas)
│   ├── views_audit.py              # Auditoria de ações
│   ├── emails.py                   # E-mails de aprovação/rejeição
│   ├── utils/decimal_utils.py      # Normalização de decimais pt-BR
│   └── templatetags/number_filters.py
│
├── farms/                          # Bounded Context: Fazendas
│   ├── models/farm.py
│   └── signals.py                  # Auto-cria saldos em nova fazenda
│
├── inventory/                      # Bounded Context: Inventário (CORE DOMAIN)
│   ├── domain/
│   │   ├── value_objects.py        # OperationType, MovementType (Enums)
│   │   ├── validators.py
│   │   └── exceptions.py
│   ├── models/
│   │   ├── animal_category.py      # Tipos de animal
│   │   ├── stock_balance.py        # FarmStockBalance (snapshot)
│   │   ├── animal_movement.py      # AnimalMovement (ledger)
│   │   └── animal_movement_cancellation.py
│   ├── services/
│   │   ├── movement_service.py     # Única porta de escrita do ledger
│   │   └── stock_query_service.py
│   └── signals.py                  # Auto-criação de saldos por categoria
│
├── operations/                     # Bounded Context: Operações
│   ├── services/
│   │   ├── occurrence_service.py   # Mortes, abates, doações
│   │   ├── transfer_service.py     # Manejo e mudança de categoria
│   │   └── occurrence_pdf_service.py
│   └── views/{ocorrencias,cadastros}.py
│
├── finance/                        # Bounded Context: Financeiro
│   ├── models/
│   │   ├── sale.py                 # Venda (cabeçalho)
│   │   ├── sale_item.py            # Lote de animais da venda
│   │   ├── payment.py              # Pagamento do cliente
│   │   ├── financial_entry.py      # Extrato (débito/crédito)
│   │   ├── deletion_log.py         # Retrato do que foi apagado
│   │   └── enums.py
│   ├── services/
│   │   ├── sale_service.py         # Estoque + dinheiro, atômico
│   │   ├── payment_service.py      # Pagamentos e ajustes manuais
│   │   └── balance_service.py      # Saldo por agregação
│   ├── utils/money.py              # Leitura de valores do metadata antigo
│   ├── filters.py                  # Período mês/ano início–fim
│   ├── views/                      # vendas, pagamentos, relatórios, htmx
│   ├── management/commands/verificar_financeiro.py
│   └── migrations/
│       ├── 0001_initial.py
│       └── 0002_backfill_vendas_existentes.py
│
├── reporting/                      # Bounded Context: Relatórios de estoque
│   ├── services/{farm,consolidated}_report_service.py
│   └── templates/reporting/        # Telas + templates de PDF
│
├── templates/
│   ├── base/base.html              # Layout principal (navbar, footer)
│   └── shared/                     # Componentes reutilizáveis
│
├── static/js/
│   ├── masks.js                    # Máscaras pt-BR + API RebanhoMasks
│   └── venda_form.js               # Formulário de venda multi-lote
│
├── tests/
│   ├── conftest.py
│   ├── test_movement_service.py
│   ├── test_atomic_operations.py
│   ├── test_stock_integrity.py
│   ├── test_ledger_immutability.py
│   ├── test_approval_flow.py
│   ├── test_report_stock.py
│   ├── test_finance_sale_service.py
│   ├── test_finance_balance.py
│   ├── test_finance_money_parser.py
│   └── test_finance_filters.py
│
├── requirements.txt
├── manage.py
├── reconcile_stock.py              # Reconciliação de saldos pelo ledger
├── deploy_manual.md                # Manual completo de deploy
└── .env.example
```

---

## 📊 Regras de Negócio

### Invariantes Fundamentais

| # | Regra | Implementação |
|---|-------|---------------|
| 1 | Saldo de animais nunca negativo | `CHECK CONSTRAINT current_quantity >= 0` no banco + validação no service |
| 2 | Ledger de estoque imutável no fluxo normal | `AnimalMovement.delete()` levanta erro; edições só via service |
| 3 | Operações atômicas | `transaction.atomic` explícito dentro dos services |
| 4 | Rastreabilidade total | `timestamp`, `created_by`, `operation_type`, `metadata` em todo movimento |
| 5 | Consistência de categorias | Signal cria saldo zerado para novas categorias em todas as fazendas |
| 6 | Valor financeiro sempre positivo | `CHECK CONSTRAINT amount > 0` — quem dá o sinal é a natureza do lançamento |
| 7 | Origem do lançamento coerente | `CHECK CONSTRAINT` garante que venda/pagamento/ajuste batem com a FK preenchida |
| 8 | Nada é apagado sem rastro | Exclusão de venda ou pagamento grava um `FinanceDeletionLog` |

### Fluxo de Validação (Múltiplas Camadas)

```
Requisição HTTP
     │
     ▼
Form/View Validation      ← Validações básicas de formulário
     │
     ▼
Service Layer             ← Regras de negócio (saldo suficiente?)
     │
     ▼
Domain Value Objects      ← Tipos válidos, operações permitidas
     │
     ▼
Database Constraints      ← Última linha de defesa (CHECK constraint)
```

### Por que `transaction.atomic` explícito nos services

O projeto usa `ATOMIC_REQUESTS = True`, mas isso **não basta**: as views capturam
`except Exception` para exibir uma mensagem amigável. Quando a view engole a
exceção, a transação do request segue viva e **comita o que já foi escrito** —
uma venda de 3 lotes que falhasse no terceiro gravaria os dois primeiros.
O bloco `with transaction.atomic()` dentro do service cria um savepoint próprio
que desfaz tudo, mesmo com o erro capturado lá em cima.

### Operações Compostas (Transacionais)

**Manejo** (transferência entre fazendas):
```
BEGIN TRANSACTION
  1. Verifica saldo suficiente na fazenda ORIGEM
  2. Cria AnimalMovement MANEJO_OUT (saída da origem)
  3. Atualiza FarmStockBalance da origem  (-N)
  4. Cria AnimalMovement MANEJO_IN  (entrada no destino)
  5. Atualiza FarmStockBalance do destino (+N)
COMMIT — ou ROLLBACK completo se qualquer passo falhar
```

**Venda com vários lotes**:
```
BEGIN TRANSACTION
  1. Soma as quantidades POR CATEGORIA e confere contra o estoque
     (a mesma categoria pode aparecer em várias linhas — validar
      linha a linha deixaria passar uma venda que no total estoura)
  2. Cria a Sale (cabeçalho)
  3. Para cada lote, em ordem determinística de categoria:
       → execute_saida() com lock no saldo
       → cria o SaleItem vinculado à movimentação
  4. Recalcula os totais da venda
  5. Cria o FinancialEntry de débito (se houver valor)
COMMIT — ou ROLLBACK completo se qualquer passo falhar
```

> A ordem determinística por categoria evita deadlock entre duas vendas
> simultâneas na mesma fazenda.

### Saldo do Cliente

```
saldo = Σ(créditos) − Σ(débitos)

  negativo → o cliente DEVE
  zero     → quitado
  positivo → o cliente tem CRÉDITO a favor (pagou adiantado ou a mais)
```

Um pagamento pode ser maior que a dívida, ou existir sem dívida nenhuma — o
crédito resultante é abatido nas compras seguintes.

### Cálculo de Estoque nos Relatórios

```
Estoque Inicial = Σ(ENTRADAS até o dia anterior ao período)
               − Σ(SAÍDAS até o dia anterior ao período)

Estoque Final   = Estoque Inicial
               + Σ(ENTRADAS no período selecionado)
               − Σ(SAÍDAS no período selecionado)
```

> Os relatórios **nunca confiam apenas no snapshot** — calculam dinamicamente
> pelo ledger, ignorando movimentações estornadas.

### Valores decimais: uma armadilha conhecida

Campos de peso e preço usam `type="text"` com máscara pt-BR, **nunca**
`type="number"` — o navegador descarta a vírgula antes do valor chegar ao Django.

Há duas regras de leitura diferentes, e confundi-las custa caro:

| Origem | Regra | Módulo |
|--------|-------|--------|
| **Digitação do usuário** (`"1.250"`) | O ponto é separador de **milhar** → 1250 | `core/utils/decimal_utils.py` |
| **Gravado no banco** (`"1.250"`, de `str(Decimal)`) | O ponto é separador **decimal** → 1,25 | `finance/utils/money.py` |

Aplicar a primeira regra a um valor da segunda origem infla o número em 1000×.
É exatamente por isso que os dois parsers existem separados.

---

## 🔧 Comandos de Manutenção

```bash
# Semeia as 9 categorias fixas do sistema (touros, vacas, bezerros, ...)
python manage.py seed_system_categories

# Dados de exemplo para desenvolvimento
python manage.py seed

# Confere a integridade do financeiro (somente leitura)
python manage.py verificar_financeiro

# ... e corrige o que for seguro corrigir
python manage.py verificar_financeiro --corrigir

# Limita a verificação a um cliente
python manage.py verificar_financeiro --cliente <uuid>

# Recalcula os saldos de estoque a partir do ledger
python reconcile_stock.py
```

O `verificar_financeiro` confere quatro coisas: se toda venda do ledger tem lote
vinculado, se todo lote aponta para uma movimentação existente, se os totais em
cache batem com a soma dos lotes, e se o extrato bate com as vendas e pagamentos.
**Rode-o depois de cada deploy que toque no financeiro.**

---

## 🧪 Testes

```bash
# Executar todos os testes
pytest

# Com relatório de cobertura
pytest --cov=. --cov-report=html

# Suite específica
pytest tests/test_finance_sale_service.py -v
pytest tests/test_stock_integrity.py -v

# Os testes de valores e período não tocam no banco — rodam em instantes
pytest tests/test_finance_money_parser.py tests/test_finance_filters.py
```

| Suite | O que testa |
|-------|-------------|
| `test_movement_service` | Regras de saldo, entradas e saídas |
| `test_atomic_operations` | Transações compostas (manejo, mudança de categoria) |
| `test_stock_integrity` | Invariante de saldo não-negativo |
| `test_ledger_immutability` | Imutabilidade dos registros do ledger |
| `test_approval_flow` | Fluxo de aprovação de novos usuários |
| `test_report_stock` | Cálculos de estoque inicial e final nos relatórios |
| `test_finance_sale_service` | Venda multi-lote, estoque, edição e exclusão |
| `test_finance_balance` | Pagamentos, ajustes e os quatro estados de saldo |
| `test_finance_money_parser` | Leitura de valores gravados no `metadata` |
| `test_finance_filters` | Intervalo de período (início, fim, invertido, bissexto) |

---

## ⚙️ CI/CD

Deploy **totalmente automatizado** via GitHub Actions. A cada push na branch `main`:

```
push → main
   │
   ▼
GitHub Actions (ubuntu-latest) → SSH na VPS
   │
   ├─ [1/9] git reset --hard origin/main
   ├─ [2/9] Garante diretórios
   ├─ [3/9] Corrige permissões de staticfiles
   ├─ [4/9] docker compose build web
   ├─ [5/9] docker compose up -d --no-deps web
   ├─ [6/9] python manage.py migrate --noinput      ⚠️
   ├─ [7/9] makemigrations --check --dry-run        ⚠️
   ├─ [8/9] collectstatic --noinput
   ├─ [9/9] docker compose restart celery
   ├─ Health check com retry (HTTP 200 em /login/)
   └─ ✅ Deploy concluído
```

> ⚠️ **Dois pontos que exigem atenção antes de dar merge na `main`:**
>
> 1. **As migrações rodam sozinhas** no passo 6, e o pipeline **não faz backup
>    do banco**. Migrações de dados executam em produção no momento do merge —
>    faça `pg_dump` e valide num restore antes.
> 2. **O passo 7 falha o deploy** se houver mudança de model sem migration
>    correspondente. Rode `makemigrations --check --dry-run` localmente antes
>    de subir.

### Secrets necessários (GitHub → Settings → Secrets → Actions)

| Secret | Descrição |
|--------|-----------|
| `VPS_HOST` | IP público da VPS |
| `VPS_USER` | Usuário SSH (ex: `deploy`) |
| `VPS_SSH_PRIVATE_KEY` | Chave privada SSH gerada no servidor |

---

## 🔐 Segurança

| Aspecto | Implementação |
|---------|--------------|
| CSRF | Proteção em todos os formulários, inclusive logout via POST |
| SQL Injection | Prevenido pelo Django ORM (queries parametrizadas) |
| XSS | Auto-escape em todos os templates Django |
| Autenticação | Login próprio em `/login/` — independente do `/admin/` |
| Autorização | `@login_required` em todas as views |
| Aprovação | Novos usuários aguardam aprovação manual de administrador |
| Integridade | `CHECK CONSTRAINT` no banco como última linha de defesa |
| Auditoria | `django-simple-history` em movimentações, vendas e pagamentos |
| Exclusões | Registradas com retrato completo em `FinanceDeletionLog` |
| Admin financeiro | Somente leitura — escrever por ali burlaria os services |
| SSL | HTTPS obrigatório em produção (Let's Encrypt) |
| Proxy | `SECURE_PROXY_SSL_HEADER` configurado para Nginx |

---

## 👨‍💻 Autor

**Warley Ferraz** — Desenvolvedor Full Stack

[![Portfolio](https://img.shields.io/badge/Portfolio-warley.dev.ferzion.com.br-16a34a?style=flat)](https://warley.dev.ferzion.com.br)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-warley--ferraz-0A66C2?style=flat&logo=linkedin)](https://www.linkedin.com/in/warley-ferraz-almeida-280a55185/)
[![GitHub](https://img.shields.io/badge/GitHub-Frraz-181717?style=flat&logo=github)](https://github.com/Frraz)

---

*Sistema desenvolvido com foco em integridade de dados, rastreabilidade completa e experiência de usuário fluida — sem SPA pesada.*
