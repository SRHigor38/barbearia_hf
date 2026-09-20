# ============================================
# TESTE DE PERSISTÊNCIA (LOCAL x PRODUÇÃO/RENDER)
# ============================================
# Prova — SEM TOCAR EM NENHUM BANCO DE PRODUÇÃO — que:
#   1. DATABASE_URL PostgreSQL é respeitada quando configurada.
#   2. SQLite NUNCA substitui DATABASE_URL.
#   3. Produção (APP_ENV=production ou RENDER=true) sem DATABASE_URL falha
#      explicitamente em vez de subir com SQLite (que perderia os dados).
#   4. DATABASE_URL apontando para SQLite é rejeitada em produção.
#   5. Ambiente LOCAL continua podendo usar SQLite normalmente.
#   6. A inicialização da aplicação NÃO executa operações destrutivas
#      (sem drop_all / TRUNCATE / DELETE FROM / DROP TABLE nas tabelas de
#      negócio) e reiniciar o serviço NÃO apaga agendamentos, despesas,
#      serviços, profissionais nem planos.
#
# Executar: python teste_persistencia.py
#
# Banco usado: TEMPORÁRIO (teste_persistencia_temp.db) — nunca o de produção.
# Nenhuma conexão é aberta com o PostgreSQL: as URLs de produção são apenas
# resolvidas/validadas na configuração (nenhum dado é lido ou escrito).

import importlib
import inspect
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
BANCO_TEMP = os.path.join(BASE, "teste_persistencia_temp.db")

# URL fictícia: só para validar a resolução da configuração (nunca conectada)
PG_URL = (
    "postgres://hf_user:senha_secreta@dpg-abc123-a.oregon-postgres.render.com:5432/barbearia"
)
SQLITE_URL = "sqlite:///" + BANCO_TEMP.replace("\\", "/")

RESULTADOS = []


def registrar(nome, resultado, detalhe=""):
    status = "PASS" if resultado else "FAIL"
    RESULTADOS.append((nome, status, detalhe))
    print(f"  [{status}] {nome}" + (f" — {detalhe}" if detalhe else ""))


# ============================================
# CONTROLE DE AMBIENTE (ISOLADO E REVERSÍVEL)
# ============================================

VARIAVEIS = ("DATABASE_URL", "APP_ENV", "RENDER", "PRODUCTION")


def _ambiente_atual():
    return {chave: os.environ.get(chave) for chave in VARIAVEIS}


def _definir_ambiente(database_url=None, app_env=None, render=None, production=None):
    """Define (ou remove) as variáveis que a configuração de banco usa."""
    valores = {
        "DATABASE_URL": database_url,
        "APP_ENV": app_env,
        "RENDER": render,
        "PRODUCTION": production,
    }
    for chave, valor in valores.items():
        if valor is None:
            os.environ.pop(chave, None)
        else:
            os.environ[chave] = valor


def carregar_config(**kwargs):
    """
    Recarrega config.py com o ambiente indicado e devolve a classe Config.

    O load_dotenv() é neutralizado ANTES de carregar o módulo para que o
    arquivo .env local não interfira: o teste controla 100% do ambiente.
    """
    import dotenv

    dotenv.load_dotenv = lambda *args, **kargs: None

    _definir_ambiente(**kwargs)

    import config

    importlib.reload(config)
    return config.Config


def config_ou_erro(**kwargs):
    """Retorna (mensagem_de_erro, config). Um dos dois é sempre None."""
    try:
        return None, carregar_config(**kwargs)
    except RuntimeError as erro:
        return str(erro), None


# ============================================
# PARTE 1: RESOLUÇÃO DE BANCO (LOCAL x PRODUÇÃO)
# ============================================


