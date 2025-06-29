# app/query_manager.py

from . import db
from .models import Pedido, ItemPedido, Produto, Cliente, Representante, Dbastpop, Grupo, Modelo, Cor
from sqlalchemy.orm import joinedload
from sqlalchemy import func, extract, desc

def get_pedidos_recepcionados(filters, page, per_page=25):
    """
    Busca e filtra os pedidos para a tela de Pedidos Recepcionados.
    """
    hoje = db.func.current_date()
    ano_selecionado = filters.get('ano', db.extract('year', hoje))
    mes_selecionado = filters.get('mes', db.extract('month', hoje))

    query = Pedido.query.options(
        joinedload(Pedido.cliente), 
        joinedload(Pedido.representante), 
        joinedload(Pedido.tipo_operacao)
    )

    if ano_selecionado:
        query = query.filter(extract('year', Pedido.PD_DATA) == ano_selecionado)
    if mes_selecionado:
        query = query.filter(extract('month', Pedido.PD_DATA) == mes_selecionado)

    if filters.get('q'):
        search_filter = f"%{filters['q']}%"
        query = query.join(Cliente).filter(
            db.or_(
                Pedido.PD_NUME.ilike(search_filter), 
                Cliente.CL_NOME.ilike(search_filter), 
                Pedido.PD_NOTA.ilike(search_filter)
            )
        )
    if filters.get('representante'):
        query = query.filter(Pedido.PD_REPR == filters['representante'])
    if filters.get('tipo_operacao'):
        query = query.filter(Pedido.PD_TPOP == filters['tipo_operacao'])
    if filters.get('bloqueado'):
        query = query.filter(Pedido.PD_BLOQ == filters['bloqueado'])
    if filters.get('repr_situ'): 
        query = query.join(Representante).filter(Representante.RP_SITU == filters['repr_situ'])
    
    return query.order_by(Pedido.PD_DATA.desc()).paginate(page=page, per_page=per_page, error_out=False)

def get_relatorio_itens_vendidos(filters, page, per_page=100):
    """
    Busca e filtra os itens vendidos para o relatório.
    """
    query = db.session.query(
        Pedido.PD_DATA, Pedido.PD_NUME, Produto.PR_CODI, Produto.PR_DENO, 
        Grupo.GR_DESC, Modelo.MO_DESC, Cor.CO_DESC, 
        ItemPedido.DP_QTDE, ItemPedido.DP_VLUN
    ).select_from(ItemPedido).join(
        Pedido, Pedido.PD_NUME == ItemPedido.DP_NUME
    ).join(
        Produto, Produto.PR_CODI == ItemPedido.DP_PROD
    ).outerjoin(
        Grupo, Grupo.GR_CODI == Produto.PR_GRUP
    ).outerjoin(
        Modelo, Modelo.MO_CODI == Produto.PR_MODE
    ).outerjoin(
        Cor, Cor.CO_CODI == Produto.PR_COR
    )
    if filters.get('data_inicio'):
        data_inicio = db.func.strptime(filters['data_inicio'], '%Y-%m-%d').date()
        query = query.filter(Pedido.PD_DATA >= data_inicio)
    if filters.get('data_fim'):
        data_fim = db.func.strptime(filters['data_fim'], '%Y-%m-%d').date()
        query = query.filter(Pedido.PD_DATA <= data_fim)
        
    return query.order_by(Pedido.PD_DATA.desc()).paginate(page=page, per_page=per_page, error_out=False)


def get_dados_para_relatorio_pdf(filters):
    """
    Busca e prepara os dados para a geração do relatório de pedidos em PDF.
    """
    query = Pedido.query.options(
        joinedload(Pedido.cliente).joinedload(Cliente.cidade),
        joinedload(Pedido.representante)
    ).join(Pedido.representante).order_by(Representante.RP_NOME, Pedido.PD_DATA.desc())

    if filters.get('recepcao_ano'):
        query = query.filter(extract('year', Pedido.PD_DTRC) == filters['recepcao_ano'])
    
    if filters.get('recepcao_mes'):
        query = query.filter(extract('month', Pedido.PD_DTRC) == filters['recepcao_mes'])

    if filters.get('representante'):
        query = query.filter(Pedido.PD_REPR == filters['representante'])

    operacoes_str = "01/02/03/04/08/10/19/22/59/61/63/65"
    operacoes = [op.strip() for op in operacoes_str.replace('/', ' ').replace(',', ' ').split() if op.strip()]
    if operacoes:
        query = query.filter(Pedido.PD_TPOP.in_(operacoes))

    return query.all()

def get_dados_filtros_comuns():
    """
    Busca dados comuns usados em vários filtros da aplicação.
    """
    representantes = db.session.query(Representante)\
        .join(Pedido, Representante.RP_CODI == Pedido.PD_REPR)\
        .filter(func.upper(Representante.RP_SITU) == 'A')\
        .distinct()\
        .order_by(Representante.RP_NOME)\
        .all()
        
    tipos_operacao = Dbastpop.query.order_by(Dbastpop.TO_DESC).all()

    anos_disponiveis = [
        ano[0] for ano in 
        db.session.query(extract('year', Pedido.PD_DATA))
        .filter(Pedido.PD_DATA.isnot(None))
        .distinct()
        .order_by(extract('year', Pedido.PD_DATA).desc())
        .all() 
        if ano[0]
    ]

    return {
        'representantes': representantes,
        'tipos_operacao': tipos_operacao,
        'anos_disponiveis': anos_disponiveis
    }