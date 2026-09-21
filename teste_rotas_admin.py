# ============================================
# TESTE DAS ROTAS ADMINISTRATIVAS (SMOKE TEST)
# ============================================
# Navega pelas principais páginas do painel com o admin autenticado,
# exatamente como acontece em produção. Protege contra regressões como o
# RecursionError que derrubava /admin/planos com "Erro interno do servidor".
#
# Executar: python teste_rotas_admin.py
# Banco: TEMPORÁRIO (teste_rotas_admin_temp.db) — nunca o de produção.
# Somente requisições GET (nenhuma mutação de dados).

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
BANCO_TEMP = os.path.join(BASE, "teste_rotas_admin_temp.db")
if os.path.exists(BANCO_TEMP):
    try:
        os.remove(BANCO_TEMP)
    except PermissionError:
        pass

os.environ["DATABASE_URL"] = "sqlite:///" + BANCO_TEMP.replace("\\", "/")
os.environ["APP_ENV"] = "development"
os.environ.pop("RENDER", None)
os.environ.pop("PRODUCTION", None)

RESULTADOS = []


def registrar(nome, resultado, detalhe=""):
    status = "PASS" if resultado else "FAIL"
    RESULTADOS.append((nome, status, detalhe))
    print(f"  [{status}] {nome}" + (f" — {detalhe}" if detalhe else ""))


# Rotas administrativas (GET) esperadas em 200 com o admin logado
ROTAS_ADMIN = [
    ("/admin/", "Dashboard"),
    ("/admin/agendamentos", "Agendamentos"),
    ("/admin/servicos", "Servicos"),
    ("/admin/profissionais", "Profissionais"),
    ("/admin/profissionais/novo", "Novo profissional"),
    ("/admin/planos", "Planos (bug do RecursionError)"),
    ("/admin/planos/novo", "Novo plano"),
    ("/admin/financeiro", "Financeiro"),
    ("/admin/financeiro/pdf", "Financeiro PDF"),
    ("/admin/gastos", "Gastos"),
    ("/admin/relatorios/financeiro", "Relatorio financeiro"),
    ("/admin/config", "Configuracoes"),
    ("/admin/servicos/editar/{servico}", "Editar servico"),
    ("/admin/profissionais/editar/{profissional}", "Editar profissional"),
    ("/admin/agendamentos/pagamento/{agendamento}", "Pagamento do agendamento"),
    ("/admin/gastos/editar/{despesa}", "Editar gasto"),
]

# Rotas públicas que devem continuar funcionando
ROTAS_PUBLICAS = [
    ("/", "Home"),
    ("/agendamento?servico=Corte", "Fluxo de agendamento"),
]

# Rotas administrativas que respondem com redirecionamento (302)
ROTAS_ADMIN_REDIRECT = [
    ("/admin/planos/codigo/{plano}", "/admin/planos", "Codigo do plano"),
]

# Rotas administrativas que exigem login
ROTAS_PROTEGIDAS = [
    ("/admin/", "Dashboard"),
    ("/admin/planos", "Planos"),
    ("/admin/financeiro", "Financeiro"),
    ("/admin/agendamentos", "Agendamentos"),
]


def _get(client, rota):
    """Executa o GET devolvendo (status, resposta) mesmo se houver excecao."""
    try:
        resposta = client.get(rota)
        return resposta.status_code, resposta
    except Exception as exc:  # noqa: BLE001 - queremos ver a causa REAL
        return f"EXCECAO {type(exc).__name__}", None