def testes_configuracao():
    print("\n[PARTE 1] Resolucao do banco de dados (config.py)")

    # --- Produção com APP_ENV=production e PostgreSQL ---
    erro, cfg = config_ou_erro(database_url=PG_URL, app_env="production")
    registrar("Producao com PostgreSQL nao falha", erro is None, erro or "")
    if cfg is None:
        return

    uri = cfg.SQLALCHEMY_DATABASE_URI
    registrar(
        "DATABASE_URL PostgreSQL e respeitada (APP_ENV=production)",
        uri.startswith("postgresql+psycopg2://"),
        f"uri={uri.split('@')[-1] if '@' in uri else uri}",
    )
    registrar("SQLite NAO substitui DATABASE_URL", "sqlite" not in uri.lower(), uri[:40])
    registrar("Host/banco originais preservados",
              "dpg-abc123-a.oregon-postgres.render.com" in uri and uri.endswith("/barbearia"))
    registrar("Senha preservada na URI", "senha_secreta" in uri)
    registrar("BANCO_POSTGRES = True", cfg.BANCO_POSTGRES is True)
    registrar("PRODUCAO detectada por APP_ENV=production", cfg.PRODUCAO is True)

    # --- Produção detectada pelo próprio Render (RENDER=true) ---
    erro, cfg = config_ou_erro(database_url=PG_URL, render="true")
    registrar("PRODUCAO detectada por RENDER=true (sem APP_ENV)", cfg is not None and cfg.PRODUCAO is True)
    registrar("PostgreSQL mantido quando so RENDER=true",
              cfg is not None and cfg.SQLALCHEMY_DATABASE_URI.startswith("postgresql+psycopg2://"))

    # --- Local/desenvolvimento COM DATABASE_URL: nunca troca por SQLite ---
    erro, cfg = config_ou_erro(database_url=PG_URL, app_env="development")
    registrar("Local com DATABASE_URL continua usando PostgreSQL",
              cfg is not None and cfg.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg2://hf_user:senha_secreta@dpg-abc123-a.oregon-postgres.render.com:5432/barbearia")

    # --- Produção SEM DATABASE_URL: falha explícita (nada de SQLite) ---
    erro, cfg = config_ou_erro(app_env="production")
    registrar("Producao sem DATABASE_URL falha (nao usa SQLite)",
              cfg is None and erro is not None)
    registrar("Mensagem de erro orienta a configurar DATABASE_URL",
              bool(erro) and "DATABASE_URL" in erro and "PostgreSQL" in erro)

    erro, cfg = config_ou_erro(render="true")
    registrar("Render sem DATABASE_URL falha (nao usa SQLite)",
              cfg is None and erro is not None and "DATABASE_URL" in erro)

    # --- Produção com DATABASE_URL apontando para SQLite: rejeitada ---
    erro, cfg = config_ou_erro(database_url=SQLITE_URL, app_env="production")
    registrar("SQLite como DATABASE_URL de producao e rejeitado",
              cfg is None and erro is not None and "SQLite" in erro)

    # --- Local/desenvolvimento sem DATABASE_URL: SQLite permitido ---
    erro, cfg = config_ou_erro()
    registrar("Local sem DATABASE_URL usa SQLite (desenvolvimento)",
              cfg is not None and cfg.SQLALCHEMY_DATABASE_URI.startswith("sqlite"))
    registrar("Local nao e identificado como producao",
              cfg is not None and cfg.PRODUCAO is False)

    erro, cfg = config_ou_erro(database_url=SQLITE_URL, app_env="development")
    registrar("Local com DATABASE_URL SQLite continua funcionando",
              cfg is not None and cfg.SQLALCHEMY_DATABASE_URI == SQLITE_URL)


# ============================================
# PARTE 2: RESTART DO SERVIÇO NÃO APAGA DADOS
# ============================================


def _contagem(modelos):
    """Conta registros das tabelas de negócio (clientes, planos, financeiro...)."""
    return {nome: modelo.query.count() for nome, modelo in modelos.items()}


def testes_restart():
    print("\n[PARTE 2] Reinicio/sleep do servico preserva os dados")

    carregar_config(database_url=SQLITE_URL, app_env="development")

    from app import create_app
    from models.agendamento import Agendamento
    from models.cliente import Cliente
    from models.despesa import Despesa
    from models.financeiro import Financeiro
    from models.plano import Plano
    from models.plano_tipo import PlanoTipo
    from models.profissional import Profissional
    from models.servico import Servico
    from services.barbearia_service import criar_agendamento, listar_profissionais
    from services.financeiro_service import registrar_despesa

    modelos = {
        "agendamentos": Agendamento,
        "clientes": Cliente,
        "despesas": Despesa,
        "financeiro": Financeiro,
        "planos": Plano,
        "planos_tipos": PlanoTipo,
        "profissionais": Profissional,
        "servicos": Servico,
    }

    # Primeira instância (o import de app.py já criou outra): estado inicial
    app = create_app()
    with app.app_context():
        registrar("Aplicacao inicia sem excecao", app is not None)

        prof = listar_profissionais()[0]
        agendamento = criar_agendamento(
            nome="Cliente Persistente",
            telefone="(11) 90000-0001",
            data="2026-09-22",
            horario="10:00",
            servico="Corte",
            profissional_id=prof.id,
        )
        registrar("Agendamento criado", agendamento is not None and agendamento.id is not None)

        despesa, erro_despesa = registrar_despesa(
            "Produtos de teste", "Produtos", 50.0, "2026-09-01"
        )
        registrar("Despesa criada", despesa is not None, erro_despesa or "")

        antes = _contagem(modelos)
        id_agendamento = agendamento.id
        registrar("1 agendamento registrado", antes["agendamentos"] == 1)
        registrar("5 servicos iniciais (sem duplicar semente)", antes["servicos"] == 5)
        registrar("8 planos pre-definidos (sem duplicar semente)", antes["planos_tipos"] == 8)

    # Simula o sleep/restart do Render: nova instância da app, MESMO banco
    app2 = create_app()
    with app2.app_context():
        depois = _contagem(modelos)

        registrar(
            "Restart preserva agendamentos (nao desaparecem)",
            depois["agendamentos"] == antes["agendamentos"] == 1,
            f"antes={antes['agendamentos']} depois={depois['agendamentos']}",
        )
        registrar("Restart preserva despesas", depois["despesas"] == antes["despesas"] == 1)
        registrar("Restart preserva financeiro", depois["financeiro"] == antes["financeiro"])
        registrar("Restart preserva servicos", depois["servicos"] == antes["servicos"] == 5)
        registrar("Restart preserva profissionais",
                  depois["profissionais"] == antes["profissionais"] == 1)
        registrar("Restart preserva planos e tipos",
                  depois["planos"] == antes["planos"] and depois["planos_tipos"] == 8)
        registrar("Restart preserva clientes", depois["clientes"] == antes["clientes"])

        agendamento2 = Agendamento.query.get(id_agendamento)
        registrar(
            "Agendamento intacto apos restart (mesmo id e dados)",
            agendamento2 is not None
            and agendamento2.nome == "Cliente Persistente"
            and agendamento2.horario == "10:00"
            and agendamento2.servico == "Corte",
        )

    print("  (banco temporario de teste: %s)" % os.path.basename(BANCO_TEMP))


# ============================================
# PARTE 3: AUDITORIA ESTÁTICA DO STARTUP
# ============================================
# Verifica no CÓDIGO-FONTE das funções de inicialização/migração que não
# existe nenhuma operação destrutiva nas tabelas de negócio.

TABELAS_NEGOCIO = [
    "admin", "agendamento", "agendamento_servico", "bloqueio", "cliente",
    "despesa", "financeiro", "plano", "plano_beneficio", "plano_tipo",
    "plano_tipo_beneficio", "profissional", "servico",
]

PADROES_PROIBIDOS = {
    "drop_all": r"drop_all\s*\(",
    "TRUNCATE": r"\bTRUNCATE\b",
    "DELETE FROM": r"\bDELETE\s+FROM\b",
    "DROP TABLE de tabela de negocio": (
        r"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:" + "|".join(TABELAS_NEGOCIO) + r")\b"
    ),
}


def testes_estaticos():
    print("\n[PARTE 3] Auditoria estatica: startup nao e destrutivo")

    import app as app_mod
    import config as config_mod
    import services.barbearia_service as servico
    import services.financeiro_service as financeiro

    funcoes = [
        ("app.create_app", app_mod.create_app),
        ("app.registrar_banco_em_uso", app_mod.registrar_banco_em_uso),
        ("barbearia_service.criar_banco_e_popular", servico.criar_banco_e_popular),
        ("barbearia_service.criar_planos_predefinidos", servico.criar_planos_predefinidos),
        ("financeiro_service.aplicar_migracoes", financeiro.aplicar_migracoes),
        ("financeiro_service._remover_not_null_agendamento",
         financeiro._remover_not_null_agendamento),
        ("financeiro_service._recriar_financeiro_sqlite",
         financeiro._recriar_financeiro_sqlite),
    ]

    for nome, funcao in funcoes:
        fonte = inspect.getsource(funcao)
        # Ignora linhas de comentario para nao gerar falso positivo
        codigo = "\n".join(
            linha for linha in fonte.splitlines() if not linha.strip().startswith("#")
        )
        encontrados = [
            rotulo
            for rotulo, padrao in PADROES_PROIBIDOS.items()
            if re.search(padrao, codigo, re.IGNORECASE)
        ]
        registrar(
            f"{nome}: sem operacao destrutiva",
            not encontrados,
            f"encontrado: {encontrados}" if encontrados else "",
        )

    # Em PostgreSQL o startup apenas ADICIONA colunas / remove NOT NULL:
    # a reconstrução da tabela (com DROP/RENAME) existe só para SQLite (dev).
    fonte_migracao = inspect.getsource(financeiro._remover_not_null_agendamento)
    registrar(
        "Migrations: PostgreSQL nunca reconstroi/apaga tabelas",
        'dialect.name == "sqlite"' in fonte_migracao and "DROP NOT NULL" in fonte_migracao,
    )
    fonte_sqlite = inspect.getsource(financeiro._recriar_financeiro_sqlite)
    registrar(
        "DROP TABLE existe apenas para a tabela temporaria legado (SQLite/dev)",
        "DROP TABLE financeiro_legado" in fonte_sqlite
        and "_recriar_financeiro_sqlite()" in fonte_migracao,
    )

    # Diagnóstico do banco em uso aparece nos logs do Render
    registrar(
        "Startup registra o banco em uso nos logs",
        "registrar_banco_em_uso" in inspect.getsource(app_mod.create_app),
    )

    # config.py não contém nenhuma rotina de apagar/recriar banco
    registrar(
        "config.py sem drop_all / DROP TABLE",
        not re.search(r"drop_all|DROP\s+TABLE", inspect.getsource(config_mod), re.IGNORECASE),
    )
    # O fallback SQLite fica no ramo NÃO-produção da configuração
    fonte_config = inspect.getsource(config_mod.Config)
    registrar(
        "Fallback SQLite existe apenas fora da producao",
        "elif PRODUCAO:" in fonte_config and 'SQLALCHEMY_DATABASE_URI = "sqlite:///"' in fonte_config,
    )


def rodar():
    print("=" * 70)
    print("TESTES DE PERSISTENCIA HF BARBEARIA (nenhum banco de producao e tocado)")
    print("=" * 70)

    ambiente = _ambiente_atual()
    try:
        testes_configuracao()
        testes_restart()
        testes_estaticos()
    finally:
        for chave, valor in ambiente.items():
            if valor is None:
                os.environ.pop(chave, None)
            else:
                os.environ[chave] = valor

    print("\n" + "=" * 70)
    passou = sum(1 for _, status, _ in RESULTADOS if status == "PASS")
    falhou = sum(1 for _, status, _ in RESULTADOS if status == "FAIL")
    print(f"TOTAL: {passou} PASS / {falhou} FAIL / {len(RESULTADOS)} testes")
    return falhou == 0, passou, falhou


if __name__ == "__main__":
    if os.path.exists(BANCO_TEMP):
        try:
            os.remove(BANCO_TEMP)
        except PermissionError:
            pass

    ok, p, f = rodar()
    print(f"\nRESULTADO GERAL: {'APROVADO' if ok else 'COM FALHAS'} ({p} PASS / {f} FAIL)")

    try:
        if os.path.exists(BANCO_TEMP):
            os.remove(BANCO_TEMP)
    except PermissionError:
        pass
    sys.exit(0 if ok else 1)


