"""Extrai só cadastros necessários da referência. Nunca importa faturamento semanal."""
import argparse
from datetime import date,timedelta
from decimal import Decimal
import json
from pathlib import Path

from fob.reference import cell_value,formula
from fob.workbook import extract
from fob.calculator import code,decimal
from .planilhas import (RULE_HEADERS,PAYROLL_HEADERS,MANAGER_HEADERS,MONTH_HEADERS,
                        PENDING_HEADERS,FREIGHT_HEADERS,CHARGES)

START='2026-10-01';END='2026-10-04'


def seed(path):
    sheets=extract(path,['Comiss','Despesas'],1150)
    commission=next(s for s in sheets if s.startswith('Comiss'))
    c=sheets[commission];d=sheets['Despesas'];rules=[];percent=[];vendors=[];managers=[];warnings=[]
    def v(sheet,row,col):return cell_value(sheet['rows'].get(str(row),{}),col)
    def manual(sheet,row,col,blank=Decimal(0)):
        if formula(sheet,row,col):raise ValueError(f'Entrada derivada não suportada: {col}{row}')
        value=v(sheet,row,col)
        return decimal(value) if value not in (None,'') else blank
    def add(reg,kind,value,origin,mode='KG',divisor=1,**dims):
        target=percent if kind in ('comissao','adicional_comissao') else rules
        target.append(dict(registro=reg,inicio=START,fim=END,tipo=kind,modalidade=mode,
                           valor=value,divisor=divisor,ativo='SIM',origem=origin,**dims))
    # Totais X/AE são entradas manuais: não reinterpretar as anotações de U:W.
    for kind,keycol,valcol,begin,end,label in [
        ('contrato','Z','AE',4,724,'cliente'),('contrato','S','X',4,161,'rede'),
        ('descarga','BG','BI',4,1150,'cliente')]:
        seen=set()
        for n in range(begin,end+1):
            key=v(d,n,keycol)
            if key in (None,'') or code(key) in seen:continue
            seen.add(code(key))
            try:value=manual(d,n,valcol)
            except ValueError as error:warnings.append(str(error));continue
            for unit in ('10','111','180') if kind=='contrato' else ('10','111','180','102'):
                add(f'{kind}:{unit}:{label}:{code(key)}',kind,value,f'Despesas!{valcol}{n}',
                    mode='PERCENTUAL' if kind=='contrato' else 'KG',unidade_documento=unit,**{label:code(key)})
    for unit in ('10','111','180','102'):
        # Defaults comprovados apenas para os quatro dias. Não extrapolar para o ano.
        for kind in ('contrato','contrato_administracao','pallet','descarga'):
            value=Decimal('0.38') if kind=='contrato_administracao' and unit=='180' else Decimal(0)
            add(f'{kind}:{unit}:padrao',kind,value,'Fórmula da referência: literal / IFERROR / não se aplica',unidade_documento=unit)
        add(f'adicional:{unit}:padrao','adicional_comissao',Decimal(0),'Literal AW=0 fora de Januária',unidade_documento=unit)
    for n in range(4,1151):
        client=v(d,n,'AG')
        if client not in (None,''):
            for unit in ('10','111','180'):
                add(f'pallet:{unit}:{code(client)}','pallet',manual(d,3,'AI'),
                    f'Despesas!AG{n}; AI3/1000',divisor=1000,unidade_documento=unit,cliente=code(client))
        for cols,units in [(('AT','AU','AW','AX'),{'10','111','180'}),(('BA','BB','BD','BE'),{'102'})]:
            unit=code(v(d,n,cols[0]));product=code(v(d,n,cols[1]));uf=v(d,n,cols[2])
            if unit not in units or not product or not uf:continue
            try:value=manual(d,n,cols[3],None)
            except ValueError as error:warnings.append(str(error));continue
            if value is None:continue
            add(f'reversa:{unit}:{product}:{uf}','logistica_reversa',value,
                f'Despesas!{cols[3]}{n}',unidade_documento=unit,produto=product,uf=uf)
    # Januária: Comissão geral CD P; adicional derivado P/12 é recalculado, não copiado de Q.
    for n in (4,5):
        if code(v(d,n,'N'))=='102':
            add('comissao:102','comissao',manual(d,n,'P'),f'Despesas!P{n}','PERCENTUAL',unidade_documento='102')
            percent=[r for r in percent if r['registro']!='adicional:102:padrao']
            add('adicional:102','adicional_comissao',manual(d,n,'P'),
                f'Despesas!Q{n}=P{n}/12','PERCENTUAL',divisor=12,unidade_documento='102')
    # Os vínculos dos gestores eram por nome; os novos modelos usam códigos opacos.
    names={}
    for n in range(103,112):
        if v(c,n,'F'):names.setdefault(str(v(c,n,'F')),'gestor:'+str(n))
    charges=[manual(c,3,col) for col in ('R','S','T','U','V','W','X','Y','Z','AA','AB')]
    common=dict(inicio=START,fim=END,dias_uteis=manual(c,2,'H'),domingos_feriados=manual(c,3,'H'),
                dias_mes=Decimal(31),dias_periodo=Decimal(4),ativo='SIM',**dict(zip(CHARGES,charges)))
    # Dias são documentados pelo recorte de outubro; não copiar K2/K3 como regra futura.
    def flags(n):
        result={}
        for key,col,expected in [('dsr_comissao','O',f'=(N{n}/$H$2*$H$3)'),
                                 ('dsr_premio','P',f'=(I{n}/$H$2*$H$3)'),
                                 ('base_encargos','Q',f'=H{n}+I{n}+N{n}+O{n}+P{n}')]:
            expression=formula(c,n,col)
            if expression==expected:result[key]='SIM'
            elif not expression and manual(c,n,col)==0:result[key]='NAO'
            else:raise ValueError(f'{commission}!{col}{n}: regra não suportada.')
        return result
    for n in range(5,100):
        seller=v(c,n,'E')
        if seller in (None,''):continue
        row=dict(common,**flags(n),registro='folha:'+code(seller),vendedor=code(seller),origem=f'{commission}!H:K{n}; N:AK derivadas')
        for key,col in [('salario','H'),('premio','I'),('percentual','J'),('adicional_percentual','K')]:
            expression=formula(c,n,col)
            if col=='K' and expression==f'=J{n}/12':row[key]=None;continue
            if col=='J' and expression==f'=VLOOKUP(E{n},Despesas!$G:$L,3,0)':
                found=next(j for j in range(4,1151) if code(v(d,j,'G'))==code(seller))
                row[key]=manual(d,found,'I');continue
            row[key]=manual(c,n,col)
        row['adicional_modo']='UM_DOZE' if formula(c,n,'K')==f'=J{n}/12' else 'DIGITADO'
        for key,col in [('gestor1','B'),('gestor2','C'),('gestor3','D')]:
            name=str(v(c,n,col) or '')
            row[key]=names.get(name,'')
            if name and name not in names:warnings.append(f'{commission}!{col}{n}: gestor não encontrado; IFERROR original=0.')
        vendors.append(row)
    for n in range(103,112):
        name=str(v(c,n,'F') or '')
        if name not in names:continue
        row=dict(common,**flags(n),registro=names[name],origem=f'{commission}!{n}; AE recalculado')
        base_formula=formula(c,n,'L')
        level=next((i for i,col in enumerate(('B','C','D'),1) if f'${col}$4:${col}$99' in base_formula),None)
        if level is None:
            warnings.append(f'{commission}!L{n}: base de equipe não comprovada; gestor pendente.');continue
        row['nivel']=level
        if not formula(c,n,'AE'):row['base_manual']=manual(c,n,'AE')
        else:
            expected=f'=AC{n}+AD{n}'
            if formula(c,n,'AE')!=expected:
                warnings.append(f'{commission}!AE{n}: fórmula não suportada, gestor não preparado.');continue
            for key,col in [('salario','H'),('premio','I'),('percentual','J'),('adicional_percentual','K')]:row[key]=manual(c,n,col)
            row['adicional_modo']='DIGITADO'
        managers.append(row)
    # Excel VLOOKUP usa primeira ocorrência; registrar duplicatas divergentes sem escolher silenciosamente.
    unique={}
    for row in rules:
        if row['registro'] in unique and row!=unique[row['registro']]:
            warnings.append('Cadastro duplicado no Excel, primeira ocorrência preservada: '+row['registro'])
        else:unique.setdefault(row['registro'],row)
    def sheet(name,headers,rows,title,help_text):
        return dict(name=name,headers=headers,rows=[[r.get(k) for k in headers] for r in rows],title=title,help=help_text)
    return dict(origem=str(Path(path).name),avisos=warnings,files={
        'Fretes.xlsx':[
            sheet('Pendências',PENDING_HEADERS,[],'Fretes a preencher · atualização automática',
                'O robô mostra itens do banco. Para NF, copie os identificadores/assinatura e deixe chave_item vazia.'),
            sheet('Preenchimentos',FREIGHT_HEADERS,[],'Fretes · preenchimento da funcionária',
                'escopo NF ou ITEM; modalidade TOTAL (R$) ou KG (R$/kg). Não misture NF e ITEM. Valor vazio não é zero.')],
        'Despesas.xlsx':[
            sheet('Cadastros',RULE_HEADERS,list(unique.values()),'Despesas · cadastros com vigência',
                'Datas inclusivas. PERCENTUAL em fração: 0,03 = 3%. Para encerrar use ativo NAO; não apague o histórico.'),
            sheet('Custo Mensal Januária',MONTH_HEADERS,[dict(competencia='2026-10-01',custo_kg=Decimal('0.6127658079'),origem='Valor confirmado pelo usuário em 21/10/2026')],
                'Januária · custo único por competência','Competência dia 01. Substitui todo frete. Sem mês próprio, usa outubro/2026; sem outubro fica pendente.')],
        'Comissoes.xlsx':[
            sheet('Vendedores',PAYROLL_HEADERS,vendors,'Comissões · parâmetros de vendedores (restrito)',
                'H:K e encargos do Excel; backend calcula N:AK pelo faturamento integral da vigência. Não informar AK pronto.'),
            sheet('Gestores',MANAGER_HEADERS,managers,'Comissões · parâmetros de gestores (restrito)',
                'Códigos gestor:103 etc. Nível 1/2/3 vem da fórmula L/M. Custos de gestores são recalculados.'),
            sheet('Percentuais',RULE_HEADERS,percent,'Comissões · percentuais e adicionais por unidade',
                'Fração decimal; percentual incide sobre valor_total_faturado / peso. Vigência inicial somente 01 a 04/10/2026.')]
        })


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('excel',type=Path);p.add_argument('saida',type=Path)
    a=p.parse_args();a.saida.write_text(json.dumps(seed(a.excel),ensure_ascii=False,default=str),encoding='utf-8')


if __name__=='__main__':main()
