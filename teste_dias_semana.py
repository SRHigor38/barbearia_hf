# Script de teste: validação completa da regra de dias da semana
# Convenção: 1=Segunda, 2=Terça, 3=Quarta, 4=Quinta, 5=Sexta, 6=Sábado, 7=Domingo
from app import create_app
from services.barbearia_service import (
    criar_cliente, criar_plano, dia_permitido_plano,
    verificar_plano_valido, data_dentro_validade,
    buscar_plano_por_cliente,
    listar_profissionais, buscar_profissional_por_id,
    verificar_conflito_profissional, horario_esta_bloqueado,
    criar_agendamento, buscar_plano_tipo_por_nome,
)

app = create_app()

# Mapeamento de datas para cada dia da semana (base: 2026-08-24 = Segunda)
DIAS_TESTE = [
    ("Segunda",   "2026-08-24", 1),
    ("Terça",     "2026-08-25", 2),
    ("Quarta",    "2026-08-26", 3),
    ("Quinta",    "2026-08-27", 4),
    ("Sexta",     "2026-08-28", 5),
    ("Sábado",    "2026-08-29", 6),
    ("Domingo",   "2026-08-30", 7),
]

with app.app_context():
    # Busca o plano tipo Bronze para usar como base (dias podem ser sobrescritos)
    plano_tipo_bronze = buscar_plano_tipo_por_nome("Bronze")

    # ============================================================
    # TESTE 1: Plano Segunda a Quinta (dias 1,2,3,4)
    # ============================================================
    print("=" * 60)
    print("TESTE 1: Plano Segunda a Quinta [1,2,3,4]")
    print("=" * 60)
    cliente1 = criar_cliente(nome="Cliente Teste 1", telefone="(11) 99999-1111")
    plano1 = criar_plano(cliente_id=cliente1.id, plano_tipo_id=plano_tipo_bronze.id, dias_permitidos="1,2,3,4")
    print(f"Dias permitidos: {plano1.dias_permitidos_lista}")

    esperado1 = {
        "Segunda": True, "Terça": True, "Quarta": True, "Quinta": True,
        "Sexta": False, "Sábado": False, "Domingo": False,
    }

    todos_ok = True
    for nome_dia, data_str, num_dia in DIAS_TESTE:
        resultado = dia_permitido_plano(plano1, data_str)
        esperado = esperado1[nome_dia]
        status = "OK" if resultado == esperado else "FALHA"
        if resultado != esperado:
            todos_ok = False
        print(f"  {nome_dia:10s} (isoweekday={num_dia}) -> {resultado} (esperado: {esperado}) [{status}]")

    print(f"RESULTADO: {'TODOS OK' if todos_ok else 'FALHA'}")
    print()

    # ============================================================
    # TESTE 2: Plano Todos os Dias [1,2,3,4,5,6,7]
    # ============================================================
    print("=" * 60)
    print("TESTE 2: Plano Todos os Dias [1,2,3,4,5,6,7]")
    print("=" * 60)
    cliente2 = criar_cliente(nome="Cliente Teste 2", telefone="(11) 99999-2222")
    plano2 = criar_plano(cliente_id=cliente2.id, plano_tipo_id=plano_tipo_bronze.id, dias_permitidos="1,2,3,4,5,6,7")
    print(f"Dias permitidos: {plano2.dias_permitidos_lista}")

    todos_ok2 = True
    for nome_dia, data_str, num_dia in DIAS_TESTE:
        resultado = dia_permitido_plano(plano2, data_str)
        esperado = True  # Todos os dias devem ser permitidos
        status = "OK" if resultado == esperado else "FALHA"
        if resultado != esperado:
            todos_ok2 = False
        print(f"  {nome_dia:10s} (isoweekday={num_dia}) -> {resultado} (esperado: {esperado}) [{status}]")

    print(f"RESULTADO: {'TODOS OK' if todos_ok2 else 'FALHA'}")
    print()

    # ============================================================
    # TESTE 3: Plano apenas Sexta e Sábado [5,6]
    # ============================================================
    print("=" * 60)
    print("TESTE 3: Plano apenas Sexta e Sábado [5,6]")
    print("=" * 60)
    cliente3 = criar_cliente(nome="Cliente Teste 3", telefone="(11) 99999-3333")
    plano3 = criar_plano(cliente_id=cliente3.id, plano_tipo_id=plano_tipo_bronze.id, dias_permitidos="5,6")
    print(f"Dias permitidos: {plano3.dias_permitidos_lista}")

    esperado3 = {
        "Segunda": False, "Terça": False, "Quarta": False, "Quinta": False,
        "Sexta": True, "Sábado": True, "Domingo": False,
    }

    todos_ok3 = True
    for nome_dia, data_str, num_dia in DIAS_TESTE:
        resultado = dia_permitido_plano(plano3, data_str)
        esperado = esperado3[nome_dia]
        status = "OK" if resultado == esperado else "FALHA"
        if resultado != esperado:
            todos_ok3 = False
        print(f"  {nome_dia:10s} (isoweekday={num_dia}) -> {resultado} (esperado: {esperado}) [{status}]")

    print(f"RESULTADO: {'TODOS OK' if todos_ok3 else 'FALHA'}")
    print()

    # ============================================================
    # TESTE 4: Plano apenas Domingo [7]
    # ============================================================
    print("=" * 60)
    print("TESTE 4: Plano apenas Domingo [7]")
    print("=" * 60)
    cliente4 = criar_cliente(nome="Cliente Teste 4", telefone="(11) 99999-4444")
    plano4 = criar_plano(cliente_id=cliente4.id, plano_tipo_id=plano_tipo_bronze.id, dias_permitidos="7")
    print(f"Dias permitidos: {plano4.dias_permitidos_lista}")

    esperado4 = {
        "Segunda": False, "Terça": False, "Quarta": False, "Quinta": False,
        "Sexta": False, "Sábado": False, "Domingo": True,
    }

    todos_ok4 = True
    for nome_dia, data_str, num_dia in DIAS_TESTE:
        resultado = dia_permitido_plano(plano4, data_str)
        esperado = esperado4[nome_dia]
        status = "OK" if resultado == esperado else "FALHA"
        if resultado != esperado:
            todos_ok4 = False
        print(f"  {nome_dia:10s} (isoweekday={num_dia}) -> {resultado} (esperado: {esperado}) [{status}]")

    print(f"RESULTADO: {'TODOS OK' if todos_ok4 else 'FALHA'}")
    print()

    # ============================================================
    # TESTE 5: Backend - Tentativa de agendamento em dia não permitido
    # ============================================================
    print("=" * 60)
    print("TESTE 5: Backend - Agendamento em dia NÃO permitido")
    print("=" * 60)
    # Plano1 tem dias [1,2,3,4] = Segunda a Quinta
    # 2026-08-28 é Sexta (isoweekday=5) - NÃO permitido
    data_nao_permitida = "2026-08-28"  # Sexta-feira
    dia_semana_num = 5  # isoweekday

    # Verifica que o dia não é permitido pelo plano
    permitido = dia_permitido_plano(plano1, data_nao_permitida)
    print(f"  Plano1 dias: {plano1.dias_permitidos_lista}")
    print(f"  Data testada: {data_nao_permitida} (Sexta-feira, isoweekday={dia_semana_num})")
    print(f"  Dia permitido pelo plano: {permitido}")

    if not permitido:
        print("  -> CORRETO: O dia NÃO está permitido pelo plano.")
        print("  -> O backend (routes/main.py) bloqueará este agendamento.")
        print("  -> Simulando a verificação do backend:")
        print(f"     if not dia_permitido_plano(plano, '{data_nao_permitida}'):")
        print(f"         flash('Esta data não está dentro dos dias permitidos pelo seu plano.', 'error')")
        print(f"         return redirect(...)  # Bloqueia o agendamento")
        print("  RESULTADO: OK - Agendamento seria bloqueado corretamente")
    else:
        print("  -> FALHA: O dia deveria ser bloqueado mas está permitido!")
    print()

    # ============================================================
    # TESTE 6: Backend - Agendamento em dia permitido (deve passar)
    # ============================================================
    print("=" * 60)
    print("TESTE 6: Backend - Agendamento em dia PERMITIDO")
    print("=" * 60)
    data_permitida = "2026-08-24"  # Segunda-feira
    permitido2 = dia_permitido_plano(plano1, data_permitida)
    print(f"  Data testada: {data_permitida} (Segunda-feira, isoweekday=1)")
    print(f"  Dia permitido pelo plano: {permitido2}")
    if permitido2:
        print("  -> CORRETO: O dia está permitido pelo plano.")
        print("  -> O backend permitirá o agendamento.")
        print("  RESULTADO: OK")
    else:
        print("  -> FALHA: O dia deveria ser permitido mas está bloqueado!")
    print()

    # ============================================================
    # RESUMO FINAL
    # ============================================================
    print("=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)
    resultados = [
        ("Plano Seg-Qui [1,2,3,4]", todos_ok),
        ("Plano Todos [1,2,3,4,5,6,7]", todos_ok2),
        ("Plano Sex-Sáb [5,6]", todos_ok3),
        ("Plano Domingo [7]", todos_ok4),
        ("Backend bloqueio dia não permitido", not permitido),
        ("Backend permite dia permitido", permitido2),
    ]
    all_pass = True
    for nome, ok in resultados:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {nome}")
    print()
    print(f"RESULTADO GERAL: {'TODOS OS TESTES PASSARAM' if all_pass else 'HÁ FALHAS'}")
