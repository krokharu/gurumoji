/* AI用ZIPの選択・取消・入力版の確認を既存画面へ接続する。 */
(() => {
// 分析準備パネルの表示幅にかかわらず、ダウンロードの所有者を一つにする。
let aiDataExportSelection = null;
let aiDataExportOwner = null;
const aiDataExportAttributes = ['organization', 'department', 'job_title', 'session_role', 'session_role_source'];

function cancelAiDataExport() {
  if (!aiDataExportOwner) return;
  const owner = aiDataExportOwner;
  aiDataExportOwner = null;
  owner.controller.abort();
  owner.selection.message = 'ダウンロードを取り消しました。サーバー側の処理停止は確認していません。';
  syncAiDataExportControls();
}

function syncAiDataExportControls() {
  const selection = aiDataExportSelection;
  if (!selection) return;
  const busy = Boolean(aiDataExportOwner);
  document.querySelectorAll('[data-ai-data-export]').forEach(panel => {
    panel.setAttribute('aria-busy', String(busy));
    panel.querySelector('[data-ai-export-names]').checked = selection.include_names;
    panel.querySelectorAll('[data-ai-export-attribute]').forEach(input => {
      input.checked = selection.speaker_attributes.includes(input.dataset.aiExportAttribute);
    });
    panel.querySelector('[data-ai-export-frames]').checked = selection.frames.enabled;
    panel.querySelectorAll('[data-ai-export-frame]').forEach(input => {
      input.value = selection.frames[input.dataset.aiExportFrame];
    });
    panel.querySelectorAll('input, [data-ai-export-download]').forEach(input => { input.disabled = busy; });
    panel.querySelector('[data-ai-export-frame-options]').disabled = busy || !selection.frames.enabled;
    panel.querySelector('[data-ai-export-cancel]').disabled = !busy;
    panel.querySelector('[data-ai-export-status]').textContent = selection.message;
  });
}

function aiDataExportFailure(status, result) {
  const messages = {
    400: '出力条件が正しくありません。範囲・枚数を確認してください。',
    404: '対象データが見つかりません。一覧から選び直してください。',
    409: '保存済みデータまたは動画が更新されました。対象を再読み込みしてから出力してください。',
    422: '動画を利用できないか、フレームを抽出できませんでした。動画と出力条件を確認してください。',
    408: '抽出の制限時間を超えました。範囲・枚数を減らして再試行してください。'
  };
  // Do not echo backend messages, media paths or arbitrary structured fields.
  const frames = result && typeof result === 'object' ? (result.frames || result.error?.frames) : null;
  const statuses = {partial: 'フレーム抽出は一部失敗しました。', failed: 'フレーム抽出に失敗しました。',
    unavailable: '動画フレームを利用できません。', unsupported: 'この動画形式には対応していません。'};
  const frameStatus = Object.hasOwn(statuses, frames?.status) ? statuses[frames.status] : '';
  return `${messages[status] || 'ZIPを作成できませんでした。時間をおいて再試行してください。'}${frameStatus ? ` ${frameStatus}` : ''} ZIPはダウンロードされていません。`;
}

async function downloadAiDataExport(panel, selection, prepared) {
  if (selection !== aiDataExportSelection || !panel.isConnected) return;
  const frames = {enabled: selection.frames.enabled};
  if (frames.enabled) {
    for (const key of ['start', 'end', 'interval', 'max_frames', 'max_dimension']) {
      const value = selection.frames[key];
      frames[key] = value.trim() === '' ? NaN : Number(value);
    }
    const valid = Object.values(frames).every(value => typeof value === 'boolean' || Number.isFinite(value))
      && frames.start >= 0 && frames.end >= frames.start && frames.end - frames.start <= 600
      && frames.interval >= 1 && Number.isInteger(frames.max_frames) && frames.max_frames >= 1 && frames.max_frames <= 24
      && Number.isInteger(frames.max_dimension) && frames.max_dimension >= 16 && frames.max_dimension <= 1280
      && Math.floor((frames.end - frames.start) / frames.interval) + 1 <= frames.max_frames;
    if (!valid) {
      selection.message = '動画の条件を確認してください。開始0秒以上・終了は開始以降600秒以内・間隔1秒以上・指定枚数1〜24枚以内・長辺16〜1280pxの有限な数値が必要です。枚数には開始・終了時刻のフレームも含みます。';
      syncAiDataExportControls();
      panel.querySelector('[data-ai-export-frame="start"]').focus();
      return;
    }
  }
  cancelAiDataExport();
  const owner = {selection, itemId: analysisState.itemId, sourceHash: prepared.source_hash, revision: prepared.revision,
    context: captureAnalysisContext(), controller: new AbortController()};
  aiDataExportOwner = owner;
  const current = () => aiDataExportOwner === owner && !owner.controller.signal.aborted
    && analysisState.itemId === owner.itemId && isAnalysisContextCurrent(owner.context)
    && analysisState.data?.manual?.preparation?.source_hash === owner.sourceHash
    && analysisState.data?.manual?.preparation?.revision === owner.revision;
  selection.message = 'ZIPを作成しています… ダウンロードを取り消せます。';
  const startedWithFocus = document.activeElement === panel.querySelector('[data-ai-export-download]');
  syncAiDataExportControls();
  if (startedWithFocus) panel.querySelector('[data-ai-export-cancel]').focus();
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(owner.itemId)}/ai-export.zip`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, signal: owner.controller.signal,
      body: JSON.stringify({include_names: selection.include_names,
        speaker_attributes: aiDataExportAttributes.filter(key => selection.speaker_attributes.includes(key)),
        expected_source_hash: owner.sourceHash, expected_revision: owner.revision, frames})
    });
    if (!current()) return;
    if (!response.ok) {
      let result = null;
      try { result = await response.json(); } catch (_) { /* Safe status fallback for non-JSON failures. */ }
      if (current()) selection.message = aiDataExportFailure(response.status, result);
      return;
    }
    if ((response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() !== 'application/zip') {
      selection.message = 'ZIP形式の応答を受け取れませんでした。ファイルはダウンロードされていません。';
      return;
    }
    const blob = await response.blob();
    if (!current()) return;
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'gurumoji-ai-data.zip';
    try {
      document.body.append(link);
      link.click();
      selection.message = 'ZIPのダウンロードを開始しました。外部AIへ自動送信していません。';
    } finally {
      link.remove();
      URL.revokeObjectURL(url);
    }
  } catch (error) {
    if (current()) selection.message = '通信に失敗しました。ZIPはダウンロードされていません。再試行してください。';
  } finally {
    if (aiDataExportOwner === owner) {
      if (!current()) selection.message = '対象または入力版が変わったため、ダウンロードを取り消しました。サーバー側の処理停止は確認していません。';
      aiDataExportOwner = null;
      const restoreFocus = panel.isConnected && document.activeElement === panel.querySelector('[data-ai-export-cancel]');
      syncAiDataExportControls();
      if (restoreFocus) panel.querySelector('[data-ai-export-download]').focus();
    }
  }
}

function renderAiDataExport(prepared, key) {
  if (!aiDataExportSelection || aiDataExportSelection.key !== key) {
    cancelAiDataExport();
    aiDataExportSelection = {key, include_names: false, speaker_attributes: [],
      frames: {enabled: false, start: '0', end: '20', interval: '1', max_frames: '24', max_dimension: '1280'},
      message: '必要な情報を選び、ZIPをダウンロードしてください。'};
  }
  const selection = aiDataExportSelection;
  const panel = document.querySelector('#ai-data-export-template').content.firstElementChild.cloneNode(true);
  // Native Tab scrolling can leave this inline panel's focus behind the sticky save bar.
  panel.addEventListener('focusin', event => {
    const control = event.target;
    requestAnimationFrame(() => {
      if (!control.isConnected || document.activeElement !== control || !document.elementFromPoint) return;
      const rect = control.getBoundingClientRect();
      const visible = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
      if (!control.contains(visible)) control.scrollIntoView({block: 'center', behavior: 'instant'});
    });
  });
  panel.querySelectorAll('input').forEach(input => {
    input.addEventListener('input', () => {
      if (aiDataExportOwner || selection !== aiDataExportSelection) return;
      if (input.matches('[data-ai-export-names]')) selection.include_names = input.checked;
      else if (input.matches('[data-ai-export-frames]')) selection.frames.enabled = input.checked;
      else if (input.dataset.aiExportAttribute) {
        selection.speaker_attributes = aiDataExportAttributes.filter(key => key === input.dataset.aiExportAttribute
          ? input.checked : selection.speaker_attributes.includes(key));
      } else selection.frames[input.dataset.aiExportFrame] = input.value;
      syncAiDataExportControls();
    });
  });
  panel.querySelector('[data-ai-export-download]').addEventListener('click', () => downloadAiDataExport(panel, selection, prepared));
  panel.querySelector('[data-ai-export-cancel]').addEventListener('click', () => {
    cancelAiDataExport();
    panel.querySelector('[data-ai-export-download]').focus();
  });
  return panel;
}


window.renderAiDataExport = renderAiDataExport;
window.syncAiDataExportControls = syncAiDataExportControls;
window.cancelAiDataExport = cancelAiDataExport;
})();
