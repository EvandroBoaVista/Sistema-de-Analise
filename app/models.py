# app/models.py
from . import db
from sqlalchemy.types import TypeDecorator, Date, String, Integer, DateTime, Numeric
from datetime import datetime
from decimal import Decimal


class SafeDecimal(TypeDecorator):
    """
    Tipo customizado para salvar Decimals como STRING no SQLite, evitando
    perda de precisão e warnings, enquanto usa o tipo nativo em outros bancos.
    """
    impl = Numeric
    cache_ok = True

    def load_dialect_impl(self, dialect):
        """Define qual tipo usar com base no dialeto do banco de dados."""
        if dialect.name == "sqlite":
            # Para SQLite, usa um tipo de texto (String) para armazenar o valor.
            return dialect.type_descriptor(String(255))
        else:
            # Para todos os outros dialetos, usa o tipo Numeric padrão.
            return dialect.type_descriptor(self.impl)

    def process_bind_param(self, value, dialect):
        """Converte o valor do Python para o formato do banco de dados."""
        # No SQLite, converte o Decimal para uma string antes de salvar.
        if dialect.name == "sqlite" and value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        """Converte o valor do banco de dados de volta para o Python."""
        # No SQLite, converte a string do banco de volta para um Decimal.
        if dialect.name == "sqlite" and value is not None:
            return Decimal(value)
        return value

# --- TABELAS DE CADASTRO BASE ---


class Dbastpop(db.Model):
    __tablename__ = 'dbastpop'
    TO_CODI = db.Column(db.String, primary_key=True)
    TO_DESC = db.Column(db.String)
    TO_GERAFIN = db.Column(db.String(1))


class Dbacida(db.Model):
    __tablename__ = 'dbascida'
    CI_CODI = db.Column(db.String, primary_key=True)
    CI_DENO = db.Column(db.String)
    CI_ESTA = db.Column(db.String)
    CI_ICMS = db.Column(SafeDecimal(10, 2))
    CI_NPAIS = db.Column(db.String)


class Cliente(db.Model):
    __tablename__ = 'dbasclie'
    CL_CODI = db.Column(db.String, primary_key=True)
    CL_SITU = db.Column(db.String(1))
    CL_NOME = db.Column(db.String)
    CL_ENDE = db.Column(db.String)
    CL_BAIR = db.Column(db.String)
    CL_CCID = db.Column(db.String, db.ForeignKey('dbascida.CI_CODI'))
    CL_FONE = db.Column(db.String)
    CL_INSC = db.Column(db.String)
    cidade = db.relationship('Dbacida', backref='clientes')


class Representante(db.Model):
    __tablename__ = 'dbasrepr'
    RP_CODI = db.Column(db.String, primary_key=True)
    RP_NOME = db.Column(db.String)
    RP_SITU = db.Column(db.String(1))


class Grupo(db.Model):
    __tablename__ = 'dbasgrpr'
    GR_CODI = db.Column(db.String, primary_key=True)
    GR_DESC = db.Column(db.String)


class Cor(db.Model):
    __tablename__ = 'dbascor'
    CO_CODI = db.Column(db.String, primary_key=True)
    CO_DESC = db.Column(db.String)


class Modelo(db.Model):
    __tablename__ = 'dbasmode'
    MO_CODI = db.Column(db.String, primary_key=True)
    MO_DESC = db.Column(db.String)


class Dbaslinha(db.Model):
    __tablename__ = 'dbaslinha'
    LI_CODI = db.Column(db.String, primary_key=True)
    LI_DESC = db.Column(db.String)


class Dbasport(db.Model):
    __tablename__ = 'dbasport'
    PORT = db.Column(db.String, primary_key=True)
    DESCR = db.Column(db.String)


class Dbassubg(db.Model):
    __tablename__ = 'dbassubg'
    SG_CODI = db.Column(db.String, primary_key=True)
    SG_DESC = db.Column(db.String)


