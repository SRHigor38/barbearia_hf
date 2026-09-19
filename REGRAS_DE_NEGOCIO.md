# 📋 Reglas de Negocio — HF Barbearia

> **Última auditoría:** 19/09/2026 — POST+CSRF en mutaciones, upload 2MB + magic bytes,
> valor de pago validado antes de persistir, exclusión de servicio bloqueada si está en uso,
> exclusión de agendamiento devuelve beneficios del plan. Sin cambios en cálculos financieros.

Documento con las reglas de negocio implementadas y verificadas en el sistema.

---

## 1. Agendamientos

### Conflicto por profesional
- Un profesional NO puede tener dos agendamientos que se solapen.
- El conflicto se valida con intervalos reales: si un agendamiento ocupa 14:00-15:00, un nuevo de 14:30-15:30 queda BLOQUEADO.
- **Profesionales distintos** PUEDEN atender el mismo horario: el bloqueo es individual, nunca global.

### Duración de servicios
- La duración del agendamiento es la suma de las duraciones de los servicios.
- Ejemplo: Corte (40 min) + Barba (25 min) = 65 min en un único agendamiento.

### Horario de funcionamiento
- Segunda a Sábado: **09:00 a 21:00**.
- Domingo: **09:00 a 12:00**.
- El backend impide agendar fuera de este horario.
- También impide que la duración del servicio exceda el cierre (ej.: 65 min no puede iniciar a las 20:00).

### Validaciones del backend
- Profesional activo.
- Fecha ≥ hoy.
- Servicio existente.
- Sin bloqueo manual.
- Sin conflicto de horario por profesional.

### Exclusões com integridade
- Excluir serviço em uso (agendamiento, paquete, catálogo o beneficios de plan) queda **BLOQUEADO**.
- Excluir agendamiento de plan **DEVUELVE los beneficios** consumidos antes de remover.
- Excluir agendamiento normal remove solo su lanzamiento financiero (sin duplicar ni dejar órfão).

---

## 2. Profesionales

- Un profesional tiene SOLO: `nome`, `foto`, `ativo`.
- **Activo**: aparece para nuevos agendamientos.
- **Inactivo**: no aparece para nuevos agendamientos pero su historial se preserva.
- La foto se valida por extensión y se guarda con nombre seguro (UUID), sin sobrescribir archivos.
- No se pueden crear especialidades, descripciones ni vínculo profesional-servicio.

---

## 3. Planos

### Validade
- Todo plano tiene validar de **30 días** desde su activación.

### Titularidad
- Los benefícios solo pueden ser utilizados por el cliente titular.
- La sesión guarda `cliente_plano_id`; el backend siempre valida `plano.cliente_id == cliente_id_de_la_sesión`.
- No se confía en parámetros de URL para la identificación.

### Benefícios
- Cada servicio del plan tiene una cantidad (`quantidade`) o es `ilimitado`.
- Se consume 1 unidad por servicio utilizado.
- **NUNCA** se decrementa un benefício ilimitado.
- El cancelamiento del agendamiento devuelve el benefício consumido (si no es ilimitado).
- Un benefício no puede quedar negativo.
- Si el plan no incluye el servicio, queda bloqueado.

### Días permitidos (convención `isoweekday`)
- 1=Segunda, 2=Terça, 3=Quarta, 4=Quinta, 5=Sexta, 6=Sábado, 7=Domingo.
- "1,2,3,4" = Segunda a Quinta (Sexta bloqueada).
- "1,2,3" = Segunda a Quarta (Quinta a Domingo bloqueados).
- El frontend solo ayuda visualmente: el backend siempre valida.

### Status del plan
- `ATIVO`: puede agendar.
- `EXPIRADO`: pasó la validar (bloqueado).
- `ESGOTADO`: se acabaron los benefícios finitos (bloqueado).
- `CANCELADO`: cancelado manualmente (bloqueado).

### Flujo de paquete (multi-servicio)
- Corte + Barba → UN único agendamiento, una fecha, un horario, un profesional.
- Se consume 1 benefício de CADA servicio utilizado.
- No se genera receita financiera por usar benefícios (el plan ya fue pagado).

---

## 4. Planos (catálogo de 8)

| Plano | Precio | Benefícios | Días |
|-------|--------|------------|------|
| Bronze | R$ 90,00 | Corte 4, Barba 4 | Seg–Qui |
| Prata | R$ 80,00 | Corte 4, Sobrancelha 4 | Seg–Qui |
| Ouro | R$ 95,00 | Corte 4, Barba 4, Sobrancelha 4 | Seg–Qui |
| VIP | R$ 109,99 | Corte/Barba/Sobrancelha ilimitados | Seg–Qui |
| Elite | R$ 79,99 | Corte ilimitado | Seg–Qua |
| Basic | R$ 80,00 | Corte 3, Barba 3 | Seg–Qui |
| Light | R$ 70,00 | Corte 3 | Seg–Qua |
| Premium | R$ 90,00 | Corte 3, Barba 3, Sobrancelha 3 | Seg–Qui |

---

## 5. Financiero

### Faturamento bruto
- Solo se suman receitas con `status == "pago"`.
- Incluye: pagos de agendamientos, venta de planes y renovaciones de planes.
- NO incluye: pagos pendientes, cancelados, ni el uso de benefícios de plan como receita nueva.

### Despesas
- Gastos manuales (`Despesa`) con categoría (Productos, Aluguel, Energía, etc.).
- Taxas de cartão/maquininha (`Financeiro.taxa_cartao`).

### Lucro líquido
- `LUCRO = Faturamento bruto − Despesas totales`.

### Pagos
- Formas: Dinheiro, PIX, Cartão.
- **Cartão**: permite registrar la taxa de maquininha.
- Cambiar de Cartão a PIX/Dinheiro **ZERA la taxa** (sin duplicar despesas).
- Cambiar el valor de la taxa actualiza sin crear registros duplicados.
- Un mismo agendamiento no puede generar dos receitas.

### Fuente única
- Dashboard, página Financeiro, Relatório y PDF usan la MISMA función `calcular_financeiro()`.
- Para el mismo período, los cuatro muestran valores idénticos.

---

## 6. Gastos

- CRUD completo (crear, editar, eliminar, listar).
- Filtro por período y por categoría.
- Validación: descripción obligatoria, valor > 0, fecha obligatoria.
- Eliminar un gasto actualiza automáticamente Dashboard, Financeiro, Relatório y PDF.

---

## 7. Seguridad

- Contraseñas con **bcrypt** (nunca texto plano).
- **CSRF** activo en todos los formularios (mutaciones solo vía POST: excluir, alternar, cancelar/renovar).
- Upload validado por extensión + magic bytes, nombre UUID, límite 2MB (413 tratado).
- Rutas administrativas protegidas con `login_necessario()`.
- No existe enlace público de administración en la Home.
- El cliente solo accede a su propio plan (titularidad por sesión).
- `SECRET_KEY` y `DATABASE_URL` vienen de variables de ambiente; `.env` no se versiona.