def rodar():
    from app import create_app
    from models.admin import Admin
    from services.barbearia_service import (
        buscar_plano_tipo_por_nome,
        buscar_servico_por_nome,
        criar_agendamento,
        criar_cliente,
        criar_plano,
        listar_profissionais,
    )
    from services.financeiro_service import registrar_despesa

    # PROPAGATE_EXCEPTIONS: se uma rota estourar, o teste mostra a excecao real
    app = create_app()
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = True

    with app.app_context():
        admin = Admin.query.first()
        admin_id = admin.id if admin else 1

        profissional = listar_profissionais()[0]
        servico = buscar_servico_por_nome("Corte")
        registrar("Servico 'Corte' disponivel (semente)", servico is not None)
        nome_servico = servico.nome if servico else "Corte"
        cliente = criar_cliente(nome="Cliente Rota Admin", telefone="(11) 90000-0002")
        plano = criar_plano(
            cliente_id=cliente.id,
            plano_tipo_id=buscar_plano_tipo_por_nome("Bronze").id,
            dias_permitidos="1,2,3",
        )
        agendamento = criar_agendamento(
            nome="Cliente Rota Admin",
            telefone="(11) 90000-0002",
            data="2026-09-22",
            horario="11:00",
            servico=nome_servico,
            profissional_id=profissional.id,
        )
        despesa, _ = registrar_despesa("Gasto Rota Admin", "Outros", 10.0, "2026-09-05")

        ids = {
            "plano": plano.id if plano else 1,
            "servico": servico.id if servico else 1,
            "profissional": profissional.id,
            "agendamento": agendamento.id if agendamento else 1,
            "despesa": despesa.id if despesa else 1,
        }

    client = app.test_client()

    # --- Sem login: rotas administrativas devem redirecionar para o login ---
    print("\n[1] Rotas administrativas exigem login")
    for rota, nome in ROTAS_PROTEGIDAS:
        status, resposta = _get(client, rota)
        destino = resposta.headers.get("Location", "") if resposta is not None else ""
        registrar(
            f"{nome} sem login redireciona para /admin/login",
            status == 302 and "/admin/login" in destino,
            f"status={status} destino={destino}",
        )

    # --- Login do admin ---
    with client.session_transaction() as sessao:
        sessao["admin_id"] = admin_id
        sessao["admin_usuario"] = "admin"

    # --- Com login: todas as rotas administrativas em 200 ---
    print("\n[2] Rotas administrativas respondem 200 (admin logado)")
    for rota, nome in ROTAS_ADMIN:
        caminho = rota.format(**ids)
        status, _ = _get(client, caminho)
        registrar(f"{nome} -> {caminho}", status == 200, f"status={status}")

    # --- Rotas administrativas que redirecionam ---
    print("\n[2b] Rotas administrativas com redirecionamento")
    for rota, destino_esperado, nome in ROTAS_ADMIN_REDIRECT:
        caminho = rota.format(**ids)
        status, resposta = _get(client, caminho)
        destino = resposta.headers.get("Location", "") if resposta is not None else ""
        registrar(
            f"{nome} -> {caminho} redireciona para {destino_esperado}",
            status == 302 and destino_esperado in destino,
            f"status={status} destino={destino}",
        )

    # --- /admin/planos renderiza os dados (nao pode vir vazia) ---
    print("\n[3] /admin/planos renderiza o conteudo real")
    status, resposta = _get(client, "/admin/planos")
    html = resposta.get_data(as_text=True) if resposta is not None else ""
    registrar("/admin/planos responde 200", status == 200, f"status={status}")
    registrar("Pagina lista o plano do cliente", "Cliente Rota Admin" in html)
    registrar("Pagina mostra o tipo de plano (Bronze)", "Bronze" in html)
    registrar("Nao exibe mensagem de erro interno",
              "Erro interno do servidor" not in html)

    # --- Filtro de período: editar a data deve mudar para "Personalizado" ---
    print("\n[3b] Filtro de periodo (datas customizadas)")
    for caminho, nome in [("/admin/financeiro", "Financeiro"),
                          ("/admin/relatorios/financeiro", "Relatorio financeiro")]:
        status, resposta = _get(client, caminho)
        html = resposta.get_data(as_text=True) if resposta is not None else ""
        ok = (
            'id="periodo-select"' in html
            and "data-personalizada" in html
            and 'addEventListener(\'input\'' in html
        )
        registrar(f"{nome}: datas editadas mudam o filtro para Personalizado",
                  ok and status == 200, f"status={status}")

    # --- Rotas públicas continuam funcionando ---
    print("\n[4] Rotas publicas continuam funcionando")
    for rota, nome in ROTAS_PUBLICAS:
        status, _ = _get(client, rota)
        registrar(f"{nome} -> {rota}", status == 200, f"status={status}")

    print("\n" + "=" * 70)
    passou = sum(1 for _, status, _ in RESULTADOS if status == "PASS")
    falhou = sum(1 for _, status, _ in RESULTADOS if status == "FAIL")
    print(f"TOTAL: {passou} PASS / {falhou} FAIL / {len(RESULTADOS)} testes")
    return falhou == 0, passou, falhou


if __name__ == "__main__":
    print("=" * 70)
    print("TESTE DAS ROTAS ADMINISTRATIVAS (banco temporario)")
    print("=" * 70)

    ok, p, f = rodar()
    print(f"\nRESULTADO GERAL: {'APROVADO' if ok else 'COM FALHAS'} ({p} PASS / {f} FAIL)")

    try:
        if os.path.exists(BANCO_TEMP):
            os.remove(BANCO_TEMP)
    except PermissionError:
        pass
    sys.exit(0 if ok else 1)

