/* Saved analysis packages are separate from live computation and researcher notes. */
const analysisStorageStates = new Map();
let analysisLinkedItemApplied = false;
let analysisLinkedEvidenceApplied = false;

function analysisStorageState() {
  const key = analysisState.itemId;
  if (!analysisStorageStates.has(key)) analysisStorageStates.set(key, {runs: [], busy: false, error: '', sequence: 0, pending: null});
  return analysisStorageStates.get(key);
}

function buildAnalysisStorage() {
  const panel = analysisCardPanel('分析を保存して読み返す', 'automatic', '', true);
  panel.panel.classList.add('analysis-storage');
  panel.body.append(analysisElement('p', 'analysis-caption',
    '見解・原文へのリンクを分析用Vaultに、全件データと条件をCSV／JSONに保存します。過去の結果も読み返せます。'));
  const button = contentButton('分析結果をObsidianに保存', () => saveAnalysisPackage(), 'primary-button small');
  button.dataset.archiveSave = 'true';
  const reload = contentButton('保存履歴を更新', () => loadAnalysisStorage());
  const bar = analysisElement('div', 'content-ai-toolbar'); bar.append(button, reload);
  const status = analysisElement('p', 'content-ai-status'); status.dataset.archiveStatus = 'true'; status.setAttribute('role', 'status');
  const history = analysisElement('div'); history.dataset.archiveHistory = 'true';
  panel.body.append(bar, status, history);
  return panel.panel;
}

function refreshAnalysisStorage() {
  if (!analysisState.data) return;
  const state = analysisStorageState();
  document.querySelectorAll('[data-archive-save], [data-archive-kwic]').forEach(button => {
    button.disabled = Boolean(state.busy || analysisState.dirty || analysisSaveInProgress);
  });
  document.querySelectorAll('[data-archive-status]').forEach(host => {
    host.textContent = state.busy ? '分析結果とVaultを保存しています…'
      : analysisState.dirty ? '設定・コードを保存してから分析結果を保存してください。'
      : state.error || `${state.runs.length}件の保存履歴 / AI仕上げ・AI見解は成功時に自動で記録します。`;
  });
  document.querySelectorAll('[data-archive-history]').forEach(host => {
    const key = JSON.stringify(state.runs.map(r => [r.id, r.status, r.vault_status, r.stale, r.error]));
    if (host.dataset.renderKey === key) return;
    host.dataset.renderKey = key; host.replaceChildren();
    const labels = {text_analysis: '文章分析', ai_insights: 'AI見解', ai_finishing: 'AI仕上げ', kwic: '文脈検索'};
    state.runs.forEach(run => {
      const details = analysisElement('details', 'analysis-archive-run');
      const summary = analysisElement('summary', '', `${labels[run.kind] || run.kind} / ${formatDate(run.created_at)}${run.stale ? ' / 更新が必要' : ''}`);
      const body = analysisElement('div', 'analysis-archive-body');
      body.append(analysisElement('p', 'analysis-caption', `元データ ${run.source_revision}版 / 分析 ${run.analysis_revision}版${run.model ? ` / ${run.model}` : ''}`));
      if (run.error) body.append(analysisElement('p', 'content-inline-notice', run.error));
      if (run.obsidian_uri) {
        const open = analysisElement('a', 'secondary-button compact-button', 'Obsidianで開く');
        open.href = run.obsidian_uri; body.append(open);
      }
      if (run.status !== 'writing' && (run.status !== 'completed' || run.vault_status !== 'completed')) {
        body.append(contentButton('保存済み結果から再試行', () => retrySavedVault(run.id)));
      }
      const files = analysisElement('div', 'analysis-archive-files');
      if (run.status === 'completed') {
        const bundle = analysisElement('a', 'analysis-export-link', 'export.zip');
        bundle.href = `/api/analysis/runs/${encodeURIComponent(run.id)}/export.zip`;
        bundle.download = '';
        files.append(bundle);
      }
      (run.artifacts || []).forEach(artifact => {
        const link = analysisElement('a', 'analysis-export-link', artifact.name);
        link.href = artifact.url; link.download = ''; files.append(link);
      });
      body.append(files); details.append(summary, body); host.append(details);
    });
  });
}

