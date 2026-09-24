/* Native radio controls keep effort selection keyboard and touch accessible. */
const effortStages = [
  ['outline', '会話の流れを整理', '会話全体を確認し、話題ごとに整理します。', 'create-outline'],
  ['cleanup', '文章の仕上げ', '必要な箇所をどの程度整えるか選びます。', 'clean-transcript'],
  ['name_extract', '話者名を確認', '自己紹介から名前の候補を探します。', 'detect-names'],
  ['name_verify', '話者を再確認', '名前と発話の対応を確認します。', 'detect-names']
];
const effortLevels = [['low', '低'], ['medium', '中'], ['high', '高'], ['ultra', '最大']];
const cleanupEffortLevels = [['off', 'なし'], ['low', '小'], ['medium', '中'], ['high', '高'], ['ultra', 'MAX']];
const effortDescriptions = {
  off: 'AIによる詳しい検討を行いません。モデルによっては選べません。',
  low: '短時間で確認します。',
  medium: '標準的な詳しさで確認します。',
  high: 'より詳しく確認します。処理時間や使用量が増える場合があります。',
  ultra: '最も詳しく確認します。処理時間や使用量が大きく増える場合があります。'
};
const cleanupEffortDescriptions = {
  off: 'AIで文章を整えず、認識結果を残します。',
  low: '発話を一つずつ確認し、明らかな誤りだけを直します。',
  medium: '発話を一つずつ確認し、誤認識や聞き取りにくい箇所を整えます。',
  high: '直前の会話や話題を参考にして整えます。',
  ultra: '前後の会話や話題を参考に、文章を詳しく整えます。'
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
      ? `<div class="thinking-mode effort-options" hidden aria-hidden="true"><label><input type="radio" name="ai_thinking_mode_${key}" value="on" checked><span>する</span></label><label><input type="radio" name="ai_thinking_mode_${key}" value="off"><span>しない</span></label></div>`
      : `<span class="effort-group-title">AIで詳しく確認</span><div class="thinking-mode effort-options"><label><input type="radio" name="ai_thinking_mode_${key}" value="on" checked><span>する</span></label><label><input type="radio" name="ai_thinking_mode_${key}" value="off"><span>しない</span></label></div>`;
    const levels = cleanup ? cleanupEffortLevels : effortLevels;
    card.innerHTML = `<legend>${title}</legend><p>${detail}</p><input type="hidden" name="ai_effort_${key}" value="medium">${thinkingMode}<span class="effort-group-title">${cleanup ? '文章の調整レベル' : '確認の詳しさ'}</span><div class="effort-options">${levels.map(([value, label]) =>
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
      : binary ? 'このモデルでは、詳しい確認をするかどうか選べます。'
      : local && !allowed.length ? 'このモデルは確認の詳しさを変更できないため、標準の設定を使用します。'
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
