function captureAnalysisContext() {
  return {itemId: analysisState.itemId, data: analysisState.data, navigation: analysisNavigationGeneration,
    mutation: analysisMutationGeneration, sourceRevision: analysisState.data?.item?.revision_count,
    analysisRevision: analysisState.data?.item?.analysis_revision};
}

function isAnalysisContextCurrent(context) {
  return context.itemId === analysisState.itemId && context.data === analysisState.data
    && context.navigation === analysisNavigationGeneration && context.mutation === analysisMutationGeneration
    && context.sourceRevision === analysisState.data?.item?.revision_count
    && context.analysisRevision === analysisState.data?.item?.analysis_revision;
}

function segmentClassificationBusy() { return segmentClassificationRequests.has(analysisState.itemId); }

function startBootSequence() {
  if (!bootSplash) {
    document.body.classList.remove('booting');
    return;
  }
  // The splash is an intro, not a real check: show it once per browser session
  // and keep it short, so reloads go straight to the workspace (UX-08).
  let seen = false;
  try {
    seen = window.sessionStorage.getItem('gurumoji.bootSplashSeen') === '1';
    window.sessionStorage.setItem('gurumoji.bootSplashSeen', '1');
  } catch (error) {
    seen = false;
  }
  if (seen) {
    bootSplash.hidden = true;
    bootSplash.setAttribute('aria-hidden', 'true');
    document.body.classList.add('boot-skipped');
    document.body.classList.remove('booting');
    return;
  }
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.setTimeout(() => {
    bootSplash.classList.add('show-main');
    window.setTimeout(() => {
      bootSplash.classList.add('is-leaving');
      document.body.classList.remove('booting');
      window.setTimeout(() => {
        bootSplash.hidden = true;
        bootSplash.setAttribute('aria-hidden', 'true');
      }, reducedMotion ? 50 : 400);
    }, reducedMotion ? 150 : 650);
  }, reducedMotion ? 200 : 1200);
}

function setAlert(element, message, error = false) {
  if (!element) return;
  element.setAttribute('role', error ? 'alert' : 'status');
  element.setAttribute('aria-live', error ? 'assertive' : 'polite');
  element.setAttribute('aria-atomic', 'true');
  element.textContent = message || '';
  element.hidden = !message;
  element.classList.toggle('error', error);
}

function listen(element, eventName, handler) {
  if (element) element.addEventListener(eventName, handler);
}

function apiFetch(input, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    return window.fetch(input, options);
  }
  const headers = new Headers(options.headers || {});
  headers.set('X-Gurumoji-Request', '1');
  return window.fetch(input, {...options, headers});
}

function deepCopy(value) {
  return JSON.parse(JSON.stringify(value));
}

function storedActiveJobId() {
  try {
    return String(window.sessionStorage.getItem(activeJobStorageKey) || '').trim();
  } catch (_) {
    return '';
  }
}

function storeActiveJobId(jobId) {
  try {
    if (jobId) window.sessionStorage.setItem(activeJobStorageKey, String(jobId));
    else window.sessionStorage.removeItem(activeJobStorageKey);
  } catch (_) {
    // Storage can be unavailable in hardened or private browser contexts.
  }
}

function storedPendingSubmissionId() {
  try {
    const raw = window.sessionStorage.getItem(pendingSubmissionStorageKey);
    if (!raw) return '';
    const pending = JSON.parse(raw);
    const submissionId = String(pending && pending.id || '').trim();
    const createdAt = Number(pending && pending.createdAt);
    if (!/^[0-9a-f]{32}$/.test(submissionId)
        || !Number.isFinite(createdAt)) {
      window.sessionStorage.removeItem(pendingSubmissionStorageKey);
      return '';
    }
    return submissionId;
  } catch (_) {
    try { window.sessionStorage.removeItem(pendingSubmissionStorageKey); } catch (_) {}
    return '';
  }
}

function storePendingSubmissionId(submissionId, retryAllowed = false) {
  try {
    if (submissionId) {
      window.sessionStorage.setItem(pendingSubmissionStorageKey, JSON.stringify({
        id: String(submissionId),
        createdAt: Date.now(),
        retryAllowed: Boolean(retryAllowed)
      }));
    } else {
      window.sessionStorage.removeItem(pendingSubmissionStorageKey);
    }
  } catch (_) {
    // Storage can be unavailable in hardened or private browser contexts.
  }
}

function pendingSubmissionRetryAllowed(submissionId) {
  try {
    const pending = JSON.parse(window.sessionStorage.getItem(pendingSubmissionStorageKey) || '{}');
    return pending.id === submissionId && pending.retryAllowed === true;
  } catch (_) {
    return false;
  }
}

function markPendingSubmissionRetryable(submissionId) {
  storePendingSubmissionId(submissionId, true);
}

function createSubmissionId() {
  if (window.crypto && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID().replaceAll('-', '');
  }
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
}

function setCurrentJobDirty(dirty = true, trackMutation = true) {
  currentJobDirty = Boolean(dirty);
  if (currentJobDirty && trackMutation) currentJobMutationGeneration += 1;
  if (resultCard) resultCard.classList.toggle('has-unsaved', currentJobDirty);
  if (saveButton) saveButton.classList.toggle('unsaved', currentJobDirty);
}

async function readJsonResponse(response) {
  const body = await response.text();
  if (!body) return {};
  try {
    return JSON.parse(body);
  } catch (error) {
    const status = `${response.status} ${response.statusText}`.trim();
    const looksLikeHtml = body.trimStart().startsWith('<')
      || (response.headers.get('content-type') || '').includes('text/html');
    if (looksLikeHtml) {
      throw new Error(
        `サーバーからHTMLエラーが返されました（${status}）。アプリを再起動してページを再読み込みしてください。`
      );
    }
    throw new Error(`サーバー応答を読み取れませんでした（${status}）。`);
  }
}

function vocabularyTermsFromInput(value = customVocabulary && customVocabulary.value) {
  return String(value || '')
    .split(/\r?\n/)
    .map(term => term.trim())
    .filter(Boolean);
}

function setCustomVocabularyStatus(message, error = false) {
  if (!customVocabularyStatus) return;
  customVocabularyStatus.textContent = message;
  customVocabularyStatus.classList.toggle('error', error);
}

function customVocabularyCountLabel(terms) {
  const count = Array.isArray(terms) ? terms.length : 0;
  return count ? `${count}語を登録` : '未登録';
}

async function loadCustomVocabulary() {
  if (!customVocabulary) return;
  try {
    const response = await apiFetch('/api/custom-vocabulary', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '単語登録を読み込めませんでした。');
    const terms = Array.isArray(data.terms) ? data.terms.map(term => String(term).trim()).filter(Boolean) : [];
    if (!customVocabularyTouched) customVocabulary.value = terms.join('\n');
    setCustomVocabularyStatus(customVocabularyCountLabel(
      customVocabularyTouched ? vocabularyTermsFromInput() : terms
    ));
    updateCreateSummary();
  } catch (error) {
    setCustomVocabularyStatus(error.message || '単語登録を読み込めませんでした。', true);
  }
}

async function saveCustomVocabulary(saveGeneration) {
  if (!customVocabulary) return;
  const sourceText = customVocabulary.value;
  const terms = vocabularyTermsFromInput(sourceText);
  setCustomVocabularyStatus('保存中…');
  try {
    const response = await apiFetch('/api/custom-vocabulary', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({terms})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '単語登録を保存できませんでした。');
    if (saveGeneration !== customVocabularyMutationGeneration) return;
    const savedTerms = Array.isArray(data.terms) ? data.terms.map(term => String(term).trim()).filter(Boolean) : [];
    customVocabulary.value = savedTerms.join('\n');
    setCustomVocabularyStatus(customVocabularyCountLabel(savedTerms));
    updateCreateSummary();
  } catch (error) {
    if (saveGeneration === customVocabularyMutationGeneration) {
      setCustomVocabularyStatus(error.message || '単語登録を保存できませんでした。', true);
    }
  }
}

