# app/importer.py
import os
import sqlite3
import json
import dbf
import traceback
import re
from dbf import Table
from decimal import Decimal, InvalidOperation
from datetime import datetime, date

APP_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(APP_DIR, '..', 'instance')
DB_PATH = os.path.join(INSTANCE_DIR, 'app.db')
CONFIG_PATH = os.path.join(INSTANCE_DIR, 'config.json')

# Mapeamento de tabelas DBF para tabelas SQLite com descrições detalhadas
TABLES_MAP = {
    # Tabela PRODPEDI - Capa dos Pedidos
    'PRODPEDI': ('prodpedi', [
        'PD_NUME',     # NUMERO DO PEDIDO
        'PD_DTEM',     # data de faturamento
        'PD_DATA',     # Data de criação
        'PD_DTRC',     # Data de recepção do pedido
        'PD_FRET',     # Porcentagem do Frete
        'PD_FFOB',     # Porcentagem do Frete FOB
        'PD_APRV',     # Porcentagem de valor Aprovado (EX. 50% aprovado)
        'PD_TTPD',     # Valor total do pedido
        'PD_NOTA',     # Numero da Nota
        'PD_CLIE',     # CODIGO DO CLIENTE
        'PD_REPR',     # CODIGO DO REPRESENTANTE
        'PD_CDPG',     # CONDIÇÃO DE PAGAMENTO
        'NATUREZA',    # NATUREZA DO CFOP
        'NATU_NOME',   # NOME DA NATUREZA
        'PD_TPOP',     # Tipo de Operação
        'ATUA_WEB',    # ATUALIZA WEB (QUANDO FOI ATUALIZADO NA WEB)
        'PD_BLOQ',     # Indica se o pedido esta bloqueado (S) ou normal (vazio)
        'PD_BANCO',    # Codigo do Portador
        'PD_TABE',     # Codigo da Tabela de preço
    ], 'PD_NUME'),

    # tabela proddped - Itens do pedido, com ligação ao PRODPEDI
    'PRODDPED': ('proddped', [
        'DP_DATA',     # data do item
        'DP_NUME',     # Numero do Pedido
        'DP_PROD',     # Codigo do Produto
        'DP_QTDE',     # Quantidade do produto
        'DP_VLUN',     # Valor Unitario
        'DP_VCOM',     # VALOR COM Nota
        'DP_VSEM',     # VALOR AGUARDANDO (SEM NOTA)
        'DP_VRIPI',    # IPI EM REAIS
        'DP_VRICMS',   # ICMS EM REAIS
        'DP_ICMSSUF',  # ICMS SUFRAMA
        'DP_IPISUFR',  # IPI SUFRAMA
        'DP_ALIPI',    # PORCENTAGEM DO IPI
        'DP_ALICMS',   # PORCENTAGEM DO ICMS
        'DP_QTORIG',   # QUANTIDADE DE ITENS ORIGINAL DO PEDIDO
        'DP_DESMENB',  # QUANTIDADO DO ITENS DESMENBRADO DO PEDIDO (zerado)
        'DP_PRETABE',  # PRECO DO ITEM QUE VEM DA TABELA DE VENDA
    ], None),

    # Tabela DBASPROD - Cadastro de Produtos
    'DBASPROD': ('dbasprod', [
        'PR_CODI',     # Codigo do Produto
        'PR_DENO',     # Descrição do Produto
        'PR_LINK',     # EAN do Produto
        'PR_GRUP',     # CODIGO DO GRUPO
        'PR_COR',      # CODIGO DA COR
        'PR_MODE',     # CODIGO DO MODELO
        'PR_SUBG',
        'PR_LINH',
        'PR_ALTU',     # ALTURA
        'PR_LARG',     # LARGURA
        'PR_PROF',     # PROFUNDIDADE
        'PR_M2',       # METROS QUADRADOS
        'PR_MCUB',     # METROS CUBICOS
        'PR_PESO',     # PESO
        'PR_PESOLIQ',  # PESO LIQUIDO
        'PR_SITU',     # SITUAÇÃO: (S) EM LINHA / (N) FORA DE LINHA
    ], 'PR_CODI'),
    
    # Tabela dbaslinha - Linha de produtos
    'DBASLINHA': ('dbaslinha', ['LI_CODI', 'LI_DESC'], 'LI_CODI'),
    # Tabela DBASPORT - Tabela dos Portadores
    'DBASPORT': ('dbasport', ['PORT', 'DESCR'], 'PORT'),
    # Tabela DBASSUBG - Sub Grupo para os produtos
    'DBASSUBG': ('dbassubg', ['SG_CODI', 'SG_DESC'], 'SG_CODI'),
    # Tabela DBASTPOP - Tabela de Operação
    'DBASTPOP': ('dbastpop', [
        'TO_CODI',     # CODIGO DA OPERAÇÃO
        'TO_DESC',     # DESCRIÇÃO DA OPERAÇÃO
        'TO_GERAFIN',  # GERA CONTAS A RECEBER/PAGAR: (S) SIM / (N) NÃO
    ], 'TO_CODI'),
    # Tabela dbascor - cor dos produtos
    'DBASCOR':  ('dbascor', ['CO_CODI', 'CO_DESC'], 'CO_CODI'),
    # TABELA DBASGRPR - GRUPO DOS PRODUTOS
    'DBASGRPR': ('dbasgrpr', ['GR_CODI', 'GR_DESC'], 'GR_CODI'),
    # TABELA DBASMODE - MODELO DO PRODUTO
    'DBASMODE': ('dbasmode', ['MO_CODI', 'MO_DESC'], 'MO_CODI'),

    # TABELA PEDIHIST - HISTORICO DE Pedido
    'PEDIHIST': ('pedihist', [
        'USUARIO',     # USUARIO QUE ALTEROU
        'HORAACESSO',  # DATA E HORA
        'OPERACAO',    # OPERAÇÃO QUE FOI FEITA
        'PEDIDO',      # NUMERO DO PEDIDO
        'CARGA',       # CARGA QUE ESTA O PEDIDO
        'OBSE',        # OBSERVAÇÃO DOS HISTORICOS
    ], None),
    
    # TABELA DBASCLIE - Cadastro de Clientes
    'DBASCLIE': ('dbasclie', [
        'CL_CODI',     # CODIGO DO CLIENTE
        'CL_SITU',     # SITUAÇÃO: (A)TIVO OU (I)NATIVO
        'CL_NOME',     # NOME DO CLIENTE
        'CL_ENDE',     # ENDEREÇO DO CLIENTE
        'CL_BAIR',     # BAIRRO DO CLIENTE
        'CL_CCID',     # CIDADE DO CLIENTE
        'CL_FONE',     # TELEFONE DO CLIENTE
        'CL_INSC'      # INSCRIÇÃO ESTADUAL DO CLIENTE
    ], 'CL_CODI'),

    # TABELA DBASREPR - Cadastro de Representantes
    'DBASREPR': ('dbasrepr', [
        'RP_CODI',     # CODIGO DO REPRESENTANTE
        'RP_NOME',     # NOME DO REPRESENTANTE
        'RP_SITU',     # SITUAÇÃO: (A)TIVO OU (I)NATIVO
    ], 'RP_CODI'),

    'DBASCIDA': ('dbascida', ['CI_CODI', 'CI_DENO', 'CI_ESTA', 'CI_ICMS', 'CI_NPAIS'], 'CI_CODI'),
}

