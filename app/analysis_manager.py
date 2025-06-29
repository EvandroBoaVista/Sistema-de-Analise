# app/analysis_manager.py

from . import db
from .models import (Pedido, ItemPedido, Produto, Grupo, Cor, Modelo, Dbacida, Cliente,
                     FaturaFiscal, ItemFaturaFiscal, Dbastpop, FichaProduto, AnaliseMargem)
from sqlalchemy import func, case, extract, distinct, desc, select, cast
from sqlalchemy.orm import aliased
from datetime import datetime
from decimal import Decimal


def get_analise_produtos_data(filters):
    """
    Busca e processa todos os dados para a página de Análise de Produtos.
    """
    base_query = db.session.query(
        Produto.PR_CODI,
        Produto.PR_DENO,
        Grupo.GR_DESC,
        func.sum(ItemPedido.DP_QTDE).label('total_qtde'),
        func.sum(ItemPedido.DP_QTDE * ItemPedido.DP_VLUN).label('total_valor'),
    ).select_from(ItemPedido).join(
        Pedido, Pedido.PD_NUME == ItemPedido.DP_NUME
    ).join(
        Produto, Produto.PR_CODI == ItemPedido.DP_PROD
    ).join(
        Grupo, Grupo.GR_CODI == Produto.PR_GRUP, isouter=True
    ).filter(Pedido.PD_DTEM.isnot(None))

    if filters.get('ano'):
        base_query = base_query.filter(extract('year', Pedido.PD_DTEM) == int(filters['ano']))
    if filters.get('mes'):
        base_query = base_query.filter(extract('month', Pedido.PD_DTEM) == int(filters['mes']))
    if filters.get('grupo'):
        base_query = base_query.filter(Produto.PR_GRUP == filters['grupo'])
    if filters.get('cor'):
        base_query = base_query.filter(Produto.PR_COR == filters['cor'])
    if filters.get('modelo'):
        base_query = base_query.filter(Produto.PR_MODE == filters['modelo'])

    produtos_agregados_sub = base_query.group_by(
        Produto.PR_CODI, Produto.PR_DENO, Grupo.GR_DESC
    ).subquery()

    faturamento_total_scalar = db.session.query(
        func.sum(produtos_agregados_sub.c.total_valor)
    ).scalar_subquery()
    
    abc_query = db.session.query(
        produtos_agregados_sub.c.PR_CODI.label('codigo'),
        produtos_agregados_sub.c.PR_DENO.label('descricao'),
        produtos_agregados_sub.c.GR_DESC.label('grupo'),
        produtos_agregados_sub.c.total_qtde.label('qtde'),
        produtos_agregados_sub.c.total_valor.label('valor'),
        (func.sum(produtos_agregados_sub.c.total_valor).over(
            order_by=desc(produtos_agregados_sub.c.total_valor)
        ) * 100 / faturamento_total_scalar).label('percentual_acumulado')
    ).select_from(produtos_agregados_sub).order_by(desc('valor'))

    abc_data_raw = abc_query.all()
    
    abc_data = []
    for produto in abc_data_raw:
        curva = 'C'
        percentual = produto.percentual_acumulado or Decimal('0.0')
        if percentual <= 80:
            curva = 'A'
        elif percentual <= 95:
            curva = 'B'
        abc_data.append({**produto._asdict(), 'curva': curva})

    top_10_produtos = abc_data[:10]
    top_produtos_labels = [p['descricao'][:25] + '...' if len(p['descricao']) > 25 else p['descricao'] for p in top_10_produtos]
    top_produtos_data = [p['valor'] for p in top_10_produtos]

    top_grupos_query = base_query.group_by(Grupo.GR_DESC).order_by(func.sum(ItemPedido.DP_QTDE).desc()).limit(5)
    top_grupos_data_raw = top_grupos_query.all()
    top_grupos_labels = [g.GR_DESC for g in top_grupos_data_raw]
    top_grupos_valores = [g.total_qtde for g in top_grupos_data_raw]

    lead_time_query = db.session.query(
        extract('month', Pedido.PD_DTEM).label('mes'),
        func.avg(func.julianday(Pedido.PD_DTEM) - func.julianday(Pedido.PD_DATA)).label('avg_days')
    ).select_from(ItemPedido)\
     .join(Pedido, Pedido.PD_NUME == ItemPedido.DP_NUME)\
     .join(Produto, Produto.PR_CODI == ItemPedido.DP_PROD)\
     .filter(Pedido.PD_DTEM.isnot(None), Pedido.PD_DATA.isnot(None))
    
    if filters.get('ano'):
        lead_time_query = lead_time_query.filter(extract('year', Pedido.PD_DTEM) == int(filters['ano']))
    if filters.get('mes'):
        lead_time_query = lead_time_query.filter(extract('month', Pedido.PD_DTEM) == int(filters['mes']))
    if filters.get('grupo'):
        lead_time_query = lead_time_query.filter(Produto.PR_GRUP == filters['grupo'])
    if filters.get('cor'):
        lead_time_query = lead_time_query.filter(Produto.PR_COR == filters['cor'])
    if filters.get('modelo'):
        lead_time_query = lead_time_query.filter(Produto.PR_MODE == filters['modelo'])

    monthly_lead_time = lead_time_query.group_by('mes').order_by('mes').all()
    meses_nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    lead_time_labels = [meses_nomes[int(m.mes)-1] for m in monthly_lead_time]
    lead_time_data = [m.avg_days for m in monthly_lead_time]

    return {
        'abc_data': abc_data,
        'top_produtos_labels': top_produtos_labels,
        'top_produtos_data': top_produtos_data,
        'top_grupos_labels': top_grupos_labels,
        'top_grupos_valores': top_grupos_valores,
        'lead_time_labels': lead_time_labels,
        'lead_time_data': lead_time_data,
    }


