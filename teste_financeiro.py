# ============================================
# TESTE DO SISTEMA FINANCEIRO - HF BARBARIA
# ============================================
# Usa banco TEMPORÁRIO (teste_fin_temp.db) e NUNCA modifica o banco real.
# Executar: python teste_financeiro.py

import os
import sys

BANCO_TEMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "teste_fin_temp.db")
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
    from models.financeiro import Financeiro
    from models.despesa import Despesa
    from models.admin import Admin
    from services.barbearia_service import (
        criar_agendamento, criar_plano, criar_cliente,
        buscar_plano_tipo_por_nome, renovar_plano, listar_profissionais,
    )
    from services.financeiro_service import (
        calcular_financeiro, registrar_despesa, atualizar_despesa,
        excluir_despesa, atualizar_pagamento_agendamento,
        periodo_para_datas, formatar_moeda,
    )

    app = create_app()

    with app.app_context():
        print("=" * 70)
        print("TESTES FINANCEIRO HF BARBARIA (banco temporário)")
        print("=" * 70)

        # T1-T4: Despesas
        desp, err = registrar_despesa("Compra de produtos", "Produtos", 120.0, "2026-08-10")
        registrar("Cadastrar gasto manual", desp is not None and err is None, f"erro: {err}")

        ok, err = atualizar_despesa(desp.id, "Produtos de limpeza", "Materiais", 150.0, "2026-08-11")
        registrar("Editar gasto", ok and err is None, f"erro: {err}")
        desp_atualizado = Despesa.query.get(desp.id)
        registrar("Edição refletida", desp_atualizado.valor == 150.0,
                  f"valor: {desp_atualizado.valor}")
        registrar("Excluir gasto", excluir_despesa(desp.id))
# T5-T9: Pagamento de agendamento (cartão/PIX/dinheiro)
        prof = listar_profissionais()[0] if listar_profissionais() else None
        ag = criar_agendamento("Cliente Teste Fin", "(38) 99999-0009", "2026-08-15",
                               "10:00", "Corte", profissional_id=prof.id)
        registrar("Agendamento normal criado", ag is not None and ag.plano_id is None)

        fin, err = atualizar_pagamento_agendamento(ag.id, "pago", "cartao", taxa_cartao=2.5)
        registrar("Registrar pagamento cartão com taxa", fin is not None and err is None,
                  f"erro: {err}")
        fin_atual = Financeiro.query.get(fin.id)
        registrar("Taxa registrada = 2.5", fin_atual.taxa_cartao == 2.5,
                  f"taxa: {fin_atual.taxa_cartao}")
        registrar("Valor bruto preservado (40)", fin.valor == 40.0, f"valor: {fin.valor}")

        atualizar_pagamento_agendamento(ag.id, "pago", "cartao", taxa_cartao=3.0)
        fin_atual = Financeiro.query.get(fin.id)
        registrar("Alterar taxa para 3.0", fin_atual.taxa_cartao == 3.0,
                  f"taxa: {fin_atual.taxa_cartao}")

        atualizar_pagamento_agendamento(ag.id, "pago", "pix")
        fin_atual = Financeiro.query.get(fin.id)
        registrar("Cartão -> PIX zera taxa", fin_atual.taxa_cartao == 0.0,
                  f"taxa: {fin_atual.taxa_cartao}")

        atualizar_pagamento_agendamento(ag.id, "pago", "dinheiro")
        fin_atual = Financeiro.query.get(fin.id)
        registrar("Cartão -> dinheiro zera taxa", fin_atual.taxa_cartao == 0.0,
                  f"taxa: {fin_atual.taxa_cartao}")

        # T10: Agendamento pendente (não conta no faturamento)
        ag2 = criar_agendamento("Cliente Pendente", "(38) 99999-0010", "2026-08-16",
                                "11:00", "Barba", profissional_id=prof.id)
        atualizar_pagamento_agendamento(ag2.id, "pendente", "")