function scheduleCustomVocabularySave({immediate = false} = {}) {
  if (!customVocabulary) return;
  if (customVocabularySaveTimer !== null) window.clearTimeout(customVocabularySaveTimer);
  const saveGeneration = customVocabularyMutationGeneration;
  setCustomVocabularyStatus('保存待ち…');
  const save = () => {
    customVocabularySaveTimer = null;
    saveCustomVocabulary(saveGeneration);
  };
  if (immediate) save();
  else customVocabularySaveTimer = window.setTimeout(save, 450);
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value.toFixed(unit ? 1 : 0)} ${units[unit]}`;
}

function formatTime(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h
    ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value || '' : new Intl.DateTimeFormat('ja-JP', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  }).format(date);
}

function selectedOptionText(select) {
  return select && select.selectedOptions && select.selectedOptions[0]
    ? select.selectedOptions[0].textContent.trim()
    : '';
}

function hasSelectedSource() {
  return Boolean(
    (sourcePath && sourcePath.value.trim())
    || (inputFile && inputFile.files && inputFile.files.length)
  );
}

function isMobileWizard() {
  return mobileWizardMedia.matches;
}

function updateBrowseButtonLabel() {
  if (!browsePathButton || browsePathButton.disabled) return;
  browsePathButton.textContent = isMobileWizard()
    ? '端末から選択'
    : (browserFilePickerOnly ? '端末からアップロード' : 'ファイルを選択');
}

function scrollBehavior() {
  return reducedMotionMedia.matches ? 'auto' : 'smooth';
}

// One stepper for every width (UX-05): on a desktop it reports progress and
// scrolls to the section; on a phone it is the wizard's page indicator.
function renderFlowSteps() {
  const hasSource = hasSelectedSource();
  const mobile = isMobileWizard();
  flowStepItems.forEach(item => {
    const step = Number(item.dataset.flowStep);
    item.classList.remove('active', 'complete', 'ready');
    if (mobile) {
      if (step === currentMobileStep) item.classList.add('active');
      else if (step < currentMobileStep) item.classList.add('complete');
      else if (step === 3 && hasSource) item.classList.add('ready');
    } else if (step === 1) {
      item.classList.add(hasSource ? 'complete' : 'active');
    } else if (step === 2) {
      if (hasSource) item.classList.add('active');
    } else if (hasSource) {
      item.classList.add('ready');
    }
    const button = item.querySelector('[data-flow-jump]');
    if (button) button.setAttribute('aria-current', item.classList.contains('active') ? 'step' : 'false');
  });
}

function renderMobileWizard() {
  if (!form) return;
  const mobile = isMobileWizard();
  form.classList.toggle('mobile-wizard-ready', mobile);
  [1, 2, 3].forEach(step => form.classList.toggle(`mobile-step-${step}`, step === currentMobileStep));
  flowSections.forEach(section => {
    const active = Number(section.dataset.flowSection) === currentMobileStep;
    section.classList.toggle('mobile-active', active);
    if (mobile) section.toggleAttribute('inert', !active);
    else section.removeAttribute('inert');
  });
  const content = mobileStepContent[currentMobileStep] || mobileStepContent[1];
  if (mobileNavStep) mobileNavStep.textContent = `${currentMobileStep} / 3`;
  if (mobileNavLabel) mobileNavLabel.textContent = content.label;
  if (mobileStepBack) mobileStepBack.disabled = jobRunning || currentMobileStep === 1;
  if (mobileStepNext) {
    mobileStepNext.disabled = jobRunning || currentMobileStep >= 3 || (currentMobileStep === 1 && !hasSelectedSource());
    mobileStepNext.textContent = content.next;
  }
  renderFlowSteps();
}

function validateMobileStep(step) {
  if (step === 1 && !hasSelectedSource()) {
    setAlert(pathError, '先に音声・動画ファイルを選択してください。', true);
    if (fileDropZone) fileDropZone.focus();
    return false;
  }
  const section = flowSections.find(item => Number(item.dataset.flowSection) === step);
  if (!section) return true;
  const invalid = [...section.querySelectorAll('input, select, textarea')].find(input => !input.checkValidity());
  if (invalid) {
    setAlert(formError, '入力内容を確認してください。', true);
    const panel = invalid.closest('[data-settings-panel]');
    if (panel) panel.open = true;
    invalid.reportValidity();
    invalid.focus();
    return false;
  }
  return true;
}

function setMobileStep(nextStep, {focusHeading = true, validateCurrent = false} = {}) {
  const target = Math.max(1, Math.min(3, Number(nextStep) || 1));
  if (validateCurrent && target > currentMobileStep && !validateMobileStep(currentMobileStep)) return false;
  currentMobileStep = target;
  setAlert(formError, '');
  renderMobileWizard();
  if (focusHeading && isMobileWizard()) {
    const steps = document.querySelector('#flow-steps');
    if (steps) steps.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
    const section = flowSections.find(item => Number(item.dataset.flowSection) === target);
    const heading = section ? section.querySelector('h2') : null;
    if (heading) {
      heading.setAttribute('tabindex', '-1');
      window.setTimeout(() => heading.focus({preventScroll: true}), 220);
    }
  }
  return true;
}

function jumpToFlowStep(step) {
  const target = Math.max(1, Math.min(3, Number(step) || 1));
  if (isMobileWizard()) {
    setMobileStep(target, {validateCurrent: target > currentMobileStep});
    return;
  }
  const section = flowSections.find(item => Number(item.dataset.flowSection) === target);
  if (section) section.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
}

// Detailed settings stay closed until asked for; "変更" opens exactly one panel.
function openSettingsPanel(name, {focus = true} = {}) {
  const panel = settingsPanels.find(item => item.dataset.settingsPanel === name);
  if (!panel) return;
  if (isMobileWizard() && currentMobileStep !== 2) setMobileStep(2, {focusHeading: false});
  panel.open = true;
  window.requestAnimationFrame(() => {
    panel.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
    if (!focus) return;
    const control = panel.querySelector('input:not([type="hidden"]):not(:disabled), select:not(:disabled), textarea:not(:disabled)');
    if (control) window.setTimeout(() => control.focus({preventScroll: true}), 260);
  });
}

function selectedConversationMode() {
  const selected = conversationModeInputs.find(input => input.checked);
  return selected && conversationModePresets[selected.value]
    ? selected.value
    : 'meeting';
}

function isSpeakerCountFixed() {
  return speakerCountFixButton?.getAttribute('aria-pressed') === 'true';
}

function syncFixedSpeakerCount() {
  if (!isSpeakerCountFixed()) return;
  minSpeakersInput.value = fixedSpeakerCountInput.value;
  maxSpeakersInput.value = fixedSpeakerCountInput.value;
  updateCreateSummary();
}

function setSpeakerCountFixed(fixed, {restoreRange = true} = {}) {
  if (fixed) {
    speakerRangeBeforeFix = {
      min: minSpeakersInput.value,
      max: maxSpeakersInput.value,
      editedMin: manuallyEditedModeFields.has('minSpeakers'),
      editedMax: manuallyEditedModeFields.has('maxSpeakers')
    };
    if (minSpeakersInput.value && minSpeakersInput.value === maxSpeakersInput.value) {
      fixedSpeakerCountInput.value = minSpeakersInput.value;
    }
    manuallyEditedModeFields.add('minSpeakers');
    manuallyEditedModeFields.add('maxSpeakers');
  } else if (speakerRangeBeforeFix && restoreRange) {
    minSpeakersInput.value = speakerRangeBeforeFix.min;
    maxSpeakersInput.value = speakerRangeBeforeFix.max;
    if (!speakerRangeBeforeFix.editedMin) manuallyEditedModeFields.delete('minSpeakers');
    if (!speakerRangeBeforeFix.editedMax) manuallyEditedModeFields.delete('maxSpeakers');
  }
  speakerCountFixButton.setAttribute('aria-pressed', String(fixed));
  speakerCountFixButton.textContent = fixed ? '人数の固定を解除する' : '話者数を固定する';
  fixedSpeakerCountField.hidden = !fixed;
  fixedSpeakerCountInput.disabled = !fixed;
  minSpeakersField.hidden = fixed;
  maxSpeakersField.hidden = fixed;
  if (fixed) {
    syncFixedSpeakerCount();
    fixedSpeakerCountInput.focus();
  } else {
    speakerRangeBeforeFix = null;
    applyConversationMode();
  }
}

function applyConversationMode(mode = selectedConversationMode()) {
  const preset = conversationModePresets[mode] || conversationModePresets.meeting;
  if (createView) createView.dataset.conversationMode = conversationModePresets[mode] ? mode : 'meeting';
  const keptLabels = [];
  conversationModeFields.forEach(field => {
    const presetValue = field.property === 'checked' ? preset[field.key] : String(preset[field.key]);
    if (!manuallyEditedModeFields.has(field.key)) {
      field.input[field.property] = presetValue;
    } else if (field.input[field.property] !== presetValue) {
      keptLabels.push(field.label);
    }
  });
  if (conversationModeHint) {
    conversationModeHint.textContent = keptLabels.length
      ? `${preset.hint} 手動で変更した「${keptLabels.join('」「')}」は変更せずに残しています。`
      : preset.hint;
  }
  if (conversationModeResetButton) conversationModeResetButton.hidden = !keptLabels.length;

  // A mode adjusts local, deterministic recognition settings only. External AI
  // remains an explicit choice in the AI finishing section.
  syncQuietFields();
  updateCreateSummary();
}

function syncTranscriptionBackend() {
  const haasSelected = transcriptionBackend?.value === 'haas_ja';
  const asrDevice = document.querySelector('#transcription-device');
  const cpuOption = asrDevice?.querySelector('option[value="cpu"]');
  if (cpuOption) cpuOption.disabled = haasSelected;
  if (haasSelected && asrDevice?.querySelector('option[value="cuda"]:not(:disabled)')) {
    asrDevice.value = 'cuda';
  }
  // Both isolated stacks diarize with Nemotron 3 and skip the WhisperX controls.
  const qwenSelected = transcriptionBackend?.value === 'qwen3_nemotron' || haasSelected;
  if (qwenSelected && isSpeakerCountFixed()) setSpeakerCountFixed(false);
  if (modelName) modelName.disabled = qwenSelected;
  if (triplePass) {
    triplePass.disabled = qwenSelected;
    if (qwenSelected) triplePass.checked = false;
  }
  [boostQuietSpeech, vadOnset, vadOffset].forEach(input => {
    if (input) input.disabled = qwenSelected;
  });
  if (speakerCountFixButton) {
    speakerCountFixButton.disabled = qwenSelected;
    const speakerCountField = speakerCountFixButton.closest('.field');
    if (speakerCountField) speakerCountField.hidden = qwenSelected;
  }
  [minSpeakersField, maxSpeakersField].forEach(field => {
    if (field) field.hidden = qwenSelected || isSpeakerCountFixed();
  });
  [minSpeakersInput, maxSpeakersInput].forEach(input => {
    if (input) input.disabled = qwenSelected;
  });
  if (qwenBackendNote) qwenBackendNote.hidden = transcriptionBackend?.value !== 'qwen3_nemotron';
  if (haasBackendNote) haasBackendNote.hidden = !haasSelected;
  if (haasSelected && languageSelect && languageSelect.value !== 'ja') languageSelect.value = 'ja';
  if (qwenVocabularyNote) qwenVocabularyNote.hidden = !qwenSelected;
}

function transcriptFinishingPlan() {
  // 実行側のモード正規化に合わせ、保存中の選択値と今回の処理を分ける。
  const mode = document.querySelector('input[name="transcript_finishing_mode"]:checked')?.value || 'custom';
  const enabled = mode !== 'off' && (document.querySelector('#ai-provider')?.value || 'none') !== 'none';
  const advanced = mode === 'advanced';
  const recommended = mode === 'recommended';
  const deferred = mode !== 'off' && !advanced && Boolean(document.querySelector('#finish-in-obsidian')?.checked);
  const values = typeof readAiEfforts === 'function' ? readAiEfforts() : {
    cleanup: document.querySelector('[name="ai_effort_cleanup"]')?.value || 'medium',
    notation: document.querySelector('[name="ai_effort_notation"]')?.value || 'off'
  };
  const fullCleanup = enabled && (advanced || (!recommended && Boolean(document.querySelector('#clean-transcript')?.checked || document.querySelector('#jev-compare')?.checked)));
  const recommendedCleanup = enabled && recommended && !deferred && values.cleanup !== 'off'
    && Boolean(typeof tokenConfigSnapshot !== 'undefined' && tokenConfigSnapshot.typesafe);
  const cleanup = !deferred && values.cleanup !== 'off' && (fullCleanup || recommendedCleanup);
  const contextOutline = cleanup && (fullCleanup || ['high', 'ultra'].includes(values.cleanup));
  const outlineOutput = enabled && !deferred && !recommended && Boolean(document.querySelector('#create-outline')?.checked);
  const names = enabled && (advanced || Boolean(document.querySelector('#detect-names')?.checked));
  const notation = enabled && !deferred && values.notation !== 'off';
  const compare = cleanup && !recommended && Boolean(document.querySelector('#jev-compare')?.checked);
  return {mode, advanced, deferred, fullCleanup, recommendedCleanup, contextOutline, outlineOutput, notation, compare,
    requested: {cleanup: Boolean(cleanup), outline: Boolean(contextOutline || outlineOutput), name_extract: Boolean(names), name_verify: Boolean(names)},
    configurable: {cleanup: enabled && Boolean(recommended || deferred || fullCleanup), outline: Boolean(contextOutline || outlineOutput), name_extract: Boolean(names), name_verify: Boolean(names)}};
}

function enabledTextDestinations() {
  const provider = aiProvider?.value || 'none';
  const mode = selectedTranscriptFinishingMode();
  if (provider === 'none' || mode === 'off') return [];
  const plan = transcriptFinishingPlan();
  const destinations = [];
  if (Object.values(plan.requested).some(Boolean) || plan.notation) {
    destinations.push({provider, label: selectedOptionText(aiProvider), model: tokenConfigSnapshot[`${provider}_model`] || 'モデル未設定'});
  }
  if (plan.recommendedCleanup || plan.compare) {
    destinations.push({provider: 'typesafe', label: 'TypeSafe Jev（外部サービス）', model: tokenConfigSnapshot.typesafe_model || 'jev-latest'});
  }
  return destinations;
}

function readSeenNotices() {
  try {
    const stored = JSON.parse(localStorage.getItem(seenNoticeStorageKey) || '[]');
    return new Set(Array.isArray(stored) ? stored : []);
  } catch (_) { return new Set(); }
}

function rememberSeenNotices(notices) {
  if (!notices || !notices.length) return;
  const seen = readSeenNotices();
  notices.forEach(notice => seen.add(notice));
  try { localStorage.setItem(seenNoticeStorageKey, JSON.stringify([...seen])); } catch (_) { /* shown again next time */ }
}

function createReadiness() {
  const blockers = [];
  const notes = [];
  const acknowledgementNotes = new Set();
  let requiresModelAcknowledgement = false;
  if (configLoadState !== 'loaded') blockers.push(configLoadState === 'error' ? '設定を確認できません。接続と処理装置から再確認してください' : '実行環境と設定を確認中です');
  if (configLoadState === 'loaded') {
    const backend = transcriptionBackend?.value || 'whisperx';
    if (audioPreprocess?.value === 'reuse') {
      const audioReadiness = tokenConfigSnapshot.transcription_readiness?.audio_preprocess?.reuse;
      if (!audioReadiness) blockers.push('RE-USEの準備状態を確認できません。設定を再確認してください');
      else {
        blockers.push(...(audioReadiness.blockers || []));
        (audioReadiness.notes || []).forEach(note => notes.push(note));
      }
    }
    if (backend === 'whisperx' && !tokenConfigSnapshot.huggingface) blockers.push('話者分離に必要なHugging Faceトークンを設定してください。');
    const readiness = tokenConfigSnapshot.transcription_readiness?.[backend];
    if (!readiness) blockers.push('方式・モデルの準備状態を取得できません。設定を再確認してください');
    else {
      blockers.push(...(readiness.blockers || []));
      (readiness.notes || []).forEach(note => { notes.push(note); acknowledgementNotes.add(note); });
      const device = document.querySelector('#transcription-device')?.value || 'cpu';
      const model = readiness.models?.[device]?.[modelName?.value];
      if (model) {
        const note = `認識モデル: ${model.message}`;
        notes.push(note);
        if (model.status !== 'cached') acknowledgementNotes.add(note);
      } else if (backend === 'whisperx') {
        const note = '選択した認識モデルの取得状況は未確認です';
        notes.push(note);
        acknowledgementNotes.add(note);
      }
    }
    enabledTextDestinations().forEach(destination => {
      if (!tokenConfigSnapshot[destination.provider]) blockers.push(`${destination.label}が未設定または接続できません`);
      if (destination.provider === 'lmstudio' && !tokenConfigSnapshot.lmstudio_model) blockers.push('ローカルLLMのモデルが未設定です');
    });
    if (selectedTranscriptFinishingMode() === 'advanced' && aiProvider?.value === 'none') blockers.push('全文仕上げに使うAIを選択してください');
  }
  if (typeof aiEffortReadiness === 'function') {
    const effortReadiness = aiEffortReadiness();
    blockers.push(...effortReadiness.blockers);
    notes.push(...effortReadiness.notes);
  }
  const seen = readSeenNotices();
  const pendingNotes = [...new Set(notes)].filter(note => !seen.has(note));
  requiresModelAcknowledgement = pendingNotes.some(note => acknowledgementNotes.has(note));
  const acknowledged = Boolean(document.querySelector('#model-readiness-ack')?.checked);
  return {ready: hasSelectedSource() && !blockers.length && (!requiresModelAcknowledgement || acknowledged), requiresModelAcknowledgement, acknowledged, blockers: [...new Set(blockers)], notes: pendingNotes};
}

function updateCreateSummary() {
  const hasSource = hasSelectedSource();
  if (fileDropZone) fileDropZone.classList.toggle('has-file', hasSource);
  if (pathDetail) pathDetail.classList.toggle('selected', hasSource);

  const readiness = createReadiness();
  const readyMessage = !hasSource ? 'ファイルを選択してください'
    : readiness.blockers.length ? 'ファイル選択済み・開始前の確認が必要です'
    : readiness.requiresModelAcknowledgement ? 'ファイル選択済み・モデルの確認や取得が必要です' : 'ファイル選択済み・開始時にモデルを読み込みます';
  const modelAcknowledgement = document.querySelector('#model-readiness-ack-row');
  if (modelAcknowledgement) modelAcknowledgement.hidden = !readiness.requiresModelAcknowledgement;
  const readinessDetails = document.querySelector('#setup-readiness-details');
  if (readinessDetails) {
    setAlert(readinessDetails, [...readiness.blockers, ...readiness.notes].join('\n'), Boolean(readiness.blockers.length));
    readinessDetails.replaceChildren();
    for (const [title, messages] of [['設定が必要な項目', readiness.blockers], ['開始時の確認事項', readiness.notes]]) {
      if (!messages.length) continue;
      const section = document.createElement('section');
      const heading = document.createElement('p');
      heading.className = 'readiness-heading';
      heading.textContent = title;
      const list = document.createElement('ul');
      const grouped = new Map();
      messages.forEach(message => {
        const match = message.match(/^([^:]+): (.+)$/s);
        const detail = match ? match[2] : message;
        if (!grouped.has(detail)) grouped.set(detail, []);
        if (match) grouped.get(detail).push(match[1]);
      });
      grouped.forEach((labels, detail) => {
        const item = document.createElement('li');
        item.textContent = `${labels.length ? `${labels.join('／')}: ` : ''}${detail.replace(/[。\s]+$/u, '')}。`;
        list.append(item);
      });
      section.append(heading, list);
      readinessDetails.append(section);
    }
  }
  const destinations = enabledTextDestinations();
  const destinationText = destinations.length ? destinations.map(item => `${item.label} / ${item.model}`).join('、') : '送信なし';
  document.querySelectorAll('[data-text-destinations]').forEach(element => { element.textContent = `今回のテキスト送信先: ${destinationText}`; });
  const deferredNote = document.querySelector('#deferred-destination-note');
  if (deferredNote) deferredNote.hidden = !(finishInObsidian?.checked && selectedTranscriptFinishingMode() === 'recommended');
  if (setupReadyState) setupReadyState.textContent = readyMessage;
  document.querySelectorAll('[data-setup-ready]').forEach(element => { element.textContent = readyMessage; });

  const modePreset = conversationModePresets[selectedConversationMode()];
  const mode = modePreset ? modePreset.label : '会議モード';
  const haasSelected = transcriptionBackend?.value === 'haas_ja';
  const qwenSelected = transcriptionBackend?.value === 'qwen3_nemotron' || haasSelected;
  const model = haasSelected
    ? 'Haas-ja v1.0（公式・実験的） + Nemotron 3'
    : qwenSelected
    ? 'Qwen3-ASR + ForcedAligner + Nemotron 3'
    : (selectedOptionText(modelName).split(' \u2014 ')[0] || '\u81ea\u52d5');
  const language = selectedOptionText(languageSelect) || '自動判定';
  const preprocess = selectedOptionText(audioPreprocess).split(' — ')[0] || 'おすすめ';
  const transcriptionDevice = document.querySelector('#transcription-device');
  const diarizationDevice = document.querySelector('#diarization-device');
  const transcriptionHardware = transcriptionDevice && transcriptionDevice.value === 'cuda' ? 'GPU (CUDA)' : 'CPU';
  const diarizationHardware = diarizationDevice && diarizationDevice.value === 'cuda' ? 'GPU (CUDA)' : 'CPU';
  const vocabularyTerms = vocabularyTermsFromInput();
  const recognitionExtras = [];
  if (vocabularyTerms.length && !qwenSelected) recognitionExtras.push(`\u5358\u8a9e\u767b\u9332 ${vocabularyTerms.length}\u8a9e`);
  const fixedSpeakerLabel = isSpeakerCountFixed() ? `話者数 ${fixedSpeakerCountInput.value || '未入力'}人に固定` : '';
  if (fixedSpeakerLabel) recognitionExtras.push(fixedSpeakerLabel);
  const finishExtras = [];
  if (triplePass && triplePass.checked) finishExtras.push('詳細処理');
  const providerLabel = aiProvider && aiProvider.value !== 'none' ? selectedOptionText(aiProvider) : '';
  const finishingPlan = transcriptFinishingPlan();
  const finishInVault = finishingPlan.deferred;
  const finishNow = Object.values(finishingPlan.requested).some(Boolean) || finishingPlan.notation;
  const configuredModel = finishNow ? String(tokenConfigSnapshot[`${aiProvider.value}_model`] || '').trim() : '';
  const finishingState = finishNow ? 'する' : 'しない';
  const finishingModel = finishNow
    ? `${providerLabel} / ${configuredModel || 'モデル未設定'}`
    : '使用モデルなし';
  const finishingDetail = finishInVault
    ? `${finishNow ? '話者を確認 / ' : ''}Obsidianに保存してあとで整える`
    : (finishNow ? [finishingPlan.requested.cleanup ? (finishingPlan.recommendedCleanup ? '必要な箇所を整える' : '全文を整える') : '', finishingPlan.requested.name_extract ? '話者を確認する' : '', finishingPlan.outlineOutput ? 'アウトラインを出力' : '', finishingPlan.notation ? '表記ゆれを統一' : ''].filter(Boolean).join(' / ') : '認識結果をそのまま残す');
  const finishingLabel = `${finishingState} / ${finishingModel}`;
  finishExtras.push(`AI仕上げ: ${finishingState}`);
  if (finishInVault) finishExtras.push('Obsidianに保存してあとで整える');
  if (finishingPlan.compare) finishExtras.push('Jev修正要否比較');
  const emotionEnabled = Boolean(emotionAnalysis && emotionAnalysis.checked);
  if (emotionEnabled) finishExtras.push('感情分析');
  const emotionLabel = emotionEnabled ? (selectedOptionText(emotionModel).split('（')[0] || '実行する') : '実行しない';
  const outputParts = ['TXT', 'JSON'];
  const outputExtras = [];
  if (writeSrt && writeSrt.checked) { outputParts.push('SRT'); outputExtras.push('SRT'); }
  if (burnSubtitledVideo && burnSubtitledVideo.checked) { outputParts.push('字幕付き動画'); outputExtras.push('字幕付き動画'); }
  const extras = [...recognitionExtras, ...finishExtras, ...outputExtras];
  const engineLabel = qwenSelected ? model : `WhisperX / ${model}`;
  const summaryText = `${mode} / ${engineLabel} / ${language} / \u524d\u51e6\u7406: ${preprocess}${extras.length ? ` / ${extras.join(' / ')}` : ''}`;
  const launchText = `\u6587\u5b57\u8d77\u3053\u3057\u65b9\u5f0f ${engineLabel}\u30fb${transcriptionHardware} / \u8a71\u8005\u5206\u96e2 ${diarizationHardware} / AI\u4ed5\u4e0a\u3052 ${finishingState}${finishInVault ? '\uff08\u3042\u3068\u3067Obsidian\uff09' : ''}`;
  if (setupSummary) setupSummary.textContent = launchText;
  document.querySelectorAll('[data-setup-summary]').forEach(element => { element.textContent = summaryText; });

  const selectedFile = inputFile && inputFile.files && inputFile.files[0];
  const directPath = sourcePath ? sourcePath.value.trim() : '';
  const sourceLabel = selectedFile
    ? selectedFile.name
    : (directPath ? directPath.split(/[\\/]/).pop() : '未選択');
  const setText = (selector, value) => {
    document.querySelectorAll(selector).forEach(element => { element.textContent = value; });
  };
  setText('[data-choice-transcription-device]', transcriptionHardware);
  setText('[data-choice-recognition-model]', `\u6587\u5b57\u8d77\u3053\u3057\u65b9\u5f0f ${engineLabel}`);
  setText('[data-choice-recognition-detail]', `話者分離 ${diarizationHardware}${fixedSpeakerLabel ? ` / ${fixedSpeakerLabel}` : ''} / ${language} / 前処理 ${preprocess}`);
  setText('[data-settings-value="vocabulary"]', vocabularyTerms.length ? `${vocabularyTerms.length}語を登録` : '未登録');
  setText('[data-choice-finishing-state]', finishingState);
  setText('[data-choice-finishing-model]', finishingModel);
  setText('[data-choice-finishing-detail]', finishingDetail);
  document.querySelectorAll('[data-choice-finishing-state]').forEach(element => element.classList.toggle('is-off', !finishNow));
  document.querySelectorAll('[data-open-panel="finishing"]').forEach(element => element.dataset.active = finishNow ? 'true' : 'false');
  setText('[data-settings-value="emotion"]', emotionLabel);
  setText('[data-settings-value="output"]', outputParts.join(' / '));
  setText('[data-review-source]', sourceLabel);
  setText('[data-review-transcription-compact]', `認識モデル ${model}・${transcriptionHardware} / 話者分離 ${diarizationHardware}`);
  setText('[data-review-transcription]', `認識モデル: ${model} / ${transcriptionHardware}`);
  setText('[data-review-diarization]', `話者分離: ${qwenSelected ? 'Nemotron 3' : 'pyannote.audio'} / ${diarizationHardware}${fixedSpeakerLabel ? ` / ${fixedSpeakerLabel}` : ''}`);
  setText('[data-review-finish]', `AI仕上げ ${finishingLabel}${finishInVault ? ' / Obsidianに保存してあとで整える' : ''}${emotionEnabled ? ` / 感情分析 ${emotionLabel}` : ''}`);
  setText('[data-review-output]', outputParts.join(' / '));
  setText('[data-flow-detail="1"]', hasSource ? sourceLabel : '未選択');
  setText('[data-flow-detail="2"]', `${mode} / ${model} / ${language}`);
  setText('[data-flow-detail="3"]', readiness.ready ? '開始時にモデル確認' : hasSource ? '開始前に要確認' : 'ファイルを選択');

  if (startButton) startButton.disabled = jobRunning || !readiness.ready;
  renderMobileWizard();
}

function isVideoSource(value) {
  return /\.(mp4|m4v|mov|mkv)$/i.test(String(value || '').trim().split(/[?#]/)[0]);
}

function hideSourcePreview() {
  window.clearTimeout(thumbnailTimer);
  thumbnailRequestId += 1;
  if (sourceThumbnailController) sourceThumbnailController.abort();
  sourceThumbnailController = null;
  if (sourceThumbnailObjectUrl) URL.revokeObjectURL(sourceThumbnailObjectUrl);
  sourceThumbnailObjectUrl = null;
  if (sourceThumbnail) {
    sourceThumbnail.removeAttribute('src');
    sourceThumbnail.hidden = true;
  }
  if (sourcePreview) {
    sourcePreview.classList.remove('loaded');
    sourcePreview.hidden = true;
  }
  if (sourcePreviewMessage) sourcePreviewMessage.textContent = '';
}

async function showSourceThumbnail(path, name = '') {
  if (!sourcePreview || !sourceThumbnail || !sourcePreviewMessage) return;
  const value = String(path || '').trim();
  if (!isVideoSource(value)) {
    hideSourcePreview();
    return;
  }
  const requestId = ++thumbnailRequestId;
  if (sourceThumbnailController) sourceThumbnailController.abort();
  sourceThumbnailController = new AbortController();
  if (sourceThumbnailObjectUrl) URL.revokeObjectURL(sourceThumbnailObjectUrl);
  sourceThumbnailObjectUrl = null;
  sourcePreview.hidden = false;
  sourcePreview.classList.remove('loaded');
  sourceThumbnail.hidden = true;
  sourcePreviewMessage.textContent = `${name || value.split(/[\\/]/).pop()} のサムネイルを作成しています…`;
  sourceThumbnail.onload = () => {
    if (requestId !== thumbnailRequestId) return;
    if (sourceThumbnailObjectUrl) URL.revokeObjectURL(sourceThumbnailObjectUrl);
    sourceThumbnailObjectUrl = null;
    sourcePreview.classList.add('loaded');
    sourceThumbnail.hidden = false;
    sourcePreviewMessage.textContent = name || value;
  };
  const showThumbnailError = () => {
    if (requestId !== thumbnailRequestId) return;
    sourcePreview.classList.remove('loaded');
    sourceThumbnail.hidden = true;
    sourcePreviewMessage.textContent = 'サムネイルを作成できませんでした。動画として開けるファイルか確認してください。';
  };
  sourceThumbnail.onerror = showThumbnailError;
  try {
    const response = await apiFetch('/api/source-thumbnail', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path: value}),
      cache: 'no-store',
      signal: sourceThumbnailController.signal
    });
    if (!response.ok) throw new Error('thumbnail request failed');
    const blob = await response.blob();
    if (requestId !== thumbnailRequestId) return;
    sourceThumbnailObjectUrl = URL.createObjectURL(blob);
    sourceThumbnail.src = sourceThumbnailObjectUrl;
  } catch (error) {
    if (error && error.name === 'AbortError') return;
    showThumbnailError();
  } finally {
    if (requestId === thumbnailRequestId) sourceThumbnailController = null;
  }
}

function scheduleSourceThumbnail(path) {
  window.clearTimeout(thumbnailTimer);
  const value = String(path || '').trim();
  if (!value || !isVideoSource(value)) {
    hideSourcePreview();
    return;
  }
  thumbnailTimer = window.setTimeout(() => showSourceThumbnail(value), 450);
}

function fallbackSpeaker(label) {
  if (!label || label === 'UNKNOWN') return '話者（未判定）';
  const match = String(label).match(/_(\d+)$/);
  return match ? `話者 ${Number(match[1]) + 1}` : label;
}

function hasUnsavedAnalysisChanges() {
  return Boolean(analysisState.dirty || preparationDirty);
}

function routeHash(view, id = '') {
  const encoded = id ? encodeURIComponent(String(id)) : '';
  if (view === 'item') return `#/data/${encoded}`;
  if (view === 'analysis' && encoded) return `#/analysis/${encoded}`;
  return viewRouteHashes[view] || '#/new';
}

