# ============================================
# TESTE: CONSULTA PÚBLICA "MEUS AGENDAMENTOS" (somente telefone)
# ============================================
# Prova que POST /meus-agendamentos:
#   - lista agendamentos NORMAIS, de PLANO e os dois tipos juntos;
#   - aceita o telefone com formatações diferentes;
#   - não revela se o telefone existe (mesma resposta p/ inexistente e sem agendamentos);
#   - nunca mostra agendamentos de outro telefone;
#   - é SOMENTE LEITURA (não mexe em plano, benefícios, agendamentos, financeiro);
#   - não expõe IDs, telefone completo nem aceita telefone pela URL.
#
# Executar: python teste_meus_agendamentos.py
# Banco: TEMPORÁRIO (teste_meus_agendamentos_temp.db) — nunca o de produção.
# Não depende de nomes do catálogo: usa os serviços/planos que existirem no banco.

import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
BANCO_TEMP = os.path.join(BASE, "teste_meus_agendamentos_temp.db")
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


def proxima_terca(minimo_dias=7):
    """Próxima terça-feira a partir de hoje + minimo_dias (dentro do funcionamento e dos planos)."""
    from datetime import date, timedelta
    d = date.today() + timedelta(days=minimo_dias)
    while d.isoweekday() != 2:
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def rodar():
    from app import create_app
    from models import db
    from models.agendamento import Agendamento
    from models.cliente import Cliente
    from models.financeiro import Financeiro
    from models.plano import Plano
    from models.plano_beneficio import PlanoBeneficio
    from models.plano_tipo import PlanoTipo
    from models.servico import Servico
    from services.barbearia_service import (
        criar_agendamento,
        criar_agendamento_plano,
        criar_cliente,
        criar_plano,
        listar_agendamentos_por_telefone,
        listar_profissionais,
    )
    from services.financeiro_service import atualizar_pagamento_agendamento, formatar_moeda
    from utils import mascarar_telefone

    print("=" * 70)
    print("TESTE MEUS AGENDAMENTOS (somente telefone) — banco temporario")
    print("=" * 70)

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False  # permite o POST direto no teste
    client = app.test_client()

    # Telefones de teste
    TEL_NORMAL = "38991390001"   # só agendamento normal
    TEL_PLANO = "38991390002"    # só agendamento de plano
    TEL_MISTO = "38991390003"    # plano + normal
    TEL_SEM_AG = "38991390004"   # cliente cadastrado, sem agendamentos
    TEL_VARIOS = "38991390005"   # vários agendamentos
    TEL_OUTRO = "38991390006"    # outro cliente (isolamento)
    TEL_INEXISTENTE = "38991390099"
    TEL_LEGADO = "(38) 99139-0007"  # registro antigo: telefone formatado e sem cliente_id

    DATA_FUTURA = proxima_terca(7)
    DATA_OUTRO = "2031-03-15"   # data exclusiva do "outro cliente" (marcador de isolamento)

    def consultar(telefone):
        resp = client.post("/meus-agendamentos", data={"telefone": telefone})
        return resp, resp.get_data(as_text=True)

    def n_cartoes(html):
        return html.count("Serviço</span>")

    with app.app_context():
        prof = listar_profissionais()[0]
        servicos = Servico.query.order_by(Servico.id).all()
        s1, s2, s3 = servicos[0], servicos[1], servicos[2]
        tipo = PlanoTipo.query.order_by(PlanoTipo.id).first()

        # --- Cliente NORMAL ---
        c_normal = criar_cliente(nome="Cliente Normal", telefone=TEL_NORMAL)
        criar_agendamento("Cliente Normal", TEL_NORMAL, DATA_FUTURA, "10:00", s1.nome,
                          profissional_id=prof.id, cliente_id=c_normal.id)

        # --- Cliente de PLANO ---
        c_plano = criar_cliente(nome="Cliente Plano", telefone=TEL_PLANO)
        plano_b = criar_plano(cliente_id=c_plano.id, plano_tipo_id=tipo.id,
                              dias_permitidos="1,2,3,4,5,6,7")
        ag_b, erro_b = criar_agendamento_plano(
            cliente_id=c_plano.id, plano_id=plano_b.id, data=DATA_FUTURA,
            horario="11:00", profissional_id=prof.id)
        registrar("Massa: agendamento de plano criado", ag_b is not None, erro_b or "")

        # --- Cliente MISTO (plano + normal) ---
        c_misto = criar_cliente(nome="Cliente Misto", telefone=TEL_MISTO)
        plano_c = criar_plano(cliente_id=c_misto.id, plano_tipo_id=tipo.id,
                              dias_permitidos="1,2,3,4,5,6,7")
        ag_c, erro_c = criar_agendamento_plano(
            cliente_id=c_misto.id, plano_id=plano_c.id, data=DATA_FUTURA,
            horario="17:00", profissional_id=prof.id)
        registrar("Massa: agendamento de plano do cliente misto", ag_c is not None, erro_c or "")
        criar_agendamento("Cliente Misto", TEL_MISTO, "2020-01-10", "09:00", s2.nome,
                          profissional_id=prof.id, cliente_id=c_misto.id)

        # --- Cliente SEM agendamentos ---
        criar_cliente(nome="Cliente Sem Agenda", telefone=TEL_SEM_AG)

        # --- Cliente com VÁRIOS agendamentos (1 futuro + 2 passados) ---
        c_varios = criar_cliente(nome="Cliente Varios", telefone=TEL_VARIOS)
        criar_agendamento("Cliente Varios", TEL_VARIOS, DATA_FUTURA, "14:00", s1.nome,
                          profissional_id=prof.id, cliente_id=c_varios.id)
        criar_agendamento("Cliente Varios", TEL_VARIOS, "2020-02-01", "09:00", s1.nome,
                          profissional_id=prof.id, cliente_id=c_varios.id)
        criar_agendamento("Cliente Varios", TEL_VARIOS, "2021-05-20", "09:00", s3.nome,
                          profissional_id=prof.id, cliente_id=c_varios.id)

        # --- OUTRO cliente (data exclusiva p/ provar isolamento) ---
        c_outro = criar_cliente(nome="Cliente Outro", telefone=TEL_OUTRO)
        criar_agendamento("Cliente Outro", TEL_OUTRO, DATA_OUTRO, "15:00", s3.nome,
                          profissional_id=prof.id, cliente_id=c_outro.id)

        # --- Registro LEGADO: telefone formatado, sem cliente_id ---
        db.session.add(Agendamento(
            nome="Cliente Legado", telefone=TEL_LEGADO, data="2022-07-07",
            horario="09:00", servico=s1.nome, profissional_id=prof.id))
        db.session.commit()

        nome_s1, nome_s2, nome_s3 = s1.nome, s2.nome, s3.nome
        preco_s1 = s1.preco
        nome_plano = plano_b.nome
        nome_prof = prof.nome
        id_ag_normal = Agendamento.query.filter_by(telefone=TEL_NORMAL).first().id

    # ------------------------------------------------------------
    # GET: formulário
    # ------------------------------------------------------------
    print("\n--- Formulario e home ---")
    r = client.get("/meus-agendamentos")
    html = r.get_data(as_text=True)
    registrar("GET /meus-agendamentos responde 200 com formulario de telefone",
              r.status_code == 200 and 'name="telefone"' in html and "Consultar" in html)
    registrar("Formulario NAO pede senha, codigo nem login",
              'name="codigo"' not in html and 'type="password"' not in html)
    registrar("Formulario usa POST", 'method="POST"' in html)

    r = client.get("/")
    registrar("Pagina inicial tem o botao Meus Agendamentos",
              r.status_code == 200 and 'href="/meus-agendamentos"' in r.get_data(as_text=True))

    # ------------------------------------------------------------
    # 1) Cliente com agendamento NORMAL
    # ------------------------------------------------------------
    print("\n--- 1) Agendamento normal ---")
    r, html = consultar(TEL_NORMAL)
    registrar("Normal: responde 200", r.status_code == 200)
    registrar("Normal: mostra servico, data, horario e profissional",
              nome_s1 in html and DATA_FUTURA.split("-")[2] in html
              and "10:00" in html and nome_prof in html)
    registrar("Normal: mostra o valor do servico",
              formatar_moeda(preco_s1) in html, formatar_moeda(preco_s1))
    registrar("Normal: indica agendamento normal (nao via plano)",
              "Agendamento normal" in html and "Via plano" not in html)
    registrar("Normal: pagamento pendente por padrao", "Pagamento pendente" in html)
    registrar("Normal: apenas 1 cartao", n_cartoes(html) == 1, f"cartoes={n_cartoes(html)}")

    with app.app_context():
        atualizar_pagamento_agendamento(id_ag_normal, "pago", "dinheiro")
    r, html = consultar(TEL_NORMAL)
    registrar("Normal: apos pagar, status mostra Pago",
              "Pago" in html and "Pagamento pendente" not in html)

    # ------------------------------------------------------------
    # 2) Cliente com agendamento de PLANO
    # ------------------------------------------------------------
    print("\n--- 2) Agendamento de plano ---")
    r, html = consultar(TEL_PLANO)
    registrar("Plano: responde 200 e mostra 1 cartao", r.status_code == 200 and n_cartoes(html) == 1)
    registrar("Plano: indica 'Via plano' com o nome do plano",
              "Via plano" in html and nome_plano in html)
    registrar("Plano: valor aparece como 'Incluso no plano'", "Incluso no plano" in html)
    registrar("Plano: nao aparece como agendamento normal / sem status de pagamento",
              "Agendamento normal" not in html and "Pagamento pendente" not in html)
    registrar("Plano: mostra profissional e horario", nome_prof in html and "11:00" in html)

    # ------------------------------------------------------------
    # 3) Cliente com os DOIS tipos
    # ------------------------------------------------------------
    print("\n--- 3) Plano + normal ---")
    r, html = consultar(TEL_MISTO)
    registrar("Misto: mostra os 2 agendamentos", n_cartoes(html) == 2, f"cartoes={n_cartoes(html)}")
    registrar("Misto: mostra 'Via plano' e 'Agendamento normal'",
              "Via plano" in html and "Agendamento normal" in html)
    registrar("Misto: separa proximos e anteriores",
              "Próximos agendamentos" in html and "Agendamentos anteriores" in html)

    # ------------------------------------------------------------
    # 4) Telefone inexistente / 5) Cliente sem agendamentos
    # ------------------------------------------------------------
    print("\n--- 4/5) Inexistente e sem agendamentos ---")
    r_inex, html_inex = consultar(TEL_INEXISTENTE)
    r_sem, html_sem = consultar(TEL_SEM_AG)
    registrar("Inexistente: 200 e mensagem de nenhum agendamento",
              r_inex.status_code == 200 and "Nenhum agendamento encontrado" in html_inex
              and n_cartoes(html_inex) == 0)
    registrar("Sem agendamentos: 200 e mensagem de nenhum agendamento",
              r_sem.status_code == 200 and "Nenhum agendamento encontrado" in html_sem
              and n_cartoes(html_sem) == 0)
    registrar("Nao revela se o telefone existe (mesma mensagem nos dois casos)",
              ("Nenhum agendamento encontrado para este telefone." in html_inex)
              and ("Nenhum agendamento encontrado para este telefone." in html_sem)
              and "não encontrado" not in html_inex.lower()
              and "cadastrad" not in html_inex.lower())

    # ------------------------------------------------------------
    # 6) Vários agendamentos
    # ------------------------------------------------------------
    print("\n--- 6) Varios agendamentos ---")
    r, html = consultar(TEL_VARIOS)
    registrar("Varios: mostra os 3 agendamentos", n_cartoes(html) == 3, f"cartoes={n_cartoes(html)}")
    pos_prox = html.find("Próximos agendamentos")
    pos_ant = html.find("Agendamentos anteriores")
    registrar("Varios: proximos aparecem antes dos anteriores",
              0 <= pos_prox < pos_ant)
    registrar("Varios: anteriores do mais recente para o mais antigo",
              html.find("20/05/2021") != -1 and html.find("01/02/2020") != -1
              and html.find("20/05/2021") < html.find("01/02/2020"))

    # ------------------------------------------------------------
    # 7) Telefone com formatações diferentes
    # ------------------------------------------------------------
    print("\n--- 7) Formatacoes do telefone ---")
    for variacao in ["38991390001", "(38) 99139-0001", "(38)99139-0001",
                     "38 99139-0001", "38991390001 "]:
        r, html = consultar(variacao)
        registrar(f"Formato {variacao!r} encontra o mesmo cliente",
                  n_cartoes(html) == 1 and nome_s1 in html)
    r, html = consultar("(38) 99139-0007")
    registrar("Registro legado (telefone formatado, sem cliente_id) e encontrado",
              n_cartoes(html) == 1 and "07/07/2022" in html)
    r, html = consultar("38991390007")
    registrar("Legado tambem e encontrado digitando so numeros",
              n_cartoes(html) == 1 and "07/07/2022" in html)
    for invalido in ["123", "abc", "(38) 9999", "3899139000199999"]:
        r, html = consultar(invalido)
        registrar(f"Telefone invalido {invalido!r} e recusado sem listar nada",
                  r.status_code == 200 and "Telefone inválido" in html and n_cartoes(html) == 0)
    r, html = consultar("")
    registrar("Telefone vazio e recusado", "Telefone inválido" in html and n_cartoes(html) == 0)
    r, html = consultar("3899139000")  # 10 digitos: prefixo do TEL_NORMAL, NAO pode casar
    registrar("Prefixo do numero (10 digitos) nao casa com outro cliente",
              n_cartoes(html) == 0)

    # ------------------------------------------------------------
    # 8) Isolamento e seguranca
    # ------------------------------------------------------------
    print("\n--- 8) Isolamento e seguranca ---")
    r, html = consultar(TEL_NORMAL)
    registrar("Cliente A nao ve o agendamento exclusivo do cliente OUTRO",
              "15/03/2031" not in html)
    r_outro, html_outro = consultar(TEL_OUTRO)
    registrar("Cliente OUTRO ve somente o proprio agendamento",
              n_cartoes(html_outro) == 1 and "15/03/2031" in html_outro
              and nome_s3 in html_outro)
    r, html = consultar(TEL_PLANO)
    registrar("Cliente de plano nao ve agendamentos de outros clientes",
              "15/03/2031" not in html and n_cartoes(html) == 1)
    r, html = consultar(TEL_NORMAL)
    registrar("Resposta nao contem o telefone completo",
              TEL_NORMAL not in html and "99139-0001" not in html)
    registrar("Resposta mostra o telefone mascarado",
              mascarar_telefone(TEL_NORMAL) in html and mascarar_telefone(TEL_NORMAL) == "(38) 9****-0001",
              mascarar_telefone(TEL_NORMAL))
    links_locais = re.findall(r'(?:href|action)="(/[^"]*)"', html)
    registrar("Resposta nao expoe IDs nem links de cancelamento",
              "/cancelar" not in html and "agendamento_id" not in html
              and not any(re.search(r"\d", link) for link in links_locais),
              f"links locais={links_locais}")
    registrar("Resposta com dados pessoais usa Cache-Control: no-store",
              r.headers.get("Cache-Control") == "no-store")
    r_get = client.get(f"/meus-agendamentos?telefone={TEL_NORMAL}")
    html_get = r_get.get_data(as_text=True)
    registrar("Telefone na URL (GET) e ignorado — nada e listado",
              r_get.status_code == 200 and n_cartoes(html_get) == 0
              and nome_s1 not in html_get and 'name="telefone"' in html_get)
    registrar("Rota publica nao grava sessao do cliente",
              "cliente_plano_id" not in client.get("/meus-agendamentos").request.environ.get("HTTP_COOKIE", ""))
    with client.session_transaction() as sess:
        registrar("Consulta nao cria login (sessao sem cliente_plano_id)",
                  "cliente_plano_id" not in sess)

    # CSRF ativo de verdade: sem token o POST e rejeitado
    app.config["WTF_CSRF_ENABLED"] = True
    r_csrf = app.test_client().post("/meus-agendamentos", data={"telefone": TEL_NORMAL})
    registrar("Com CSRF ativo, POST sem token e rejeitado (app redireciona p/ home) e nada e listado",
              r_csrf.status_code in (302, 400)
              and nome_s1 not in r_csrf.get_data(as_text=True),
              f"status={r_csrf.status_code}")
    app.config["WTF_CSRF_ENABLED"] = False

    # ------------------------------------------------------------
    # 9) Planos NAO foram alterados / 10) Agendamento normal NAO alterado
    # ------------------------------------------------------------
    print("\n--- 9/10) Somente leitura ---")

    def snapshot():
        with app.app_context():
            return {
                "agendamentos": Agendamento.query.count(),
                "financeiros": Financeiro.query.count(),
                "clientes": Cliente.query.count(),
                "planos": [(p.id, p.status, p.data_validade) for p in Plano.query.order_by(Plano.id).all()],
                "beneficios": [(b.id, b.quantidade_utilizada)
                               for b in PlanoBeneficio.query.order_by(PlanoBeneficio.id).all()],
                "fin_status": [(f.id, f.status, f.valor, f.data_pagamento)
                               for f in Financeiro.query.order_by(Financeiro.id).all()],
            }

    antes = snapshot()
    for tel in [TEL_NORMAL, TEL_PLANO, TEL_MISTO, TEL_SEM_AG, TEL_VARIOS,
                TEL_INEXISTENTE, TEL_LEGADO, "123"]:
        for _ in range(2):
            consultar(tel)
    depois = snapshot()
    registrar("Consultas nao alteram agendamentos, clientes nem financeiro",
              antes["agendamentos"] == depois["agendamentos"]
              and antes["clientes"] == depois["clientes"]
              and antes["financeiros"] == depois["financeiros"]
              and antes["fin_status"] == depois["fin_status"])
    registrar("Consultas nao alteram planos (status/validade)", antes["planos"] == depois["planos"])
    registrar("Consultas nao consomem nem devolvem beneficios do plano",
              antes["beneficios"] == depois["beneficios"])

    # O fluxo normal de agendamento continua funcionando e aparece na consulta
    data_nova = proxima_terca(14)
    with app.app_context():
        prof_id = listar_profissionais()[0].id
    TEL_NOVO = "38991390008"
    r_ag = client.post("/agendamento", data={
        "nome": "Cliente Novo", "telefone": "(38) 99139-0008", "data": data_nova,
        "horario": "16:00", "servico": nome_s1, "profissional_id": str(prof_id),
    })
    with app.app_context():
        ag_novo = Agendamento.query.filter_by(telefone=TEL_NOVO).first()
        fin_novo = Financeiro.query.filter_by(agendamento_id=ag_novo.id).first() if ag_novo else None
    registrar("Fluxo normal /agendamento continua criando agendamento + financeiro pendente",
              r_ag.status_code == 200 and ag_novo is not None
              and fin_novo is not None and fin_novo.status == "pendente")
    r, html = consultar("(38) 99139-0008")
    registrar("Agendamento recem criado aparece na consulta",
              n_cartoes(html) == 1 and nome_s1 in html and "16:00" in html)

    # Funcao de servico isolada
    with app.app_context():
        registrar("Servico: telefone invalido devolve listas vazias",
                  listar_agendamentos_por_telefone("123")["total"] == 0
                  and listar_agendamentos_por_telefone(None)["total"] == 0)
        res = listar_agendamentos_por_telefone(TEL_MISTO)
        registrar("Servico: misto tem 1 proximo (plano) e 1 anterior (normal)",
                  len(res["proximos"]) == 1 and res["proximos"][0]["via_plano"] is True
                  and len(res["anteriores"]) == 1 and res["anteriores"][0]["via_plano"] is False
                  and res["total"] == 2)
        registrar("Servico: itens nao carregam IDs nem telefone",
                  all(set(i.keys()) == {"servico", "data", "data_br", "horario", "profissional",
                                        "via_plano", "plano_nome", "valor", "pagamento", "situacao"}
                      for i in res["proximos"] + res["anteriores"]))

    registrar("mascarar_telefone: celular, fixo e invalido",
              mascarar_telefone("38991388394") == "(38) 9****-8394"
              and mascarar_telefone("3899138394") == "(38) ****-8394"
              and mascarar_telefone("123") == ""
              and mascarar_telefone(None) == "")

    print("\n" + "=" * 70)
    passou = sum(1 for _, status, _ in RESULTADOS if status == "PASS")
    falhou = sum(1 for _, status, _ in RESULTADOS if status == "FAIL")
    print(f"TOTAL: {passou} PASS / {falhou} FAIL / {len(RESULTADOS)} testes")
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