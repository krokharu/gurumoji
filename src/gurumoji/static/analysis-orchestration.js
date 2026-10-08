/* Read-only visualization of durable Core/Handler snapshots. Rendering,
 * animation, reopening and polling never call an AI or start/resume a run. */
const orchestrationRoles = [
  {id: 'core', label: 'Core', subtitle: '問い・統合・終了判断', kind: 'ai'},
  {id: 'handler', label: 'Handler', subtitle: '発注・台帳・保存・停止', kind: 'code'},
  {id: 'interpretation', label: '会話解釈', subtitle: 'テーマ・展開・別解', kind: 'ai'},
  {id: 'statistics', label: '数量・統計', subtitle: 'Python集計', kind: 'code'},
  {id: 'verification', label: '独立検証', subtitle: '原文・数値・根拠', kind: 'ai'},
  {id: 'critic', label: '批判者', subtitle: '反証・代替説明', kind: 'ai'},
  {id: 'obsidian_manager', label: 'Obsidian管理', subtitle: 'Core判断・Handler記録・データ参照', kind: 'code'}
];
const orchestrationState = {itemId: '', itemName: '', runId: '', run: null, epoch: 0, poll: null, timer: null,
  operation: '', submission: null, setup: null, setupEpoch: 0, viewerEpoch: 0, fetchedAt: null, error: '', lastSeq: null, resultRequest: 0, taskFingerprint: '', recoveryFingerprint: '', initialFingerprint: '', outputFingerprint: ''};
