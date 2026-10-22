// Ferramenta local de preparação. O robô operacional NÃO depende de Node/artifact-tool.
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [seedPath, outputDir, previewDir] = process.argv.slice(2);
const seed = JSON.parse(await fs.readFile(seedPath,'utf8'));
await fs.mkdir(outputDir,{recursive:true});
await fs.mkdir(previewDir,{recursive:true});
const ids=new Set(['registro','vendedor','gestor1','gestor2','gestor3','empresa_contexto','unidade_documento',
  'serie','nota_numero','produto','cliente','rede','familia','uf','rota_cliente','chave_item','assinatura_nf',
  'escopo','modalidade','tipo','ativo','origem','observacao','situacao','motivo','produto_descricao','adicional_modo',
  'dsr_comissao','dsr_premio','base_encargos']);
const dates=new Set(['inicio','fim','competencia']);
function col(n){let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;}
try { for(const [filename,sheets] of Object.entries(seed.files)){
  const wb=Workbook.create();
  for(const [sheetIndex,spec] of sheets.entries()){
    const sh=wb.worksheets.add(spec.name),end=col(spec.headers.length),last=Math.max(6,spec.rows.length+5);
    sh.showGridLines=false;sh.tabColor='#7d1626';sh.freezePanes.freezeRows(5);
    sh.getRange(`A1:${end}${last}`).format.font={name:'Arial',size:10,color:'#26332c'};
    sh.getRange(`A1:${end}${last}`).format.columnWidth=19;
    sh.getRange(`A1:${end}${last}`).format.rowHeight=22;
    sh.getRange('A1').values=[[spec.title]];sh.getRange('A1').format.font={name:'Arial',size:14,bold:true,color:'#7d1626'};
    sh.getRange('A2').values=[[spec.help]];sh.getRange('A2').format.font={name:'Arial',size:10,color:'#5c675f'};
    sh.getRange('A3').values=[['Modelo local · origem '+seed.origem+' · cadastros financeiros validados somente em 01–04/10/2026']];
    sh.getRange(`A5:${end}5`).values=[spec.headers];
    sh.getRange(`A5:${end}5`).format={fill:'#7d1626',font:{name:'Arial',size:10,bold:true,color:'#ffffff'},rowHeight:34,wrapText:true};
    const rows=spec.rows.map(row=>row.map((v,i)=>{
      if(v===null||v==='')return null;
      const key=spec.headers[i];
      if(dates.has(key))return new Date(v+'T12:00:00Z');
      return ids.has(key)?String(v):Number(v);
    }));
    if(rows.length)sh.getRange(`A6:${end}${last}`).values=rows;
    spec.headers.forEach((key,i)=>{
      const range=sh.getRange(`${col(i+1)}6:${col(i+1)}${Math.max(last,200)}`);
      const integer=key==='ano_nf'||key==='nivel'||key.startsWith('dias_')||key==='domingos_feriados'||key==='divisor';
      const percent=key.includes('percentual')||['fgts','inss_empresa','inss_terceiros','sat','fap','decimo_terceiro','fgts_decimo','inss_decimo','ferias','fgts_ferias','inss_ferias'].includes(key);
      range.setNumberFormat(dates.has(key)?'dd/mm/yyyy':ids.has(key)?'@':integer?'0':percent?'0.0000%':key==='custo_kg'?'0.0000000000':key==='salario'||key==='premio'?'#,##0.00':'0.##############');
      if(ids.has(key))range.format.font.color='#18653f';
      else range.format.font.color='#1261a0';
      if(key==='origem'||key==='observacao'||key==='motivo')sh.getRange(`${col(i+1)}5:${col(i+1)}${last}`).format.columnWidth=44;
      if(key==='registro')sh.getRange(`${col(i+1)}5:${col(i+1)}${last}`).format.columnWidth=42;
      if(key==='chave_item'||key==='assinatura_nf')sh.getRange(`${col(i+1)}5:${col(i+1)}${last}`).format.columnWidth=72;
      if(['ativo','modalidade','escopo'].includes(key))range.dataValidation={rule:{type:'list',values:key==='ativo'?['SIM','NAO']:key==='escopo'?['NF','ITEM']:spec.name==='Preenchimentos'?['TOTAL','KG']:['KG','PERCENTUAL']}};
    });
    // Tabelas automáticas sem fórmulas nem links externos. Pendências usa somente filtro.
    if(spec.name!=='Pendências')sh.tables.add(`A5:${end}${last}`,true,`TabelaCustos${sheetIndex+1}`).style='TableStyleLight1';
    else {
      const status=col(spec.headers.indexOf('situacao')+1);
      sh.getRange(`${status}6:${status}30005`).conditionalFormats.add('cellIs',{operator:'equal',formula:'"REVISAR_IDENTIFICACAO"',format:{fill:'#fce4d6'}});
      sh.getRange(`${status}6:${status}30005`).conditionalFormats.add('cellIs',{operator:'equal',formula:'"PENDENTE"',format:{fill:'#fff2cc'}});
    }
  }
  wb.recalculate();
  const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',options:{useRegex:true,maxResults:10}});
  console.log(filename,'abas',sheets.length,'linhas',sheets.map(s=>s.rows.length).join(','),scan.ndjson.slice(0,160));
  for(const spec of sheets){
    const preview=await wb.render({sheetName:spec.name,range:`A1:${col(Math.min(spec.headers.length,7))}10`,scale:1,format:'png'});
    await fs.writeFile(path.join(previewDir,filename.replace('.xlsx','')+'-'+spec.name.replaceAll(' ','_')+'.png'),new Uint8Array(await preview.arrayBuffer()));
  }
  await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(previewDir,filename));
  await fs.copyFile(path.join(previewDir,filename),path.join(outputDir,filename));
} } catch(error) { console.error(error.message); process.exitCode=1; }