class Produto(db.Model):
    __tablename__ = 'dbasprod'
    PR_CODI = db.Column(db.String, primary_key=True)
    PR_DENO = db.Column(db.String)
    PR_LINK = db.Column(db.String)
    PR_GRUP = db.Column(db.String, db.ForeignKey('dbasgrpr.GR_CODI'))
    PR_COR = db.Column(db.String, db.ForeignKey('dbascor.CO_CODI'))
    PR_MODE = db.Column(db.String, db.ForeignKey('dbasmode.MO_CODI'))
    PR_SUBG = db.Column(db.String, db.ForeignKey('dbassubg.SG_CODI'))
    PR_LINH = db.Column(db.String, db.ForeignKey('dbaslinha.LI_CODI'))
    PR_ALTU = db.Column(SafeDecimal(10, 4))
    PR_LARG = db.Column(SafeDecimal(10, 4))
    PR_PROF = db.Column(SafeDecimal(10, 4))
    PR_M2 = db.Column(SafeDecimal(10, 4))
    PR_MCUB = db.Column(SafeDecimal(10, 4))
    PR_PESO = db.Column(SafeDecimal(10, 4))
    PR_PESOLIQ = db.Column(SafeDecimal(10, 4))
    PR_SITU = db.Column(db.String(1))

    grupo = db.relationship('Grupo', backref='produtos')
    cor = db.relationship('Cor', backref='produtos')
    modelo = db.relationship('Modelo', backref='produtos')
    subgrupo = db.relationship('Dbassubg', backref='produtos')
    linha = db.relationship('Dbaslinha', backref='produtos')

# --- TABELAS DE MOVIMENTO ---


class Pedido(db.Model):
    __tablename__ = 'prodpedi'
    PD_NUME = db.Column(db.String, primary_key=True)
    PD_DTEM = db.Column(Date)
    PD_DATA = db.Column(Date)
    PD_DTRC = db.Column(Date)
    PD_FRET = db.Column(SafeDecimal(10, 2))
    PD_FFOB = db.Column(SafeDecimal(10, 2))
    PD_APRV = db.Column(SafeDecimal(10, 2))
    PD_TTPD = db.Column(SafeDecimal(10, 2))
    PD_NOTA = db.Column(db.String)
    PD_CLIE = db.Column(db.String)
    pd_clie_fk = db.Column("PD_CLIE_FK", db.String, db.ForeignKey('dbasclie.CL_CODI'))
    PD_REPR = db.Column(db.String, db.ForeignKey('dbasrepr.RP_CODI'))
    PD_CDPG = db.Column(db.String)
    NATUREZA = db.Column(db.String)
    NATU_NOME = db.Column(db.String)
    PD_TPOP = db.Column(db.String, db.ForeignKey('dbastpop.TO_CODI'))
    ATUA_WEB = db.Column(db.String)
    PD_BLOQ = db.Column(db.String(1))
    PD_BANCO = db.Column(db.String, db.ForeignKey('dbasport.PORT'))
    PD_TABE = db.Column(db.String)

    cliente = db.relationship('Cliente', foreign_keys=[pd_clie_fk], backref='pedidos')
    representante = db.relationship('Representante', backref='pedidos')
    itens = db.relationship('ItemPedido', backref='pedido', lazy=True, cascade="all, delete-orphan")
    historicos = db.relationship('HistoricoPedido', backref='pedido_ref', lazy='dynamic')
    banco = db.relationship('Dbasport', backref='pedidos')
    tipo_operacao = db.relationship('Dbastpop', backref='pedidos')


class ItemPedido(db.Model):
    __tablename__ = 'proddped'
    id = db.Column(Integer, primary_key=True, autoincrement=True)
    DP_NUME = db.Column(db.String, db.ForeignKey('prodpedi.PD_NUME'), nullable=False)
    DP_PROD = db.Column(db.String, db.ForeignKey('dbasprod.PR_CODI'))
    DP_DATA = db.Column(Date)
    DP_QTDE = db.Column(SafeDecimal(10, 4))
    DP_VLUN = db.Column(SafeDecimal(14, 4))
    DP_VCOM = db.Column(SafeDecimal(14, 4))
    DP_VSEM = db.Column(SafeDecimal(14, 4))
    DP_VRIPI = db.Column(SafeDecimal(14, 4))
    DP_VRICMS = db.Column(SafeDecimal(14, 4))
    DP_ICMSSUF = db.Column(SafeDecimal(14, 4))
    DP_IPISUFR = db.Column(SafeDecimal(14, 4))
    DP_ALIPI = db.Column(SafeDecimal(10, 4))
    DP_ALICMS = db.Column(SafeDecimal(10, 4))
    DP_QTORIG = db.Column(SafeDecimal(10, 4))
    DP_DESMENB = db.Column(SafeDecimal(10, 4))
    DP_PRETABE = db.Column(SafeDecimal(14, 4))

    produto = db.relationship('Produto', backref='itens_pedido')