function parseRouteHash(hash) {
  const parts = String(hash || '').replace(/^#\/?/, '').split('/').filter(Boolean).map(part => {
    try { return decodeURIComponent(part); } catch (_) { return part; }
  });
  const [head, id = ''] = parts;
  if (head === 'data' && id) return {view: 'item', itemId: id};
  if (head === 'data') return {view: 'library', itemId: ''};
  if (head === 'analysis') return {view: 'analysis', itemId: id};
  if (head === 'speakers') return {view: 'speakers', itemId: ''};
  if (Object.hasOwn(viewRouteHashes, head)) return {view: head, itemId: ''};
  return null;
}

function syncRouteHash(hash, {replace = false} = {}) {
  currentRouteHash = hash;
  if (window.location.hash === hash) return;
  try {
    if (replace) window.history.replaceState(null, '', hash);
    else window.history.pushState(null, '', hash);
  } catch (_) {
    // Screens still switch when the history API is unavailable.
  }
}

// Every move between screens passes these checks, so unsaved edits are never
// dropped without asking (UX-30).
function confirmLeave({target, itemId = '', analysisItemId = ''}) {
  const resultVisible = resultCard && !resultCard.hidden;
  const sameItem = target === 'item' && itemId && currentJob && String(currentJob.id) === String(itemId);
  const leavingCurrentResult = currentJobDirty && !sameItem && (resultVisible || target === 'item');
  if (leavingCurrentResult && !window.confirm('文字起こし、会話プロファイル、または話者連携に未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  const leavingSpeakerManagement = target !== 'speakers'
    && speakerRegistryCard
    && !speakerRegistryCard.hidden
    && speakerRegistryDirty;
  if (leavingSpeakerManagement && !window.confirm('話者管理に未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  const requestedAnalysisId = String(analysisItemId || '').trim();
  const analysisVisible = analysisCard && !analysisCard.hidden;
  const switchingAnalysisItem = target === 'analysis' && requestedAnalysisId && requestedAnalysisId !== analysisState.itemId;
  const leavingAnalysis = hasUnsavedAnalysisChanges()
    && (switchingAnalysisItem || (analysisVisible && target !== 'analysis'));
  if (leavingAnalysis && !window.confirm('分析設定・手動コード・準備記録に未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  return true;
}

function loadAnalysisView(requestedItemId, {discardDirty = false} = {}) {
  if (!analysisCard) return;
  if (requestedItemId && analysisCatalogLoaded) {
    if (requestedItemId !== analysisState.itemId || !analysisState.data) {
      loadAnalysisItem(requestedItemId, {discardDirty});
    } else {
      if (analysisItemSelect) analysisItemSelect.value = requestedItemId;
      const executionView = document.querySelector('#analysis-execution-view');
      if (executionView) executionView.hidden = true;
      renderAnalysisWorkspace();
      onContentAnalysisLoaded();
    }
    return;
  }
  if (requestedItemId) {
    analysisState.itemId = requestedItemId;
    analysisState.data = null;
    if (analysisItemSelect) analysisItemSelect.value = requestedItemId;
  }
  loadAnalysisCatalog();
}

function setActiveNavigation(view) {
  [
    [showNewButton, view === 'new'],
    [showLibraryButton, view === 'library' || view === 'item'],
    [showAnalysisButton, view === 'analysis'],
    [showSpeakersButton, view === 'speakers'],
    ...priorDataButtons.map(button => [button, view === button.dataset.priorView])
  ].forEach(([button, active]) => {
    if (!button) return;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
    button.tabIndex = active ? 0 : -1;
  });
  [
    [showLibraryListButton, view === 'library'],
    [showLibraryAnalysisButton, view === 'analysis']
  ].forEach(([button, active]) => {
    if (!button) return;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
}

function showView(view, {analysisItemId = '', itemId = '', force = false, replace = false} = {}) {
  const target = view === 'item' || Object.hasOwn(viewRouteHashes, view) ? view : 'new';
  const requestedAnalysisId = String(analysisItemId || '').trim();
  if (target === 'item' && !currentJob) return false;
  const targetItemId = target === 'item' ? String(itemId || currentJob.id) : '';
  if (!force && !confirmLeave({target, itemId: targetItemId, analysisItemId: requestedAnalysisId})) return false;
  const resultVisible = resultCard && !resultCard.hidden;
  const switchingAnalysisItem = target === 'analysis' && requestedAnalysisId && requestedAnalysisId !== analysisState.itemId;
  const contextChanged = document.body.dataset.view !== target || switchingAnalysisItem;
  const closedFixedViewer = contextChanged && typeof closeFixedAnalysisViewer === 'function' && closeFixedAnalysisViewer();
  const closedAnalysisDialog = contextChanged && typeof closeAnalysisExecutionDialog === 'function' && closeAnalysisExecutionDialog();
  const closedOrchestrationDialog = contextChanged && typeof closeAnalysisOrchestrationDialogs === 'function' && closeAnalysisOrchestrationDialogs();
  if (contextChanged) {
    analysisNavigationGeneration += 1;
    analysisSaveOwner = null;
    analysisSaveInProgress = false;
    analysisTermRunRequested = false;
  }
  resultRequestSequence += 1;
  // A previous view's save cannot own this view's button or messages.
  if (saveButton) saveButton.disabled = false;
  if (resultVisible && currentJobDirty && target !== 'item') setCurrentJobDirty(false);
  if (target !== 'item' && mediaPlayer) mediaPlayer.pause();
  if (createView) createView.hidden = target !== 'new';
  if (runningView) runningView.hidden = target !== 'running';
  if (processedDataHub) processedDataHub.hidden = !['library', 'analysis'].includes(target);
  if (libraryCard) libraryCard.hidden = target !== 'library';
  if (analysisCard) analysisCard.hidden = target !== 'analysis';
  if (speakerRegistryCard) speakerRegistryCard.hidden = target !== 'speakers';
  if (resultCard) resultCard.hidden = target !== 'item';
  priorDataPanels.forEach(panel => { panel.hidden = panel.dataset.priorPanel !== target; });
  document.body.dataset.view = target;
  setActiveNavigation(target);
  if (closedFixedViewer || closedAnalysisDialog || closedOrchestrationDialog) {
    const navigation = target === 'analysis' ? showAnalysisButton : target === 'speakers' ? showSpeakersButton
      : priorDataButtons.find(button => button.dataset.priorView === target)
        || (target === 'new' ? showNewButton : showLibraryButton);
    if (navigation?.isConnected && !navigation.closest('[hidden]')) navigation.focus();
  }
  if (target === 'analysis') loadAnalysisView(requestedAnalysisId, {discardDirty: force || Boolean(switchingAnalysisItem)});
  if (target === 'library') loadLibrary();
  if (target === 'speakers' && speakerRegistryCard) loadSpeakerRegistry();
  if (target === 'folders') loadLibraryGroupManager();
  if (target === 'new') {
    renderMobileWizard();
    syncCreateViewState();
  }
  if (target === 'running') syncCreateViewState();
  const hashId = target === 'item'
    ? targetItemId
    : (target === 'analysis' ? (requestedAnalysisId || analysisState.itemId) : '');
  syncRouteHash(routeHash(target, hashId), {replace});
  document.dispatchEvent(new CustomEvent('gurumoji-view-change', {detail: {view: target}}));
  return true;
}

function openAnalysisForItem(itemId) {
  const targetItemId = String(itemId || '').trim();
  if (!targetItemId) return false;
  const returning = analysisEvidenceReturn?.itemId === targetItemId;
  const sameRevision = currentJob && analysisState.data
    && Number(currentJob.revision_count) === Number(analysisState.data.item.revision_count);
  if (returning && sameRevision) {
    analysisCatalog = analysisEvidenceReturn.catalog;
    analysisCatalogLoaded = true;
  }
  const opened = showView('analysis', {analysisItemId: targetItemId});
  if (opened && returning && sameRevision) {
    restoreAnalysisEvidencePosition();
    pollContentInsights();
  }
  return opened;
}

function openResultDestination(destination) {
  const target = String(destination || '').trim();
  if (target === 'analysis') return openAnalysisForItem(currentJobId);
  if (target === 'library' || target === 'speakers') return showView(target);
  return false;
}

// Tabs inside one record's workspace (UX-02): editing, conversation, summary, files.
function setItemTab(name) {
  const target = itemPanels.some(panel => panel.dataset.itemPanel === name) ? name : 'transcript';
  activeItemTab = target;
  itemPanels.forEach(panel => { panel.hidden = panel.dataset.itemPanel !== target; });
  itemTabButtons.forEach(button => {
    const active = button.dataset.itemTab === target;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
}

// 実行状況は独立した画面で管理し、ヘッダーから戻れるようにする。
function updateJobChip(job) {
  if (!jobChip || !jobChipLabel) return;
  const status = job ? String(job.status || '') : '';
  const active = Boolean(progressCard && !progressCard.hidden)
    && (jobRunning || ['admitting', 'queued', 'running', 'committing'].includes(status));
  const pendingCompleted = Boolean(completedJob && job && completedJob.id === job.id && status === 'completed');
  const failed = ['failed', 'cancelled'].includes(status) && Boolean(progressCard && !progressCard.hidden);
  jobChip.hidden = !(active || pendingCompleted || failed || queuedJobCount > 0);
  jobChip.classList.toggle('is-active', active);
  jobChip.classList.toggle('is-complete', pendingCompleted);
  jobChip.setAttribute('aria-controls', pendingCompleted && !queuedJobCount ? 'result-card' : 'running-view');
  jobChip.classList.toggle('has-error', failed);
  const titles = {admitting: '受付中', queued: '開始待ち', running: '文字起こし中', committing: '結果を保存中', failed: 'エラー', cancelled: '中止しました'};
  if (active) jobChipLabel.textContent = `${titles[status] || '処理中'} ${Number(job?.progress || 0)}%`;
  else if (queuedJobCount > 0) jobChipLabel.textContent = `待機中 ${queuedJobCount}件`;
  else if (pendingCompleted) jobChipLabel.textContent = '文字起こしが完了 — 結果を開く';
  else jobChipLabel.textContent = titles[status] || '処理状況';
  if (active && queuedJobCount > 0) jobChipLabel.textContent += ` ・待機 ${queuedJobCount}件`;
}

function syncCreateViewState() {
  const progressVisible = Boolean(progressCard && !progressCard.hidden);
  if (form) form.hidden = false;
  const empty = document.querySelector('#job-empty-state');
  if (empty) empty.hidden = progressVisible || queuedJobCount > 0;
  const notice = document.querySelector('#job-resume-notice');
  if (notice) notice.hidden = !(progressVisible || queuedJobCount > 0);
  document.querySelectorAll('[data-open-job]').forEach(button => {
    button.textContent = completedJob && !queuedJobCount ? '結果を開く' : '実行状況を開く';
    button.setAttribute('aria-controls', completedJob && !queuedJobCount ? 'result-card' : 'running-view');
  });
  const message = document.querySelector('#job-resume-message');
  if (message) message.textContent = jobRunning
    ? '文字起こしを実行中です。画面を移動しても処理は続きます。追加のファイルは実行状況画面から待機登録できます。'
    : queuedJobCount > 0 ? `待機中の処理が${queuedJobCount}件あります。実行状況画面から確認できます。`
    : completedJob ? '文字起こしが完了しました。結果を確認できます。' : '前回の文字起こしの処理状況を確認できます。';
  const resultButton = document.querySelector('#progress-open-result');
  if (resultButton) resultButton.hidden = !completedJob || queuedJobCount > 0;
  if (cancelButton) cancelButton.hidden = !jobRunning;
  const dismiss = document.querySelector('#progress-dismiss');
  if (dismiss) dismiss.hidden = jobRunning || !progressVisible;
  updateJobChip(lastProgressJob);
}

function showProgressCard({scroll = false, open = false} = {}) {
  if (!progressCard) return;
  progressCard.hidden = false;
  syncCreateViewState();
  if (open) showView('running');
  if (scroll && runningView && !runningView.hidden) {
    progressCard.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
  }
}

function openJobProgress() {
  if (completedJob && !queuedJobCount) {
    const job = completedJob;
    if (!confirmLeave({target: 'item', itemId: job.id})) return;
    completedJob = null;
    renderResult(job);
    return;
  }
  if (showView('running') && progressCard && !progressCard.hidden) {
    progressCard.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
  }
}

// Tablists follow the WAI-ARIA tabs pattern (UX-23): one Tab stop per list on the
// selected tab, and arrow/Home/End keys move focus between tabs. Activation stays
// on Enter/Space because switching views can ask about unsaved changes.
function syncTabStops() {
  document.querySelectorAll('[role="tablist"]').forEach(tablist => {
    const tabs = [...tablist.querySelectorAll('[role="tab"]')];
    const selected = tabs.find(tab => tab.getAttribute('aria-selected') === 'true') || tabs[0];
    tabs.forEach(tab => tab.setAttribute('tabindex', tab === selected ? '0' : '-1'));
  });
}

function newLocalSpeakerId() {
  return self.crypto && self.crypto.randomUUID
    ? self.crypto.randomUUID().replaceAll('-', '')
    : `speaker_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function blankSpeakerRecord() {
  return {
    id: newLocalSpeakerId(),
    participant_code: '',
    display_name: '',
    pseudonym: '',
    default_role: 'participant',
    organization: '',
    department: '',
    job_title: '',
    confidentiality_status: 'unknown',
    tags: [],
    attributes: {},
    notes: '',
    active: true
  };
}

function attributesToText(attributes) {
  return Object.entries(attributes || {}).map(([key, value]) => `${key}=${value}`).join('; ');
}

function textToAttributes(value) {
  const attributes = {};
  String(value || '').split(/[;\n]+/).forEach(part => {
    const separator = part.includes('=') ? '=' : ':';
    const index = part.indexOf(separator);
    if (index <= 0) return;
    const key = part.slice(0, index).trim();
    const itemValue = part.slice(index + 1).trim();
    if (key) attributes[key] = itemValue;
  });
  return attributes;
}

function speakerSurveyQuestionKeys(records = speakerRegistry) {
  const keys = new Set();
  records.forEach(record => {
    const attributes = record && typeof record.attributes === 'object' ? record.attributes : {};
    Object.keys(attributes || {}).forEach(key => {
      const clean = String(key || '').trim();
      if (clean) keys.add(clean);
    });
  });
  return [...keys].sort((a, b) => a.localeCompare(b, 'ja', {numeric: true, sensitivity: 'base'}));
}

function speakerSurveyAnswer(record, question) {
  const attributes = record && typeof record.attributes === 'object' ? record.attributes : {};
  return String((attributes || {})[question] ?? '').trim();
}

function speakerSurveyQuestionSummary(records, question) {
  const counts = new Map();
  const answeredRecords = [];
  records.forEach(record => {
    const answer = speakerSurveyAnswer(record, question);
    if (!answer) return;
    answeredRecords.push(record);
    counts.set(answer, (counts.get(answer) || 0) + 1);
  });
  const values = [...counts.entries()]
    .map(([value, count]) => ({value, count}))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value, 'ja', {numeric: true}));
  return {
    question,
    answeredRecords,
    answered: answeredRecords.length,
    missing: Math.max(0, records.length - answeredRecords.length),
    values
  };
}

function speakerSurveyNumericValue(value) {
  const normalized = String(value || '').trim().normalize('NFKC').replaceAll(',', '');
  if (/^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$/.test(normalized)) return Number(normalized);
  const scale = normalized.match(/^([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*[:：]/);
  return scale ? Number(scale[1]) : null;
}

function speakerSurveyNumericSummary(records, question) {
  const values = records
    .map(record => speakerSurveyNumericValue(speakerSurveyAnswer(record, question)))
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  const answered = records.filter(record => speakerSurveyAnswer(record, question)).length;
  if (values.length < 2 || values.length < answered * 0.8) return null;
  const middle = Math.floor(values.length / 2);
  const median = values.length % 2 ? values[middle] : (values[middle - 1] + values[middle]) / 2;
  return {
    count: values.length,
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
    median,
    minimum: values[0],
    maximum: values[values.length - 1]
  };
}

function speakerSurveyCorrelation(records, questionA, questionB) {
  const pairs = records.map(record => [
    speakerSurveyNumericValue(speakerSurveyAnswer(record, questionA)),
    speakerSurveyNumericValue(speakerSurveyAnswer(record, questionB))
  ]).filter(([a, b]) => Number.isFinite(a) && Number.isFinite(b));
  if (pairs.length < 3) return null;
  const meanA = pairs.reduce((sum, pair) => sum + pair[0], 0) / pairs.length;
  const meanB = pairs.reduce((sum, pair) => sum + pair[1], 0) / pairs.length;
  const numerator = pairs.reduce((sum, pair) => sum + (pair[0] - meanA) * (pair[1] - meanB), 0);
  const denominatorA = pairs.reduce((sum, pair) => sum + (pair[0] - meanA) ** 2, 0);
  const denominatorB = pairs.reduce((sum, pair) => sum + (pair[1] - meanB) ** 2, 0);
  const denominator = Math.sqrt(denominatorA * denominatorB);
  if (!denominator) return null;
  return {count: pairs.length, coefficient: numerator / denominator};
}

function scheduleSpeakerSurveyAnalysis() {
  window.clearTimeout(speakerSurveyAnalysisTimer);
  speakerSurveyAnalysisTimer = window.setTimeout(renderSpeakerSurveyAnalysis, 160);
}

function appendSpeakerSurveyBar(container, label, count, total, maximum) {
  const row = analysisElement('div', 'speaker-survey-bar');
  const heading = analysisElement('div');
  heading.append(
    analysisElement('strong', '', label),
    analysisElement('span', '', `${count}人 / ${total ? (100 * count / total).toFixed(1) : '0.0'}%`)
  );
  const track = analysisElement('div', 'speaker-survey-bar-track');
  const fill = analysisElement('i');
  fill.style.width = `${maximum ? (100 * count / maximum).toFixed(2) : 0}%`;
  track.append(fill);
  row.append(heading, track);
  container.append(row);
}

function buildSpeakerSurveyCompleteness(records, questions) {
  const panel = analysisElement('section', 'speaker-survey-panel');
  panel.append(
    analysisElement('h4', '', '質問別の回答率'),
    analysisElement('p', 'speaker-survey-help', '')
  );
  panel.lastChild.textContent = '回答漏れの確認と、分析対象にする質問の選択ができます。';
  const list = analysisElement('div', 'speaker-survey-completeness');
  questions
    .map(question => speakerSurveyQuestionSummary(records, question))
    .sort((a, b) => b.answered - a.answered || a.question.localeCompare(b.question, 'ja'))
    .forEach(summary => {
      const button = analysisElement('button', summary.question === speakerSurveyAnalysisState.primaryQuestion ? 'active' : '');
      button.type = 'button';
      button.setAttribute('aria-pressed', String(summary.question === speakerSurveyAnalysisState.primaryQuestion));
      const text = analysisElement('span');
      text.append(
        analysisElement('strong', '', summary.question),
        analysisElement('small', '', `${summary.answered} / ${records.length}人`)
      );
      const track = analysisElement('i');
      const fill = analysisElement('b');
      fill.style.width = `${records.length ? (100 * summary.answered / records.length).toFixed(2) : 0}%`;
      track.append(fill);
      button.append(text, track);
      button.addEventListener('click', () => {
        speakerSurveyAnalysisState.primaryQuestion = summary.question;
        speakerSurveyAnalysisState.answerFilter = '';
        if (speakerSurveyAnalysisState.secondaryQuestion === summary.question) {
          speakerSurveyAnalysisState.secondaryQuestion = questions.find(item => item !== summary.question) || '';
        }
        renderSpeakerSurveyAnalysis();
      });
      list.append(button);
    });
  panel.append(list);
  return panel;
}

function buildSpeakerSurveyCrosstab(records, primaryQuestion, secondaryQuestion) {
  const panel = analysisElement('section', 'speaker-survey-panel speaker-survey-crosstab');
  panel.append(
    analysisElement('h4', '', '2項目クロス集計'),
    analysisElement('p', 'speaker-survey-help', `${primaryQuestion} × ${secondaryQuestion} の組み合わせ人数と行内割合です。`)
  );
  const primary = speakerSurveyQuestionSummary(records, primaryQuestion);
  const secondary = speakerSurveyQuestionSummary(records, secondaryQuestion);
  const rowValues = primary.values.slice(0, 12).map(item => item.value);
  const columnValues = secondary.values.slice(0, 10).map(item => item.value);
  if (!rowValues.length || !columnValues.length) {
    panel.append(analysisElement('p', 'analysis-no-data', 'クロス集計できる回答がありません。'));
    return panel;
  }
  const wrap = analysisElement('div', 'speaker-survey-table-wrap');
  const table = document.createElement('table');
  table.className = 'speaker-survey-table';
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  headRow.append(analysisElement('th', '', primaryQuestion));
  columnValues.forEach(value => headRow.append(analysisElement('th', '', value)));
  headRow.append(analysisElement('th', '', '合計'));
  head.append(headRow);
  const body = document.createElement('tbody');
  rowValues.forEach(rowValue => {
    const row = document.createElement('tr');
    row.append(analysisElement('th', '', rowValue));
    const rowTotal = records.filter(record => speakerSurveyAnswer(record, primaryQuestion) === rowValue).length;
    columnValues.forEach(columnValue => {
      const count = records.filter(record => (
        speakerSurveyAnswer(record, primaryQuestion) === rowValue
        && speakerSurveyAnswer(record, secondaryQuestion) === columnValue
      )).length;
      const cell = analysisElement('td', count ? 'has-value' : '', count
        ? `${count}（${rowTotal ? (100 * count / rowTotal).toFixed(0) : 0}%）`
        : '—');
      if (count) cell.style.setProperty('--survey-cell-strength', String(count / Math.max(1, rowTotal)));
      row.append(cell);
    });
    row.append(analysisElement('td', 'total', String(rowTotal)));
    body.append(row);
  });
  table.append(head, body);
  wrap.append(table);
  panel.append(wrap);
  if (primary.values.length > rowValues.length || secondary.values.length > columnValues.length) {
    panel.append(analysisElement('p', 'speaker-survey-note', '表示量を抑えるため、回答数が多い選択肢を優先して表示しています。'));
  }
  const correlation = speakerSurveyCorrelation(records, primaryQuestion, secondaryQuestion);
  if (correlation) {
    const correlationBox = analysisElement('div', 'speaker-survey-correlation');
    correlationBox.append(
      analysisElement('span', '', '数値回答の相関'),
      analysisElement('strong', '', `r = ${correlation.coefficient.toFixed(3)}`),
      analysisElement('small', '', `n = ${correlation.count}。関連の強さを示す記述値で、因果関係は示しません。`)
    );
    panel.append(correlationBox);
  }
  return panel;
}
