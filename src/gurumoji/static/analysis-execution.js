/* Durable M0-M7 analysis execution UI.  The server owns plans, ordering,
   attempts, cancellation and recovery; this file only edits plans and renders
   versioned state returned by the analysis core. */
const analysisExecutionStorageKey = 'gurumoji.analysisExecution.v2';
const analysisExecutionStageDefinitions = Array.from({length: 8}, (_, index) => ({
  id: `M${index}`,
  label: `M${index}`,
  title: [
    '入力・計画枠', 'アウトライン範囲', '一次分析', '図表仕様',
    '実行定義の確定', '本分析', '比較範囲', '成果物・公開'
  ][index]
}));

const analysisExecutionState = {
  id: '', itemId: '', itemName: '', mode: 'automatic', status: 'idle', active: false,
  currentIndex: -1, stages: [], settings: {}, logs: [], startedAt: 0,
  cancelRequested: false, generation: 0, restored: false, resuming: false,
  definitionRevision: 0, pollTimer: null
};

const analysisRunDialog = document.querySelector('#analysis-run-dialog');
const analysisRunForm = document.querySelector('#analysis-run-form');
const analysisRunButton = document.querySelector('#analysis-run-button');
const analysisRunSettingsButton = document.querySelector('#analysis-run-settings-button');
const analysisRunStartButton = document.querySelector('#analysis-run-start');
const analysisRunDialogMessage = document.querySelector('#analysis-run-dialog-message');
const analysisExecutionView = document.querySelector('#analysis-execution-view');
const analysisExecutionChip = document.querySelector('#analysis-job-chip');
const analysisExecutionChipLabel = document.querySelector('#analysis-job-chip-label');
let analysisExecutionElapsedTimer = null;

function analysisExecutionSetDialogMessage(message = '', error = false) {
  setAlert(analysisRunDialogMessage, message, error);
}

function analysisExecutionMode() {
  return document.querySelector('input[name="analysis_run_mode"]:checked')?.value || 'automatic';
}

function analysisExecutionDefinitionFromForm(status = 'draft') {
  const source = document.querySelector('#analysis-definition-source')?.value || 'text';
  const rule = document.querySelector('#analysis-definition-rule')?.value || 'text_length';
  return {
    definition_id: document.querySelector('#analysis-definition-id')?.value.trim() || '',
    name: document.querySelector('#analysis-definition-name')?.value.trim() || '',
    description: document.querySelector('#analysis-definition-description')?.value.trim() || '',
    unit_of_analysis: 'segment', source_columns: [source],
    output_column: document.querySelector('#analysis-definition-output')?.value.trim() || '',
    data_type: document.querySelector('#analysis-definition-type')?.value || (rule === 'identity' ? 'category' : 'number'),
    measurement_level: document.querySelector('#analysis-definition-level')?.value || (rule === 'identity' ? 'nominal' : 'ratio'),
    measurement_rule: rule,
    method: document.querySelector('#analysis-definition-method')?.value || 'descriptive',
    status
  };
}

function analysisExecutionSyncManualFields() {
  const manual = analysisExecutionMode() === 'manual';
  const editor = document.querySelector('#analysis-manual-definition');
  const option = document.querySelector('[data-analysis-run-option="manual_measurement"] input');
  if (editor) editor.hidden = !manual;
  if (option) {
    option.checked = manual;
    option.disabled = !manual;
  }
  const preset = document.querySelector('#analysis-run-preset-field');
  if (preset) preset.hidden = manual;
}

function analysisExecutionValidatePlan() {
  if (!analysisState.itemId || !analysisState.data) return '先に分析対象を読み込んでください。';
  if (hasUnsavedAnalysisChanges()) return '未保存の分析設定・手動コード・準備記録があります。保存してから実行してください。';
  if (analysisExecutionMode() !== 'manual') return '';
  const value = analysisExecutionDefinitionFromForm();
  if (!value.name) return '手動実行ではラベル名を入力してください。';
  if (!/^[A-Za-z][A-Za-z0-9_-]{2,63}$/.test(value.definition_id)) return '定義IDは英字で始まる3〜64文字の英数字・_・-です。';
  if (!value.description) return '測定方法を入力してください。';
  if (!/^[A-Za-z][A-Za-z0-9_]{1,62}$/.test(value.output_column)) return '生成する列は英字で始まる英数字・_です。';
  if (value.method === 'descriptive' && !['interval', 'ratio'].includes(value.measurement_level)) {
    return '名義・順序尺度には度数集計を選んでください。平均へ自動置換しません。';
  }
  return '';
}

