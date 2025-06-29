# app/routes.py

import os
import threading
from flask import render_template, request, flash, redirect, url_for, current_app, Response
from sqlalchemy.orm import joinedload
from sqlalchemy import func, extract, desc, and_, or_, case, distinct
from datetime import datetime, date, timedelta
from collections import OrderedDict
from itertools import groupby
from decimal import Decimal, InvalidOperation
from . import db
from .config_utils import save_config, load_config
from .importer import import_data
from .pdf_generator import generate_order_report
# Importação dos módulos de lógica de negócio
from .kpi_calculator import get_dashboard_kpis, get_pedidos_kpis, get_contas_a_receber_kpis
from .analysis_manager import (get_analise_produtos_data, get_analise_estados_data,
                               get_margem_contribuicao_data, get_top_produtos_faturamento)
from .query_manager import get_pedidos_recepcionados, get_relatorio_itens_vendidos, get_dados_para_relatorio_pdf, get_dados_filtros_comuns
from . import faturamento_manager

# Importação dos modelos necessários
from .models import (Pedido, ItemPedido, Produto, Cliente, Representante, Dbacida,
                     Grupo, Cor, Modelo, HistoricoPedido, Dbastpop, PedidoExcluido,
                     MovimentoFinanceiro, FaturaFiscal, AnaliseMargem, Dbassubg)


@current_app.route('/')
def index():
    return redirect(url_for('dashboard'))


@current_app.route('/dashboard')
def dashboard():
    hoje = datetime.now()
    ano_selecionado = request.args.get('ano', default=hoje.year, type=int)

    mes_selecionado_str = request.args.get('mes')
    if mes_selecionado_str == '':
        mes_selecionado = None
    elif mes_selecionado_str is None:
        mes_selecionado = hoje.month
    else:
        mes_selecionado = int(mes_selecionado_str)

    kpis = get_dashboard_kpis(ano_selecionado, mes_selecionado)

    anos_query = db.session.query(extract('year', Pedido.PD_DATA)).filter(Pedido.PD_DATA.isnot(None)).distinct().order_by(extract('year', Pedido.PD_DATA).desc())
    anos_disponiveis = [ano[0] for ano in anos_query.all() if ano[0]]
    if not anos_disponiveis:
        anos_disponiveis = [hoje.year]

    meses_nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

    monthly_stats_query = db.session.query(
        extract('month', Pedido.PD_DATA).label('mes'),
        func.sum(Pedido.PD_TTPD).label('total_valor'),
        func.count(distinct(Pedido.PD_NUME)).label('total_pedidos'),
        func.sum(ItemPedido.DP_QTDE).label('total_itens')
    ).join(ItemPedido, ItemPedido.DP_NUME == Pedido.PD_NUME)\
    .filter(
        Pedido.PD_DATA.isnot(None),
        extract('year', Pedido.PD_DATA) == ano_selecionado
    ).group_by('mes').order_by('mes').all()

    stats_map = {stat.mes: stat for stat in monthly_stats_query}

    chart_labels = meses_nomes
    faturamento_data = []
    avg_items_data = []

    for i in range(1, 13):
        stat = stats_map.get(i)
        if stat and stat.total_pedidos > 0:
            faturamento_data.append(stat.total_valor or 0)
            avg_items_data.append(stat.total_itens / stat.total_pedidos)
        else:
            faturamento_data.append(0)
            avg_items_data.append(0)

    pedidos_filtrados = Pedido.query.filter(extract('year', Pedido.PD_DATA) == ano_selecionado)
    if mes_selecionado:
        pedidos_filtrados = pedidos_filtrados.filter(extract('month', Pedido.PD_DATA) == mes_selecionado)

    if pedidos_filtrados.first():
        pedidos_filtrados_subquery = pedidos_filtrados.with_entities(Pedido.PD_TTPD, Pedido.PD_TPOP, Pedido.PD_REPR).subquery()
        
        vendas_por_operacao = db.session.query(
            Dbastpop.TO_DESC, func.sum(pedidos_filtrados_subquery.c.PD_TTPD)
        ).join(Dbastpop, Dbastpop.TO_CODI == pedidos_filtrados_subquery.c.PD_TPOP)\
        .group_by(Dbastpop.TO_DESC)\
        .order_by(func.sum(pedidos_filtrados_subquery.c.PD_TTPD).desc()).all()
        
        operacao_labels = [desc for desc, _ in vendas_por_operacao]
        operacao_data = [valor for _, valor in vendas_por_operacao]

        top_representantes = db.session.query(
            Representante.RP_NOME, func.sum(pedidos_filtrados_subquery.c.PD_TTPD)
        ).join(Representante, Representante.RP_CODI == pedidos_filtrados_subquery.c.PD_REPR)\
        .group_by(Representante.RP_NOME)\
        .order_by(func.sum(pedidos_filtrados_subquery.c.PD_TTPD).desc()).limit(10).all()
        
        top_reps_labels = [nome for nome, _ in top_representantes]
        top_reps_data = [valor for _, valor in top_representantes]
    else:
        operacao_labels, operacao_data, top_reps_labels, top_reps_data = [], [], [], []

    return render_template(
        'dashboard.html',
        title='Dashboard',
        kpis=kpis,
        anos_disponiveis=anos_disponiveis,
        ano_selecionado=ano_selecionado,
        mes_selecionado=mes_selecionado,
        chart_labels=chart_labels,
        faturamento_data=faturamento_data,
        avg_items_data=avg_items_data,
        operacao_labels=operacao_labels,
        operacao_data=operacao_data,
        top_reps_labels=top_reps_labels,
        top_reps_data=top_reps_data
    )


