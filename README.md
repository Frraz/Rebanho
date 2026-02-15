# 🐄 Sistema de Gestão de Rebanhos

> Sistema profissional de controle de rebanhos bovinos com rastreabilidade completa, integridade de estoque garantida e relatórios gerenciais avançados.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-4.2-092E20?style=flat&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-336791?style=flat&logo=postgresql&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.x-06B6D4?style=flat&logo=tailwindcss&logoColor=white)
![Alpine.js](https://img.shields.io/badge/Alpine.js-3.x-8BC0D0?style=flat&logo=alpinedotjs&logoColor=white)
![HTMX](https://img.shields.io/badge/HTMX-1.9-3D72D7?style=flat)

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Funcionalidades](#-funcionalidades)
- [Arquitetura](#-arquitetura)
- [Stack Tecnológica](#-stack-tecnológica)
- [Instalação](#-instalação)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Regras de Negócio](#-regras-de-negócio)
- [Módulos do Sistema](#-módulos-do-sistema)
- [Segurança](#-segurança)
- [Testes](#-testes)
- [Roadmap](#-roadmap)

---

## 🎯 Visão Geral

O sistema foi projetado para fazendas que necessitam de **controle rigoroso de rebanho** com rastreabilidade completa de cada animal, desde o nascimento até a saída (venda, abate, morte ou doação).

A arquitetura garante que o **saldo de animais nunca fique negativo**, todas as operações são **atômicas e auditáveis**, e os relatórios podem ser gerados tanto a partir do estado atual quanto **recalculados pelo histórico completo de movimentações**.

### Diferenciais Técnicos

- **Ledger Pattern**: Cada movimentação é um registro imutável — nunca deletado ou alterado
- **Snapshot + Ledger**: Saldo atual em cache para performance, recalculável do zero a qualquer momento
- **Operações Compostas Atômicas**: Manejo e mudança de categoria executam múltiplas escritas em uma única transação
- **Dashboard Dual**: Interface minimalista com toggle para painel completo de métricas e gráficos

---

## ✨ Funcionalidades

### Dashboard
- **Modo Simples**: Boas-vindas, 4 cards de KPIs e atalhos de ação rápida
- **Modo Métricas** (toggle): Painel completo com gráficos interativos, tabela de movimentações recentes e indicadores avançados
- Estado persistido via `localStorage` — sistema lembra o último modo escolhido

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
| **Abate** | Peso, observações |
| **Venda** | Cliente, peso, preço |
| **Doação** | Cliente/donatário, peso |

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
- **Por Fazenda**: Estoque inicial → Ocorrências → Movimentações → Consolidado → Estoque final → Detalhamentos (mortes, vendas, abates, doações)
- **Fazendas Reunidas**: Consolidação de todas as fazendas com breakdown individual
- Filtros por mês, ano e categoria de animal
- Layout fiel ao modelo Excel do processo atual do cliente
- URLs com parâmetros GET — bookmarkáveis e compartilháveis
- Impressão otimizada (landscape, 9pt)

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
                     │ atualiza (via service/signal)
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

---

## 🛠️ Stack Tecnológica

### Backend
- **Django 4.2** — Framework principal
- **PostgreSQL 14+** — Banco de dados com constraints críticos de integridade
- **Redis** — Cache e broker de filas
- **Celery** — Tarefas assíncronas
- **django-extensions** — Ferramentas de desenvolvimento

### Frontend
- **TailwindCSS 3** (CDN) — Estilização utilitária
- **Alpine.js 3** — Reatividade local (dropdowns, modais, dashboard toggle, auto-dismiss)
- **HTMX 1.9** — Interações server-side sem SPA pesada
- **Chart.js 4** — Gráficos interativos no painel de métricas

### Qualidade e Performance
- UUID como primary key em todas as entidades
- Índices otimizados no banco de dados
- `select_related` / `prefetch_related` estratégicos
- `timezone.make_aware` em todos os datetimes (suporte a fuso horário)

---

## 🚀 Instalação

### Pré-requisitos

- Python 3.10+
- PostgreSQL 14+
- Redis 7+

### Passo a Passo

**1. Clone o repositório**
```bash
git clone <repository-url>
cd rebanho
```

**2. Crie e ative o ambiente virtual**
```bash
python -m venv venv
source venv/bin/activate       # Linux/Mac
venv\Scripts\activate          # Windows
```

**3. Instale as dependências**
```bash
pip install -r requirements.txt
```

**4. Configure as variáveis de ambiente**
```bash
cp .env.example .env
# Edite o .env com suas configurações
```

Exemplo de `.env`:
```env
SECRET_KEY=sua-chave-secreta-aqui
DEBUG=True
DATABASE_URL=postgres://usuario:senha@localhost:5432/rebanho_db
REDIS_URL=redis://localhost:6379/0
ALLOWED_HOSTS=localhost,127.0.0.1
TIME_ZONE=America/Sao_Paulo
```

**5. Crie o banco e execute as migrations**
```bash
createdb rebanho_db
python manage.py makemigrations
python manage.py migrate
```

**6. Crie um superusuário**
```bash
python manage.py createsuperuser
```

**7. Colete os arquivos estáticos**
```bash
python manage.py collectstatic --no-input
```

**8. Inicie o servidor**
```bash
python manage.py runserver
```

Acesse: [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/)

**9. (Opcional) Celery e Redis**
```bash
# Terminal 2
redis-server

# Terminal 3
celery -A config worker -l info

# Terminal 4
celery -A config beat -l info
```

---

## 📁 Estrutura do Projeto

```
rebanho/
│
├── config/                         # Configurações Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── core/                           # App central
│   ├── views.py                    # Dashboard (simples + métricas)
│   ├── urls.py
│   └── templates/
│       ├── core/dashboard.html
│       └── registration/login.html
│
├── farms/                          # Bounded Context: Fazendas
│   ├── models.py
│   ├── views.py
│   └── templates/farms/
│
├── inventory/                      # Bounded Context: Inventário (CORE DOMAIN)
│   ├── domain/
│   │   └── value_objects.py        # OperationType, MovementType (Enums)
│   ├── models/
│   │   ├── animal_category.py      # Tipos de animal
│   │   ├── stock_balance.py        # FarmStockBalance (snapshot)
│   │   ├── animal_movement.py      # AnimalMovement (ledger)
│   │   └── __init__.py
│   ├── services/
│   │   ├── movement_service.py     # Entradas/saídas simples
│   │   ├── transfer_service.py     # Manejo e mudança de categoria
│   │   └── stock_query_service.py  # Queries de saldo
│   └── signals.py                  # Auto-criação de saldos
│
├── operations/                     # Bounded Context: Operações
│   ├── views/
│   │   ├── ocorrencias.py
│   │   └── movimentacoes.py
│   └── templates/operations/
│
├── reporting/                      # Bounded Context: Relatórios
│   ├── services/
│   │   ├── farm_report_service.py
│   │   └── consolidated_report_service.py
│   ├── views.py
│   ├── urls.py
│   ├── templatetags/
│   │   └── report_tags.py          # Filtros: get_item, sum_values
│   └── templates/reporting/
│       ├── farm_report.html
│       └── consolidated_report.html
│
├── templates/                      # Templates globais
│   ├── base/
│   │   └── base.html               # Layout principal
│   └── shared/
│       ├── pagination.html
│       ├── search_bar.html
│       └── confirm_modal.html
│
├── static/
│   └── js/
│       └── masks.js                # Máscaras: CPF/CNPJ, telefone, peso
│
├── manage.py
├── requirements.txt
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
Model Constraints         ← Django model validation
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

Os relatórios **nunca confiam apenas no snapshot** — calculam dinamicamente pelo ledger:

```
Estoque Inicial = Σ(ENTRADAS até o dia anterior ao período)
               − Σ(SAÍDAS até o dia anterior ao período)

Estoque Final   = Estoque Inicial
               + Σ(ENTRADAS no período selecionado)
               − Σ(SAÍDAS no período selecionado)
```

---

## 📦 Módulos do Sistema

### Dashboard Dual

**Modo Simples** (padrão):
- Saudação com nome do usuário e mês atual
- 4 cards: Total de Animais, Fazendas Ativas, Categorias, Movimentos do Mês
- 6 atalhos de ação rápida (Nascimento, Compra, Venda, Manejo, Relatório, Fazendas)
- Botão **"Exibir Métricas"** com animação

**Modo Métricas** (toggle):
- 4 KPI cards com gradiente colorido
- Gráfico de barras horizontais: animais por fazenda
- Gráfico de rosca: distribuição por categoria
- Gráfico de linhas: entradas vs saídas (últimos 7 dias)
- Gráfico de barras: tipos de movimentação no mês
- Tabela das últimas 15 movimentações com status visual
- Botão **"Modo Simples"**

> Estado (simples/métricas) salvo em `localStorage` e restaurado automaticamente.

### Relatório por Fazenda

Estrutura do relatório (fiel ao modelo Excel do cliente):

```
1. Filtros (mês, ano, fazenda, categoria) — ocultos na impressão
2. Estoque Inicial — tabela horizontal por categoria
3. Tabela Principal Unificada:
   ├── Grupo Ocorrências:   Morte | Venda | Abate
   ├── Grupo Movimentações: Nasc. | Desm. | Man.(+) | Man.(-) | M.Cat.(+) | M.Cat.(-) | Compra | Doação
   └── Grupo Consolidado:   Entrada | Saída
4. Estoque Final — tabela horizontal por categoria
5. OBS: Causa das Mortes    (tabela detalhada)
6. OBS: Doações             (tabela detalhada)
7. OBS: Controle de Vendas  (tabela detalhada)
8. OBS: Abates              (tabela detalhada)
```

### Relatório Fazendas Reunidas

Mesmo modelo do relatório por fazenda, consolidando **todas as fazendas**, com seção adicional de **breakdown por fazenda** (acordeão expansível, aberto na impressão).

---

## 🔐 Segurança

| Aspecto | Implementação |
|---------|--------------|
| **CSRF** | Proteção em todos os formulários (inclusive logout via POST) |
| **SQL Injection** | Prevenido pelo Django ORM (queries parametrizadas) |
| **XSS** | Auto-escape em todos os templates Django |
| **Autenticação** | Login próprio em `/login/` — não depende do `/admin/` |
| **Autorização** | `@login_required` em todas as views |
| **Integridade** | `CHECK CONSTRAINT` no banco como última linha de defesa |
| **Concorrência** | Versioning otimista nas operações críticas de estoque |

---

## 🧪 Testes

```bash
# Executar todos os testes
pytest

# Com relatório de cobertura
pytest --cov=. --cov-report=html

# App específico
pytest inventory/tests/
pytest reporting/tests/
```

### Estrutura de Testes Recomendada

```
tests/
├── unit/
│   ├── test_movement_service.py       # Regras de saldo e operações
│   ├── test_transfer_service.py       # Manejo e mudança de categoria
│   └── test_report_service.py         # Cálculos de estoque e relatório
├── integration/
│   ├── test_ocorrencias_flow.py       # Fluxo completo de ocorrências
│   └── test_movimentacoes_flow.py     # Fluxo completo de movimentações
└── conftest.py                        # Fixtures compartilhadas
```

---

## 🗺️ Roadmap

### ✅ Concluído
- [x] Arquitetura Clean Architecture + DDD leve
- [x] Models com UUID, constraints e índices otimizados
- [x] CRUD completo: Fazendas, Categorias, Clientes, Tipos de Morte
- [x] Ocorrências: Morte, Abate, Venda, Doação
- [x] Movimentações: Nascimento, Desmame, Compra, Saldo, Manejo, Mudança de Categoria
- [x] Services com transações atômicas e validação de saldo
- [x] Signals para auto-criação de saldos por categoria
- [x] Relatório por Fazenda (layout Excel fiel ao cliente)
- [x] Relatório Consolidado (Fazendas Reunidas)
- [x] Dashboard dual (simples + métricas com gráficos Chart.js)
- [x] Login/logout próprio (`/login/`)
- [x] Navbar com item ativo destacado por seção
- [x] Mensagens com auto-dismiss e progress bar (Alpine.js)
- [x] Máscaras de input (CPF/CNPJ, telefone, peso)

### 🔄 Em Desenvolvimento
- [ ] Filtros e busca nas listagens (Ocorrências, Movimentações)
- [ ] Paginação nas listagens
- [ ] Modais de confirmação inline (Alpine.js)

### 📋 Planejado
- [ ] Exportação PDF dos relatórios
- [ ] Testes automatizados (pytest)
- [ ] Cache de relatórios via Redis
- [ ] API REST (Django REST Framework)
- [ ] Deploy em produção (Nginx + Gunicorn + Docker)
- [ ] Notificações por e-mail (Celery)

---

*Sistema desenvolvido com foco em integridade de dados, rastreabilidade completa e experiência de usuário fluida — sem SPA pesada.*