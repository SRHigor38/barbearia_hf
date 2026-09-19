# 💈 HF Barbearia

Sistema web profissional para gerenciamento completo de barbearia: agendamento online, planos mensais, controle financeiro, relatórios e exportação PDF.

> **Auditoria 19/09/2026:** mutações só via POST+CSRF, upload 2MB com magic bytes + erro 413 tratado,
> valor do pagamento validado antes de persistir, exclusão de serviço bloqueada se em uso,
> exclusão de agendamento com plano devolve benefícios. Cálculos financeiros inalterados
> (fonte única `calcular_financeiro()`; planos sempre em REAIS).

---

## ✨ Funcionalidades

### Agendamento online
- Selección de servicio, profesional, fecha y horario
- Prevención de conflictos por profesional (mismo horario permitido para profesionales distintos)
- Respeto a la duración de los servicios
- Horario de funcionamiento validado en el backend (Seg-Sáb 09:00-21:00, Dom 09:00-12:00)
- Agendamiento de múltiples servicios en un único agendamiento (Corte + Barba)

### Planos mensais
- 8 planos pré-definidos (Bronze, Prata, Ouro, VIP, Elite, Basic, Light, Premium)
- Benefícios por servicio (cantidad o ilimitados)
- Dias permitidos por plano
- Validade de 30 días
- Área "Meu Plano" con acceso por teléfono + chave
- Consumo e devolución de benefícios
- Renovación y cancelación

### Profesionales
- Alta/baja (activo/inactivo)
- Histórico preservado
- Fotos con validación de extensión y nombre seguro

### Controle financeiro
- Faturamento bruto (solo pagos confirmados)
- Despesas/gastos manuales con categorías
- Taxas de cartón/maquininha vinculadas al pago
- Lucro líquido automático: Faturamento bruto − Despesas totales
- Formas de pago: Dinheiro, PIX, Cartón
- Filtro por período (hoy, semana, mes, mes pasado, personalizado)
- Relatório financiero y exportación PDF

### Administración
- Login administrativo seguro (bcrypt + CSRF + sesión)
- Dashboard con indicadores
- Gestión de agendamientos, servicios, profesionales, planos
- Configuración de usuario y contraseña del admin

---

## 🛠 Tecnologías Utilizadas

| Tecnología | Finalidad |
|------------|-----------|
| **Python 3.13** | Lenguaje principal (3.13.6 en producción) |
| **Flask 3.1** | Framework web |
| **SQLAlchemy 2.0** | ORM |
| **SQLite** | Banco local (desarrollo) |
| **PostgreSQL** | Banco de producción (via DATABASE_URL) |
| **psycopg2-binary** | Driver PostgreSQL |
| **Flask-WTF** | Protección CSRF |
| **Flask-Bcrypt** | Criptografía de contraseñas |
| **ReportLab** | Generación de PDF |
| **python-dotenv** | Variables de ambiente |
| **Gunicorn** | Servidor WSGI para producción |
| **Bootstrap 5** | Framework CSS |
| **Bootstrap Icons** | Íconos |

---

## 📁 Estructura del Proyecto