@current_app.route('/configurar', methods=['GET', 'POST'])
def configurar():
    config = load_config()
    if request.method == 'POST':
        path = request.form.get('dbf_path', '').strip()
        if not path:
            flash('O campo de caminho não pode estar vazio.', 'warning')
        elif os.path.isdir(path):
            save_config({'dbf_path': path})
            flash('Caminho da rede salvo com sucesso!', 'success')
        else:
            flash(f'Erro: O caminho "{path}" não foi encontrado ou não é um diretório válido.', 'danger')
        return redirect(url_for('configurar'))
    return render_template('configurar.html', current_path=config.get('dbf_path', ''), title='Configurações')


@current_app.route('/iniciar-importacao', methods=['POST'])
def iniciar_importacao():
    import_thread = threading.Thread(target=import_data)
    import_thread.start()
    flash('A importação foi iniciada em segundo plano. Os dados atualizados aparecerão em alguns instantes.', 'info')
    return redirect(url_for('configurar'))


@current_app.route('/pedidos')
def listar_pedidos():
    hoje = datetime.now()
    page = request.args.get('page', 1, type=int)
    
    current_filters = {
        'ano': request.args.get('ano', default=hoje.year, type=int),
        'mes': request.args.get('mes', default=hoje.month, type=int),
        'q': request.args.get('q', '', type=str),
        'representante': request.args.get('representante', '', type=str),
        'tipo_operacao': request.args.get('tipo_operacao', '', type=str),
        'bloqueado': request.args.get('bloqueado', '', type=str),
        'repr_situ': request.args.get('repr_situ', '', type=str)
    }

    kpis = get_pedidos_kpis(current_filters['ano'], current_filters['mes'])
    pedidos_paginados = get_pedidos_recepcionados(current_filters, page)
    dados_filtros = get_dados_filtros_comuns()

    return render_template(
        'pedidos.html',
        pedidos_paginados=pedidos_paginados,
        title='Pedidos Recepcionados',
        current_filters=current_filters,
        ano_selecionado=current_filters['ano'],
        mes_selecionado=current_filters['mes'],
        **dados_filtros,
        **kpis
    )


@current_app.route('/pedidos/excluidos')
def listar_pedidos_excluidos():
    page = request.args.get('page', 1, type=int)
    pedidos_query = PedidoExcluido.query.options(
        joinedload(PedidoExcluido.cliente),
        joinedload(PedidoExcluido.representante)
    ).order_by(PedidoExcluido.data_importacao.desc())
    pedidos_paginados = pedidos_query.paginate(page=page, per_page=50, error_out=False)
    return render_template('pedidos_excluidos.html',
                           pedidos_paginados=pedidos_paginados,
                           title="Pedidos Excluídos")