const orchestrationStorageKey = 'gurumoji.orchestration.v1';
const orchestrationNode = id => document.getElementById(`orchestration-${id}`);
const orchestrationActiveStatuses = ['accepted', 'queued', 'running', 'cancelling', 'stopping'];
const orchestrationPublicationTargets = ['input', 'orchestrator', 'visualization'];
const orchestrationVaultWriters = [['input','Input'], ['orchestrator','Orchestrator'], ['visualization','Visualization'], ['research','Research']];
function orchestrationPendingCompletion(run) {
  const stages=Array.isArray(run?.initial_stages) ? run.initial_stages : run?.initial?.stages || [];
  return Boolean(run?.tasks?.some(task=>['running','cancel_requested'].includes(task.status)) || stages.some(stage=>stage.status==='running'));
}
function isAnalysisOrchestrationActive() { return Boolean(orchestrationState.submission || orchestrationActiveStatuses.includes(orchestrationState.run?.status) || orchestrationPendingCompletion(orchestrationState.run)); }
function orchestrationLabel(status) {
  return {accepted:'受付済み', queued:'待機', idle:'待機', pending:'待機', running:'実行中', succeeded:'処理成功', completed:'処理終了',
    cancelling:'停止・完了待ち', stopping:'停止・完了待ち', cancelled:'利用者停止', stopped:'停止', interrupted:'中断・復旧待ち',
    cancel_requested:'停止要求済み', uncertain:'実行結果不明', quarantined:'結果を隔離', paused:'一時停止', recovery_required:'中断・手動復旧待ち', failed:'失敗', blocked:'実行不可', waiting:'確認待ち', skipped:'未実施', validated:'形式確認済み',
    linked:'参照を保存済み',disabled:'無効',unavailable:'利用不可',missing:'削除済み',edited:'編集を検出',conflict:'競合'}[status] || status || '状態未取得';
}
function orchestrationText(id, value) { const node = orchestrationNode(id); if (node && node.textContent !== value) node.textContent = value; }
function orchestrationElement(tag, text, className) { const element = document.createElement(tag); if (text !== undefined) element.textContent = text; if (className) element.className = className; return element; }
function orchestrationNumber(value) { return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('ja-JP') : '未計測'; }
function orchestrationBase(itemId = orchestrationState.itemId, runId = orchestrationState.runId) { return `/api/library/${encodeURIComponent(itemId)}/analysis/orchestration${runId ? `/${encodeURIComponent(runId)}` : ''}`; }
function orchestrationPersist() {
  // Only opaque identifiers are retained in browser storage; never source text/results.
  try { sessionStorage.setItem(orchestrationStorageKey, JSON.stringify({itemId:orchestrationState.itemId, runId:orchestrationState.runId})); } catch (_) { /* unavailable */ }
}
function closeAnalysisOrchestrationDialogs() {
  const closedHistory = typeof closeAnalysisHistoryViewer === 'function' && closeAnalysisHistoryViewer();
  const closed = closedHistory || ['settings', 'live'].some(name => orchestrationNode(name)?.open);
  ++orchestrationState.setupEpoch; ++orchestrationState.viewerEpoch;
  for (const name of ['settings', 'live']) if (orchestrationNode(name)?.open) orchestrationNode(name).close();
  return closed;
}
function orchestrationFormMode() { return document.querySelector('input[name="orchestration_stop"]:checked')?.value || 'auto'; }
function orchestrationRoleOverrides() {
  return Object.fromEntries(orchestrationRoles.filter(role => role.kind === 'ai').flatMap(role => {
    const provider = orchestrationNode(`provider-${role.id}`)?.value;
    const model = orchestrationNode(`model-${role.id}`)?.value.trim();
    const common = orchestrationNode('provider').value;
    return provider || model ? [[role.id, {provider: provider || common, model: model || (provider && provider !== common ? '' : orchestrationNode('model').value.trim())}]] : [];
  }));
}
function orchestrationCloudProviders() {
  const common = orchestrationNode('provider').value;
  const overrides = orchestrationRoleOverrides();
  return [...new Set(orchestrationRoles.filter(role => role.kind === 'ai').map(role => overrides[role.id]?.provider || common).filter(p => ['openai', 'google'].includes(p)))];
}
function orchestrationSyncForm() {
  const mode = orchestrationFormMode();
  orchestrationNode('time-field').hidden = !['time', 'auto'].includes(mode);
  orchestrationNode('iterations-field').hidden = !['iterations', 'auto'].includes(mode);
  orchestrationNode('importance-field').hidden = !['importance', 'auto'].includes(mode);
  orchestrationNode('time').required = mode === 'time';
  orchestrationNode('iterations').required = mode === 'iterations';
  orchestrationText('stop-explanation', {
    time:'開始からの経過時間で新規発注を止めます。進行中の呼出しを必ず期限内に終える保証ではありません。',
    iterations:'Coreの結果統合から次の実行案選択までを1巡と数えます。並列タスク数や再試行回数とは別です。',
    importance:'問いへの影響を高・中・低で暫定評価します。頻度・モデルの自信とは異なり、基準は未校正です。',
    auto:'Coreが最低3回、根拠・批判・未解決点を検討し、その後は継続・終了を判断します。時間・回数は空欄で無上限にできます。手動停止・安全上限・実行障害は最低回数より優先します。'
  }[mode]);
  for (const role of orchestrationRoles.filter(role => role.kind === 'ai')) {
    const provider = orchestrationNode(`provider-${role.id}`)?.value;
    const input = orchestrationNode(`model-${role.id}`);
    if (input) input.placeholder = provider && provider !== orchestrationNode('provider').value ? '空欄なら実行先の設定済みモデル' : '空欄なら共通設定';
  }
  const cloud = orchestrationCloudProviders();
  orchestrationNode('cloud-disclosure').hidden = cloud.length === 0;
  orchestrationText('cloud-targets', `送信先: ${cloud.map(p => p === 'openai' ? 'OpenAI' : 'Google Gemini').join('、')}。原文や途中結果を含む固定した分析入力を送信します。`);
}
function orchestrationSetupCurrent(epoch = orchestrationState.setupEpoch) {
  return epoch === orchestrationState.setupEpoch && orchestrationNode('settings').open && orchestrationState.setup && isAnalysisContextCurrent(orchestrationState.setup);
}
function openAnalysisOrchestrationSettings() {
  if (isAnalysisOrchestrationActive() && orchestrationState.runId) { showAnalysisOrchestration(); return; }
  closeAnalysisExecutionDialog();
  const nextContext = captureAnalysisContext();
  const same = orchestrationState.setup && isAnalysisContextCurrent(orchestrationState.setup);
  orchestrationState.setup = nextContext; ++orchestrationState.setupEpoch;
  // Consent belongs to a new submission, never to a past run or a later opening.
  // An uncertain submission retains the exact choice needed for an idempotent retry.
  orchestrationNode('publication-all').checked = Boolean(orchestrationState.submission?.itemId === nextContext.itemId && orchestrationState.submission.payload.publication_targets?.length);
  orchestrationNode('memory-enabled').checked = orchestrationState.submission?.itemId === nextContext.itemId ? orchestrationState.submission.payload.obsidian_management !== false : true;
  if (!same) {
    orchestrationNode('question').value = String(analysisState.config?.research_question || '').slice(0, 2000);
    orchestrationNode('cloud-consent').checked = false;
    orchestrationNode('history-list').replaceChildren();
  }
  orchestrationText('settings-target', `${nextContext.data?.item?.source_name || '分析対象を選択してください'} · 入力版 ${nextContext.sourceRevision ?? '不明'} / 分析版 ${nextContext.analysisRevision ?? '不明'}`);
  const blocked = !nextContext.itemId || !nextContext.data ? '先に分析対象を読み込んでください。' : hasUnsavedAnalysisChanges() ? '未保存の変更があります。分析設定を保存してから開始してください。' : analysisExecutionState.active ? '基礎分析を実行中です。終了してから自律分析を開始してください。' : '';
  setAlert(orchestrationNode('settings-message'), blocked, Boolean(blocked));
  orchestrationNode('start').disabled = Boolean(blocked || orchestrationState.operation === 'start');
  orchestrationSyncForm();
  orchestrationNode('settings').showModal();
}
function orchestrationPayload() {
  if (!orchestrationSetupCurrent() || !orchestrationState.setup.itemId) throw Error('分析対象が変わりました。設定を開き直してください。');
  if (hasUnsavedAnalysisChanges()) throw Error('未保存の変更を保存してから開始してください。');
  if (analysisExecutionState.active) throw Error('基礎分析の終了を待ってください。');
  const mode = orchestrationFormMode(), question = orchestrationNode('question').value.trim();
  if (!question) throw Error('明らかにしたいことを入力してください。');
  const integer = (id, required, max) => {
    const raw = orchestrationNode(id).value.trim();
    if (!raw && !required) return null;
    const number = Number(raw);
    if (!Number.isInteger(number) || number < 1 || number > max) throw Error(`${orchestrationNode(id).closest('label').querySelector('span').textContent}を1〜${max}の整数で指定してください。`);
    if (id === 'iterations' && mode === 'auto' && number < 3) throw Error('AIお任せの回数上限は最低3回以上にしてください。');
    return number;
  };
  const cloud = orchestrationCloudProviders();
  if (cloud.length && !orchestrationNode('cloud-consent').checked) throw Error('クラウドへの会話原文・途中結果の送信に同意するか、全担当をローカルに戻してください。');
  return {source_revision:orchestrationState.setup.sourceRevision, analysis_revision:orchestrationState.setup.analysisRevision,
    question, provider:orchestrationNode('provider').value, model:orchestrationNode('model').value.trim(), provider_policy:cloud.length ? 'cloud_allowed' : 'local_only', cloud_consent:cloud.length > 0 && orchestrationNode('cloud-consent').checked,
    stop_mode:mode, time_limit_seconds:['time','auto'].includes(mode) ? (integer('time', mode === 'time', 1440) ?? 0) * 60 || null : null,
    max_iterations:['iterations','auto'].includes(mode) ? integer('iterations', mode === 'iterations', 1000) : null,
    importance_threshold:orchestrationNode('importance').value, max_calls:integer('max-calls',true,1000), max_tasks:integer('max-tasks',true,2000),
    concurrency:integer('concurrency',true,4), research_mode:'exploratory', roles:orchestrationRoleOverrides(),
    publication_targets:orchestrationNode('publication-all').checked ? [...orchestrationPublicationTargets] : [],
    obsidian_management:orchestrationNode('memory-enabled').checked};
}
async function startAnalysisOrchestration(event) {
  event?.preventDefault();
  if (orchestrationState.operation) return;
  let payload;
  try { payload = orchestrationPayload(); } catch (error) { setAlert(orchestrationNode('settings-message'), error.message, true); return; }
  const context = orchestrationState.setup, setupEpoch = orchestrationState.setupEpoch;
  const fingerprint = JSON.stringify(payload);
  // An ambiguous transport failure must not silently become a second request.
  if (orchestrationState.submission && (orchestrationState.submission.itemId !== context.itemId || orchestrationState.submission.fingerprint !== fingerprint)) {
    setAlert(orchestrationNode('settings-message'), '前の開始要求の受付状態が不明です。設定を変更して再送せず、「保存済み実行」で確認してください。', true); return;
  }
  const submission = orchestrationState.submission || {itemId:context.itemId, fingerprint, payload:{...payload, request_id: typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : createSubmissionId()}};
  orchestrationState.submission = submission; orchestrationState.operation = 'start'; orchestrationNode('start').disabled = true;
  try {
    const response = await analysisExecutionRequestJson(orchestrationBase(submission.itemId, ''), {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(submission.payload)});
    if (!response.run?.run_id) throw Error('受付IDを取得できませんでした。保存済み実行から確認してください。');
    orchestrationState.submission = null;
    orchestrationAdopt(response.run, submission.itemId, context.data?.item?.source_name);
    if (orchestrationSetupCurrent(setupEpoch)) { orchestrationNode('settings').close(); showAnalysisOrchestration(); }
    orchestrationSchedule();
  } catch (error) {
    if (error.status && error.status < 500) orchestrationState.submission = null;
    if (orchestrationSetupCurrent(setupEpoch)) setAlert(orchestrationNode('settings-message'), `${error.message}${orchestrationState.submission ? ' 受付状態は未確定です。同じ設定で再送する場合は同じ依頼IDを使います。保存済み実行も確認できます。' : ''}`, true);
  } finally {
    orchestrationState.operation = '';
    if (orchestrationState.run) renderAnalysisOrchestration();
    if (orchestrationSetupCurrent(setupEpoch)) orchestrationNode('start').disabled = false;
  }
}
function orchestrationAdopt(run, itemId, itemName = '') {
  if (run.item_id && run.item_id !== itemId) throw Error('取得した実行の対象が一致しません。');
  ++orchestrationState.epoch; orchestrationState.poll = null;
  orchestrationTableReset();
  orchestrationAssetReset();
  window.clearTimeout(orchestrationState.timer);
  Object.assign(orchestrationState,{runId:run.run_id,itemId,itemName:itemName || run.item_name || run.source_name || (analysisState.itemId===itemId ? analysisState.data?.item?.source_name : '') || '',run,error:'',operation:orchestrationState.operation==='start'?'start':'',lastSeq:null,taskFingerprint:'',recoveryFingerprint:'',initialFingerprint:'',outputFingerprint:'',fetchedAt:Date.now()});
  orchestrationPersist(); renderAnalysisOrchestration();
}
function orchestrationSchedule() {
  window.clearTimeout(orchestrationState.timer);
  const run=orchestrationState.run, publication=run?.publication;
  const outputActive=run?.status==='completed' && (publication?.save_status==='saving' || ['pending','publishing'].includes(publication?.publication_status));
  if (orchestrationActiveStatuses.includes(run?.status) || !run || outputActive || orchestrationPendingCompletion(run)) orchestrationState.timer = window.setTimeout(pollAnalysisOrchestration, 1500);
}
async function pollAnalysisOrchestration() {
  if (!orchestrationState.runId || orchestrationState.poll || orchestrationState.operation) return;
  window.clearTimeout(orchestrationState.timer);
  const token = {epoch:orchestrationState.epoch,itemId:orchestrationState.itemId,runId:orchestrationState.runId}; orchestrationState.poll = token;
  const owns = () => orchestrationState.epoch === token.epoch && orchestrationState.poll === token;
  try {
    const response = await analysisExecutionRequestJson(orchestrationBase(token.itemId, token.runId));
    if (!owns()) return;
    if (response.run?.run_id !== token.runId || response.run.item_id && response.run.item_id !== token.itemId) throw Error('状態の対象IDが一致しません。');
    orchestrationState.run = response.run; orchestrationState.error = ''; orchestrationState.fetchedAt = Date.now();
  } catch (error) { if (owns()) orchestrationState.error = `状態を取得できません: ${error.message}。実行が停止したかは未確認です。`; }
  finally { if (owns()) { orchestrationState.poll = null; renderAnalysisOrchestration(); orchestrationSchedule(); } }
}
function showAnalysisOrchestration() {
  if (!orchestrationState.runId) { openAnalysisOrchestrationSettings(); return; }
  ++orchestrationState.viewerEpoch;
  orchestrationNode('result-view').hidden = true;
  renderAnalysisOrchestration();
  if (!orchestrationNode('live').open) orchestrationNode('live').showModal();
  pollAnalysisOrchestration();
}
function orchestrationRunRole(id) {
  const roles = orchestrationState.run?.roles;
  return Array.isArray(roles) ? roles.find(role => (role.id || role.role) === id) || {} : roles?.[id] || {};
}
function orchestrationRenderRole(role) {
  const run = orchestrationState.run || {}, data = orchestrationRunRole(role.id);
  const tasks = (run.tasks || []).filter(task => (task.role || task.assigned_to) === role.id);
  const status = data.status || (tasks.some(t => t.status === 'running') ? 'running' : tasks.length ? 'idle' : 'pending');
  const card = orchestrationElement('article', undefined, 'orchestration-role'); card.dataset.role = role.id; card.dataset.status = status;
  const heading = orchestrationElement('div', undefined, 'orchestration-role-heading');
  heading.append(orchestrationElement('strong', role.label), orchestrationElement('span', role.kind === 'ai' ? 'AI' : 'CODE','orchestration-kind'));
  const config = run.config?.roles?.[role.id] || {};
  const provider = data.provider || config.provider || run.config?.provider;
  const model = data.model || config.model || run.config?.model;
  const modelText = role.kind === 'code' ? (role.id === 'statistics' ? 'Python · 決定的な集計' : 'アプリ · LLM呼出しなし') : `${provider || '実行先未取得'} / ${model || 'モデル未取得'}`;
  card.append(heading,orchestrationElement('small',role.subtitle),orchestrationElement('p',modelText,'orchestration-role-model'));
  card.append(orchestrationElement('p',orchestrationLabel(status),'orchestration-role-status'));
  if(role.id==='obsidian_manager') {
    card.append(orchestrationElement('p','判断と台帳の参照を受け取り、管理ノートと索引を更新します。','orchestration-role-task'));
    return card;
  }
  const assigned = data.assigned ?? (Array.isArray(run.tasks) ? tasks.length : null), completed = data.completed ?? (Array.isArray(run.tasks) ? tasks.filter(t=>['succeeded','completed'].includes(t.status)).length : null), failed = data.failed ?? (Array.isArray(run.tasks) ? tasks.filter(t=>t.status==='failed').length : null);
  card.append(orchestrationElement('p',`割当 ${orchestrationNumber(assigned)} · 成功 ${orchestrationNumber(completed)} · 失敗/要確認 ${orchestrationNumber(failed)}`,'orchestration-role-counts'));
  const current = data.current_task || tasks.find(t=>t.status==='running')?.title;
  card.append(orchestrationElement('p',typeof current === 'object' ? current.title || current.task_id : current || '進行中タスクなし','orchestration-role-task'));
  return card;
}
function renderAnalysisOrchestration() {
  const state = orchestrationState, run = state.run, live = orchestrationNode('live'); if (!live) return;
  const active = orchestrationActiveStatuses.includes(run?.status);
  orchestrationTableAvailability();
  orchestrationHumanAvailability();
  orchestrationAssetAvailability();
  orchestrationParticipantAvailability();
  const draining = !active && orchestrationPendingCompletion(run);
  orchestrationNode('chip').hidden = !state.runId;
  orchestrationNode('chip').classList.toggle('is-active', active || draining);
  orchestrationText('chip-label', `自律分析 · ${run ? orchestrationLabel(run.status) : '状態確認'}`);
  if (!run) { orchestrationText('status','保存済みの状態を確認中'); setAlert(orchestrationNode('live-message'),state.error,Boolean(state.error)); return; }
  orchestrationText('live-title',active ? '問いから、次の分析へ' : '保存された分析の状態');
  orchestrationText('live-target',`${run.item_name || run.source_name || state.itemName || state.itemId} · Run ${run.run_id} · 入力版 ${run.source_revision ?? run.config?.source_revision ?? '不明'}`);
  orchestrationText('live-question',run.config?.question || run.question || '分析目的は未取得');
  orchestrationText('status',`${orchestrationLabel(run.status)}${draining ? ' · 残処理の終了待ち' : ''}${run.phase ? ` · ${{core:'Coreの判断',specialists:'専門処理',stop_review:'終了前レビュー',stopped:'停止',initial:'初期分析（コード処理）'}[run.phase] || run.phase}` : ''}`);
  orchestrationText('updated',state.fetchedAt ? `最終取得 ${new Date(state.fetchedAt).toLocaleTimeString('ja-JP')}` : '未取得');
  const notice=[state.error,run.error,run.uncertain_tasks?.length ? `実行結果が不明なタスク: ${run.uncertain_tasks.join(', ')}。二重実行を避けるため、自動再発注・通常の再開はできません。` : ''].filter(Boolean).join('\n');
  setAlert(orchestrationNode('live-message'),notice,Boolean(notice));
  const usage = run.usage || {}, tasks = run.tasks || [];
  const tokenValue = usage.total_tokens ?? usage.tokens;
  const tokenLabel = ['partial','reported'].includes(usage.measurement_status) || usage.tokens_complete === false || usage.tokens_partial || usage.partial ? 'トークン（一部計測）' : 'トークン（実測）';
  const metrics = [[run.iteration ?? null,'Core巡回'],[usage.calls ?? usage.llm_calls ?? null,`AI呼出し / ${run.config?.max_calls ?? '—'}`],[Array.isArray(run.tasks) ? tasks.length : null,'登録タスク'],[tokenValue ?? null,tokenLabel]];
  orchestrationNode('metrics').replaceChildren(...metrics.map(([value,label])=>{const node=orchestrationElement('div');node.append(orchestrationElement('strong',orchestrationNumber(value)),orchestrationElement('span',label));return node;}));
  orchestrationNode('role-core').replaceChildren(orchestrationRenderRole(orchestrationRoles[0]));
  orchestrationNode('role-handler').replaceChildren(orchestrationRenderRole(orchestrationRoles[1]));
  orchestrationNode('specialists').replaceChildren(...orchestrationRoles.slice(2).map(orchestrationRenderRole));
  const events = run.events || [], latest = events.at(-1), seq = latest?.seq ?? latest?.sequence ?? null;
  // Only a new persisted event triggers a short transfer animation. No fabricated progress.
  if (active && seq !== null && seq !== state.lastSeq) {
    const link = orchestrationNode(latest.from === 'core' || latest.to === 'core' ? 'flow-decision' : 'flow-dispatch');
    link.classList.remove('has-event'); void link.offsetWidth; link.classList.add('has-event');
  }
  state.lastSeq=seq;
  orchestrationText('live-event',latest ? `最新の記録: ${latest.message || latest.type}${latest.from || latest.to ? ` · ${latest.from || '—'} → ${latest.to || '—'}` : ''}` : 'イベントはまだ記録されていません。');
  const stop = orchestrationNode('stop'), resume = orchestrationNode('resume');
  const canCancel = Array.isArray(run.allowed_actions) ? run.allowed_actions.includes('cancel') : active;
  stop.hidden = !canCancel && !['cancelling','stopping'].includes(run.status); stop.disabled = Boolean(state.operation || !canCancel || ['cancelling','stopping'].includes(run.status));
  stop.textContent = ['cancelling','stopping'].includes(run.status) ? '停止・完了を待っています' : '停止する';
  const canResume = Array.isArray(run.allowed_actions) ? run.allowed_actions.includes('resume') : run.can_resume === true;
  resume.hidden = !canResume; resume.disabled = Boolean(state.operation);
  orchestrationNode('refresh').disabled = Boolean(state.operation || state.poll);
  const reasons = {question_satisfied:'問いを充足',human_review_required:'人の確認待ち',no_new_tasks:'追加タスクなし',importance_threshold:'重要度しきい値',execution_failure:'実行障害',review_incomplete:'レビュー未完了',call_timeout:'呼出し時間上限',call_budget_limit:'AI呼出し上限',task_budget_limit:'タスク上限',source_deleted:'入力データの削除',user_cancelled:'利用者停止',user_stop:'利用者停止',time_limit:'時間上限',iteration_limit:'回数上限',call_budget:'AI呼出し上限',task_budget:'タスク上限',budget_limit:'予算上限',completed:'問いを充足',no_more_evidence:'追加の証拠なし',error:'実行障害',human_review:'人の確認待ち'};
  orchestrationText('stop-reason',run.stop_reason ? `停止理由: ${reasons[run.stop_reason] || run.stop_reason}。保存済みの部分結果・未実施レビューを含めて確認してください。` : '利用者停止と安全上限を最優先します。研究上の結論は未確定の探索的下書きです。');
  const config = run.config || {};
  orchestrationText('config',`実行条件: ${config.stop_mode || '未取得'} / 最低 ${config.min_iterations ?? '未取得'}回 / 時間 ${config.time_limit_seconds ?? '無上限'}${config.time_limit_seconds ? '秒' : ''} / 回数上限 ${config.max_iterations ?? '無上限'} / 呼出し上限 ${config.max_calls ?? '不明'} / タスク上限 ${config.max_tasks ?? '不明'} / 外部送信 ${config.provider_policy === 'local_only' ? 'なし（ローカル限定）' : config.provider_policy === 'cloud_allowed' ? '同意済みクラウドを許可' : '未取得'}`);
  for (const [id, suffix] of [['export-json','export.json'],['export-md','export.md']]) orchestrationNode(id).href = `${orchestrationBase()}/${suffix}`;
  orchestrationText('usage-note',`利用量の計測: ${{reported:'一部計測（全量未保証）',unavailable:'未計測'}[usage.measurement_status] || usage.measurement_status || '未取得'} · 計測済み呼出し ${orchestrationNumber(usage.measured_calls)} / ${orchestrationNumber(usage.calls)} · 費用 ${usage.cost == null ? '未計測' : `${String(usage.cost)} ${usage.currency || '通貨未取得'}`}。未計測分を0として補完しません。`);
  orchestrationText('conclusion',run.current_view?.summary || '統合結果はまだ保存されていません。');
  const notes=orchestrationNode('conclusion-notes');notes.replaceChildren();
  for(const [key,label] of [['alternatives','代替説明'],['unresolved','未解決点']])for(const value of run.current_view?.[key] || [])notes.append(orchestrationElement('li',`${label}: ${typeof value === 'string' ? value : JSON.stringify(value)}`));
  orchestrationText('review-state',`終了前レビュー: ${{reviewed:'実施済み（研究上の結論は未確定）',pending:'待機',not_started:'未実施',not_reviewed:'未実施',incomplete:'未完了',unavailable:'実施できず'}[run.review_status] || run.review_status || '状態未取得'}${run.stale ? ' · 入力版が更新された結果です' : ''}`);
  orchestrationRenderInitial(run); orchestrationRenderOutput(run); orchestrationRenderMemory(run); orchestrationRenderRecovery(run); orchestrationRenderTasks(tasks); orchestrationRenderReview(run);
  orchestrationNode('events').replaceChildren(...events.slice(-100).map(event=>orchestrationElement('li',`${event.seq ?? event.sequence ?? '—'} · ${event.message || event.type}${event.task_id ? ` · ${event.task_id}` : ''}`)));
}
function orchestrationRenderInitial(run) {
  const initial=run.initial || {}, stages=Array.isArray(run.initial_stages) ? run.initial_stages : initial.stages || [];
  const available=run.phase==='initial' || Boolean(run.initial) || stages.length>0;
  orchestrationNode('initial').hidden=!available;
  if(!available)return;
  const completed=stages.filter(stage=>stage.status==='completed').length;
  const canResume=Array.isArray(run.allowed_actions) ? run.allowed_actions.includes('resume') : run.can_resume===true;
  orchestrationText('initial-summary',stages.length ? `${completed} / ${stages.length} 段階を保存済み。${initial.status==='ready' ? '初期版は保存済みです。' : run.status==='recovery_required' ? canResume ? '中断した段階は、下の再開操作から復旧できます。' : '再開は許可されていません。表示されたエラーを確認してください。' : ''}` : initial.status==='ready' ? '初期版は保存済みです。この実行には段階別の記録がありません。' : '初期分析の保存地点を確認しています。');
  const fingerprint=JSON.stringify([run.run_id,stages]);
  if(fingerprint===orchestrationState.initialFingerprint)return;
  orchestrationState.initialFingerprint=fingerprint;
  const host=orchestrationNode('initial-stages');host.replaceChildren();
  for(const stage of stages){
    const row=orchestrationElement('li');row.dataset.status=stage.status || 'unknown';
    row.append(orchestrationElement('strong',stage.label || stage.stage_id || stage.id || '段階名未取得'),orchestrationElement('span',stage.status==='completed' ? '保存済み' : orchestrationLabel(stage.status),'orchestration-checkpoint-status'));
    const attempts=stage.attempt_count ?? stage.attempts;
    row.append(orchestrationElement('small',`コード処理 · 実行回数 ${orchestrationNumber(attempts)}${stage.status==='completed' ? ' · 保存済み（再開時に再利用）' : ''}`));
    if(stage.error)row.append(orchestrationElement('p',stage.error,'orchestration-checkpoint-error'));
    if(stage.output_hash || stage.artifact_hash){const details=orchestrationElement('details');details.append(orchestrationElement('summary','保存記録'),orchestrationElement('p',`Hash: ${stage.output_hash || stage.artifact_hash}${stage.completed_at ? ` · 保存日時: ${stage.completed_at}` : ''}`));row.append(details);}
    host.append(row);
  }
}
function orchestrationPublicationSelected(publication) {
  const selected=publication?.publication_targets;
  return Array.isArray(selected) && selected.length===orchestrationPublicationTargets.length && orchestrationPublicationTargets.every(target=>selected.includes(target));
}
function orchestrationOutputLabel(status) {
  return {not_started:'未保存',saving:'保存中',saved:'保存済み',failed:'失敗',interrupted:'中断・要確認',not_selected:'未選択（OFF）',pending:'待機',publishing:'出力中',published:'出力処理成功',incomplete:'一部未完了',conflict:'競合・要確認',unknown:'結果不明',skipped:'未実施'}[status] || status || '状態未取得';
}
function orchestrationArtifactLink(artifact) {
  if(typeof artifact?.url!=='string' || !artifact.url.trim())return null;
  try { const url=new URL(artifact.url,window.location.href);if(!['http:','https:'].includes(url.protocol) || url.username || url.password)return null; } catch(_){return null;}
  const link=orchestrationElement('a',artifact.name || '保存成果物');link.setAttribute('href',artifact.url);link.setAttribute('download','');return link;
}
function orchestrationRenderMemory(run) {
  const memory=run.obsidian_management || {status:'disabled',enabled:false};
  orchestrationText('memory-status',`Obsidian管理: ${orchestrationLabel(memory.status)}${memory.stale ? ' · 入力更新前の記録' : ''}`);
  orchestrationText('memory-location',memory.note_id ? `Orchestrator Vault · ${memory.note_id}` : 'この実行の管理ノートは未保存です。');
  const link=orchestrationNode('memory-note');
  link.hidden=!memory.note_id || !['linked','pending'].includes(memory.status);
  if(link.hidden)link.removeAttribute('href');else link.href=`${orchestrationBase(run.item_id,run.run_id)}/memory/note`;
  const retry=orchestrationNode('memory-retry');
  retry.hidden=memory.enabled!==true || ['linked','disabled','unavailable'].includes(memory.status);
  retry.disabled=Boolean(orchestrationState.operation);
  retry.textContent=orchestrationState.operation==='memory/retry' ? '管理ノートの応答を待っています' : '管理ノートを照合・更新';
  orchestrationText('memory-warning',{failed:'管理ノートを保存できませんでした。分析台帳は保持されています。',missing:'削除済みノートを自動で復元しません。全履歴JSONから元の記録を参照できます。',edited:'手動編集を検出しました。更新時には編集版を履歴へ保存します。',conflict:'管理ノートの所有権・版・hashを確認できません。元の台帳を参照してください。'}[memory.status] || '');
}
function orchestrationRenderOutput(run) {
  const publication=run.publication, selected=orchestrationPublicationSelected(publication), retry=orchestrationNode('publication-retry');
  retry.hidden=!(run.status==='completed' && publication?.can_retry===true);
  retry.disabled=Boolean(orchestrationState.operation);
  retry.textContent=orchestrationState.operation==='publication/retry' ? '保存・出力の応答を待っています' : selected ? '保存・4 Vault出力を再試行' : '固定成果物の保存を再試行';
  const fingerprint=JSON.stringify([run.run_id,run.status,publication]);
  if(fingerprint===orchestrationState.outputFingerprint)return;
  orchestrationState.outputFingerprint=fingerprint;
  orchestrationText('save-status',`アプリ内の固定成果物: ${publication ? orchestrationOutputLabel(publication.save_status) : '保存記録未取得'}${publication?.result_run_id ? ` · ${publication.result_run_id}` : ''}${publication?.stale ? ' · 入力更新前の固定版' : ''}`);
  orchestrationText('publication-status',`Vault出力: ${publication ? orchestrationOutputLabel(publication.publication_status) : '未選択（OFF）'}`);
  orchestrationText('publication-scope',selected ? '開始時に選択済み: Input／Orchestrator／Visualization／Researchの4つ一式。Researchには保存時点の発話本文を含みます。分析の終了と各保存先の成功は別の状態です。' : 'この実行では4 Vault出力を選択していません。保存・再開・再試行から出力先を追加することはありません。');
  const host=orchestrationNode('publication-outcomes');host.replaceChildren();
  for(const [id,label] of orchestrationVaultWriters){
    const outcome=publication?.outcomes?.[id];
    const status=outcome?.status || (selected ? 'unknown' : 'not_selected');
    const row=orchestrationElement('li');row.dataset.writer=id;row.dataset.status=status;
    row.append(orchestrationElement('strong',label),orchestrationElement('span',orchestrationOutputLabel(status)));
    if(outcome?.error)row.append(orchestrationElement('small',outcome.error));host.append(row);
  }
  setAlert(orchestrationNode('publication-error'),publication?.error || '',Boolean(publication?.error));
  const missing=publication?.result_run?.vault_notes?.missing;
  orchestrationNode('publication-note-policy').hidden=!Array.isArray(missing) || !missing.length;
  orchestrationText('publication-note-policy',Array.isArray(missing) && missing.length ? `削除済みノートの記録が${missing.length}件あります。既存の削除保護を維持します。出力処理が成功しても、全ノートの存在を保証するものではありません。` : '');
  const artifacts=orchestrationNode('output-artifacts');artifacts.replaceChildren();
  for(const artifact of publication?.result_run?.artifacts || []){
    const link=orchestrationArtifactLink(artifact);if(!link)continue;
    const row=orchestrationElement('li');row.append(link);artifacts.append(row);
  }
  orchestrationText('publication-retry-note',selected ? '再試行は同じ固定成果物・同じ承認済み範囲で4つの保存先を再訪します。失敗先だけの再試行ではありません。AI・統計の再計算は行いません。生成ノートの手動編集履歴・削除保護を使います。' : '再試行が許可された場合も、固定成果物の保存だけが対象です。AI・統計の再計算やVault出力は行いません。');
}
function orchestrationRenderTasks(tasks) {
  const fingerprint=JSON.stringify([orchestrationState.runId,tasks,orchestrationState.run?.results]);
  if(fingerprint===orchestrationState.taskFingerprint)return;
  orchestrationState.taskFingerprint=fingerprint;
  const focused=document.activeElement?.dataset?.orchestrationResult;
  const host=orchestrationNode('tasks'); host.replaceChildren(); orchestrationText('task-count',`(${tasks.length})`);
  for (const task of tasks) {
    const row=orchestrationElement('tr');
    const title=orchestrationElement('td',orchestrationTableNames[task.method_id] || orchestrationAssetMethodNames[task.method_id] || task.title || task.task_id || '名称未取得'); title.append(orchestrationElement('small',task.task_id || ''));
    const role=orchestrationRoles.find(r=>r.id===(task.role || task.assigned_to));
    const who=orchestrationElement('td',`${role?.label || task.role || '担当未取得'} / ${role?.kind === 'code' ? 'コード実行' : task.model || 'モデル未取得'}`);
    const result=orchestrationElement('td');
    const resultId = task.result_id || (orchestrationState.run?.results || []).find(result=>result.task_id===task.task_id)?.result_id;
    if (resultId) { const button=orchestrationElement('button','結果を読む','link-button');button.type='button';button.dataset.orchestrationResult=resultId;button.addEventListener('click',()=>orchestrationReadResults(resultId));result.append(button); }
    else result.textContent=task.error || '保存結果なし';
    row.append(title,who,orchestrationElement('td',orchestrationLabel(task.status)),result);host.append(row);
  }
  if(focused && orchestrationNode('live').open) [...host.querySelectorAll('button')].find(button=>button.dataset.orchestrationResult===focused)?.focus();
  if (!tasks.length) { const row=orchestrationElement('tr'),cell=orchestrationElement('td','タスクはまだ登録されていません。');cell.colSpan=4;row.append(cell);host.append(row); }
}
function orchestrationRenderReview(run) {
  const host=orchestrationNode('review-content');host.replaceChildren();
  const issues=run.issues || run.critic_issues || run.unresolved_issues || run.critic_findings || [];
  const decisions=run.critique_responses || run.critic_decisions || run.critic_responses || run.core_decisions || [];
  if (!issues.length && !decisions.length) host.append(orchestrationElement('p',run.review_status === 'reviewed' ? '保存済みの終了前レビューに指摘はありません。研究上の妥当性・確認分析の成功を意味しません。' : '批判レビュー・Coreの採否記録はまだ取得されていません。指摘なし・検証済みとは扱いません。'));
  for (const issue of issues) host.append(orchestrationElement('p',`${issue.issue_id || '指摘ID未取得'} · ${issue.severity || issue.importance || '重要度未取得'} · ${issue.status || '採否未取得'} · ${issue.reason || issue.message || issue.claim || issue.title || JSON.stringify(issue)}${issue.evidence_ids?.length ? ` / 根拠 ${issue.evidence_ids.join(', ')}` : ''}${issue.target_id ? ` / 対象 ${issue.target_id} 第${issue.target_version ?? '不明'}版` : ''}`));
  for (const decision of decisions) host.append(orchestrationElement('p',`Core / ${decision.issue_id || '対象指摘未取得'}: ${{adopt:'採用',reject:'棄却',defer:'保留'}[decision.disposition] || decision.disposition || decision.decision || decision.status || '判断未取得'} · ${decision.reason || decision.rationale || JSON.stringify(decision)}${decision.impact ? ` / 結論への影響: ${decision.impact}` : ''}`));
}
function orchestrationRenderRecovery(run) {
  const available=run.status==='recovery_required' && Array.isArray(run.uncertain_tasks) && run.uncertain_tasks.length>0;
  orchestrationNode('recovery').hidden=!available;
  if(!available){orchestrationState.recoveryFingerprint='';return;}
  const fingerprint=JSON.stringify([run.run_id,run.uncertain_tasks]);
  if(fingerprint!==orchestrationState.recoveryFingerprint){
    orchestrationState.recoveryFingerprint=fingerprint;
    const host=orchestrationNode('recovery-tasks');host.replaceChildren();
    for(const id of run.uncertain_tasks){
      const task=(run.tasks||[]).find(task=>task.task_id===id),label=orchestrationElement('label',undefined,'check-row'),checkbox=orchestrationElement('input');
      checkbox.type='checkbox';checkbox.value=id;checkbox.dataset.recoveryTask=id;
      label.append(checkbox,orchestrationElement('span',`${id} · ${task?.title || '名称未取得'} を放棄する（再送なし）`));host.append(label);
    }
  }
  orchestrationNode('abandon').disabled=Boolean(orchestrationState.operation) || !orchestrationNode('recovery-tasks').querySelector('input:checked');
}
function orchestrationAbandonAndResume(){
  const run=orchestrationState.run;
  if(run?.status!=='recovery_required' || orchestrationState.operation)return;
  const selected=[...orchestrationNode('recovery-tasks').querySelectorAll('input:checked')].map(input=>input.value).filter(id=>(run.uncertain_tasks||[]).includes(id));
  if(!selected.length)return;
  orchestrationAction('resume',{recovery:Object.fromEntries(selected.map(id=>[id,'abandon']))});
}
async function orchestrationAction(action, payload = {}) {
  if (!orchestrationState.runId || orchestrationState.operation) return;
  const allowed=orchestrationState.run?.allowed_actions;
  if (['cancel','resume'].includes(action) && !payload.recovery && Array.isArray(allowed) && !allowed.includes(action)) return;
  if (action === 'publication/retry' && (orchestrationState.run?.status !== 'completed' || orchestrationState.run?.publication?.can_retry !== true)) return;
  if (action === 'memory/retry' && orchestrationState.run?.obsidian_management?.enabled !== true) return;
  if (action === 'cancel' && !window.confirm('新規タスクの発注を止めます。完了済み結果は保持し、停止不能な呼出しは完了待ちになります。停止しますか？')) return;
  if (action === 'resume' && !window.confirm(payload.recovery ? `選択した${Object.keys(payload.recovery).length}件の結果不明な呼出しを放棄します（${Object.keys(payload.recovery).join(', ')}）。結果は採用せず再送もしません。発生済み費用は不明です。残り予算で復旧を続けますか？` : '保存済みの条件・送信先・残り予算で再開します。完了済み結果を保持します。再開しますか？')) return;
  const epoch=++orchestrationState.epoch,itemId=orchestrationState.itemId,runId=orchestrationState.runId;
  orchestrationState.poll=null;window.clearTimeout(orchestrationState.timer);
  orchestrationState.operation=action;renderAnalysisOrchestration();
  let refreshNeeded=false;
  try {
    const result=await analysisExecutionRequestJson(`${orchestrationBase(itemId,runId)}/${action}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(['publication/retry','memory/retry'].includes(action) ? {} : payload)});
    if (epoch!==orchestrationState.epoch) return;
    if (result.run?.run_id!==runId || result.run.item_id && result.run.item_id!==itemId) throw Error('実行の対象IDが一致しません。');
    orchestrationState.run=result.run;orchestrationState.error='';orchestrationState.fetchedAt=Date.now();
  } catch(error) { refreshNeeded=true; if(epoch===orchestrationState.epoch) orchestrationState.error=`${action==='cancel'?'停止':action==='publication/retry'?'保存・出力の再試行':action==='memory/retry'?'管理ノートの更新':'再開'}の受付を確認できません: ${error.message}。状態を更新して確認してください。`; }
  finally { if(epoch===orchestrationState.epoch){orchestrationState.operation='';renderAnalysisOrchestration();if(refreshNeeded)pollAnalysisOrchestration();else orchestrationSchedule();} }
}
async function orchestrationReadResults(resultId = '') {
  const request=++orchestrationState.resultRequest,epoch=orchestrationState.epoch,viewer=orchestrationState.viewerEpoch,runId=orchestrationState.runId;
  const host=orchestrationNode('result-content');host.replaceChildren(orchestrationElement('p','保存済み結果を取得しています…'));orchestrationNode('result-view').hidden=false;
  try {
    const data=await analysisExecutionRequestJson(`${orchestrationBase()}/results${resultId ? `/${encodeURIComponent(resultId)}` : ''}`);
    if(request!==orchestrationState.resultRequest || epoch!==orchestrationState.epoch || viewer!==orchestrationState.viewerEpoch || runId!==orchestrationState.runId || !orchestrationNode('live').open) return;
    host.replaceChildren(orchestrationElement('p','固定された保存結果です。初期版・根拠ID・未解決点を含めて確認してください。'));
    if (!orchestrationTableResult(host,data.raw)) {
      const pre=orchestrationElement('pre',JSON.stringify(data,null,2));pre.tabIndex=0;host.append(pre);
    }
  } catch(error) { if(request===orchestrationState.resultRequest && epoch===orchestrationState.epoch && viewer===orchestrationState.viewerEpoch && orchestrationNode('live').open)host.replaceChildren(orchestrationElement('p',`結果を取得できません: ${error.message}`)); }
}
async function orchestrationHistory() {
  if(!orchestrationSetupCurrent())return;
  const epoch=orchestrationState.setupEpoch,itemId=orchestrationState.setup.itemId,host=orchestrationNode('history-list');
  host.replaceChildren(orchestrationElement('p','保存済み実行を取得しています…'));
  try {
    const data=await analysisExecutionRequestJson(orchestrationBase(itemId,''));
    if(!orchestrationSetupCurrent(epoch))return;
    host.replaceChildren();
    for(const run of data.runs || []) {
      const button=orchestrationElement('button',`${orchestrationLabel(run.status)} · ${run.config?.question || run.run_id}`,'secondary-button');button.type='button';
      button.addEventListener('click',()=>{if(!orchestrationSetupCurrent(epoch))return;orchestrationAdopt(run,itemId);if(run.request_id===orchestrationState.submission?.payload.request_id)orchestrationState.submission=null;orchestrationNode('settings').close();showAnalysisOrchestration();});host.append(button);
    }
    if(!data.runs?.length)host.append(orchestrationElement('p','保存済み実行はありません。'));
  }catch(error){if(orchestrationSetupCurrent(epoch))host.replaceChildren(orchestrationElement('p',error.message));}
}
function bindAnalysisOrchestration() {
  listen(orchestrationNode('asset-load'),'click',()=>orchestrationAssetLoad());
  listen(orchestrationNode('asset-next'),'click',()=>orchestrationAssetLoad(orchestrationAssetState.options?.next_offset));
  listen(orchestrationNode('asset-method'),'change',orchestrationAssetInputs);
  listen(orchestrationNode('asset-inputs'),'change',orchestrationAssetParameters);
  listen(orchestrationNode('asset-form'),'input',orchestrationAssetInvalidate);
  listen(orchestrationNode('asset-form'),'change',orchestrationAssetInvalidate);
  listen(orchestrationNode('asset-form'),'submit',orchestrationAssetAdd);
  listen(orchestrationNode('asset-clear'),'click',()=>{orchestrationAssetState.steps=[];orchestrationAssetState.refreshRequired=false;orchestrationAssetInvalidate();orchestrationAssetRenderSteps();orchestrationAssetInputs();});
  listen(orchestrationNode('asset-review'),'click',orchestrationAssetReview);
  listen(orchestrationNode('asset-execute'),'click',orchestrationAssetExecute);
  listen(orchestrationNode('participant-form'),'input',orchestrationParticipantEdit);
  listen(orchestrationNode('participant-form'),'change',orchestrationParticipantEdit);
  listen(orchestrationNode('participant-form'),'submit',orchestrationParticipantReview);
  listen(orchestrationNode('participant-save'),'click',orchestrationParticipantSave);
  listen(orchestrationNode('participant-prepare'),'click',orchestrationAssetPrepareParticipant);
  listen(orchestrationNode('human-load'),'click',()=>orchestrationHumanLoad(orchestrationHumanState.options?.offset||0));
  listen(orchestrationNode('human-next'),'click',()=>orchestrationHumanLoad(orchestrationHumanState.options?.next_offset,false));
  listen(orchestrationNode('human-evidence'),'click',()=>orchestrationNode('viewer').click());
  listen(orchestrationNode('human-asset'),'change',()=>orchestrationHumanSelect('asset'));
  listen(orchestrationNode('human-target'),'change',()=>orchestrationHumanSelect('target'));
  listen(orchestrationNode('human-step'),'change',()=>orchestrationHumanSelect('step'));
  listen(orchestrationNode('human-form'),'input',orchestrationHumanEdit);
  listen(orchestrationNode('human-decision'),'change',orchestrationHumanEdit);
  listen(orchestrationNode('human-author-confirm'),'change',orchestrationHumanEdit);
  listen(orchestrationNode('human-form'),'submit',orchestrationHumanReview);
  listen(orchestrationNode('human-save'),'click',orchestrationHumanSave);
  listen(orchestrationNode('table-load'),'click',()=>orchestrationTableLoad());
  listen(orchestrationNode('table-next'),'click',()=>orchestrationTableLoad(orchestrationTableState.options?.next_offset));
  listen(orchestrationNode('table-form'),'submit',orchestrationTableReview);
  listen(orchestrationNode('table-execute'),'click',orchestrationTableExecute);
  for (const id of ['table-asset','table-method','table-second']) listen(orchestrationNode(id),'change',orchestrationTableParameters);
  listen(orchestrationNode('table-parameters'),'input',orchestrationTableInvalidate);
  listen(orchestrationNode('table-parameters'),'change',orchestrationTableInvalidate);
  const overrideHost=orchestrationNode('role-overrides');
  for(const role of orchestrationRoles.filter(r=>r.kind==='ai')) {
    const row=orchestrationElement('div',undefined,'orchestration-form-grid');
    const provider=orchestrationElement('label',undefined,'field');provider.append(orchestrationElement('span',`${role.label}の実行先`));
    const select=orchestrationElement('select');select.id=`orchestration-provider-${role.id}`;
    for(const [value,label] of [['','共通設定'],['lmstudio','LM Studio（ローカル）'],['openai','OpenAI'],['google','Google Gemini']]){const option=orchestrationElement('option',label);option.value=value;select.append(option);}provider.append(select);
    const model=orchestrationElement('label',undefined,'field');model.append(orchestrationElement('span',`${role.label}のモデルID`));const input=orchestrationElement('input');input.id=`orchestration-model-${role.id}`;input.placeholder='空欄なら共通設定';input.maxLength=200;model.append(input);row.append(provider,model);overrideHost.append(row);
  }
  listen(orchestrationNode('open'),'click',openAnalysisOrchestrationSettings);
  listen(orchestrationNode('chip'),'click',showAnalysisOrchestration);
  listen(orchestrationNode('form'),'submit',startAnalysisOrchestration);
  listen(orchestrationNode('settings-close'),'click',()=>orchestrationNode('settings').close());
  listen(orchestrationNode('settings'),'close',()=>{if(!orchestrationNode('settings').open)++orchestrationState.setupEpoch;});
  listen(orchestrationNode('live-close'),'click',()=>orchestrationNode('live').close());
  listen(orchestrationNode('live'),'close',()=>{if(!orchestrationNode('live').open)++orchestrationState.viewerEpoch;});
  listen(orchestrationNode('stop'),'click',()=>orchestrationAction('cancel'));
  listen(orchestrationNode('resume'),'click',()=>orchestrationAction('resume'));
  listen(orchestrationNode('publication-retry'),'click',()=>orchestrationAction('publication/retry'));
  listen(orchestrationNode('memory-retry'),'click',()=>orchestrationAction('memory/retry'));
  listen(orchestrationNode('abandon'),'click',orchestrationAbandonAndResume);
  listen(orchestrationNode('recovery-tasks'),'change',()=>orchestrationRenderRecovery(orchestrationState.run));
  listen(orchestrationNode('refresh'),'click',pollAnalysisOrchestration);
  listen(orchestrationNode('results'),'click',()=>orchestrationReadResults());
  listen(orchestrationNode('history'),'click',orchestrationHistory);
  listen(orchestrationNode('form'),'input',event=>{if(event.target.matches('select[id^="orchestration-provider"], #orchestration-provider'))orchestrationNode('cloud-consent').checked=false;orchestrationSyncForm();});
  listen(orchestrationNode('form'),'change',event=>{if(event.target.matches('select[id^="orchestration-provider"], #orchestration-provider'))orchestrationNode('cloud-consent').checked=false;orchestrationSyncForm();});
  const motion=window.matchMedia('(prefers-reduced-motion: reduce)');
  orchestrationNode('reduced-motion').checked=motion.matches;
  listen(orchestrationNode('reduced-motion'),'change',()=>orchestrationNode('live').classList.toggle('reduce-motion',orchestrationNode('reduced-motion').checked));
  motion.addEventListener?.('change',event=>{orchestrationNode('reduced-motion').checked=event.matches;orchestrationNode('live').classList.toggle('reduce-motion',event.matches);});
  orchestrationNode('live').classList.toggle('reduce-motion',motion.matches);
  let stored;try{stored=JSON.parse(sessionStorage.getItem(orchestrationStorageKey)||'null');}catch(_){/* unavailable */}
  if(stored?.itemId && stored?.runId){orchestrationState.itemId=stored.itemId;orchestrationState.runId=stored.runId;renderAnalysisOrchestration();pollAnalysisOrchestration();}
}
const orchestrationTableState = {options:null, reviewed:null, loading:false, sending:false, request:0};
const orchestrationTableNames = {table_projection:'列・行の抽出',table_aggregate:'発話ごとの件数',table_join:'発話ごとの表結合',table_frequency:'カテゴリの度数',table_crosstab:'2カテゴリのクロス集計'};
const orchestrationConnectedNames = {theme_evidence_table:'採用テーマの根拠を表にする',unit_projection:'固定単位表の列・行の抽出',unit_aggregate:'固定単位ごとの集約',unit_join:'同じ固定単位の表結合',unit_correlation:'固定単位の探索的相関'};
const orchestrationTableFieldNames = {value_column:'値の列',status_column:'欠測・処理状態の列',row_column:'行カテゴリの列',column_column:'列カテゴリの列',group_by:'グループ列',key:'結合キー',operation:'集計方法',unit:'集計単位'};
function orchestrationTableInvalidate() {
  orchestrationTableState.reviewed=null;
  orchestrationNode('table-confirmation').hidden=true;
}
function orchestrationTableReset() {
  ++orchestrationTableState.request;
  Object.assign(orchestrationTableState,{options:null,reviewed:null,loading:false,sending:false});
  orchestrationNode('table-form').hidden=true;
  orchestrationNode('table-next').hidden=true;
  orchestrationNode('table-message').textContent='';
}
function orchestrationTableAvailability() {
  const run=orchestrationState.run, state=orchestrationTableState;
  const ready=['queued','running'].includes(run?.status) && run?.phase!=='initial' && !run?.stale && !run?.cancel_requested;
  const reason=ready?(state.options && state.options.context.generation!==run?.generation?'実行の固定版が変わりました。保存表を再取得してください。':'現在の固定実行へ追加できます。保存表と現在の許可を確認してください。'):run?.phase==='initial'?'固定入力の準備中です。準備が終わってから確認してください。':'停止・完了・入力変更または復旧待ちの実行には追加できません。';
  if (!ready || state.options && state.options.context.generation!==run?.generation) orchestrationTableInvalidate();
  orchestrationText('table-availability',reason);
  orchestrationNode('table-load').disabled=!ready||state.loading||state.sending;
  orchestrationNode('table-next').disabled=!ready||state.loading||state.sending;
  const stale=state.options && state.options.context.generation!==run?.generation;
  orchestrationNode('table-review').disabled=!ready||stale||state.loading||state.sending;
  orchestrationNode('table-execute').disabled=!ready||state.loading||state.sending||!state.reviewed;
}
async function orchestrationTableJson(url,options={}) {
  // Preserve the existing HTTP error contract, including its responsible field.
  const response=await apiFetch(url,options), data=await readJsonResponse(response);
  if(!response.ok){const error=Error(data.error||`HTTP ${response.status}`);error.field=data.field;error.code=data.reason_code;throw error;}
  return data;
}
function orchestrationTableError(error) {
  const labels={parameters:'処理パラメーター',bindings:'保存表・利用許可',context:'固定入力・実行状態',method_id:'処理方式'};
  orchestrationText('table-message',`${labels[error.field]||orchestrationTableFieldNames[error.field]||'保存表の接続'}: ${error.message}。選択肢を再取得して確認してください。`);
  const node=orchestrationNode(`table-param-${error.field}`)||orchestrationNode(error.field==='method_id'?'table-method':'table-asset');
  node.setAttribute('aria-invalid','true');node.setAttribute('aria-describedby','orchestration-table-message');
}
async function orchestrationTableLoad(offset=0) {
  const state=orchestrationTableState;if(state.loading||state.sending)return;
  const request=++state.request,epoch=orchestrationState.epoch,viewer=orchestrationState.viewerEpoch;
  state.loading=true;state.options=null;orchestrationTableInvalidate();orchestrationNode('table-form').hidden=true;
  orchestrationText('table-message','保存表と利用許可を取得しています…');orchestrationTableAvailability();
  const current=()=>request===state.request&&epoch===orchestrationState.epoch&&viewer===orchestrationState.viewerEpoch&&orchestrationNode('live').open;
  try {
    const data=await orchestrationTableJson(`${orchestrationBase()}/table-pilot?offset=${Number(offset)||0}`);
    if(!current())return;
    state.options=data;
    for(const [id,entries] of [['table-asset',data.inputs],['table-second',data.inputs],['table-method',data.methods]]) {
      orchestrationNode(id).replaceChildren(...entries.map((entry,index)=>{
        const option=orchestrationElement('option',entry.method_id?orchestrationTableNames[entry.method_id]:`保存表 ${data.offset+index+1} · ${entry.row_ids.length}行 · ${entry.fields.join(' / ')}`);
        option.value=entry.method_id||String(index);return option;
      }));
      orchestrationNode(id).removeAttribute('aria-invalid');
    }
    orchestrationNode('table-next').hidden=data.next_offset===null;
    orchestrationNode('table-form').hidden=!data.inputs.length;
    orchestrationText('table-message',data.inputs.length?'利用可能な保存表です。処理方式と列を選んでください。':'この固定入力で利用できる保存表はありません。保存済み表・宣言済み変数・利用許可が必要です。');
    if(data.inputs.length)orchestrationTableParameters();
  }catch(error){if(current())orchestrationTableError(error);}
  finally{if(request===state.request){state.loading=false;orchestrationTableAvailability();}}
}
function orchestrationTableSelection() {
  const options=orchestrationTableState.options;
  return {options,asset:options?.inputs[Number(orchestrationNode('table-asset').value)],
    second:options?.inputs[Number(orchestrationNode('table-second').value)],
    method:options?.methods.find(m=>m.method_id===orchestrationNode('table-method').value)};
}
function orchestrationTableParameters() {
  orchestrationTableInvalidate();const {options,asset,method}=orchestrationTableSelection();if(!asset||!method)return;
  orchestrationNode('table-second-field').hidden=method.method_id!=='table_join';
  const typeLabels={integer:'整数',number:'数値',boolean:'真偽',string:'文字列',nominal:'名義尺度',ordinal:'順序尺度',ratio:'比率尺度',interval:'間隔尺度',utterance:'発話'};
  const types=Object.fromEntries(asset.variables.map(v=>[v.variable_id,[v.value_type,v.scale,v.unit].map(k=>typeLabels[k]||k).join(' / ')]));
  orchestrationText('table-scope',`固定入力版 ${options.input.source_revision} · 分析版 ${options.input.analysis_revision} · 対象 ${asset.scope.member_ids.length}発話 · 除外 ${asset.scope.context_ids.length}発話 · 宣言された単位: 発話`);
  const host=orchestrationNode('table-parameters');host.replaceChildren();
  const field=(name,choices,selected)=>{
    const label=orchestrationElement('label',undefined,'field'),caption=orchestrationElement('span',orchestrationTableFieldNames[name]||name);caption.id=`orchestration-table-label-${name}`;label.append(caption);
    const select=orchestrationElement('select');select.id=`orchestration-table-param-${name}`;
    select.setAttribute('aria-labelledby',caption.id);
    for(const [value,text] of choices){const option=orchestrationElement('option',text);option.value=value;select.append(option);}if(selected!==undefined)select.value=selected;
    label.append(select);host.append(label);
  };
  for(const name of method.parameter_fields) {
    if(name==='columns'){
      const box=orchestrationElement('fieldset');box.append(orchestrationElement('legend','抽出する列（宣言済み）'));
      for(const column of asset.fields){const label=orchestrationElement('label',undefined,'check-row');const input=orchestrationElement('input');input.type='checkbox';input.value=column;input.checked=true;input.disabled=['utterance_id','conversation_id','value_status'].includes(column);input.name='table-columns';label.append(input,orchestrationElement('span',`${column}${types[column]?` · ${types[column]}`:''}${input.disabled?'（固定の必須列）':''}`));box.append(label);}host.append(box);
    }else if(name==='row_ids'){
      const label=orchestrationElement('label',undefined,'field');label.append(orchestrationElement('span','保存順で先頭から抽出する行数'));
      const input=orchestrationElement('input');input.type='number';input.min='1';input.max=String(asset.row_ids.length);input.value=input.max;input.required=true;input.id='orchestration-table-param-row_ids';label.append(input);host.append(label);
    }else if(name==='operation')field(name,[[method.parameter_defaults[name],'件数']],method.parameter_defaults[name]);
    else if(name==='unit')field(name,[['utterance','発話']],method.parameter_defaults[name]);
    else if(['status_column','group_by','key'].includes(name))field(name,[[method.parameter_defaults[name],{status_column:'保存された欠測・処理状態',group_by:'発話ごと',key:'同じ発話'}[name]]],method.parameter_defaults[name]);
    else field(name,asset.variables.filter(v=>!['utterance_id','conversation_id','value_status','source_utterance_ids'].includes(v.variable_id)).map(v=>[v.variable_id,`${v.variable_id} · ${types[v.variable_id]}`]));
  }
  orchestrationTableAvailability();
}
function orchestrationTableReview(event) {
  event.preventDefault();const state=orchestrationTableState;if(state.sending||state.loading)return;
  const {options,asset,second,method}=orchestrationTableSelection();if(!asset||!method)return;
  if(options.context.generation!==orchestrationState.run?.generation)return;
  orchestrationTableInvalidate();
  try{
    const request=JSON.parse(JSON.stringify(asset.projection_request));request.bindings.slot=method.slot;request.parameters={};
    for(const name of method.parameter_fields){
      if(name==='columns')request.parameters.columns=Array.from(orchestrationNode('table-parameters').querySelectorAll('input[name="table-columns"]:checked'),n=>n.value);
      else if(name==='row_ids'){const n=Number(orchestrationNode('table-param-row_ids').value);if(!Number.isInteger(n)||n<1||n>asset.row_ids.length)throw Error('抽出行数は保存表の行数以内で指定してください');request.parameters.row_ids=asset.row_ids.slice(0,n);}
      else request.parameters[name]=orchestrationNode(`table-param-${name}`).value;
    }
    if(request.parameters.columns?.length===0)throw Error('抽出する列を1つ以上選んでください');
    if(method.method_id==='table_join'){
      if(!second||second===asset)throw Error('結合する別の保存表を選んでください');
      if(second.scope.manifest_hash!==asset.scope.manifest_hash)throw Error('対象集合の同じ保存表を選んでください');
      request.bindings.inputs=[request.bindings.inputs[0],JSON.parse(JSON.stringify(second.projection_request.bindings.inputs[0]))];
      request.bindings.inputs.forEach((binding,index)=>{binding.input_ref_id=`table-input-${index}`;});
    }
    if(new Blob([JSON.stringify(request)]).size>options.max_bytes)throw Error('選択内容が上限を超えています。抽出する列・行を減らしてください');
    state.reviewed={request,method:method.method_id,epoch:orchestrationState.epoch};
    const params=Object.entries(request.parameters).map(([k,v])=>`${orchestrationTableFieldNames[k]||({columns:'抽出列',row_ids:'抽出行'}[k])}: ${k==='row_ids'?`${v.length}行`:Array.isArray(v)?v.join(' / '):({count:'件数',sum:'合計',mean:'平均',min:'最小',max:'最大',utterance:'発話'}[v]||v)}`).join(' · ');
    orchestrationText('table-summary',`${orchestrationTableNames[method.method_id]} · ${method.method_id==='table_join'?'保存表2件':'保存表1件'} · ${params}。固定入力版 ${options.input.source_revision}、対象 ${asset.scope.member_ids.length}発話。実行結果は研究者の採用・確定解釈とは別です。`);
    orchestrationNode('table-confirmation').hidden=false;orchestrationText('table-message','内容を確認し、実行ボタンを押してください。');orchestrationTableAvailability();
  }catch(error){orchestrationTableError(error);}
}
async function orchestrationTableExecute() {
  const state=orchestrationTableState,reviewed=state.reviewed;if(!reviewed||state.sending||reviewed.epoch!==orchestrationState.epoch)return;
  state.sending=true;orchestrationTableAvailability();const epoch=orchestrationState.epoch,viewer=orchestrationState.viewerEpoch;
  try{
    const data=await orchestrationTableJson(`${orchestrationBase()}/table-pilot/${encodeURIComponent(reviewed.method)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(reviewed.request)});
    if(epoch!==orchestrationState.epoch||viewer!==orchestrationState.viewerEpoch||!orchestrationNode('live').open)return;
    orchestrationTableInvalidate();orchestrationText('table-message',data.task.registration_duplicate?'同じ内容は受付済みです。状態・保存結果を確認してください。':'表処理を受け付けました。処理中・失敗・保存済み結果はタスク台帳で確認できます。');
    pollAnalysisOrchestration();
  }catch(error){if(epoch===orchestrationState.epoch&&viewer===orchestrationState.viewerEpoch&&orchestrationNode('live').open){orchestrationTableInvalidate();orchestrationTableError(error);}}
  finally{if(epoch===orchestrationState.epoch){state.sending=false;orchestrationTableAvailability();}}
}
function orchestrationTableResult(host,raw) {
  if(['qualitative_compare','qualitative_reuse'].includes(raw?.method_id))return orchestrationQualitativeResult(host,raw);
  const title=orchestrationTableNames[raw?.method_id]||orchestrationConnectedNames[raw?.method_id];
  if(!title||!raw.datasets?.table)return false;
  const table=raw.datasets.table,p=raw.population||{},m=raw.manifest||{};
  if(!Array.isArray(table.fields)||!Array.isArray(table.rows)||!table.fields.every(field=>typeof field==='string'))return false;
  host.append(orchestrationElement('h4',title),orchestrationElement('p',`対象の分母 ${p.denominator??m.included_denominator??'未取得'} · 計算の分母 ${p.calculation_denominator??m.calculation_denominator??'未取得'} · 欠測 ${p.missing_ids?.length??'未取得'} · 未処理 ${p.unprocessed_ids?.length??'未取得'} · 不明 ${p.unknown_ids?.length??'未取得'} · 除外 ${p.excluded_ids?.length??'未取得'} · 観測ゼロ ${p.observed_zero_ids?.length??'未取得'}`));
  const wrap=orchestrationElement('div',undefined,'orchestration-table-wrap');wrap.tabIndex=0;wrap.setAttribute('aria-label','保存された固定表（左右にスクロールできます）');
  const grid=orchestrationElement('table'),head=orchestrationElement('thead'),header=orchestrationElement('tr');
  for(const f of table.fields){const th=orchestrationElement('th',f);th.scope='col';header.append(th);}head.append(header);grid.append(head);
  const body=orchestrationElement('tbody');for(const row of table.rows){const tr=orchestrationElement('tr');for(const f of table.fields){
    const value=row[f],category=['category','row_value','column_value'].includes(f)&&['table_frequency','table_crosstab'].includes(raw.method_id);
    const text=value===undefined?'未取得':value===null?'null（保存値）':category?`${typeof value==='string'?`「${value}」`:String(value)}（${{string:'文字列',number:'数値',boolean:'真偽'}[typeof value]||'型未取得'}）`:f==='value_status'?({observed:'観測済み',missing:'欠測',unprocessed:'未処理',excluded:'除外',unknown:'不明'}[value]||String(value)):Array.isArray(value)?value.join(' / '):String(value);
    tr.append(orchestrationElement('td',text));}body.append(tr);}grid.append(body);wrap.append(grid);host.append(wrap,orchestrationElement('p','列が多い表は左右にスクロールできます。キーボードでは表に移動し、左右の矢印キーで列を確認できます。','field-note'));
  const evidence=orchestrationElement('button','固定入力・発話の根拠を履歴ビューアーで読む','secondary-button');evidence.type='button';evidence.addEventListener('click',()=>orchestrationNode('viewer').click());host.append(evidence);
  if(raw.unit_contract){
    const units={utterance:'発話',conversation_speaker:'会話内の話者',participant:'参加者',conversation:'会話'};
    host.append(orchestrationElement('p',`保存された分析単位：${units[raw.unit_contract.unit]||'未対応・未取得'}。探索的な構造計算であり、測定の妥当性・独立性・確定解釈の認定とは別です。`));
    const denominators=raw.unit_contract.denominators;
    if(denominators&&typeof denominators==='object'){
      const details=orchestrationElement('details'),summary=orchestrationElement('summary','保存された単位別の分母・欠測と出典');details.append(summary);
      for(const [unit,counts] of Object.entries(denominators)){
        if(!counts||typeof counts!=='object')continue;
        details.append(orchestrationElement('p',`${unit}：対象 ${counts.included??'未取得'} · 観測 ${counts.observed??'未取得'} · 欠測 ${counts.missing??'未取得'} · 未処理 ${counts.unprocessed??'未取得'} · 不明 ${counts.unknown??'未取得'} · 除外 ${counts.excluded??'未取得'} · 固定発話 ${(raw.unit_contract.sources?.[unit]||[]).join(' / ')||'未取得'}`));
      }host.append(details);
    }
    for(const limitation of raw.limitations||[])host.append(orchestrationElement('p',limitation,'field-note'));
  }
  host.append(orchestrationElement('p','空セルをゼロとは扱いません。表の値・対象集合・計算対象はこの保存結果の固定版です。研究者による採否は別に確認してください。','field-note'));return true;
}
function orchestrationQualitativeResult(host,raw) {
  const names={support:'支持',counter:'反例',complement:'補完',conflict:'競合',incomparable:'比較できない'},roles={data_input:'分析入力',selection_basis:'選択の根拠',evidence_context:'根拠の文脈'};
  try{
    const text=raw.datasets?.table?.rows?.[0]?.bundle_json;
    if(raw.datasets?.table?.rows?.length!==1||raw.datasets.table.fields?.length!==1||raw.datasets.table.fields[0]!=='bundle_json'||typeof text!=='string'||new Blob([text]).size>65536)throw Error();
    const bundle=JSON.parse(text),expectedStage=raw.method_id==='qualitative_compare'?'B1_comparison':'A2_rereading';
    if(bundle.version!=='qualitative-evidence-1'||bundle.stage!==expectedStage||bundle.human_status!=='human_pending'||bundle.independent_validation!==false||bundle.same_parent_evidence!==true||
      !Array.isArray(bundle.inputs)||bundle.inputs.length>32||!Array.isArray(bundle.relations)||bundle.relations.length>64||!Array.isArray(bundle.omitted_inputs)||bundle.omitted_inputs.length>32||
      !bundle.relations.every(relation=>Object.hasOwn(names,relation.relation)&&typeof relation.reason==='string'&&relation.left&&relation.right&&relation.semantic_status==='human_pending'))throw Error();
    host.append(orchestrationElement('h4',raw.method_id==='qualitative_compare'?'固定根拠の質的比較':'同じ親根拠を用いた再読'),orchestrationElement('p','作成時の採否：研究者記録待ち。関係は確認前の申告・提案です。保存済みの研究者記録は別に確認してください。'),orchestrationElement('p','同じ親の根拠を参照します。別の再分析タスクや予算による独立検証を行った結果ではありません。','field-note'));
    const wrap=orchestrationElement('div',undefined,'orchestration-table-wrap');wrap.tabIndex=0;wrap.setAttribute('aria-label','保存された質的比較の関係と理由');
    const table=orchestrationElement('table'),head=orchestrationElement('thead'),row=orchestrationElement('tr');
    for(const title of ['左の対象','右の対象','関係の申告','明示された理由']){const th=orchestrationElement('th',title);th.scope='col';row.append(th);}head.append(row);table.append(head);
    const body=orchestrationElement('tbody'),target=value=>value.label||value.target_id||value.input_ref_id||'対象名未取得';
    for(const relation of bundle.relations){const tr=orchestrationElement('tr');for(const value of [target(relation.left),target(relation.right),names[relation.relation],relation.reason])tr.append(orchestrationElement('td',value));body.append(tr);}table.append(body);wrap.append(table);host.append(wrap);
    if(!bundle.relations.length)host.append(orchestrationElement('p','関係の申告なし（保存値）。支持や一致を推定しません。'));
    const refs=orchestrationElement('details');refs.append(orchestrationElement('summary','保存された参照の役割・省略'));
    for(const input of bundle.inputs)refs.append(orchestrationElement('p',`${roles[input.role]||'未対応の役割'} · ${input.input_ref_id||'参照名未取得'} · 固定資産の種類：${input.kind||'未取得'}`));
    for(const omitted of bundle.omitted_inputs)refs.append(orchestrationElement('p',`省略した参照：${omitted.input_ref_id||'未取得'} · 理由：${omitted.omission_reason||'未取得'}`));host.append(refs);
    const evidence=orchestrationElement('button','固定入力と根拠を履歴ビューアーで読む','secondary-button');evidence.type='button';evidence.addEventListener('click',()=>orchestrationNode('viewer').click());host.append(evidence);
    for(const limitation of bundle.limitations||[])host.append(orchestrationElement('p',limitation,'field-note'));
  }catch(_){host.replaceChildren(orchestrationElement('p','保存された質的比較の形式・状態を確認できません。元の保存版を再取得してください。'));}
  return true;
}
// Researcher drafts stay in memory only. GET supplies immutable targets and
// revision context; neither viewing nor polling records a human decision.
const orchestrationHumanState={runKey:'',options:null,selection:null,drafts:new Map(),loading:false,sending:false,request:0};
const orchestrationHumanDecision={adopt:'採用',reject:'不採用',defer:'保留'};
const orchestrationHumanFields=['actor','source','decision','reason'];
const orchestrationHumanTargetNames={candidate:'候補全体',theme:'テーマ',relation_graph:'関係グラフ',qualitative_bundle:'質的比較・再利用の結果',participant_mapping:'参加者対応を記録する固定単位表'};
const orchestrationHumanRequiredSteps={candidate:['ta-p1','ta-p4','ta-p5','ta-p6'],theme:['ta-p1','ta-p4','ta-p5','ta-p6'],relation_graph:['manual-interaction-review'],qualitative_bundle:['qualitative-interpretation-review'],participant_mapping:['participant-mapping-review']};
const orchestrationHumanCopy=value=>JSON.parse(JSON.stringify(value));
const orchestrationHumanAssetKey=option=>JSON.stringify(option.asset_key);
const orchestrationHumanTargetKey=option=>`${orchestrationHumanAssetKey(option)}:${option.target.domain}:${option.target.content_hash}:${option.target.version}`;
function orchestrationHumanDraftKey(selection=orchestrationHumanState.selection) {
  return selection?`${orchestrationHumanState.runKey}:${orchestrationHumanTargetKey(selection.option)}:${selection.step?.step_id||''}`:'';
}
function orchestrationHumanDraft() { return orchestrationHumanState.drafts.get(orchestrationHumanDraftKey()); }
function orchestrationHumanCapture() {
  const draft=orchestrationHumanDraft();if(!draft)return;
  for(const id of orchestrationHumanFields)draft[id]=orchestrationNode(`human-${id}`).value;
}
function orchestrationHumanMessage(text,error=false,focus=false) {
  const node=orchestrationNode('human-message');node.textContent=text;node.dataset.error=String(error);
  if(focus)node.focus();
}
function orchestrationHumanReason(code) {
  return ({human_run_cancelled:'この実行は停止されています。',human_producer_stale:'保存候補の作成条件が現在の実行と一致しません。',
    permission_revoked:'利用許可が失効しています。',parent_permission_revoked:'元資料の利用許可が失効しています。',
    producer_unavailable:'候補を作成した実行を確認できません。',human_state_unavailable:'保存候補の利用状態が失効・停止しています。',revision_conflict:'保存版が更新されています。',
    human_pending:'独立した研究者記録がまだ揃っていません。',no_thematic_candidates:'保存済みテーマ候補はありません。'})[code]||'現在の保存状態・利用条件では記録できません。再取得して確認してください。';
}
function orchestrationHumanAvailability() {
  const state=orchestrationHumanState,key=`${orchestrationState.itemId}:${orchestrationState.runId}`;
  if(state.runKey!==key) {
    orchestrationHumanCapture();state.runKey=key;state.options=null;state.selection=null;state.loading=false;++state.request;
    orchestrationNode('human-form').hidden=true;orchestrationNode('human-next').hidden=true;
    orchestrationNode('human-confirmation').hidden=true;orchestrationHumanMessage('');
  }
  const run=orchestrationState.run,option=state.selection?.option,draft=orchestrationHumanDraft();
  const stale=state.options?.generation!==null&&state.options?.generation!==undefined&&state.options.generation!==run?.generation;
  const unavailable=option&&state.options&&!state.options.options.some(current=>orchestrationHumanTargetKey(current)===orchestrationHumanTargetKey(option));
  const blocked=!run||!['accepted','queued','running','completed','succeeded','idle','paused'].includes(run.status)||run.stale||run.cancel_requested||stale;
  const ready=!blocked&&!unavailable&&state.options?.enabled===true&&option?.enabled===true&&Boolean(state.selection?.step);
  orchestrationText('human-availability',!run?'保存済み実行を選んでください。':blocked?'実行の停止・入力変更・未対応状態を検出しました。記録内容を保持し、保存対象を再取得してください。':state.options?.enabled===false?orchestrationHumanReason(state.options.reason_code):option?.enabled===false?orchestrationHumanReason(option.reason_code):option?.human_steps.length===1?'表示された一つの確認を、研究者自身の判断として記録します。表示の取得は判断を記録しません。':'TAの四つの段階をそれぞれ独立して記録します。表示の取得は判断を記録しません。');
  for(const id of ['load','next'])orchestrationNode(`human-${id}`).disabled=!run||state.loading||state.sending||Boolean(draft?.uncertain);
  orchestrationNode('human-evidence').disabled=!run;
  orchestrationNode('human-review').disabled=!ready||state.loading||state.sending||Boolean(draft?.uncertain)||Boolean(draft?.refreshRequired);
  orchestrationNode('human-save').disabled=!ready||state.loading||state.sending||!draft?.payload;
  for(const id of ['asset','target','step','author-confirm',...orchestrationHumanFields])orchestrationNode(`human-${id}`).disabled=state.sending||Boolean(draft?.uncertain);
  if(unavailable)for(const id of ['asset','target','step'])orchestrationNode(`human-${id}`).disabled=true;
  if(blocked)orchestrationNode('human-confirmation').hidden=true;
}
function orchestrationHumanOptionsValid(data) {
  const integer=value=>Number.isSafeInteger(value)&&value>=0, hash=value=>typeof value==='string'&&/^sha256:[0-9a-f]{64}$/.test(value);
  const targetValid=option=>{
    const target=option.target,kind=option.target_kind,steps=orchestrationHumanRequiredSteps[kind];
    if(!Object.hasOwn(orchestrationHumanRequiredSteps,kind)||!steps||!target||!integer(target.version)||target.version<1||!hash(target.content_hash))return false;
    if(['candidate','theme'].includes(kind))return target.domain===(kind==='candidate'?'ta-candidate-content-v1':'ta-theme-content-v1');
    const keys=['domain','library_id','store_run_id','artifact_id','output_name','version','content_hash'];
    return target.domain==='raw-bytes-v1'&&target.version===1&&Object.keys(target).length===keys.length&&keys.every(key=>Object.hasOwn(target,key))&&
      ['library_id','store_run_id','artifact_id','output_name'].every(key=>typeof target[key]==='string'&&target[key]===option.asset_key[key]);
  };
  return data?.schema_id==='gurumoji.human-record-options'&&data.schema_version===1&&data.item_id===orchestrationState.itemId&&data.run_id===orchestrationState.runId&&
    (data.generation===null||integer(data.generation))&&typeof data.enabled==='boolean'&&(!data.enabled||integer(data.generation))&&integer(data.offset)&&data.offset<=10000&&data.limit===20&&
    (data.next_offset===null||integer(data.next_offset)&&data.next_offset<=10000)&&Array.isArray(data.options)&&data.options.length<=20&&data.options.every(option=>
      option.asset_key&&typeof option.library_id==='string'&&option.asset_key.library_id===option.library_id&&option.scope&&
      typeof option.label==='string'&&targetValid(option)&&
      integer(option.expected_state_revision)&&typeof option.enabled==='boolean'&&Array.isArray(option.human_steps)&&option.human_steps.length===orchestrationHumanRequiredSteps[option.target_kind].length&&
      new Set(option.human_steps.map(step=>step.step_id)).size===option.human_steps.length&&option.human_steps.every(step=>orchestrationHumanRequiredSteps[option.target_kind].includes(step.step_id)&&typeof step.label==='string'&&integer(step.next_revision)&&step.next_revision>=1&&
        (step.latest_record===null?step.next_revision===1&&step.next_supersedes_record_ref===null:
          step.latest_record?.record?.actor?.kind==='researcher'&&typeof step.latest_record.record.actor.actor_id==='string'&&
          Boolean(orchestrationHumanDecision[step.latest_record.record.decision])&&hash(step.latest_record.record_ref?.content_hash)&&
          step.next_revision===step.latest_record.record.revision+1&&step.next_supersedes_record_ref?.content_hash===step.latest_record.record_ref.content_hash)));
}
async function orchestrationHumanJson(url,options={}) {
  const response=await apiFetch(url,options),data=await readJsonResponse(response);
  if(!response.ok){const error=Error(data.error||`HTTP ${response.status}`);Object.assign(error,{field:data.field,code:data.reason_code,status:response.status});throw error;}
  return {data,status:response.status};
}
async function orchestrationHumanLoad(offset=0,preserve=Boolean(orchestrationHumanState.selection)) {
  const state=orchestrationHumanState;if(state.loading||state.sending||orchestrationHumanDraft()?.uncertain)return;
  orchestrationHumanCapture();const previous=state.selection,request=++state.request,epoch=orchestrationState.epoch,viewer=orchestrationState.viewerEpoch;
  const oldKey=previous&&orchestrationHumanTargetKey(previous.option),oldStep=previous?.step?.step_id;
  state.loading=true;state.options=null;orchestrationNode('human-confirmation').hidden=true;orchestrationHumanAvailability();
  const current=()=>request===state.request&&epoch===orchestrationState.epoch&&viewer===orchestrationState.viewerEpoch&&orchestrationNode('live').open;
  try {
    const {data:received}=await orchestrationHumanJson(`${orchestrationBase()}/human-records?offset=${offset}`);
    if(!current())return;
    if(!orchestrationHumanOptionsValid(received))throw Error('研究者記録の読取形式・対象・改訂情報を確認できません。未対応の応答です。');
    // Participant identities require the separate structured assignment form;
    // the ordinary narrative memo must never become a mapping implicitly.
    const data={...received,options:received.options.filter(option=>option.target_kind!=='participant_mapping')};
    state.options=data;
    const retained=preserve&&data.options.find(option=>orchestrationHumanTargetKey(option)===oldKey);
    if(preserve&&previous&&!retained) {
      const draft=orchestrationHumanDraft();if(draft){draft.refreshRequired=true;draft.payload=null;}
      orchestrationNode('human-form').hidden=false;
      orchestrationHumanMessage('元の対象版が現在の選択肢にありません。原文メモは元の対象に保持しました。別の候補へ転用せず、対象を確認してください。',true,true);return;
    }
    const assets=[...data.options.reduce((map,option)=>{const key=orchestrationHumanAssetKey(option);if(!map.has(key)||option.target_kind==='candidate')map.set(key,option);return map;},new Map()).values()];
    orchestrationNode('human-asset').replaceChildren(...assets.map((option,index)=>{const node=orchestrationElement('option',`保存対象 ${data.offset+index+1} · ${option.label}`);node.value=orchestrationHumanAssetKey(option);return node;}));
    orchestrationNode('human-next').hidden=data.next_offset===null;
    if(retained)orchestrationNode('human-asset').value=orchestrationHumanAssetKey(retained);
    state.selection=null;orchestrationNode('human-form').hidden=!data.options.length;
    if(data.options.length)orchestrationHumanSelect('asset',retained,oldStep,preserve);
    if(!preserve)orchestrationHumanMessage(data.options.length?'対象と一つの段階を選び、研究者本人の記録を入力してください。':received.options.length?'参加者対応は「保存した根拠をつなぎ、局所分析」の対応表で記録してください。':'この実行に記録可能な保存候補はありません。');
    const draft=orchestrationHumanDraft();if(draft){draft.refreshRequired=false;draft.payload=null;}
  } catch(error) {
    if(current()){orchestrationNode('human-form').hidden=!state.selection;orchestrationHumanMessage(`保存候補の取得: ${error.message}。入力メモは保持しています。`,true);}
  } finally {if(request===state.request){state.loading=false;orchestrationHumanAvailability();}}
}
function orchestrationHumanSelect(kind,retained=null,oldStep=null,preserveMessage=false) {
  const state=orchestrationHumanState;orchestrationHumanCapture();
  if(kind==='asset') {
    const choices=state.options?.options.filter(option=>orchestrationHumanAssetKey(option)===orchestrationNode('human-asset').value)||[];
    orchestrationNode('human-target').replaceChildren(...choices.map(option=>{const node=orchestrationElement('option',`${orchestrationHumanTargetNames[option.target_kind]} · ${option.label} · 版 ${option.target.version}`);node.value=orchestrationHumanTargetKey(option);return node;}));
    if(retained)orchestrationNode('human-target').value=orchestrationHumanTargetKey(retained);
  }
  const option=state.options?.options.find(option=>orchestrationHumanTargetKey(option)===orchestrationNode('human-target').value);
  if(!option){state.selection=null;orchestrationHumanAvailability();return;}
  if(kind!=='step') {
    const placeholder=orchestrationElement('option','今回記録する一つの段階を選択');placeholder.value='';
    orchestrationNode('human-step').replaceChildren(placeholder,...option.human_steps.map(step=>{const node=orchestrationElement('option',step.label);node.value=step.step_id;return node;}));
    if(oldStep)orchestrationNode('human-step').value=oldStep;
  }
  const step=option.human_steps.find(step=>step.step_id===orchestrationNode('human-step').value);state.selection={option,step};
  const key=orchestrationHumanDraftKey();
  if(!state.drafts.has(key))state.drafts.set(key,{actor:step?.latest_record?.record.actor.actor_id||'',source:'',reason:'',decision:'',payload:null,uncertain:false,refreshRequired:false});
  const draft=orchestrationHumanDraft();
  for(const id of orchestrationHumanFields){const node=orchestrationNode(`human-${id}`);node.value=draft[id];node.removeAttribute('aria-invalid');}
  if(step?.latest_record)orchestrationNode('human-actor').value=draft.actor=step.latest_record.record.actor.actor_id;
  orchestrationNode('human-actor').readOnly=Boolean(step?.latest_record);
  orchestrationNode('human-author-field').hidden=!step?.latest_record;
  orchestrationNode('human-author-confirm').required=Boolean(step?.latest_record);
  orchestrationNode('human-author-confirm').checked=false;
  const scope=option.scope;
  orchestrationText('human-scope',`対象版 ${option.target.version} · 対象発話 ${scope.member_ids?.length??'未取得'}件 · 除外 ${scope.excluded_ids?.length??'未取得'}件 · ローカル保存。対象集合は保存版に固定されています。${option.target_kind==='theme'?'このテーマの判断は、候補全体の採用とは別です。':''}`);
  orchestrationNode('human-stages').replaceChildren(...option.human_steps.map(entry=>orchestrationElement('li',`${entry.label}：${entry.latest_record?`${orchestrationHumanDecision[entry.latest_record.record.decision]}を記録済み（第${entry.latest_record.record.revision}版）`:'研究者記録なし'}`)));
  orchestrationText('human-existing',step?.latest_record?`既存記録の訂正（第${step.next_revision}版）です。記録者・対象・段階は引き継ぎます。前の理由：${step.latest_record.record.reason}`:step?'この段階の新しい研究者記録です。':option.human_steps.length===4?'四つの段階を一度に確認済みにする操作はありません。':'表示された確認段階を選び、対象の保存版と原文を確認して判断してください。');
  orchestrationNode('human-confirmation').hidden=!draft.uncertain;
  if(!option.enabled&&!preserveMessage)orchestrationHumanMessage(`${orchestrationHumanReason(option.reason_code)} 入力メモは元の対象に保持しています。`,true);
  orchestrationHumanAvailability();
}
function orchestrationHumanEdit(event) {
  if(![...orchestrationHumanFields,'author-confirm'].some(id=>event.target===orchestrationNode(`human-${id}`)))return;
  event.target.removeAttribute('aria-invalid');
  orchestrationHumanCapture();const draft=orchestrationHumanDraft();if(!draft)return;
  draft.payload=null;orchestrationNode('human-confirmation').hidden=true;orchestrationHumanAvailability();
}
function orchestrationHumanError(error) {
  const id=error.field==='source_text'?'source':error.field==='expected_state_revision'?'asset':
    error.code?.includes('actor')?'actor':error.code?.includes('source')?'source':error.code?.includes('step')?'step':error.code?.includes('target')?'target':'asset';
  const node=orchestrationNode(`human-${id}`);node.setAttribute('aria-invalid','true');node.setAttribute('aria-describedby','orchestration-human-message');
  orchestrationHumanMessage(`研究者記録の保存: ${error.message}。原文メモと判断は保持しています。`,true);node.focus();
}
async function orchestrationHumanReview(event) {
  event.preventDefault();orchestrationHumanAvailability();if(orchestrationNode('human-review').disabled)return;
  const form=orchestrationNode('human-form');if(!form.reportValidity())return;
  orchestrationHumanCapture();const state=orchestrationHumanState,{option,step}=state.selection,draft=orchestrationHumanDraft(),key=orchestrationHumanDraftKey(),epoch=orchestrationState.epoch;
  if(!draft.actor.trim()||!draft.source.trim()||!draft.reason.trim()||!orchestrationHumanDecision[draft.decision]){orchestrationHumanMessage('記録者・原文メモ・判断・理由をそれぞれ入力してください。',true);return;}
  state.sending=true;orchestrationHumanAvailability();
  try {
    const bytes=new TextEncoder().encode(draft.source),digest=await crypto.subtle.digest('SHA-256',bytes);
    if(epoch!==orchestrationState.epoch||key!==orchestrationHumanDraftKey())return;
    const recordId=step.latest_record?.record.record_id||`researcher-${crypto.randomUUID()}`;
    const record={record_id:recordId,revision:step.next_revision,supersedes_record_ref:orchestrationHumanCopy(step.next_supersedes_record_ref),
      actor:step.latest_record?orchestrationHumanCopy(step.latest_record.record.actor):{kind:'researcher',actor_id:draft.actor.trim()},decision:draft.decision,
      target:orchestrationHumanCopy(option.target),allowed_step_ids:[step.step_id],scope:orchestrationHumanCopy(option.scope),recorded_at:new Date().toISOString(),reason:draft.reason,
      record_ref:{target_type:'researcher_memo',target_id:`human-source:${recordId}`,version:String(step.next_revision),content_hash:`sha256:${Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('')}`,hash_domain:'raw-bytes-v1',library_id:option.library_id}};
    const payload={asset_key:orchestrationHumanCopy(option.asset_key),record,source_text:draft.source,expected_state_revision:option.expected_state_revision};
    if(new TextEncoder().encode(JSON.stringify(payload)).length>65536)throw Error('記録が保存上限を超えています。原文メモ・理由を短くしてください。');
    draft.payload=payload;
    orchestrationText('human-summary',`${orchestrationHumanTargetNames[option.target_kind]} · ${option.label} · 版 ${option.target.version}\n${step.label}\n記録者：${record.actor.actor_id}\n判断：${orchestrationHumanDecision[record.decision]}\n理由：${record.reason}\n原文メモ：\n${draft.source}\nこの一つの段階だけを、第${record.revision}版としてローカルに保存します。`);
    orchestrationNode('human-confirmation').hidden=false;orchestrationNode('human-save').textContent='確認した研究者記録を保存';
  }catch(error){orchestrationHumanMessage(`記録内容の確認: ${error.message}。メモは保持しています。`,true);}
  finally{state.sending=false;orchestrationHumanAvailability();if(draft.payload)orchestrationNode('human-save').focus();}
}
async function orchestrationHumanSave() {
  orchestrationHumanAvailability();const state=orchestrationHumanState,draft=orchestrationHumanDraft();if(state.sending||!draft?.payload||orchestrationNode('human-save').disabled)return;
  const payload=draft.payload,key=orchestrationHumanDraftKey(),epoch=orchestrationState.epoch,base=orchestrationBase();
  state.sending=true;orchestrationHumanAvailability();orchestrationHumanMessage('研究者の原文メモと、この段階の判断を保存しています…');
  let refresh=false;
  try {
    const {data,status}=await orchestrationHumanJson(`${base}/human-records`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(![200,201].includes(status)||data.record?.record_id!==payload.record.record_id||data.record?.revision!==payload.record.revision||typeof data.duplicate!=='boolean')throw Error('保存の応答を確認できません。');
    draft.payload=null;draft.uncertain=false;draft.refreshRequired=true;
    if(epoch!==orchestrationState.epoch||key!==orchestrationHumanDraftKey())return;
    orchestrationNode('human-confirmation').hidden=true;
    orchestrationHumanMessage(data.duplicate?'同じ研究者記録は保存済みです。重複して記録していません。':'この段階の研究者記録を保存しました。他の段階の判断は変更していません。',false,true);refresh=true;
  }catch(error) {
    if(error.status>=400&&error.status<500){draft.payload=null;draft.uncertain=false;draft.refreshRequired=true;refresh=true;}
    else {draft.uncertain=true;orchestrationNode('human-save').textContent='同じ記録の保存結果を確認・再送';}
    if(epoch===orchestrationState.epoch&&key===orchestrationHumanDraftKey()) {
      orchestrationHumanError(error);
      if(draft.uncertain)orchestrationHumanMessage(`保存結果を確認できません: ${error.message}。新しい記録を作らず、同じ内容で確認・再送できます。原文は保持しています。`,true,true);
      else orchestrationNode('human-confirmation').hidden=true;
    }
  }finally {
    state.sending=false;orchestrationHumanAvailability();
    if(refresh&&epoch===orchestrationState.epoch&&key===orchestrationHumanDraftKey())await orchestrationHumanLoad(state.options?.offset||0,true);
  }
}
// Connected execution uses only the bounded current Store catalogue. No
// scientific value, role eligibility, scope or future semantic target is made
// by the browser. Queued dependencies are execution requests, not saved data.
const orchestrationAssetState={options:null,steps:[],reviewed:null,loading:false,sending:false,uncertain:false,refreshRequired:false,request:0,runKey:'',choices:[]};
const orchestrationAssetParameterFields={theme_evidence_table:['theme_id'],unit_projection:['columns','unit_ids'],unit_aggregate:['value_column','operation','unit','participant_mapping'],unit_join:['keys'],unit_correlation:['x_column','y_column','statistic'],qualitative_compare:['proposals'],qualitative_reuse:['relation_ids']};
const orchestrationAssetRoleLabels={data_input:'処理の入力',selection_basis:'選択の根拠',evidence_context:'根拠の文脈'};
const orchestrationAssetMethodNames={...orchestrationConnectedNames,qualitative_compare:'固定根拠の質的比較',qualitative_reuse:'同じ親根拠を用いた再読'};
const orchestrationAssetValueNames={count:'件数',sum:'合計',mean:'平均',conversation_speaker:'会話内の話者',conversation:'会話',participant:'参加者',pearson:'Pearson（探索用）',spearman:'Spearman（探索用）',support:'支持',counter:'反例',complement:'補完',conflict:'競合',incomparable:'比較できない'};
const orchestrationAssetCopy=orchestrationHumanCopy;
const orchestrationAssetOmissions=()=>orchestrationAssetMethod()?.omission_reason_choices||[];
function orchestrationAssetInputName(input){const index=orchestrationAssetState.options?.inputs.findIndex(i=>i.option_id===input.option_id);return /(?:^|\/)\S+\.json$/.test(input.label)?`${{observation_table:'保存単位表',claim_set:'保存した解釈・主張',relation_graph:'保存した関係グラフ',snapshot:'固定した原文'}[input.kind]||'保存根拠'} ${index+1}`:input.label;}
function orchestrationAssetReset(){
  const state=orchestrationAssetState;++state.request;Object.assign(state,{options:null,steps:[],reviewed:null,loading:false,sending:false,uncertain:false,refreshRequired:false,choices:[]});
  orchestrationNode('asset-form').hidden=true;orchestrationNode('asset-next').hidden=true;orchestrationNode('asset-confirmation').hidden=true;orchestrationNode('asset-steps').replaceChildren();orchestrationText('asset-message','');
  orchestrationParticipantCapture();orchestrationParticipantState.context=null;orchestrationParticipantState.option=null;orchestrationParticipantState.key='';orchestrationNode('participant').hidden=true;
}
function orchestrationAssetInvalidate(){if(orchestrationAssetState.uncertain)return;orchestrationAssetState.reviewed=null;orchestrationNode('asset-confirmation').hidden=true;}
function orchestrationAssetReason(code){return ({human_pending:'必要な研究者記録がまだ揃っていません。',participant_mapping_missing:'参加者との対応を研究者が記録し、入力への接続を確認する必要があります。',permission_revoked:'利用許可が失効しています。',parent_permission_revoked:'元資料の利用許可が失効しています。',input_changed:'固定入力と現在の入力が一致しません。',run_stopped:'この実行は停止されています。',no_connected_inputs:'この実行には利用できる保存根拠がありません。',interface_draft_only:'この接続はまだ利用できません。'})[code]||'現在の保存状態・利用条件では使えません。状態を再取得して確認してください。';}
function orchestrationAssetAvailability(){
  const state=orchestrationAssetState,run=orchestrationState.run;
  const blocked=!run||!['accepted','queued','running'].includes(run.status)||run.stale||run.cancel_requested||state.options&&state.options.generation!==run.generation;
  const ready=!blocked&&state.options?.enabled===true&&!state.refreshRequired;
  orchestrationText('asset-availability',blocked?'現在の固定実行は追加処理を受け付けられません。停止・入力版・実行状態を確認してください。':state.options?.enabled===false?orchestrationAssetReason(state.options.reason_code):'処理は探索用です。研究者の判断・測定の妥当性・独立検証の認定とは別です。');
  for(const id of ['load','next'])orchestrationNode(`asset-${id}`).disabled=!run||state.loading||state.sending||state.uncertain||orchestrationParticipantState.sending||Boolean(orchestrationParticipantDraft()?.uncertain);
  orchestrationNode('asset-add').disabled=!ready||state.loading||state.sending||state.uncertain||state.steps.length>=32;
  orchestrationNode('asset-review').disabled=!ready||state.loading||state.sending||state.uncertain||!state.steps.length;
  orchestrationNode('asset-execute').disabled=!ready||state.loading||state.sending||!state.reviewed;
  orchestrationNode('asset-clear').disabled=state.loading||state.sending||state.uncertain;
  orchestrationNode('participant-prepare').disabled=!ready||state.loading||state.sending||state.uncertain;
  for(const node of orchestrationNode('asset-form').querySelectorAll('input,select,textarea'))node.disabled=state.sending||state.uncertain||node.dataset.fixed==='true';
  if(blocked)orchestrationNode('asset-confirmation').hidden=true;
}
function orchestrationAssetOptionsValid(data){
  const integer=value=>Number.isSafeInteger(value)&&value>=0,hash=value=>typeof value==='string'&&/^sha256:[0-9a-f]{64}$/.test(value);
  const strings=(values,max)=>Array.isArray(values)&&values.length<=max&&values.every(value=>typeof value==='string'&&value.length>0&&value.length<=1000)&&new Set(values).size===values.length;
  return data?.schema_id==='gurumoji.asset-plan-options'&&data.schema_version===1&&data.version==='asset-plan-options-1'&&data.item_id===orchestrationState.itemId&&data.run_id===orchestrationState.runId&&typeof data.library_id==='string'&&integer(data.generation)&&typeof data.enabled==='boolean'&&integer(data.offset)&&data.offset<=10000&&data.limit===20&&(data.next_offset===null||integer(data.next_offset)&&data.next_offset<=10000)&&
    data.plan_template?.version==='asset-plan-1'&&typeof data.plan_template.plan_id==='string'&&data.plan_template.plan_id.length>0&&integer(data.plan_template.plan_version)&&data.plan_template.plan_version>=1&&
    Array.isArray(data.methods)&&data.methods.length<=7&&new Set(data.methods.map(m=>m.method_id)).size===data.methods.length&&data.methods.every(m=>Object.hasOwn(orchestrationAssetParameterFields,m.method_id)&&strings(m.parameter_fields,8)&&m.parameter_fields.length===orchestrationAssetParameterFields[m.method_id].length&&m.parameter_fields.every(f=>orchestrationAssetParameterFields[m.method_id].includes(f))&&strings(m.roles,3)&&m.roles.length>0&&m.roles.every(r=>Object.hasOwn(orchestrationAssetRoleLabels,r))&&integer(m.min_inputs)&&integer(m.max_inputs)&&m.min_inputs>=1&&m.max_inputs<=32&&m.min_inputs<=m.max_inputs&&['observation_table','claim_set'].includes(m.output_kind)&&m.output_name==='tables/table.json'&&m.parameter_choices&&m.parameter_defaults)&&
    Array.isArray(data.inputs)&&data.inputs.length<=20&&new Set(data.inputs.map(i=>i.option_id)).size===data.inputs.length&&new Set(data.inputs.map(i=>i.input_ref_id)).size===data.inputs.length&&data.inputs.every(i=>typeof i.option_id==='string'&&typeof i.input_ref_id==='string'&&typeof i.label==='string'&&typeof i.enabled==='boolean'&&i.scope?.mode==='dataset'&&typeof i.scope.scope_id==='string'&&hash(i.scope.manifest_hash)&&i.source&&['frozen','original'].includes(i.source.type)&&
      (i.source.type==='frozen'?i.source.asset_key?.library_id===data.library_id&&hash(i.source.content_hash):i.source.source_ref?.library_id===data.library_id&&hash(i.source.source_ref.content_hash))&&strings(i.fields,128)&&strings(i.unit_ids,1024)&&strings(i.theme_ids,64)&&strings(i.relation_ids,64)&&strings(i.roles,3)&&i.roles.every(r=>Object.hasOwn(orchestrationAssetRoleLabels,r))&&Array.isArray(i.semantic_targets)&&i.semantic_targets.length<=128&&i.semantic_targets.every(t=>t.input_ref_id===i.input_ref_id&&typeof t.target_kind==='string'&&typeof t.target_id==='string'&&(integer(t.version)&&t.version>=1||typeof t.version==='string'&&t.version.length>0&&t.version.length<=1000)&&hash(t.content_hash))&&strings(i.compatible_methods,7)&&i.compatible_methods.every(m=>Object.hasOwn(orchestrationAssetParameterFields,m)));
}
async function orchestrationAssetLoad(offset=0){
  const state=orchestrationAssetState;if(state.loading||state.sending||state.uncertain||orchestrationParticipantState.sending||orchestrationParticipantDraft()?.uncertain)return;
  const request=++state.request,epoch=orchestrationState.epoch,viewer=orchestrationState.viewerEpoch;
  state.loading=true;state.options=null;orchestrationAssetInvalidate();orchestrationAssetAvailability();orchestrationParticipantAvailability();orchestrationText('asset-message','保存根拠と現在の利用条件を取得しています…');
  const current=()=>request===state.request&&epoch===orchestrationState.epoch&&viewer===orchestrationState.viewerEpoch&&orchestrationNode('live').open;
  try{
    const {data}=await orchestrationHumanJson(`${orchestrationBase()}/asset-plans/options?offset=${offset}`);if(!current())return;
    if(!orchestrationAssetOptionsValid(data))throw Error('未対応の選択情報・固定入力・対象集合です。');
    state.options=data;
    // A changed catalogue never silently rebinds an existing plan. Keep its
    // exact request for inspection and require explicit clearing/rebuilding.
    if(state.steps.length){state.refreshRequired=true;orchestrationText('asset-message','保存条件を再取得しました。元の計画を保持しています。対象を確認して計画を取り消し、改めて選択してください。');}
    else{state.refreshRequired=false;orchestrationText('asset-message',data.inputs.length?'処理と保存参照を選択してください。':'この実行に利用できる保存根拠はありません。');}
    orchestrationNode('asset-form').hidden=!data.inputs.length;orchestrationNode('asset-next').hidden=data.next_offset===null;
    orchestrationNode('asset-method').replaceChildren(...data.methods.map(m=>{const n=orchestrationElement('option',orchestrationAssetMethodNames[m.method_id]);n.value=m.method_id;return n;}));orchestrationAssetInputs();orchestrationParticipantRender();
  }catch(error){if(current()){state.refreshRequired=true;orchestrationNode('asset-form').hidden=true;orchestrationText('asset-message',`保存根拠の取得：${error.message}。未保存の計画は保持しています。`);}}
  finally{if(request===state.request){state.loading=false;orchestrationAssetAvailability();orchestrationParticipantAvailability();}}
}
function orchestrationAssetMethod(){return orchestrationAssetState.options?.methods.find(m=>m.method_id===orchestrationNode('asset-method').value);}
function orchestrationAssetInputs(){
  orchestrationAssetInvalidate();const state=orchestrationAssetState,m=orchestrationAssetMethod();if(!m)return;
  const host=orchestrationNode('asset-inputs');host.replaceChildren();state.choices=[];
  for(const input of state.options.inputs){state.choices.push({input,source:input.source});}
  for(const [index,step] of state.steps.entries()){
    const producer=state.options.methods.find(method=>method.method_id===step.method_id);
    // Only explicit server capability metadata can offer a not-yet-saved
    // dependency. Its values/semantic targets remain unavailable until saved.
    if(producer?.compatible_methods?.includes(m.method_id)&&Array.isArray(producer.output_fields)){
      const ready=producer.output_fields.length>0&&producer.output_reason_code!=='require_saved_output'&&['unit_aggregate','unit_join','qualitative_compare'].includes(m.method_id);
      state.choices.push({input:{option_id:step.step_id,input_ref_id:`dependency-${step.step_id}`,label:`計画の処理 ${index+1}：${orchestrationAssetMethodNames[step.method_id]}（保存待ち）`,enabled:ready,reason_code:ready?null:'require_saved_output',scope:step.scope,roles:['data_input'],compatible_methods:producer.compatible_methods,fields:producer.output_fields,unit_ids:[],theme_ids:[],relation_ids:[],semantic_targets:[],confirmed_participant_mapping:null},source:{type:'from_step',step_id:step.step_id,output_name:producer.output_name}});
    }
  }
  for(const [index,{input}] of state.choices.entries()){
    const row=orchestrationElement('div',undefined,'orchestration-asset-input'),label=orchestrationElement('label',undefined,'check-row'),check=orchestrationElement('input');check.type='checkbox';check.dataset.choice=String(index);check.id=`orchestration-asset-choice-${index}`;
    const compatible=input.enabled&&input.compatible_methods.includes(m.method_id);check.disabled=!compatible;check.dataset.fixed=String(!compatible);label.append(check,orchestrationElement('span',`${orchestrationAssetInputName(input)}${compatible?'':` · ${orchestrationAssetReason(input.reason_code)}`}`));row.append(label);
    const roleLabel=orchestrationElement('label',undefined,'field'),roleCaption=orchestrationElement('span','この参照の役割');roleCaption.id=`orchestration-asset-role-${index}-label`;roleLabel.append(roleCaption);const role=orchestrationElement('select');role.id=`orchestration-asset-role-${index}`;role.setAttribute('aria-labelledby',roleCaption.id);
    for(const value of input.roles.filter(r=>m.roles.includes(r))){const option=orchestrationElement('option',orchestrationAssetRoleLabels[value]);option.value=value;role.append(option);}roleLabel.append(role);row.append(roleLabel);host.append(row);
    if(['qualitative_compare','qualitative_reuse'].includes(m.method_id)&&Array.isArray(orchestrationAssetOmissions())&&orchestrationAssetOmissions().length){
      const omitLabel=orchestrationElement('label',undefined,'check-row'),omit=orchestrationElement('input');omit.type='checkbox';omit.dataset.omit=String(index);omitLabel.append(omit,orchestrationElement('span','この参照を処理せず、省略した理由を記録する'));row.append(omitLabel);
      const reasonLabel=orchestrationElement('label',undefined,'field'),reasonCaption=orchestrationElement('span','省略する理由');reasonCaption.id=`orchestration-asset-omit-${index}-label`;reasonLabel.append(reasonCaption);const reason=orchestrationElement('select');reason.id=`orchestration-asset-omit-${index}`;reason.setAttribute('aria-labelledby',reasonCaption.id);
      for(const choice of orchestrationAssetOmissions()){if(typeof choice.value!=='string'||typeof choice.label!=='string')continue;const option=orchestrationElement('option',choice.label);option.value=choice.value;reason.append(option);}reasonLabel.append(reason);row.append(reasonLabel);
      check.addEventListener('change',()=>{if(check.checked)omit.checked=false;});omit.addEventListener('change',()=>{if(omit.checked)check.checked=false;});
    }
  }
  orchestrationAssetParameters();
}
function orchestrationAssetSelected(){return Array.from(orchestrationNode('asset-inputs').querySelectorAll('input[data-choice]:checked,input[data-omit]:checked'),check=>{const index=check.dataset.choice??check.dataset.omit,choice=orchestrationAssetState.choices[Number(index)];return {...choice,role:orchestrationNode(`asset-role-${index}`).value,omitted:check.dataset.omit!==undefined,omission_reason:check.dataset.omit!==undefined?orchestrationNode(`asset-omit-${index}`).value:null};});}
function orchestrationAssetField(name,title,choices,multiple=false,fixed=[]){
  const host=orchestrationNode('asset-parameters'),label=orchestrationElement(multiple?'fieldset':'label',undefined,'field'),caption=orchestrationElement(multiple?'legend':'span',title);caption.id=`orchestration-asset-param-${name}-label`;label.append(caption);
  if(multiple){for(const [value,text] of choices){const row=orchestrationElement('label',undefined,'check-row'),n=orchestrationElement('input');n.type='checkbox';n.name=`asset-${name}`;n.value=value;n.checked=fixed.includes(value);n.dataset.fixed=String(fixed.includes(value));n.disabled=fixed.includes(value);row.append(n,orchestrationElement('span',text));label.append(row);}if(choices.length){const all=orchestrationElement('button','表示された選択肢をすべて選ぶ','secondary-button');all.type='button';all.addEventListener('click',()=>{for(const n of label.querySelectorAll('input'))n.checked=true;orchestrationAssetInvalidate();});label.append(all);}}
  else{const n=orchestrationElement('select');n.id=`orchestration-asset-param-${name}`;n.setAttribute('aria-labelledby',caption.id);for(const [value,text] of choices){const o=orchestrationElement('option',text);o.value=value;n.append(o);}const value=orchestrationAssetMethod()?.parameter_defaults[name];if(choices.some(choice=>choice[0]===value))n.value=value;label.append(n);}
  host.append(label);
}
function orchestrationAssetParameters(){
  orchestrationAssetInvalidate();const m=orchestrationAssetMethod(),selected=orchestrationAssetSelected().filter(s=>!s.omitted),first=selected[0]?.input,host=orchestrationNode('asset-parameters');host.replaceChildren();if(!m)return;
  orchestrationText('asset-scope',selected.map(({input,role})=>`${orchestrationAssetInputName(input)} · ${orchestrationAssetRoleLabels[role]} · 対象 ${input.scope.member_ids?.length??'未取得'}件 · 除外 ${input.scope.excluded_ids?.length??'未取得'}件 · 分析単位 ${{utterance:'発話',conversation_speaker:'会話内話者',conversation:'会話',participant:'参加者',report_claim:'探索結果',dataset_claim:'質的主張'}[input.unit]||'保存後に確認'}`).join(' / '));
  const field=(name,title,values,multiple=false,fixed=[])=>orchestrationAssetField(name,title,values.map(v=>[v,orchestrationAssetValueNames[v]||v]),multiple,fixed);
  for(const name of m.parameter_fields){
    if(name==='columns')field(name,'抽出する宣言済み列',first?.fields||[],true,['unit_id','conversation_id','value_status']);
    else if(name==='unit_ids')orchestrationAssetField(name,'抽出する保存単位',(first?.unit_ids||[]).map((id,index)=>[id,`保存単位 ${index+1}`]),true);
    else if(name==='keys')field(name,'両方の表に宣言された結合列',first?.fields.filter(f=>selected.every(({input})=>input.fields.includes(f)))||[],true,['unit_id']);
    else if(name==='theme_id')orchestrationAssetField(name,'記録されたテーマ',(first?.theme_ids||[]).map((id,index)=>[id,`保存テーマ ${index+1}`]));
    else if(['value_column','x_column','y_column'].includes(name))field(name,{value_column:'集約する宣言済み列',x_column:'比較する値の列（左）',y_column:'比較する値の列（右）'}[name],name==='value_column'?first?.aggregate_columns||first?.fields.filter(f=>!['unit_id','utterance_id','conversation_id','speaker_id','participant_id','value_status','source_utterance_ids','source_rows'].includes(f))||[]:first?.numeric_columns||[]);
    else if(['operation','unit','statistic'].includes(name))field(name,{operation:'集約方法',unit:'集約の単位',statistic:'探索的な相関の方法'}[name],m.parameter_choices[name]||[]);
    else if(name==='participant_mapping')host.append(orchestrationElement('p',first?.confirmed_participant_mapping?'この保存入力に結び付いた研究者の参加者対応記録を使います。':'参加者単位は、明示的な対応記録がこの保存入力に結び付いた後に利用できます。会話内話者・会話とは別です。','field-note'));
    else if(name==='relation_ids'){const basis=selected.filter(s=>s.role==='selection_basis');orchestrationAssetField(name,'選択の根拠に保存された関係',(basis.length===1?basis[0].input.relation_ids:[]).map((id,index)=>[id,`保存関係 ${index+1}`]),true);}
    else if(name==='proposals'){
      const targets=selected.flatMap(({input})=>input.semantic_targets.map((target,index)=>({target,label:`${orchestrationAssetInputName(input)} · ${{asset:'保存対象全体',theme:'テーマ',utterance:'発話',relation:'関係',row:'保存行'}[target.target_kind]||'保存された意味対象'} ${index+1} · ${typeof target.version==='number'?`版 ${target.version}`:'固定原文版'}` })));orchestrationAssetState.targets=targets;
      for(const side of ['left','right'])orchestrationAssetField(side,side==='left'?'比較する固定対象（左）':'比較する固定対象（右）',targets.map((entry,index)=>[String(index),entry.label]));
      field('relation','研究者が提案する関係',m.parameter_choices.relation||[]);
      for(const [id,title,tag,max] of [['actor','提案者の名前','input',200],['reason','この関係を提案する明示的な理由','textarea',2000]]){const label=orchestrationElement('label',undefined,'field');label.append(orchestrationElement('span',title));const n=orchestrationElement(tag);n.id=`orchestration-asset-param-${id}`;n.required=true;n.maxLength=max;if(tag==='textarea')n.rows=3;label.append(n);host.append(label);}
      host.append(orchestrationElement('p','これは研究者として明示した関係の提案です。原文に基づく採否は、保存後に別の研究者記録として確認します。','field-note'));
    }
  }
  if(m.method_id==='unit_aggregate'){
    orchestrationNode('asset-param-operation').addEventListener('change',()=>orchestrationAssetAggregateFields(first));orchestrationAssetAggregateFields(first);
  }
  orchestrationAssetAvailability();
}
function orchestrationAssetAggregateFields(input){
  const operation=orchestrationNode('asset-param-operation').value,node=orchestrationNode('asset-param-value_column'),previous=node.value;
  // Count may inspect any server-declared aggregate field. Sum/mean require
  // the saved input's explicit numeric metadata; a future value is unknown.
  const fields=operation==='count'?input?.aggregate_columns||input?.fields.filter(field=>!['unit_id','utterance_id','conversation_id','speaker_id','participant_id','value_status','source_utterance_ids','source_rows'].includes(field))||[]:input?.numeric_columns||[];
  node.replaceChildren(...fields.map(field=>{const option=orchestrationElement('option',field);option.value=field;return option;}));if(fields.includes(previous))node.value=previous;
  if(!fields.length){const option=orchestrationElement('option','この処理に使える宣言済み列は未取得です。保存後に再取得してください。');option.value='';node.append(option);}
  orchestrationAssetInvalidate();
}
function orchestrationAssetError(error){
  const field=error.field||'',leaf=field.split(/[.\[\]]/).filter(Boolean).at(-1),code=error.code||'';
  const id=field.includes('parameters')||orchestrationAssetMethod()?.parameter_fields.includes(leaf)||/parameter|proposal|participant_mapping/.test(code)?'asset-parameters':/input|scope|source|asset_key/.test(field)||/scope|input|permission/.test(code)?'asset-inputs':'asset-method';
  const target=orchestrationNode(id);target.setAttribute('aria-invalid','true');target.setAttribute('aria-describedby','orchestration-asset-message');target.tabIndex=-1;orchestrationText('asset-message',`${error.message}。計画と入力した理由は保持しています。`);target.focus();
}
function orchestrationAssetAdd(event){
  event.preventDefault();orchestrationAssetAvailability();if(orchestrationNode('asset-add').disabled||!orchestrationNode('asset-form').reportValidity())return;
  const state=orchestrationAssetState,m=orchestrationAssetMethod(),selected=orchestrationAssetSelected(),params={};
  try{
    if(selected.length<m.min_inputs||selected.length>m.max_inputs)throw Error(`保存参照を${m.min_inputs}〜${m.max_inputs}件選択してください。`);
    if(!selected.every(s=>s.input.roles.includes(s.role)&&m.roles.includes(s.role)&&(s.omitted?['qualitative_compare','qualitative_reuse'].includes(m.method_id)&&orchestrationAssetOmissions().some(c=>c.value===s.omission_reason):s.input.enabled&&s.input.compatible_methods.includes(m.method_id))))throw Error('利用可能な入力と役割を再確認してください。');
    const included=selected.filter(s=>!s.omitted),scope=included[0]?.input.scope;if(!scope)throw Error('処理する保存参照を選択してください。');if(!['qualitative_compare','qualitative_reuse'].includes(m.method_id)&&!included.every(s=>s.input.scope.scope_id===scope.scope_id&&s.input.scope.manifest_hash===scope.manifest_hash))throw Error('固定対象集合が異なります。未対応の集合を結合しません。');
    if(m.method_id==='unit_join'&&new Set(included.map(s=>JSON.stringify(s.source))).size!==included.length)throw Error('結合する異なる保存表を選択してください。');
    for(const name of m.parameter_fields){
      if(['columns','unit_ids','keys','relation_ids'].includes(name)){params[name]=Array.from(orchestrationNode('asset-parameters').querySelectorAll(`input[name="asset-${name}"]:checked`),n=>n.value);if(!params[name].length)throw Error('宣言された列・単位・関係を選択してください。');}
      else if(name==='participant_mapping'){
        params[name]=null;
        if(params.unit==='participant'){
          const mapping=included[0].input.confirmed_participant_mapping;
          if(!mapping||mapping.actor?.kind!=='researcher'||!mapping.record_ref||!Array.isArray(mapping.assignments))throw Error('参加者の対応記録がこの保存入力に結び付いていません。再取得して確認してください。');
          params[name]=orchestrationAssetCopy({actor:mapping.actor,record_ref:mapping.record_ref,assignments:mapping.assignments});
        }
      }
      else if(name==='proposals'){
        const left=state.targets[Number(orchestrationNode('asset-param-left').value)],right=state.targets[Number(orchestrationNode('asset-param-right').value)];
        if(!left||!right||left.target.input_ref_id===right.target.input_ref_id)throw Error('異なる保存参照の固定対象を二つ選択してください。未保存の意味対象は比較できません。');
        const actor=orchestrationNode('asset-param-actor').value.trim(),reason=orchestrationNode('asset-param-reason').value;if(!actor||!reason.trim())throw Error('提案者と関係の理由を入力してください。');
        const sid=`local-step-${state.steps.length+1}`;params[name]=[{relation_id:`relation-${state.steps.length+1}`,left:orchestrationAssetCopy(left.target),right:orchestrationAssetCopy(right.target),relation:orchestrationNode('asset-param-relation').value,reason,actor:{kind:'researcher',actor_id:actor,step_ids:[sid]}}];
      }else {params[name]=orchestrationNode(`asset-param-${name}`).value;if(!params[name])throw Error('宣言された必須項目を選択してください。');}
    }
    if(params.x_column&&params.x_column===params.y_column)throw Error('異なる二つの値の列を選択してください。');
    if(m.method_id==='unit_aggregate'&&['sum','mean'].includes(params.operation)&&!included[0].input.numeric_columns?.includes(params.value_column))throw Error('この保存入力の数値列を確認できません。保存後に根拠を再取得してください。');
    const step={step_id:`local-step-${state.steps.length+1}`,method_id:m.method_id,parameters:params,scope:{scope_id:scope.scope_id,manifest_hash:scope.manifest_hash},inputs:selected.map(s=>({input_ref_id:s.input.input_ref_id,role:s.role,selection:s.omitted?'omitted':'selected',omission_reason:s.omission_reason,...(s.omitted?{}:{source:orchestrationAssetCopy(s.source)})}))};
    const request={...state.options.plan_template,steps:[...state.steps,step]};if(new TextEncoder().encode(JSON.stringify(request)).length>65536)throw Error('選択内容が保存上限を超えています。');
    state.steps.push(step);orchestrationAssetInvalidate();orchestrationAssetRenderSteps();orchestrationAssetInputs();orchestrationText('asset-message','計画に追加しました。計画全体を確認してから実行してください。');
  }catch(error){orchestrationAssetError(error);}
}
function orchestrationAssetRenderSteps(){
  const state=orchestrationAssetState;
  orchestrationNode('asset-steps').replaceChildren(...state.steps.map((step,index)=>{
    const method=state.options?.methods.find(m=>m.method_id===step.method_id),labels={columns:'抽出列',keys:'結合列',x_column:'左の値',y_column:'右の値',statistic:'相関方法',...orchestrationTableFieldNames};
    const refs=step.inputs.map(ref=>{
      const input=state.options?.inputs.find(input=>input.input_ref_id===ref.input_ref_id),name=input?orchestrationAssetInputName(input):'固定された保存参照';
      if(ref.selection==='omitted')return `${name} · 省略：${method?.omission_reason_choices?.find(choice=>choice.value===ref.omission_reason)?.label||'保存された理由'}`;
      if(ref.source.type==='from_step')return `計画の処理 ${state.steps.findIndex(parent=>parent.step_id===ref.source.step_id)+1}の保存後に実行 · ${orchestrationAssetRoleLabels[ref.role]}`;
      return `${name} · ${orchestrationAssetRoleLabels[ref.role]}`;
    }).join(' / ');
    const parameters=Object.entries(step.parameters).filter(([name])=>!['participant_mapping','proposals','unit_ids','theme_id','relation_ids'].includes(name)).map(([name,value])=>`${labels[name]||name}：${Array.isArray(value)?value.join(' / '):orchestrationAssetValueNames[value]||value}`).join(' · ');
    const counts=`${step.parameters.unit_ids?` · ${step.parameters.unit_ids.length}保存単位`:''}${step.parameters.relation_ids?` · ${step.parameters.relation_ids.length}保存関係`:''}${step.parameters.theme_id?' · 選択した保存テーマ':''}`;
    const proposal=step.parameters.proposals?.[0];
    return orchestrationElement('li',`${index+1}. ${orchestrationAssetMethodNames[step.method_id]} · ${refs} · ${parameters}${counts}${proposal?` · 提案者 ${proposal.actor.actor_id} · ${orchestrationAssetValueNames[proposal.relation]}：${proposal.reason}`:''}`);
  }));
  for(const id of ['clear','review'])orchestrationNode(`asset-${id}`).hidden=!state.steps.length;orchestrationAssetAvailability();
}
function orchestrationAssetReview(){
  const state=orchestrationAssetState;orchestrationAssetAvailability();if(orchestrationNode('asset-review').disabled)return;
  state.reviewed={request:{...orchestrationAssetCopy(state.options.plan_template),steps:orchestrationAssetCopy(state.steps)},epoch:orchestrationState.epoch,viewer:orchestrationState.viewerEpoch};
  orchestrationText('asset-summary',`${state.steps.length}件の処理を、表示された役割・固定対象集合・依存順にローカルコードで実行します。この実行の進行状況と保存結果はタスク台帳で確認できます。探索結果は研究者の採用や独立検証とは別です。`);orchestrationNode('asset-confirmation').hidden=false;orchestrationAssetAvailability();orchestrationNode('asset-execute').focus();
}
async function orchestrationAssetExecute(){
  const state=orchestrationAssetState,r=state.reviewed;orchestrationAssetAvailability();if(!r||state.sending||orchestrationNode('asset-execute').disabled||r.epoch!==orchestrationState.epoch||r.viewer!==orchestrationState.viewerEpoch)return;
  state.sending=true;orchestrationAssetAvailability();const base=orchestrationBase();
  try{
    const {data,status}=await orchestrationHumanJson(`${base}/asset-plans`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(r.request)});
    if(![200,202].includes(status)||typeof data.duplicate!=='boolean'||!data.tasks||data.identity?.plan_id!==r.request.plan_id||data.identity.plan_version!==r.request.plan_version)throw Error('受付の結果を確認できません。');
    if(r.epoch!==orchestrationState.epoch)return;
    state.uncertain=false;state.refreshRequired=true;state.reviewed=null;orchestrationNode('asset-confirmation').hidden=true;
    orchestrationText('asset-message',data.duplicate?'同じ計画は受付済みです。重複して実行していません。保存結果を確認してください。':'計画を受け付けました。未処理・失敗・保存済み結果はタスク台帳で確認してください。');if(r.viewer===orchestrationState.viewerEpoch&&orchestrationNode('live').open)pollAnalysisOrchestration();
  }catch(error){
    if(r.epoch!==orchestrationState.epoch)return;
    if(error.status>=400&&error.status<500){state.reviewed=null;state.refreshRequired=true;state.uncertain=false;orchestrationNode('asset-confirmation').hidden=true;}
    else{state.uncertain=true;orchestrationNode('asset-execute').textContent='同じ計画の受付結果を確認・再送';}
    if(r.viewer===orchestrationState.viewerEpoch&&orchestrationNode('live').open)orchestrationAssetError(error);
  }finally{if(r.epoch===orchestrationState.epoch){state.sending=false;orchestrationAssetAvailability();}}
}
const orchestrationParticipantState={drafts:new Map(),key:'',option:null,context:null,sending:false,request:0};
function orchestrationParticipantDraft(){return orchestrationParticipantState.drafts.get(orchestrationParticipantState.key);}
function orchestrationParticipantCapture(){
  const draft=orchestrationParticipantDraft();if(!draft)return;
  for(const id of ['actor','reason','decision'])draft[id]=orchestrationNode(`participant-${id}`).value;
  draft.assignments=Array.from(orchestrationNode('participant-assignments').querySelectorAll('input'),input=>({conversation_id:input.dataset.conversation,speaker_id:input.dataset.speaker,participant_id:input.value}));
}
function orchestrationParticipantRender(){
  const state=orchestrationParticipantState;orchestrationParticipantCapture();const context=orchestrationAssetState.options?.participant_context,option=context?.human_record_option;
  const preparation=orchestrationAssetState.options?.inputs?.find(input=>input.option_id===context?.preparation_option_id&&input.input_ref_id===context?.preparation_input_ref_id&&input.enabled&&input.compatible_methods.includes('unit_projection'));
  const canPrepare=context?.reason_code==='require_saved_output'&&context.preparation_method==='unit_projection'&&preparation?.fields.length&&preparation.unit_ids.length;
  orchestrationNode('participant-prepare').hidden=!canPrepare;
  const valid=context&&option?.target_kind==='participant_mapping'&&option.owner_item_id===orchestrationState.itemId&&typeof option.owner_run_id==='string'&&option.owner_run_id.length>0&&Array.isArray(context.speakers)&&context.speakers.length>0&&context.speakers.length<=128&&
    new Set(context.speakers.map(s=>s.conversation_id)).size===1&&context.speakers.every(s=>Object.keys(s).length===2&&typeof s.conversation_id==='string'&&typeof s.speaker_id==='string')&&
    Array.isArray(context.known_participants)&&context.known_participants.length<=128&&context.known_participants.every(p=>Object.keys(p).length===1&&typeof p.participant_id==='string')&&
    orchestrationHumanOptionsValid({schema_id:'gurumoji.human-record-options',schema_version:1,item_id:orchestrationState.itemId,run_id:orchestrationState.runId,generation:orchestrationAssetState.options.generation,enabled:true,offset:0,limit:20,next_offset:null,options:[option]});
  state.context=valid?context:null;state.option=valid?option:null;orchestrationNode('participant').hidden=!context;
  if(!valid){orchestrationNode('participant-form').hidden=true;orchestrationText('participant-status',canPrepare?'対応を記録する保存済み単位表が必要です。元の表の宣言済み列と全保存単位をそのまま保存する処理を計画に追加し、確認して実行してください。':context?'対応を記録できる固定会話・話者・研究者対象を確認できません。自由記述から補いません。':'');return;}
  const key=`${orchestrationState.itemId}:${orchestrationState.runId}:${orchestrationHumanTargetKey(option)}`;state.key=key;
  const step=option.human_steps.find(step=>step.step_id==='participant-mapping-review');
  if(!state.drafts.has(key))state.drafts.set(key,{actor:step.latest_record?.record.actor.actor_id||'',reason:'',decision:'',assignments:context.speakers.map(s=>({...s,participant_id:context.confirmed_mapping?.assignments?.find(a=>a.conversation_id===s.conversation_id&&a.speaker_id===s.speaker_id)?.participant_id||''})),payload:null,uncertain:false,refreshRequired:false});
  const draft=orchestrationParticipantDraft();if(!draft.uncertain){draft.refreshRequired=false;draft.payload=null;}orchestrationNode('participant-form').hidden=false;
  orchestrationNode('participant-assignments').replaceChildren(...context.speakers.map(s=>{const label=orchestrationElement('label',undefined,'field');label.append(orchestrationElement('span',`会話 ${s.conversation_id} · 話者 ${s.speaker_id} に対応する参加者`));const input=orchestrationElement('input');input.required=true;input.maxLength=200;input.dataset.conversation=s.conversation_id;input.dataset.speaker=s.speaker_id;input.value=draft.assignments.find(a=>a.conversation_id===s.conversation_id&&a.speaker_id===s.speaker_id)?.participant_id||'';label.append(input);return label;}));
  for(const id of ['actor','reason','decision'])orchestrationNode(`participant-${id}`).value=draft[id];
  if(step.latest_record){draft.actor=step.latest_record.record.actor.actor_id;orchestrationNode('participant-actor').value=draft.actor;}
  orchestrationNode('participant-actor').readOnly=Boolean(step.latest_record);orchestrationNode('participant-author-field').hidden=!step.latest_record;orchestrationNode('participant-author').required=Boolean(step.latest_record);orchestrationNode('participant-author').checked=false;
  orchestrationText('participant-status',`対象版 ${option.target.version} · ${context.speakers.length}話者 · ${step.latest_record?`既存の対応記録を第${step.next_revision}版として訂正`:'参加者対応の独立した確認記録'}。${context.confirmed_mapping?'保存した対応あり。現在の入力への結び付きは保存根拠ごとに確認します。':'参加者対応は未確認です。'}`);
  orchestrationNode('participant-confirmation').hidden=!draft.uncertain;orchestrationParticipantAvailability();
}
function orchestrationAssetPrepareParticipant(){
  const state=orchestrationAssetState,context=state.options?.participant_context;
  orchestrationAssetAvailability();if(!context||context.preparation_method!=='unit_projection'||state.sending||state.loading||state.uncertain||state.refreshRequired||!state.options.enabled||state.options.generation!==orchestrationState.run?.generation)return;
  const index=state.options.inputs.findIndex(input=>input.option_id===context.preparation_option_id&&input.input_ref_id===context.preparation_input_ref_id&&input.enabled&&input.compatible_methods.includes('unit_projection'));if(index<0)return;
  orchestrationNode('asset-method').value='unit_projection';orchestrationAssetInputs();const choice=orchestrationNode(`asset-choice-${index}`);choice.checked=true;orchestrationAssetParameters();
  for(const input of orchestrationNode('asset-parameters').querySelectorAll('input[name="asset-columns"],input[name="asset-unit_ids"]'))input.checked=true;
  orchestrationAssetAdd({preventDefault(){}});orchestrationNode('asset-review').focus();
}
function orchestrationParticipantAvailability(){
  const state=orchestrationParticipantState,draft=orchestrationParticipantDraft(),run=orchestrationState.run;
  const ready=Boolean(state.option?.enabled&&orchestrationAssetState.options?.generation===run?.generation&&!run?.cancel_requested&&!run?.stale&&['accepted','queued','running','completed','succeeded','idle','paused'].includes(run?.status));
  orchestrationNode('participant-review').disabled=!ready||state.sending||Boolean(draft?.uncertain)||Boolean(draft?.refreshRequired);
  orchestrationNode('participant-save').disabled=!ready||state.sending||!draft?.payload;
  for(const n of orchestrationNode('participant-form').querySelectorAll('input,select,textarea'))n.disabled=state.sending||Boolean(draft?.uncertain);
  if(!ready)orchestrationNode('participant-confirmation').hidden=true;
}
function orchestrationParticipantEdit(){
  const draft=orchestrationParticipantDraft();if(!draft||draft.uncertain)return;orchestrationParticipantCapture();draft.payload=null;orchestrationNode('participant-confirmation').hidden=true;for(const node of orchestrationNode('participant-form').querySelectorAll('[aria-invalid]'))node.removeAttribute('aria-invalid');orchestrationParticipantAvailability();
}
function orchestrationParticipantError(error){
  const field=error.field||'',id=field.includes('actor')?'participant-actor':field.includes('decision')?'participant-decision':field.includes('reason')?'participant-reason':field.includes('source')||field.includes('assignment')?'participant-assignments':'participant-status';
  const node=orchestrationNode(id);node.setAttribute('aria-invalid','true');node.setAttribute('aria-describedby','orchestration-participant-message');if(!node.matches('input,select,textarea'))node.tabIndex=-1;
  orchestrationText('participant-message',`${error.message}。対応表と理由は保持しています。保存状態を再取得して確認してください。`);node.focus();
}
async function orchestrationParticipantReview(event){
  event.preventDefault();orchestrationParticipantAvailability();if(orchestrationNode('participant-review').disabled||!orchestrationNode('participant-form').reportValidity())return;
  orchestrationParticipantCapture();const state=orchestrationParticipantState,draft=orchestrationParticipantDraft(),option=state.option,step=option.human_steps.find(s=>s.step_id==='participant-mapping-review'),epoch=orchestrationState.epoch,viewer=orchestrationState.viewerEpoch,key=state.key;
  state.sending=true;orchestrationParticipantAvailability();orchestrationAssetAvailability();
  try{
    if(!draft.actor.trim()||!draft.reason.trim()||!orchestrationHumanDecision[draft.decision]||draft.assignments.some(a=>!a.participant_id.trim()))throw Error('すべての話者の対応・記録者・判断・理由を入力してください。');
    // This explicitly authored table is the complete researcher source. Never
    // turn an old free-text memo into participant identities.
    const assignments=draft.assignments.map(a=>({...a,participant_id:a.participant_id.trim()})),source=JSON.stringify({participant_mapping:assignments}),digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(source));
    if(epoch!==orchestrationState.epoch||viewer!==orchestrationState.viewerEpoch||!orchestrationNode('live').open||key!==state.key)return;
    const recordId=step.latest_record?.record.record_id||`researcher-${crypto.randomUUID()}`,record={record_id:recordId,revision:step.next_revision,supersedes_record_ref:orchestrationHumanCopy(step.next_supersedes_record_ref),actor:step.latest_record?orchestrationHumanCopy(step.latest_record.record.actor):{kind:'researcher',actor_id:draft.actor.trim()},decision:draft.decision,target:orchestrationHumanCopy(option.target),allowed_step_ids:['participant-mapping-review'],scope:orchestrationHumanCopy(option.scope),recorded_at:new Date().toISOString(),reason:draft.reason,record_ref:{target_type:'researcher_memo',target_id:`human-source:${recordId}`,version:String(step.next_revision),content_hash:`sha256:${Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('')}`,hash_domain:'raw-bytes-v1',library_id:option.library_id}};
    draft.payload={asset_key:orchestrationHumanCopy(option.asset_key),record,source_text:source,expected_state_revision:option.expected_state_revision};if(new TextEncoder().encode(JSON.stringify(draft.payload)).length>65536)throw Error('対応表が保存上限を超えています。');
    orchestrationText('participant-summary',`${option.label} · 対象版 ${option.target.version}\n${step.label}\n${assignments.map(a=>`会話 ${a.conversation_id} · 話者 ${a.speaker_id} → 参加者 ${a.participant_id}`).join('\n')}\n記録者：${record.actor.actor_id}\n判断：${orchestrationHumanDecision[record.decision]}\n理由：${record.reason}\nこの対応表を原文記録として第${record.revision}版に保存します。他のTA段階や派生入力を自動採用しません。`);
    orchestrationNode('participant-confirmation').hidden=false;
  }catch(error){orchestrationText('participant-message',`${error.message}。対応と理由は保持しています。`);}
  finally{state.sending=false;orchestrationParticipantAvailability();orchestrationAssetAvailability();if(draft.payload&&epoch===orchestrationState.epoch&&viewer===orchestrationState.viewerEpoch&&orchestrationNode('live').open)orchestrationNode('participant-save').focus();}
}
async function orchestrationParticipantSave(){
  orchestrationParticipantAvailability();const state=orchestrationParticipantState,draft=orchestrationParticipantDraft();if(state.sending||orchestrationNode('participant-save').disabled||!draft?.payload)return;
  const payload=draft.payload,epoch=orchestrationState.epoch,viewer=orchestrationState.viewerEpoch,key=state.key;state.sending=true;orchestrationParticipantAvailability();orchestrationAssetAvailability();
  try{
    const {data,status}=await orchestrationHumanJson(`${orchestrationBase(state.option.owner_item_id,state.option.owner_run_id)}/human-records`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(![200,201].includes(status)||data.record?.record_id!==payload.record.record_id||data.record.revision!==payload.record.revision||typeof data.duplicate!=='boolean')throw Error('保存の応答を確認できません。');
    draft.payload=null;draft.uncertain=false;draft.refreshRequired=true;
    if(epoch!==orchestrationState.epoch||viewer!==orchestrationState.viewerEpoch||!orchestrationNode('live').open||key!==state.key)return;orchestrationNode('participant-confirmation').hidden=true;orchestrationText('participant-message',data.duplicate?'同じ対応記録は保存済みです。':'対応表を研究者の原文記録として保存しました。派生入力の採否・現在の対応を再取得して確認してください。');
  }catch(error){
    if(error.status>=400&&error.status<500){draft.payload=null;draft.refreshRequired=true;draft.uncertain=false;orchestrationNode('participant-confirmation').hidden=true;}
    else{draft.uncertain=true;orchestrationNode('participant-save').textContent='同じ対応記録の保存結果を確認・再送';}
    if(epoch===orchestrationState.epoch&&viewer===orchestrationState.viewerEpoch&&orchestrationNode('live').open&&key===state.key)orchestrationParticipantError(error);
  }finally{state.sending=false;orchestrationParticipantAvailability();orchestrationAssetAvailability();}
}
window.addEventListener('DOMContentLoaded',bindAnalysisOrchestration);
