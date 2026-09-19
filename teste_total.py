# ============================================
# TESTE AUTOMATIZADO COMPLETO - HF BARBARIA
# ============================================
# Usa banco TEMPORÁRIO (teste_total_temp.db) e NUNCA modifica o banco real.
# Executar: python teste_total.py

import os
import sys

BANCO_TEMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "teste_total_temp.db")
if os.path.exists(BANCO_TEMP):
    try:
        os.remove(BANCO_TEMP)
    except PermissionError:
        pass

os.environ["DATABASE_URL"] = "sqlite:///" + BANCO_TEMP.replace("\\", "/")

RESULTADOS = []


def registrar(nome, resultado, detalhe=""):
    status = "PASS" if resultado else "FAIL"
    RESULTADOS.append((nome, status, detalhe))
    print(f"  [{status}] {nome}" + (f" — {detalhe}" if detalhe else ""))


def rodar():
    from app import create_app
    from models import db
    from models.agendamento import Agendamento
    from services.barbearia_service import (
        criar_cliente, criar_plano, buscar_plano_por_cliente,
        buscar_plano_tipo_por_nome, buscar_servico_por_nome,
        consumir_beneficios, cancelar_plano, atualizar_status_plano,
        dia_permitido_plano, criar_agendamento_plano, criar_agendamento,
        verificar_conflito_profissional, listar_profissionais,
        criar_profissional, atualizar_profissional, listar_planos_tipos,
        cancelar_agendamento_com_beneficios, validar_horario,
        horario_dentro_funcionamento, listar_profissionais_disponiveis,
    )
    from datetime import datetime, timedelta

    app = create_app()

    with app.app_context():
        print("=" * 70)
        print("TESTES HF BARBARIA (banco temporário)")
        print("=" * 70)

        # T1: Aplicação inicia
        registrar("Aplicação inicia", app is not None)

        # T2-4: Tabelas criadas
        tabelas_esperadas = {
            "cliente", "servico", "profissional", "admin", "bloqueio",
            "plano_tipo", "plano_tipo_beneficio", "plano", "plano_beneficio",
            "agendamento", "agendamento_servico", "financeiro",
        }
        tabelas = set(db.metadata.tables.keys())
        faltantes = tabelas_esperadas - tabelas
        registrar("Todas as tabelas criadas", not faltantes, f"faltando: {faltantes}")

        # T5: 8 planos
        tipos = listar_planos_tipos()
        registrar("Existem 8 planos", len(tipos) == 8, f"encontrados: {len(tipos)}")

        # T6: Benefícios corretos por plano
        regras = {
            "Bronze": {"Corte": 4, "Barba": 4},
            "Prata": {"Corte": 4, "Sobrancelha": 4},
            "Ouro": {"Corte": 4, "Barba": 4, "Sobrancelha": 4},
            "VIP": {"Corte": "ilimitado", "Barba": "ilimitado", "Sobrancelha": "ilimitado"},
            "Elite": {"Corte": "ilimitado"},
            "Basic": {"Corte": 3, "Barba": 3},
            "Light": {"Corte": 3},
            "Premium": {"Corte": 3, "Barba": 3, "Sobrancelha": 3},
        }
        ok_ben = True
        for nome, esperado in regras.items():
            pt = buscar_plano_tipo_por_nome(nome)
            if pt is None:
                ok_ben = False
                continue
            for ben in pt.beneficios:
                if ben.ilimitado:
                    if esperado.get(ben.servico.nome) != "ilimitado":
                        ok_ben = False
                else:
                    if esperado.get(ben.servico.nome) != ben.quantidade:
                        ok_ben = False
        registrar("Benefícios dos 8 planos corretos", ok_ben)

        # Valores dos planos (centavos)
        valores_esperados = {
            "Bronze": 90.00, "Prata": 80.00, "Ouro": 95.00, "VIP": 109.99,
            "Elite": 79.99, "Basic": 80.00, "Light": 70.00, "Premium": 90.00,
        }
        ok_val = True
        for nome, valor in valores_esperados.items():
            pt = buscar_plano_tipo_por_nome(nome)
            if pt is None or round(float(pt.preco), 2) != valor:
                ok_val = False
                print(f"    {nome}: esperado {valor}, encontrado {pt.preco if pt else 'None'}")
        registrar("Preços dos 8 planos corretos", ok_val)

        # T7: Validade de 30 dias
        cliente_t = criar_cliente(nome="Cliente Validade", telefone="(38) 99999-0001")
        plano_bronze = criar_plano(cliente_id=cliente_t.id,
                                   plano_tipo_id=buscar_plano_tipo_por_nome("Bronze").id)
        val_esperada = (datetime.now().date() + timedelta(days=30)).strftime("%Y-%m-%d")
        registrar("Validade = 30 dias", plano_bronze.data_validade == val_esperada,
                  f"validade: {plano_bronze.data_validade}")
