# 💈 HF Barbearia

Sistema web profissional para gerenciamento de barbearia. Agendamento online, painel administrativo, controle financeiro e muito mais.

## 🎯 Objetivos do Sistema

- Permitir que clientes agendem horários online de forma simples e rápida
- Gerenciar serviços oferecidos pela barbearia (CRUD completo)
- Controlar agendamentos e evitar conflitos de horários
- Gerenciar finanças: status de pagamento, formas de pagamento e totais
- Fornecer dashboard com indicadores do negócio
- Proteger o acesso administrativo com autenticação segura

## 🛠 Tecnologias Utilizadas

| Tecnologia | Versão | Finalidade |
|------------|--------|------------|
| **Python** | 3.13 | Linguagem de programação principal |
| **Flask** | 3.1.3 | Framework web |
| **SQLAlchemy** | 2.0.51 | ORM para banco de dados |
| **SQLite** | — | Banco de dados relacional |
| **Flask-WTF** | 1.3.0 | Proteção CSRF |
| **Flask-Bcrypt** | 1.0.1 | Criptografia de senhas |
| **Bootstrap** | 5.3.3 | Framework CSS |
| **Bootstrap Icons** | 1.11.3 | Ícones |
| **Google Fonts** | — | Fonte Poppins |
| **python-dotenv** | 1.2.2 | Variáveis de ambiente |

## 📁 Arquitetura do Projeto

```
barbearia_hf/
├── app.py                    # Factory: cria e configura a app Flask
├── config.py                 # Configurações centralizadas (SQLite, SECRET_KEY)
├── .env                      # Variáveis de ambiente (NUNCA versionar)
├── .gitignore                # Arquivos ignorados pelo Git
├── requirements.txt          # Dependências do projeto
├── README.md                 # Documentação
│
├── models/                   # Modelos do banco de dados
│   ├── __init__.py           # Inicialização do SQLAlchemy (db)
│   ├── servico.py            # Tabela: servico
│   ├── agendamento.py        # Tabela: agendamento
│   ├── admin.py              # Tabela: admin (autenticação)
│   └── financeiro.py         # Tabela: financeiro
│
├── routes/                   # Rotas da aplicação (Blueprints)
│   ├── __init__.py           # Definição dos Blueprints
│   ├── main.py               # Rotas públicas (/, /agendamento)
│   └── admin.py              # Rotas administrativas (/admin/*)
│
├── services/                 # Lógica de negócio
│   ├── __init__.py
│   └── barbearia_service.py  # Funções de validação, consultas e criação
│
├── static/                   # Arquivos estáticos
│   ├── style.css             # Design system completo
│   └── imagens/              # Imagens do site
│
└── templates/                # Templates HTML (Jinja2)
    ├── index.html            # Página inicial (cliente)
    ├── agendamento.html      # Formulário de agendamento
    ├── confirmacao.html      # Confirmação do agendamento
    ├── admin_base.html       # Layout base do admin (sidebar)
    ├── admin_login.html      # Página de login
    ├── admin_dashboard.html  # Dashboard com indicadores
    ├── admin_agendamentos.html # Listagem de agendamentos
    ├── admin_servicos.html   # CRUD de serviços
    └── admin_financeiro.html # Módulo financeiro
```

## 🗄 Banco de Dados

### Tabelas e Relacionamentos

```
┌───────────────────┐       ┌──────────────────────┐
│     servico       │       │    agendamento       │
├───────────────────┤       ├──────────────────────┤
│ id (PK)           │       │ id (PK)              │
│ nome (unique)     │       │ nome                 │
│ preco             │       │ telefone             │
│ tempo             │       │ data                 │
└───────────────────┘       │ horario              │
                            │ servico              │
┌───────────────────┐       │ criado_em            │
│      admin        │       ├──────────────────────┤
├───────────────────┤       │ id (FK) → financeiro │
│ id (PK)           │       └──────────┬───────────┘
│ usuario (unique)  │                  │
│ senha_hash        │                  │ 1:1
└───────────────────┘       ┌──────────┴───────────┐
                            │    financeiro        │
                            ├──────────────────────┤
                            │ id (PK)              │
                            │ agendamento_id (FK)  │
                            │ valor                │
                            │ status               │
                            │ forma_pagamento      │
                            │ criado_em            │
                            └──────────────────────┘
```

