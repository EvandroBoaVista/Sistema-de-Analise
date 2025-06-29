# app/faturamento_manager.py

from . import db
from .models import FaturaFiscal, ItemFaturaFiscal, Cliente
from sqlalchemy.orm import joinedload
from sqlalchemy import func, extract
from decimal import Decimal
from calendar import monthrange


def get_faturamento_data(filters, page, per_page=25):
    """
    Busca e processa de forma unificada todos os dados para a página de
    Análise de Faturamento, incluindo KPIs, dados para gráficos e a lista
    de faturas paginada.
    """
    ano = filters.get('ano')
    mes = filters.get('mes')
    data_inicio = filters.get('data_inicio')
    data_fim = filters.get('data_fim')
    cfops = filters.get('cfops')
    tipo = filters.get('tipo')
    search_query = filters.get('q')

    # Query base para todos os cálculos e listagem
    base_query = FaturaFiscal.query

    # Aplica filtros de período (data específica ou ano/mês)
    if data_inicio and data_fim:
        base_query = base_query.filter(FaturaFiscal.nf_data.between(data_inicio, data_fim))
    else:
        if ano:
            base_query = base_query.filter(extract('year', FaturaFiscal.nf_data) == int(ano))
        if mes:
            base_query = base_query.filter(extract('month', FaturaFiscal.nf_data) == int(mes))

    # Aplica outros filtros
    if cfops:
        base_query = base_query.filter(FaturaFiscal.nf_ccfo.in_(cfops))
    if tipo:
        base_query = base_query.filter(FaturaFiscal.nf_tipo == tipo)
    if search_query:
        search_filter = f"%{search_query}%"
        base_query = base_query.outerjoin(Cliente, FaturaFiscal.nf_clie == Cliente.CL_CODI).filter(
            db.or_(
                FaturaFiscal.nf_nume.ilike(search_filter),
                FaturaFiscal.nf_pedi.ilike(search_filter),
                Cliente.CL_NOME.ilike(search_filter)
            )
        )

    # --- 1. Calcula os KPIs para o período filtrado completo ---
    kpi_totals = base_query.with_entities(
        func.sum(FaturaFiscal.nf_ttprod).label('total_produtos'),
        func.sum(FaturaFiscal.nf_icms).label('total_icms'),
        func.sum(FaturaFiscal.nf_vipi).label('total_ipi')
    ).first()

    total_produtos = kpi_totals.total_produtos or Decimal('0.0')
    total_impostos = (kpi_totals.total_icms or Decimal('0.0')) + (kpi_totals.total_ipi or Decimal('0.0'))

    kpis = {
        'faturamento_total': float(total_produtos),
        'total_impostos': float(total_impostos),
        'carga_tributaria_media': (total_impostos / total_produtos * 100) if total_produtos > 0 else 0
    }

    # --- 2. Prepara dados para o Gráfico de Composição (Mensal ou Diário) ---
    # A lógica agora é dinâmica com base nos filtros aplicados.
    if mes and ano and not (data_inicio and data_fim):
        # Se um mês específico foi selecionado, muda para visualização DIÁRIA.
        num_days = monthrange(ano, mes)[1]
        chart_labels = [f"{day:02d}/{mes:02d}" for day in range(1, num_days + 1)]

        daily_query = base_query.with_entities(
            extract('day', FaturaFiscal.nf_data).label('dia'),
            func.sum(FaturaFiscal.nf_ttprod).label('total_produtos'),
            func.sum(FaturaFiscal.nf_icms).label('total_icms'),
            func.sum(FaturaFiscal.nf_vipi).label('total_ipi')
        ).filter(FaturaFiscal.nf_data.isnot(None)).group_by('dia').order_by('dia')

        period_data = daily_query.all()
        data_map = {p.dia: p for p in period_data}

        produtos_data = [float(data_map.get(i).total_produtos or 0) if data_map.get(i) else 0 for i in range(1, num_days + 1)]
        icms_data = [float(data_map.get(i).total_icms or 0) if data_map.get(i) else 0 for i in range(1, num_days + 1)]
        ipi_data = [float(data_map.get(i).total_ipi or 0) if data_map.get(i) else 0 for i in range(1, num_days + 1)]

    else:
        # Comportamento padrão: visualização MENSAL para ano inteiro ou range de datas.
        chart_labels = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

        monthly_query = base_query.with_entities(
            extract('month', FaturaFiscal.nf_data).label('mes'),
            func.sum(FaturaFiscal.nf_ttprod).label('total_produtos'),
            func.sum(FaturaFiscal.nf_icms).label('total_icms'),
            func.sum(FaturaFiscal.nf_vipi).label('total_ipi')
        ).filter(FaturaFiscal.nf_data.isnot(None)).group_by('mes').order_by('mes')

        period_data = monthly_query.all()
        data_map = {p.mes: p for p in period_data}

        produtos_data = [float(data_map.get(i).total_produtos or 0) if data_map.get(i) else 0 for i in range(1, 13)]
        icms_data = [float(data_map.get(i).total_icms or 0) if data_map.get(i) else 0 for i in range(1, 13)]
        ipi_data = [float(data_map.get(i).total_ipi or 0) if data_map.get(i) else 0 for i in range(1, 13)]


    # --- 3. Top 5 Clientes por Faturamento ---
    top_clientes_query = base_query.with_entities(
        Cliente.CL_NOME,
        func.sum(FaturaFiscal.nf_vlco).label('total_faturado')
    ).join(Cliente, FaturaFiscal.nf_clie == Cliente.CL_CODI).group_by(Cliente.CL_NOME).order_by(
        db.desc('total_faturado')).limit(5)
    top_clientes_data = top_clientes_query.all()

    # --- 4. Top 5 Produtos por Faturamento ---
    itens_base_query = db.session.query(ItemFaturaFiscal).join(FaturaFiscal, FaturaFiscal.id == ItemFaturaFiscal.fatura_id)
    # Reaplicar filtros relevantes à query de itens
    if data_inicio and data_fim:
        itens_base_query = itens_base_query.filter(FaturaFiscal.nf_data.between(data_inicio, data_fim))
    else:
        if ano: itens_base_query = itens_base_query.filter(extract('year', FaturaFiscal.nf_data) == int(ano))
        if mes: itens_base_query = itens_base_query.filter(extract('month', FaturaFiscal.nf_data) == int(mes))
    if cfops: itens_base_query = itens_base_query.filter(FaturaFiscal.nf_ccfo.in_(cfops))
    if tipo: itens_base_query = itens_base_query.filter(FaturaFiscal.nf_tipo == tipo)

    top_produtos_query = itens_base_query.with_entities(
        ItemFaturaFiscal.nf_descri,
        func.sum(ItemFaturaFiscal.nf_vrliq).label('total_vendido')
    ).group_by(ItemFaturaFiscal.nf_descri).order_by(db.desc('total_vendido')).limit(5)
    top_produtos_data = top_produtos_query.all()

    # --- 5. Faturamento por Estado (UF) ---
    por_estado_query = base_query.with_entities(
        FaturaFiscal.nf_esta,
        func.sum(FaturaFiscal.nf_vlco).label('total_faturado')
    ).group_by(FaturaFiscal.nf_esta).order_by(db.desc('total_faturado')).limit(15)
    por_estado_data = por_estado_query.all()

    # --- 6. Lista Paginada de Faturas ---
    faturas_paginadas = base_query.options(
        joinedload(FaturaFiscal.cliente_rel)
    ).order_by(
        FaturaFiscal.nf_data.desc(), FaturaFiscal.nf_nume.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return {
        'kpis': kpis,
        'chart_labels': chart_labels,
        'produtos_data': produtos_data,
        'icms_data': icms_data,
        'ipi_data': ipi_data,
        'top_clientes': [{'nome': c.CL_NOME, 'valor': float(c.total_faturado or 0)} for c in top_clientes_data],
        'top_produtos': [{'nome': p.nf_descri, 'valor': float(p.total_vendido or 0)} for p in top_produtos_data],
        'por_estado': [{'uf': e.nf_esta or 'N/D', 'valor': float(e.total_faturado or 0)} for e in por_estado_data],
        'faturas_paginadas': faturas_paginadas
    }


def get_cfops_for_period(filters):
    """ Busca todos os CFOPs distintos para um determinado período e tipo de nota. """
    query = db.session.query(FaturaFiscal.nf_ccfo).distinct().order_by(FaturaFiscal.nf_ccfo)

    if filters.get('data_inicio') and filters.get('data_fim'):
        query = query.filter(FaturaFiscal.nf_data.between(filters['data_inicio'], filters['data_fim']))
    else:
        if filters.get('ano'):
            query = query.filter(extract('year', FaturaFiscal.nf_data) == int(filters['ano']))
        if filters.get('mes'):
            query = query.filter(extract('month', FaturaFiscal.nf_data) == int(filters['mes']))

    if filters.get('tipo'):
        query = query.filter(FaturaFiscal.nf_tipo == filters['tipo'])

    return [c[0] for c in query.all() if c[0]]


def get_detalhes_fatura(fatura_id):
    """
    Busca uma fatura específica e todos os seus itens.
    """
    fatura = FaturaFiscal.query.get_or_404(fatura_id)
    return fatura, fatura.itens.all()