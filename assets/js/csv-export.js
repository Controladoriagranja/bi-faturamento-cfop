/* CSV compartilhado: precisão textual, páginas ordenadas e concorrência limitada. */
const CsvExport = (() => {
  const numeric = /^-?\d+(?:\.\d+)?(?:e[+-]?\d+)?$/i;
  function cell(value, decimal = false) {
    let text = value == null ? '' : String(value);
    if (decimal && numeric.test(text)) text = text.replace('.', ',');
    if (/^\s*[=+@-]/.test(text) && !(decimal && /^-\d/.test(text))) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  }
  function writer(headers, numericColumns = []) {
    const numbers = new Set(numericColumns), chunks = ['\uFEFF', headers.map(v => cell(v)).join(';') + '\r\n'];
    let count = 0;
    return {
      append(rows) {
        if (!rows.length) return;
        chunks.push(rows.map(row => row.map((v, i) => cell(v, numbers.has(i))).join(';')).join('\r\n') + '\r\n');
        count += rows.length;
      },
      get count() { return count; },
      download(name) {
        const url = URL.createObjectURL(new Blob(chunks, {type: 'text/csv;charset=utf-8'}));
        const link = document.createElement('a');
        link.href = url; link.download = name; document.body.append(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
      }
    };
  }
  async function pages({request, total, signal, cached, onPage}) {
    const size = 500, controller = new AbortController();
    const abort = () => controller.abort();
    const check = () => { if (controller.signal.aborted) throw new DOMException('Exportação cancelada.', 'AbortError'); };
    if (!Number.isSafeInteger(total) || total < 0) throw new Error('Quantidade de registros inválida. Consulte novamente.');
    signal?.addEventListener('abort', abort, {once: true});
    if (signal?.aborted) abort();
    try {
      check();
      if (cached?.pagina === 1 && cached.total_registros === total && cached.linhas?.length === total) {
        await onPage(cached.linhas, total); check(); return;
      }
      const last = Math.ceil(total / size);
      for (let first = 1; first <= last; first += 2) {
        const batch = await Promise.all(Array.from({length: Math.min(2, last - first + 1)}, async (_, offset) => {
          const page = first + offset;
          const data = await request(page, size, controller.signal);
          check();
          if (!Array.isArray(data.linhas) || data.total_registros !== total ||
              (data.pagina != null && data.pagina !== page) ||
              (data.por_pagina != null && data.por_pagina !== size) ||
              data.linhas.length !== Math.min(size, total - (page - 1) * size)) {
            throw new Error('A fonte mudou ou retornou uma página incompleta. Consulte novamente e repita a exportação.');
          }
          return data.linhas;
        }));
        for (const rows of batch) { check(); await onPage(rows, total); }
        // Libera o navegador para mostrar progresso e receber o cancelamento.
        await new Promise(resolve => setTimeout(resolve, 0));
      }
      check();
    } catch (error) { controller.abort(); throw error; }
    finally { signal?.removeEventListener('abort', abort); }
  }
  return {writer, pages};
})();