class HistoricoPedido(db.Model):
    __tablename__ = 'pedihist'
    id = db.Column(Integer, primary_key=True, autoincrement=True)
    USUARIO = db.Column(db.String)
    HORAACESSO = db.Column(db.String)
    OPERACAO = db.Column(db.String, db.ForeignKey('dbastpop.TO_CODI'))
    PEDIDO = db.Column(db.String, db.ForeignKey('prodpedi.PD_NUME'))
    CARGA = db.Column(db.String)
    OBSE = db.Column(db.String)

    operacao_ref = db.relationship('Dbastpop', backref='historicos')

# --- TABELAS DE FATURAMENTO E FINANCEIRO ---


class FaturaFiscal(db.Model):
    __tablename__ = 'fatura_fiscal_capa'
    id = db.Column(Integer, primary_key=True, autoincrement=True)
    periodo_origem = db.Column(String(6), index=True)
    nf_tipo = db.Column(String(1))
    nf_nume = db.Column(String(20), index=True)
    nf_data = db.Column(Date)
    nf_dtsaida = db.Column(Date)
    nf_remd = db.Column(String(50))
    nf_tpve = db.Column(String(50))
    nf_naturez = db.Column(String(100))
    nf_ccfo = db.Column(String(10))
    nf_clie = db.Column(String(20), db.ForeignKey('dbasclie.CL_CODI'))
    nf_ncida = db.Column(String(100))
    nf_nompais = db.Column(String(50))
    nf_esta = db.Column(String(2))
    nf_ccgc = db.Column(String(20))
    nf_ttprod = db.Column(SafeDecimal(14, 4))
    nf_vlco = db.Column(SafeDecimal(14, 4))
    nf_bsca = db.Column(SafeDecimal(14, 4))
    nf_icms = db.Column(SafeDecimal(14, 4))
    nf_oicm = db.Column(String(50))
    nf_picm = db.Column(SafeDecimal(10, 4))
    nf_vipi = db.Column(SafeDecimal(14, 4))
    nf_pipi = db.Column(SafeDecimal(10, 4))
    nf_oipi = db.Column(String(50))
    nf_obse = db.Column(String(255))
    nf_pedi = db.Column(String(20))
    nf_forn = db.Column(String(50))
    nf_frete = db.Column(SafeDecimal(14, 4))
    nf_nfe = db.Column(String(50))
    nf_cricms = db.Column(String(50))
    nf_bscricm = db.Column(SafeDecimal(14, 4))
    nf_volume = db.Column(SafeDecimal(10, 4))
    nf_pesobru = db.Column(SafeDecimal(10, 4))
    nf_pesoliq = db.Column(SafeDecimal(10, 4))
    nf_motcanc = db.Column(String(255))

    cliente_rel = db.relationship('Cliente', foreign_keys=[nf_clie])
    itens = db.relationship('ItemFaturaFiscal', backref='fatura', lazy='dynamic')


class ItemFaturaFiscal(db.Model):
    __tablename__ = 'fatura_fiscal_itens'
    id = db.Column(Integer, primary_key=True, autoincrement=True)
    periodo_origem = db.Column(String(6), index=True)
    fatura_id = db.Column(Integer, db.ForeignKey('fatura_fiscal_capa.id'))
    nf_tiponf = db.Column(String(1))
    nf_numero = db.Column(String(20), index=True)
    nf_serie = db.Column(String(5))
    nf_ccfoit = db.Column(String(10))
    nf_produto = db.Column(String(20))
    nf_unidade = db.Column(String(5))
    nf_descri = db.Column(String(100))
    nf_ncm = db.Column(String(20))
    nf_sittri = db.Column(String(10))
    nf_volume = db.Column(SafeDecimal(10, 4))
    nf_pesobru = db.Column(SafeDecimal(10, 4))
    nf_pesoliq = db.Column(SafeDecimal(10, 4))
    nf_qtprod = db.Column(SafeDecimal(10, 4))
    nf_vrbruto = db.Column(SafeDecimal(14, 4))
    nf_vrdesc = db.Column(SafeDecimal(14, 4))
    nf_pcdesc = db.Column(SafeDecimal(10, 4))
    nf_vrliq = db.Column(SafeDecimal(14, 4))
    nf_descpis = db.Column(SafeDecimal(14, 4))
    nf_percpis = db.Column(SafeDecimal(10, 4))
    nf_desccof = db.Column(SafeDecimal(14, 4))
    nf_perccof = db.Column(SafeDecimal(10, 4))
    nf_descicm = db.Column(SafeDecimal(14, 4))
    nf_percicm = db.Column(SafeDecimal(10, 4))
    nf_bscaicm = db.Column(SafeDecimal(14, 4))
    nf_vricms = db.Column(SafeDecimal(14, 4))
    nf_pcims = db.Column(SafeDecimal(10, 4))
    nf_bcpred = db.Column(SafeDecimal(14, 4))
    nf_bscaipi = db.Column(SafeDecimal(14, 4))
    nf_vripi = db.Column(SafeDecimal(14, 4))
    nf_percipi = db.Column(SafeDecimal(10, 4))
    nf_icmorig = db.Column(String(10))
    nf_vrfrete = db.Column(SafeDecimal(14, 4))
    nf_tppis = db.Column(String(10))
    nf_tpcofin = db.Column(String(10))
    nf_pfpc = db.Column(SafeDecimal(10, 4))
    nf_aldes = db.Column(String(50))
    nf_vlfpc = db.Column(SafeDecimal(14, 4))
    nf_vicde = db.Column(SafeDecimal(14, 4))
    nf_vicre = db.Column(SafeDecimal(14, 4))
    nf_tvpis = db.Column(SafeDecimal(14, 4))
    nf_tvcofin = db.Column(SafeDecimal(14, 4))


