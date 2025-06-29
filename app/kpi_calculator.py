# app/kpi_calculator.py

from . import db
from .models import MovimentoFinanceiro, Pedido, ItemPedido, Representante, Cliente
from sqlalchemy import func, case, distinct, extract, and_
from datetime import date, datetime, timedelta
from decimal import Decimal

def get_dashboard_kpis(ano_selecionado, mes_selecionado):
    """
    Calcula os KPIs para o Dashboard principal.
    """
    pedidos_filtrados_subquery = db.session.query(
        Pedido.PD_NUME,
        Pedido.PD_TTPD,
        Pedido.PD_REPR,
        Pedido.PD_DATA,
        Pedido.PD_DTRC,
        Pedido.PD_DTEM
    ).filter(Pedido.PD_DATA.isnot(None))

    if ano_selecionado:
        pedidos_filtrados_subquery = pedidos_filtrados_subquery.filter(extract('year', Pedido.PD_DATA) == ano_selecionado)
    if mes_selecionado:
        pedidos_filtrados_subquery = pedidos_filtrados_subquery.filter(extract('month', Pedido.PD_DATA) == mes_selecionado)
    
    pedidos_filtrados_subquery = pedidos_filtrados_subquery.subquery()

    total_pedidos = db.session.query(func.count(pedidos_filtrados_subquery.c.PD_NUME)).scalar()
    total_faturado_kpi = db.session.query(func.sum(pedidos_filtrados_subquery.c.PD_TTPD)).scalar() or Decimal('0.0')
    
    total_produtos_vendidos = db.session.query(func.sum(ItemPedido.DP_QTDE))\
        .join(pedidos_filtrados_subquery, ItemPedido.DP_NUME == pedidos_filtrados_subquery.c.PD_NUME).scalar() or 0
    
    reps_com_venda = db.session.query(func.count(distinct(pedidos_filtrados_subquery.c.PD_REPR))).scalar() or 0
    
    kpi_lead_time_query = db.session.query(func.avg(func.julianday(pedidos_filtrados_subquery.c.PD_DTEM) - func.julianday(pedidos_filtrados_subquery.c.PD_DTRC)))\
        .filter(pedidos_filtrados_subquery.c.PD_DTEM.isnot(None), pedidos_filtrados_subquery.c.PD_DTRC.isnot(None))
    
    avg_lead_time_recepcao = kpi_lead_time_query.scalar() or 0.0
    
    clientes_ativos = db.session.query(func.count(Cliente.CL_CODI)).filter(func.upper(Cliente.CL_SITU) == 'A').scalar()
    representantes_ativos = db.session.query(func.count(Representante.RP_CODI)).filter(func.upper(Representante.RP_SITU) == 'A').scalar()
    
    return {
        'total_pedidos': total_pedidos,
        'total_faturado': f'{total_faturado_kpi:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
        'total_produtos_vendidos': f'{Decimal(total_produtos_vendidos or 0):,.0f}'.replace(',', '.'),
        'reps_com_venda': reps_com_venda,
        'avg_lead_time_recepcao': f'{avg_lead_time_recepcao:.1f}'.replace('.', ','),
        'clientes_ativos': clientes_ativos,
        'representantes_ativos': representantes_ativos,
    }

