# ============================================
# TESTE: FUSO HORÁRIO NA EXIBIÇÃO ("Criado em")
# ============================================
# O banco grava criado_em em UTC (datetime.utcnow) — isso NÃO muda.
# A conversão para o horário de Brasília acontece SOMENTE na exibição, pelo
# filtro Jinja formatar_data_hora_br (utils.py).
#
# Caso real corrigido: um agendamento criado em 20/09/2026 às 22:05 (horário
# de Brasília) era gravado como 21/09/2026 01:05 UTC e aparecia na tela com a
# DATA DO DIA SEGUINTE. Agora aparece 20/09/2026 22:05.
#
# Executar: python teste_fuso_horario.py
# Banco: TEMPORÁRIO (teste_fuso_temp.db) — nunca o de produção.

import os
import sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
BANCO_TEMP = os.path.join(BASE, "teste_fuso_temp.db")
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


def rodar():
    from app import create_app
    from models import db
    from models.agendamento import Agendamento
    from services.barbearia_service import criar_agendamento, listar_profissionais
    from utils import FUSO_BRASIL, formatar_data_hora_br

    print("=" * 70)
    print("TESTE DE FUSO HORARIO NA EXIBICAO (banco temporario)")
    print("=" * 70)

    # ------------------------------------------------------------
    # [1] Função de conversão (caso real relatado)
    # ------------------------------------------------------------
    print("\n[1] formatar_data_hora_br converte UTC -> Brasilia")

    caso = formatar_data_hora_br(datetime(2026, 9, 21, 0, 43))
    registrar(
        "datetime(2026,9,21,0,43) UTC vira '20/09/2026 21:43'",
        caso == "20/09/2026 21:43",
        caso,
    )
    caso_tz = formatar_data_hora_br(datetime(2026, 9, 21, 0, 43, tzinfo=timezone.utc))
    registrar(
        "Mesmo valor com tzinfo=UTC vira '20/09/2026 21:43'",
        caso_tz == "20/09/2026 21:43",
        caso_tz,
    )
    registrar(
        "Nao aparece mais a data UTC crua (21/09/2026 00:43)",
        caso != "21/09/2026 00:43",
        caso,
    )
    registrar("None devolve string vazia", formatar_data_hora_br(None) == "")
    registrar(
        "FUSO_BRASIL e America/Sao_Paulo",
        FUSO_BRASIL.key == "America/Sao_Paulo",
        FUSO_BRASIL.key,
    )
    caso_br = formatar_data_hora_br(datetime(2026, 9, 20, 21, 43, tzinfo=FUSO_BRASIL))
    registrar(
        "Datetime ja em Brasilia nao muda de horario",
        caso_br == "20/09/2026 21:43",
        caso_br,
    )
    registrar(
        "Meia-noite UTC vira 21:00 do dia anterior",
        formatar_data_hora_br(datetime(2026, 9, 21, 0, 0)) == "20/09/2026 21:00",
        formatar_data_hora_br(datetime(2026, 9, 21, 0, 0)),
    )
    registrar(
        "Horario comercial muda apenas a hora, nao o dia",
        formatar_data_hora_br(datetime(2026, 9, 21, 15, 30)) == "21/09/2026 12:30",
        formatar_data_hora_br(datetime(2026, 9, 21, 15, 30)),
    )
    registrar(
        "Nao usa horario de verao em 2026 (Brasil sem DST)",
        formatar_data_hora_br(datetime(2026, 1, 15, 12, 0)) == "15/01/2026 09:00",
        formatar_data_hora_br(datetime(2026, 1, 15, 12, 0)),
    )

    # ------------------------------------------------------------
    # [2] Filtro Jinja registrado na aplicação
    # ------------------------------------------------------------
    print("\n[2] Filtro registrado no Jinja (app.py)")
    app = create_app()
    app.config["TESTING"] = True

    filtro = app.jinja_env.filters.get("formatar_data_hora_br")
    registrar("Filtro 'formatar_data_hora_br' registrado", filtro is not None)
    registrar("Filtro aponta para utils.formatar_data_hora_br",
              filtro is formatar_data_hora_br)
    registrar("Filtro 'formatar_telefone' continua registrado",
              app.jinja_env.filters.get("formatar_telefone") is not None)
    registrar("Filtro 'formatar_moeda' continua registrado",
              app.jinja_env.filters.get("formatar_moeda") is not None)

    # ------------------------------------------------------------
    # [3] End-to-end: a tela /admin/agendamentos mostra o horário convertido
    # ------------------------------------------------------------
    print("\n[3] Tela /admin/agendamentos converte o 'Criado em'")
    with app.app_context():
        profissional = listar_profissionais()[0]
        agendamento = criar_agendamento(
            "Cliente Fuso", "38991380055", "2026-10-05", "10:00", "Corte",
            profissional_id=profissional.id,
        )
        # Simula o caso real: valor gravado em UTC que, em Brasília,
        # corresponde a 20/09/2026 22:05 (dia anterior!)
        agendamento.criado_em = datetime(2026, 9, 21, 1, 5)
        db.session.commit()

        # O armazenamento continua em UTC (nada é convertido no banco)
        novo = criar_agendamento(
            "Cliente Fuso 2", "38991380056", "2026-10-06", "11:00", "Corte",
            profissional_id=profissional.id,
        )
        diferenca = abs((novo.criado_em - datetime.utcnow()).total_seconds())
        registrar("criado_em continua gravado em UTC (utcnow)",
                  diferenca < 300, f"diferenca={int(diferenca)}s")
        registrar("Agendamento Fuso e o segundo continuam no banco",
                  Agendamento.query.count() == 2)

    client = app.test_client()
    with client.session_transaction() as sessao:
        sessao["admin_id"] = 1
        sessao["admin_usuario"] = "admin"

    resposta = client.get("/admin/agendamentos")
    html = resposta.get_data(as_text=True)
    registrar("Pagina de agendamentos responde 200", resposta.status_code == 200)
    registrar("Coluna 'Criado em' continua na tela", "Criado em" in html)
    registrar("Mostra 20/09/2026 22:05 (horario de Brasilia)",
              "20/09/2026 22:05" in html)
    registrar("Nao mostra mais o valor UTC cru 21/09/2026 01:05",
              "21/09/2026 01:05" not in html)

    # ------------------------------------------------------------
    # [4] O template usa o filtro (e nao o strftime cru)
    # ------------------------------------------------------------
    print("\n[4] Templates usam o filtro Jinja")
    caminho = os.path.join(BASE, "templates", "admin_agendamentos.html")
    with open(caminho, encoding="utf-8") as arquivo:
        template = arquivo.read()
    registrar("admin_agendamentos.html usa criado_em|formatar_data_hora_br",
              "criado_em|formatar_data_hora_br" in template)
    registrar("admin_agendamentos.html nao usa mais criado_em.strftime",
              "criado_em.strftime" not in template)

    pasta_templates = os.path.join(BASE, "templates")
    crus = []
    for nome in sorted(os.listdir(pasta_templates)):
        if nome.endswith(".html"):
            with open(os.path.join(pasta_templates, nome), encoding="utf-8") as arquivo:
                if "criado_em.strftime" in arquivo.read():
                    crus.append(nome)
    registrar("Nenhum template exibe criado_em com strftime cru",
              crus == [], ", ".join(crus))

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
