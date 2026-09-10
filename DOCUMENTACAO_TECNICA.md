# 📘 Documentación Técnica — HF Barbearia

Documentación para desarrolladores. Explica la arquitectura, modelos, flujos y reglas técnicas del sistema.

---

## 1. Arquitectura del Sistema

```
Flask (create_app)
 ├── routes/          → Blueprints: main (público) y admin (protegido)
 ├── services/        → Lógica de negocio (barbearia, financeiro, pdf)
 ├── models/          → Modelos SQLAlchemy
 ├── templates/       → Jinja2 (identidad visual negro/dorado/blanco)
 └── static/          → CSS e imágenes
```

### Patrón de fábrica

`app.py` expone `create_app()` que:

1. Crea la app Flask.
2. Carga la configuración (`config.py`).
3. Inicializa SQLAlchemy, CSRF y Bcrypt.
4. Registra los blueprints.
5. Define error handlers (404, 500, 400).
6. Dentro de `app_context()`:
   - Llama `criar_banco_e_popular()` (crea tablas y datos iniciales).
   - Llama `aplicar_migracoes()` (agrega columnas nuevas sin borrar datos).
   - Crea el admin por defecto si no existe.

---

## 2. Modelos Principales

### Cliente
- `nome`, `telefone`, `email` (opcional), histórico de agendamientos.
- Identificado por teléfono en el flujo "Meu Plano".

### Servicio
- `nome` (único), `preco`, `tempo` (minutos).

### Profesional
- Solo `nome`, `foto`, `ativo`. Campos mínimos intencionales.

### Agendamiento
- Cliente, servicio, fecha, horario, profesional, plano (opcional).
- `servicos_relacionados` permite múltiples servicios en un único agendamiento.
- `duracao_total` = suma de las duraciones de los servicios.

### PlanoTipo (catálogo)
- Los 8 planes con `preco` en CENTAVOS (9000 = R$ 90,00) y `dias_permitidos` ("1,2,3,4" = Seg-Qui).

### Plano (del cliente)
- Pertenece a un `cliente` (1:1, `cliente_id` único) y a un `plano_tipo`.
- `status`: ATIVO / EXPIRADO / ESGOTADO / CANCELADO.
- `codigo_acesso` para identificación del cliente.
- Validade de 30 días.

### PlanoBeneficio / PlanoTipoBeneficio
- Beneficio real (PlanoBeneficio) vs. definición del catálogo (PlanoTipoBeneficio).
- `ilimitado`, `quantidade`, `quantidade_utilizada`, `restante`, `disponible`.

### Financeiro
- Movimiento financiero unificado: receitas de agendamientos (`agendamento_id`),
  venta/renovación de planos (`plano_id`), `taxa_cartao`, `status`.
- `valor` en REAIS (Float). Solo `status == "pago"` entra en el faturamento.

### Despesa
- Gasto manual: `descricao`, `categoria`, `valor`, `data`, `observacao`.

### Admin
- `usuario` (único) y `senha_hash` (bcrypt).

### Bloqueio
- Bloqueo manual de fecha/horario.

---

## 3. Relacionamientos Clave

| Modelo | Relación |
|--------|----------|
| Cliente → Plano | 1:1 (`cliente_id` único) |
| Plano → PlanoTipo | N:1 |
| Plano → PlanoBeneficio | 1:N (cascade delete-orphan) |
| Agendamiento → Cliente/Profesional/Plano | N:1 (nullable) |
| Agendamiento → AgendamientoServicio | 1:N (junction) |
| Agendamiento → Financeiro | 1:1 (uselist=False) |
| Plano → Financeiro | 1:N (venda + renovaciones) |
---

## 4. Flujo de Agendamiento Normal

1. Cliente selecciona un servicio en la Home (`/agendamiento?servico=X`).
2. Completa nombre, teléfono, fecha, horario y elige profesional.
3. El backend valida:
   - Servicio existe.
   - Teléfono con formato válido.
   - Fecha ≥ hoy.
   - Horario dentro del funcionamiento (Seg-Sáb 09:00-21:00, Dom 09:00-12:00) y duración que no exceda el cierre.
   - Profesional activo.
   - Conflicto por profesional (incluye solapamiento parcial).
   - Bloqueo manual.
4. Se crea `Cliente` (si no existe) + `Agendamiento` + `Financeiro(status="pendente")`.

---

## 5. Flujo de Planos ("Meu Plano")