# T8: Titularidade
        cliente_a = criar_cliente(nome="Cliente A", telefone="(38) 99999-0002")
        cliente_b = criar_cliente(nome="Cliente B", telefone="(38) 99999-0003")
        plano_a = criar_plano(cliente_id=cliente_a.id,
                              plano_tipo_id=buscar_plano_tipo_por_nome("Bronze").id)
        profissionais = listar_profissionais()
        prof = profissionais[0] if profissionais else None
        ag, err = criar_agendamento_plano(cliente_b.id, plano_a.id, "2026-08-24", "10:00", prof.id)
        registrar("Cliente B não usa plano de A", ag is None and err and "não pertence" in err.lower(),
                  f"erro: {err}")
        ag_ok, err_ok = criar_agendamento_plano(cliente_a.id, plano_a.id, "2026-08-24", "10:00", prof.id)
        registrar("Cliente A usa próprio plano", ag_ok is not None, f"erro: {err_ok}")
        if ag_ok:
            cancelar_agendamento_com_beneficios(ag_ok.id)

        # T9-10: Dia permitido / não permitido (Bronze = Seg..Qui)
        registrar("Segunda permitida (Bronze)", dia_permitido_plano(plano_a, "2026-08-24"))
        registrar("Sexta bloqueada (Bronze)", not dia_permitido_plano(plano_a, "2026-08-28"))

        # T11-13: Benefício disponível/esgotado/ilimitado
        servico_corte = buscar_servico_por_nome("Corte")
        servico_barba = buscar_servico_por_nome("Barba")
        registrar("Benefício disponível", plano_a.get_beneficio(servico_corte.id).disponivel)
        for _ in range(4):
            consumir_beneficios(plano_a.id, [servico_corte.id, servico_barba.id])
        plano_a = buscar_plano_por_cliente(cliente_a.id)
        registrar("Benefício esgotado", not plano_a.get_beneficio(servico_corte.id).disponivel)
        ag, err = criar_agendamento_plano(cliente_a.id, plano_a.id, "2026-08-25", "10:00", prof.id)
        registrar("Bloqueia agendamento com saldo esgotado", ag is None, f"erro: {err}")

        cliente_vip = criar_cliente(nome="Cliente VIP", telefone="(38) 99999-0004")
        plano_vip = criar_plano(cliente_id=cliente_vip.id,
                                plano_tipo_id=buscar_plano_tipo_por_nome("VIP").id)
        registrar("Benefício ilimitado (VIP)", plano_vip.tem_beneficio_ilimitado)
        for _ in range(3):
            consumir_beneficios(plano_vip.id, [s.id for s in plano_vip.servicos_inclusos])
        plano_vip = buscar_plano_por_cliente(cliente_vip.id)
        registrar("VIP continua disponível após uso", plano_vip.tem_beneficio_ilimitado)

        # T14-15: Plano expirado / cancelado
        plano_vip.data_validade = "2020-01-01"
        db.session.commit()
        status = atualizar_status_plano(plano_vip)
        registrar("Plano expirado", status == "EXPIRADO", status)

        cliente_canc = criar_cliente(nome="Cliente Cancel", telefone="(38) 99999-0005")
        plano_canc = criar_plano(cliente_id=cliente_canc.id,
                                 plano_tipo_id=buscar_plano_tipo_por_nome("Light").id)
        cancelar_plano(plano_canc.id)
        plano_canc = buscar_plano_por_cliente(cliente_canc.id)
        registrar("Plano cancelado", plano_canc.status == "CANCELADO", plano_canc.status)
# T16: Agendamento com plano (pacote múltiplos serviços)
        cliente_pk = criar_cliente(nome="Cliente Pacote", telefone="(38) 99999-0006")
        plano_pk = criar_plano(cliente_id=cliente_pk.id,
                               plano_tipo_id=buscar_plano_tipo_por_nome("Ouro").id)
        ag, err = criar_agendamento_plano(cliente_pk.id, plano_pk.id, "2026-08-26", "14:00", prof.id)
        registrar("Criou agendamento com pacote", ag is not None, f"erro: {err}")
        if ag:
            total_ag = Agendamento.query.filter_by(plano_id=plano_pk.id).count()
            registrar("Um único agendamento para o pacote", total_ag == 1, f"total: {total_ag}")
            registrar("Serviços vinculados (Ouro=3)", len(ag.servicos_relacionados) == 3,
                      f"vínculos: {len(ag.servicos_relacionados)}")

        # T17: Agendamento normal
        ag_n = criar_agendamento("Cliente Normal", "(38) 99999-0007", "2026-08-27", "15:00",
                                 "Corte", profissional_id=prof.id)
        registrar("Agendamento normal criado", ag_n is not None and ag_n.plano_id is None)

        # T18-19: Dois serviços / duração total
        registrar("Pacote Ouro = 3 serviços no tipo", len(plano_pk.servicos_inclusos) == 3)
        registrar("Duração Bronze = 40+25=65", plano_a.duracao_total == 65,
                  f"duração: {plano_a.duracao_total}")
        registrar("Duração Ouro = 40+25+20=85", plano_pk.duracao_total == 85,
                  f"duração: {plano_pk.duracao_total}")

        # T20-21: Conflito por profissional / profissionais diferentes
        conflito_mesmo = verificar_conflito_profissional(prof.id, "2026-08-26", "14:00", 65)
        registrar("Conflito no mesmo profissional", conflito_mesmo)
        prof2 = criar_profissional(nome="CARLOS")
        conflito_outro = verificar_conflito_profissional(prof2.id, "2026-08-26", "14:00", 65)
        registrar("Sem conflito para outro profissional", not conflito_outro)

        # T22: Profissional inativo
        atualizar_profissional(prof2.id, ativo=False)
        disponiveis = listar_profissionais_disponiveis("2026-09-01", "10:00", 40)
        ids = [p.id for p in disponiveis]
        registrar("Profissional inativo não disponível", prof2.id not in ids)
