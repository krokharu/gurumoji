/* Native radio controls keep effort selection keyboard and touch accessible. */
const effortStages = [
  ['outline', '全体アウトライン', '校正の参照用と、仕上げ後の議題整理', 'create-outline'],
  ['cleanup', 'おすすめ文章整形', 'Jevの候補を発話単位で確認し、エフォートに応じた文脈で置換', 'clean-transcript'],
  ['name_extract', '話者名の候補抽出', '自己紹介から氏名の候補を拾う', 'detect-names'],
  ['name_verify', '話者リンクの再確認', '氏名と発話者の対応をもう一度確認', 'detect-names']
];
const effortLevels = [['low', '低'], ['medium', '中'], ['high', '高'], ['ultra', 'ultra']];
const cleanupEffortLevels = [['off', 'なし'], ['low', '小'], ['medium', '中'], ['high', '高'], ['ultra', 'MAX']];
const effortDescriptions = {
  off: '思考モードをOFFにします。対応していないモデルでは選べません。',
  low: '短く考えて、速度と使用量を抑えます。',
  medium: '時間と思考量のバランスを取ります。',
  high: 'より長く考えます。時間・使用量が増える場合があります。',
  ultra: '対応モデルで最大の思考量を使います。時間・使用量が大きく増える場合があります。'
};
const cleanupEffortDescriptions = {
  off: '文章整形AIを実行せず、原文とローカルの安全な正規化だけを使います。',
  low: '対象発話だけを読み、原文をできる限り残して致命的な誤りだけを最小修正します。',
  medium: '対象発話だけを読み、意味不明・ノイズ・途切れ・明白な誤認識を文章として修正します。',
  high: 'アウトラインと直前1発話を読み、必要時だけさらに前を1発話ずつ最大10回まで追加します。',
  ultra: 'アウトラインと前後最大10発話を読み、会話の流れから予測できる文章への書き直しを許可します。'
};
let localEffortCapability = null;
let localEffortModel = null;
const effortRoot = document.querySelector('#ai-effort-settings');
if (effortRoot) {
  effortStages.forEach(([key, title, detail]) => {
    const card = document.createElement('fieldset');
    card.className = 'effort-card';
    card.dataset.stage = key;
    const cleanup = key === 'cleanup';
    const thinkingMode = cleanup
      ? `<div class="thinking-mode effort-options" hidden aria-hidden="true"><label><input type="radio" name="ai_thinking_mode_${key}" value="on" checked><span>ON</span></label><label><input type="radio" name="ai_thinking_mode_${key}" value="off"><span>OFF</span></label></div>`
      : `<span class="effort-group-title">思考モード</span><div class="thinking-mode effort-options"><label><input type="radio" name="ai_thinking_mode_${key}" value="on" checked><span>ON</span></label><label><input type="radio" name="ai_thinking_mode_${key}" value="off"><span>OFF</span></label></div>`;
    const levels = cleanup ? cleanupEffortLevels : effortLevels;
    card.innerHTML = `<legend>${title}</legend><p>${detail}</p><input type="hidden" name="ai_effort_${key}" value="medium">${thinkingMode}<span class="effort-group-title">${cleanup ? '文章整形エフォート' : 'エフォート'}</span><div class="effort-options">${levels.map(([value, label]) =>
      `<label><input type="radio" name="ai_effort_choice_${key}" value="${value}" ${value === 'medium' ? 'checked' : ''}><span>${label}</span></label>`).join('')}</div><p class="effort-description" aria-live="polite"></p>`;
    effortRoot.append(card);
  });
  try {
    const saved = JSON.parse(localStorage.getItem('gurumoji.ai-efforts') || '{}');
    effortStages.forEach(([key]) => {
      const value = saved[key];
      const card = effortRoot.querySelector(`[data-stage="${key}"]`);
      if (!card || !value) return;
      if (value === 'off' && key === 'cleanup') card.querySelector('input[name="ai_effort_choice_cleanup"][value="off"]').checked = true;
      else if (value === 'off') card.querySelector('input[name="ai_thinking_mode_' + key + '"][value="off"]').checked = true;
      else card.querySelector('input[name="ai_effort_choice_' + key + '"][value="' + (value === 'auto' ? 'medium' : value) + '"]')?.click();
    });
  } catch (_) { /* Settings remain usable when storage is unavailable. */ }
  effortRoot.addEventListener('change', () => {
    try { localStorage.setItem('gurumoji.ai-efforts', JSON.stringify(readAiEfforts())); } catch (_) {}
    syncAiEffortSettings();
  });
  ['ai-provider', 'finish-in-obsidian', 'clean-transcript', 'detect-names', 'create-outline'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', syncAiEffortSettings);
  });
  syncAiEffortSettings();
}
function readAiEfforts() {
  return Object.fromEntries(effortStages.map(([key]) => {
    if (key === 'cleanup') {
      const legacyMode = document.querySelector('input[name="ai_thinking_mode_cleanup"]:checked')?.value || 'on';
      return [key, legacyMode === 'off' ? 'off' : (document.querySelector('input[name="ai_effort_choice_cleanup"]:checked')?.value || 'medium')];
    }
    const mode = document.querySelector(`input[name="ai_thinking_mode_${key}"]:checked`)?.value || 'on';
    const effort = document.querySelector(`input[name="ai_effort_choice_${key}"]:checked`)?.value || 'medium';
    return [key, mode === 'off' ? 'off' : effort];
  }));
}
function syncAiEffortSettings() {
  const provider = document.querySelector('#ai-provider');
  const local = provider?.value === 'lmstudio';
  if (!local) localEffortModel = null;
  const model = typeof tokenConfigSnapshot === 'undefined' ? '' : tokenConfigSnapshot.lmstudio_model || '';
  if (local && localEffortModel !== model) {
    localEffortModel = model;
    localEffortCapability = null;
    apiFetch('/api/ai/lmstudio-reasoning').then(r => r.ok ? r.json() : Promise.reject())
      .then(data => { if (localEffortModel === model) { localEffortCapability = data.reasoning || {}; syncAiEffortSettings(); } })
      .catch(() => { if (localEffortModel === model) { localEffortCapability = {}; syncAiEffortSettings(); } });
  }
  const allowed = localEffortCapability?.allowed_options || [];
  const localCapabilityLoaded = localEffortCapability !== null;
  const binary = local && allowed.includes('off') && allowed.includes('on') && !allowed.includes('low');
  const localValueSupported = (value) => {
    if (!local || !localCapabilityLoaded || binary) return true;
    const aliases = {
      low: ['low', 'minimal'],
      medium: ['medium', 'low', 'minimal'],
      high: ['high', 'xhigh', 'medium', 'low', 'minimal'],
      ultra: ['xhigh', 'high', 'medium', 'low', 'minimal']
    };
    return (aliases[value] || []).some(option => allowed.includes(option));
  };
  const obsidian = document.querySelector('#finish-in-obsidian')?.checked;
  const recommended = document.querySelector('input[name="transcript_finishing_mode"][value="recommended"]')?.checked;
  effortStages.forEach(([key, , , toggle]) => {
    const card = effortRoot?.querySelector(`[data-stage="${key}"]`);
    if (!card) return;
    const enabled = key === 'cleanup' ? recommended || obsidian || document.getElementById(toggle)?.checked
      : key === 'outline' ? obsidian || document.querySelector('#clean-transcript')?.checked || document.getElementById(toggle)?.checked
      : document.getElementById(toggle)?.checked || (obsidian && provider?.value === 'none');
    card.disabled = Boolean(provider?.disabled || provider?.value === 'none' || !enabled);
    const modeInputs = card.querySelectorAll('[name^="ai_thinking_mode_"]');
    const effortInputs = card.querySelectorAll('[name^="ai_effort_choice_"]');
    const baseDisabled = Boolean(provider?.disabled) || card.disabled;
    if (key === 'cleanup') {
      const legacyThinkingOn = card.querySelector('[name="ai_thinking_mode_cleanup"]:checked')?.value !== 'off';
      effortInputs.forEach(input => { input.disabled = baseDisabled || !legacyThinkingOn; });
      const level = readAiEfforts()[key];
      card.querySelector('input[type="hidden"]').value = level;
      card.dataset.effort = level;
      card.querySelector('.effort-description').textContent = card.disabled
        ? 'AIを選択すると設定できます。'
        : cleanupEffortDescriptions[level];
      return;
    }
    const offInput = card.querySelector('[value="off"]');
    modeInputs.forEach(input => {
      input.disabled = baseDisabled || (input.value === 'off' && local && localCapabilityLoaded && !allowed.includes('off'));
    });
    // A saved unsupported OFF setting must not leave a local model in an invalid state.
    if (offInput?.disabled && offInput.checked) card.querySelector('[value="on"]').checked = true;
    const thinkingOn = card.querySelector('[name^="ai_thinking_mode_"]:checked')?.value !== 'off';
    effortInputs.forEach(input => {
      const value = input.value;
      input.disabled = baseDisabled || !thinkingOn || !localValueSupported(value);
    });
    if (local && localCapabilityLoaded && card.querySelector('[name^="ai_effort_choice_"]:checked')?.disabled) {
      const fallback = [...effortInputs].find(input => !input.disabled);
      if (fallback) fallback.checked = true;
    }
    const level = readAiEfforts()[key];
    card.querySelector('input[type="hidden"]').value = level;
    card.dataset.effort = level;
    card.querySelector('.effort-description').textContent = card.disabled ? 'この処理を有効にすると設定できます。'
      : binary ? 'このモデルは思考ON／OFFに対応します。ONではモデルの既定の思考量を使います。'
      : local && !allowed.length ? 'このモデルは思考量の指定を公開していないため、モデル既定の動作を使用します。'
      : effortDescriptions[level];
  });
}
function renderAiFinishingActivity(job) {
  const panel = document.querySelector('#ai-finishing-activity');
  if (!panel) return;
  const active = job.status === 'running' && ['finishing', 'speaker_names', 'outline'].includes(job.stage);
  panel.hidden = !active;
  panel.setAttribute('aria-busy', String(active));
  if (!active) return;
  const title = panel.querySelector('[data-finishing-title]');
  title.textContent = job.stage_label || 'AI仕上げ中';
  panel.querySelector('[data-finishing-detail]').textContent = job.message || 'AIの応答を待っています…';
}

// Poll only the displayed conversation; never start a finishing operation here.
let obsidianPollBusy = false;
setInterval(async () => {
  const panel = document.querySelector('#obsidian-finishing-activity');
  if (!panel || obsidianPollBusy || document.hidden) return;
  const itemId = typeof currentJobId === 'undefined' ? '' : currentJobId;
  if (!itemId) { panel.hidden = true; return; }
  obsidianPollBusy = true;
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/obsidian-finishing`, {
      signal: AbortSignal.timeout(5000)
    });
    if (!response.ok) throw new Error('status unavailable');
    const state = await response.json();
    if (itemId !== currentJobId) { panel.hidden = true; return; }
    panel.hidden = ['unprepared', 'ready'].includes(state.status);
    panel.setAttribute('aria-busy', String(state.status === 'running'));
    panel.querySelector('.finishing-orbit').hidden = state.status !== 'running';
    panel.querySelector('[data-obsidian-detail]').textContent = state.message;
  } catch (_) { panel.hidden = true; }
  finally { obsidianPollBusy = false; }
}, 3000);