1. El admin registra al cliente en un plan y entrega teléfono + código.
2. El cliente entra en `/meu-plano`, ingresa teléfono + código.
3. La sesión guarda `cliente_plano_id` (no se confía en parámetros de URL).
4. `/meu-plano/area` muestra beneficios, validez y días.
5. `/meu-plano/agendar` valida en el backend:
   - Titularidad (`plano.cliente_id == cliente_id` de la sesión).
   - Status ATIVO (no CANCELADO/EXPIRADO/ESGOTADO).
   - Fecha dentro de validez.
   - Día permitido (`isoweekday`).
   - Beneficios disponibles para el paquete completo.
   - Profesional activo, horario, conflicto, duración, bloqueo.
6. Se crea UN único `Agendamiento` con N `AgendamientoServicio`.
7. Se consumen los beneficios (solo finitos). NUNCA se decrementa un beneficio ilimitado.
8. No se crea `Financeiro` (el plan ya fue pagado) → evita doble contaje.

---

## 6. Flujo Financiero

### Fuente única: `services/financeiro_service.py`

| Componente | Función |
|------------|---------|
| Dashboard | `calcular_financeiro(ini, fim)` |
| Página Financeiro | `calcular_financeiro(ini, fim)` |
| Relatório Financeiro | `calcular_financeiro(ini, fim)` |
| PDF | `calcular_financeiro(ini, fim)` |

- **Faturamento bruto** = sumatoria de `Financeiro` con `status == "pago"` (agendamientos + venta de planes + renovaciones).
- **Despesas** = gastos manuales (`Despesa`) + taxas de cartón (`Financeiro.taxa_cartao`).
- **Taxas** = suma de `taxa_cartao` donde `forma_pagamento == "cartao"`.
- **Lucro líquido** = Faturamento bruto − Despesas totales.

### Unidades monetarias

- `planos_tipo.preco`: CENTAVOS (9000 = R$ 90,00).
- `financeiro.valor`, `financeiro.taxa_cartao`, `despesa.valor`: REAIS (Float).
- `preco_plano_reais()` y `formatar_moeda()` centralizan las conversiones.
---

## 7. Reglas Técnicas Importantes

1. **Días de la semana**: convención única `isoweekday()` (1=Segunda … 7=Domingo). Jamás usar `weekday()`.
2. **Horario de funcionamiento**: funciones `validar_horario(horario, data)` y `horario_dentro_funcionamento(data, horario, duracao)` en `barbearia_service`.
3. **Conflicto por profesional**: `verificar_conflito_profissional()` calcula intervalos y detecta solapamiento.
4. **Titularidad**: siempre `plano.cliente_id == session["cliente_plano_id"]`.
5. **Doble contaje financiero**: el uso de benefício de plan NO crea `Financeiro`; solo venta/renovación lo hacen.
6. **Status financiero**: solo `"pago"` entra en el faturamento; `pendente`/`cancelado` se ignoran.

---

## 8. Rutas Principales

### Públicas (`routes/main.py`)
| Ruta | Método | Descripción |
|------|--------|-------------|
| `/` | GET | Home con servicios |
| `/agendamiento` | GET/POST | Agendamiento normal |
| `/api/horarios` | GET | Horarios disponibles (profesional) |
| `/meu-plano` | GET/POST | Login teléfono + código |
| `/meu-plano/area` | GET | Área del cliente del plan |
| `/meu-plano/agendar` | GET/POST | Agendamiento con plan |
| `/api/horarios-plano` | GET | Horarios para plan |
| `/api/profesionales-disponibles` | GET | Profesionales libres |

### Administrativas (`routes/admin.py`, protegidas por `login_necessario()`)
| Ruta | Descripción |
|------|-------------|
| `/admin/` | Dashboard |
| `/admin/agendamientos` | Lista de agendamientos |
| `/admin/agendamientos/pagamento/<id>` | Registrar/alterar pago |
| `/admin/servicos` | CRUD servicios |
| `/admin/profesionales` | CRUD profesionales |
| `/admin/planos` | Planos de clientes |
| `/admin/financeiro` | Panel financiero con filtros |
| `/admin/financeiro/pdf` | Exportación PDF |
| `/admin/gastos` | CRUD gastos |
| `/admin/relatorios` | Relatório por período |
| `/admin/relatorios/financeiro` | Relatório financiero |
| `/admin/config` | Cambiar usuario/contraseña |

---

## 9. Estrategia SQLite / PostgreSQL

- `config.py` lee `DATABASE_URL`. Si está definida, la usa (normalizando `postgres://` → `postgresql+psycopg2://`). Si no, usa SQLite local `barbearia.db`.
- `db.create_all()` crea tablas nuevas; `aplicar_migracoes()` agrega columnas faltantes a `financeiro` (compatible SQLite via `PRAGMA table_info` y PostgreSQL via `information_schema`).
- Los datos existentes se preservan: las migraciones solo agregan columnas, nunca borran.
- `render.yaml` crea el PostgreSQL y `Procfile` ejecuta `gunicorn app:app`.