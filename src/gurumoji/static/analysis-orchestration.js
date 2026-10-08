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
    const title=orchestrationElement('td',orchestrationTableNames[task.method_id] || task.title || task.task_id || '名称未取得'); title.append(orchestrationElement('small',task.task_id || ''));
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
  if(!orchestrationTableNames[raw?.method_id]||!raw.datasets?.table)return false;
  const table=raw.datasets.table,p=raw.population||{},m=raw.manifest||{};
  host.append(orchestrationElement('h4',orchestrationTableNames[raw.method_id]),orchestrationElement('p',`対象の分母 ${m.included_denominator??'未取得'} · 計算の分母 ${m.calculation_denominator??'未取得'} · 欠測 ${p.missing_ids?.length??'未取得'} · 未処理 ${p.unprocessed_ids?.length??'未取得'} · 不明 ${p.unknown_ids?.length??'未取得'} · 除外 ${p.excluded_ids?.length??'未取得'} · 観測ゼロ ${p.observed_zero_ids?.length??'未取得'}`));
  const wrap=orchestrationElement('div',undefined,'orchestration-table-wrap');wrap.tabIndex=0;wrap.setAttribute('aria-label','保存された固定表');
  const grid=orchestrationElement('table'),head=orchestrationElement('thead'),header=orchestrationElement('tr');
  for(const f of table.fields){const th=orchestrationElement('th',f);th.scope='col';header.append(th);}head.append(header);grid.append(head);
  const body=orchestrationElement('tbody');for(const row of table.rows){const tr=orchestrationElement('tr');for(const f of table.fields){
    const value=row[f],category=['category','row_value','column_value'].includes(f)&&['table_frequency','table_crosstab'].includes(raw.method_id);
    const text=value===undefined?'未取得':value===null?'null（保存値）':category?`${typeof value==='string'?`「${value}」`:String(value)}（${{string:'文字列',number:'数値',boolean:'真偽'}[typeof value]||'型未取得'}）`:f==='value_status'?({observed:'観測済み',missing:'欠測',unprocessed:'未処理',excluded:'除外',unknown:'不明'}[value]||String(value)):Array.isArray(value)?value.join(' / '):String(value);
    tr.append(orchestrationElement('td',text));}body.append(tr);}grid.append(body);wrap.append(grid);host.append(wrap);
  const evidence=orchestrationElement('button','固定入力・発話の根拠を履歴ビューアーで読む','secondary-button');evidence.type='button';evidence.addEventListener('click',()=>orchestrationNode('viewer').click());host.append(evidence);
  host.append(orchestrationElement('p','空セルをゼロとは扱いません。表の値・対象集合・計算対象はこの保存結果の固定版です。研究者による採否は別に確認してください。','field-note'));return true;
}
// Researcher drafts stay in memory only. GET supplies immutable targets and
// revision context; neither viewing nor polling records a human decision.
const orchestrationHumanState={runKey:'',options:null,selection:null,drafts:new Map(),loading:false,sending:false,request:0};
const orchestrationHumanDecision={adopt:'採用',reject:'不採用',defer:'保留'};
const orchestrationHumanFields=['actor','source','decision','reason'];
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
  orchestrationText('human-availability',!run?'保存済み実行を選んでください。':blocked?'実行の停止・入力変更・未対応状態を検出しました。記録内容を保持し、保存候補を再取得してください。':state.options?.enabled===false?orchestrationHumanReason(state.options.reason_code):option?.enabled===false?orchestrationHumanReason(option.reason_code):'四つの段階をそれぞれ独立して記録します。表示の取得は判断を記録しません。');
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
  return data?.schema_id==='gurumoji.human-record-options'&&data.schema_version===1&&data.item_id===orchestrationState.itemId&&data.run_id===orchestrationState.runId&&
    (data.generation===null||integer(data.generation))&&typeof data.enabled==='boolean'&&(!data.enabled||integer(data.generation))&&integer(data.offset)&&data.offset<=10000&&data.limit===20&&
    (data.next_offset===null||integer(data.next_offset)&&data.next_offset<=10000)&&Array.isArray(data.options)&&data.options.length<=20&&data.options.every(option=>
      option.asset_key&&typeof option.library_id==='string'&&option.asset_key.library_id===option.library_id&&option.scope&&
      ['candidate','theme'].includes(option.target_kind)&&typeof option.label==='string'&&option.target&&
      option.target.domain===(option.target_kind==='candidate'?'ta-candidate-content-v1':'ta-theme-content-v1')&&integer(option.target.version)&&option.target.version>=1&&hash(option.target.content_hash)&&
      integer(option.expected_state_revision)&&typeof option.enabled==='boolean'&&Array.isArray(option.human_steps)&&option.human_steps.length===4&&
      new Set(option.human_steps.map(step=>step.step_id)).size===4&&option.human_steps.every(step=>typeof step.step_id==='string'&&typeof step.label==='string'&&integer(step.next_revision)&&step.next_revision>=1&&
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
    const {data}=await orchestrationHumanJson(`${orchestrationBase()}/human-records?offset=${offset}`);
    if(!current())return;
    if(!orchestrationHumanOptionsValid(data))throw Error('研究者記録の読取形式・対象・改訂情報を確認できません。未対応の応答です。');
    state.options=data;
    const retained=preserve&&data.options.find(option=>orchestrationHumanTargetKey(option)===oldKey);
    if(preserve&&previous&&!retained) {
      const draft=orchestrationHumanDraft();if(draft){draft.refreshRequired=true;draft.payload=null;}
      orchestrationNode('human-form').hidden=false;
      orchestrationHumanMessage('元の対象版が現在の選択肢にありません。原文メモは元の対象に保持しました。別の候補へ転用せず、対象を確認してください。',true,true);return;
    }
    const assets=[...data.options.reduce((map,option)=>{const key=orchestrationHumanAssetKey(option);if(!map.has(key)||option.target_kind==='candidate')map.set(key,option);return map;},new Map()).values()];
    orchestrationNode('human-asset').replaceChildren(...assets.map((option,index)=>{const node=orchestrationElement('option',`保存候補 ${data.offset+index+1} · ${option.label}`);node.value=orchestrationHumanAssetKey(option);return node;}));
    orchestrationNode('human-next').hidden=data.next_offset===null;
    if(retained)orchestrationNode('human-asset').value=orchestrationHumanAssetKey(retained);
    state.selection=null;orchestrationNode('human-form').hidden=!data.options.length;
    if(data.options.length)orchestrationHumanSelect('asset',retained,oldStep,preserve);
    if(!preserve)orchestrationHumanMessage(data.options.length?'対象と一つの段階を選び、研究者本人の記録を入力してください。':'この実行に記録可能な保存候補はありません。');
    const draft=orchestrationHumanDraft();if(draft){draft.refreshRequired=false;draft.payload=null;}
  } catch(error) {
    if(current()){orchestrationNode('human-form').hidden=!state.selection;orchestrationHumanMessage(`保存候補の取得: ${error.message}。入力メモは保持しています。`,true);}
  } finally {if(request===state.request){state.loading=false;orchestrationHumanAvailability();}}
}
function orchestrationHumanSelect(kind,retained=null,oldStep=null,preserveMessage=false) {
  const state=orchestrationHumanState;orchestrationHumanCapture();
  if(kind==='asset') {
    const choices=state.options?.options.filter(option=>orchestrationHumanAssetKey(option)===orchestrationNode('human-asset').value)||[];
    orchestrationNode('human-target').replaceChildren(...choices.map(option=>{const node=orchestrationElement('option',`${option.target_kind==='candidate'?'候補全体':'テーマ'} · ${option.label} · 版 ${option.target.version}`);node.value=orchestrationHumanTargetKey(option);return node;}));
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
  orchestrationText('human-existing',step?.latest_record?`既存記録の訂正（第${step.next_revision}版）です。記録者・対象・段階は引き継ぎます。前の理由：${step.latest_record.record.reason}`:step?'この段階の新しい研究者記録です。':'四つの段階を一度に確認済みにする操作はありません。');
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
    orchestrationText('human-summary',`${option.target_kind==='candidate'?'候補全体':'テーマ'} · ${option.label} · 版 ${option.target.version}\n${step.label}\n記録者：${record.actor.actor_id}\n判断：${orchestrationHumanDecision[record.decision]}\n理由：${record.reason}\n原文メモ：\n${draft.source}\nこの一つの段階だけを、第${record.revision}版としてローカルに保存します。`);
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
window.addEventListener('DOMContentLoaded',bindAnalysisOrchestration);