class MovimentoFinanceiro(db.Model):
    __tablename__ = 'ctremvto'
    id = db.Column(Integer, primary_key=True, autoincrement=True)
    mv_origem = db.Column(db.String(20))
    mv_tipo = db.Column(db.String(1))
    mv_data = db.Column(Date)
    mv_pedi = db.Column(db.String(20), db.ForeignKey('prodpedi.PD_NUME'))
    mv_remd = db.Column(db.String(20))
    mv_orde = db.Column(db.String(10))
    mv_clie = db.Column(db.String(20))
    mv_clie_fk = db.Column(db.String, db.ForeignKey('dbasclie.CL_CODI'))
    mv_repr = db.Column(db.String(4), db.ForeignKey('dbasrepr.RP_CODI'))
    mv_vcto = db.Column(Date)
    mv_nota = db.Column(String(20))
    mv_vltt = db.Column(SafeDecimal(10, 2))
    mv_vipi = db.Column(SafeDecimal(10, 2))
    mv_valo = db.Column(SafeDecimal(10, 2))
    mv_dtbx = db.Column(Date)
    mv_vlbx = db.Column(SafeDecimal(10, 2))
    mv_port = db.Column(db.String(50), db.ForeignKey('dbasport.PORT'))
    mv_boleto = db.Column(db.String(50))
    mv_dttr = db.Column(Date)
    mv_obse = db.Column(db.String(255))
    acerto = db.Column(db.String(20))
    mv_saldo = db.Column(SafeDecimal(10, 2))
    mv_ultalte = db.Column(Date)
    mv_usua = db.Column(db.String(50))
    mv_reneg = db.Column(db.String(20))

    cliente = db.relationship('Cliente', foreign_keys=[mv_clie_fk], backref='movimentos_financeiros')
    representante = db.relationship('Representante', backref='movimentos_financeiros')
    pedido = db.relationship('Pedido', backref='movimentos_financeiros')
    portador = db.relationship('Dbasport', backref='movimentos_financeiros')


class FichaProduto(db.Model):
    __tablename__ = 'ficha_produto'
    id = db.Column(Integer, primary_key=True, autoincrement=True)
    periodo_origem = db.Column(String(6), index=True)
    data_referencia = db.Column(Date, index=True)
    produto_codi = db.Column(String(20), db.ForeignKey('dbasprod.PR_CODI'), index=True)
    preco_medio = db.Column(SafeDecimal(14, 4))
    ultimo_preco = db.Column(SafeDecimal(14, 4))
    despesa_fixa = db.Column(SafeDecimal(14, 4))

    produto = db.relationship('Produto', backref='fichas')

# --- NOVA TABELA PARA RESULTADOS DA ANÁLISE ---