### Relacionamentos

- **Agendamento → Financeiro**: 1 para 1 (cada agendamento gera um registro financeiro)
- **Financeiro.agendamento_id** → Chave estrangeira para `agendamento.id`

## 🔄 Fluxo Completo do Sistema

```
CLIENTE
    │
    ├── Acessa página inicial
    │   ├── Visualiza serviços (cards com preço e duração)
    │   └── Clica em "Agendar"
    │
    ├── Formulário de agendamento
    │   ├── Dados do serviço (readonly)
    │   ├── Nome, telefone, data, horário
    │   └── Envia formulário
    │
    ├── Validação (servidor)
    │   ├── Serviço existe?
    │   ├── Nome preenchido?
    │   ├── Telefone válido? (regex)
    │   ├── Data futura?
    │   ├── Horário permitido?
    │   └── Conflito de horário?
    │
    ├── Banco de Dados
    │   ├── Salva agendamento
    │   └── Cria registro financeiro (status: pendente)
    │
    └── Confirmação
        └── Exibe dados do agendamento

ADMINISTRADOR
    │
    ├── Login (/admin/login)
    │   ├── Usuário + senha
    │   └── Verificação bcrypt
    │
    ├── Dashboard (/admin)
    │   ├── Agendamentos hoje/mês
    │   ├── Serviços cadastrados
    │   ├── Clientes atendidos
    │   ├── Faturamento hoje/mês
    │   └── Últimos agendamentos
    │
    ├── Agendamentos (/admin/agendamentos)
    │   ├── Listar todos
    │   └── Excluir (remove financeiro associado)
    │
    ├── Serviços (/admin/servicos)
    │   ├── Listar
    │   ├── Adicionar
    │   ├── Editar
    │   └── Excluir
    │
    └── Financeiro (/admin/financeiro)
        ├── Totais (dia/mês/ano)
        ├── Listar registros
        └── Atualizar status e forma de pagamento
```

## 🔒 Segurança

- **CSRF Protection**: Todos os formulários possuem token CSRF (Flask-WTF)
- **Hash de Senha**: Senhas armazenadas com bcrypt (nunca em texto puro)
- **Sessão**: Autenticação via sessão Flask com cookies assinados
- **Proteção de Rotas**: Rotas administrativas protegidas por `login_necessario()`
- **Validação de Dados**: Todas as entradas são validadas no servidor

## 🚀 Como Instalar

### Pré-requisitos

- Python 3.10+
- pip (gerenciador de pacotes Python)

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/barbearia_hf.git
cd barbearia_hf

# 2. Crie um ambiente virtual (recomendado)
python -m venv venv

# 3. Ative o ambiente virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Instale as dependências
pip install -r requirements.txt

# 5. Configure o arquivo .env
# Crie um arquivo .env na raiz do projeto com:
# SECRET_KEY=sua-chave-secreta-aqui

# 6. Execute a aplicação
python app.py
```

## ▶️ Como Executar

```bash
python app.py
```

O servidor iniciará em `http://127.0.0.1:5000`

### Acessos

| Página | URL | Descrição |
|--------|-----|-----------|
| Site (cliente) | `http://127.0.0.1:5000` | Agendamento online |
| Admin | `http://127.0.0.1:5000/admin/login` | Painel administrativo |

### Credenciais padrão

| Usuário | Senha |
|---------|-------|
| `admin` | `admin123` |

> ⚠️ **Importante:** Altere a senha padrão em produção!

## 🌐 Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `SECRET_KEY` | Chave secreta para assinar cookies e tokens | `fallback-dev-key` |
| `FLASK_DEBUG` | Modo debug (true/false) | `true` |

