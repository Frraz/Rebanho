# 🐄 Gestão de Rebanhos

> Sistema profissional de controle de rebanhos bovinos com rastreabilidade completa, integridade de estoque garantida e relatórios gerenciais avançados.

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
- [Arquitetura](#-arquitetura)
- [Stack Tecnológica](#-stack-tecnológica)
- [Instalação Local](#-instalação-local)
- [Deploy em Produção](#-deploy-em-produção)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Regras de Negócio](#-regras-de-negócio)
- [Testes](#-testes)
- [CI/CD](#-cicd)
- [Segurança](#-segurança)

---

## 🎯 Visão Geral

Sistema web para fazendas que necessitam de **controle rigoroso de rebanho** com rastreabilidade completa de cada animal, desde o nascimento até a saída (venda, abate, morte ou doação).

A arquitetura garante que o **saldo de animais nunca fique negativo**, todas as operações são **atômicas e auditáveis**, e os relatórios podem ser gerados tanto a partir do estado atual quanto **recalculados pelo histórico completo de movimentações**.

### Diferenciais Técnicos

- **Ledger Pattern** — cada movimentação é um registro imutável, nunca deletado ou alterado
- **Snapshot + Ledger** — saldo atual em cache para performance, recalculável do zero a qualquer momento
- **Operações Compostas Atômicas** — manejo e mudança de categoria executam múltiplas escritas em uma única transação
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
| **Clientes** | Nome, CPF/CNPJ, telefone e endereço — vinculados a vendas e doações |

### Ocorrências (Saídas de Estoque)

| Tipo | Campos Específicos |
|------|--------------------|
| **Morte** | Tipo de morte obrigatório |
| **Abate** | Peso e observações |
| **Venda** | Cliente, peso e preço |
| **Doação** | Cliente/donatário e peso |

### Movimentações (Entradas e Transferências)

| Tipo | Descrição |
|------|-----------|
| **Nascimento** | Entrada direta por nascimento natural |
| **Desmame** | Transição de bezerros para categoria adulta |
| **Compra** | Entrada de animais adquiridos externamente |
| **Ajuste de Saldo** | Correção de inventário |
| **Manejo** | Transferência entre fazendas (operação atômica composta) |
| **Mudança de Categoria** | Reclassificação do animal (operação atômica composta) |

### Relatórios
- **Por Fazenda** — estoque inicial → ocorrências → movimentações → consolidado → estoque final → detalhamentos (mortes, vendas, abates, doações)
- **Fazendas Reunidas** — consolidação de todas as fazendas com breakdown individual
- Filtros por mês, ano e categoria de animal
- Layout fiel ao modelo Excel do processo atual do cliente
- URLs com parâmetros GET — bookmarkáveis e compartilháveis
- Impressão otimizada (landscape, 9pt)

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
│   MovementService │ TransferService │ ReportService       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                      DOMAIN                              │
│         Value Objects │ Enums │ Domain Rules              │
│      OperationType │ MovementType │ Invariants            │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                  INFRASTRUCTURE                          │
│     Django ORM │ PostgreSQL │ Redis │ Celery              │
│         Models │ Migrations │ Admin                       │
└─────────────────────────────────────────────────────────┘
```

### Padrão Ledger + Snapshot

```
┌──────────────────────────────────────────┐
│         AnimalMovement (Ledger)           │
│                                           │
│  ✓ Fonte absoluta da verdade              │
│  ✓ Imutável (sem UPDATE/DELETE)           │
│  ✓ Auditável com timestamp + usuário      │
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

### Bounded Contexts (DDD)

| Context | Responsabilidade |
|---------|-----------------|
| `farms` | Fazendas e dados cadastrais |
| `inventory` | Saldo, movimentações e domínio de estoque |
| `operations` | Ocorrências (saídas) e movimentações (entradas/transferências) |
| `reporting` | Geração de relatórios gerenciais |
| `core` | Dashboard, autenticação e páginas centrais |

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
| Containerização | Docker + Compose | latest |
| Web Server | Nginx + Gunicorn | 1.24 / 21+ |
| SSL | Let's Encrypt (certbot) | — |
| Frontend | TailwindCSS (CDN) | 3.x |
| Reatividade | Alpine.js | 3.x |
| Interação Server | HTMX | 1.9 |
| Gráficos | Chart.js | 4.4 |
| CI/CD | GitHub Actions | — |

---

## 🚀 Instalação Local

### Pré-requisitos

- Python 3.12+
- PostgreSQL 14+
- Redis 7+

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

# 7. Coletar arquivos estáticos
python manage.py collectstatic --noinput

# 8. Iniciar servidor
python manage.py runserver
```

Acesse: [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/)

```bash
# Celery (terminal separado — opcional para desenvolvimento)
celery -A config worker -l info
```

---

## 🖥️ Deploy em Produção

O projeto possui um manual completo de deploy disponível em [`DEPLOY.md`](./DEPLOY.md), cobrindo do zero ao sistema online em uma VPS Ubuntu zerada.

### Resumo da infraestrutura

- **VPS** — Ubuntu 22.04 LTS
- **Containerização** — Docker Compose (app + celery + redis)
- **Banco** — PostgreSQL instalado no host (fora do Docker)
- **Web Server** — Nginx como proxy reverso
- **SSL** — Let's Encrypt com renovação automática
- **CI/CD** — GitHub Actions com deploy automático a cada push na `main`

```bash
# Deploy manual (primeira vez na VPS)
git clone https://github.com/Frraz/Rebanho /var/www/docker-instances/Rebanho
cd /var/www/docker-instances/Rebanho
cp .env.example .env.prod      # preencher com valores de produção
docker compose build
docker compose up -d
docker compose exec web python manage.py createsuperuser
```

Consulte [`DEPLOY.md`](./DEPLOY.md) para o passo a passo completo incluindo PostgreSQL, Nginx e SSL.

---

## 📁 Estrutura do Projeto

```
rebanho/
│
├── .github/
│   └── workflows/
│       └── deploy.yml              # CI/CD — deploy automático
│
├── config/                         # Configurações Django
│   ├── settings.py
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
│
├── core/                           # App central
│   ├── views.py                    # Dashboard (simples + métricas)
│   ├── views_audit.py              # Auditoria de ações
│   ├── emails.py                   # Envio de e-mails (aprovação, rejeição)
│   └── templates/
│       ├── core/dashboard.html
│       └── registration/login.html
│
├── farms/                          # Bounded Context: Fazendas
│   ├── models/farm.py
│   ├── signals.py                  # Auto-cria saldos em nova fazenda
│   └── views.py
│
├── inventory/                      # Bounded Context: Inventário (CORE DOMAIN)
│   ├── domain/
│   │   ├── value_objects.py        # OperationType, MovementType (Enums)
│   │   ├── validators.py
│   │   └── exceptions.py
│   ├── models/
│   │   ├── animal_category.py      # Tipos de animal
│   │   ├── stock_balance.py        # FarmStockBalance (snapshot)
│   │   └── animal_movement.py      # AnimalMovement (ledger)
│   ├── services/
│   │   ├── movement_service.py
│   │   ├── reconciliation_service.py
│   │   └── stock_query_service.py
│   ├── repositories/
│   │   └── stock_repository.py
│   └── signals.py                  # Auto-criação de saldos por categoria
│
├── operations/                     # Bounded Context: Operações
│   ├── services/
│   │   ├── occurrence_service.py   # Mortes, abates, vendas, doações
│   │   └── transfer_service.py     # Manejo e mudança de categoria
│   └── views/
│       ├── ocorrencias.py
│       └── cadastros.py
│
├── reporting/                      # Bounded Context: Relatórios
│   ├── queries/report_queries.py   # Queries otimizadas
│   ├── services/
│   │   ├── farm_report_service.py
│   │   └── consolidated_report_service.py
│   └── templatetags/report_tags.py
│
├── templates/                      # Templates globais
│   ├── base/base.html              # Layout principal (navbar, footer)
│   └── shared/                     # Componentes reutilizáveis
│
├── static/
│   └── js/masks.js                 # Máscaras: CPF/CNPJ, telefone, peso
│
├── scripts/
│   └── deploy_prod.sh              # Script de deploy executado pelo CI/CD
│
├── tests/
│   ├── conftest.py
│   ├── test_movement_service.py
│   ├── test_atomic_operations.py
│   ├── test_stock_integrity.py
│   ├── test_ledger_immutability.py
│   ├── test_approval_flow.py
│   └── test_report_stock.py
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── manage.py
├── DEPLOY.md                       # Manual completo de deploy
└── .env.example
```

---

## 📊 Regras de Negócio

### Invariantes Fundamentais

| # | Regra | Implementação |
|---|-------|---------------|
| 1 | Saldo nunca negativo | `CHECK CONSTRAINT current_quantity >= 0` no banco + validação no service |
| 2 | Ledger imutável | `AnimalMovement` sem métodos de update/delete |
| 3 | Operações atômicas | `@transaction.atomic` em todos os services |
| 4 | Rastreabilidade total | `timestamp`, `created_by`, `operation_type`, `metadata` em todo movimento |
| 5 | Consistência de categorias | Signal cria saldo zerado para novas categorias em todas as fazendas automaticamente |

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

**Mudança de Categoria**:
```
BEGIN TRANSACTION
  1. Verifica saldo da categoria ORIGEM na fazenda
  2. Cria AnimalMovement MUDANCA_CATEGORIA_OUT
  3. Atualiza FarmStockBalance (categoria origem -N)
  4. Cria AnimalMovement MUDANCA_CATEGORIA_IN
  5. Atualiza FarmStockBalance (categoria destino +N)
COMMIT — ou ROLLBACK completo se qualquer passo falhar
```

### Cálculo de Estoque nos Relatórios

```
Estoque Inicial = Σ(ENTRADAS até o dia anterior ao período)
               − Σ(SAÍDAS até o dia anterior ao período)

Estoque Final   = Estoque Inicial
               + Σ(ENTRADAS no período selecionado)
               − Σ(SAÍDAS no período selecionado)
```

> Os relatórios **nunca confiam apenas no snapshot** — calculam dinamicamente pelo ledger, garantindo consistência mesmo que o snapshot esteja desatualizado.

---

## 🧪 Testes

```bash
# Executar todos os testes
pytest

# Com relatório de cobertura
pytest --cov=. --cov-report=html

# Suite específica
pytest tests/test_movement_service.py -v
pytest tests/test_stock_integrity.py -v
```

| Suite | O que testa |
|-------|-------------|
| `test_movement_service` | Regras de saldo, entradas e saídas |
| `test_atomic_operations` | Transações compostas (manejo, mudança de categoria) |
| `test_stock_integrity` | Invariante de saldo não-negativo |
| `test_ledger_immutability` | Imutabilidade dos registros do ledger |
| `test_approval_flow` | Fluxo de aprovação de novos usuários |
| `test_report_stock` | Cálculos de estoque inicial e final nos relatórios |

---

## ⚙️ CI/CD

Deploy **totalmente automatizado** via GitHub Actions. A cada push na branch `main`:

```
push → main
   │
   ▼
GitHub Actions (ubuntu-latest)
   │
   ├─ SSH na VPS
   ├─ git reset --hard origin/main
   ├─ docker compose build web
   ├─ docker compose up -d --no-deps web
   ├─ Health check com retry (HTTP 200 em /login/)
   ├─ docker compose restart celery
   └─ ✅ Deploy concluído
```

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