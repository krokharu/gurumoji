/* 接続確認と明示的な管理ノート検索。返却文字列はテキストとして表示する。 */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const dialog = $('#obussql-dialog');
  if (!dialog) return;
  const notes = $('#obussql-notes'), results = $('#obussql-results');
  const message = $('#obussql-message'), query = $('#obussql-query');
  const search = $('#obussql-search'), more = $('#obussql-more'), refresh = $('#obussql-refresh');
  const selected = new Map(), titles = new Map();
  let available = false, nextOffset = null, searching = false, listing = false, checking = false;
  let statusSequence = 0, notesSequence = 0, searchSequence = 0, dialogSequence = 0, searchRequest = 0;
  const node = (tag, text = '') => { const element = document.createElement(tag); element.textContent = text; return element; };
  async function request(url, payload) {
    const response = await apiFetch(url, payload === undefined ? {} : {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'ObusSQLへの接続に失敗しました。');
    return data;
  }
  function sync() {
    $('#obussql-selected-count').textContent = `${selected.size} / 16件を選択`;
    search.disabled = !available || searching || listing || !selected.size || !query.value.trim();
    more.disabled = listing || searching;
    refresh.disabled = checking || listing || searching;
  }
  function invalidate() { searchSequence += 1; results.replaceChildren(); message.textContent = ''; sync(); }
  function paintStatus(data) {
    available = data.available === true;
    document.querySelectorAll('[data-obussql-pill]').forEach(pill => {
      pill.classList.remove('loading', 'ready', 'missing');
      pill.classList.add(available ? 'ready' : 'missing');
      pill.textContent = available ? 'ObusSQL 接続済み（ノート読取）' : 'ObusSQL 未接続';
    });
    document.querySelectorAll('[data-obussql-detail]').forEach(detail => {
      detail.textContent = available ? '管理ノートの読取接続を確認しました。対象と検索語を選んでください。' : (data.message || '接続状態を確認できませんでした。');
    });
    const maf = data.maf;
    $('#obussql-maf-detail').textContent = maf ? `ワークフロー実行：${maf.message || '状態を確認できませんでした。'} ノート読取とは別の接続です。` : '';
    if (data.dev_bridge?.enabled) {
      $('#obussql-maf-detail').textContent = data.dev_bridge.message || '開発版MAF分析の状態を確認できませんでした。';
    }
    if (!available) { selected.clear(); notes.replaceChildren(); more.hidden = true; invalidate(); }
    sync();
  }
  async function loadStatus() {
    const sequence = ++statusSequence;
    checking = true; sync();
    try {
      const data = await request('/api/obsidian/obussql');
      if (sequence !== statusSequence) return false;
      paintStatus(data);
      return available;
    } catch (error) {
      if (sequence === statusSequence) paintStatus({available: false, message: error.message});
      return false;
    } finally { if (sequence === statusSequence) { checking = false; sync(); } }
  }
  async function loadNotes(offset = 0) {
    if (!available || listing || !dialog.open) return;
    const sequence = ++notesSequence;
    listing = true;
    if (offset === 0) { selected.clear(); titles.clear(); notes.replaceChildren(); invalidate(); }
    message.textContent = '管理ノートを確認しています…'; sync();
    try {
      const data = await request(`/api/obsidian/obussql/notes?offset=${offset}`);
      if (sequence !== notesSequence || !dialog.open) return;
      for (const note of data.notes || []) {
        const label = node('label'); label.className = 'obussql-note';
        const checkbox = document.createElement('input'); checkbox.type = 'checkbox';
        titles.set(note.note_id, note.title || note.note_id);
        const text = node('span', note.title || note.note_id); text.append(node('small', note.vault));
        checkbox.addEventListener('change', () => {
          if (checkbox.checked && selected.size >= 16) {
            checkbox.checked = false; message.textContent = '対象ノートは最大16件です。'; return;
          }
          if (checkbox.checked) selected.set(note.note_id, {note_id: note.note_id, sha256: note.sha256});
          else selected.delete(note.note_id);
          invalidate();
        });
        label.append(checkbox, text); notes.append(label);
      }
      nextOffset = Number.isInteger(data.next_offset) ? data.next_offset : null;
      more.hidden = nextOffset === null;
      message.textContent = notes.children.length ? `${notes.children.length}件の候補を表示しています。` : '読取対象の管理ノートがありません。アプリから保存した管理ノートが対象です。';
    } catch (error) { if (sequence === notesSequence && dialog.open) message.textContent = error.message; }
    finally { if (sequence === notesSequence) { listing = false; sync(); } }
  }
  function render(data) {
    const context = data.context;
    if (context?.schema_version !== 'bounded-context-v1' || !Array.isArray(context.selection)) {
      throw new Error('ObusSQLの結果形式が確認対象と異なります。接続する版を確認してください。');
    }
    const articles = [];
    for (const entry of context.selection) {
      const quote = entry.node?.original?.quote;
      if (!quote || typeof quote.text !== 'string') throw new Error('ObusSQLの根拠本文を確認できませんでした。');
      const article = node('article');
      article.append(node('h4', titles.get(quote.resource_id) || quote.resource_id || '管理ノート'));
      article.append(node('pre', quote.text));
      article.append(node('small', [quote.line_start ? `行 ${quote.line_start}–${quote.line_end || quote.line_start}` : '', quote.source_revision ? `版 ${quote.source_revision}` : ''].filter(Boolean).join(' / ')));
      articles.push(article);
    }
    results.replaceChildren(...articles);
    message.textContent = articles.length ? `${articles.length}件の根拠を表示しました。選択範囲と読取量の上限内での一致結果です。` : '指定した範囲に表示できる一致結果はありません。';
  }
  async function open() {
    const sequence = ++dialogSequence;
    if (!dialog.open) dialog.showModal();
    if (await loadStatus() && sequence === dialogSequence) await loadNotes();
  }
  document.querySelectorAll('[data-open-obussql]').forEach(button => button.addEventListener('click', open));
  refresh.addEventListener('click', async () => { if (await loadStatus()) await loadNotes(); });
  more.addEventListener('click', () => { if (nextOffset !== null) loadNotes(nextOffset); });
  query.addEventListener('input', invalidate);
  $('#obussql-search-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (search.disabled) return;
    const sequence = ++searchSequence;
    const requestId = ++searchRequest;
    const payload = {notes: [...selected.values()], query: query.value.trim()};
    searching = true; results.replaceChildren(); message.textContent = '選択したノートを検索しています…'; sync();
    try {
      const data = await request('/api/obsidian/obussql/preview', payload);
      if (sequence === searchSequence && dialog.open) render(data);
    } catch (error) { if (sequence === searchSequence && dialog.open) message.textContent = error.message; }
    finally { if (requestId === searchRequest) { searching = false; sync(); } }
  });
  $('#obussql-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    dialogSequence += 1; notesSequence += 1; searchSequence += 1; searchRequest += 1;
    listing = false; searching = false; sync();
  });
  sync(); loadStatus();
})();