def get_analise_estados_data(filters):
    """
    Busca e processa todos os dados para a página de Análise de Estados.
    """
    codigos_ecommerce = ['0517', '0163']
    codigos_exportacao = ['0607']
    codigos_nao_fisicos = codigos_ecommerce + codigos_exportacao

    def executar_consulta(ano, mes):
        query = db.session.query(
            func.sum(ItemPedido.DP_QTDE * ItemPedido.DP_VLUN).label('total_valor'),
            func.count(distinct(Pedido.PD_NUME)).label('total_pedidos'),
            func.sum(ItemPedido.DP_QTDE).label('total_itens')
        ).select_from(Pedido)\
        .join(ItemPedido, ItemPedido.DP_NUME == Pedido.PD_NUME)\
        .join(Pedido.cliente.of_type(Cliente))\
        .join(Cliente.cidade.of_type(Dbacida))

        if ano:
            query = query.filter(extract('year', Pedido.PD_DATA) == ano)
        if mes:
            query = query.filter(extract('month', Pedido.PD_DATA) == mes)
        if filters.get('estado'):
            query = query.filter(Dbacida.CI_ESTA == filters['estado'])
        if filters.get('cidade'):
            query = query.filter(Dbacida.CI_CODI == filters['cidade'])
        
        canal = filters.get('canal_venda')
        if canal == 'fisico':
            query = query.filter(Pedido.PD_REPR.notin_(codigos_nao_fisicos))
        elif canal == 'ecommerce':
            query = query.filter(Pedido.PD_REPR.in_(codigos_ecommerce))
        elif canal == 'exportacao':
            query = query.filter(Pedido.PD_REPR.in_(codigos_exportacao))

        if filters.get('estado'):
            query = query.add_columns(Dbacida.CI_DENO.label('localidade')).group_by(Dbacida.CI_DENO)
        else:
            query = query.add_columns(Dbacida.CI_ESTA.label('localidade')).group_by(Dbacida.CI_ESTA)
            
        return query.order_by(db.desc('total_valor')).all()

    ano_selecionado = filters.get('ano', datetime.now().year)
    mes_str = filters.get('mes')
    mes_selecionado = int(mes_str) if mes_str else None

    resultados_atuais = executar_consulta(ano_selecionado, mes_selecionado)
    
    ano_anterior, mes_anterior = (ano_selecionado - 1, 12) if mes_selecionado and mes_selecionado == 1 else (ano_selecionado, (mes_selecionado or 1) - 1)
    
    resultados_anteriores = []
    if mes_selecionado:
        resultados_anteriores = executar_consulta(ano_anterior, mes_anterior)

    def formatar_resultados(resultados):
        return [{
            'localidade': r.localidade,
            'total_valor': f'{r.total_valor or 0:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
            'total_pedidos': r.total_pedidos,
            'total_itens': r.total_itens
        } for r in resultados]

    total_geral_valor = sum(r.total_valor for r in resultados_atuais if r.total_valor)
    total_geral_pedidos = sum(r.total_pedidos for r in resultados_atuais)

    top_10_atuais = resultados_atuais[:10]
    top_10_anteriores = resultados_anteriores[:10]

    return {
        'resultados_atuais': formatar_resultados(resultados_atuais),
        'resultados_anteriores': formatar_resultados(resultados_anteriores),
        'total_geral_valor_fmt': f'{total_geral_valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
        'total_geral_pedidos': total_geral_pedidos,
        'chart_labels_atual': [r.localidade for r in top_10_atuais],
        'chart_data_atual': [r.total_valor for r in top_10_atuais],
        'chart_labels_anterior': [r.localidade for r in top_10_anteriores],
        'chart_data_anterior': [r.total_valor for r in top_10_anteriores],
    }