def get_pedidos_kpis(ano, mes):
    """
    Calcula os KPIs para a tela de listagem de Pedidos Recepcionados.
    """
    period_filters = [
        Pedido.PD_DATA.isnot(None),
        extract('year', Pedido.PD_DATA) == ano,
        extract('month', Pedido.PD_DATA) == mes
    ]

    kpi_aprovados = db.session.query(func.sum(Pedido.PD_TTPD))\
        .filter(*period_filters, Pedido.PD_BLOQ != 'S').scalar() or Decimal('0.0')

    kpi_bloqueados = db.session.query(func.sum(Pedido.PD_TTPD))\
        .filter(*period_filters, Pedido.PD_BLOQ == 'S').scalar() or Decimal('0.0')
    
    avg_lead_time_recepcao = db.session.query(func.avg(func.julianday(Pedido.PD_DTEM) - func.julianday(Pedido.PD_DTRC)))\
        .filter(Pedido.PD_DTEM.isnot(None), Pedido.PD_DTRC.isnot(None))\
        .filter(*period_filters).scalar() or 0.0
    
    kpi_devolucoes = db.session.query(func.sum(Pedido.PD_TTPD))\
        .filter(Pedido.PD_TPOP == '20', *period_filters).scalar() or Decimal('0.0')

    count_aprovados = db.session.query(func.count(Pedido.PD_NUME)).filter(*period_filters, Pedido.PD_BLOQ != 'S').scalar() or 0
    count_bloqueados = db.session.query(func.count(Pedido.PD_NUME)).filter(*period_filters, Pedido.PD_BLOQ == 'S').scalar() or 0
    total_pedidos_periodo = count_aprovados + count_bloqueados
    kpi_taxa_aprovacao = (count_aprovados / total_pedidos_periodo * 100) if total_pedidos_periodo > 0 else 0.0

    kpi_ticket_medio = db.session.query(func.avg(Pedido.PD_TTPD))\
        .filter(*period_filters, Pedido.PD_BLOQ != 'S').scalar() or Decimal('0.0')
        
    return {
        'kpi_devolucoes_fmt': f'{kpi_devolucoes:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
        'kpi_aprovados_fmt': f'{kpi_aprovados:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
        'kpi_bloqueados_fmt': f'{kpi_bloqueados:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
        'kpi_taxa_aprovacao_fmt': f"{kpi_taxa_aprovacao:.1f}".replace('.', ','),
        'kpi_ticket_medio_fmt': f"{kpi_ticket_medio:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
        'avg_lead_time_recepcao': avg_lead_time_recepcao
    }

def get_contas_a_receber_kpis(processed_data):
    """
    Calcula todos os KPIs para a tela de Contas a Receber a partir de dados já processados.
    """
    today = date.today()
    total_aberto = Decimal('0.0')
    total_vencido = Decimal('0.0')
    total_baixado = Decimal('0.0')
    titulos_vencidos = 0
    total_dias_atraso_baixados = 0
    titulos_baixados_com_atraso = 0
    
    total_valor_filtrado = Decimal('0.0')
    total_notas_filtrado = Decimal('0.0')
    total_papeletas_filtrado = Decimal('0.0')

    for item in processed_data:
        mv = item['movimento']
        status = item['status']
        dias_atraso = item['dias_atraso']
        
        valor = mv.mv_valo or Decimal('0.0')
        total_valor_filtrado += valor
        
        if mv.mv_origem == 'NOTA':
            total_notas_filtrado += valor
        elif mv.mv_origem == 'PAPELETA':
            total_papeletas_filtrado += valor
        
        if status == 'baixado':
            total_baixado += (mv.mv_vlbx or Decimal('0.0'))
            if dias_atraso > 0:
                total_dias_atraso_baixados += dias_atraso
                titulos_baixados_com_atraso += 1
        elif status == 'vencido':
            total_vencido += valor
            titulos_vencidos += 1
        elif status == 'aberto':
            total_aberto += valor

    total_carteira = total_aberto + total_vencido
    tmr = (total_dias_atraso_baixados / titulos_baixados_com_atraso) if titulos_baixados_com_atraso > 0 else 0.0
    
    # CORREÇÃO: A linha que calculava a inadimplência foi removida.
    
    return {
        'total_recebido': total_baixado,
        'total_aberto': total_aberto,
        'total_vencido': total_vencido,
        'total_carteira': total_carteira,
        'titulos_vencidos': titulos_vencidos,
        'tmr': tmr,
        'perc_notas': (total_notas_filtrado / total_valor_filtrado * 100) if total_valor_filtrado > 0 else 0,
        'perc_papeletas': (total_papeletas_filtrado / total_valor_filtrado * 100) if total_valor_filtrado > 0 else 0
    }