## 📦 Dependências

```
bcrypt==5.0.0
Flask==3.1.3
Flask-Bcrypt==1.0.1
Flask-SQLAlchemy==3.1.1
Flask-WTF==1.3.0
python-dotenv==1.2.2
SQLAlchemy==2.0.51
WTForms==3.2.2
```

## ✨ Funcionalidades

### Cliente
- ✅ Página inicial com cards de serviços
- ✅ Formulário de agendamento com validações
- ✅ Prevenção de conflito de horários
- ✅ Confirmação de agendamento
- ✅ Design responsivo (Bootstrap 5)
- ✅ Animações suaves

### Administrador
- ✅ Dashboard com indicadores
- ✅ CRUD de serviços
- ✅ Gerenciamento de agendamentos
- ✅ Módulo financeiro (com status e forma de pagamento)
- ✅ Totais de faturamento (dia/mês/ano)
- ✅ Sidebar com navegação
- ✅ Autenticação segura (bcrypt)
- ✅ Proteção CSRF

### Segurança
- ✅ Senhas criptografadas (bcrypt)
- ✅ Proteção CSRF em todos os formulários
- ✅ Sessão protegida
- ✅ Validação de dados no servidor
- ✅ Tratamento de erros HTTP (404, 500, 400)

## 📋 Próximas Melhorias

### Versão 1.1
- [ ] Relatório de agendamentos por período (data inicial / data final)
- [ ] Gráficos no Dashboard (agendamentos por dia/semana)
- [ ] Exportar relatório financeiro em CSV
- [ ] Cancelamento de agendamento pelo cliente

### Versão 1.2
- [ ] Múltiplos barbeiros/profissionais
- [ ] Notificações por WhatsApp (lembrete de agendamento)
- [ ] Upload de foto de perfil do admin
- [ ] Histórico de agendamentos por cliente

### Versão 2.0
- [ ] Integração com PIX (QR Code)
- [ ] Pagamento online com cartão de crédito
- [ ] Aplicativo mobile (PWA)
- [ ] API REST para integração com outros sistemas
- [ ] Autenticação com Google/WhatsApp
- [ ] Agendamento recorrente (cliente fiel)

## 📜 Changelog

### Etapa 1 — Correções Iniciais
- Validação de rotas e parâmetros
- Proteção CSRF
- Tratamento de erros HTTP
- Flash messages para feedback

### Etapa 2 — Banco de Dados
- Implementação do SQLite com SQLAlchemy
- Modelo Servico com dados iniciais

### Etapa 3 — Agendamentos
- Modelo Agendamento
- Validação de telefone com regex
- Prevenção de conflito de horários
- Salvamento no banco

### Etapa 4 — Painel Administrativo
- CRUD de serviços (criar, editar, excluir)
- Listagem de agendamentos
- Templates administrativos

### Etapa 5 — Autenticação
- Login do administrador com bcrypt
- Proteção de rotas administrativas
- Sessão segura

### Etapa 6 — Arquitetura
- Reorganização em módulos (models, routes, services)
- Implementação de Blueprints
- Factory pattern (create_app)

### Etapa 7 — Revisão
- Correções finais
- .gitignore
- Documentação inicial

### Etapa 8 — Redesign Front-End
- Bootstrap 5 + Bootstrap Icons
- Design system completo (CSS)
- Sidebar no admin
- Animações e responsividade
- Hero section, cards modernos

### Módulo Financeiro
- Modelo Financeiro com relacionamento
- Criação automática ao agendar
- Exclusão em cascata
- Totais por dia/mês/ano
- Status e forma de pagamento

### Auditoria Final
- Revisão completa de todos os arquivos
- Remoção de imports não utilizados
- Correção de imports duplicados
- Debug configurável via variável de ambiente
- Geração de requirements.txt
- Documentação profissional (README.md)

## 👨‍💻 Autor

**HS Tech** — Desenvolvimento de sistemas web

---

© 2026 HF Barbearia. Todos os direitos reservados.