def get_margem_contribuicao_data(filters, page, per_page=50):
    """
    Busca os dados pré-calculados da margem de contribuição da tabela AnaliseMargem,
    aplicando os filtros selecionados pelo usuário.
    """
    base_query = db.session.query(AnaliseMargem)

    if filters.get('data_inicio'):
        base_query = base_query.filter(AnaliseMargem.data_nf >= filters['data_inicio'])
    if filters.get('data_fim'):
        base_query = base_query.filter(AnaliseMargem.data_nf <= filters['data_fim'])
    if filters.get('grupo'):
        base_query = base_query.filter(AnaliseMargem.grupo_descricao == filters['grupo'])
    if filters.get('subgrupo'):
        base_query = base_query.filter(AnaliseMargem.subgrupo_descricao == filters['subgrupo'])
    if filters.get('modelo'):
        base_query = base_query.filter(AnaliseMargem.modelo_descricao == filters['modelo'])
    if filters.get('status'):
        base_query = base_query.filter(AnaliseMargem.produto_status == filters['status'])

    kpi_query = base_query.with_entities(
        func.sum(AnaliseMargem.total_faturado_nf),
        func.sum(AnaliseMargem.mc_valor)
    ).first()

    total_faturado = kpi_query[0] or Decimal(0)
    total_mc = kpi_query[1] or Decimal(0)
    
    total_custo_liquido = total_faturado - total_mc
    media_mc_perc = (total_mc / total_faturado * 100) if total_faturado > 0 else 0

    kpis = {
        'total_faturado': total_faturado,
        'total_custo_liquido': total_custo_liquido,
        'total_mc': total_mc,
        'media_mc_perc': media_mc_perc
    }
    
    # --- NOVAS CONSULTAS PARA OS RANKINGS ---
    # Top 20 por Valor de Venda
    top_vendas_query = base_query.with_entities(
        AnaliseMargem.produto_desc,
        func.sum(AnaliseMargem.receita_total_item).label('total_venda')
    ).group_by(AnaliseMargem.produto_desc).order_by(desc('total_venda')).limit(20).all()

    # Top 20 por Rentabilidade (Margem de Contribuição em R$)
    top_rentabilidade_query = base_query.with_entities(
        AnaliseMargem.produto_desc,
        func.sum(AnaliseMargem.mc_valor).label('total_margem')
    ).group_by(AnaliseMargem.produto_desc).order_by(desc('total_margem')).limit(20).all()
    # --- FIM DAS NOVAS CONSULTAS ---

    paginated_query = base_query.order_by(AnaliseMargem.data_nf.desc(), AnaliseMargem.nf_numero.desc())
    dados_paginados = paginated_query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        'dados_paginados': dados_paginados,
        'kpis': kpis,
        'top_vendas': top_vendas_query,
        'top_rentabilidade': top_rentabilidade_query
    }


def get_top_produtos_faturamento(filters):
    """
    Busca os 20 produtos com maior faturamento (baseado no valor líquido da nota fiscal)
    dentro de um período específico.
    """
    query = db.session.query(
        ItemFaturaFiscal.nf_produto,
        Produto.PR_DENO,
        func.sum(ItemFaturaFiscal.nf_vrliq).label('total_faturado')
    ).join(
        Produto, ItemFaturaFiscal.nf_produto == Produto.PR_CODI
    ).join(
        FaturaFiscal, ItemFaturaFiscal.fatura_id == FaturaFiscal.id
    ).filter(
        FaturaFiscal.nf_tipo == 'S'
    )

    if filters.get('data_inicio'):
        query = query.filter(FaturaFiscal.nf_data >= filters['data_inicio'])
    if filters.get('data_fim'):
        query = query.filter(FaturaFiscal.nf_data <= filters['data_fim'])

    query = query.group_by(
        ItemFaturaFiscal.nf_produto,
        Produto.PR_DENO
    ).order_by(
        desc('total_faturado')
    ).limit(20)

    return query.all()