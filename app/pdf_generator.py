# app/pdf_generator.py

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import landscape, A4 # ALTERADO: Usando A4 em vez de letter
from reportlab.lib import colors
from reportlab.lib.units import inch, mm # ALTERADO: Adicionado mm para facilitar os cálculos
from io import BytesIO
from datetime import datetime

# --- Função para desenhar o cabeçalho, rodapé e borda em cada página ---
def on_each_page(canvas, doc):
    """
    Função chamada em cada nova página para desenhar elementos estáticos.
    """
    canvas.saveState()
    
    page_width, page_height = landscape(A4)
    
    # --- NOVO: Desenha a borda da página ---
    border_margin = 2 * mm
    canvas.setStrokeColorRGB(0.1, 0.1, 0.1) # Cor cinza escuro para a borda
    canvas.setLineWidth(0.5) # Linha fina
    canvas.rect(
        border_margin,
        border_margin,
        page_width - 2 * border_margin,
        page_height - 2 * border_margin
    )

    # --- Cabeçalho Principal ---
    # Ajustado para o novo layout de margens
    header_y_pos = page_height - (doc.topMargin / 2) - 5
    canvas.setFont('Helvetica-Bold', 14)
    canvas.drawCentredString(page_width / 2, header_y_pos, "Relatório de Pedidos")

    # --- Rodapé ---
    # Ajustado para se alinhar com as novas margens
    footer_y_pos = doc.bottomMargin / 2
    canvas.setFont('Helvetica', 8)
    canvas.drawString(doc.leftMargin, footer_y_pos, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    canvas.drawRightString(page_width - doc.rightMargin, footer_y_pos, f"Página {canvas.getPageNumber()}")

    canvas.restoreState()

def generate_order_report(grouped_pedidos, filter_params):
    """
    Gera um relatório de pedidos agrupado por representante.
    """
    buffer = BytesIO()
    
    # --- ALTERADO: Margens reduzidas para aproveitar o máximo da folha A4 em paisagem ---
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            rightMargin=15, leftMargin=15,
                            topMargin=50, bottomMargin=40)

    styles = getSampleStyleSheet()
    # Estilos de parágrafo ajustados
    style_h2 = ParagraphStyle(name='h2', parent=styles['h2'], fontSize=11, spaceBefore=12, spaceAfter=8)
    style_normal = styles['Normal']
    style_normal.fontSize = 8
    style_normal_small = ParagraphStyle(name='small', parent=styles['Normal'], fontSize=7)
    
    story = []

    # --- Filtros Aplicados ---
    if filter_params:
        filters_text = " | ".join(f"<strong>{key}</strong>: {value}" for key, value in filter_params.items() if value)
        story.append(Paragraph(f"<font size='8'>Filtros Aplicados: {filters_text}</font>", style_normal))
        story.append(Spacer(1, 8))

    # --- Tabela de Resumo Geral ---
    all_pedidos = [p for sublist in grouped_pedidos.values() for p in sublist]
    grand_total_pedidos = len(all_pedidos)
    grand_total_valor = sum(float(p.PD_TTPD or 0) for p in all_pedidos)
    
    summary_data = [
        ['Total de Pedidos no Relatório', f"{grand_total_pedidos}"],
        ['Valor Total no Relatório', f"R$ {grand_total_valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')]
    ]
    # Tabela de resumo com largura maior
    summary_table = Table(summary_data, colWidths=[200, 150])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(summary_table)

    # --- Loop por cada representante para criar sua seção ---
    for i, (rep_nome, pedidos) in enumerate(grouped_pedidos.items()):
        if i > 0:
            story.append(PageBreak())

        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Representante: {rep_nome}", style_h2))

        table_data = [
            ['Nº Pedido', 'Criação', 'Recepção', 'Cliente', 'Cidade/UF', 'Operação', 'Nº Nota', 'Status', 'Valor (R$)']
        ]

        for pedido in pedidos:
            status = 'Bloqueado' if pedido.PD_BLOQ == 'S' else 'Aprovado'
            cidade_uf = 'N/A'
            if pedido.cliente and pedido.cliente.cidade:
                cidade_uf = f"{pedido.cliente.cidade.CI_DENO}/{pedido.cliente.cidade.CI_ESTA}"

            row = [
                pedido.PD_NUME,
                pedido.PD_DATA.strftime('%d/%m/%Y') if pedido.PD_DATA else '',
                pedido.PD_DTRC.strftime('%d/%m/%Y') if pedido.PD_DTRC else '',
                Paragraph(pedido.cliente.CL_NOME if pedido.cliente else 'N/A', style_normal_small),
                Paragraph(cidade_uf, style_normal_small),
                pedido.PD_TPOP,
                pedido.PD_NOTA or '',
                status,
                f"{float(pedido.PD_TTPD or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            ]
            table_data.append(row)
        
        # --- ALTERADO: Larguras de coluna recalculadas para preencher a página ---
        # Largura total disponível: 841.89 (A4) - 15 (LM) - 15 (RM) = 811.89 pt
        table = Table(table_data, colWidths=[60, 60, 60, 221.89, 120, 50, 70, 60, 110])
        
        # --- ALTERADO: Estilo da tabela otimizado (linhas finas, menos padding) ---
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F81BD')), # Azul corporativo
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (8, 1), (8, -1), 'RIGHT'), # Alinha valor à direita
            ('ALIGN', (3, 1), (3, -1), 'LEFT'), # Alinha cliente à esquerda
            ('ALIGN', (4, 1), (4, -1), 'LEFT'), # Alinha cidade à esquerda
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.black), # Linhas da grade mais finas
        ]))
        story.append(table)
        
        sub_total_valor = sum(float(p.PD_TTPD or 0) for p in pedidos)
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f"<b>Total para {rep_nome}:</b> {len(pedidos)} pedido(s), somando <b>R$ {sub_total_valor:,.2f}</b>".replace(',', 'X').replace('.', ',').replace('X', '.'),
            style_normal
        ))

    # Constrói o documento usando a função on_each_page para cabeçalho/rodapé
    doc.build(story, onFirstPage=on_each_page, onLaterPages=on_each_page)
    buffer.seek(0)
    return buffer