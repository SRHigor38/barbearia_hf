# ============================================
# SERVIÇO: Geração de Relatório PDF
# ============================================
# Gera o relatório financeiro em PDF usando reportlab
# (biblioteca 100% Python, compatível com Render/PostgreSQL,
# sem depender de ferramentas instaladas no servidor).

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

from services.financeiro_service import formatar_moeda, nome_forma_pagamento


def gerar_relatorio_pdf(data_inicio, data_fim, indicadores, movimentacoes):
    """
    Gera o PDF do relatório financeiro do período.
    Retorna um buffer (BytesIO) pronto para send_file.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "Titulo", parent=estilos["Title"], fontSize=18,
        textColor=colors.HexColor("#1a1a1a"), alignment=TA_CENTER, spaceAfter=2,
    )
    estilo_subtitulo = ParagraphStyle(
        "Subtitulo", parent=estilos["Normal"], fontSize=11,
        textColor=colors.HexColor("#555555"), alignment=TA_CENTER, spaceAfter=8,
    )
    estilo_secao = ParagraphStyle(
        "Secao", parent=estilos["Heading2"], fontSize=13,
        textColor=colors.HexColor("#1a1a1a"), spaceBefore=12, spaceAfter=6,
    )
    estilo_celula = ParagraphStyle(
        "Celula", parent=estilos["Normal"], fontSize=9, leading=11,
    )

    elementos = []

    # Cabeçalho
    elementos.append(Paragraph("HF BARBEARIA", estilo_titulo))
    elementos.append(Paragraph("RELATÓRIO FINANCEIRO", estilo_subtitulo))
    elementos.append(Paragraph(
        f"Período: {data_inicio} até {data_fim}", estilo_subtitulo
    ))
    elementos.append(Spacer(1, 4 * mm))

    # Resumo financeiro
    elementos.append(Paragraph("RESUMO FINANCEIRO", estilo_secao))
    resumo = [
        ["Indicador", "Valor"],
        ["Faturamento Bruto", formatar_moeda(indicadores["receita_bruta"])],
        ["Total de Despesas", formatar_moeda(indicadores["despesas_total"])],
        ["Taxas de Maquininha", formatar_moeda(indicadores["despesas_taxas"])],
        ["Lucro Líquido", formatar_moeda(indicadores["lucro_liquido"])],
    ]
    tabela_resumo = Table(resumo, colWidths=[90 * mm, 80 * mm])
    tabela_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#222222")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, -2), colors.HexColor("#f7f7f7")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 4 * mm))

    return _agregar_detalle(doc, elementos, estilos, estilo_celula, estilo_secao,
                            indicadores, movimentacoes, buffer)
def _agregar_detalle(doc, elementos, estilos, estilo_celula, estilo_secao,
                     indicadores, movimentacoes, buffer):
    """Constrói as tabelas de detalhe (receitas/despesas) e o resumo final."""
    elementos.append(Paragraph("DETALHAMENTO DAS MOVIMENTAÇÕES", estilo_secao))

    receitas = [m for m in movimentacoes if m["tipo"] == "receita"]
    despesas = [m for m in movimentacoes if m["tipo"] == "despesa"]

    # Receitas
    if receitas:
        elementos.append(Paragraph(f"Receitas ({len(receitas)})", estilo_secao))
        dados_receitas = [["Data", "Descrição", "Origem", "Pgto.", "Valor"]]
        for r in receitas:
            dados_receitas.append([
                r["data"],
                Paragraph(str(r["descricao"])[:70], estilo_celula),
                r["origem"],
                nome_forma_pagamento(r["forma_pagamento"]),
                formatar_moeda(r["valor"]),
            ])
        tabela_rec = Table(dados_receitas,
                           colWidths=[22 * mm, 70 * mm, 32 * mm, 22 * mm, 28 * mm])
        tabela_rec.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5d1a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elementos.append(tabela_rec)
    else:
        elementos.append(Paragraph("<i>Nenhuma receita no período.</i>", estilos["Normal"]))

    # Despesas
    if despesas:
        elementos.append(Paragraph(f"Despesas ({len(despesas)})", estilo_secao))
        dados_desp = [["Data", "Descrição", "Categoria", "Valor"]]
        for d in despesas:
            dados_desp.append([
                d["data"],
                Paragraph(str(d["descricao"])[:70], estilo_celula),
                d["origem"],
                formatar_moeda(d["valor"]),
            ])
        tabela_desp = Table(dados_desp,
                            colWidths=[22 * mm, 80 * mm, 44 * mm, 28 * mm])
        tabela_desp.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8b1a1a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elementos.append(tabela_desp)
    else:
        elementos.append(Paragraph("<i>Nenhuma despesa no período.</i>", estilos["Normal"]))

    # Rodapé com totais
    elementos.append(Spacer(1, 6 * mm))
    resumo_final = [
        ["RECEITAS", formatar_moeda(indicadores["receita_bruta"])],
        ["DESPESAS", formatar_moeda(indicadores["despesas_total"])],
        ["LUCRO LÍQUIDO", formatar_moeda(indicadores["lucro_liquido"])],
    ]
    tabela_final = Table(resumo_final, colWidths=[90 * mm, 80 * mm])
    tabela_final.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#222222")),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabela_final)

    elementos.append(Spacer(1, 8 * mm))
    elementos.append(Paragraph(
        f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} — HF Barbearia",
        estilos["Normal"],
    ))

    doc.build(elementos)
    buffer.seek(0)
    return buffer