# T23: Dashboard exige login
        with app.test_request_context():
            from routes.admin import inicio as dashboard_inicio
            resp = dashboard_inicio()
            registrar("Dashboard exige login (redireciona)", resp.status_code == 302,
                      f"status: {resp.status_code}")

        # T24: Rota /admin/relatorios foi removida da interface
        # (404 interno -> errorhandler do app redireciona 302 para a home)
        client_rel = app.test_client()
        resp_rel = client_rel.get("/admin/relatorios")
        registrar("Rota /admin/relatorios removida (302 home)", resp_rel.status_code == 302,
                  f"status: {resp_rel.status_code}")

        # T25: Site público (via test_client para obter Response real)
        try:
            client = app.test_client()
            resp = client.get("/")
            html = resp.get_data(as_text=True)
            registrar("Home responde 200", resp.status_code == 200, f"status: {resp.status_code}")
            registrar("Home não contém 'Admin'", "Admin" not in html)
            registrar("Home não contém 'Agendar Agora'", "Agendar Agora" not in html)
            registrar("Home contém Instagram real", "hf_barbearia_" in html)
            registrar("Home contém WhatsApp real", "wa.me/5538988600331" in html)
            registrar("Home contém horários", "09:00 às 21:00" in html and "09:00 às 12:00" in html)
        except Exception as e:
            registrar("Home responde 200", False, str(e))

        # T26: Área administrativa
        with app.test_request_context("/admin"):
            from routes.admin import inicio as admin_inicio
            resp = admin_inicio()
            registrar("Admin sem login redireciona", resp.status_code == 302,
                      f"status: {resp.status_code}")

        # Horários: funcionamento backend
        registrar("Seg-Sáb 09:00 permitido", validar_horario("09:00", "2026-08-28"))
        registrar("Seg-Sáb 20:00 permitido", validar_horario("20:00", "2026-08-28"))
        registrar("Seg-Sáb 21:00 bloqueado", not validar_horario("21:00", "2026-08-28"))
        registrar("Seg-Sáb 08:00 bloqueado", not validar_horario("08:00", "2026-08-28"))
        registrar("Domingo 11:00 permitido", validar_horario("11:00", "2026-08-30"))
        registrar("Domingo 12:00 bloqueado", not validar_horario("12:00", "2026-08-30"))
        registrar("65min às 20:00 excede", not horario_dentro_funcionamento("2026-08-28", "20:00", 65))
        registrar("65min às 19:00 ok", horario_dentro_funcionamento("2026-08-28", "19:00", 65))
        registrar("Domingo 65min às 11:00 excede", not horario_dentro_funcionamento("2026-08-30", "11:00", 65))

        # Resumo
        print("\n" + "=" * 70)
        print("RESUMO FINAL")
        print("=" * 70)
        passou = sum(1 for _, s, _ in RESULTADOS if s == "PASS")
        falhou = sum(1 for _, s, _ in RESULTADOS if s == "FAIL")
        for nome, status, detalhe in RESULTADOS:
            print(f"  {status} — {nome}" + (f" ({detalhe})" if detalhe else ""))
        print(f"\nTOTAL: {passou} PASS / {falhou} FAIL / {len(RESULTADOS)} testes")

        return falhou == 0, passou, falhou


# ============================================
# PONTO DE ENTRADA
# ============================================
if __name__ == "__main__":
    ok, p, f = rodar()
    print(f"\nRESULTADO GERAL: {'APROVADO' if ok else 'COM FALHAS'} ({p} PASS / {f} FAIL)")

    # Limpeza: remove apenas o banco temporário
    try:
        if os.path.exists(BANCO_TEMP):
            os.remove(BANCO_TEMP)
            print(f"Banco temporário removido: {BANCO_TEMP}")
    except PermissionError:
        print(f"AVISO: não foi possível remover {BANCO_TEMP}. Remova manualmente.")

    sys.exit(0 if ok else 1)
