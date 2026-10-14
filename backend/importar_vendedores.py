"""Lê o XLSX e gera carga idempotente. Não conecta ao banco nem executa SQL."""
import argparse,json
from collections import Counter
from pathlib import Path
import openpyxl

def codigo(v):
    if v is None:return ''
    if isinstance(v,(int,float)):
        if float(v)!=int(v):raise ValueError('Código de vendedor fracionado.')
        v=str(int(v))
    s=str(v).strip()
    if not s.isdigit():raise ValueError('Código de vendedor não numérico: '+s)
    return s.lstrip('0') or '0'

def ler_planilha(arquivo):
    w=openpyxl.load_workbook(arquivo,read_only=True,data_only=True)
    rows=list(w.worksheets[0].values)
    if tuple(str(v or '').strip() for v in rows[1][:4])!=('Vendedor','Nome','Canal Venda','Vendedor Pai'):
        raise ValueError('Cabeçalho esperado na segunda linha da primeira aba.')
    usados={};duplicados=[];lidas=0
    for row in rows[2:]:
        if row[0] is None or str(row[0]).strip()=='':continue
        lidas+=1;v=codigo(row[0]);textos=[str(x or '').strip() for x in row[1:4]]
        textos=[x.replace('Varejo Grande Bh','Varejo Grande BH') for x in textos]
        item=dict(zip(('vendedor','nome','canal_venda','vendedor_pai'),[v,*textos]))
        if v in usados:
            if usados[v]!=item:raise ValueError('Mapeamento conflitante para vendedor '+v)
            duplicados.append(v);continue
        usados[v]=item
    w.close()
    return list(usados.values()),dict(registros_lidos=lidas,codigos_unicos=len(usados),duplicados_identicos=duplicados)

def gerar_sql(rows):
    def literal(v):return "'"+v.replace("'","''")+"'"
    return ('-- Gerado do XLSX oficial; rever antes de executar em produção.\nBEGIN;\n'
      'INSERT INTO comercial.vendedor_grupo (vendedor,nome,canal_venda,vendedor_pai) VALUES\n'+
      ',\n'.join('('+','.join(literal(r[k]) for k in ('vendedor','nome','canal_venda','vendedor_pai'))+')' for r in rows)+
      '\nON CONFLICT (vendedor) DO UPDATE SET nome=EXCLUDED.nome,\n'
      'canal_venda=EXCLUDED.canal_venda,vendedor_pai=EXCLUDED.vendedor_pai;\nCOMMIT;\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('xlsx',type=Path);p.add_argument('--gerar-sql',type=Path,required=True)
    a=p.parse_args();rows,audit=ler_planilha(a.xlsx)
    a.gerar_sql.parent.mkdir(parents=True,exist_ok=True)
    a.gerar_sql.write_text(gerar_sql(rows),encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=False))