function analysisExecutionUpdatePlanSummary() {
  analysisExecutionSyncManualFields();
  const manual = analysisExecutionMode() === 'manual';
  const summary = document.querySelector('#analysis-run-plan-summary');
  if (summary) {
    summary.replaceChildren();
    const strong = document.createElement('strong');
    strong.textContent = 'M0〜M7の固定計画：';
    summary.append(strong, document.createTextNode(
      manual
        ? '手入力定義を少数試行 → 採用版をM4で固定 → 既存2手法と全件測定 ／ 外部送信なし'
        : '既存の発話量・会話時間構造をM2で並列実行 ／ 外部送信なし'
    ));
  }
  const error = analysisExecutionValidatePlan();
  analysisExecutionSetDialogMessage(error, Boolean(error));
  if (analysisRunStartButton) analysisRunStartButton.disabled = Boolean(error);
}

function openAnalysisExecutionDialog(options = {}) {
  if (!analysisRunDialog || typeof analysisRunDialog.showModal !== 'function') return;
  if (analysisExecutionState.active) {
    showAnalysisExecutionView();
    return;
  }
  const requestedMode = options.mode === 'manual' ? 'manual' : 'automatic';
  const mode = document.querySelector(`input[name="analysis_run_mode"][value="${requestedMode}"]`);
  if (mode) mode.checked = true;
  const details = document.querySelector('#analysis-run-details');
  if (details) details.open = Boolean(options.showDetails || requestedMode === 'manual');
  analysisExecutionUpdatePlanSummary();
  if (!analysisRunDialog.open) analysisRunDialog.showModal();
  window.requestAnimationFrame(() => document.querySelector('input[name="analysis_run_mode"]:checked')?.focus());
}

function analysisExecutionPersist() {
  const value = {
    id: analysisExecutionState.id, itemId: analysisExecutionState.itemId,
    itemName: analysisExecutionState.itemName, mode: analysisExecutionState.mode,
    startedAt: analysisExecutionState.startedAt
  };
  try { sessionStorage.setItem(analysisExecutionStorageKey, JSON.stringify(value)); } catch (_) { /* memory only */ }
}

function analysisExecutionRestore() {
  let stored = null;
  try { stored = JSON.parse(sessionStorage.getItem(analysisExecutionStorageKey) || 'null'); } catch (_) { /* unavailable */ }
  if (!stored?.id || !stored?.itemId) return false;
  Object.assign(analysisExecutionState, stored, {status: 'accepted', active: true, restored: true});
  return true;
}

function analysisExecutionClearPersisted() {
  try { sessionStorage.removeItem(analysisExecutionStorageKey); } catch (_) { /* unavailable */ }
}

