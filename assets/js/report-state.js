/* Estado de interface por relatório e por aba. Não armazena dados nem credenciais. */
class ReportState {
  constructor(page) {
    this.key=`granja-faturamento:${page}:v1`;
    try {
      const saved=JSON.parse(sessionStorage.getItem(this.key)||'null');
      this.data=saved&&typeof saved==='object'&&!Array.isArray(saved)?saved:{};
    } catch (_) {this.data={};}
    this.ready=false;
  }
  get(key,fallback=null) {return this.data[key]??fallback;}
  save(changes) {
    Object.assign(this.data,changes);
    try {sessionStorage.setItem(this.key,JSON.stringify(this.data));} catch (_) {}
  }
  bind({form,filters,dates}) {
    this.filters=filters;this.dates=dates;
    const save=()=>this.saveDraft();
    document.getElementById(form).addEventListener('input',save);
    document.getElementById(form).addEventListener('change',save);
    window.addEventListener('pagehide',save);
    // Salva antes de seguir links, inclusive quando o navegador usa seu cache de páginas.
    document.addEventListener('click',event=>{if(event.target.closest('a[href]'))save();});
  }
  current() {
    return {...Object.fromEntries(Object.entries(this.dates).map(([key,id])=>[key,document.getElementById(id).value])),...this.filters.values()};
  }
  saveDraft() {if(this.ready)this.save({draft:this.current()});}
  parameters(source) {
    if(!source||typeof source!=='object'||Array.isArray(source))return null;
    const params={};
    for(const key of Object.keys(this.dates)) {
      const value=source[key];
      if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||Number.isNaN(Date.parse(value)))return null;
      params[key]=value;
    }
    if(params.data_inicio>params.data_fim)return null;
    for(const field of this.filters.fields) {
      const selected=Array.isArray(source[field.apiKey])?source[field.apiKey].filter(v=>typeof v==='string'&&v.length<=150).slice(0,100):[];
      if(selected.length)params[field.apiKey]=selected;
    }
    return params;
  }
  restore(defaults) {
    const saved=this.get('draft');
    const draft=saved&&typeof saved==='object'&&!Array.isArray(saved)?saved:defaults;
    for(const [key,id] of Object.entries(this.dates)) {
      const value=draft[key];
      document.getElementById(id).value=typeof value==='string'&&(value===''||/^\d{4}-\d{2}-\d{2}$/.test(value))?value:defaults[key]||'';
    }
    for(const field of this.filters.fields)this.filters.set(field.apiKey,Array.isArray(draft[field.apiKey])?draft[field.apiKey].filter(v=>typeof v==='string').slice(0,100):[]);
    this.ready=true;this.saveDraft();
  }
  applied() {return this.parameters(this.get('applied'));}
  matchesDraft(params) {
    const normalized=value=>JSON.stringify(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,v])=>[key,Array.isArray(v)?[...v].sort():v]));
    return normalized(this.current())===normalized(params);
  }
}