```
barbearia_hf/
├── app.py                        # Factory Flask
├── config.py                     # Configuración (DATABASE_URL, SECRET_KEY)
├── requirements.txt              # Dependencias
├── Procfile                      # gunicorn app:app (Render)
├── runtime.txt                   # python-3.13.6
├── render.yaml                   # Deploy Render + PostgreSQL
├── .env.example                  # Plantilla de variables de entorno
│
├── models/                       # Modelos SQLAlchemy
│   ├── admin.py                  # Admin (usuario, senha_hash)
│   ├── agendamento.py            # Agendamiento
│   ├── agendamento_servico.py    # Junction agendamiento ↔ servicios
│   ├── bloqueio.py               # Bloqueo manual de horario
│   ├── cliente.py                # Cliente
│   ├── despesa.py                # Gasto manual
│   ├── financeiro.py             # Movimiento financiero
│   ├── plano.py                  # Plano del cliente
│   ├── plano_beneficio.py        # Benefício real consumido
│   ├── plano_tipo.py             # Catálogo de 8 planos
│   ├── plano_tipo_beneficio.py   # Benefício por tipo de plano
│   ├── profesional.py            # Profesional
│   └── servico.py                # Servicio
│
├── routes/
│   ├── __init__.py               # Blueprints main y admin
│   ├── main.py                   # Rotas públicas
│   └── admin.py                  # Rotas administrativas
│
├── services/
│   ├── barbearia_service.py      # Lógica de negocio principal
│   ├── financeiro_service.py     # Cálculo financiero central (fuente única)
│   └── pdf_service.py            # Generación de PDF
│
├── static/                       # CSS e imágenes
├── templates/                    # Templates Jinja2
│
├── teste_total.py                # Suite 45 tests (banco temporal)
├── teste_financeiro.py           # Suite 29 tests financieros
├── teste_planos.py               # Suite 19 tests de planos
├── teste_dias_semana.py          # Test de días semanales
├── teste_ajustes_exibicao.py     # Suite exibição (telefone/nome/pagamento)
└── teste_correcao_planos.py      # Suite correção monetária dos planos (REAIS)
```
---

## 📦 Instalación

1. Clonar el proyecto

   ```
   git clone https://github.com/SRHigor38/barbearia_hf.git
   cd barbearia_hf
   ```

2. Crear ambiente virtual

   ```
   python -m venv venv
   ```

   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`

3. Instalar dependencias

   ```
   pip install -r requirements.txt
   ```

4. Configurar variables de ambiente

   Copiar `.env.example` a `.env` y definir los valores.

   ```
   SECRET_KEY=valor-seguro
   # DATABASE_URL=postgresql://usuario:senha@host:5432/barbearia
   ```

5. Ejecutar el proyecto

   ```
   python app.py
   ```

   La app estará en `http://localhost:5000`.

---

## 🗄 Banco de Datos

- **Desarrollo local**: SQLite (`barbearia.db`) — funciona sin configurar nada.
- **Producción**: PostgreSQL usando la variable de ambiente `DATABASE_URL`.
- Las tablas se crean automáticamente al iniciar (`db.create_all()` + `aplicar_migracoes()`), preservando los datos existentes.

```
Flask → SQLAlchemy → PostgreSQL (producción)
                    → SQLite (desarrollo)
```

---

## 🧪 Testes

Los testes usan un banco TEMPORÁRIO (`*_temp.db`) y nunca modifican `barbearia.db`.

```
python teste_total.py          # 45 tests (planos, agendamientos, horarios)
python teste_financeiro.py     # 29 tests (financiero, gastos, admin)
python teste_planos.py         # 19 tests (planos)
python teste_dias_semana.py    # dias de la semana
```

---

## 🔒 Seguridad

- Contraseñas almacenadas con **bcrypt** (nunca texto plano)
- **CSRF** con Flask-WTF en todos los formularios (incluyendo excluir/alternar/cancelar/renovar vía POST)
- Ações destrutivas (excluir, alternar status, cancelar/renovar plano) solo vía **POST + CSRF** (nunca GET)
- Sesión protegida con `SECRET_KEY` (variable de ambiente)
- Rotas administrativas protegidas con `login_necessario()`
- Subida de fotos validada (extensión permitida + magic bytes, nombre seguro UUID, límite 2MB via MAX_CONTENT_LENGTH)
- `.env` nunca se versiona (está en `.gitignore`)

---

## 🚀 Producción

El proyecto está preparado para **Render + PostgreSQL**:

- `Procfile` → `gunicorn app:app`
- `render.yaml` → crea el servicio web y el banco PostgreSQL, inyectando `DATABASE_URL` y `SECRET_KEY`
- `DATABASE_URL` se lee desde el entorno (no está hardcodeada)

Pasos en Render:
1. Conectar el repositorio GitHub.
2. Render creará el Web Service y el PostgreSQL con `render.yaml`.
3. El banco se crea e inicializa automáticamente en el primer arranque.

---

## 👨‍💻 Autor

**HS Tech** — Desarrollo de sistemas web

© 2026 HF Barbearia. Todos los derechos reservados.