function analysisExecutionLogFromEvents(events) {
  const labels = {
    pipeline_accepted: '実行計画を受け付けました。', pipeline_running: '固定計画の実行を開始しました。',
    milestone_started: '段階を開始', milestone_committed: '段階を確定',
    milestone_waiting: '段階を停止', cancel_requested: '取消を要求しました。',
    pipeline_cancelled: '分析を中止しました。', retry_accepted: '失敗した処理の再試行を受け付けました。',
    pipeline_completed: '全成果物と公開状態を確定しました。', pipeline_failed: 'pipelineが停止しました。'
  };
  return (events || []).map(event => {
    const time = new Date(event.created_at).toLocaleTimeString('ja-JP', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
    const milestone = event.payload?.milestone ? ` ${event.payload.milestone}` : '';
    return `${time}  ${labels[event.type] || event.type}${milestone}`;
  });
}

function analysisExecutionApplyResponse(response) {
  analysisExecutionState.status = response.status;
  analysisExecutionState.active = ['accepted', 'running', 'waiting', 'cancelling'].includes(response.status)
    && response.allowed_actions?.includes('cancel');
  analysisExecutionState.currentIndex = Math.max(0, analysisExecutionStageDefinitions.findIndex(
    value => value.id === response.current_milestone
  ));
  analysisExecutionState.stages = (response.milestones || []).map(value => ({
    id: value.id,
    label: value.id,
    title: analysisExecutionStageDefinitions.find(stage => stage.id === value.id)?.title || value.id,
    status: value.status,
    steps: value.steps || []
  }));
  analysisExecutionState.settings = {
    ...(analysisExecutionState.settings || {}), progress: response.progress,
    publications: response.publications || [], allowedActions: response.allowed_actions || [],
    error: response.error || '', waitReason: response.wait_reason || '', resultRun: response.result_run
  };
  analysisExecutionState.logs = analysisExecutionLogFromEvents(response.events);
  analysisExecutionState.cancelRequested = response.status === 'cancelling';
  if (response.status === 'completed' && typeof loadAnalysisItem === 'function' && analysisExecutionState.itemId) {
    loadAnalysisItem(analysisExecutionState.itemId, {execute: true});
  }
  if (['completed', 'cancelled', 'failed'].includes(response.status)) analysisExecutionClearPersisted();
  else analysisExecutionPersist();
  renderAnalysisExecution();
}

function analysisExecutionStatusLabel(status) {
  return {
    pending: '待機', active: '実行中', waiting: '入力・回復待ち', committed: '完了',
    failed: '失敗', cancelled: '取消', not_applicable: '対象外'
  }[status] || status;
}

function analysisExecutionPercent() {
  if (Number.isFinite(analysisExecutionState.settings?.progress)) return analysisExecutionState.settings.progress;
  if (!analysisExecutionState.stages.length) return 0;
  return Math.round(100 * analysisExecutionState.stages.filter(value => value.status === 'committed').length
    / analysisExecutionState.stages.length);
}

function analysisExecutionElapsedText() {
  const seconds = Math.max(0, Math.floor((Date.now() - Number(analysisExecutionState.startedAt || Date.now())) / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

function renderAnalysisExecution() {
  if (analysisExecutionView && !analysisExecutionView.hidden) analysisExecutionSetWorkspaceVisibility(true);
  const stagesHost = document.querySelector('#analysis-execution-stages');
  if (stagesHost) {
    stagesHost.replaceChildren();
    analysisExecutionState.stages.forEach(stage => {
      const item = document.createElement('li');
      const css = stage.status === 'committed' ? 'completed'
        : stage.status === 'active' ? 'running'
          : stage.status === 'pending' ? 'skipped' : stage.status;
      item.className = `analysis-execution-stage ${css}`;
      item.dataset.executionStage = stage.id;
      const strong = document.createElement('strong'); strong.textContent = `${stage.id} ${stage.title}`;
      const small = document.createElement('small'); small.textContent = analysisExecutionStatusLabel(stage.status);
      item.append(strong, small); stagesHost.append(item);
    });
  }
  const percent = analysisExecutionPercent();
  const percentText = document.querySelector('#analysis-execution-percent');
  const track = document.querySelector('#analysis-execution-track');
  if (percentText) percentText.textContent = `${percent}%`;
  if (track) {
    track.setAttribute('aria-valuenow', String(percent));
    const bar = track.querySelector('i'); if (bar) bar.style.width = `${percent}%`;
  }
  const current = analysisExecutionState.stages[analysisExecutionState.currentIndex]
    || analysisExecutionState.stages.find(value => ['failed', 'waiting', 'cancelled'].includes(value.status))
    || analysisExecutionState.stages.at(-1);
  const stateLabel = document.querySelector('#analysis-execution-state-label');
  const title = document.querySelector('#analysis-execution-current-title');
  const message = document.querySelector('#analysis-execution-message');
  if (stateLabel) stateLabel.textContent = current ? `${current.id} ${analysisExecutionStatusLabel(current.status)}` : '開始準備';
  if (title) title.textContent = current?.title || '入力と設定を確認しています';
  if (message) {
    const failed = current?.steps?.find(value => value.error);
    const publications = analysisExecutionState.settings?.publications || [];
    const publicationFailure = publications.find(value => !['published', 'not_selected', 'pending'].includes(value.status));
    message.textContent = failed?.error || publicationFailure?.error || analysisExecutionState.settings?.error
      || (analysisExecutionState.status === 'completed' ? '選択した成果物の保存と公開を確定しました。' : '固定した計画と親成果の確定順に処理しています。');
  }
  const heading = document.querySelector('#analysis-execution-title');
  if (heading) heading.textContent = analysisExecutionState.status === 'completed' ? '分析が完了しました'
    : analysisExecutionState.status === 'waiting' ? '分析を再開できます'
      : analysisExecutionState.status === 'cancelled' ? '分析を中止しました' : '分析を実行しています';
  const summary = document.querySelector('#analysis-execution-summary');
  if (summary) summary.textContent = 'M0〜M7をサーバー側の永続ゲートで管理します。完了済み成果物は再試行時も保持されます。';
  const elapsed = document.querySelector('#analysis-execution-elapsed');
  const mode = document.querySelector('#analysis-execution-mode');
  const external = document.querySelector('#analysis-execution-external');
  if (elapsed) elapsed.textContent = analysisExecutionElapsedText();
  if (mode) mode.textContent = analysisExecutionState.mode === 'manual' ? '手入力定義' : '自動計画';
  if (external) external.textContent = 'なし（local_only）';
  const log = document.querySelector('#analysis-execution-log');
  if (log) log.textContent = analysisExecutionState.logs.join('\n');
  const orbit = document.querySelector('#analysis-execution-orbit');
  if (orbit) orbit.classList.toggle('is-idle', !analysisExecutionState.active);
  const cancel = document.querySelector('#analysis-execution-cancel');
  const results = document.querySelector('#analysis-execution-results');
  const review = document.querySelector('#analysis-execution-review');
  if (cancel) {
    cancel.hidden = !analysisExecutionState.active;
    cancel.disabled = analysisExecutionState.cancelRequested;
    cancel.textContent = analysisExecutionState.cancelRequested ? '中止を待っています…' : '分析を中止';
  }
  if (results) results.hidden = analysisExecutionState.status !== 'completed';
  if (review) {
    review.hidden = !['waiting', 'failed'].includes(analysisExecutionState.status);
    review.textContent = analysisExecutionState.settings?.allowedActions?.includes('retry_publication')
      ? '公開だけ再試行' : '失敗した処理を再試行';
  }
  if (analysisRunButton) analysisRunButton.textContent = analysisExecutionState.active ? '実行状況を見る' : '分析を実行';
  if (analysisExecutionChip) {
    analysisExecutionChip.hidden = analysisExecutionState.status === 'idle';
    analysisExecutionChip.classList.toggle('is-active', analysisExecutionState.active);
    analysisExecutionChip.classList.toggle('is-complete', analysisExecutionState.status === 'completed');
    analysisExecutionChip.classList.toggle('has-error', ['waiting', 'failed'].includes(analysisExecutionState.status));
  }
  if (analysisExecutionChipLabel) analysisExecutionChipLabel.textContent = analysisExecutionState.active
    ? `${current?.id || 'M0'} 実行中` : analysisExecutionState.status === 'completed' ? '分析完了' : '分析を確認';
}

function analysisExecutionSetWorkspaceVisibility(showExecution) {
  if (analysisExecutionView) analysisExecutionView.hidden = !showExecution;
  const shell = document.querySelector('#analysis-shell');
  const empty = document.querySelector('#analysis-empty');
  const loading = document.querySelector('#analysis-loading');
  const comparison = document.querySelector('#interview-comparison-details');
  if (showExecution) {
    if (shell) shell.hidden = true;
    if (empty) empty.hidden = true;
    if (loading) loading.hidden = true;
    if (comparison) comparison.hidden = true;
  } else {
    if (shell) shell.hidden = !analysisState.data;
    if (empty) empty.hidden = Boolean(analysisState.data);
    if (loading) loading.hidden = true;
    if (comparison) comparison.hidden = false;
  }
}

function showAnalysisExecutionView({updateRoute = true} = {}) {
  if (!analysisExecutionState.itemId) return;
  if (analysisState.itemId !== analysisExecutionState.itemId || analysisCard?.hidden) {
    showView('analysis', {analysisItemId: analysisExecutionState.itemId});
  }
  analysisExecutionSetWorkspaceVisibility(true);
  renderAnalysisExecution();
  if (updateRoute) syncRouteHash(`${routeHash('analysis', analysisExecutionState.itemId)}/run`);
  if (analysisExecutionState.id && ['accepted', 'running', 'waiting', 'cancelling'].includes(analysisExecutionState.status)) {
    analysisExecutionPoll();
  }
}

function hideAnalysisExecutionView({updateRoute = true} = {}) {
  analysisExecutionSetWorkspaceVisibility(false);
  if (analysisState.data) renderAnalysisWorkspace();
  if (updateRoute && analysisExecutionState.itemId) syncRouteHash(routeHash('analysis', analysisExecutionState.itemId));
}

async function analysisExecutionRequestJson(input, options = {}) {
  const response = await apiFetch(input, options);
  const data = await readJsonResponse(response);
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

async function analysisExecutionPoll() {
  if (!analysisExecutionState.id || analysisExecutionState.resuming) return;
  analysisExecutionState.resuming = true;
  try {
    const data = await analysisExecutionRequestJson(`/api/library/${encodeURIComponent(analysisExecutionState.itemId)}/analysis/pipelines/${encodeURIComponent(analysisExecutionState.id)}`);
    analysisExecutionApplyResponse(data);
  } catch (error) {
    analysisExecutionState.logs.push(`状態取得失敗：${error.message}`);
    renderAnalysisExecution();
  } finally {
    analysisExecutionState.resuming = false;
  }
  if (['accepted', 'running', 'cancelling'].includes(analysisExecutionState.status)) {
    window.clearTimeout(analysisExecutionState.pollTimer);
    analysisExecutionState.pollTimer = window.setTimeout(analysisExecutionPoll, 350);
  }
}

async function analysisExecutionPrepareDefinition() {
  if (analysisExecutionMode() !== 'manual') return [];
  const draft = analysisExecutionDefinitionFromForm('draft');
  if (analysisExecutionState.definitionRevision) draft.expected_revision = analysisExecutionState.definitionRevision;
  const base = `/api/library/${encodeURIComponent(analysisState.itemId)}/analysis/definitions/${encodeURIComponent(draft.definition_id)}`;
  const jsonHeaders = {'Content-Type': 'application/json'};
  const saved = await analysisExecutionRequestJson(base, {method: 'PUT', headers: jsonHeaders, body: JSON.stringify(draft)});
  analysisExecutionState.definitionRevision = saved.definition.revision;
  const trial = await analysisExecutionRequestJson(`${base}/trials`, {method: 'POST', headers: jsonHeaders, body: JSON.stringify({limit: 20})});
  const trialHost = document.querySelector('#analysis-definition-trial-result');
  if (trialHost) trialHost.textContent = `試行 ${trial.trial.sample_size}件：有効${trial.trial.valid_count}件・欠測${trial.trial.missing_count}件。外部送信なし。`;
  const adopted = await analysisExecutionRequestJson(base, {method: 'PUT', headers: jsonHeaders, body: JSON.stringify({
    ...draft, status: 'adopted', expected_revision: analysisExecutionState.definitionRevision
  })});
  analysisExecutionState.definitionRevision = adopted.definition.revision;
  return [draft.definition_id];
}

async function startAnalysisExecution(event) {
  event?.preventDefault();
  analysisExecutionUpdatePlanSummary();
  const validation = analysisExecutionValidatePlan();
  if (validation) return;
  if (analysisRunStartButton) analysisRunStartButton.disabled = true;
  analysisExecutionSetDialogMessage('固定計画と少数試行を確認しています。');
  try {
    const definitionIds = await analysisExecutionPrepareDefinition();
    const item = analysisState.data.item;
    const publish = Boolean(document.querySelector('#analysis-run-publish')?.checked);
    const payload = {
      request_id: typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : createSubmissionId(),
      source_revision: item.revision_count, analysis_revision: item.analysis_revision,
      mode: analysisExecutionMode(), definition_ids: definitionIds,
      provider_policy: 'local_only',
      publication_targets: publish ? ['input', 'orchestrator', 'visualization'] : [],
      research_protocol: {classification: 'exploratory', data_viewed: true}
    };
    await analysisExecutionRequestJson(`/api/library/${encodeURIComponent(analysisState.itemId)}/analysis/plans/preview`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    });
    const response = await analysisExecutionRequestJson(`/api/library/${encodeURIComponent(analysisState.itemId)}/analysis/pipelines`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    });
    const selected = analysisCatalog.find(value => value.id === analysisState.itemId);
    Object.assign(analysisExecutionState, {
      id: response.pipeline_id, itemId: analysisState.itemId,
      itemName: selected?.source_name || item.source_name || '分析対象',
      mode: payload.mode, startedAt: Date.now(), restored: false
    });
    analysisExecutionApplyResponse(response);
    if (analysisRunDialog?.open) analysisRunDialog.close();
    showAnalysisExecutionView();
  } catch (error) {
    analysisExecutionSetDialogMessage(error.message || '分析計画を開始できませんでした。', true);
  } finally {
    if (analysisRunStartButton) analysisRunStartButton.disabled = Boolean(analysisExecutionValidatePlan());
  }
}

async function cancelAnalysisExecution() {
  if (!analysisExecutionState.active || analysisExecutionState.cancelRequested) return;
  if (!window.confirm('現在の分析を中止しますか？ 完了済みの結果は保持されます。')) return;
  analysisExecutionState.cancelRequested = true;
  renderAnalysisExecution();
  try {
    const response = await analysisExecutionRequestJson(`/api/library/${encodeURIComponent(analysisExecutionState.itemId)}/analysis/pipelines/${encodeURIComponent(analysisExecutionState.id)}/cancel`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'
    });
    analysisExecutionApplyResponse(response);
    analysisExecutionPoll();
  } catch (error) {
    analysisExecutionState.cancelRequested = false;
    analysisExecutionState.logs.push(`中止要求失敗：${error.message}`);
    renderAnalysisExecution();
  }
}

async function analysisExecutionReviewPlan() {
  const retry = analysisExecutionState.settings?.allowedActions?.some(value => value.startsWith('retry'));
  if (!retry) {
    hideAnalysisExecutionView();
    openAnalysisExecutionDialog({mode: analysisExecutionState.mode, showDetails: true});
    return;
  }
  try {
    const response = await analysisExecutionRequestJson(`/api/library/${encodeURIComponent(analysisExecutionState.itemId)}/analysis/pipelines/${encodeURIComponent(analysisExecutionState.id)}/retry`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'
    });
    analysisExecutionApplyResponse(response);
    analysisExecutionPoll();
  } catch (error) {
    analysisExecutionState.logs.push(`再試行失敗：${error.message}`);
    renderAnalysisExecution();
  }
}

function analysisExecutionBind() {
  listen(analysisRunButton, 'click', () => analysisExecutionState.active ? showAnalysisExecutionView() : openAnalysisExecutionDialog());
  listen(analysisRunSettingsButton, 'click', () => openAnalysisExecutionDialog({mode: 'manual', showDetails: true}));
  listen(document.querySelector('#analysis-run-close'), 'click', () => analysisRunDialog?.close());
  listen(analysisRunForm, 'submit', startAnalysisExecution);
  document.querySelectorAll('input[name="analysis_run_mode"], #analysis-manual-definition input, #analysis-manual-definition select, #analysis-run-publish')
    .forEach(control => listen(control, 'input', analysisExecutionUpdatePlanSummary));
  listen(document.querySelector('#analysis-execution-background'), 'click', () => hideAnalysisExecutionView());
  listen(document.querySelector('#analysis-execution-results'), 'click', async () => {
    if (typeof loadAnalysisStorage === 'function') await loadAnalysisStorage();
    if (typeof loadAnalysisItem === 'function' && analysisExecutionState.itemId) {
      await loadAnalysisItem(analysisExecutionState.itemId, {execute: true});
    }
    hideAnalysisExecutionView();
  });
  listen(document.querySelector('#analysis-execution-review'), 'click', analysisExecutionReviewPlan);
  listen(document.querySelector('#analysis-execution-cancel'), 'click', cancelAnalysisExecution);
  listen(analysisExecutionChip, 'click', showAnalysisExecutionView);
  window.addEventListener('popstate', () => window.setTimeout(() => {
    const wantsRun = /#\/analysis\/[^/]+\/run$/.test(window.location.hash);
    if (wantsRun && analysisExecutionState.itemId) showAnalysisExecutionView({updateRoute: false});
    else if (analysisExecutionView && !analysisExecutionView.hidden) hideAnalysisExecutionView({updateRoute: false});
  }, 0));
}

window.addEventListener('DOMContentLoaded', () => {
  analysisExecutionBind();
  analysisExecutionRestore();
  renderAnalysisExecution();
  if (analysisExecutionElapsedTimer !== null) window.clearInterval(analysisExecutionElapsedTimer);
  analysisExecutionElapsedTimer = window.setInterval(() => {
    if (analysisExecutionState.status !== 'idle') renderAnalysisExecution();
  }, 1000);
  if (analysisExecutionState.restored) analysisExecutionPoll();
  if (/#\/analysis\/[^/]+\/run$/.test(window.location.hash) && analysisExecutionState.itemId) {
    showAnalysisExecutionView({updateRoute: false});
  }
});