UNIFIED_TABLES = {
    # Unifica CTREMVTO (Notas) e CTREPAPL (Papeletas)
    'ctremvto': {
        'sources': [
            {'dbf_file': 'CTREMVTO.DBF', 'prefix': 'MV_', 'origin': 'NOTA FISCAL'},
            {'dbf_file': 'CTREPAPL.DBF', 'prefix': 'PF_', 'origin': 'PAPELETA'}
        ],
        'dest_columns': [
            'mv_origem',   # Origem (NOTA FISCAL ou PAPELETA)
            'mv_tipo',     # (A) ENTRADA/FATURAMENTO / (B) BAIXA
            'mv_data',     # DATA DO FATURAMENTO
            'mv_pedi',     # NUMERO DO PEDIDO
            'mv_remd',     # NUMERO DA CARGA
            'mv_orde',     # NUMERO DA PARCELA
            'mv_clie',     # CODIGO DO CLIENTE
            'mv_repr',     # CODIGO DO REPRESENTANTE
            'mv_vcto',     # DATA DO VENCIMENTO
            'mv_nota',     # NUMERO DA NOTA FISCAL
            'mv_vltt',     # VALOR TOTAL DA DIVISÃO DA NOTA
            'mv_vipi',     # VALOR DO IPI
            'mv_valo',     # VALOR DA PARCELA
            'mv_dtbx',     # DATA DA BAIXA
            'mv_vlbx',     # VALOR QUE FOI BAIXADO
            'mv_port',     # PORTADOR
            'mv_boleto',   # NUMERO DO BOLETO
            'mv_dttr',     # DATA QUE FOI ENVIADO AO BANCO
            'mv_obse',     # OBSERVAÇÃO
            'acerto',      # NUMERO DO ACERTO
            'mv_saldo',    # SALDO
            'mv_ultalte',  # DATA DE ULTIMA ALTERAÇÃO
            'mv_usua',     # ULTIMO USUARIO QUE ALTEROU
            'mv_reneg',    # RENEGOCIAÇÃO
        ],
        'date_cols': ['DATA', 'VCTO', 'DTBX', 'DTTR', 'ULTALTE'],
        'numeric_cols': ['VLTT', 'VIPI', 'VALO', 'VLBX', 'SALDO']
    }
}


def parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.strptime(value.strip(), '%Y%m%d').date()
        except (ValueError, TypeError):
            return None
    return None


def parse_decimal_as_string(value):
    if value is None:
        return None
    try:
        return str(Decimal(str(value)))
    except (InvalidOperation, TypeError):
        return None


def load_dbf_path_from_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"ERRO: Arquivo de configuração '{CONFIG_PATH}' não encontrado.")
        return None
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            path = config.get('dbf_path')
            if not path or not os.path.isdir(path):
                print(f"ERRO: O caminho '{path}' configurado não é um diretório válido.")
                return None
            return path
    except Exception as e:
        print(f"ERRO ao ler o arquivo de configuração: {e}")
        return None


def import_patterned_data(cursor, dbf_path, pattern, dest_table, column_mapping, date_cols, numeric_cols, transformations=None):
    if transformations is None:
        transformations = {}

    print("\n" + "="*40)
    print(f"INICIANDO IMPORTAÇÃO PARA TABELA CONSOLIDADA: {dest_table.upper()}")

    file_pattern = re.compile(pattern, re.IGNORECASE)

    try:
        cursor.execute(f"DELETE FROM {dest_table}")
        print(f"Tabela de destino '{dest_table}' limpa.")
    except sqlite3.OperationalError as e:
        print(f"AVISO: Tabela de destino '{dest_table}' não encontrada ou erro ao limpar: {e}")

    all_records = []
    found_files = False
    for filename in os.listdir(dbf_path):
        match = file_pattern.match(filename)
        if match:
            found_files = True
            periodo = match.group(1)
            print(f"  -> Processando ficheiro: {filename} (Período: {periodo})")

            data_ref_from_period = None
            if dest_table == 'ficha_produto':
                try:
                    ano = int(f"20{periodo[:2]}")
                    mes = int(periodo[2:])
                    data_ref_from_period = date(ano, mes, 1)
                except (ValueError, TypeError):
                    pass

            dbf_full_path = os.path.join(dbf_path, filename)
            try:
                with dbf.Table(dbf_full_path, codepage='cp850') as table_dbf:
                    for record in table_dbf:
                        if dbf.is_deleted(record):
                            continue

                        record_data = {'periodo_origem': periodo}
                        if data_ref_from_period:
                            record_data['data_referencia'] = data_ref_from_period

                        for dbf_col, sql_col in column_mapping.items():
                            try:
                                value = record[dbf_col]

                                if dbf_col in transformations:
                                    value = transformations[dbf_col](value)

                                if dbf_col in date_cols:
                                    record_data[sql_col] = parse_date(value)
                                elif dbf_col in numeric_cols:
                                    record_data[sql_col] = parse_decimal_as_string(value)
                                else:
                                    record_data[sql_col] = value.strip() if isinstance(value, str) else value
                            except (dbf.FieldMissingError, IndexError):
                                record_data[sql_col] = None

                        cols_order = ['periodo_origem']
                        if data_ref_from_period:
                            cols_order.append('data_referencia')
                        cols_order.extend(column_mapping.values())

                        all_records.append(tuple(record_data.get(c) for c in cols_order))
            except Exception as e:
                print(f"     ERRO ao processar o ficheiro {filename}: {e}")

    if not found_files:
        print(f"  -> Nenhum ficheiro encontrado com o padrão '{pattern}'")

    if all_records:
        try:
            cols = ['periodo_origem']
            if dest_table == 'ficha_produto':
                cols.append('data_referencia')
            cols.extend(column_mapping.values())

            placeholders = ', '.join(['?'] * len(cols))
            sql = f"INSERT INTO {dest_table} ({', '.join(cols)}) VALUES ({placeholders})"
            cursor.executemany(sql, all_records)
            print(f"  -> OK: {len(all_records)} registos importados para '{dest_table}'.")
        except Exception as e:
            print(f"     ERRO ao inserir dados no banco de dados para '{dest_table}': {e}")
            traceback.print_exc()

    print(f"IMPORTAÇÃO PARA {dest_table.upper()} CONCLUÍDA.")
    print("="*40)