class AnaliseMargem(db.Model):
    __tablename__ = 'analise_margem'
    id = db.Column(Integer, primary_key=True, autoincrement=True)
    item_fatura_id = db.Column(Integer, db.ForeignKey('fatura_fiscal_itens.id'), index=True)
    fatura_id = db.Column(Integer, db.ForeignKey('fatura_fiscal_capa.id'), index=True)

    data_nf = db.Column(Date, index=True)
    nf_numero = db.Column(String)
    pedido_numero = db.Column(String)
    cliente_nome = db.Column(String)
    produto_cod = db.Column(String)
    produto_desc = db.Column(String)
    qtde = db.Column(SafeDecimal(10, 4))
    vlr_unit_ped = db.Column(SafeDecimal(14, 4))
    receita_com_nota = db.Column(SafeDecimal(14, 4))
    receita_sem_nota = db.Column(SafeDecimal(14, 4))
    total_faturado_nf = db.Column(SafeDecimal(14, 4))
    custo_unit_ficha = db.Column(SafeDecimal(14, 4))
    custo_producao = db.Column(SafeDecimal(14, 4))
    icms = db.Column(SafeDecimal(14, 4))
    ipi = db.Column(SafeDecimal(14, 4))
    pis = db.Column(SafeDecimal(14, 4))
    cofins = db.Column(SafeDecimal(14, 4))
    mc_valor = db.Column(SafeDecimal(14, 4))
    mc_perc = db.Column(SafeDecimal(10, 4))

    # --- COLUNAS ATUALIZADAS E ADICIONADAS ---
    receita_total_item = db.Column(SafeDecimal(14, 4))
    produto_status = db.Column(String(20))
    grupo_descricao = db.Column(String)
    modelo_descricao = db.Column(String)
    subgrupo_descricao = db.Column(String)
    # --- FIM DAS ALTERAÇÕES ---

    item_fatura = db.relationship('ItemFaturaFiscal', backref='analise_margem')
    fatura = db.relationship('FaturaFiscal', backref='analise_margem')


# --- TABELAS DE ARQUIVAMENTO (EXCLUÍDOS) ---

class PedidoExcluido(db.Model):
    __tablename__ = 'prodpedi_excluidos'
    id = db.Column(Integer, primary_key=True, autoincrement=True)
    data_importacao = db.Column(DateTime, default=datetime.utcnow)
    PD_NUME = db.Column(db.String)
    PD_DTEM = db.Column(Date)
    PD_NOTA = db.Column(db.String)
    PD_CLIE = db.Column(db.String)
    PD_REPR = db.Column(db.String, db.ForeignKey('dbasrepr.RP_CODI'))
    PD_CDPG = db.Column(db.String)
    NATUREZA = db.Column(db.String)
    NATU_NOME = db.Column(db.String)
    ATUA_WEB = db.Column(db.String)
    PD_DATA = db.Column(Date)
    PD_DTRC = db.Column(Date)
    PD_FRET = db.Column(db.String)
    PD_FFOB = db.Column(db.String)
    PD_APRV = db.Column(db.String)
    PD_TTPD = db.Column(SafeDecimal(10, 2))
    PD_BLOQ = db.Column(db.String)
    PD_TABE = db.Column(db.String)
    PD_BANCO = db.Column(db.String)
    PD_TPOP = db.Column(db.String)
    pd_clie_fk = db.Column("pd_clie_fk", db.String, db.ForeignKey('dbasclie.CL_CODI'))

    cliente = db.relationship('Cliente', foreign_keys=[pd_clie_fk], backref='pedidos_excluidos')
    representante = db.relationship('Representante', foreign_keys=[PD_REPR])
    historicos = db.relationship(
        'HistoricoPedido',
        primaryjoin="foreign(PedidoExcluido.PD_NUME) == remote(HistoricoPedido.PEDIDO)",
        backref='pedido_excluido_ref'
    )


class MovimentoFinanceiroExcluido(db.Model):
    __tablename__ = 'ctremvto_excluidos'
    id = db.Column(Integer, primary_key=True, autoincrement=True)
    data_importacao = db.Column(DateTime, default=datetime.utcnow)
    mv_origem = db.Column(db.String(10))
    mv_tipo = db.Column(db.String(1))
    mv_data = db.Column(Date)
    mv_pedi = db.Column(db.String(20))
    mv_remd = db.Column(db.String(20))
    mv_orde = db.Column(db.String(10))
    mv_clie = db.Column(db.String(20))
    mv_repr = db.Column(db.String(4))
    mv_vcto = db.Column(Date)
    mv_nota = db.Column(String(20))
    mv_vltt = db.Column(SafeDecimal(10, 2))
    mv_vipi = db.Column(SafeDecimal(10, 2))
    mv_valo = db.Column(SafeDecimal(10, 2))
    mv_dtbx = db.Column(Date)
    mv_vlbx = db.Column(SafeDecimal(10, 2))
    mv_port = db.Column(db.String(50))
    mv_boleto = db.Column(db.String(50))
    mv_dttr = db.Column(Date)
    mv_obse = db.Column(db.String(255))
    acerto = db.Column(db.String(20))
    mv_saldo = db.Column(SafeDecimal(10, 2))
    mv_ultalte = db.Column(Date)
    mv_usua = db.Column(db.String(50))
    mv_reneg = db.Column(db.String(20))
    mv_clie_fk = db.Column(db.String)