@current_app.route('/pedido/<numero_pedido>')
def detalhe_pedido(numero_pedido):
    pedido = Pedido.query.options(joinedload(Pedido.cliente).joinedload(Cliente.cidade)).filter_by(PD_NUME=numero_pedido).first_or_404()
    itens = ItemPedido.query.filter_by(DP_NUME=numero_pedido).options(joinedload(ItemPedido.produto).joinedload(Produto.grupo), joinedload(ItemPedido.produto).joinedload(Produto.cor), joinedload(ItemPedido.produto).joinedload(Produto.modelo)).all()

    dias_criacao_recepcao = None
    if pedido.PD_DATA and pedido.PD_DTRC:
        dias_criacao_recepcao = (pedido.PD_DTRC - pedido.PD_DATA).days

    dias_recepcao_faturamento = None
    if pedido.PD_DTRC and pedido.PD_DTEM:
        dias_recepcao_faturamento = (pedido.PD_DTEM - pedido.PD_DTRC).days

    return render_template('detalhe_pedido.html',
                           pedido=pedido,
                           itens=itens,
                           title=f'Pedido {numero_pedido}',
                           HistoricoPedido=HistoricoPedido,
                           dias_criacao_recepcao=dias_criacao_recepcao,
                           dias_recepcao_faturamento=dias_recepcao_faturamento)


@current_app.route('/pedido/excluido/<numero_pedido>')
def detalhe_pedido_excluido(numero_pedido):
    pedido = PedidoExcluido.query.filter_by(PD_NUME=numero_pedido).first_or_404()
    
    historicos = HistoricoPedido.query.filter_by(PEDIDO=pedido.PD_NUME)\
        .order_by(HistoricoPedido.HORAACESSO.desc()).all()
    
    return render_template('detalhe_pedido_excluido.html',
                           pedido=pedido,
                           historicos=historicos,
                           title=f"Detalhe do Pedido Excluído {numero_pedido}")


@current_app.route('/analise/produtos')
def analise_produtos():
    page = request.args.get('page', 1, type=int)
    current_filters = {
        'ano': request.args.get('ano'),
        'mes': request.args.get('mes'),
        'grupo': request.args.get('grupo', ''),
        'cor': request.args.get('cor', ''),
        'modelo': request.args.get('modelo', '')
    }

    data = get_analise_produtos_data(current_filters)

    start = (page - 1) * 50
    end = start + 50
    paginated_abc_data = data['abc_data'][start:end]
    from flask_paginate import Pagination
    pagination = Pagination(page=page, total=len(data['abc_data']), per_page=50, css_framework='bootstrap5')

    anos_disponiveis = [ano[0] for ano in db.session.query(extract('year', Pedido.PD_DTEM)).filter(Pedido.PD_DTEM.isnot(None)).distinct().order_by(extract('year', Pedido.PD_DTEM).desc()).all() if ano[0]]
    grupos, cores, modelos = Grupo.query.order_by(Grupo.GR_DESC).all(), Cor.query.order_by(Cor.CO_DESC).all(), Modelo.query.order_by(Modelo.MO_DESC).all()

    return render_template(
        'analise_produtos.html',
        title="Análise de Produtos",
        produtos_analise=paginated_abc_data,
        pagination=pagination,
        anos_disponiveis=anos_disponiveis,
        grupos=grupos, cores=cores, modelos=modelos,
        current_filters=current_filters,
        **data
    )


@current_app.route('/analise/top-produtos')
def analise_top_produtos():
    filters = {
        'data_inicio': request.args.get('data_inicio'),
        'data_fim': request.args.get('data_fim')
    }
    top_produtos = get_top_produtos_faturamento(filters)
    return render_template(
        'analise_top_produtos.html',
        title="Top 20 Produtos por Faturamento",
        top_produtos=top_produtos,
        current_filters=filters
    )


@current_app.route('/relatorio/itens-vendidos')
def relatorio_itens_vendidos():
    page = request.args.get('page', 1, type=int)
    current_filters = {
        'data_inicio': request.args.get('data_inicio'),
        'data_fim': request.args.get('data_fim')
    }
    
    itens_paginados = get_relatorio_itens_vendidos(current_filters, page)
    
    return render_template('itens_vendidos.html',
                           title="Relatório de Itens Vendidos",
                           itens_paginados=itens_paginados,
                           current_filters=current_filters)