# T11-T12: Receitas de plano e renovação (sem dupla contagem)
        cliente_p = criar_cliente(nome="Cliente Plano", telefone="(38) 99999-0011")
        plano = criar_plano(cliente_id=cliente_p.id,
                            plano_tipo_id=buscar_plano_tipo_por_nome("Bronze").id)
        registrar("Plano criado com receita", plano is not None)
        rec_plano = Financeiro.query.filter_by(plano_id=plano.id, tipo="plano").first()
        registrar("Receita de plano (R$ 90,00)", rec_plano is not None and rec_plano.valor == 90.0,
                  f"valor: {rec_plano.valor if rec_plano else 'None'}")

        renovar_plano(plano.id)
        rec_renov = Financeiro.query.filter_by(plano_id=plano.id, tipo="renovacao_plano").first()
        registrar("Receita de renovação (R$ 90,00)",
                  rec_renov is not None and rec_renov.valor == 90.0,
                  f"valor: {rec_renov.valor if rec_renov else 'None'}")

        # T13-T15: Cálculo financeiro e dupla contagem
        # Receitas: 40 (corte dinheiro) + 90 (plano) + 90 (renovação) = 220
        ini, fim = periodo_para_datas("personalizado", "2026-01-01", "2026-12-31")
        ind = calcular_financeiro(ini, fim)
        registrar("Receita bruta = 220,00", ind["receita_bruta"] == 220.0,
                  f"receita: {ind['receita_bruta']}")
        registrar("Lucro líquido = 220,00", ind["lucro_liquido"] == 220.0,
                  f"lucro: {ind['lucro_liquido']}")
        registrar("Pendente não conta (3 receitas)", ind["quantidade_receitas"] == 3,
                  f"quantidade: {ind['quantidade_receitas']}")

        # T15: Taxa de cartão vira despesa
        ag3 = criar_agendamento("Cliente Cartao", "(38) 99999-0012", "2026-08-17",
                                "14:00", "Corte", profissional_id=prof.id)
        atualizar_pagamento_agendamento(ag3.id, "pago", "cartao", taxa_cartao=2.0)
        ind2 = calcular_financeiro(ini, fim)
        registrar("Taxa 2.00 contabilizada", ind2["despesas_taxas"] == 2.0,
                  f"taxas: {ind2['despesas_taxas']}")
        registrar("Cartão soma 40 ao bruto", ind2["receita_bruta"] == 260.0,
                  f"bruto: {ind2['receita_bruta']}")
        registrar("Lucro = 260 - 2 = 258", ind2["lucro_liquido"] == 258.0,
                  f"lucro: {ind2['lucro_liquido']}")
# T16-T18: Administrador (senha e usuário)
        admin = Admin.query.first()
        bcrypt_app = app.bcrypt
        registrar("Admin padrão existe (admin/admin123)", admin is not None
                  and admin.usuario == "admin"
                  and bcrypt_app.check_password_hash(admin.senha_hash, "admin123"))

        admin.senha_hash = bcrypt_app.generate_password_hash("nova123").decode("utf-8")
        db.session.commit()
        registrar("Senha alterada (nova123 ok)", bcrypt_app.check_password_hash(
            admin.senha_hash, "nova123"))
        registrar("Senha antiga não funciona", not bcrypt_app.check_password_hash(
            admin.senha_hash, "admin123"))

        admin.usuario = "novo_admin"
        db.session.commit()
        registrar("Usuário alterado", admin.usuario == "novo_admin")

        # T19: Formatar moeda
        registrar("Formatar moeda (90 -> R$ 90,00)", formatar_moeda(90) == "R$ 90,00",
                  formatar_moeda(90))

        # T20: Rotas financeiras exigem login
        client = app.test_client()
        for rota in ["/admin/financeiro", "/admin/gastos", "/admin/relatorios/financeiro",
                     "/admin/config"]:
            r = client.get(rota)
            registrar(f"Rota {rota} exige login", r.status_code in (301, 302),
                      f"status: {r.status_code}")

        # Resumo
        print("\n" + "=" * 70)
        passou = sum(1 for _, s, _ in RESULTADOS if s == "PASS")
        falhou = sum(1 for _, s, _ in RESULTADOS if s == "FAIL")
        for nome, status, detalhe in RESULTADOS:
            print(f"  {status} — {nome}" + (f" ({detalhe})" if detalhe else ""))
        print(f"\nTOTAL: {passou} PASS / {falhou} FAIL / {len(RESULTADOS)} testes")
        return falhou == 0, passou, falhou


if __name__ == "__main__":
    ok, p, f = rodar()
    print(f"\nRESULTADO GERAL: {'APROVADO' if ok else 'COM FALHAS'} ({p} PASS / {f} FAIL)")
    try:
        if os.path.exists(BANCO_TEMP):
            os.remove(BANCO_TEMP)
    except PermissionError:
        pass
    sys.exit(0 if ok else 1)