def calcular_e_salvar_margem(cursor):
    """
    Calcula a margem de contribuição para todos os itens faturados e salva
    os resultados na nova tabela 'analise_margem'.
    """
    print("\n" + "="*40)
    print("INICIANDO CÁLCULO E ARMAZENAMENTO DA MARGEM DE CONTRIBUIÇÃO...")

    try:
        cursor.execute("DELETE FROM analise_margem")
        print("Tabela 'analise_margem' limpa com sucesso.")
    except sqlite3.OperationalError as e:
        print(f"AVISO: Tabela 'analise_margem' não encontrada ou erro ao limpar: {e}")

    sql_calculo = """
        SELECT
            ffi.id AS item_fatura_id,
            ff.id AS fatura_id,
            ff.nf_data,
            ffi.nf_numero,
            ff.nf_pedi,
            c.CL_NOME,
            ffi.nf_produto,
            ffi.nf_descri,
            pr.PR_SITU,
            gr.GR_DESC,
            mo.MO_DESC,
            sg.SG_DESC,
            ffi.nf_qtprod,
            dp.DP_VLUN,
            dp.DP_VCOM,
            dp.DP_VSEM,
            ffi.nf_vrliq,
            (SELECT preco_medio FROM ficha_produto 
             WHERE produto_codi = ffi.nf_produto AND data_referencia <= ff.nf_data 
             ORDER BY data_referencia DESC LIMIT 1) AS custo_medio_unitario,
            ffi.nf_vricms,
            ffi.nf_vripi,
            ffi.nf_tvpis,
            ffi.nf_tvcofin
        FROM fatura_fiscal_itens ffi
        JOIN fatura_fiscal_capa ff ON ffi.fatura_id = ff.id
        JOIN prodpedi p ON ff.nf_pedi = p.PD_NUME
        JOIN dbastpop tpop ON p.PD_TPOP = tpop.TO_CODI
        JOIN proddped dp ON p.PD_NUME = dp.DP_NUME AND ffi.nf_produto = dp.DP_PROD
        JOIN dbasclie c ON ff.nf_clie = c.CL_CODI
        JOIN dbasprod pr ON ffi.nf_produto = pr.PR_CODI
        LEFT JOIN dbasgrpr gr ON pr.PR_GRUP = gr.GR_CODI
        LEFT JOIN dbasmode mo ON pr.PR_MODE = mo.MO_CODI
        LEFT JOIN dbassubg sg ON pr.PR_SUBG = sg.SG_CODI
        WHERE
            tpop.TO_GERAFIN = 'S' AND
            ff.nf_tipo = 'S' AND
            EXISTS (
                SELECT 1 FROM ficha_produto fp
                WHERE fp.produto_codi = ffi.nf_produto AND fp.data_referencia <= ff.nf_data
            )
    """

    try:
        cursor.execute(sql_calculo)
        resultados = cursor.fetchall()
        print(f"  -> {len(resultados)} itens encontrados para cálculo.")

        registros_para_inserir = []
        for row in resultados:
            item_fatura_id, fatura_id, data_nf, nf_numero, pedido_numero, cliente_nome, \
            produto_cod, produto_desc, produto_status, grupo_descricao, modelo_descricao, \
            subgrupo_descricao, qtde, vlr_unit_ped, receita_com_nota, receita_sem_nota, \
            total_faturado_nf, custo_unit_ficha, icms, ipi, pis, cofins = row

            qtde = Decimal(qtde or 0)
            vlr_unit_ped = Decimal(vlr_unit_ped or 0)
            receita_com_nota = Decimal(receita_com_nota or 0)
            receita_sem_nota = Decimal(receita_sem_nota or 0)
            custo_unit_ficha = Decimal(custo_unit_ficha or 0)
            icms = Decimal(icms or 0)
            ipi = Decimal(ipi or 0)
            pis = Decimal(pis or 0)
            cofins = Decimal(cofins or 0)
            total_faturado_nf = Decimal(total_faturado_nf or 0)

            receita_total_item = (receita_com_nota + receita_sem_nota) * qtde
            custo_producao = custo_unit_ficha * qtde
            base_calculo_mc = (vlr_unit_ped * qtde)
            impostos_total = icms + ipi + pis + cofins
            mc_valor = base_calculo_mc - custo_producao - impostos_total
            mc_perc = (mc_valor / base_calculo_mc * 100) if base_calculo_mc > 0 else 0

            registros_para_inserir.append((
                item_fatura_id, fatura_id, data_nf, nf_numero, pedido_numero, cliente_nome,
                produto_cod, produto_desc, str(qtde), str(vlr_unit_ped), str(receita_com_nota), str(receita_sem_nota),
                str(total_faturado_nf), str(custo_unit_ficha), str(custo_producao), str(icms), str(ipi), str(pis), str(cofins),
                str(mc_valor), str(mc_perc),
                str(receita_total_item),
                produto_status,
                grupo_descricao,
                modelo_descricao,
                subgrupo_descricao
            ))

        if registros_para_inserir:
            sql_insert = """
                INSERT INTO analise_margem (
                    item_fatura_id, fatura_id, data_nf, nf_numero, pedido_numero, cliente_nome, 
                    produto_cod, produto_desc, qtde, vlr_unit_ped, receita_com_nota, receita_sem_nota, 
                    total_faturado_nf, custo_unit_ficha, custo_producao, icms, ipi, pis, cofins,
                    mc_valor, mc_perc, 
                    receita_total_item, produto_status, grupo_descricao, modelo_descricao, subgrupo_descricao
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.executemany(sql_insert, registros_para_inserir)
            print(f"  -> OK: {len(registros_para_inserir)} registros de margem salvos no banco de dados.")

    except Exception as e:
        print(f"     ERRO ao calcular e salvar a margem de contribuição: {e}")
        traceback.print_exc()

    print("CÁLCULO DA MARGEM DE CONTRIBUIÇÃO CONCLUÍDO.")
    print("="*40)


def import_data():
    print("\n" + "="*60)
    print("INICIANDO PROCESSO DE IMPORTAÇÃO GERAL...")
    dbf_path = load_dbf_path_from_config()
    if not dbf_path:
        print("IMPORTAÇÃO FALHOU: Caminho dos arquivos DBF não configurado ou inválido.")
        return

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    print(f"Destino dos dados: Banco de dados '{DB_PATH}'")

    all_table_names = [v[0] for v in TABLES_MAP.values()] + list(UNIFIED_TABLES.keys()) + ['fatura_fiscal_capa', 'fatura_fiscal_itens', 'ficha_produto', 'analise_margem']
    for table_name in reversed(all_table_names):
        try:
            cursor.execute(f"DELETE FROM {table_name}")
        except sqlite3.OperationalError:
            pass
        if table_name in ['prodpedi', 'ctremvto']:
            try:
                cursor.execute(f"DELETE FROM {table_name}_excluidos")
            except sqlite3.OperationalError:
                pass
    conn.commit()
    print("Tabelas limpas com sucesso.")

    for dbf_file_key, (table_name, columns, pk_column_name) in TABLES_MAP.items():
        dbf_full_path = os.path.join(dbf_path, f'{dbf_file_key}.DBF')
        if not os.path.exists(dbf_full_path):
            print(f"  -> AVISO: Arquivo {dbf_file_key}.DBF não encontrado. Pulando.")
            continue
        print(f"  -> Processando: {dbf_file_key}.DBF")
        try:
            with dbf.Table(dbf_full_path, codepage='cp850') as table_dbf:
                records_to_insert, deleted_records_to_insert = [], []
                seen_pks = set()
                pk_index = columns.index(pk_column_name) if pk_column_name else -1
                date_cols = {'prodpedi': ['PD_DTEM', 'PD_DATA', 'PD_DTRC'], 'proddped': ['DP_DATA']}
                numeric_cols = {
                    'prodpedi': ['PD_TTPD', 'PD_FRET', 'PD_FFOB', 'PD_APRV'],
                    'proddped': ['DP_QTDE', 'DP_VLUN', 'DP_VCOM', 'DP_VSEM', 'DP_VRIPI', 'DP_VRICMS',
                                 'DP_ICMSSUF', 'DP_IPISUFR', 'DP_ALIPI', 'DP_ALICMS', 'DP_QTORIG',
                                 'DP_DESMENB', 'DP_PRETABE'],
                    'dbascida': ['CI_ICMS'],
                    'dbasprod': ['PR_ALTU', 'PR_LARG', 'PR_PROF', 'PR_M2', 'PR_MCUB', 'PR_PESO', 'PR_PESOLIQ']
                }

                for record in table_dbf:
                    is_deleted = dbf.is_deleted(record)
                    if is_deleted and table_name != 'prodpedi':
                        continue
                    values = []
                    for col_name in columns:
                        try:
                            value = record[col_name]
                            if table_name in date_cols and col_name in date_cols.get(table_name, []):
                                values.append(parse_date(value))
                            elif isinstance(value, str):
                                values.append(value.strip())
                            elif table_name in numeric_cols and col_name in numeric_cols.get(table_name, []):
                                values.append(parse_decimal_as_string(value))
                            else:
                                values.append(value)
                        except (dbf.FieldMissingError, IndexError):
                            values.append(None)

                    final_tuple_list = list(values)
                    if table_name == 'prodpedi':
                        clie_index = columns.index('PD_CLIE')
                        original_clie_code = values[clie_index]
                        truncated_clie_code = original_clie_code[:-3] if original_clie_code and len(original_clie_code) > 3 else original_clie_code
                        final_tuple_list.append(truncated_clie_code)

                    final_tuple = tuple(final_tuple_list)
                    if is_deleted:
                        deleted_records_to_insert.append(final_tuple)
                    else:
                        if pk_index != -1 and values[pk_index] in seen_pks:
                            continue
                        if pk_index != -1:
                            seen_pks.add(values[pk_index])
                        records_to_insert.append(final_tuple)

            if records_to_insert:
                cols = columns + ['pd_clie_fk'] if table_name == 'prodpedi' else columns
                placeholders = ', '.join(['?'] * len(cols))
                sql = f"INSERT OR IGNORE INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders})"
                cursor.executemany(sql, records_to_insert)

            if deleted_records_to_insert:
                cols = columns + ['pd_clie_fk']
                placeholders = ', '.join(['?'] * len(cols))
                sql = f"INSERT INTO prodpedi_excluidos ({', '.join(cols)}) VALUES ({placeholders})"
                cursor.executemany(sql, deleted_records_to_insert)

            conn.commit()
            print(f"     OK: {len(records_to_insert)} registros importados e {len(deleted_records_to_insert)} arquivados para '{table_name}'.")
        except Exception as e:
            print(f"     ERRO DETALHADO ao processar {dbf_file_key}.DBF: {repr(e)}")
            traceback.print_exc()
            conn.rollback()

    for dest_table, config in UNIFIED_TABLES.items():
        print(f"  -> Processando e unificando para a tabela: {dest_table}")
        records_to_insert, deleted_records_to_insert, seen_keys = [], [], set()
        for source in config['sources']:
            dbf_file_path = os.path.join(dbf_path, source['dbf_file'])
            if not os.path.exists(dbf_file_path):
                print(f"     AVISO: Arquivo de origem {source['dbf_file']} não encontrado. Pulando.")
                continue

            print(f"     Lendo de: {source['dbf_file']}")
            try:
                with dbf.Table(dbf_file_path, codepage='cp850') as table_dbf:
                    prefix = source['prefix']
                    origin_tag = source['origin']
                    for record in table_dbf:
                        is_deleted = dbf.is_deleted(record)

                        nota_key = record[f'{prefix}NOTA']
                        orde_key = record[f'{prefix}ORDE']
                        tipo_key = record[f'{prefix}TIPO']

                        if nota_key or orde_key:
                            composite_key = f"{nota_key}-{orde_key}-{tipo_key}"
                            if composite_key in seen_keys:
                                continue
                            seen_keys.add(composite_key)

                        record_data = {'mv_origem': origin_tag}
                        for col in config['dest_columns']:
                            if col == 'mv_origem':
                                continue
                            source_col = col.replace('mv_', prefix).upper() if col != 'acerto' else 'ACERTO'
                            try:
                                value = record[source_col]
                                col_suffix = col.replace('mv_', '').upper()
                                if col_suffix in config['date_cols']:
                                    record_data[col] = parse_date(value)
                                elif col_suffix in config['numeric_cols']:
                                    record_data[col] = parse_decimal_as_string(value)
                                elif isinstance(value, str):
                                    record_data[col] = value.strip()
                                else:
                                    record_data[col] = value
                            except (dbf.FieldMissingError, IndexError):
                                record_data[col] = None

                        clie_code = record[f'{prefix}CLIE']
                        record_data['mv_clie_fk'] = clie_code[:-3] if clie_code and len(clie_code) > 3 else clie_code
                        final_tuple = tuple(record_data.get(col) for col in config['dest_columns'] + ['mv_clie_fk'])

                        if is_deleted:
                            deleted_records_to_insert.append(final_tuple)
                        else:
                            records_to_insert.append(final_tuple)
            except Exception as e:
                print(f"     ERRO DETALHADO ao processar {source['dbf_file']}: {repr(e)}")
                traceback.print_exc()

        if records_to_insert:
            cols = config['dest_columns'] + ['mv_clie_fk']
            placeholders = ', '.join(['?'] * len(cols))
            sql = f"INSERT INTO {dest_table} ({', '.join(cols)}) VALUES ({placeholders})"
            cursor.executemany(sql, records_to_insert)

        if deleted_records_to_insert:
            cols = config['dest_columns'] + ['mv_clie_fk']
            placeholders = ', '.join(['?'] * len(cols))
            sql = f"INSERT INTO {dest_table}_excluidos ({', '.join(cols)}) VALUES ({placeholders})"
            cursor.executemany(sql, deleted_records_to_insert)

        conn.commit()
        print(f"     OK: {len(records_to_insert)} registros unificados importados e {len(deleted_records_to_insert)} arquivados para '{dest_table}'.")

    ftnf_column_map = {
        'NF_TIPO': 'nf_tipo', 'NF_NUME': 'nf_nume', 'NF_DATA': 'nf_data', 'NF_DTSAIDA': 'nf_dtsaida', 'NF_REMD': 'nf_remd',
        'NF_TPVE': 'nf_tpve', 'NF_NATUREZ': 'nf_naturez', 'NF_CCFO': 'nf_ccfo', 'NF_CLIE': 'nf_clie', 'NF_NCIDA': 'nf_ncida',
        'NF_NOMPAIS': 'nf_nompais', 'NF_ESTA': 'nf_esta', 'NF_CCGC': 'nf_ccgc', 'NF_TTPROD': 'nf_ttprod', 'NF_VLCO': 'nf_vlco',
        'NF_BSCA': 'nf_bsca', 'NF_ICMS': 'nf_icms', 'NF_OICM': 'nf_oicm', 'NF_PICM': 'nf_picm', 'NF_VIPI': 'nf_vipi',
        'NF_PIPI': 'nf_pipi', 'NF_OIPI': 'nf_oipi', 'NF_OBSE': 'nf_obse', 'NF_PEDI': 'nf_pedi', 'NF_FORN': 'nf_forn',
        'NF_FRETE': 'nf_frete', 'NF_NFE': 'nf_nfe', 'NF_CRICMS': 'nf_cricms', 'NF_BSCRICM': 'nf_bscricm', 'NF_VOLUME': 'nf_volume',
        'NF_PESOBRU': 'nf_pesobru', 'NF_PESOLIQ': 'nf_pesoliq', 'NF_MOTCANC': 'nf_motcanc',
    }
    import_patterned_data(cursor, dbf_path, r'FTNF(\d{4})\.DBF', 'fatura_fiscal_capa', ftnf_column_map, ['NF_DATA', 'NF_DTSAIDA'], ['NF_TTPROD', 'NF_VLCO', 'NF_BSCA', 'NF_ICMS', 'NF_PICM', 'NF_VIPI', 'NF_PIPI', 'NF_FRETE', 'NF_BSCRICM', 'NF_VOLUME', 'NF_PESOBRU', 'NF_PESOLIQ'], {'NF_CLIE': lambda v: v[:-3] if isinstance(v, str) and len(v) > 3 else v})

    itnf_column_map = {
        'NF_TIPONF': 'nf_tiponf', 'NF_NUMERO': 'nf_numero', 'NF_SERIE': 'nf_serie', 'NF_CCFOIT': 'nf_ccfoit', 'NF_PRODUTO': 'nf_produto',
        'NF_UNIDADE': 'nf_unidade', 'NF_DESCRI': 'nf_descri', 'NF_NCM': 'nf_ncm', 'NF_SITTRI': 'nf_sittri', 'NF_VOLUME': 'nf_volume',
        'NF_PESOBRU': 'nf_pesobru', 'NF_PESOLIQ': 'nf_pesoliq', 'NF_QTPROD': 'nf_qtprod', 'NF_VRBRUTO': 'nf_vrbruto', 'NF_VRDESC': 'nf_vrdesc',
        'NF_PCDESC': 'nf_pcdesc', 'NF_VRLIQ': 'nf_vrliq', 'NF_DESCPIS': 'nf_descpis', 'NF_PERCPIS': 'nf_percpis', 'NF_DESCCOF': 'nf_desccof',
        'NF_PERCCOF': 'nf_perccof', 'NF_DESCICM': 'nf_descicm', 'NF_PERCICM': 'nf_percicm', 'NF_BSCAICM': 'nf_bscaicm', 'NF_VRICMS': 'nf_vricms',
        'NF_PCIMS': 'nf_pcims', 'NF_BCPRED': 'nf_bcpred', 'NF_BSCAIPI': 'nf_bscaipi', 'NF_VRIPI': 'nf_vripi', 'NF_PERCIPI': 'nf_percipi',
        'NF_ICMORIG': 'nf_icmorig', 'NF_VRFRETE': 'nf_vrfrete', 'NF_TPPIS': 'nf_tppis', 'NF_TVPIS': 'nf_tvpis', 'NF_TPCOFIN': 'nf_tpcofin',
        'NF_TVCOFIN': 'nf_tvcofin', 'NF_PFPC': 'nf_pfpc', 'NF_ALDES': 'nf_aldes', 'NF_VLFPC': 'nf_vlfpc', 'NF_VICDE': 'nf_vicde', 'NF_VICRE': 'nf_vicre',
    }
    import_patterned_data(
        cursor=cursor, dbf_path=dbf_path, pattern=r'ITNF(\d{4})\.DBF',
        dest_table='fatura_fiscal_itens',
        column_mapping=itnf_column_map,
        date_cols=[],
        numeric_cols=[
            'NF_VOLUME', 'NF_PESOBRU', 'NF_PESOLIQ', 'NF_QTPROD', 'NF_VRBRUTO',
            'NF_VRDESC', 'NF_PCDESC', 'NF_VRLIQ', 'NF_DESCPIS', 'NF_PERCPIS',
            'NF_DESCCOF', 'NF_PERCCOF', 'NF_DESCICM', 'NF_PERCICM', 'NF_BSCAICM',
            'NF_VRICMS', 'NF_PCIMS', 'NF_BCPRED', 'NF_BSCAIPI', 'NF_VRIPI',
            'NF_PERCIPI', 'NF_VRFRETE', 'NF_PFPC', 'NF_VLFPC', 'NF_VICDE', 'NF_VICRE',
            'NF_TVPIS', 'NF_TVCOFIN'
        ]
    )

    ficha_column_map = {
        'PRODUTO': 'produto_codi', 'PR_MEDIO': 'preco_medio',
        'PR_UPRE': 'ultimo_preco', 'DESPFIXA': 'despesa_fixa',
    }
    import_patterned_data(cursor, dbf_path, r'FICHA(\d{4})\.DBF', 'ficha_produto', ficha_column_map, [], ['PR_MEDIO', 'PR_UPRE', 'DESPFIXA'])

    try:
        print("\n" + "="*40)
        print("ATUALIZANDO RELACIONAMENTO ENTRE FATURAS E ITENS...")
        update_sql = "UPDATE fatura_fiscal_itens SET fatura_id = (SELECT id FROM fatura_fiscal_capa WHERE fatura_fiscal_capa.nf_nume = fatura_fiscal_itens.nf_numero AND fatura_fiscal_capa.periodo_origem = fatura_fiscal_itens.periodo_origem) WHERE EXISTS (SELECT 1 FROM fatura_fiscal_capa WHERE fatura_fiscal_capa.nf_nume = fatura_fiscal_itens.nf_numero AND fatura_fiscal_capa.periodo_origem = fatura_fiscal_itens.periodo_origem);"
        cursor.execute(update_sql)
        conn.commit()
        print(f"  -> OK: {cursor.rowcount} itens de fatura foram relacionados às suas capas.")
        print("="*40)
    except Exception as e:
        print(f"     ERRO ao atualizar o relacionamento de faturas: {e}")
        traceback.print_exc()

    calcular_e_salvar_margem(cursor)
    conn.commit()

    conn.close()
    print("PROCESSO DE IMPORTAÇÃO GERAL CONCLUÍDO.")
    print("="*60 + "\n")