@current_app.route('/analise/estados')
def analise_estados():
    hoje = datetime.now()
    filters = {
        'ano': request.args.get('ano', default=hoje.year, type=int),
        'mes': request.args.get('mes'),
        'estado': request.args.get('estado', ''),
        'cidade': request.args.get('cidade', ''),
        'canal_venda': request.args.get('canal_venda', 'todos')
    }
    
    data = get_analise_estados_data(filters)
    
    dados_filtros = get_dados_filtros_comuns()
    estados_disponiveis = [e[0] for e in db.session.query(Dbacida.CI_ESTA).distinct().order_by(Dbacida.CI_ESTA).all()]
    cidades_disponiveis = db.session.query(Dbacida.CI_CODI, Dbacida.CI_DENO, Dbacida.CI_ESTA).order_by(Dbacida.CI_DENO).all()
    
    meses_nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    
    ano_selecionado = filters.get('ano')
    mes_str = filters.get('mes')
    mes_selecionado = int(mes_str) if mes_str else None

    ano_anterior = ano_selecionado - 1 if ano_selecionado else hoje.year - 1
    mes_anterior = (mes_selecionado - 1) if mes_selecionado and mes_selecionado > 1 else 12
    
    label_mes_anterior = f"{meses_nomes[mes_anterior-1]}/{ano_anterior}" if mes_selecionado else ""

    return render_template(
        'analise_estados.html',
        title="Análise por Localização",
        anos_disponiveis=dados_filtros['anos_disponiveis'],
        estados_disponiveis=estados_disponiveis,
        cidades_disponiveis=cidades_disponiveis,
        label_mes_anterior=label_mes_anterior,
        ano_selecionado=ano_selecionado,
        mes_selecionado=mes_selecionado,
        estado_selecionado=filters.get('estado'),
        cidade_selecionada=filters.get('cidade'),
        canal_venda_selecionado=filters.get('canal_venda'),
        **data
    )


@current_app.route('/relatorios')
def relatorios_index():
    dados_filtros = get_dados_filtros_comuns()
    
    return render_template('relatorios.html',
                           title="Central de Relatórios",
                           representantes=dados_filtros['representantes'],
                           anos_disponiveis=dados_filtros['anos_disponiveis'])