async function loadAnalysisStorage() {
  if (!analysisState.data) return;
  const itemId = analysisState.itemId;
  const state = analysisStorageState(); const sequence = ++state.sequence;
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/runs`, {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '保存履歴を取得できませんでした。');
    if (sequence !== state.sequence) return;
    state.runs = data.runs || [];
  } catch (error) { if (sequence === state.sequence) state.error = error.message; }
  if (analysisState.itemId === itemId) refreshAnalysisStorage();
}

async function saveAnalysisPackage(kwic = null) {
  if (!analysisState.data || analysisState.dirty || analysisSaveInProgress) return;
  const itemId = analysisState.itemId;
  const state = analysisStorageState();
  if (state.busy) return;
  const item = analysisState.data.item;
  const identity = JSON.stringify([itemId, item.revision_count, item.analysis_revision, kwic]);
  const storageKey = `gurumoji.analysisSave.${itemId}`;
  let pending = state.pending;
  try { pending = JSON.parse(sessionStorage.getItem(storageKey) || 'null') || pending; } catch (_) { /* optional storage */ }
  if (!pending || pending.identity !== identity) pending = {identity, request_id: crypto.randomUUID()};
  state.pending = pending; state.busy = true; state.error = ''; refreshAnalysisStorage();
  try { sessionStorage.setItem(storageKey, JSON.stringify(pending)); } catch (_) { /* keep in memory */ }
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/runs`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
        request_id: pending.request_id, source_revision: item.revision_count,
        analysis_revision: item.analysis_revision, ...(kwic ? {kwic} : {})
      })
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '分析結果を保存できませんでした。');
    state.pending = null;
    try { sessionStorage.removeItem(storageKey); } catch (_) { /* optional storage */ }
    state.error = data.run?.vault_status === 'completed' ? '分析結果とVaultを保存しました。'
      : data.run?.error || '結果ファイルは保存済みです。Vaultの状態を確認してください。';
  } catch (error) { state.error = error.message; }
  finally {
    state.busy = false;
    if (itemId === analysisState.itemId) { await loadAnalysisStorage(); refreshAnalysisStorage(); }
  }
}

async function retrySavedVault(runId) {
  const itemId = analysisState.itemId;
  const state = analysisStorageState();
  if (state.busy) return;
  state.busy = true; state.error = ''; refreshAnalysisStorage();
  try {
    const response = await apiFetch(`/api/analysis/runs/${encodeURIComponent(runId)}/vault`, {method: 'POST'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'Vaultを保存できませんでした。');
    state.error = data.run.error || '保存済みの結果からVaultを保存しました。';
  } catch (error) { state.error = error.message; }
  finally {
    state.busy = false;
    if (itemId === analysisState.itemId) { await loadAnalysisStorage(); refreshAnalysisStorage(); }
  }
}

async function openLinkedAnalysisEvidence() {
  if (analysisLinkedEvidenceApplied || !analysisState.data) return;
  const params = new URLSearchParams(location.search);
  const sid = params.get('segment');
  if (!sid || params.get('item') !== analysisState.itemId) return;
  analysisLinkedEvidenceApplied = true;
  const itemId = analysisState.itemId;
  const segment = analysisState.data.segments.find(s => s.id === sid);
  if (!segment) { setAlert(document.querySelector('#analysis-message'), '引用された発話は現在のデータにはありません。Vaultの保存済み原文を確認してください。', true); return; }
  if (params.get('text_hash')) {
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(segment.text))), b => b.toString(16).padStart(2, '0')).join('');
    if (analysisState.itemId !== itemId) return;
    if (hash !== params.get('text_hash') || Math.abs(Number(params.get('start')) - segment.start) > .001
      || Math.abs(Number(params.get('end')) - segment.end) > .001 || params.get('speaker') !== segment.speaker) {
      setAlert(document.querySelector('#analysis-message'), '引用の保存後に発話が更新されています。過去の原文はVaultで確認できます。現在の発話は分析画面から確認してください。', true);
      return;
    }
  }
  await openInsightMedia(segment);
}
