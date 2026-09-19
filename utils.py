# ============================================
# HELPERS DE APRESENTAÇÃO / NORMALIZAÇÃO
# ============================================
# Funções reutilizáveis centralizadas (sem dependência do Flask/DB),
# usadas pelas rotas e templates para padronizar telefone, nome e
# chaves alternativas de busca. Não altera regras de negócio.

import re


def normalizar_telefone(telefone):
    """
    Retorna apenas os dígitos do telefone (sem o código do país +55).

    É o formato preferencial de ARMAZENAMENTO no banco (ex: "38991388394").
    Seguro para valores já formatados: "(38) 99138-8394" -> "38991388394".
    O "+55" só é removido quando compõe o número (12 ou 13 dígitos), para
    não afetar o DDD 55 (ex: "55 99138-8394" permanece com 11 dígitos).
    """
    if telefone is None:
        return ""
    digitos = re.sub(r"\D", "", str(telefone))
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        digitos = digitos[2:]
    return digitos


def formatar_telefone(telefone):
    """
    Formata um telefone no padrão brasileiro para EXIBIÇÃO.

        11 dígitos -> (38) 99138-8394  (celular)
        10 dígitos -> (38) 9913-8834   (fixo)
        Outros     -> devolve os dígitos sem alteração (sem inventar números)

    Funciona com valores já formatados ("(38) 99138-8394") e com o valor
    armazenado apenas com números ("38991388394").
    """
    digitos = normalizar_telefone(telefone)

    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return digitos


# Conectores portugueses que ficam em minúsculo no meio do nome.
# A PRIMEIRA palavra do nome sempre é capitalizada (mesmo que seja um
# conector, ex: "da silva" -> "Da Silva").
_CONECTORES_NOME = {"da", "de", "do", "das", "dos", "e"}


def normalizar_nome(nome):
    """
    Normaliza o nome para o padrão Title Case com conectores em minúsculo.

        "joão da silva"  -> "João da Silva"
        "JOAO DA SILVA"  -> "Joao da Silva"
        "jOaO dA sIlVa"  -> "Joao da Silva"
        "da silva"       -> "Da Silva"   (primeira palavra é capitalizada)
        "joão e maria"   -> "João e Maria"

    Nomes totalmente em minúsculo ou totalmente em maiúsculo são corrigidos.
    """
    if not nome:
        return ""
    normalizadas = []
    for indice, palavra in enumerate(nome.split()):
        minuscula = palavra.lower()
        if indice > 0 and minuscula in _CONECTORES_NOME:
            normalizadas.append(minuscula)
        else:
            normalizadas.append(palavra[:1].upper() + palavra[1:].lower())
    return " ".join(normalizadas)


def nomes_busca_telefone(telefone):
    """
    Lista de variações de armazenamento de um telefone para CONSULTA.

    Cobre registros gravados somente com números (padrão atual) e registros
    antigos gravados formatados, sem alterar o dado no banco.
    """
    digitos = normalizar_telefone(telefone)
    variacoes = {str(telefone or "").strip(), digitos}
    if len(digitos) == 11:
        variacoes.add(f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}")
    elif len(digitos) == 10:
        variacoes.add(f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}")
    return [v for v in variacoes if v]