@current_app.route('/relatorio/pedidos/gerar', methods=['POST'])
def gerar_relatorio_pedidos():
    hoje = datetime.now()
    filters = {
        'representante': request.form.get('representante'),
        'recepcao_ano': request.args.get('recepcao_ano', default=hoje.year, type=int),
        'recepcao_mes': request.args.get('recepcao_mes', default=hoje.month, type=int)
    }

    pedidos = get_dados_para_relatorio_pdf(filters)

    if not pedidos:
        flash('Nenhum pedido encontrado com os filtros selecionados.', 'warning')
        return redirect(url_for('relatorios_index'))

    grouped_pedidos = OrderedDict()
    pedidos_sorted = sorted(pedidos, key=lambda p: p.representante.RP_NOME if p.representante else "Sem Representante")
    
    if not filters.get('representante'):
        for rep_nome, group in groupby(pedidos_sorted, key=lambda p: p.representante.RP_NOME if p.representante else "Sem Representante"):
            grouped_pedidos[rep_nome] = list(group)
    else:
        repr_obj = db.session.get(Representante, filters['representante'])
        repr_nome = repr_obj.RP_NOME if repr_obj else "Representante Desconhecido"
        grouped_pedidos[repr_nome] = pedidos
    
    filter_params = {
        'Ano Recepção': filters['recepcao_ano'],
        'Mês Recepção': filters['recepcao_mes'],
        'Representante': list(grouped_pedidos.keys())[0] if filters.get('representante') else "Todos"
    }

    pdf_buffer = generate_order_report(grouped_pedidos, filter_params)

    return Response(pdf_buffer, mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment;filename=relatorio_pedidos.pdf'})


@current_app.route('/analise/recepcao-faturamento')
def analise_recepcao_faturamento():
    hoje = datetime.now()
    ano_selecionado = request.args.get('ano', default=hoje.year, type=int)
    mes_selecionado = request.args.get('mes', default=hoje.month, type=int)
    page = request.args.get('page', 1, type=int)

    dias_para_faturar_subquery = db.session.query(
        Pedido.PD_NUME,
        (func.julianday(Pedido.PD_DTEM) - func.julianday(Pedido.PD_DTRC)).label('dias')
    ).filter(
        Pedido.PD_DTRC.isnot(None),
        Pedido.PD_DTEM.isnot(None),
        func.julianday(Pedido.PD_DTEM) >= func.julianday(Pedido.PD_DTRC)
    ).subquery()

    query_kpis = db.session.query(
        func.count(Pedido.PD_NUME),
        func.avg(dias_para_faturar_subquery.c.dias)
    ).join(
        dias_para_faturar_subquery, Pedido.PD_NUME == dias_para_faturar_subquery.c.PD_NUME
    ).filter(
        extract('year', Pedido.PD_DTRC) == ano_selecionado,
        extract('month', Pedido.PD_DTRC) == mes_selecionado
    )
    
    total_pedidos_periodo, tempo_medio_periodo = query_kpis.one()

    kpis = {
        'total_pedidos': total_pedidos_periodo or 0,
        'tempo_medio': tempo_medio_periodo or 0.0
    }

    query_tabela = Pedido.query.join(
        dias_para_faturar_subquery, Pedido.PD_NUME == dias_para_faturar_subquery.c.PD_NUME
    ).filter(
        extract('year', Pedido.PD_DTRC) == ano_selecionado,
        extract('month', Pedido.PD_DTRC) == mes_selecionado
    ).options(
        joinedload(Pedido.cliente),
        joinedload(Pedido.representante)
    ).add_columns(dias_para_faturar_subquery.c.dias.label('dias_para_faturar')) \
    .order_by(
        desc('dias_para_faturar')
    )

    pedidos_paginados = query_tabela.paginate(page=page, per_page=25, error_out=False)

    def get_chart_data_for_year(year, subquery):
        query_data = db.session.query(
            extract('month', Pedido.PD_DTRC).label('mes'),
            func.avg(subquery.c.dias).label('avg_days')
        ).join(
            subquery, Pedido.PD_NUME == subquery.c.PD_NUME
        ).filter(
            extract('year', Pedido.PD_DTRC) == year
        ).group_by('mes').order_by('mes').all()
        
        data_map = {m.mes: m.avg_days for m in query_data}
        return [data_map.get(i, 0) for i in range(1, 13)]

    chart_data_atual = get_chart_data_for_year(ano_selecionado, dias_para_faturar_subquery)
    ano_anterior = ano_selecionado - 1
    chart_data_anterior = get_chart_data_for_year(ano_anterior, dias_para_faturar_subquery)

    meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    chart_labels = meses_nomes
    
    anos_query = db.session.query(extract('year', Pedido.PD_DTRC)).filter(Pedido.PD_DTRC.isnot(None)).distinct().order_by(extract('year', Pedido.PD_DTRC).desc())
    anos_disponiveis = [ano[0] for ano in anos_query.all() if ano[0]]
    if not anos_disponiveis:
        anos_disponiveis = [hoje.year]

    return render_template(
        'analise_recepcao_faturamento.html',
        title="Análise Recepção x Faturamento",
        kpis=kpis,
        pedidos_paginados=pedidos_paginados,
        ano_selecionado=ano_selecionado,
        mes_selecionado=mes_selecionado,
        anos_disponiveis=anos_disponiveis,
        chart_labels=chart_labels,
        chart_data_atual=chart_data_atual,
        chart_data_anterior=chart_data_anterior,
        ano_anterior=ano_anterior
    )

    
@current_app.route('/financeiro/contas-a-receber')
def contas_a_receber():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    today = date.today()

    filters = {
        'vcto_inicio': request.args.get('vcto_inicio', ''),
        'vcto_fim': request.args.get('vcto_fim', ''),
        'representante': request.args.get('representante', ''),
        'cliente': request.args.get('cliente', ''),
        'faixa_atraso': request.args.get('faixa_atraso', ''),
        'ano': request.args.get('ano', ''),
        'mes': request.args.get('mes', ''),
        'origem': request.args.get('origem', '')
    }

    dias_atraso_expr = case(
        (MovimentoFinanceiro.mv_dtbx.isnot(None), func.julianday(MovimentoFinanceiro.mv_dtbx) - func.julianday(MovimentoFinanceiro.mv_vcto)),
        (MovimentoFinanceiro.mv_vcto < today, func.julianday(today) - func.julianday(MovimentoFinanceiro.mv_vcto)),
        else_=0
    ).label('dias_atraso')
    
    base_query = db.session.query(
        MovimentoFinanceiro,
        dias_atraso_expr
    ).options(
        joinedload(MovimentoFinanceiro.cliente),
        joinedload(MovimentoFinanceiro.representante)
    ).filter(MovimentoFinanceiro.mv_tipo == 'A')

    if filters['vcto_inicio']:
        base_query = base_query.filter(MovimentoFinanceiro.mv_vcto >= filters['vcto_inicio'])
    if filters['vcto_fim']:
        base_query = base_query.filter(MovimentoFinanceiro.mv_vcto <= filters['vcto_fim'])
    if filters['representante']:
        base_query = base_query.filter(MovimentoFinanceiro.mv_repr == filters['representante'])
    if filters['cliente']:
        base_query = base_query.filter(MovimentoFinanceiro.mv_clie_fk == filters['cliente'])
    if filters['ano']:
        base_query = base_query.filter(extract('year', MovimentoFinanceiro.mv_vcto) == int(filters['ano']))
    if filters['mes']:
        base_query = base_query.filter(extract('month', MovimentoFinanceiro.mv_vcto) == int(filters['mes']))
    if filters['origem']:
        base_query = base_query.filter(MovimentoFinanceiro.mv_origem == filters['origem'])
    if filters['faixa_atraso']:
        is_vencido = and_(MovimentoFinanceiro.mv_dtbx.is_(None), MovimentoFinanceiro.mv_vcto < today)
        base_query = base_query.filter(is_vencido)
        if filters['faixa_atraso'] == '1-30':
            base_query = base_query.filter(dias_atraso_expr.between(1, 30))
        elif filters['faixa_atraso'] == '31-90':
            base_query = base_query.filter(dias_atraso_expr.between(31, 90))
        elif filters['faixa_atraso'] == '91+':
            base_query = base_query.filter(dias_atraso_expr > 90)
    
    all_filtered_data = base_query.all()
    
    processed_data = []
    for mv, dias_atraso in all_filtered_data:
        if mv.mv_dtbx is not None:
            status = 'baixado'
        elif mv.mv_vcto is not None and mv.mv_vcto < today:
            status = 'vencido'
        else:
            status = 'aberto'
        
        processed_data.append({
            'movimento': mv,
            'dias_atraso': round(dias_atraso) if dias_atraso is not None else 0,
            'status': status
        })
    
    kpis = get_contas_a_receber_kpis(processed_data)

    grouped_by_pedido = {}
    for item in processed_data:
        mv = item['movimento']
        pedido_key = mv.mv_pedi or f"avulso-{mv.id}"
        
        if pedido_key not in grouped_by_pedido:
            grouped_by_pedido[pedido_key] = {
                'pedido': mv.mv_pedi,
                'nota': mv.mv_nota,
                'cliente': mv.cliente,
                'representante': mv.representante,
                'emissao': mv.mv_data,
                'installments': []
            }
        grouped_by_pedido[pedido_key]['installments'].append(item)

    for key in grouped_by_pedido:
        grouped_by_pedido[key]['total_valor'] = sum(i['movimento'].mv_valo for i in grouped_by_pedido[key]['installments'] if i['movimento'].mv_valo)

    sorted_groups = sorted(grouped_by_pedido.values(), key=lambda x: x.get('emissao') or date.min, reverse=True)

    start = (page - 1) * per_page
    end = start + per_page
    paginated_groups = sorted_groups[start:end]
    
    from flask_paginate import Pagination
    pagination = Pagination(page=page, per_page=per_page, total=len(sorted_groups), css_framework='bootstrap5')

    representantes = Representante.query.filter(Representante.RP_SITU == 'A').order_by(Representante.RP_NOME).all()
    clientes = Cliente.query.filter(Cliente.CL_SITU == 'A').order_by(Cliente.CL_NOME).all()
    
    anos_query = db.session.query(extract('year', MovimentoFinanceiro.mv_vcto))\
        .filter(MovimentoFinanceiro.mv_vcto.isnot(None)).distinct()\
        .order_by(extract('year', MovimentoFinanceiro.mv_vcto).desc())
    anos_disponiveis = [ano[0] for ano in anos_query.all()]
    
    return render_template(
        'contas_a_receber.html',
        title="Contas a Receber",
        grouped_titulos=paginated_groups,
        pagination=pagination,
        kpis=kpis,
        filters=filters,
        representantes=representantes,
        clientes=clientes,
        anos_disponiveis=anos_disponiveis
    )


@current_app.route('/fatura/<int:fatura_id>')
def detalhe_fatura(fatura_id):
    fatura, itens = faturamento_manager.get_detalhes_fatura(fatura_id)

    for item in itens:
        try:
            item.vlr_icms_calculado = Decimal(item.nf_vricms or 0)
            item.vlr_ipi_calculado = Decimal(item.nf_vripi or 0)
            item.vlr_pis_calculado = Decimal(item.nf_tvpis or 0)
            item.vlr_cofins_calculado = Decimal(item.nf_tvcofin or 0)
        except (TypeError, InvalidOperation):
            item.vlr_icms_calculado = Decimal(0)
            item.vlr_ipi_calculado = Decimal(0)
            item.vlr_pis_calculado = Decimal(0)
            item.vlr_cofins_calculado = Decimal(0)

    return render_template(
        'detalhe_fatura.html',
        title=f"Detalhes da Fatura {fatura.nf_nume}",
        fatura=fatura,
        itens=itens
    )


@current_app.route('/financeiro/faturamento')
def analise_faturamento():
    hoje = datetime.now()
    page = request.args.get('page', 1, type=int)
    
    filters = {
        'ano': request.args.get('ano', default=hoje.year, type=int),
        'mes': request.args.get('mes', type=int) if request.args.get('mes') else None,
        'data_inicio': request.args.get('data_inicio', ''),
        'data_fim': request.args.get('data_fim', ''),
        'cfops': request.args.getlist('cfop'),
        'tipo': request.args.get('tipo', ''),
        'q': request.args.get('q', '', type=str),
    }

    if filters['data_inicio'] and filters['data_fim']:
        filters['ano'] = None
        filters['mes'] = None

    page_title = "Análise de Faturamento"
    title_sufix = ""
    if filters.get('tipo') == 'S':
        title_sufix = " (Saídas)"
    elif filters.get('tipo') == 'E':
        title_sufix = " (Entradas/Devoluções)"
    page_title += title_sufix

    data = faturamento_manager.get_faturamento_data(filters, page)
    
    cfops_disponiveis = faturamento_manager.get_cfops_for_period(filters)
    anos_query = db.session.query(
        extract('year', FaturaFiscal.nf_data)
    ).filter(
        FaturaFiscal.nf_data.isnot(None)
    ).distinct().order_by(
        extract('year', FaturaFiscal.nf_data).desc()
    )
    anos_disponiveis = [ano[0] for ano in anos_query.all() if ano[0]]
    if not anos_disponiveis:
        anos_disponiveis = [hoje.year]

    return render_template(
        'analise_faturamento.html',
        title=page_title,
        title_sufix=title_sufix,
        anos_disponiveis=anos_disponiveis,
        current_filters=filters,
        cfops_disponiveis=cfops_disponiveis,
        **data
    )


@current_app.route('/financeiro/margem-contribuicao')
def analise_margem_contribuicao():
    page = request.args.get('page', 1, type=int)
    
    current_filters = {
        'data_inicio': request.args.get('data_inicio'),
        'data_fim': request.args.get('data_fim'),
        'grupo': request.args.get('grupo'),
        'subgrupo': request.args.get('subgrupo'),
        'modelo': request.args.get('modelo'),
        'status': request.args.get('status')
    }

    data = get_margem_contribuicao_data(current_filters, page)

    distinct_grupos = db.session.query(AnaliseMargem.grupo_descricao).distinct().order_by(AnaliseMargem.grupo_descricao).all()
    distinct_subgrupos = db.session.query(AnaliseMargem.subgrupo_descricao).distinct().order_by(AnaliseMargem.subgrupo_descricao).all()
    distinct_modelos = db.session.query(AnaliseMargem.modelo_descricao).distinct().order_by(AnaliseMargem.modelo_descricao).all()
    
    filter_options = {
        'grupos': [g[0] for g in distinct_grupos if g[0]],
        'subgrupos': [sg[0] for sg in distinct_subgrupos if sg[0]],
        'modelos': [m[0] for m in distinct_modelos if m[0]]
    }
    
    return render_template(
        'analise_margem.html',
        title="Análise de Margem de Contribuição",
        dados_paginados=data['dados_paginados'],
        kpis=data['kpis'],
        top_vendas=data['top_vendas'],
        top_rentabilidade=data['top_rentabilidade'],
        current_filters=current_filters,
        filter_options=filter_options
    )


@current_app.template_filter('format_currency')
def format_currency_filter(value):
    if value is None:
        return "R$ 0,00"
    
    try:
        val = Decimal(value)
    except (InvalidOperation, TypeError):
        return "R$ 0,00"

    formatted_value = f'R$ {val:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    if val < 0:
        return formatted_value.replace('R$ ', '-R$ ')
    return formatted_value