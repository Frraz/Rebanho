# Sistema de Gestão de Rebanhos

Sistema profissional de gestão de rebanhos desenvolvido com Django + HTMX + Alpine.js + TailwindCSS.

## 🎯 Características Principais

- **Arquitetura Limpa**: Clean Architecture + DDD leve
- **Alta Performance**: PostgreSQL + Redis + Celery
- **Controle de Estoque Robusto**: Ledger pattern (Event Sourcing parcial)
- **Integridade de Dados**: Transações atômicas + controle de concorrência
- **Interface Moderna**: HTMX para interatividade sem SPA pesada

## 📋 Módulos do Sistema

### 1. Dashboard
- Painel de rebanho com visão geral
- Estatísticas e indicadores

### 2. Cadastros
- **Fazendas**: Gerenciamento de fazendas
- **Tipos de Animal**: Categorias de animais (Bezerro, Vaca, Novilho, etc.)
- **Tipos de Morte**: Causas de morte
- **Clientes**: Cadastro de compradores

### 3. Ocorrências
- **Morte**: Registro de óbitos (com tipo de morte)
- **Abate**: Registro de abates
- **Venda**: Vendas para clientes (com peso)
- **Doação**: Doações de animais

### 4. Movimentações
- **Nascimento**: Entrada por nascimento
- **Desmame**: Entrada por desmame
- **Saldo**: Ajuste de saldo
- **Compra**: Entrada por compra
- **Manejo**: Transferência entre fazendas (operação composta)
- **Mudança de Categoria**: Alteração de categoria (operação composta)

### 5. Relatórios
- **Por Fazenda**: Relatório detalhado de uma fazenda específica
- **Fazendas Reunidas**: Relatório consolidado de todas as fazendas

## 🚀 Instalação

### Pré-requisitos

- Python 3.10+
- PostgreSQL 14+
- Redis 7+

### Passo a Passo

1. **Clone o repositório**
```bash
git clone <repository-url>
cd livestock_management
```

2. **Crie um ambiente virtual**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. **Instale as dependências**
```bash
pip install -r requirements.txt
```

4. **Configure as variáveis de ambiente**
```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

5. **Configure o banco de dados**
```bash
# Crie o banco de dados no PostgreSQL
createdb livestock_db

# Execute as migrations
python manage.py makemigrations
python manage.py migrate
```

6. **Crie um superusuário**
```bash
python manage.py createsuperuser
```

7. **Inicie o servidor de desenvolvimento**
```bash
python manage.py runserver
```

8. **Em outro terminal, inicie o Celery** (opcional)
```bash
celery -A config worker -l info
```

9. **Em outro terminal, inicie o Redis** (opcional)
```bash
redis-server
```

## 📁 Estrutura do Projeto

```
livestock_management/
├── config/              # Configurações do Django
├── core/                # App central (dashboard, auth)
├── farms/               # Bounded Context: Fazendas
├── inventory/           # Bounded Context: Inventário (CORE)
│   ├── domain/          # Lógica de domínio pura
│   ├── models/          # Entidades
│   ├── services/        # Serviços de negócio
│   └── repositories/    # Queries complexas
├── operations/          # Bounded Context: Operações
├── reporting/           # Bounded Context: Relatórios
├── templates/           # Templates globais
├── static/              # Arquivos estáticos
└── manage.py
```

## 🏗️ Arquitetura

### Controle de Estoque (Ledger + Snapshot)

```
┌─────────────────────────────────────┐
│    AnimalMovement (Ledger)          │
│    - Fonte da verdade               │
│    - Imutável                       │
│    - Auditável                      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  FarmStockBalance (Snapshot)        │
│  - Saldo consolidado                │
│  - Cache para performance           │
│  - Recalculável do ledger           │
└─────────────────────────────────────┘
```

### Garantias de Integridade

1. **Ledger Imutável**: AnimalMovement não pode ser alterado/deletado
2. **Constraint no Banco**: `current_quantity >= 0`
3. **Transações Atômicas**: Todas as operações são transacionais
4. **Controle de Concorrência**: Versioning otimista

## 🧪 Testes

```bash
# Executar todos os testes
pytest

# Executar com coverage
pytest --cov=.

# Executar testes de um app específico
pytest inventory/tests/
```

## 📊 Regras de Negócio

### Invariantes Fundamentais

1. **Saldo nunca negativo**: `current_quantity >= 0` (SEMPRE)
2. **Ledger imutável**: Registros nunca são alterados
3. **Operações atômicas**: Rollback em caso de falha
4. **Rastreabilidade completa**: Todo movimento é auditável

### Operações Compostas

- **Manejo**: Remove da fazenda origem + Adiciona na fazenda destino (1 transação)
- **Mudança de Categoria**: Remove da categoria origem + Adiciona na categoria destino (1 transação)

## 🔐 Segurança

- Proteção CSRF em todos os formulários
- SQL Injection: Prevenido pelo Django ORM
- XSS: Templates com auto-escape
- Validações em múltiplas camadas (domain, model, form)

## 📝 Licença

[Definir licença]

## 👥 Contribuindo

[Definir processo de contribuição]

## 📞 Suporte

[Definir canais de suporte]