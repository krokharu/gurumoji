const form = document.querySelector('#job-form');
const processedDataHub = document.querySelector('#processed-data-hub');
const libraryCard = document.querySelector('#library-card');
const speakerRegistryCard = document.querySelector('#speaker-registry-card');
const analysisCard = document.querySelector('#analysis-card');
const analysisItemSelect = document.querySelector('#analysis-item-select');
const analysisDesktopContent = document.querySelector('#analysis-desktop-content');
const analysisMobileContent = document.querySelector('#analysis-mobile-content');
const speakerRegistryBody = document.querySelector('#speaker-registry-body');
const speakerRegistryList = document.querySelector('#speaker-registry-list');
const speakerRegistrySaveButton = document.querySelector('#save-speakers-button');
const speakerRegistrySaveState = document.querySelector('#registry-save-state');
const sourcePath = document.querySelector('#source-path');
const inputFile = document.querySelector('#input-file');
const browsePathButton = document.querySelector('#browse-path-button');
const pathDetail = document.querySelector('#path-detail');
const pathError = document.querySelector('#path-error');
const fileDropZone = document.querySelector('#file-drop-zone');
const sourcePreview = document.querySelector('#source-preview');
const sourceThumbnail = document.querySelector('#source-thumbnail');
const sourcePreviewMessage = document.querySelector('#source-preview-message');
const formError = document.querySelector('#form-error');
const startButton = document.querySelector('#start-button');
const progressCard = document.querySelector('#progress-card');
const resultCard = document.querySelector('#result-card');
const cancelButton = document.querySelector('#cancel-button');
const saveButton = document.querySelector('#save-button');
const newButton = document.querySelector('#new-button');
const resultAnalysisButton = document.querySelector('#result-analysis-button');
const resultContextName = document.querySelector('#result-context-name');
const resultContextButtons = [...document.querySelectorAll('[data-result-destination]')];
const deleteRecordButton = document.querySelector('#delete-record-button');
const boostQuietSpeech = document.querySelector('#boost-quiet-speech');
const triplePass = document.querySelector('#triple-pass');
const vadOnset = document.querySelector('#vad-onset');
const vadOffset = document.querySelector('#vad-offset');
const emotionAnalysis = document.querySelector('#emotion-analysis');
const emotionModel = document.querySelector('#emotion-model');
const aiProvider = document.querySelector('#ai-provider');
const modelName = document.querySelector('#model-name');
const languageSelect = document.querySelector('[name="language"]');
const audioPreprocess = document.querySelector('[name="audio_preprocess"]');
const writeSrt = document.querySelector('[name="write_srt"]');
const burnSubtitledVideo = document.querySelector('[name="burn_subtitled_video"]');
const setupReadyState = document.querySelector('#setup-ready-state');
const setupSummary = document.querySelector('#setup-summary');
const quickFlowItems = [...document.querySelectorAll('.quick-flow li')];
const mobileStepBack = document.querySelector('#mobile-step-back');
const mobileStepNext = document.querySelector('#mobile-step-next');
const mobileStepNumber = document.querySelector('#mobile-step-number');
const mobileStepTitle = document.querySelector('#mobile-step-title');
const mobileStepDescription = document.querySelector('#mobile-step-description');
const mobileNavStep = document.querySelector('#mobile-nav-step');
const mobileNavLabel = document.querySelector('#mobile-nav-label');
const mobileStepDots = [...document.querySelectorAll('[data-mobile-dot]')];
const mobileStepSections = [...document.querySelectorAll('[data-mobile-step]')];
const mobileWizardMedia = window.matchMedia('(max-width: 959px)');
const cleanTranscript = document.querySelector('#clean-transcript');
const detectNames = document.querySelector('#detect-names');
const createOutline = document.querySelector('#create-outline');
const speakerIdentityProvider = document.querySelector('#speaker-identity-provider');
const rerunSpeakerIdentificationButton = document.querySelector('#rerun-speaker-identification');
const speakerIdentityStatus = document.querySelector('#speaker-identity-status');
const showLibraryButton = document.querySelector('#show-library-button');
const showLibraryListButton = document.querySelector('#show-library-list-button');
const showLibraryAnalysisButton = document.querySelector('#show-library-analysis-button');
const showNewButton = document.querySelector('#show-new-button');
const showSpeakersButton = document.querySelector('#show-speakers-button');
const segmentEditor = document.querySelector('#segment-editor');
const speakerEditor = document.querySelector('#speaker-editor');
const mediaReview = document.querySelector('#media-review');
const mediaPlayerHost = document.querySelector('#media-player-host');
const bootSplash = document.querySelector('#boot-splash');
const aiOptionInputs = [cleanTranscript, detectNames, createOutline].filter(Boolean);
const aiModelDialog = document.querySelector('#ai-model-dialog');
const aiModelForm = document.querySelector('#ai-model-form');
const aiModelProviderLabel = document.querySelector('#ai-model-provider-label');
const aiModelCurrent = document.querySelector('#ai-model-current');
const aiModelSearch = document.querySelector('#ai-model-search');
const aiModelSelect = document.querySelector('#ai-model-select');
const aiModelDescription = document.querySelector('#ai-model-description');
const aiModelError = document.querySelector('#ai-model-error');
const saveAiModelButton = document.querySelector('#save-ai-model-button');

let tokenConfigSnapshot = {};
let aiModelCatalog = [];
let activeAiModelProvider = '';

let currentJobId = null;
let currentJob = null;
let pollTimer = null;
let systemActivityTimer = null;
let systemActivityController = null;
let pollFailureCount = 0;
let jobFlowGeneration = 0;
let mediaPlayer = null;
let selectedSegmentId = null;
let playbackStopAt = null;
let libraryTimer = null;
let thumbnailTimer = null;
let thumbnailRequestId = 0;
let sourceThumbnailController = null;
let sourceThumbnailObjectUrl = null;
let jobRunning = false;
let currentJobDirty = false;
let currentJobMutationGeneration = 0;
let currentMobileStep = 1;
let speakerRegistry = [];
let speakerRegistryDeletedIds = new Set();
let speakerRegistryLoaded = false;
let speakerRegistryRevision = 0;
let speakerRegistryDirty = false;
let speakerRegistryMutationGeneration = 0;
let speakerRegistrySaveInProgress = false;
let speakerSurveyAnalysisTimer = null;
const speakerSurveyAnalysisState = {
  primaryQuestion: '',
  secondaryQuestion: '',
  answerFilter: '',
  includeInactive: false
};
let libraryRequestController = null;
let libraryRequestSequence = 0;
let trainingStatusLoaded = false;
let analysisCatalogLoaded = false;
let analysisCatalog = [];
let analysisRequestController = null;
let analysisRequestSequence = 0;
let analysisSaveInProgress = false;
let analysisMutationGeneration = 0;
let analysisInitialSectionApplied = false;
let analysisNavigationFrame = 0;
let analysisTermRunRequested = false;
const analysisState = {
  itemId: '',
  mode: 'automatic',
  data: null,
  config: {},
  annotations: {},
  dirty: false,
  segmentQuery: '',
  annotatedOnly: false,
  automaticScope: 'overall',
  speakerSort: 'speaking_desc',
  speakerAttributeFilter: '',
  selectedSpeaker: ''
};
const activeJobStorageKey = 'gurumoji.activeJobId';
const pendingSubmissionStorageKey = 'gurumoji.pendingSubmission';
const pollBaseDelayMs = 1200;
const pollMaxDelayMs = 30000;
const systemActivityDelayMs = 1200;
const submitRecoveryMaxAttempts = 6;
let browserFilePickerOnly = browsePathButton
  ? browsePathButton.dataset.pickerMode === 'browser'
  : false;

const speakerRoleLabels = {
  participant: '参加者',
  moderator: '司会・モデレーター',
  facilitator: '進行・ファシリテーター',
  assistant_moderator: '副司会',
  observer: '観察者',
  note_taker: '記録者・書記',
  interviewer: 'インタビュアー',
  chair: '議長',
  presenter: '発表者',
  decision_maker: '意思決定者',
  attendee: '出席者',
  guest: 'ゲスト',
  other: 'その他'
};
const consentLabels = {
  unknown: '未確認',
  pending: '確認中',
  granted: '同意済み',
  declined: '非同意',
  not_required: '不要'
};
const attendanceLabels = {
  unknown: '未確認',
  planned: '予定',
  attended: '参加',
  absent: '欠席',
  left_early: '途中退出',
  remote: 'オンライン'
};
const speakerThemeColors = [
  '#E86A5A', '#2F80ED', '#27AE60', '#9B51E0', '#F2994A', '#00A6A6',
  '#EB5FA7', '#7A6FBE', '#6C8B3C', '#C47F17', '#3E8ED0', '#B85C5C',
  '#D1495B', '#00798C', '#6A4C93', '#8F5B34', '#B33C86', '#4D9078',
  '#E4572E', '#577590'
];

const mobileStepContent = {
  1: {title: 'ファイルを選ぶ', description: '端末の音声・動画を1つ選択します', label: 'ファイル'},
  2: {title: '認識を設定', description: 'おすすめ設定を確認し、必要な項目だけ変更します', label: '認識設定'},
  3: {title: '仕上げを選ぶ', description: 'AI仕上げと感情分析は必要な場合だけ有効にします', label: '仕上げ'},
  4: {title: '確認して開始', description: '出力形式と設定内容を確認して開始します', label: '開始'},
};

loadConfig();
loadSpeakerRegistry();
restoreActiveJob();
startBootSequence();

function startBootSequence() {
  if (!bootSplash) {
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
      }, reducedMotion ? 50 : 720);
    }, reducedMotion ? 250 : 1500);
  }, 200);
}

function setAlert(element, message, error = false) {
  if (!element) return;
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

function renderMobileWizard() {
  if (!form) return;
  const mobile = isMobileWizard();
  form.classList.toggle('mobile-wizard-ready', mobile);
  [1, 2, 3, 4].forEach(step => form.classList.toggle(`mobile-step-${step}`, step === currentMobileStep));
  mobileStepSections.forEach(section => {
    const active = Number(section.dataset.mobileStep) === currentMobileStep;
    section.classList.toggle('mobile-active', active);
    if (mobile) section.toggleAttribute('inert', !active);
    else section.removeAttribute('inert');
  });

  const content = mobileStepContent[currentMobileStep];
  if (mobileStepNumber) mobileStepNumber.textContent = `STEP ${currentMobileStep} / 4`;
  if (mobileStepTitle) mobileStepTitle.textContent = content.title;
  if (mobileStepDescription) mobileStepDescription.textContent = content.description;
  if (mobileNavStep) mobileNavStep.textContent = `${currentMobileStep} / 4`;
  if (mobileNavLabel) mobileNavLabel.textContent = content.label;
  mobileStepDots.forEach(dot => {
    const step = Number(dot.dataset.mobileDot);
    dot.classList.toggle('active', step === currentMobileStep);
    dot.classList.toggle('complete', step < currentMobileStep);
    if (step === currentMobileStep) dot.setAttribute('aria-current', 'step');
    else dot.removeAttribute('aria-current');
  });

  if (mobileStepBack) mobileStepBack.disabled = jobRunning || currentMobileStep === 1;
  if (mobileStepNext) {
    mobileStepNext.disabled = jobRunning || (currentMobileStep === 1 && !hasSelectedSource());
    mobileStepNext.textContent = currentMobileStep === 3 ? '確認へ' : '次へ';
  }
}

function validateMobileStep(step) {
  if (step === 1 && !hasSelectedSource()) {
    setAlert(pathError, '先に音声・動画ファイルを選択してください。', true);
    if (fileDropZone) fileDropZone.focus();
    return false;
  }
  const section = mobileStepSections.find(item => Number(item.dataset.mobileStep) === step);
  if (!section) return true;
  const invalid = [...section.querySelectorAll('input, select, textarea')].find(input => !input.checkValidity());
  if (invalid) {
    setAlert(formError, '入力内容を確認してください。', true);
    invalid.reportValidity();
    invalid.focus();
    return false;
  }
  return true;
}

function setMobileStep(nextStep, {focusHeading = true, validateCurrent = false} = {}) {
  const target = Math.max(1, Math.min(4, Number(nextStep) || 1));
  if (validateCurrent && target > currentMobileStep && !validateMobileStep(currentMobileStep)) return false;
  currentMobileStep = target;
  setAlert(formError, '');
  renderMobileWizard();
  if (focusHeading && isMobileWizard()) {
    const header = document.querySelector('.mobile-create-header');
    if (header) header.scrollIntoView({behavior: 'smooth', block: 'start'});
    if (mobileStepTitle) {
      mobileStepTitle.setAttribute('tabindex', '-1');
      window.setTimeout(() => mobileStepTitle.focus({preventScroll: true}), 220);
    }
  }
  return true;
}

function updateCreateSummary() {
  const hasSource = hasSelectedSource();
  if (fileDropZone) fileDropZone.classList.toggle('has-file', hasSource);
  if (pathDetail) pathDetail.classList.toggle('selected', hasSource);

  quickFlowItems.forEach(item => item.classList.remove('active', 'complete'));
  if (quickFlowItems.length) {
    if (hasSource) {
      quickFlowItems[0].classList.add('complete');
      quickFlowItems[quickFlowItems.length - 1].classList.add('active');
    } else {
      quickFlowItems[0].classList.add('active');
    }
  }

  const readyMessage = hasSource
    ? '準備できました。文字起こしを開始できます'
    : 'ファイルを選択してください';
  if (setupReadyState) setupReadyState.textContent = readyMessage;
  document.querySelectorAll('[data-setup-ready]').forEach(element => { element.textContent = readyMessage; });

  if (setupSummary) {
    const model = selectedOptionText(modelName).split(' — ')[0] || '自動';
    const language = selectedOptionText(languageSelect) || '自動判定';
    const preprocess = selectedOptionText(audioPreprocess).split(' — ')[0] || 'おすすめ';
    const finishExtras = [];
    if (triplePass && triplePass.checked) finishExtras.push('詳細処理');
    const enabledAiOptions = aiOptionInputs.filter(input => input.checked).length;
    if (aiProvider && aiProvider.value !== 'none' && enabledAiOptions) {
      finishExtras.push(`${selectedOptionText(aiProvider)} AI仕上げ ${enabledAiOptions}項目`);
    }
    if (emotionAnalysis && emotionAnalysis.checked) finishExtras.push('感情分析');
    const outputExtras = [];
    if (writeSrt && writeSrt.checked) outputExtras.push('SRT');
    if (burnSubtitledVideo && burnSubtitledVideo.checked) outputExtras.push('字幕付き動画');
    const extras = [...finishExtras, ...outputExtras];
    const summaryText = `${model} / ${language} / 前処理: ${preprocess}${extras.length ? ` / ${extras.join(' / ')}` : ''}`;
    setupSummary.textContent = summaryText;
    document.querySelectorAll('[data-setup-summary]').forEach(element => { element.textContent = summaryText; });
    const selectedFile = inputFile && inputFile.files && inputFile.files[0];
    const directPath = sourcePath ? sourcePath.value.trim() : '';
    const sourceLabel = selectedFile
      ? selectedFile.name
      : (directPath ? directPath.split(/[\\/]/).pop() : '未選択');
    document.querySelectorAll('[data-mobile-review-source]').forEach(element => { element.textContent = sourceLabel; });
    document.querySelectorAll('[data-mobile-review-recognition]').forEach(element => {
      element.textContent = `${model} / ${language} / ${preprocess}`;
    });
    document.querySelectorAll('[data-mobile-review-finish]').forEach(element => {
      element.textContent = finishExtras.length ? finishExtras.join(' / ') : '追加処理なし';
    });
  }

  if (startButton) startButton.disabled = jobRunning || !hasSource;
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

function showProcessedDataSection(section, {force = false, itemId = ''} = {}) {
  const analysis = section === 'analysis';
  const requestedItemId = String(itemId || '').trim();
  const leavingAnalysis = !analysis
    && analysisCard
    && !analysisCard.hidden
    && analysisState.dirty;
  if (!force && leavingAnalysis && !window.confirm('分析設定または手動コードに未保存の変更があります。保存せずにデータ一覧へ移動しますか？')) {
    return false;
  }
  const switchingAnalysisItem = analysis
    && requestedItemId
    && requestedItemId !== analysisState.itemId
    && analysisState.dirty;
  if (!force && switchingAnalysisItem && !window.confirm('分析設定または手動コードに未保存の変更があります。保存せずに別の処理済みデータを分析しますか？')) {
    return false;
  }
  if (libraryCard) libraryCard.hidden = analysis;
  if (analysisCard) analysisCard.hidden = !analysis;
  if (showLibraryListButton) {
    showLibraryListButton.classList.toggle('active', !analysis);
    showLibraryListButton.setAttribute('aria-selected', String(!analysis));
  }
  if (showLibraryAnalysisButton) {
    showLibraryAnalysisButton.classList.toggle('active', analysis);
    showLibraryAnalysisButton.setAttribute('aria-selected', String(analysis));
  }
  if (analysis && analysisCard) {
    if (requestedItemId && analysisCatalogLoaded) {
      if (requestedItemId !== analysisState.itemId || !analysisState.data) {
        loadAnalysisItem(requestedItemId, {discardDirty: force || switchingAnalysisItem});
      } else if (analysisItemSelect) {
        analysisItemSelect.value = requestedItemId;
      }
    } else {
      if (requestedItemId) {
        analysisState.itemId = requestedItemId;
        analysisState.data = null;
        if (analysisItemSelect) analysisItemSelect.value = requestedItemId;
      }
      loadAnalysisCatalog();
    }
  }
  if (!analysis && libraryCard) loadLibrary();
  return true;
}

function showView(view, {analysisItemId = ''} = {}) {
  const leavingCurrentResult = resultCard
    && !resultCard.hidden
    && currentJobDirty;
  if (leavingCurrentResult && !window.confirm('文字起こし、会話プロファイル、または話者連携に未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  const leavingSpeakerManagement = view !== 'speakers'
    && speakerRegistryCard
    && !speakerRegistryCard.hidden
    && speakerRegistryDirty;
  if (leavingSpeakerManagement && !window.confirm('話者管理に未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  const opensProcessedData = view === 'library' || view === 'analysis';
  const leavingAnalysis = !opensProcessedData
    && analysisCard
    && !analysisCard.hidden
    && analysisState.dirty;
  if (leavingAnalysis && !window.confirm('分析設定または手動コードに未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  if (leavingCurrentResult) setCurrentJobDirty(false);
  const library = opensProcessedData;
  const create = view === 'new';
  const speakers = view === 'speakers';
  if (processedDataHub) processedDataHub.hidden = !library;
  if (speakerRegistryCard) speakerRegistryCard.hidden = !speakers;
  if (form) form.hidden = !create;
  if (library || create || speakers) {
    if (mediaPlayer) mediaPlayer.pause();
    if (resultCard) resultCard.hidden = true;
    if (progressCard && !jobRunning) progressCard.hidden = true;
  }
  if (showLibraryButton) showLibraryButton.classList.toggle('active', library);
  if (showNewButton) showNewButton.classList.toggle('active', create);
  if (showSpeakersButton) showSpeakersButton.classList.toggle('active', speakers);
  if (showLibraryButton) showLibraryButton.setAttribute('aria-selected', String(library));
  if (showNewButton) showNewButton.setAttribute('aria-selected', String(create));
  if (showSpeakersButton) showSpeakersButton.setAttribute('aria-selected', String(speakers));
  if (library) {
    showProcessedDataSection(view === 'analysis' ? 'analysis' : 'list', {
      force: true,
      itemId: analysisItemId
    });
  }
  if (speakers && speakerRegistryCard) loadSpeakerRegistry();
  if (create) renderMobileWizard();
  return true;
}

function openAnalysisForItem(itemId) {
  const targetItemId = String(itemId || '').trim();
  if (!targetItemId) return false;
  return showView('analysis', {analysisItemId: targetItemId});
}

function openResultDestination(destination) {
  const target = String(destination || '').trim();
  if (target === 'analysis') return openAnalysisForItem(currentJobId);
  if (target === 'library' || target === 'speakers') return showView(target);
  return false;
}

listen(showLibraryButton, 'click', () => showView('library'));
listen(showLibraryListButton, 'click', () => showProcessedDataSection('list'));
listen(showLibraryAnalysisButton, 'click', () => showProcessedDataSection('analysis'));
listen(showNewButton, 'click', () => showView('new'));
listen(showSpeakersButton, 'click', () => showView('speakers'));

window.addEventListener('beforeunload', event => {
  if (!currentJobDirty && !speakerRegistryDirty && !analysisState.dirty) return;
  event.preventDefault();
  event.returnValue = '';
});

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

function renderSpeakerSurveyAnalysis() {
  const container = document.querySelector('#speaker-survey-analysis-content');
  if (!container) return;
  window.clearTimeout(speakerSurveyAnalysisTimer);
  speakerSurveyAnalysisTimer = null;
  const allQuestions = speakerSurveyQuestionKeys(speakerRegistry);
  const metric = document.querySelector('#registry-survey-metric');
  if (metric) metric.textContent = String(allQuestions.length);
  container.replaceChildren();
  if (!allQuestions.length) {
    const empty = analysisElement('div', 'speaker-survey-empty');
    empty.append(
      analysisElement('strong', '', '事前アンケート回答がまだありません'),
      analysisElement('p', '', 'Googleフォームの回答CSVを読み込むか、各話者の「事前アンケート回答」に「質問=回答」の形式で入力してください。')
    );
    container.append(empty);
    return;
  }

  const records = speakerSurveyAnalysisState.includeInactive
    ? [...speakerRegistry]
    : speakerRegistry.filter(record => record.active !== false);
  if (!allQuestions.includes(speakerSurveyAnalysisState.primaryQuestion)) {
    speakerSurveyAnalysisState.primaryQuestion = allQuestions[0];
  }
  if (
    !allQuestions.includes(speakerSurveyAnalysisState.secondaryQuestion)
    || speakerSurveyAnalysisState.secondaryQuestion === speakerSurveyAnalysisState.primaryQuestion
  ) {
    speakerSurveyAnalysisState.secondaryQuestion = allQuestions.find(
      question => question !== speakerSurveyAnalysisState.primaryQuestion
    ) || '';
  }
  const primaryQuestion = speakerSurveyAnalysisState.primaryQuestion;
  const primary = speakerSurveyQuestionSummary(records, primaryQuestion);
  if (
    speakerSurveyAnalysisState.answerFilter
    && !primary.values.some(item => item.value === speakerSurveyAnalysisState.answerFilter)
  ) {
    speakerSurveyAnalysisState.answerFilter = '';
  }

  const controls = analysisElement('div', 'speaker-survey-controls');
  const primaryLabel = analysisElement('label', 'field');
  primaryLabel.append(analysisElement('span', '', '分析する質問'));
  const primarySelect = document.createElement('select');
  allQuestions.forEach(question => primarySelect.add(new Option(question, question)));
  primarySelect.value = primaryQuestion;
  primarySelect.addEventListener('change', () => {
    speakerSurveyAnalysisState.primaryQuestion = primarySelect.value;
    speakerSurveyAnalysisState.answerFilter = '';
    if (speakerSurveyAnalysisState.secondaryQuestion === primarySelect.value) {
      speakerSurveyAnalysisState.secondaryQuestion = allQuestions.find(question => question !== primarySelect.value) || '';
    }
    renderSpeakerSurveyAnalysis();
  });
  primaryLabel.append(primarySelect);

  const secondaryLabel = analysisElement('label', 'field');
  secondaryLabel.append(analysisElement('span', '', 'クロス集計する質問'));
  const secondarySelect = document.createElement('select');
  secondarySelect.add(new Option('クロス集計しない', ''));
  allQuestions.filter(question => question !== primaryQuestion)
    .forEach(question => secondarySelect.add(new Option(question, question)));
  secondarySelect.value = speakerSurveyAnalysisState.secondaryQuestion;
  secondarySelect.addEventListener('change', () => {
    speakerSurveyAnalysisState.secondaryQuestion = secondarySelect.value;
    renderSpeakerSurveyAnalysis();
  });
  secondaryLabel.append(secondarySelect);

  const filterLabel = analysisElement('label', 'field');
  filterLabel.append(analysisElement('span', '', '回答で参加者を絞り込み'));
  const answerSelect = document.createElement('select');
  answerSelect.add(new Option('すべての回答', ''));
  primary.values.forEach(item => answerSelect.add(new Option(`${item.value}（${item.count}人）`, item.value)));
  answerSelect.value = speakerSurveyAnalysisState.answerFilter;
  answerSelect.addEventListener('change', () => {
    speakerSurveyAnalysisState.answerFilter = answerSelect.value;
    renderSpeakerSurveyAnalysis();
  });
  filterLabel.append(answerSelect);

  const inactiveLabel = analysisElement('label', 'mini-check speaker-survey-inactive');
  const inactive = document.createElement('input');
  inactive.type = 'checkbox';
  inactive.checked = speakerSurveyAnalysisState.includeInactive;
  inactive.addEventListener('change', () => {
    speakerSurveyAnalysisState.includeInactive = inactive.checked;
    speakerSurveyAnalysisState.answerFilter = '';
    renderSpeakerSurveyAnalysis();
  });
  inactiveLabel.append(inactive, document.createTextNode('無効な話者を含める'));
  controls.append(primaryLabel, secondaryLabel, filterLabel, inactiveLabel);
  container.append(controls);

  const overview = analysisElement('div', 'speaker-survey-overview');
  const responseRate = records.length ? 100 * primary.answered / records.length : 0;
  [
    ['分析対象', `${records.length}人`, speakerSurveyAnalysisState.includeInactive ? '全登録話者' : '有効な話者'],
    ['質問項目', `${allQuestions.length}問`, 'CSVの未知列を含む'],
    ['回答済み', `${primary.answered}人`, `${responseRate.toFixed(1)}%`],
    ['未回答', `${primary.missing}人`, primary.missing ? '回答漏れを確認' : '回答完了']
  ].forEach(([label, value, note]) => {
    const item = analysisElement('div');
    item.append(
      analysisElement('span', '', label),
      analysisElement('strong', '', value),
      analysisElement('small', '', note)
    );
    overview.append(item);
  });
  container.append(overview);

  const grid = analysisElement('div', 'speaker-survey-grid');
  const distributionPanel = analysisElement('section', 'speaker-survey-panel');
  distributionPanel.append(
    analysisElement('h4', '', `回答分布：${primaryQuestion}`),
    analysisElement('p', 'speaker-survey-help', '同じ回答をまとめ、回答者全体に占める割合を表示します。')
  );
  const distribution = analysisElement('div', 'speaker-survey-bars');
  const maximum = Math.max(0, ...primary.values.map(item => item.count));
  primary.values.slice(0, 20).forEach(item => {
    appendSpeakerSurveyBar(distribution, item.value, item.count, primary.answered, maximum);
  });
  if (!primary.values.length) distribution.append(analysisElement('p', 'analysis-no-data', 'この質問への回答がありません。'));
  distributionPanel.append(distribution);
  if (primary.values.length > 20) {
    distributionPanel.append(analysisElement('p', 'speaker-survey-note', `回答数上位20件を表示（全${primary.values.length}種類）`));
  }
  const numeric = speakerSurveyNumericSummary(records, primaryQuestion);
  if (numeric) {
    const numericBox = analysisElement('div', 'speaker-survey-numeric');
    [
      ['平均', numeric.mean.toFixed(2)],
      ['中央値', numeric.median.toFixed(2)],
      ['最小', numeric.minimum.toFixed(2)],
      ['最大', numeric.maximum.toFixed(2)]
    ].forEach(([label, value]) => {
      const item = analysisElement('span');
      item.append(analysisElement('small', '', label), document.createTextNode(value));
      numericBox.append(item);
    });
    numericBox.append(analysisElement('p', '', `数値として解釈できた回答 n=${numeric.count}`));
    distributionPanel.append(numericBox);
  }
  grid.append(distributionPanel, buildSpeakerSurveyCompleteness(records, allQuestions));
  container.append(grid);

  if (speakerSurveyAnalysisState.secondaryQuestion) {
    container.append(buildSpeakerSurveyCrosstab(
      records,
      primaryQuestion,
      speakerSurveyAnalysisState.secondaryQuestion
    ));
  }

  const participantPanel = analysisElement('section', 'speaker-survey-panel speaker-survey-participants');
  const selectedRecords = records.filter(record => (
    !speakerSurveyAnalysisState.answerFilter
    || speakerSurveyAnswer(record, primaryQuestion) === speakerSurveyAnalysisState.answerFilter
  ));
  participantPanel.append(
    analysisElement('h4', '', `該当参加者（${selectedRecords.length}人）`),
    analysisElement('p', 'speaker-survey-help', speakerSurveyAnalysisState.answerFilter
      ? `「${speakerSurveyAnalysisState.answerFilter}」と回答した参加者です。`
      : '回答内容と参加者を照合できます。氏名より仮名・参加者コードの利用を推奨します。')
  );
  const tableWrap = analysisElement('div', 'speaker-survey-table-wrap');
  const table = document.createElement('table');
  table.className = 'speaker-survey-table participant';
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  ['参加者', '参加者コード', primaryQuestion, speakerSurveyAnalysisState.secondaryQuestion].filter(Boolean)
    .forEach(label => headRow.append(analysisElement('th', '', label)));
  head.append(headRow);
  const body = document.createElement('tbody');
  selectedRecords.slice(0, 100).forEach(record => {
    const row = document.createElement('tr');
    [
      speakerRecordName(record),
      record.participant_code || '—',
      speakerSurveyAnswer(record, primaryQuestion) || '未回答',
      speakerSurveyAnalysisState.secondaryQuestion
        ? speakerSurveyAnswer(record, speakerSurveyAnalysisState.secondaryQuestion) || '未回答'
        : null
    ].filter(value => value !== null).forEach(value => row.append(analysisElement('td', '', value)));
    body.append(row);
  });
  table.append(head, body);
  tableWrap.append(table);
  participantPanel.append(tableWrap);
  if (selectedRecords.length > 100) {
    participantPanel.append(analysisElement('p', 'speaker-survey-note', '画面には先頭100人を表示しています。全件はCSV書き出しで確認できます。'));
  }
  container.append(participantPanel);
}

function setSpeakerRegistryDirty(dirty = true, trackMutation = true) {
  speakerRegistryDirty = dirty;
  if (speakerRegistryDirty && trackMutation) speakerRegistryMutationGeneration += 1;
  const metric = document.querySelector('#registry-dirty-metric');
  if (metric) {
    metric.textContent = dirty ? '未保存' : '保存済み';
    metric.classList.toggle('unsaved', dirty);
  }
  if (speakerRegistrySaveState) {
    speakerRegistrySaveState.textContent = dirty ? '未保存の変更があります' : '保存済み';
    speakerRegistrySaveState.classList.toggle('unsaved', dirty);
  }
  if (speakerRegistrySaveButton) speakerRegistrySaveButton.disabled = !dirty || speakerRegistrySaveInProgress;
  if (speakerRegistryCard) speakerRegistryCard.classList.toggle('has-unsaved', dirty);
  scheduleSpeakerSurveyAnalysis();
}

function makeSheetInput(record, key, {
  type = 'text', wide = false, multiline = false, label = '', placeholder = '', afterInput = null
} = {}) {
  const input = document.createElement(multiline ? 'textarea' : 'input');
  if (!multiline) input.type = type;
  if (wide) input.className = 'cell-wide';
  if (label) input.setAttribute('aria-label', label);
  if (placeholder) input.placeholder = placeholder;
  input.dataset.speakerId = record.id;
  input.dataset.speakerField = key;
  input.value = Array.isArray(record[key]) ? record[key].join(', ') : (record[key] || '');
  input.addEventListener('input', () => {
    record[key] = key === 'tags'
      ? input.value.split(/[,、;]+/).map(item => item.trim()).filter(Boolean)
      : input.value;
    setSpeakerRegistryDirty();
    if (afterInput) afterInput(input.value);
  });
  return input;
}

function makeSheetSelect(record, key, labels, {label = '', afterChange = null} = {}) {
  const select = document.createElement('select');
  if (label) select.setAttribute('aria-label', label);
  select.dataset.speakerId = record.id;
  select.dataset.speakerField = key;
  Object.entries(labels).forEach(([value, label]) => select.add(new Option(label, value)));
  select.value = record[key] || Object.keys(labels)[0];
  select.addEventListener('change', () => {
    record[key] = select.value;
    setSpeakerRegistryDirty();
    if (afterChange) afterChange(select.value);
  });
  return select;
}

function appendSheetCell(row, control) {
  const cell = document.createElement('td');
  cell.append(control);
  row.append(cell);
}

async function loadSpeakerRegistry(force = false) {
  if (speakerRegistryLoaded && !force) {
    renderSpeakerRegistry();
    return speakerRegistry;
  }
  try {
    const response = await apiFetch('/api/speakers', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '話者管理データを取得できませんでした。');
    speakerRegistry = Array.isArray(data.speakers) ? data.speakers : [];
    speakerRegistryRevision = Number(data.registry_revision || 0);
    speakerRegistryDeletedIds.clear();
    speakerRegistryLoaded = true;
    setSpeakerRegistryDirty(false);
    renderSpeakerRegistry();
    if (currentJob && !resultCard.hidden) renderSpeakerEditor();
    return speakerRegistry;
  } catch (error) {
    setAlert(document.querySelector('#speaker-registry-message'), error.message, true);
    return [];
  }
}

function speakerRecordName(record) {
  return String(record.pseudonym || record.display_name || record.participant_code || '名前未設定').trim();
}

function speakerRecordSearchText(record) {
  return [
    record.participant_code, record.display_name, record.pseudonym, record.organization,
    record.department, record.job_title, ...(record.tags || []),
    ...Object.entries(record.attributes || {}).flat(), record.notes
  ].join(' ').toLocaleLowerCase();
}

function visibleSpeakerRegistry() {
  const searchElement = document.querySelector('#speaker-registry-search');
  const roleElement = document.querySelector('#speaker-registry-role-filter');
  const showInactiveElement = document.querySelector('#speaker-registry-show-inactive');
  const query = (searchElement ? searchElement.value : '').trim().toLocaleLowerCase();
  const role = roleElement ? roleElement.value : '';
  const showInactive = !showInactiveElement || showInactiveElement.checked;
  return speakerRegistry.filter(record => {
    if (!showInactive && !record.active) return false;
    if (role && record.default_role !== role) return false;
    if (!query) return true;
    return speakerRecordSearchText(record).includes(query);
  });
}

function updateSpeakerRegistryOverview() {
  const active = speakerRegistry.filter(record => record.active !== false);
  const values = {
    '#registry-total-metric': speakerRegistry.length,
    '#registry-active-metric': active.length,
    '#registry-survey-metric': speakerSurveyQuestionKeys(speakerRegistry).length
  };
  Object.entries(values).forEach(([selector, value]) => {
    const element = document.querySelector(selector);
    if (element) element.textContent = String(value);
  });
}

function removeSpeakerRecord(record) {
  if (!window.confirm(`${speakerRecordName(record)} を話者管理から削除しますか？\n「変更を保存」するまで削除は確定しません。`)) return;
  speakerRegistryDeletedIds.add(record.id);
  speakerRegistry = speakerRegistry.filter(item => item.id !== record.id);
  setSpeakerRegistryDirty();
  renderSpeakerRegistry();
}

function makeAttributesControl(record, label) {
  const attributes = document.createElement('textarea');
  attributes.value = attributesToText(record.attributes);
  attributes.placeholder = '例：満足度=5; 年齢層=30代; 利用歴=3年以上';
  attributes.setAttribute('aria-label', label);
  attributes.dataset.speakerId = record.id;
  attributes.dataset.speakerField = 'attributes';
  attributes.addEventListener('input', () => {
    record.attributes = textToAttributes(attributes.value);
    setSpeakerRegistryDirty();
  });
  return attributes;
}

function renderSpeakerRegistryTable(visible) {
  speakerRegistryBody.replaceChildren();
  if (!visible.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 13;
    cell.className = 'speaker-registry-empty';
    cell.textContent = '条件に一致する話者はいません。検索条件を変えるか、新しい話者を追加してください。';
    row.append(cell);
    speakerRegistryBody.append(row);
    return;
  }

  visible.forEach(record => {
    const row = document.createElement('tr');
    row.dataset.speakerId = record.id;
    row.classList.toggle('inactive', !record.active);
    const active = document.createElement('input');
    active.type = 'checkbox';
    active.checked = record.active !== false;
    active.setAttribute('aria-label', `${speakerRecordName(record)}を有効にする`);
    active.addEventListener('change', () => {
      record.active = active.checked;
      setSpeakerRegistryDirty();
      row.classList.toggle('inactive', !record.active);
      updateSpeakerRegistryOverview();
      const showInactive = document.querySelector('#speaker-registry-show-inactive');
      if (!active.checked && showInactive && !showInactive.checked) renderSpeakerRegistry();
    });
    appendSheetCell(row, active);
    appendSheetCell(row, makeSheetInput(record, 'participant_code', {label: `${speakerRecordName(record)}の参加者コード`}));
    appendSheetCell(row, makeSheetInput(record, 'display_name', {label: `${speakerRecordName(record)}の氏名`}));
    appendSheetCell(row, makeSheetInput(record, 'pseudonym', {label: `${speakerRecordName(record)}の仮名・表示名`}));
    appendSheetCell(row, makeSheetSelect(record, 'default_role', speakerRoleLabels, {
      label: `${speakerRecordName(record)}の既定役割`,
      afterChange: () => {
        const roleFilter = document.querySelector('#speaker-registry-role-filter');
        if (roleFilter && roleFilter.value) renderSpeakerRegistry();
      }
    }));
    appendSheetCell(row, makeSheetInput(record, 'organization', {label: `${speakerRecordName(record)}の組織`}));
    appendSheetCell(row, makeSheetInput(record, 'department', {label: `${speakerRecordName(record)}の部署`}));
    appendSheetCell(row, makeSheetInput(record, 'job_title', {label: `${speakerRecordName(record)}の役職`}));
    appendSheetCell(row, makeSheetSelect(record, 'confidentiality_status', consentLabels, {label: `${speakerRecordName(record)}の守秘同意`}));
    appendSheetCell(row, makeSheetInput(record, 'tags', {wide: true, label: `${speakerRecordName(record)}のタグ`}));
    appendSheetCell(row, makeAttributesControl(record, `${speakerRecordName(record)}の事前アンケート回答`));
    appendSheetCell(row, makeSheetInput(record, 'notes', {multiline: true, label: `${speakerRecordName(record)}の備考`}));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'sheet-delete';
    remove.textContent = '削除';
    remove.setAttribute('aria-label', `${speakerRecordName(record)}を削除`);
    remove.addEventListener('click', () => removeSpeakerRecord(record));
    appendSheetCell(row, remove);
    speakerRegistryBody.append(row);
  });
}

function createSpeakerCardField(labelText, control, wide = false) {
  const label = document.createElement('label');
  label.className = `field speaker-card-field${wide ? ' wide' : ''}`;
  const text = document.createElement('span');
  text.textContent = labelText;
  label.append(text, control);
  return label;
}

function renderSpeakerRegistryCards(visible) {
  speakerRegistryList.replaceChildren();
  if (!visible.length) {
    const empty = document.createElement('div');
    empty.className = 'speaker-registry-empty';
    empty.textContent = '条件に一致する話者はいません。条件をクリアするか、新しい話者を追加してください。';
    speakerRegistryList.append(empty);
    return;
  }

  visible.forEach(record => {
    const card = document.createElement('article');
    card.className = 'speaker-management-card';
    card.dataset.speakerId = record.id;
    card.classList.toggle('inactive', record.active === false);

    const header = document.createElement('header');
    const identity = document.createElement('div');
    const role = document.createElement('span');
    role.className = 'speaker-card-role';
    const title = document.createElement('h3');
    const subtitle = document.createElement('p');
    identity.append(role, title, subtitle);
    const activeLabel = document.createElement('label');
    activeLabel.className = 'speaker-card-active';
    const active = document.createElement('input');
    active.type = 'checkbox';
    active.checked = record.active !== false;
    const activeText = document.createElement('span');
    activeText.textContent = '有効';
    activeLabel.append(active, activeText);
    header.append(identity, activeLabel);

    const refreshIdentity = () => {
      role.textContent = speakerRoleLabels[record.default_role] || 'その他';
      title.textContent = speakerRecordName(record);
      subtitle.textContent = [record.participant_code, record.organization, record.job_title].filter(Boolean).join(' ・ ') || '基本情報を入力してください';
      active.setAttribute('aria-label', `${speakerRecordName(record)}を有効にする`);
    };
    refreshIdentity();
    active.addEventListener('change', () => {
      record.active = active.checked;
      card.classList.toggle('inactive', !active.checked);
      setSpeakerRegistryDirty();
      updateSpeakerRegistryOverview();
      const showInactive = document.querySelector('#speaker-registry-show-inactive');
      if (!active.checked && showInactive && !showInactive.checked) renderSpeakerRegistry();
    });

    const primary = document.createElement('div');
    primary.className = 'speaker-card-grid primary';
    primary.append(
      createSpeakerCardField('参加者コード', makeSheetInput(record, 'participant_code', {label: '参加者コード', afterInput: refreshIdentity})),
      createSpeakerCardField('氏名', makeSheetInput(record, 'display_name', {label: '氏名', afterInput: refreshIdentity})),
      createSpeakerCardField('仮名・表示名', makeSheetInput(record, 'pseudonym', {label: '仮名・表示名', afterInput: refreshIdentity})),
      createSpeakerCardField('既定役割', makeSheetSelect(record, 'default_role', speakerRoleLabels, {
        label: '既定役割', afterChange: () => {
          refreshIdentity();
          const roleFilter = document.querySelector('#speaker-registry-role-filter');
          if (roleFilter && roleFilter.value) renderSpeakerRegistry();
        }
      }))
    );

    const details = document.createElement('details');
    details.className = 'speaker-card-details';
    const summary = document.createElement('summary');
    summary.textContent = '所属・アンケート・詳細を編集';
    const detailGrid = document.createElement('div');
    detailGrid.className = 'speaker-card-grid details';
    detailGrid.append(
      createSpeakerCardField('組織', makeSheetInput(record, 'organization', {label: '組織', afterInput: refreshIdentity})),
      createSpeakerCardField('部署', makeSheetInput(record, 'department', {label: '部署'})),
      createSpeakerCardField('役職', makeSheetInput(record, 'job_title', {label: '役職', afterInput: refreshIdentity})),
      createSpeakerCardField('守秘同意', makeSheetSelect(record, 'confidentiality_status', consentLabels, {label: '守秘同意'})),
      createSpeakerCardField('タグ', makeSheetInput(record, 'tags', {label: 'タグ', placeholder: '例：顧客, 管理職'}), true),
      createSpeakerCardField('事前アンケート回答', makeAttributesControl(record, '事前アンケート回答'), true),
      createSpeakerCardField('備考', makeSheetInput(record, 'notes', {multiline: true, label: '備考'}), true)
    );
    details.append(summary, detailGrid);

    const footer = document.createElement('footer');
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'sheet-delete';
    remove.textContent = 'この話者を削除';
    remove.addEventListener('click', () => removeSpeakerRecord(record));
    footer.append(remove);

    card.append(header, primary, details, footer);
    speakerRegistryList.append(card);
  });
}

function renderSpeakerRegistry() {
  if (!speakerRegistryBody || !speakerRegistryList) return;
  const visible = visibleSpeakerRegistry();
  if (mobileWizardMedia.matches) {
    speakerRegistryBody.replaceChildren();
    renderSpeakerRegistryCards(visible);
  } else {
    speakerRegistryList.replaceChildren();
    renderSpeakerRegistryTable(visible);
  }
  updateSpeakerRegistryOverview();
  renderSpeakerSurveyAnalysis();
  const count = document.querySelector('#speaker-registry-count');
  if (count) count.textContent = `${visible.length}人を表示（登録 ${speakerRegistry.length}人）`;
}

async function saveSpeakerRegistry() {
  if (speakerRegistrySaveInProgress) return;
  const invalid = speakerRegistry.find(record => (
    !String(record.participant_code || '').trim()
    && !String(record.display_name || '').trim()
    && !String(record.pseudonym || '').trim()
  ));
  if (invalid) {
    setAlert(document.querySelector('#speaker-registry-message'), '氏名、仮名、参加者コードのいずれかを入力してください。', true);
    return;
  }
  const button = speakerRegistrySaveButton;
  const saveGeneration = speakerRegistryMutationGeneration;
  speakerRegistrySaveInProgress = true;
  if (button) button.disabled = true;
  try {
    const response = await apiFetch('/api/speakers', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        registry_revision: speakerRegistryRevision,
        speakers: speakerRegistry,
        delete_ids: [...speakerRegistryDeletedIds]
      })
    });
    const data = await readJsonResponse(response);
    if (!response.ok) {
      const conflict = response.status === 409
        ? '別の画面で話者管理が更新されています。未保存内容を控えてから再読み込みしてください。'
        : '話者管理データを保存できませんでした。';
      throw new Error(response.status === 409 ? conflict : (data.error || conflict));
    }
    speakerRegistryRevision = Number(data.registry_revision || speakerRegistryRevision);
    if (speakerRegistryMutationGeneration === saveGeneration) {
      speakerRegistry = data.speakers || [];
      speakerRegistryDeletedIds.clear();
      setSpeakerRegistryDirty(false);
      renderSpeakerRegistry();
      setAlert(document.querySelector('#speaker-registry-message'), `${speakerRegistry.length}人の話者情報を保存しました。`);
      if (currentJob && !resultCard.hidden) renderSpeakerEditor();
    } else {
      setSpeakerRegistryDirty(true, false);
      setAlert(document.querySelector('#speaker-registry-message'), '保存開始後の追加変更が残っています。内容を確認して、もう一度保存してください。', true);
    }
  } catch (error) {
    setAlert(document.querySelector('#speaker-registry-message'), error.message, true);
  } finally {
    speakerRegistrySaveInProgress = false;
    if (button) button.disabled = !speakerRegistryDirty;
  }
}

listen(document.querySelector('#add-speaker-button'), 'click', () => {
  const record = blankSpeakerRecord();
  const search = document.querySelector('#speaker-registry-search');
  const role = document.querySelector('#speaker-registry-role-filter');
  const showInactive = document.querySelector('#speaker-registry-show-inactive');
  if (search) search.value = '';
  if (role) role.value = '';
  if (showInactive) showInactive.checked = true;
  speakerRegistry.unshift(record);
  setSpeakerRegistryDirty();
  renderSpeakerRegistry();
  window.requestAnimationFrame(() => {
    const control = document.querySelector(`[data-speaker-id="${record.id}"][data-speaker-field="participant_code"]`);
    if (control) {
      control.scrollIntoView({behavior: 'smooth', block: 'center'});
      control.focus();
    }
  });
});
listen(speakerRegistrySaveButton, 'click', saveSpeakerRegistry);
listen(document.querySelector('#speaker-registry-search'), 'input', renderSpeakerRegistry);
listen(document.querySelector('#speaker-registry-role-filter'), 'change', renderSpeakerRegistry);
listen(document.querySelector('#speaker-registry-show-inactive'), 'change', renderSpeakerRegistry);
listen(document.querySelector('#speaker-registry-clear-filters'), 'click', () => {
  const search = document.querySelector('#speaker-registry-search');
  const role = document.querySelector('#speaker-registry-role-filter');
  const showInactive = document.querySelector('#speaker-registry-show-inactive');
  if (search) search.value = '';
  if (role) role.value = '';
  if (showInactive) showInactive.checked = true;
  renderSpeakerRegistry();
});
listen(document.querySelector('#import-speakers-button'), 'click', () => {
  if (speakerRegistryDirty && !window.confirm('未保存の変更があります。CSVを読み込むと現在の編集内容は置き換わります。続けますか？')) return;
  const input = document.querySelector('#speaker-csv-input');
  if (input) input.click();
});
listen(document.querySelector('#speaker-csv-input'), 'change', async event => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const body = new FormData();
  body.append('csv_file', file);
  body.append('registry_revision', String(speakerRegistryRevision));
  const importGeneration = speakerRegistryMutationGeneration;
  speakerRegistrySaveInProgress = true;
  setSpeakerRegistryDirty(speakerRegistryDirty, false);
  try {
    const response = await apiFetch('/api/speakers/import', {method: 'POST', body});
    const data = await readJsonResponse(response);
    if (!response.ok) {
      const conflict = response.status === 409
        ? '別の画面で話者管理が更新されています。再読み込みしてからCSVを取り込んでください。'
        : 'CSVを取り込めませんでした。';
      throw new Error(response.status === 409 ? conflict : (data.error || conflict));
    }
    speakerRegistryRevision = Number(data.registry_revision || speakerRegistryRevision);
    if (speakerRegistryMutationGeneration === importGeneration) {
      speakerRegistry = data.speakers || [];
      speakerRegistryLoaded = true;
      speakerRegistryDeletedIds.clear();
      setSpeakerRegistryDirty(false);
      renderSpeakerRegistry();
      setAlert(document.querySelector('#speaker-registry-message'), `${data.imported_count}行を取り込み、話者管理へ保存しました。未知の列は追加属性として保持しています。`);
    } else {
      setSpeakerRegistryDirty(true, false);
      setAlert(document.querySelector('#speaker-registry-message'), 'CSVは保存されましたが、取込開始後の追加変更が画面に残っています。再度保存してから一覧を再読み込みしてください。', true);
    }
  } catch (error) {
    setAlert(document.querySelector('#speaker-registry-message'), error.message, true);
  } finally {
    speakerRegistrySaveInProgress = false;
    if (speakerRegistrySaveButton) speakerRegistrySaveButton.disabled = !speakerRegistryDirty;
    event.target.value = '';
  }
});

const roleFilter = document.querySelector('#speaker-registry-role-filter');
if (roleFilter) {
  Object.entries(speakerRoleLabels).forEach(([value, label]) => roleFilter.add(new Option(label, value)));
}

mobileWizardMedia.addEventListener('change', () => {
  if (speakerRegistryLoaded) renderSpeakerRegistry();
  setLibraryFiltersOpen(false);
});

listen(sourcePath, 'input', () => {
  setAlert(pathError, '');
  const value = sourcePath.value.trim();
  if (value && inputFile) inputFile.value = '';
  pathDetail.textContent = value
    ? `${value.split(/[\\/]/).pop()} — このパスを直接処理します`
    : 'ファイルが選択されていません';
  scheduleSourceThumbnail(value);
  updateCreateSummary();
});

listen(browsePathButton, 'click', async () => {
  setAlert(pathError, '');
  if (!browsePathButton) return;
  if (browserFilePickerOnly || isMobileWizard()) {
    if (inputFile) inputFile.click();
    return;
  }
  browsePathButton.disabled = true;
  browsePathButton.textContent = '選択画面を開いています…';
  try {
    const response = await apiFetch('/api/select-input', {method: 'POST', cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error([data.error, data.hint].filter(Boolean).join('\n'));
    if (data.cancelled) return;
    if (inputFile) inputFile.value = '';
    sourcePath.value = data.path || '';
    pathDetail.textContent = `${data.name || data.path} / ${formatBytes(Number(data.size))} — アップロードせず、このパスを直接処理します`;
    showSourceThumbnail(data.path || '', data.name || '');
    updateCreateSummary();
  } catch (error) {
    setAlert(pathError, error.message || 'ファイル選択に失敗しました。', true);
  } finally {
    browsePathButton.disabled = false;
    updateBrowseButtonLabel();
  }
});

listen(fileDropZone, 'keydown', event => {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  event.preventDefault();
  if (!jobRunning && browsePathButton) browsePathButton.click();
});

function handleInputFileSelection() {
  setAlert(pathError, '');
  const file = inputFile.files && inputFile.files[0];
  if (file) {
    sourcePath.value = '';
    pathDetail.textContent = browserFilePickerOnly
      ? `${file.name} / ${formatBytes(file.size)} — Colabへ一時アップロードして処理します`
      : `${file.name} / ${formatBytes(file.size)} — このPC内だけで一時コピーして処理します`;
    hideSourcePreview();
  } else if (!sourcePath.value.trim()) {
    pathDetail.textContent = 'ファイルが選択されていません';
  }
  updateCreateSummary();
}

listen(inputFile, 'change', handleInputFileSelection);

['dragenter', 'dragover'].forEach(eventName => {
  listen(fileDropZone, eventName, event => {
    event.preventDefault();
    if (!jobRunning) fileDropZone.classList.add('is-dragging');
  });
});
['dragleave', 'drop'].forEach(eventName => {
  listen(fileDropZone, eventName, event => {
    event.preventDefault();
    fileDropZone.classList.remove('is-dragging');
  });
});
listen(fileDropZone, 'drop', event => {
  if (jobRunning || !inputFile) return;
  const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
  if (!file) return;
  try {
    const transfer = new DataTransfer();
    transfer.items.add(file);
    inputFile.files = transfer.files;
    handleInputFileSelection();
  } catch (error) {
    setAlert(pathError, 'ドラッグ＆ドロップを利用できません。［ファイルを選択］から指定してください。', true);
  }
});

function setHardwareLight(element, available, availableText, unavailableText, title = '') {
  if (!element) return;
  element.classList.remove('checking', 'available', 'unavailable');
  element.classList.add(available ? 'available' : 'unavailable');
  element.textContent = available ? availableText : unavailableText;
  element.title = title;
}

function setHardwareLights(kind, available, availableText, unavailableText, title = '') {
  document.querySelectorAll(`[data-hardware="${kind}"]`).forEach(element => {
    setHardwareLight(element, available, availableText, unavailableText, title);
  });
}

function applyMachineProfile(machine) {
  if (!machine) return;
  const cpu = machine.cpu || {};
  const gpu = machine.gpu || {};
  const recommended = machine.recommended || {};
  const summary = document.querySelector('#machine-summary');
  const recommendation = document.querySelector('#machine-recommendation');
  const modelSelect = document.querySelector('#model-name');
  const transcriptionDevice = document.querySelector('#transcription-device');
  const diarizationDevice = document.querySelector('#diarization-device');

  setHardwareLights(
    'cpu',
    Boolean(cpu.available),
    'CPU 利用可',
    'CPU 利用不可',
    `${cpu.name || 'CPU'} / ${cpu.logical_threads || '?'} threads`
  );
  setHardwareLights(
    'gpu',
    Boolean(gpu.cuda_available),
    'GPU 利用可',
    'GPU 利用不可',
    gpu.cuda_available
      ? `${gpu.name || 'CUDA GPU'} / VRAM ${Number(gpu.vram_gib || 0).toFixed(1)} GB`
      : (gpu.reason || 'CUDAを利用できません')
  );

  const cpuParts = [
    cpu.name || 'CPU',
    `${cpu.logical_threads || '?'} threads`,
  ];
  if (Number(machine.memory_gib) > 0) cpuParts.push(`RAM ${Number(machine.memory_gib).toFixed(1)} GB`);
  const gpuText = gpu.cuda_available
    ? `${gpu.name} / VRAM ${Number(gpu.vram_gib || 0).toFixed(1)} GB / CUDA ${gpu.cuda_version || '?'} / CC ${gpu.capability || '?'}`
    : (gpu.reason || 'CUDA GPUは利用できません');
  if (summary) summary.textContent = `${cpuParts.join(' / ')}　｜　${gpuText}`;

  [transcriptionDevice, diarizationDevice].forEach(select => {
    if (!select) return;
    const cudaOption = select.querySelector('option[value="cuda"]');
    if (cudaOption) cudaOption.disabled = !gpu.cuda_available;
    if (!gpu.cuda_available && select.value === 'cuda') select.value = 'cpu';
  });

  if (modelSelect && [...modelSelect.options].some(option => option.value === recommended.model_name)) {
    modelSelect.value = recommended.model_name;
  }
  if (transcriptionDevice && [...transcriptionDevice.options].some(option => (
    option.value === recommended.device && !option.disabled
  ))) {
    transcriptionDevice.value = recommended.device;
  }
  if (diarizationDevice && [...diarizationDevice.options].some(option => (
    option.value === recommended.diarization_device && !option.disabled
  ))) {
    diarizationDevice.value = recommended.diarization_device;
  }

  if (recommendation) {
    const deviceLabel = recommended.device === 'cuda' ? 'GPU' : 'CPU';
    const diarizationLabel = recommended.diarization_device === 'cuda' ? 'GPU' : 'CPU';
    recommendation.textContent = recommended.model_name
      ? `自動設定: ${recommended.model_name} / 文字起こし ${deviceLabel} / 話者分離 ${diarizationLabel}。${recommended.reason || ''}`
      : '';
  }
  updateCreateSummary();
}

async function loadConfig() {
  const message = document.querySelector('#token-message');
  if (!message) return;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await apiFetch('/api/config', {cache: 'no-store', signal: controller.signal});
    const data = await readJsonResponse(response);
    tokenConfigSnapshot = data && typeof data === 'object' ? data : {};
    applyMachineProfile(data.machine);
    const runtime = data.runtime || {};
    browserFilePickerOnly = Boolean(runtime.browser_upload);
    if (browsePathButton) {
      browsePathButton.dataset.pickerMode = browserFilePickerOnly ? 'browser' : 'native';
      updateBrowseButtonLabel();
    }
    if (!response.ok || !data.ok) throw new Error(data.error || '設定を取得できません');
    const recognized = [];
    [['hf', 'huggingface', 'Hugging Face'], ['openai', 'openai', 'OpenAI'], ['google', 'google', 'Google']].forEach(([id, key, label]) => {
      const pill = document.querySelector(`#status-${id}`);
      if (!pill) return;
      pill.classList.remove('loading', 'ready', 'missing');
      pill.classList.add(data[key] ? 'ready' : 'missing');
      pill.textContent = data[key] ? `${label} ✓` : label;
      pill.title = data[key] ? '設定済み' : '未設定';
      if (pill.dataset.modelProvider) {
        const currentModel = String(data[`${key}_model`] || '').trim();
        pill.dataset.currentModel = currentModel;
        pill.title = data[key]
          ? `クリックしてモデルを変更（現在: ${currentModel || 'tokens.json の設定'}）`
          : `${label} APIキーがtokens.jsonに設定されていません`;
      }
      if (data[key]) recognized.push(label);
    });
    const outputDir = document.querySelector('#output-dir');
    if (outputDir) outputDir.placeholder = `${data.default_output_dir}（実行ごとにサブフォルダーを作成）`;
    message.textContent = recognized.length
      ? `認識済み: ${recognized.join(' / ')}。発光しているトークンを使用できます。`
      : 'トークンを認識できません。tokens.json を確認してください。';
  } catch (error) {
    message.textContent = error.name === 'AbortError'
      ? '設定確認がタイムアウトしました。アプリを再起動して http://127.0.0.1:7860 を開き直してください。'
      : error.message;
    message.style.color = '#913733';
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function clearSystemActivityPolling() {
  if (systemActivityTimer !== null) window.clearTimeout(systemActivityTimer);
  systemActivityTimer = null;
  if (systemActivityController) systemActivityController.abort();
  systemActivityController = null;
}

function formatActivityRate(mebibytesPerSecond) {
  const value = Math.max(0, Number(mebibytesPerSecond) || 0);
  if (value >= 1) return `${value.toFixed(value >= 10 ? 0 : 1)} MB/s`;
  return `${Math.round(value * 1024)} KB/s`;
}

function setResourceMetric(name, payload, detail) {
  const available = Boolean(payload && payload.available);
  const percent = Math.max(0, Math.min(100, Number(payload && payload.utilization_percent) || 0));
  const value = document.querySelector(`#monitor-${name}-value`);
  const bar = document.querySelector(`#monitor-${name}-bar`);
  const detailElement = document.querySelector(`#monitor-${name}-detail`);
  const card = value ? value.closest('.resource-metric') : null;
  if (value) {
    const displayedPercent = name === 'cpu' ? percent.toFixed(1) : Math.round(percent);
    value.textContent = available ? `${displayedPercent}%` : '--%';
  }
  if (bar) bar.style.width = available ? `${percent}%` : '0%';
  if (detailElement) detailElement.textContent = available ? detail : '利用できません';
  if (card) card.classList.toggle('is-unavailable', !available);
}

function renderSystemActivity(activity) {
  document.querySelectorAll('.resource-metric').forEach(card => card.classList.remove('is-stale'));
  const cpu = activity && activity.cpu ? activity.cpu : {};
  const memory = activity && activity.memory ? activity.memory : {};
  const gpu = activity && activity.gpu ? activity.gpu : {};
  const disk = activity && activity.disk ? activity.disk : {};
  setResourceMetric('cpu', cpu, 'システム全体の使用率');
  setResourceMetric(
    'memory',
    memory,
    `${Number(memory.used_gib || 0).toFixed(1)} / ${Number(memory.total_gib || 0).toFixed(1)} GB`
  );
  setResourceMetric(
    'gpu',
    gpu,
    gpu.available
      ? `VRAM ${Number(gpu.memory_used_gib || 0).toFixed(1)} / ${Number(gpu.memory_total_gib || 0).toFixed(1)} GB (${Math.round(Number(gpu.memory_percent || 0))}%)`
      : ''
  );
  const readLight = document.querySelector('#monitor-read-light');
  const writeLight = document.querySelector('#monitor-write-light');
  const readRate = document.querySelector('#monitor-read-rate');
  const writeRate = document.querySelector('#monitor-write-rate');
  if (readLight) readLight.classList.toggle('is-active', Boolean(disk.available && disk.read_active));
  if (writeLight) writeLight.classList.toggle('is-active', Boolean(disk.available && disk.write_active));
  if (readRate) readRate.textContent = disk.available ? formatActivityRate(disk.read_mib_per_second) : '--';
  if (writeRate) writeRate.textContent = disk.available ? formatActivityRate(disk.write_mib_per_second) : '--';
}

function scheduleSystemActivityPolling() {
  if (!jobRunning || systemActivityTimer !== null || systemActivityController) return;
  systemActivityTimer = window.setTimeout(() => {
    systemActivityTimer = null;
    pollSystemActivity();
  }, systemActivityDelayMs);
}

async function pollSystemActivity() {
  if (!jobRunning || !progressCard || progressCard.hidden || systemActivityController) return;
  const controller = new AbortController();
  systemActivityController = controller;
  try {
    const response = await apiFetch('/api/system/activity', {cache: 'no-store', signal: controller.signal});
    const activity = await readJsonResponse(response);
    if (!response.ok) throw new Error(activity.error || 'システム使用状況を取得できませんでした。');
    if (jobRunning) renderSystemActivity(activity);
  } catch (error) {
    if (error.name !== 'AbortError') {
      document.querySelectorAll('.resource-metric').forEach(card => card.classList.add('is-stale'));
    }
  } finally {
    if (systemActivityController === controller) systemActivityController = null;
    scheduleSystemActivityPolling();
  }
}

function startSystemActivityPolling() {
  if (!jobRunning || !progressCard || progressCard.hidden) return;
  if (systemActivityTimer === null && !systemActivityController) pollSystemActivity();
}

function setRunning(running) {
  if (!form) return;
  jobRunning = running;
  if (running) startSystemActivityPolling();
  else clearSystemActivityPolling();
  [...form.elements].forEach(element => {
    element.disabled = running || element.dataset.alwaysDisabled === 'true';
  });
  if (cancelButton) cancelButton.disabled = !running;
  syncQuietFields();
  syncEmotionFields();
  syncAiFields();
  updateCreateSummary();
}

function syncQuietFields() {
  const controlsDisabled = (boostQuietSpeech && boostQuietSpeech.disabled) || (triplePass && triplePass.disabled);
  const enabled = ((boostQuietSpeech && boostQuietSpeech.checked) || (triplePass && triplePass.checked)) && !controlsDisabled;
  [vadOnset, vadOffset].forEach(input => { if (input) input.disabled = !enabled; });
}

function syncEmotionFields() {
  if (emotionModel) emotionModel.disabled = !emotionAnalysis || emotionAnalysis.disabled || !emotionAnalysis.checked;
}

function syncAiFields() {
  if (!aiProvider) return;
  const providerDisabled = aiProvider.disabled;
  const disabled = providerDisabled || aiProvider.value === 'none';
  aiOptionInputs.forEach(input => {
    if (aiProvider.value === 'none') input.checked = false;
    input.disabled = disabled;
    const row = input.closest('.check-row');
    if (row) row.classList.toggle('disabled', disabled);
  });
}

function selectDefaultAiOptions() {
  if (!aiProvider) return;
  if (aiProvider.value !== 'none') {
    aiOptionInputs.forEach(input => { input.checked = true; });
  }
  syncAiFields();
  updateCreateSummary();
}

listen(boostQuietSpeech, 'change', syncQuietFields);
listen(triplePass, 'change', () => {
  syncQuietFields();
  updateCreateSummary();
});
listen(emotionAnalysis, 'change', () => {
  syncEmotionFields();
  updateCreateSummary();
});
listen(aiProvider, 'change', selectDefaultAiOptions);
[modelName, languageSelect, audioPreprocess, writeSrt, burnSubtitledVideo].forEach(input => {
  listen(input, 'change', updateCreateSummary);
});
aiOptionInputs.forEach(input => listen(input, 'change', updateCreateSummary));
syncQuietFields();
syncEmotionFields();
syncAiFields();
updateCreateSummary();

listen(mobileStepBack, 'click', () => setMobileStep(currentMobileStep - 1));
listen(mobileStepNext, 'click', () => setMobileStep(currentMobileStep + 1, {validateCurrent: true}));
document.querySelectorAll('[data-mobile-edit-step]').forEach(button => {
  listen(button, 'click', () => setMobileStep(Number(button.dataset.mobileEditStep)));
});
mobileWizardMedia.addEventListener('change', () => {
  updateBrowseButtonLabel();
  renderMobileWizard();
});

if (form) {
  form.addEventListener('invalid', event => {
    if (!isMobileWizard()) return;
    event.preventDefault();
    const section = event.target.closest('[data-mobile-step]');
    if (section) currentMobileStep = Number(section.dataset.mobileStep) || currentMobileStep;
    renderMobileWizard();
    setAlert(formError, '入力内容を確認してください。', true);
    window.setTimeout(() => event.target.focus(), 80);
  }, true);
}

function jobFromPayload(payload) {
  if (!payload || typeof payload !== 'object') return null;
  if (payload.id && payload.status) return payload;
  for (const key of ['job', 'active_job', 'activeJob']) {
    const job = payload[key];
    if (job && typeof job === 'object' && job.id && job.status) return job;
  }
  return null;
}

function clearPollTimer() {
  if (pollTimer !== null) window.clearTimeout(pollTimer);
  pollTimer = null;
}

function schedulePoll(delay = pollBaseDelayMs) {
  clearPollTimer();
  if (!currentJobId || !jobRunning) return;
  pollTimer = window.setTimeout(() => {
    pollTimer = null;
    pollJob();
  }, delay);
}

async function fetchActiveJob() {
  const response = await apiFetch('/api/jobs/active', {cache: 'no-store'});
  if (response.status === 204 || response.status === 404) return null;
  const payload = await readJsonResponse(response);
  if (!response.ok) throw new Error(payload.error || '実行中ジョブを確認できませんでした。');
  return jobFromPayload(payload);
}

async function fetchPersistedJob(jobId) {
  if (!jobId) return null;
  const response = await apiFetch(`/api/library/${encodeURIComponent(jobId)}`, {cache: 'no-store'});
  if (response.status === 404) return null;
  const payload = await readJsonResponse(response);
  if (!response.ok) throw new Error(payload.error || '保存済み結果を確認できませんでした。');
  return jobFromPayload(payload);
}

function resumeJob(job, {scroll = false} = {}) {
  if (!job || !job.id) return false;
  const cancellable = ['queued', 'running'].includes(job.status);
  const active = cancellable || ['admitting', 'committing'].includes(job.status);
  currentJobId = String(job.id);
  storePendingSubmissionId('');
  clearPollTimer();
  renderProgress(job);
  if (resultCard) resultCard.hidden = true;
  if (progressCard) {
    progressCard.hidden = false;
    if (scroll) progressCard.scrollIntoView({behavior: 'smooth', block: 'start'});
  }
  if (active) {
    storeActiveJobId(currentJobId);
    setRunning(true);
    if (cancelButton) cancelButton.disabled = !cancellable;
    schedulePoll();
    return true;
  }
  storeActiveJobId('');
  setRunning(false);
  if (cancelButton) cancelButton.disabled = true;
  if (job.status === 'completed') renderResult(job);
  return true;
}

async function restoreActiveJob() {
  const restoreGeneration = ++jobFlowGeneration;
  setRunning(true);
  if (cancelButton) cancelButton.disabled = true;
  const storedId = storedActiveJobId();
  if (storedId) {
    try {
      const response = await apiFetch(`/api/jobs/${encodeURIComponent(storedId)}`, {cache: 'no-store'});
      const payload = await readJsonResponse(response);
      if (restoreGeneration !== jobFlowGeneration) return;
      if (response.ok) {
        const job = jobFromPayload(payload);
        if (job) {
          pollFailureCount = 0;
          resumeJob(job);
          return;
        }
      } else if (response.status !== 404) {
        throw new Error(payload.error || '保存したジョブへ再接続できませんでした。');
      }
      const persistedJob = await fetchPersistedJob(storedId);
      if (restoreGeneration !== jobFlowGeneration) return;
      if (persistedJob) {
        pollFailureCount = 0;
        resumeJob(persistedJob);
        return;
      }
      storeActiveJobId('');
    } catch (_) {
      if (restoreGeneration !== jobFlowGeneration) return;
      currentJobId = storedId;
      storeActiveJobId(storedId);
      setRunning(true);
      if (progressCard) progressCard.hidden = false;
      const message = document.querySelector('#progress-message');
      if (message) message.textContent = '実行中ジョブへ再接続しています…';
      schedulePoll();
      return;
    }
  }
  const pendingSubmissionId = storedPendingSubmissionId();
  if (pendingSubmissionId) {
    if (pendingSubmissionRetryAllowed(pendingSubmissionId)) {
      setRunning(false);
      setAlert(
        formError,
        '前回の送信は未受付と確認されました。同じ送信IDで安全に再送できます。必要ならファイルを選び直して［文字起こしを開始］を押してください。',
        true
      );
      return;
    }
    setRunning(true);
    if (progressCard) progressCard.hidden = false;
    const message = document.querySelector('#progress-message');
    if (message) message.textContent = '送信中だったジョブの受付状況を確認しています…';
    await recoverSubmittedJob(
      '送信中にページが再読み込みされました。',
      pendingSubmissionId,
      0,
      restoreGeneration
    );
    return;
  }
  try {
    const activeJob = await fetchActiveJob();
    if (restoreGeneration !== jobFlowGeneration) return;
    if (activeJob) {
      pollFailureCount = 0;
      resumeJob(activeJob);
      return;
    }
  } catch (_) {
    // Older backends may not expose /api/jobs/active yet. Normal startup continues.
  }
  if (restoreGeneration === jobFlowGeneration) {
    currentJobId = null;
    setRunning(false);
    if (cancelButton) cancelButton.disabled = true;
  }
}

async function recoverSubmittedJob(
  errorMessage,
  submissionId,
  attempt = 0,
  recoveryGeneration = jobFlowGeneration,
  absenceConfirmed = false
) {
  if (recoveryGeneration !== jobFlowGeneration) return;
  let confirmedAbsentThisAttempt = false;
  try {
    let recoveredJob = null;
    let exactAbsent = !submissionId;
    let persistedAbsent = !submissionId;
    if (submissionId) {
      const response = await apiFetch(`/api/jobs/${encodeURIComponent(submissionId)}`, {cache: 'no-store'});
      if (response.ok) recoveredJob = jobFromPayload(await readJsonResponse(response));
      else if (response.status !== 404) {
        const payload = await readJsonResponse(response);
        throw new Error(payload.error || '送信したジョブを確認できませんでした。');
      } else {
        exactAbsent = true;
      }
      if (!recoveredJob) {
        recoveredJob = await fetchPersistedJob(submissionId);
        persistedAbsent = !recoveredJob;
      }
    }
    let activeAbsent = false;
    if (!recoveredJob) {
      recoveredJob = await fetchActiveJob();
      activeAbsent = !recoveredJob;
    }
    confirmedAbsentThisAttempt = exactAbsent && persistedAbsent && activeAbsent;
    if (recoveryGeneration !== jobFlowGeneration) return;
    if (recoveredJob) {
      pollFailureCount = 0;
      resumeJob(recoveredJob, {scroll: true});
      setAlert(formError, '送信結果を再確認し、文字起こしジョブへ接続しました。', true);
      return;
    }
  } catch (_) {
    // A transient read failure is handled by the same bounded retry as a 404/204.
  }
  if (recoveryGeneration !== jobFlowGeneration) return;
  const confirmedAbsent = absenceConfirmed || confirmedAbsentThisAttempt;
  if (attempt + 1 >= submitRecoveryMaxAttempts) {
    storeActiveJobId('');
    currentJobId = null;
    setRunning(false);
    if (progressCard) progressCard.hidden = true;
    if (confirmedAbsent) markPendingSubmissionRetryable(submissionId);
    setAlert(
      formError,
      confirmedAbsent
        ? `${errorMessage} サーバーで受付が確認されませんでした。同じ送信IDで再送するため、もう一度［文字起こしを開始］を押してください。`
        : `${errorMessage} 受付状況を確認できません。前回の送信IDを保護しています。接続回復後にもう一度［文字起こしを開始］を押すか、ページを再読み込みしてください。`,
      true
    );
    return;
  }
  const delay = Math.min(pollMaxDelayMs, pollBaseDelayMs * (2 ** attempt));
  const message = document.querySelector('#progress-message');
  if (message) message.textContent = `送信の受付状況を確認しています… ${Math.ceil(delay / 1000)}秒後に再試行します。`;
  if (cancelButton) cancelButton.disabled = true;
  window.setTimeout(() => {
    if (recoveryGeneration === jobFlowGeneration) {
      recoverSubmittedJob(
        errorMessage,
        submissionId,
        attempt + 1,
        recoveryGeneration,
        confirmedAbsent
      );
    }
  }, delay);
}

listen(form, 'submit', async event => {
  event.preventDefault();
  setAlert(formError, '');
  const unresolvedSubmissionId = storedPendingSubmissionId();
  const retryUnacceptedSubmission = Boolean(
    unresolvedSubmissionId && pendingSubmissionRetryAllowed(unresolvedSubmissionId)
  );
  if (unresolvedSubmissionId && !retryUnacceptedSubmission) {
    const recoveryGeneration = ++jobFlowGeneration;
    setRunning(true);
    if (resultCard) resultCard.hidden = true;
    if (progressCard) {
      progressCard.hidden = false;
      progressCard.scrollIntoView({behavior: 'smooth', block: 'start'});
    }
    if (cancelButton) cancelButton.disabled = true;
    const message = document.querySelector('#progress-message');
    if (message) message.textContent = '前回の送信結果を再確認しています…';
    await recoverSubmittedJob(
      '前回の送信結果がまだ確認できません。',
      unresolvedSubmissionId,
      0,
      recoveryGeneration
    );
    return;
  }
  if (!sourcePath.value.trim() && !(inputFile && inputFile.files && inputFile.files.length)) {
    setAlert(formError, '処理する音声・動画ファイルを選択してください。', true);
    const sourceSection = document.querySelector('#setup-source');
    if (sourceSection) sourceSection.scrollIntoView({behavior: 'smooth', block: 'start'});
    return;
  }
  const provider = aiProvider ? aiProvider.value : 'none';
  if (provider === 'none') aiOptionInputs.forEach(input => { input.checked = false; });
  const wantsAi = provider !== 'none' && aiOptionInputs.some(input => input.checked);
  if (wantsAi && provider === 'none') {
    setAlert(formError, 'AI 機能を使う場合は OpenAI または Google Gemini を選択してください。', true);
    return;
  }
  // Disabled form controls are omitted from FormData. Capture every selected
  // option, especially source_path/input_file, before locking the form.
  const jobFormData = new FormData(form);
  const submissionId = retryUnacceptedSubmission
    ? unresolvedSubmissionId
    : createSubmissionId();
  const submissionGeneration = ++jobFlowGeneration;
  storePendingSubmissionId(submissionId);
  let responseStatus = null;
  setRunning(true);
  resultCard.hidden = true;
  progressCard.hidden = false;
  progressCard.scrollIntoView({behavior: 'smooth', block: 'start'});
  try {
    const response = await apiFetch('/api/jobs', {
      method: 'POST',
      headers: {'X-Gurumoji-Submission-Id': submissionId},
      body: jobFormData
    });
    responseStatus = response.status;
    const data = await readJsonResponse(response);
    if (submissionGeneration !== jobFlowGeneration) return;
    if (response.status === 409) {
      let activeJob = jobFromPayload(data);
      if (!activeJob) {
        try { activeJob = await fetchActiveJob(); } catch (_) { activeJob = null; }
      }
      if (submissionGeneration !== jobFlowGeneration) return;
      if (activeJob) {
        pollFailureCount = 0;
        resumeJob(activeJob, {scroll: true});
        setAlert(formError, data.error || '実行中の文字起こしへ再接続しました。', true);
        return;
      }
    }
    if (!response.ok) throw new Error(data.error || '処理を開始できませんでした。');
    pollFailureCount = 0;
    resumeJob(data);
  } catch (error) {
    if (submissionGeneration !== jobFlowGeneration) return;
    clearPollTimer();
    currentJobId = null;
    if (cancelButton) cancelButton.disabled = true;
    if (responseStatus !== null && responseStatus >= 400 && responseStatus < 500) {
      storePendingSubmissionId('');
      setRunning(false);
      if (progressCard) progressCard.hidden = true;
      setAlert(formError, error.message, true);
      return;
    }
    await recoverSubmittedJob(error.message, submissionId, 0, submissionGeneration);
  }
});

async function pollJob() {
  if (!currentJobId) return;
  const requestedJobId = currentJobId;
  try {
    const response = await apiFetch(`/api/jobs/${encodeURIComponent(requestedJobId)}`, {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (requestedJobId !== currentJobId) return;
    if (response.status === 404) {
      const persistedJob = await fetchPersistedJob(requestedJobId);
      if (persistedJob) {
        pollFailureCount = 0;
        resumeJob(persistedJob);
        return;
      }
      let activeJob = null;
      try { activeJob = await fetchActiveJob(); } catch (_) { activeJob = null; }
      if (activeJob) {
        pollFailureCount = 0;
        resumeJob(activeJob);
        return;
      }
      clearPollTimer();
      storeActiveJobId('');
      currentJobId = null;
      setRunning(false);
      if (cancelButton) cancelButton.disabled = true;
      throw new Error(data.error || '実行中ジョブが見つかりません。アプリを再起動した可能性があります。');
    }
    if (!response.ok) throw new Error(data.error || '進捗を取得できません。');
    pollFailureCount = 0;
    resumeJob(data);
  } catch (error) {
    if (!currentJobId || !jobRunning) {
      document.querySelector('#progress-message').textContent = error.message;
      return;
    }
    pollFailureCount += 1;
    const delay = Math.min(pollMaxDelayMs, pollBaseDelayMs * (2 ** Math.min(pollFailureCount - 1, 5)));
    document.querySelector('#progress-message').textContent = `${error.message} ${Math.ceil(delay / 1000)}秒後に再接続します…`;
    schedulePoll(delay);
  }
}

function fallbackProgressStage(job, progress) {
  if (job.status === 'admitting') return {label: '送信データの受付', progress: 0};
  if (job.status === 'queued') return {label: '開始準備', progress: 0};
  if (job.status === 'committing') return {label: '結果ファイルの保存', progress: Math.max(75, progress)};
  if (job.status === 'completed') return {label: '処理完了', progress: 100};
  const stages = [
    [0, 8, '処理環境の確認'],
    [8, 52, '文字起こし'],
    [52, 64, '発話時刻の補正'],
    [64, 80, '話者の分離'],
    [80, 88, '文字起こしの仕上げ'],
    [88, 90, '音声感情の分析'],
    [90, 94, '話者名の確認'],
    [94, 97, '議題アウトラインの作成'],
    [97, 100, '結果ファイルの保存']
  ];
  const stage = stages.find(([start, end]) => progress >= start && progress < end) || stages.at(-1);
  const [start, end, label] = stage;
  return {label, progress: Math.round(100 * (progress - start) / Math.max(1, end - start))};
}

function renderAiTokenUsage(rootSelector, rawUsage) {
  const root = document.querySelector(rootSelector);
  if (!root) return;
  const usage = rawUsage && typeof rawUsage === 'object' ? rawUsage : {};
  const provider = String(usage.provider || '').toLowerCase();
  const requestCount = Math.max(0, Number(usage.request_count) || 0);
  const visible = ['openai', 'google'].includes(provider) && requestCount > 0;
  root.hidden = !visible;
  if (!visible) return;
  const format = value => new Intl.NumberFormat('ja-JP').format(Math.max(0, Number(value) || 0));
  const providerElement = root.querySelector('[data-ai-provider]');
  const modelElement = root.querySelector('[data-ai-model]');
  const inputElement = root.querySelector('[data-ai-input]');
  const outputElement = root.querySelector('[data-ai-output]');
  const totalElement = root.querySelector('[data-ai-total]');
  const requestsElement = root.querySelector('[data-ai-requests]');
  if (providerElement) providerElement.textContent = provider === 'openai' ? 'OpenAI' : 'Google Gemini';
  if (modelElement) modelElement.textContent = String(usage.model || '');
  if (inputElement) inputElement.textContent = format(usage.input_tokens);
  if (outputElement) outputElement.textContent = format(usage.output_tokens);
  if (totalElement) totalElement.textContent = format(usage.total_tokens);
  if (requestsElement) requestsElement.textContent = `${format(requestCount)}回`;
  const optionalDetails = [
    ['[data-ai-cached]', usage.cached_tokens],
    ['[data-ai-reasoning]', usage.reasoning_tokens]
  ];
  optionalDetails.forEach(([selector, value]) => {
    const element = root.querySelector(selector);
    const count = Math.max(0, Number(value) || 0);
    if (!element) return;
    element.hidden = count <= 0;
    const number = element.querySelector('b');
    if (number) number.textContent = format(count);
  });
  const unreported = root.querySelector('[data-ai-unreported]');
  if (unreported) unreported.hidden = Boolean(usage.reported);
}

function renderProgress(job) {
  const progress = Number(job.progress || 0);
  const fallbackStage = fallbackProgressStage(job, progress);
  const hasCurrentStage = Boolean(job.stage_label)
    && !(job.stage === 'queued' && job.status === 'running' && progress > 0);
  const stageLabel = hasCurrentStage ? job.stage_label : fallbackStage.label;
  const stageProgress = Math.max(0, Math.min(100, Number(
    hasCurrentStage ? job.stage_progress : fallbackStage.progress
  ) || 0));
  const active = ['admitting', 'queued', 'running', 'committing'].includes(job.status);
  const activityLabels = {
    admitting: 'RECEIVING', queued: 'WAITING', running: 'RUNNING', committing: 'SAVING',
    completed: 'COMPLETED', failed: 'ERROR', cancelled: 'STOPPED'
  };
  progressCard.classList.toggle('is-active', active);
  progressCard.classList.toggle('has-error', ['failed', 'cancelled'].includes(job.status));
  document.querySelector('#progress-number').textContent = `${progress}%`;
  document.querySelector('#progress-bar').style.width = `${progress}%`;
  document.querySelector('#progress-overall-track').setAttribute('aria-valuenow', String(progress));
  document.querySelector('#progress-stage-label').textContent = stageLabel;
  document.querySelector('#progress-stage-number').textContent = `${stageProgress}%`;
  document.querySelector('#progress-stage-bar').style.width = `${stageProgress}%`;
  document.querySelector('#progress-stage-track').setAttribute('aria-valuenow', String(stageProgress));
  document.querySelector('#progress-activity-label').textContent = activityLabels[job.status] || 'WORKING';
  document.querySelector('#progress-message').textContent = job.message || '';
  document.querySelector('#progress-log').textContent = (job.logs || []).join('\n');
  renderAiTokenUsage('#progress-ai-usage', job.ai_usage);
  const titles = {admitting: '受付中', queued: '開始待ち', running: '文字起こし中', committing: '結果を保存中', completed: '処理完了', failed: 'エラー', cancelled: '中止しました'};
  document.querySelector('#progress-title').textContent = titles[job.status] || '処理中';
  document.querySelector('#progress-message').style.color = ['failed', 'cancelled'].includes(job.status) ? '#913733' : '';
}

listen(cancelButton, 'click', async () => {
  if (!currentJobId) return;
  cancelButton.disabled = true;
  try {
    const response = await apiFetch(`/api/jobs/${currentJobId}/cancel`, {method: 'POST'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error);
    document.querySelector('#progress-message').textContent = '中止を要求しました…';
  } catch (error) {
    document.querySelector('#progress-message').textContent = error.message;
    if (jobRunning) cancelButton.disabled = false;
  }
});

function updateFacetSelect(select, values, allLabel) {
  const selected = select.value;
  select.replaceChildren(new Option(allLabel, ''));
  values.forEach(value => select.add(new Option(value, value)));
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

function libraryFilterState() {
  return {
    keyword: document.querySelector('#library-keyword').value.trim(),
    speaker: document.querySelector('#library-speaker').value,
    emotion: document.querySelector('#library-emotion').value,
    sort: document.querySelector('#library-sort').value
  };
}

function updateLibraryFilterState() {
  const state = libraryFilterState();
  const conditions = [];
  if (state.keyword) conditions.push(`「${state.keyword}」`);
  if (state.speaker) conditions.push(`話者: ${state.speaker}`);
  if (state.emotion) conditions.push(`感情: ${state.emotion}`);
  if (state.sort !== 'updated_desc') {
    const sort = document.querySelector('#library-sort');
    conditions.push(`並び: ${sort.options[sort.selectedIndex].text}`);
  }
  const summary = document.querySelector('#library-filter-summary');
  const badge = document.querySelector('#library-filter-badge');
  const clear = document.querySelector('#library-clear-filters');
  if (summary) summary.textContent = conditions.length
    ? `${conditions.join(' / ')} で表示しています`
    : 'すべてのデータを表示しています';
  if (badge) badge.textContent = conditions.length ? `${conditions.length}条件` : '条件なし';
  if (clear) clear.disabled = conditions.length === 0;
}

function renderLibraryLoading() {
  const list = document.querySelector('#library-list');
  list.replaceChildren();
  for (let index = 0; index < 3; index += 1) {
    const skeleton = document.createElement('div');
    skeleton.className = 'library-skeleton';
    skeleton.setAttribute('aria-hidden', 'true');
    skeleton.innerHTML = '<i></i><div><b></b><span></span><span></span></div>';
    list.append(skeleton);
  }
}

function renderLibraryOverview(items) {
  const duration = items.reduce((sum, item) => sum + Number(item.duration || 0), 0);
  const speakers = new Set(items.flatMap(item => item.speakers || []));
  const latest = items.reduce((value, item) => {
    const updated = String(item.updated_at || '');
    return updated > value ? updated : value;
  }, '');
  const values = {
    '#library-total-metric': String(items.length),
    '#library-duration-metric': items.length ? formatTime(duration) : '00:00',
    '#library-speaker-metric': String(speakers.size),
    '#library-updated-metric': latest ? formatDate(latest) : '—'
  };
  Object.entries(values).forEach(([selector, value]) => {
    const element = document.querySelector(selector);
    if (element) element.textContent = value;
  });
}

async function loadLibrary() {
  const list = document.querySelector('#library-list');
  const message = document.querySelector('#library-message');
  setAlert(message, '');
  updateLibraryFilterState();
  const state = libraryFilterState();
  const params = new URLSearchParams(state);
  if (libraryRequestController) libraryRequestController.abort();
  libraryRequestController = new AbortController();
  const requestId = ++libraryRequestSequence;
  list.setAttribute('aria-busy', 'true');
  renderLibraryLoading();
  try {
    const response = await apiFetch(`/api/library?${params}`, {signal: libraryRequestController.signal});
    const data = await readJsonResponse(response);
    if (requestId !== libraryRequestSequence) return;
    if (!response.ok) throw new Error(data.error || 'ライブラリを取得できません。');
    updateFacetSelect(document.querySelector('#library-speaker'), data.facets.speakers || [], 'すべての話者');
    updateFacetSelect(document.querySelector('#library-emotion'), data.facets.emotions || [], 'すべての感情');
    const items = data.items || [];
    document.querySelector('#library-count').textContent = `${data.total}件を表示`;
    renderLibraryOverview(items);
    renderLibraryItems(items);
    updateLibraryFilterState();
    if (!trainingStatusLoaded) loadTrainingStatus();
  } catch (error) {
    if (error.name === 'AbortError') return;
    if (requestId !== libraryRequestSequence) return;
    list.replaceChildren();
    setAlert(message, error.message, true);
  } finally {
    if (requestId === libraryRequestSequence) list.setAttribute('aria-busy', 'false');
  }
}

function renderLibraryItems(items) {
  const list = document.querySelector('#library-list');
  list.replaceChildren();
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'library-empty';
    const title = document.createElement('strong');
    title.textContent = '条件に一致するデータはありません';
    const description = document.createElement('p');
    description.textContent = '検索条件を変えるか、新しい文字起こしを始めてください。';
    const actions = document.createElement('div');
    const clear = document.createElement('button');
    clear.type = 'button';
    clear.className = 'secondary-button';
    clear.textContent = '条件をクリア';
    clear.addEventListener('click', clearLibraryFilters);
    const create = document.createElement('button');
    create.type = 'button';
    create.className = 'primary-button small';
    create.textContent = '＋ 新しい文字起こし';
    create.addEventListener('click', () => showView('new'));
    actions.append(clear, create);
    empty.append(title, description, actions);
    list.append(empty);
    return;
  }
  items.forEach(item => {
    const card = document.createElement('article');
    card.className = 'library-item';
    const media = document.createElement('div');
    media.className = 'library-media';
    const thumbnail = document.createElement('img');
    thumbnail.className = 'library-thumbnail';
    thumbnail.src = item.thumbnail_url;
    thumbnail.alt = `${item.source_name} のワードクラウド`;
    thumbnail.loading = 'lazy';
    const mediaFallback = document.createElement('span');
    mediaFallback.className = 'library-media-fallback';
    mediaFallback.textContent = 'プレビューなし';
    const mediaBadge = document.createElement('span');
    mediaBadge.className = 'library-media-badge';
    mediaBadge.textContent = item.media_url ? (item.media_kind === 'video' ? '動画' : '音声') : 'テキスト';
    thumbnail.addEventListener('error', () => {
      media.classList.add('unavailable');
      thumbnail.remove();
    });
    media.append(thumbnail, mediaFallback, mediaBadge);
    const body = document.createElement('div');
    body.className = 'library-item-body';
    const heading = document.createElement('div');
    heading.className = 'library-item-heading';
    const title = document.createElement('h3');
    title.textContent = item.source_name;
    const updated = document.createElement('time');
    updated.dateTime = item.updated_at || '';
    updated.textContent = `更新 ${formatDate(item.updated_at)}`;
    heading.append(title, updated);
    const meta = document.createElement('div');
    meta.className = 'library-meta';
    const mediaLabel = item.media_url ? (item.media_kind === 'video' ? '動画あり' : '音声あり') : '元メディアなし';
    [
      `発話 ${item.segment_count}件`,
      formatTime(item.duration),
      mediaLabel,
      `修正 ${item.revision_count}回`
    ].forEach(value => {
      const metric = document.createElement('span');
      metric.textContent = value;
      meta.append(metric);
    });
    const preview = document.createElement('p');
    preview.className = 'library-preview';
    preview.textContent = item.preview || '本文はまだありません。';
    const chips = document.createElement('div');
    chips.className = 'library-chips';
    (item.speakers || []).slice(0, 5).forEach(value => {
      const chip = document.createElement('span');
      chip.className = 'library-chip';
      chip.textContent = value;
      chips.append(chip);
    });
    if ((item.speakers || []).length > 5) {
      const chip = document.createElement('span');
      chip.className = 'library-chip';
      chip.textContent = `＋${item.speakers.length - 5}人`;
      chips.append(chip);
    }
    (item.emotions || []).forEach(value => {
      const chip = document.createElement('span');
      chip.className = 'library-chip emotion';
      chip.textContent = value;
      chips.append(chip);
    });
    if (item.match_count) {
      const chip = document.createElement('span');
      chip.className = 'library-chip';
      chip.textContent = `キーワード一致 ${item.match_count}発話`;
      chips.append(chip);
    }
    body.append(heading, meta, preview, chips);
    const actions = document.createElement('div');
    actions.className = 'library-actions';
    const open = document.createElement('button');
    open.className = 'library-card-open';
    open.type = 'button';
    open.setAttribute('aria-label', `${item.source_name}を開いて編集`);
    open.addEventListener('click', () => openLibraryItem(item.id));
    const analyze = document.createElement('button');
    analyze.className = 'library-analysis-button';
    analyze.type = 'button';
    analyze.textContent = '分析・可視化';
    analyze.setAttribute('aria-label', `${item.source_name}を分析・可視化`);
    analyze.addEventListener('click', () => openAnalysisForItem(item.id));
    const remove = document.createElement('button');
    remove.className = 'library-delete-button';
    remove.type = 'button';
    remove.textContent = '削除';
    remove.setAttribute('aria-label', `${item.source_name}を削除`);
    remove.addEventListener('click', () => deleteLibraryItem(item.id, item.source_name));
    actions.append(analyze, remove);
    card.append(open, media, body, actions);
    list.append(card);
  });
}

async function loadTrainingStatus() {
  const container = document.querySelector('#training-status');
  if (trainingStatusLoaded) return;
  trainingStatusLoaded = true;
  try {
    const response = await apiFetch('/api/training');
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '学習履歴を確認できませんでした。');
    container.replaceChildren();
    const label = document.createElement('span');
    label.textContent = `くしなだ学習データ: ${data.event_count}件（音声＋感情 ${data.ready_count}件）`;
    container.append(label);
    if (data.jsonl_url) {
      const link = document.createElement('a');
      link.href = data.jsonl_url;
      link.textContent = 'JSONL';
      link.download = '';
      container.append(link);
    }
    if (data.manifest_url) {
      const link = document.createElement('a');
      link.href = data.manifest_url;
      link.textContent = 'CSV';
      link.download = '';
      container.append(link);
    }
  } catch (error) {
    trainingStatusLoaded = false;
    container.textContent = error.message || '学習履歴を確認できませんでした。';
  }
}

['#library-speaker', '#library-emotion', '#library-sort'].forEach(selector => {
  listen(document.querySelector(selector), 'change', () => loadLibrary());
});
listen(document.querySelector('#library-keyword'), 'input', () => {
  window.clearTimeout(libraryTimer);
  libraryTimer = window.setTimeout(loadLibrary, 250);
});

function clearLibraryFilters() {
  document.querySelector('#library-keyword').value = '';
  document.querySelector('#library-speaker').value = '';
  document.querySelector('#library-emotion').value = '';
  document.querySelector('#library-sort').value = 'updated_desc';
  updateLibraryFilterState();
  loadLibrary();
}

function setLibraryFiltersOpen(open) {
  if (!libraryCard) return;
  libraryCard.classList.toggle('filters-open', open);
  const toggle = document.querySelector('#library-filter-toggle');
  if (toggle) toggle.setAttribute('aria-expanded', String(open));
}

listen(document.querySelector('#library-clear-filters'), 'click', clearLibraryFilters);
listen(document.querySelector('#library-filter-toggle'), 'click', event => {
  setLibraryFiltersOpen(event.currentTarget.getAttribute('aria-expanded') !== 'true');
});
listen(document.querySelector('#library-refresh-button'), 'click', () => {
  trainingStatusLoaded = false;
  loadLibrary();
});
listen(document.querySelector('#library-create-new-button'), 'click', () => showView('new'));

function selectedAiModelEntry() {
  if (!aiModelSelect) return null;
  return aiModelCatalog.find(item => item.id === aiModelSelect.value) || null;
}

function updateAiModelDescription() {
  if (!aiModelDescription) return;
  const entry = selectedAiModelEntry();
  aiModelDescription.textContent = entry
    ? (entry.description || `モデルID: ${entry.id}`)
    : 'モデルを選択してください。';
}

function renderAiModelOptions() {
  if (!aiModelSelect) return;
  const query = String(aiModelSearch && aiModelSearch.value || '').trim().toLocaleLowerCase();
  const previous = aiModelSelect.value || String(aiModelDialog && aiModelDialog.dataset.selectedModel || '');
  const visible = aiModelCatalog.filter(item => {
    const haystack = `${item.id} ${item.label || ''} ${item.description || ''}`.toLocaleLowerCase();
    return !query || haystack.includes(query);
  });
  aiModelSelect.replaceChildren();
  visible.forEach(item => {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.label && item.label !== item.id
      ? `${item.label} (${item.id})`
      : item.id;
    aiModelSelect.append(option);
  });
  if (visible.some(item => item.id === previous)) aiModelSelect.value = previous;
  else if (visible.length) aiModelSelect.selectedIndex = 0;
  if (saveAiModelButton) saveAiModelButton.disabled = visible.length === 0;
  updateAiModelDescription();
}

async function openAiModelDialog(provider) {
  const normalizedProvider = String(provider || '').trim().toLowerCase();
  if (!['openai', 'google'].includes(normalizedProvider)) return;
  const label = normalizedProvider === 'google' ? 'Google Gemini' : 'OpenAI';
  if (!tokenConfigSnapshot[normalizedProvider]) {
    window.alert(`${label} APIキーがtokens.jsonに設定されていません。`);
    return;
  }
  activeAiModelProvider = normalizedProvider;
  aiModelCatalog = [];
  if (aiModelProviderLabel) aiModelProviderLabel.textContent = label;
  if (aiModelCurrent) aiModelCurrent.textContent = String(tokenConfigSnapshot[`${normalizedProvider}_model`] || '読込中…');
  if (aiModelSearch) aiModelSearch.value = '';
  if (aiModelDescription) aiModelDescription.textContent = 'APIから利用可能なモデルを取得しています…';
  setAlert(aiModelError, '');
  if (aiModelSelect) {
    const loadingOption = document.createElement('option');
    loadingOption.textContent = 'モデル一覧を読込中…';
    loadingOption.disabled = true;
    aiModelSelect.replaceChildren(loadingOption);
  }
  if (saveAiModelButton) saveAiModelButton.disabled = true;
  if (!aiModelDialog || typeof aiModelDialog.showModal !== 'function') {
    window.alert('このブラウザではモデル選択画面を開けません。');
    return;
  }
  if (!aiModelDialog.open) aiModelDialog.showModal();
  try {
    const response = await apiFetch(`/api/ai/models?provider=${encodeURIComponent(normalizedProvider)}`, {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'モデル一覧を取得できませんでした。');
    const selected = String(data.selected_model || '').trim();
    const models = Array.isArray(data.models) ? data.models : [];
    aiModelCatalog = models
      .map(item => ({
        id: String(item && item.id || '').trim(),
        label: String(item && item.label || '').trim(),
        description: String(item && item.description || '').trim()
      }))
      .filter(item => item.id);
    if (selected && !aiModelCatalog.some(item => item.id === selected)) {
      aiModelCatalog.unshift({
        id: selected,
        label: selected,
        description: 'tokens.jsonで現在選択されているモデルです。'
      });
    }
    aiModelDialog.dataset.selectedModel = selected;
    if (aiModelCurrent) aiModelCurrent.textContent = selected || '未設定';
    renderAiModelOptions();
    window.requestAnimationFrame(() => aiModelSearch && aiModelSearch.focus());
  } catch (error) {
    if (aiModelSelect) aiModelSelect.replaceChildren();
    if (aiModelDescription) aiModelDescription.textContent = '';
    setAlert(aiModelError, error.message, true);
  }
}

document.querySelectorAll('[data-model-provider]').forEach(button => {
  listen(button, 'click', () => openAiModelDialog(button.dataset.modelProvider));
});
listen(document.querySelector('#cancel-ai-model-button'), 'click', () => {
  if (aiModelDialog) aiModelDialog.close();
});
listen(aiModelSearch, 'input', renderAiModelOptions);
listen(aiModelSelect, 'change', updateAiModelDescription);
listen(aiModelForm, 'submit', async event => {
  event.preventDefault();
  const model = String(aiModelSelect && aiModelSelect.value || '').trim();
  if (!activeAiModelProvider || !model) {
    setAlert(aiModelError, 'モデルを選択してください。', true);
    return;
  }
  setAlert(aiModelError, '');
  if (saveAiModelButton) saveAiModelButton.disabled = true;
  try {
    const response = await apiFetch('/api/ai/model', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({provider: activeAiModelProvider, model})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'モデル設定を保存できませんでした。');
    if (aiModelDialog) aiModelDialog.close();
    await loadConfig();
    setAlert(document.querySelector('#token-message'), `${model} をtokens.jsonに保存しました。`);
  } catch (error) {
    setAlert(aiModelError, error.message, true);
    if (saveAiModelButton) saveAiModelButton.disabled = false;
  }
});

const addRecordDialog = document.querySelector('#add-record-dialog');
const addRecordForm = document.querySelector('#add-record-form');
const addRecordName = document.querySelector('#add-record-name');

function openAddRecordDialog() {
  setAlert(document.querySelector('#add-record-error'), '');
  if (addRecordName) addRecordName.value = '';
  if (addRecordDialog && typeof addRecordDialog.showModal === 'function') {
    addRecordDialog.showModal();
    window.requestAnimationFrame(() => addRecordName && addRecordName.focus());
    return;
  }
  const fallbackName = window.prompt('追加するデータの名前を入力してください。', '新規文字起こし');
  if (fallbackName && fallbackName.trim()) createEmptyLibraryRecord(fallbackName.trim());
}

async function createEmptyLibraryRecord(sourceName) {
  try {
    const response = await apiFetch('/api/library', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({source_name: sourceName})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '追加できませんでした。');
    if (addRecordDialog && addRecordDialog.open) addRecordDialog.close();
    renderResult(data);
  } catch (error) {
    const target = addRecordDialog && addRecordDialog.open
      ? document.querySelector('#add-record-error')
      : document.querySelector('#library-message');
    setAlert(target, error.message, true);
  } finally {
    const button = document.querySelector('#confirm-add-record-button');
    if (button) button.disabled = false;
  }
}

listen(document.querySelector('#add-record-button'), 'click', openAddRecordDialog);
listen(document.querySelector('#cancel-add-record-button'), 'click', () => {
  if (addRecordDialog) addRecordDialog.close();
});
listen(addRecordForm, 'submit', event => {
  event.preventDefault();
  if (!addRecordName || !addRecordName.reportValidity()) return;
  const button = document.querySelector('#confirm-add-record-button');
  if (button) button.disabled = true;
  createEmptyLibraryRecord(addRecordName.value.trim());
});

async function openLibraryItem(itemId) {
  try {
    const response = await apiFetch(`/api/library/${itemId}`);
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'データを開けませんでした。');
    renderResult(data);
  } catch (error) {
    setAlert(document.querySelector('#library-message'), error.message, true);
  }
}

function deleteRecoveryNote(data) {
  const paths = Array.isArray(data && data.recovery_paths)
    ? data.recovery_paths
      .map(value => String(value || '').trim())
      .filter(Boolean)
    : [];
  return paths.length ? ` 復旧・確認先: ${paths.join(' / ')}` : '';
}

async function deleteLibraryItem(itemId, name) {
  if (!window.confirm(`「${name}」をライブラリから削除しますか？\n保存メディアも削除されます。出力ファイルと学習履歴は残ります。`)) return;
  try {
    if (currentJobId === itemId && mediaPlayer) {
      mediaPlayer.pause();
      mediaPlayer.removeAttribute('src');
      mediaPlayer.load();
      mediaPlayer = null;
    }
    const response = await apiFetch(`/api/library/${itemId}`, {method: 'DELETE'});
    const data = await readJsonResponse(response);
    const recoveryNote = deleteRecoveryNote(data);
    if (!response.ok) {
      throw new Error(`${data.error || '削除できませんでした。'}${recoveryNote}`);
    }
    if (currentJobId === itemId) {
      currentJobId = null;
      currentJob = null;
      storeActiveJobId('');
      setCurrentJobDirty(false);
    }
    analysisCatalogLoaded = false;
    analysisCatalog = [];
    if (analysisState.itemId === itemId) {
      analysisState.itemId = '';
      analysisState.data = null;
      analysisState.config = {};
      analysisState.annotations = {};
      setAnalysisDirty(false);
    }
    showView('library');
    await loadLibrary();
    const cleanupWarning = data.cleanup_warning || '';
    setAlert(
      document.querySelector('#library-message'),
      `「${name}」を削除しました。${cleanupWarning}${recoveryNote}`,
      Boolean(cleanupWarning || recoveryNote)
    );
  } catch (error) {
    setAlert(document.querySelector('#library-message'), error.message, true);
  }
}

function renderDownloads(files) {
  const container = document.querySelector('#download-links');
  container.replaceChildren();
  (files || []).filter(file => !String(file.name || '').toLowerCase().endsWith('.json')).forEach(file => {
    const link = document.createElement('a');
    link.href = file.url;
    link.textContent = `${file.name.split('.').pop().toUpperCase()} を保存`;
    link.setAttribute('download', file.name);
    container.append(link);
  });
}

function renderOutline(outline) {
  const view = document.querySelector('#outline-view');
  const content = document.querySelector('#outline-content');
  content.replaceChildren();
  const sections = outline && Array.isArray(outline.sections) ? outline.sections : [];
  if (!sections.length) {
    const empty = document.createElement('p');
    empty.className = 'outline-empty';
    empty.textContent = 'AIアウトラインはまだありません。新しい文字起こしでAI仕上げを有効にすると、ここへ自動生成されます。';
    content.append(empty);
    view.hidden = false;
    return;
  }
  sections.forEach(section => {
    const row = document.createElement('section');
    row.className = 'outline-section';
    const time = document.createElement('span');
    time.className = 'outline-time';
    time.textContent = `${formatTime(section.start)}–${formatTime(section.end)}`;
    const body = document.createElement('div');
    const title = document.createElement('h4');
    title.textContent = section.title || '議題';
    const list = document.createElement('ul');
    (section.bullets || []).forEach(value => {
      const item = document.createElement('li');
      item.textContent = value;
      list.append(item);
    });
    body.append(title, list);
    row.append(time, body);
    content.append(row);
  });
  view.hidden = false;
}

function segmentEmotionText(segment) {
  const emotions = segment && typeof segment.emotions === 'object' && segment.emotions ? segment.emotions : {};
  return Object.keys(emotions).sort().map(key => {
    const item = emotions[key] || {};
    const confidence = typeof item.confidence === 'number' ? ` ${item.confidence.toFixed(2)}` : '';
    return `${item.model_name || key}: ${item.label_ja || item.label || '不明'}${confidence}`;
  }).join(' / ');
}

function kushinadaEmotion(segment) {
  const data = segment && segment.emotions && segment.emotions.kushinada;
  return data && data.label ? data.label : '';
}

function renderEmotionSummary(summary) {
  const view = document.querySelector('#emotion-view');
  const content = document.querySelector('#emotion-content');
  content.replaceChildren();
  if (!summary || !summary.enabled) { view.hidden = true; return; }
  if (summary.status === 'failed') {
    const chip = document.createElement('span');
    chip.className = 'emotion-chip error';
    chip.textContent = `感情分析は未完了: ${summary.error || '詳細不明'}`;
    content.append(chip);
  } else {
    const modelNames = {};
    (summary.models || []).forEach(model => { modelNames[model.key] = model.name || model.key; });
    Object.entries(summary.label_counts || {}).forEach(([modelKey, counts]) => {
      const labels = Object.values(counts || {})
        .sort((a, b) => Number(b.count || 0) - Number(a.count || 0))
        .map(item => `${item.label_ja || item.label}: ${item.count}`);
      const chip = document.createElement('span');
      chip.className = 'emotion-chip';
      chip.textContent = `${modelNames[modelKey] || modelKey} / ${labels.join('、') || 'データなし'}`;
      content.append(chip);
    });
  }
  view.hidden = false;
}

function renderMedia(job) {
  mediaPlayerHost.replaceChildren();
  mediaPlayer = null;
  playbackStopAt = null;
  selectedSegmentId = null;
  if (!job.media_url) {
    mediaReview.hidden = true;
    return;
  }
  mediaPlayer = document.createElement(job.media_kind === 'video' ? 'video' : 'audio');
  mediaPlayer.controls = true;
  mediaPlayer.preload = 'metadata';
  mediaPlayer.src = job.media_url;
  mediaPlayer.addEventListener('timeupdate', () => {
    if (playbackStopAt !== null && mediaPlayer.currentTime >= playbackStopAt) {
      mediaPlayer.pause();
      playbackStopAt = null;
    }
  });
  mediaPlayerHost.append(mediaPlayer);
  mediaReview.hidden = false;
}

function renderResult(job) {
  analysisCatalogLoaded = false;
  analysisCatalog = [];
  currentJob = deepCopy(job);
  currentJob.segments = Array.isArray(currentJob.segments) ? currentJob.segments : [];
  currentJob.speaker_names = currentJob.speaker_names || {};
  currentJob.session_profile = currentJob.session_profile || {};
  currentJob.speaker_profiles = currentJob.speaker_profiles || {};
  if (speakerIdentityProvider && aiProvider && ['openai', 'google'].includes(aiProvider.value)) {
    speakerIdentityProvider.value = aiProvider.value;
  }
  if (speakerIdentityStatus) {
    const identifiedCount = Object.values(currentJob.speaker_names).filter(value => String(value || '').trim()).length;
    speakerIdentityStatus.textContent = identifiedCount
      ? `${identifiedCount}名の表示名を反映済みです。既存名は再実行で上書きしません。`
      : '話者名は未反映です。OpenAIまたはGeminiで話者特定だけを実行できます。';
  }
  currentJobId = job.id;
  storeActiveJobId('');
  document.querySelector('#result-title').textContent = job.source_name || '確認・手動編集';
  if (resultContextName) resultContextName.textContent = job.source_name || '選択中のデータ';
  const outputDirectory = document.querySelector('#result-output-dir');
  if (outputDirectory) {
    outputDirectory.textContent = job.output_dir ? `実行フォルダー　${job.output_dir}` : '';
    outputDirectory.hidden = !job.output_dir;
  }
  renderDownloads(job.files);
  renderAiTokenUsage('#result-ai-usage', job.ai_usage);
  renderOutline(job.outline);
  renderEmotionSummary(job.emotion_analysis);
  renderMedia(job);
  renderSessionProfile();
  renderSpeakerEditor();
  updateSegmentFilterOptions();
  renderSegments();
  setAlert(document.querySelector('#save-message'), '');
  if (job.output_warning) {
    setAlert(document.querySelector('#save-message'), job.output_warning, true);
  }
  libraryCard.hidden = true;
  if (processedDataHub) processedDataHub.hidden = true;
  if (speakerRegistryCard) speakerRegistryCard.hidden = true;
  if (analysisCard) analysisCard.hidden = true;
  form.hidden = true;
  progressCard.hidden = true;
  resultCard.hidden = false;
  showLibraryButton.classList.add('active');
  showNewButton.classList.remove('active');
  if (showSpeakersButton) showSpeakersButton.classList.remove('active');
  showLibraryButton.setAttribute('aria-selected', 'true');
  showNewButton.setAttribute('aria-selected', 'false');
  if (showSpeakersButton) showSpeakersButton.setAttribute('aria-selected', 'false');
  setCurrentJobDirty(false);
  resultCard.scrollIntoView({behavior: 'smooth', block: 'start'});
}

function speakerLabels() {
  return [...new Set(currentJob.segments.map(segment => segment.speaker || 'UNKNOWN'))].sort();
}

function renderSessionProfile() {
  if (!currentJob) return;
  const profile = currentJob.session_profile || {};
  const fields = {
    '#session-type': ['session_type', 'focus_group'],
    '#session-date': ['session_date', ''],
    '#session-location': ['location', ''],
    '#session-objective': ['objective', ''],
    '#session-guide': ['moderator_guide', ''],
    '#session-conditions': ['group_conditions', ''],
    '#session-field-notes': ['field_notes', '']
  };
  Object.entries(fields).forEach(([selector, [key, fallback]]) => {
    const element = document.querySelector(selector);
    if (element) element.value = profile[key] || fallback;
  });
  const dateInput = document.querySelector('#session-date');
  const dateNote = document.querySelector('#session-date-note');
  if (dateInput) {
    dateInput.dataset.autoValue = profile.session_date_source === 'media_metadata'
      ? String(profile.session_date || '')
      : '';
  }
  if (dateNote) {
    dateNote.textContent = profile.session_date_source === 'media_metadata'
      ? '動画の撮影日時から自動入力しました。必要に応じて変更できます。'
      : '動画から取得できない場合は、手動で入力・変更できます。';
  }
  const notesDetails = document.querySelector('#session-notes-details');
  const notesSummary = document.querySelector('#session-notes-summary');
  const hasNotes = Boolean(String(profile.field_notes || '').trim());
  if (notesDetails) notesDetails.open = hasNotes;
  if (notesSummary) notesSummary.textContent = hasNotes ? '入力済み' : '未入力';
  const exportLink = document.querySelector('#conversation-speaker-export');
  if (exportLink) {
    exportLink.href = currentJob.speaker_data_url || `/api/library/${currentJobId}/speakers.csv`;
  }
}

function captureSessionProfile() {
  if (!currentJob) return {};
  const read = selector => {
    const element = document.querySelector(selector);
    return element ? element.value.trim() : '';
  };
  const sessionDate = read('#session-date');
  const dateInput = document.querySelector('#session-date');
  const sessionDateSource = sessionDate && dateInput && dateInput.dataset.autoValue === sessionDate
    ? 'media_metadata'
    : sessionDate ? 'manual' : '';
  currentJob.session_profile = {
    session_type: read('#session-type') || 'focus_group',
    session_date: sessionDate,
    session_date_source: sessionDateSource,
    location: read('#session-location'),
    objective: read('#session-objective'),
    moderator_guide: read('#session-guide'),
    group_conditions: read('#session-conditions'),
    field_notes: read('#session-field-notes')
  };
  return currentJob.session_profile;
}

function speakerMetrics() {
  const metrics = {};
  let totalSeconds = 0;
  (currentJob.segments || []).forEach(segment => {
    const label = segment.speaker || 'UNKNOWN';
    const duration = Math.max(0, Number(segment.end || 0) - Number(segment.start || 0));
    const data = metrics[label] || {count: 0, seconds: 0, characters: 0};
    data.count += 1;
    data.seconds += duration;
    data.characters += String(segment.text || '').length;
    metrics[label] = data;
    totalSeconds += duration;
  });
  Object.values(metrics).forEach(data => {
    data.share = totalSeconds > 0 ? data.seconds / totalSeconds : 0;
  });
  return metrics;
}

function ensureConversationSpeakerProfiles() {
  currentJob.speaker_profiles = currentJob.speaker_profiles || {};
  speakerLabels().forEach((label, index) => {
    currentJob.speaker_profiles[label] = {
      speaker_label: label,
      global_speaker_id: '',
      display_name: currentJob.speaker_names[label] || '',
      theme_color: speakerThemeColors[index % speakerThemeColors.length],
      session_role: 'participant',
      organization: '',
      department: '',
      job_title: '',
      attendance_status: 'attended',
      conditions: '',
      notes: '',
      ...(currentJob.speaker_profiles[label] || {})
    };
  });
}

function conversationControl(type, value, options, onChange) {
  const control = document.createElement(type === 'textarea' ? 'textarea' : type === 'select' ? 'select' : 'input');
  if (type === 'select') {
    Object.entries(options || {}).forEach(([optionValue, label]) => control.add(new Option(label, optionValue)));
    control.value = value || Object.keys(options || {})[0];
    control.addEventListener('change', () => {
      onChange(control.value);
      setCurrentJobDirty();
    });
  } else {
    if (type !== 'textarea') control.type = type === 'color' ? 'color' : 'text';
    control.value = value || '';
    control.addEventListener('input', () => {
      onChange(control.value);
      setCurrentJobDirty();
    });
  }
  return control;
}

function renderSpeakerInsights(metrics) {
  const container = document.querySelector('#speaker-insights');
  if (!container) return;
  container.replaceChildren();
  const profiles = Object.values(currentJob.speaker_profiles || {});
  const sessionType = (currentJob.session_profile || {}).session_type
    || (document.querySelector('#session-type') || {}).value
    || 'focus_group';
  const add = (text, level = '') => {
    const chip = document.createElement('span');
    chip.className = `speaker-insight${level ? ` ${level}` : ''}`;
    chip.textContent = text;
    container.append(chip);
  };
  add(`話者 ${profiles.length}人`);
  if (sessionType === 'focus_group') {
    const participants = profiles.filter(profile => profile.session_role === 'participant');
    const moderators = profiles.filter(profile => ['moderator', 'facilitator', 'assistant_moderator'].includes(profile.session_role));
    const observers = profiles.filter(profile => ['observer', 'note_taker'].includes(profile.session_role));
    add(`参加者 ${participants.length}人`, participants.length >= 6 && participants.length <= 8 ? '' : 'warning');
    add(moderatorCountText(moderators.length), moderators.length ? '' : 'error');
    add(`観察・記録 ${observers.length}人`, observers.length ? '' : 'warning');
    const participantSeconds = participants.reduce((sum, profile) => (
      sum + Number((metrics[profile.speaker_label] || {}).seconds || 0)
    ), 0);
    const dominant = participants.find(profile => (
      participantSeconds > 0
      && Number((metrics[profile.speaker_label] || {}).seconds || 0) / participantSeconds >= 0.5
    ));
    if (dominant) add(`${dominant.display_name || dominant.speaker_label} の発言が参加者内50%以上`, 'warning');
  } else if (sessionType === 'meeting') {
    const leaders = profiles.filter(profile => ['chair', 'facilitator', 'moderator'].includes(profile.session_role));
    add(`進行・議長 ${leaders.length}人`, leaders.length ? '' : 'warning');
    const decisionMakers = profiles.filter(profile => profile.session_role === 'decision_maker');
    if (decisionMakers.length) add(`意思決定者 ${decisionMakers.length}人`);
  }
}

function moderatorCountText(count) {
  return `司会・進行 ${count}人`;
}

function renderSpeakerEditor() {
  speakerEditor.replaceChildren();
  if (!currentJob) return;
  captureSessionProfile();
  ensureConversationSpeakerProfiles();
  const labels = speakerLabels();
  const metrics = speakerMetrics();
  renderSpeakerInsights(metrics);
  if (!labels.length) {
    const note = document.createElement('p');
    note.className = 'segment-empty';
    note.textContent = '発話を追加すると、会話別の話者連携を設定できます。';
    speakerEditor.append(note);
    return;
  }
  const table = document.createElement('table');
  table.className = 'conversation-speaker-sheet';
  const head = document.createElement('thead');
  head.innerHTML = '<tr><th>音声話者</th><th>表示名</th><th>テーマカラー</th><th>グローバル話者</th><th>会話役割</th><th>組織</th><th>部署</th><th>役職</th><th>参加状態</th><th>会話固有条件</th><th>メモ</th><th>発言量</th></tr>';
  table.append(head);
  const body = document.createElement('tbody');
  labels.forEach(label => {
    const profile = currentJob.speaker_profiles[label];
    const row = document.createElement('tr');
    const labelCell = document.createElement('td');
    labelCell.className = 'speaker-label-cell';
    labelCell.textContent = label;
    row.append(labelCell);
    const displayName = conversationControl('input', profile.display_name || currentJob.speaker_names[label], null, value => {
      profile.display_name = value.trim();
      currentJob.speaker_names[label] = value.trim();
      updateSpeakerBadges();
    });
    displayName.placeholder = fallbackSpeaker(label);
    appendSheetCell(row, displayName);
    const themeColor = conversationControl('color', profile.theme_color, null, value => {
      profile.theme_color = value.toUpperCase();
      updateSpeakerBadges();
    });
    themeColor.className = 'speaker-theme-color';
    themeColor.setAttribute('aria-label', `${displayName.value || fallbackSpeaker(label)}のテーマカラー`);
    appendSheetCell(row, themeColor);

    const globalSelect = document.createElement('select');
    globalSelect.add(new Option('未連携', ''));
    speakerRegistry.filter(record => record.active !== false).forEach(record => {
      const name = record.pseudonym || record.display_name || record.participant_code;
      const detail = [record.organization, record.job_title].filter(Boolean).join(' / ');
      globalSelect.add(new Option(detail ? `${name} — ${detail}` : name, record.id));
    });
    if (profile.global_speaker_id && !speakerRegistry.some(record => record.id === profile.global_speaker_id)) {
      globalSelect.add(new Option('削除済みの管理対象話者', profile.global_speaker_id));
    }
    globalSelect.value = profile.global_speaker_id || '';
    globalSelect.addEventListener('change', () => {
      profile.global_speaker_id = globalSelect.value;
      const record = speakerRegistry.find(item => item.id === globalSelect.value);
      if (record) {
        profile.display_name = record.pseudonym || record.display_name || record.participant_code;
        profile.session_role = record.default_role || 'participant';
        profile.organization = record.organization || '';
        profile.department = record.department || '';
        profile.job_title = record.job_title || '';
        profile.conditions = attributesToText(record.attributes);
        currentJob.speaker_names[label] = profile.display_name;
      }
      renderSpeakerEditor();
      updateSpeakerBadges();
      setCurrentJobDirty();
    });
    appendSheetCell(row, globalSelect);
    appendSheetCell(row, conversationControl('select', profile.session_role, speakerRoleLabels, value => {
      profile.session_role = value;
      renderSpeakerInsights(metrics);
    }));
    ['organization', 'department', 'job_title'].forEach(key => {
      appendSheetCell(row, conversationControl('input', profile[key], null, value => { profile[key] = value; }));
    });
    appendSheetCell(row, conversationControl('select', profile.attendance_status, attendanceLabels, value => { profile.attendance_status = value; }));
    appendSheetCell(row, conversationControl('textarea', profile.conditions, null, value => { profile.conditions = value; }));
    appendSheetCell(row, conversationControl('textarea', profile.notes, null, value => { profile.notes = value; }));
    const metric = metrics[label] || {count: 0, seconds: 0, share: 0};
    const metricCell = document.createElement('td');
    metricCell.className = 'speaker-metric-cell';
    metricCell.textContent = `${metric.count}回 / ${formatTime(metric.seconds)} / ${(metric.share * 100).toFixed(1)}%`;
    row.append(metricCell);
    body.append(row);
  });
  table.append(body);
  speakerEditor.append(table);
}

[
  '#session-date', '#session-location', '#session-objective', '#session-guide',
  '#session-conditions', '#session-field-notes'
].forEach(selector => {
  listen(document.querySelector(selector), 'input', () => {
    captureSessionProfile();
    const notesSummary = document.querySelector('#session-notes-summary');
    if (selector === '#session-field-notes' && notesSummary) {
      notesSummary.textContent = document.querySelector(selector).value.trim() ? '入力済み' : '未入力';
    }
    setCurrentJobDirty();
  });
});
listen(document.querySelector('#session-type'), 'change', () => {
  captureSessionProfile();
  if (currentJob) renderSpeakerInsights(speakerMetrics());
  setCurrentJobDirty();
});

function updateSegmentFilterOptions() {
  const select = document.querySelector('#segment-speaker-filter');
  const selected = select.value;
  select.replaceChildren(new Option('すべて', ''));
  speakerLabels().forEach(label => select.add(new Option(currentJob.speaker_names[label] || fallbackSpeaker(label), label)));
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

function occurrenceCount(text, keyword) {
  if (!keyword) return 0;
  return String(text || '').toLocaleLowerCase().split(keyword).length - 1;
}

function visibleSegments() {
  const keyword = document.querySelector('#segment-keyword').value.trim().toLocaleLowerCase();
  const speaker = document.querySelector('#segment-speaker-filter').value;
  const emotion = document.querySelector('#segment-emotion-filter').value;
  const sort = document.querySelector('#segment-sort').value;
  const values = currentJob.segments.filter(segment => {
    if (keyword && !String(segment.text || '').toLocaleLowerCase().includes(keyword)) return false;
    if (speaker && (segment.speaker || 'UNKNOWN') !== speaker) return false;
    const label = kushinadaEmotion(segment);
    if (emotion === 'none' && label) return false;
    if (emotion && emotion !== 'none' && label !== emotion) return false;
    return true;
  });
  values.sort((a, b) => {
    if (sort === 'time_desc') return Number(b.start || 0) - Number(a.start || 0);
    if (sort === 'speaker') return String(a.speaker || '').localeCompare(String(b.speaker || ''), 'ja') || Number(a.start || 0) - Number(b.start || 0);
    if (sort === 'emotion') return kushinadaEmotion(a).localeCompare(kushinadaEmotion(b), 'ja') || Number(a.start || 0) - Number(b.start || 0);
    if (sort === 'keyword') return occurrenceCount(b.text, keyword) - occurrenceCount(a.text, keyword) || Number(a.start || 0) - Number(b.start || 0);
    return Number(a.start || 0) - Number(b.start || 0);
  });
  return values;
}

function createField(labelText, control) {
  const label = document.createElement('label');
  label.className = 'field';
  const caption = document.createElement('span');
  caption.textContent = labelText;
  label.append(caption, control);
  return label;
}

function renderSegments() {
  segmentEditor.replaceChildren();
  const values = visibleSegments();
  document.querySelector('#segment-count').textContent = `表示 ${values.length} / 全 ${currentJob.segments.length} 発話`;
  if (!values.length) {
    const empty = document.createElement('div');
    empty.className = 'segment-empty';
    empty.textContent = currentJob.segments.length ? '絞り込み条件に一致する発話はありません。' : '発話はまだありません。「発話を追加」から登録できます。';
    segmentEditor.append(empty);
    return;
  }
  values.forEach(segment => {
    const row = document.createElement('article');
    row.className = `segment${segment.id === selectedSegmentId ? ' selected' : ''}`;
    row.dataset.segmentId = segment.id;
    const meta = document.createElement('div');
    meta.className = 'segment-meta';
    const time = document.createElement('span');
    time.className = 'segment-time';
    time.textContent = `${formatTime(segment.start)}–${formatTime(segment.end)}`;
    const speaker = document.createElement('span');
    speaker.className = 'segment-speaker';
    speaker.dataset.label = segment.speaker || 'UNKNOWN';
    speaker.textContent = currentJob.speaker_names[speaker.dataset.label] || fallbackSpeaker(speaker.dataset.label);
    speaker.style.borderColor = (currentJob.speaker_profiles[speaker.dataset.label] || {}).theme_color || '';
    meta.append(time, speaker);
    const emotionText = segmentEmotionText(segment);
    if (emotionText) {
      const emotion = document.createElement('span');
      emotion.className = 'segment-emotion';
      emotion.textContent = emotionText;
      meta.append(emotion);
    }
    const play = document.createElement('button');
    play.type = 'button';
    play.className = 'segment-play';
    play.textContent = currentJob.media_url ? '▶ 前後を再生' : '元メディアなし';
    play.disabled = !currentJob.media_url;
    play.addEventListener('click', () => playSegment(segment.id));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'segment-delete';
    remove.textContent = '発話を削除';
    remove.addEventListener('click', () => {
      currentJob.segments = currentJob.segments.filter(item => item.id !== segment.id);
      if (selectedSegmentId === segment.id) selectedSegmentId = null;
      setCurrentJobDirty();
      renderSpeakerEditor();
      updateSegmentFilterOptions();
      renderSegments();
    });
    meta.append(play, remove);

    const body = document.createElement('div');
    body.className = 'segment-body';
    const fields = document.createElement('div');
    fields.className = 'segment-fields';
    const start = document.createElement('input');
    start.type = 'number'; start.min = '0'; start.step = '0.01'; start.value = Number(segment.start || 0).toFixed(2);
    start.addEventListener('change', () => {
      segment.start = Math.max(0, Number(start.value) || 0);
      setCurrentJobDirty();
      renderSegments();
    });
    const end = document.createElement('input');
    end.type = 'number'; end.min = '0'; end.step = '0.01'; end.value = Number(segment.end || 0).toFixed(2);
    end.addEventListener('change', () => {
      segment.end = Math.max(0, Number(end.value) || 0);
      setCurrentJobDirty();
      renderSegments();
    });
    const speakerInput = document.createElement('input');
    speakerInput.type = 'text'; speakerInput.maxLength = 80; speakerInput.value = segment.speaker || 'UNKNOWN';
    speakerInput.addEventListener('change', () => {
      segment.speaker = speakerInput.value.trim() || 'UNKNOWN';
      setCurrentJobDirty();
      renderSpeakerEditor();
      updateSegmentFilterOptions();
      renderSegments();
    });
    const emotionSelect = document.createElement('select');
    [['', '未設定'], ['neu', '平常'], ['hap', '喜び'], ['ang', '怒り'], ['sad', '悲しみ']].forEach(([value, label]) => emotionSelect.add(new Option(label, value)));
    emotionSelect.value = kushinadaEmotion(segment);
    emotionSelect.addEventListener('change', () => {
      segment.kushinada_label = emotionSelect.value;
      segment.emotions = segment.emotions || {};
      if (emotionSelect.value) {
        const labels = {neu: '平常', hap: '喜び', ang: '怒り', sad: '悲しみ'};
        segment.emotions.kushinada = {...(segment.emotions.kushinada || {}), label: emotionSelect.value, label_ja: labels[emotionSelect.value], model_name: 'くしなだ'};
      } else {
        delete segment.emotions.kushinada;
      }
      setCurrentJobDirty();
      renderSegments();
    });
    fields.append(createField('開始（秒）', start), createField('終了（秒）', end), createField('話者ラベル', speakerInput), createField('くしなだ感情', emotionSelect));
    const textarea = document.createElement('textarea');
    textarea.value = segment.text || '';
    textarea.setAttribute('aria-label', `${speaker.textContent}の発話`);
    textarea.addEventListener('input', () => {
      segment.text = textarea.value;
      setCurrentJobDirty();
    });
    body.append(fields, textarea);
    row.append(meta, body);
    row.addEventListener('click', event => {
      if (!event.target.closest('input, textarea, select, button') && currentJob.media_url) playSegment(segment.id);
    });
    segmentEditor.append(row);
  });
}

function updateSpeakerBadges() {
  document.querySelectorAll('.segment-speaker').forEach(badge => {
    const label = badge.dataset.label;
    badge.textContent = currentJob.speaker_names[label] || fallbackSpeaker(label);
    badge.style.borderColor = (currentJob.speaker_profiles[label] || {}).theme_color || '';
  });
}

async function rerunSpeakerIdentification() {
  if (!currentJobId || !currentJob || !rerunSpeakerIdentificationButton) return;
  if (currentJobDirty) {
    setAlert(document.querySelector('#save-message'), '編集内容を保存してから話者名を再特定してください。', true);
    return;
  }
  const provider = speakerIdentityProvider ? speakerIdentityProvider.value : 'openai';
  rerunSpeakerIdentificationButton.disabled = true;
  if (speakerIdentityProvider) speakerIdentityProvider.disabled = true;
  if (speakerIdentityStatus) speakerIdentityStatus.textContent = '自己紹介候補の抽出と話者IDの再確認を実行しています…';
  setAlert(document.querySelector('#save-message'), '');
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(currentJobId)}/speaker-identification`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        provider,
        revision_count: Number(currentJob.revision_count || 0)
      })
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '話者名を再特定できませんでした。');
    const summary = data.speaker_identity || {};
    renderResult(data);
    const ambiguousCount = Object.keys(summary.ambiguous_labels || {}).length
      + Object.keys(summary.duplicate_names || {}).length;
    const repairs = summary.repairs || {};
    const repairedSegments = Math.max(0, Number(repairs.aliased_segments) || 0)
      + Math.max(0, Number(repairs.corrected_segments) || 0);
    const hasChanges = Boolean(summary.applied_count || repairedSegments);
    const nameMessage = summary.applied_count
      ? `${summary.applied_count}名を話者IDへ反映しました。`
      : '新たに反映できる話者名はありませんでした。';
    const repairMessage = repairedSegments
      ? ` 話者ラベルの重複・断裂を${repairedSegments}発話修正しました。`
      : '';
    const ambiguityMessage = ambiguousCount
      ? ` 一意に特定できない${ambiguousCount}件は反映していません。`
      : '';
    const message = nameMessage + repairMessage + ambiguityMessage;
    if (speakerIdentityStatus) speakerIdentityStatus.textContent = message;
    setAlert(document.querySelector('#save-message'), message, !hasChanges);
  } catch (error) {
    if (speakerIdentityStatus) speakerIdentityStatus.textContent = error.message;
    setAlert(document.querySelector('#save-message'), error.message, true);
  } finally {
    rerunSpeakerIdentificationButton.disabled = false;
    if (speakerIdentityProvider) speakerIdentityProvider.disabled = false;
  }
}

listen(rerunSpeakerIdentificationButton, 'click', rerunSpeakerIdentification);

['#segment-keyword', '#segment-speaker-filter', '#segment-emotion-filter', '#segment-sort'].forEach(selector => {
  const element = document.querySelector(selector);
  if (!element) return;
  element.addEventListener(element.tagName === 'INPUT' ? 'input' : 'change', renderSegments);
});

listen(document.querySelector('#add-segment-button'), 'click', () => {
  if (!currentJob) return;
  const lastEnd = currentJob.segments.reduce((value, segment) => Math.max(value, Number(segment.end || 0)), 0);
  const id = self.crypto && self.crypto.randomUUID ? self.crypto.randomUUID().replaceAll('-', '') : `new_${Date.now()}`;
  currentJob.segments.push({id, start: lastEnd, end: lastEnd + 1, speaker: speakerLabels()[0] || 'SPEAKER_00', text: '', emotions: {}, kushinada_label: ''});
  setCurrentJobDirty();
  document.querySelector('#segment-keyword').value = '';
  document.querySelector('#segment-speaker-filter').value = '';
  document.querySelector('#segment-emotion-filter').value = '';
  renderSpeakerEditor();
  updateSegmentFilterOptions();
  renderSegments();
  const row = document.querySelector(`[data-segment-id="${id}"] textarea`);
  if (row) { row.focus(); row.scrollIntoView({behavior: 'smooth', block: 'center'}); }
});

function playSegment(segmentId) {
  if (!mediaPlayer || !currentJob) return;
  const segment = currentJob.segments.find(item => item.id === segmentId);
  if (!segment) return;
  selectedSegmentId = segmentId;
  const context = Number(document.querySelector('#play-context').value) || 5;
  const start = Math.max(0, Number(segment.start || 0) - context);
  playbackStopAt = Number(segment.end || segment.start || 0) + context;
  document.querySelector('#media-caption').textContent = `${formatTime(segment.start)}–${formatTime(segment.end)} / ${currentJob.speaker_names[segment.speaker] || fallbackSpeaker(segment.speaker)}（前後 ${context} 秒）`;
  mediaPlayer.currentTime = start;
  const promise = mediaPlayer.play();
  if (promise) promise.catch(() => {});
  document.querySelectorAll('.segment').forEach(row => row.classList.toggle('selected', row.dataset.segmentId === segmentId));
  mediaReview.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

function adjacentSegment(direction) {
  if (!currentJob || !currentJob.segments.length) return;
  const ordered = [...currentJob.segments].sort((a, b) => Number(a.start || 0) - Number(b.start || 0));
  let index = ordered.findIndex(segment => segment.id === selectedSegmentId);
  if (index < 0) index = direction > 0 ? -1 : ordered.length;
  index = Math.max(0, Math.min(ordered.length - 1, index + direction));
  playSegment(ordered[index].id);
}

listen(document.querySelector('#previous-segment-button'), 'click', () => adjacentSegment(-1));
listen(document.querySelector('#next-segment-button'), 'click', () => adjacentSegment(1));
listen(document.querySelector('#replay-segment-button'), 'click', () => {
  const first = currentJob && [...currentJob.segments].sort((a, b) => Number(a.start || 0) - Number(b.start || 0))[0];
  if (selectedSegmentId) playSegment(selectedSegmentId);
  else if (first) playSegment(first.id);
});

listen(saveButton, 'click', async () => {
  if (!currentJobId || !currentJob) return;
  const message = document.querySelector('#save-message');
  setAlert(message, '');
  saveButton.disabled = true;
  const payloadSegments = currentJob.segments.map(segment => ({
    ...segment,
    kushinada_label: segment.kushinada_label !== undefined ? segment.kushinada_label : kushinadaEmotion(segment)
  }));
  captureSessionProfile();
  ensureConversationSpeakerProfiles();
  const savedItemId = currentJobId;
  const saveGeneration = currentJobMutationGeneration;
  try {
    const response = await apiFetch(`/api/library/${savedItemId}`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        revision_count: Number(currentJob.revision_count || 0),
        source_name: currentJob.source_name,
        speaker_names: currentJob.speaker_names,
        segments: payloadSegments,
        session_profile: currentJob.session_profile,
        speaker_profiles: currentJob.speaker_profiles
      })
    });
    const data = await readJsonResponse(response);
    if (!response.ok) {
      const fallback = response.status === 409
        ? '別の画面または処理でデータが更新されています。未保存内容を控えてから再読み込みしてください。'
        : '保存できませんでした。';
      const revisionDetail = response.status === 409 && Number.isFinite(Number(data.current_revision))
        ? `（現在のリビジョン: ${Number(data.current_revision)}）`
        : '';
      throw new Error(`${data.error || fallback}${revisionDetail}`);
    }
    const hasLaterChanges = currentJobId === savedItemId
      && currentJobMutationGeneration !== saveGeneration;
    if (currentJobId === savedItemId && !hasLaterChanges) {
      renderResult(data);
    } else if (currentJobId === savedItemId && currentJob) {
      currentJob.revision_count = Number(data.revision_count || currentJob.revision_count || 0);
      currentJob.files = Array.isArray(data.files) ? data.files : currentJob.files;
      renderDownloads(currentJob.files);
      setCurrentJobDirty(true, false);
    }
    const learning = data.learning_events
      ? `修正差分 ${data.learning_events} 件を、くしなだ学習用データへ追加しました。`
      : '新しい修正差分はありませんでした。';
    const warning = [data.output_warning, data.learning_warning].filter(Boolean).join(' ');
    const laterChangeNotice = hasLaterChanges
      ? ' 保存開始後の追加変更が残っています。内容を確認して、もう一度保存してください。'
      : '';
    setAlert(document.querySelector('#save-message'), `編集内容と出力ファイルを保存しました。${learning}${warning}${laterChangeNotice}`, Boolean(warning || hasLaterChanges));
    loadTrainingStatus();
  } catch (error) {
    setCurrentJobDirty(true, false);
    setAlert(message, error.message, true);
  } finally {
    saveButton.disabled = false;
  }
});

listen(deleteRecordButton, 'click', () => {
  if (currentJobId && currentJob) deleteLibraryItem(currentJobId, currentJob.source_name);
});

resultContextButtons.forEach(button => {
  listen(button, 'click', () => openResultDestination(button.dataset.resultDestination));
});
listen(resultAnalysisButton, 'click', () => openAnalysisForItem(currentJobId));
listen(newButton, 'click', () => showView('library'));

function analysisElement(tagName, className = '', textValue = '') {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (textValue !== undefined && textValue !== null && textValue !== '') {
    element.textContent = String(textValue);
  }
  return element;
}

function safeAnalysisColor(value, fallback = '#1C6B50') {
  const color = String(value || '').toUpperCase();
  return /^#[0-9A-F]{6}$/.test(color) ? color : fallback;
}

function boundedAnalysisPercent(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.min(100, Math.max(0, number)) : 0;
}

function analysisNumberText(value, digits = 1, suffix = '') {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(digits)}${suffix}` : '—';
}

function analysisExportLink(label, dataset, className = 'analysis-export-link') {
  const exports = analysisState.data && analysisState.data.exports;
  const href = exports && exports[dataset];
  if (!href || !String(href).startsWith('/api/')) return null;
  const link = analysisElement('a', className, label);
  link.href = href;
  link.download = '';
  link.setAttribute('aria-label', `${label}をダウンロード`);
  return link;
}

function analysisExportDirectory(title, classification, datasets) {
  const section = analysisCardPanel(title, classification, '', true);
  const links = analysisElement('div', 'analysis-export-directory');
  datasets.forEach(([dataset, label]) => {
    const link = analysisExportLink(label, dataset, 'analysis-data-export');
    if (link) links.append(link);
  });
  if (links.childNodes.length) section.body.append(links);
  else section.body.append(analysisElement('p', 'analysis-no-data', '出力できる集計データがありません。'));
  return section.panel;
}

function setAnalysisDirty(dirty, trackMutation = true) {
  analysisState.dirty = Boolean(dirty);
  if (analysisState.dirty && trackMutation) analysisMutationGeneration += 1;
  document.querySelectorAll('[data-analysis-save]').forEach(button => {
    button.disabled = !analysisState.dirty || analysisSaveInProgress;
    button.textContent = analysisSaveInProgress
      ? '保存中…'
      : analysisState.dirty ? '設定とコードを保存' : '保存済み';
  });
  document.querySelectorAll('[data-analysis-save-state]').forEach(element => {
    element.textContent = analysisState.dirty ? '未保存の変更があります' : '分析設定は保存済みです';
    element.classList.toggle('unsaved', analysisState.dirty);
  });
  const sideStatus = document.querySelector('#analysis-desktop-side-status');
  if (sideStatus) {
    sideStatus.classList.toggle('unsaved', analysisState.dirty);
    sideStatus.textContent = analysisState.dirty
      ? '設定・コードに未保存の変更があります'
      : analysisState.data ? '保存済みデータから集計中' : '';
  }
}

function setAnalysisLoading(loading) {
  const loadingView = document.querySelector('#analysis-loading');
  const shell = document.querySelector('#analysis-shell');
  const empty = document.querySelector('#analysis-empty');
  if (loadingView) loadingView.hidden = !loading;
  if (shell) shell.hidden = loading || !analysisState.data;
  if (empty) empty.hidden = loading || Boolean(analysisState.data);
  if (analysisItemSelect) analysisItemSelect.disabled = loading;
}

function updateAnalysisTarget() {
  const selected = analysisCatalog.find(item => item.id === analysisState.itemId);
  const name = document.querySelector('#analysis-target-name');
  const meta = document.querySelector('#analysis-target-meta');
  if (name) name.textContent = selected ? selected.source_name : '未選択';
  if (meta) {
    meta.textContent = selected
      ? `発話 ${selected.segment_count || 0}件 / ${formatTime(selected.duration || 0)} / 更新 ${formatDate(selected.updated_at)}`
      : '処理済みデータを選択してください';
  }
  const exportLink = document.querySelector('#analysis-json-export');
  const jsonHref = analysisState.data && analysisState.data.exports && analysisState.data.exports.json;
  if (exportLink) {
    exportLink.hidden = !jsonHref;
    if (jsonHref && String(jsonHref).startsWith('/api/')) exportLink.href = jsonHref;
  }
  const xlsxLink = document.querySelector('#analysis-xlsx-export');
  const xlsxHref = analysisState.data && analysisState.data.exports && analysisState.data.exports.xlsx;
  if (xlsxLink) {
    xlsxLink.hidden = !xlsxHref;
    if (xlsxHref && String(xlsxHref).startsWith('/api/')) xlsxLink.href = xlsxHref;
  }
}

async function loadAnalysisCatalog(force = false) {
  if (analysisCatalogLoaded && !force) {
    if (analysisState.itemId && !analysisState.data) loadAnalysisItem(analysisState.itemId);
    return;
  }
  setAlert(document.querySelector('#analysis-message'), '');
  if (analysisItemSelect) {
    analysisItemSelect.disabled = true;
    analysisItemSelect.replaceChildren(new Option('処理済みデータを読み込んでいます…', ''));
  }
  try {
    const response = await apiFetch('/api/library?sort=updated_desc', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '分析対象を取得できませんでした。');
    analysisCatalog = Array.isArray(data.items) ? data.items : [];
    analysisCatalogLoaded = true;
    if (analysisItemSelect) {
      analysisItemSelect.replaceChildren();
      if (!analysisCatalog.length) {
        analysisItemSelect.add(new Option('分析できる処理済みデータがありません', ''));
      } else {
        analysisCatalog.forEach(item => {
          const label = `${item.source_name}（発話 ${item.segment_count || 0}件）`;
          analysisItemSelect.add(new Option(label, item.id));
        });
      }
    }
    const currentExists = analysisCatalog.some(item => item.id === analysisState.itemId);
    const resultExists = analysisCatalog.some(item => item.id === currentJobId);
    const nextId = currentExists
      ? analysisState.itemId
      : resultExists ? currentJobId : (analysisCatalog[0] || {}).id || '';
    if (analysisItemSelect) analysisItemSelect.value = nextId;
    if (nextId) await loadAnalysisItem(nextId, {discardDirty: force});
    else {
      analysisState.itemId = '';
      analysisState.data = null;
      updateAnalysisTarget();
      setAnalysisLoading(false);
    }
  } catch (error) {
    setAlert(document.querySelector('#analysis-message'), error.message, true);
    analysisState.data = null;
    setAnalysisLoading(false);
  } finally {
    if (analysisItemSelect) analysisItemSelect.disabled = false;
  }
}

async function loadAnalysisItem(itemId, {discardDirty = false} = {}) {
  const nextId = String(itemId || '');
  if (!nextId) return;
  if (!discardDirty && analysisState.dirty && nextId !== analysisState.itemId) {
    const leave = window.confirm('分析設定または手動コードに未保存の変更があります。破棄して別のデータを開きますか？');
    if (!leave) {
      if (analysisItemSelect) analysisItemSelect.value = analysisState.itemId;
      return;
    }
  }
  if (analysisRequestController) analysisRequestController.abort();
  analysisRequestController = new AbortController();
  const requestId = ++analysisRequestSequence;
  analysisState.itemId = nextId;
  analysisState.data = null;
  if (analysisItemSelect) analysisItemSelect.value = nextId;
  updateAnalysisTarget();
  setAnalysisLoading(true);
  setAlert(document.querySelector('#analysis-message'), '');
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(nextId)}/analysis`, {
      cache: 'no-store', signal: analysisRequestController.signal
    });
    const payload = await readJsonResponse(response);
    if (requestId !== analysisRequestSequence) return;
    if (!response.ok) throw new Error(payload.error || '分析データを取得できませんでした。');
    const data = payload.analysis && typeof payload.analysis === 'object' ? payload.analysis : payload;
    analysisState.data = data;
    analysisState.config = deepCopy(data.config || {});
    analysisState.annotations = deepCopy(data.annotations || {});
    analysisState.segmentQuery = '';
    analysisState.annotatedOnly = false;
    analysisState.speakerAttributeFilter = '';
    analysisState.selectedSpeaker = '';
    setAnalysisDirty(false);
    renderAnalysisWorkspace();
  } catch (error) {
    if (error.name === 'AbortError') return;
    if (requestId !== analysisRequestSequence) return;
    analysisState.data = null;
    setAlert(document.querySelector('#analysis-message'), error.message, true);
  } finally {
    if (requestId === analysisRequestSequence) setAnalysisLoading(false);
  }
}

function setAnalysisMode(mode) {
  analysisState.mode = mode === 'manual' ? 'manual' : 'automatic';
  renderAnalysisWorkspace();
}

function renderAnalysisWorkspace() {
  if (!analysisState.data) return;
  document.querySelectorAll('[data-analysis-mode]').forEach(button => {
    const active = button.dataset.analysisMode === analysisState.mode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  updateAnalysisTarget();
  if (analysisDesktopContent) {
    analysisDesktopContent.replaceChildren();
    analysisDesktopContent.append(
      analysisState.mode === 'manual'
        ? renderManualAnalysis(false)
        : renderAutomaticAnalysis(false)
    );
  }
  if (analysisMobileContent) {
    analysisMobileContent.replaceChildren();
    analysisMobileContent.append(
      analysisState.mode === 'manual'
        ? renderManualAnalysis(true)
        : renderAutomaticAnalysis(true)
    );
  }
  const shell = document.querySelector('#analysis-shell');
  const empty = document.querySelector('#analysis-empty');
  if (shell) shell.hidden = false;
  if (empty) empty.hidden = true;
  setAnalysisDirty(analysisState.dirty, false);
  scheduleAnalysisNavigationSync();
  if (!analysisInitialSectionApplied && requestedAnalysisSection) {
    analysisInitialSectionApplied = true;
    requestAnimationFrame(() => {
      const content = window.matchMedia('(max-width: 959px)').matches
        ? analysisMobileContent : analysisDesktopContent;
      const target = content && content.querySelector(`[data-analysis-anchor="${requestedAnalysisSection}"]`);
      const jump = content && content.querySelector(`[data-analysis-jump="${requestedAnalysisSection}"]`);
      if (jump) {
        content.querySelectorAll('[data-analysis-jump]').forEach(button => button.classList.toggle('active', button === jump));
      }
      if (target) target.scrollIntoView({block: 'start'});
    });
  }
}

function analysisCardPanel(titleText, classification, exportDataset = '', wide = false) {
  const panel = analysisElement('section', `analysis-panel${wide ? ' wide' : ''}`);
  const heading = analysisElement('header', 'analysis-panel-heading');
  const titleGroup = analysisElement('div');
  const badgeLabels = {automatic: '自動集計', configured: '要設定', manual: '要確認・解釈'};
  titleGroup.append(
    analysisElement('span', `analysis-kind ${classification}`, badgeLabels[classification] || classification),
    analysisElement('h3', '', titleText)
  );
  heading.append(titleGroup);
  if (exportDataset) {
    const link = analysisExportLink('CSV', exportDataset);
    if (link) heading.append(link);
  }
  const body = analysisElement('div', 'analysis-panel-body');
  panel.append(heading, body);
  return {panel, body};
}

function appendAnalysisMetric(container, label, value, note = '') {
  const card = analysisElement('div', 'analysis-overview-metric');
  card.append(analysisElement('span', '', label), analysisElement('strong', '', value));
  if (note) card.append(analysisElement('small', '', note));
  container.append(card);
}

function appendAnalysisBar(container, label, value, detail = '', color = '#1C6B50') {
  const row = analysisElement('div', 'analysis-bar-row');
  const heading = analysisElement('div', 'analysis-bar-heading');
  heading.append(analysisElement('strong', '', label), analysisElement('span', '', detail));
  const track = analysisElement('div', 'analysis-bar-track');
  const fill = analysisElement('i');
  const percent = boundedAnalysisPercent(value);
  fill.style.width = `${percent}%`;
  fill.style.backgroundColor = safeAnalysisColor(color);
  track.setAttribute('role', 'img');
  track.setAttribute('aria-label', `${label} ${percent.toFixed(1)}%`);
  track.append(fill);
  row.append(heading, track);
  container.append(row);
}

function analysisSvgElement(tagName, attributes = {}, textValue = '') {
  const element = document.createElementNS('http://www.w3.org/2000/svg', tagName);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  if (textValue !== '') element.textContent = String(textValue);
  return element;
}

function buildAnalysisLineSvg(series, bins) {
  const svg = analysisSvgElement('svg', {
    class: 'analysis-timeline-chart', viewBox: '0 0 760 300', role: 'img', tabindex: '0'
  });
  svg.append(
    analysisSvgElement('title', {}, '時間帯別の発話量の折れ線グラフ'),
    analysisSvgElement('desc', {}, '横軸が会話の時刻、縦軸が各時間帯に含まれる発話秒数です。点にカーソルを合わせると値を確認できます。')
  );
  const plot = {x: 58, y: 18, width: 674, height: 224};
  const allValues = series.flatMap(item => item.values).map(value => Math.max(0, Number(value) || 0));
  const maximum = Math.max(1, ...allValues);
  [0, .25, .5, .75, 1].forEach(ratio => {
    const y = plot.y + plot.height * (1 - ratio);
    svg.append(
      analysisSvgElement('line', {
        x1: plot.x, x2: plot.x + plot.width, y1: y, y2: y, class: 'analysis-chart-grid'
      }),
      analysisSvgElement('text', {
        x: plot.x - 10, y: y + 4, 'text-anchor': 'end', class: 'analysis-chart-axis-label'
      }, (maximum * ratio).toFixed(maximum < 10 ? 1 : 0))
    );
  });
  const count = Math.max(1, bins.length);
  series.forEach(item => {
    const points = item.values.map((rawValue, index) => {
      const value = Math.max(0, Number(rawValue) || 0);
      const x = plot.x + plot.width * (count === 1 ? .5 : index / (count - 1));
      const y = plot.y + plot.height * (1 - value / maximum);
      return {x, y, value, index};
    });
    const path = analysisSvgElement('path', {
      d: points.map((point, index) => `${index ? 'L' : 'M'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' '),
      class: 'analysis-line-series', stroke: safeAnalysisColor(item.color),
      'vector-effect': 'non-scaling-stroke'
    });
    svg.append(path);
    points.forEach(point => {
      const circle = analysisSvgElement('circle', {
        cx: point.x, cy: point.y, r: bins.length > 45 ? 2.3 : 4,
        class: 'analysis-line-point', fill: safeAnalysisColor(item.color)
      });
      const bin = bins[point.index] || {};
      circle.append(analysisSvgElement('title', {}, `${item.label} / ${formatTime(bin.start || 0)}–${formatTime(bin.end || 0)} / ${point.value.toFixed(1)}秒`));
      svg.append(circle);
    });
  });
  const labelIndexes = [...new Set([0, Math.floor((count - 1) / 2), count - 1])];
  labelIndexes.forEach(index => {
    const bin = bins[index] || {};
    const x = plot.x + plot.width * (count === 1 ? .5 : index / (count - 1));
    const anchor = index === 0 ? 'start' : index === count - 1 ? 'end' : 'middle';
    svg.append(analysisSvgElement('text', {
      x, y: 275, 'text-anchor': anchor, class: 'analysis-chart-axis-label'
    }, formatTime(bin.start || 0)));
  });
  svg.append(analysisSvgElement('text', {
    x: 17, y: 135, transform: 'rotate(-90 17 135)', 'text-anchor': 'middle', class: 'analysis-chart-axis-title'
  }, '発話秒数'));
  return svg;
}

function buildAnalysisTimelineChart(rawBins, speakerMetrics = []) {
  const bins = Array.isArray(rawBins) ? rawBins : [];
  const module = analysisElement('div', 'analysis-chart-module');
  const toolbar = analysisElement('div', 'analysis-chart-toolbar');
  const explanation = analysisElement('div', 'analysis-chart-explanation');
  explanation.append(
    analysisElement('strong', '', '会話中の発話量を追う'),
    analysisElement('span', '', '表示を切り替えて、全体の山と話者ごとの参加タイミングを比較できます。')
  );
  const switcher = analysisElement('div', 'analysis-chart-switch');
  switcher.setAttribute('role', 'group');
  switcher.setAttribute('aria-label', '時間推移グラフの表示');
  const totalButton = analysisElement('button', 'active', '全体');
  const speakerButton = analysisElement('button', '', '話者別');
  [totalButton, speakerButton].forEach(button => button.type = 'button');
  switcher.append(totalButton, speakerButton);
  toolbar.append(explanation, switcher);
  const stage = analysisElement('div', 'analysis-chart-stage');
  const legend = analysisElement('div', 'analysis-chart-legend');
  const note = analysisElement('p', 'analysis-chart-note');
  module.append(toolbar, stage, legend, note);

  const palette = ['#1C6B50', '#2F80ED', '#E87941', '#9B51E0', '#6C8B3C', '#C34F72'];
  const metricMap = new Map((Array.isArray(speakerMetrics) ? speakerMetrics : []).map(item => [String(item.speaker), item]));
  const speakerTotals = new Map();
  bins.forEach(bin => (Array.isArray(bin.speakers) ? bin.speakers : []).forEach(item => {
    const id = String(item.speaker || item.speaker_name || 'UNKNOWN');
    speakerTotals.set(id, (speakerTotals.get(id) || 0) + Math.max(0, Number(item.seconds) || 0));
  }));
  const visibleSpeakers = [...speakerTotals.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);

  function render(mode) {
    const speakerMode = mode === 'speakers';
    totalButton.classList.toggle('active', !speakerMode);
    speakerButton.classList.toggle('active', speakerMode);
    totalButton.setAttribute('aria-pressed', String(!speakerMode));
    speakerButton.setAttribute('aria-pressed', String(speakerMode));
    const series = speakerMode
      ? visibleSpeakers.map(([speaker], index) => {
          const metric = metricMap.get(speaker) || {};
          return {
            id: speaker,
            label: metric.speaker_name || (bins.flatMap(bin => bin.speakers || []).find(item => String(item.speaker) === speaker) || {}).speaker_name || speaker,
            color: safeAnalysisColor(metric.color, palette[index % palette.length]),
            values: bins.map(bin => Number(((bin.speakers || []).find(item => String(item.speaker) === speaker) || {}).seconds) || 0)
          };
        })
      : [{
          id: 'total', label: '全体', color: '#1C6B50',
          values: bins.map(item => Number(item.speaking_seconds) || 0)
        }];
    stage.replaceChildren(buildAnalysisLineSvg(series, bins));
    legend.replaceChildren();
    series.forEach(item => {
      const entry = analysisElement('span');
      const marker = analysisElement('i');
      marker.style.backgroundColor = safeAnalysisColor(item.color);
      entry.append(marker, document.createTextNode(item.label));
      legend.append(entry);
    });
    note.textContent = speakerMode
      ? `発話時間が多い上位${visibleSpeakers.length}話者を表示しています。折れ線の高さは各時間帯の秒数で、累積値ではありません。`
      : '時間帯ごとの総発話秒数です。重なり発話がある場合、時間帯の長さを超えることがあります。';
  }
  totalButton.addEventListener('click', () => render('total'));
  speakerButton.addEventListener('click', () => render('speakers'));
  render('total');
  return module;
}

function analysisPValueText(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  if (number < .001) return 'p < .001';
  return `p = ${number.toFixed(3)}`;
}

function buildAnalysisCooccurrenceChart(rawEdges) {
  const namespace = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(namespace, 'svg');
  svg.classList.add('analysis-cooccurrence-chart');
  svg.setAttribute('viewBox', '0 0 720 430');
  svg.setAttribute('role', 'img');
  const title = document.createElementNS(namespace, 'title');
  title.textContent = '発話単位の語の共起ネットワーク';
  const description = document.createElementNS(namespace, 'desc');
  description.textContent = '同じ発話に現れた内容語をJaccard係数の強さで結んだ探索用ネットワークです。';
  svg.append(title, description);
  const edges = (Array.isArray(rawEdges) ? rawEdges : []).slice(0, 35);
  const weights = new Map();
  edges.forEach(edge => {
    weights.set(edge.term_a, (weights.get(edge.term_a) || 0) + (Number(edge.jaccard) || 0));
    weights.set(edge.term_b, (weights.get(edge.term_b) || 0) + (Number(edge.jaccard) || 0));
  });
  const nodes = [...weights.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 18)
    .map(([term, weight], index, values) => {
      const angle = -Math.PI / 2 + 2 * Math.PI * index / Math.max(1, values.length);
      const ring = 145 + 28 * (index % 2);
      return {
        term, weight,
        x: 360 + Math.cos(angle) * ring,
        y: 215 + Math.sin(angle) * ring
      };
    });
  const nodeMap = new Map(nodes.map(node => [node.term, node]));
  const visibleEdges = edges.filter(edge => nodeMap.has(edge.term_a) && nodeMap.has(edge.term_b));
  const maxJaccard = Math.max(.001, ...visibleEdges.map(edge => Number(edge.jaccard) || 0));
  visibleEdges.forEach(edge => {
    const source = nodeMap.get(edge.term_a);
    const target = nodeMap.get(edge.term_b);
    const line = document.createElementNS(namespace, 'line');
    line.setAttribute('x1', String(source.x));
    line.setAttribute('y1', String(source.y));
    line.setAttribute('x2', String(target.x));
    line.setAttribute('y2', String(target.y));
    line.setAttribute('class', 'analysis-network-edge');
    line.setAttribute('stroke-width', String(1 + 7 * (Number(edge.jaccard) || 0) / maxJaccard));
    const tooltip = document.createElementNS(namespace, 'title');
    tooltip.textContent = `${edge.term_a} × ${edge.term_b}: 共起 ${edge.cooccurrence_count}発話 / Jaccard ${Number(edge.jaccard || 0).toFixed(3)}`;
    line.append(tooltip);
    svg.append(line);
  });
  const maxWeight = Math.max(.001, ...nodes.map(node => node.weight));
  nodes.forEach(node => {
    const group = document.createElementNS(namespace, 'g');
    group.setAttribute('class', 'analysis-network-node');
    const radius = 12 + 13 * node.weight / maxWeight;
    const circle = document.createElementNS(namespace, 'circle');
    circle.setAttribute('cx', String(node.x));
    circle.setAttribute('cy', String(node.y));
    circle.setAttribute('r', String(radius));
    const label = document.createElementNS(namespace, 'text');
    label.setAttribute('x', String(node.x));
    label.setAttribute('y', String(node.y + radius + 15));
    label.setAttribute('text-anchor', 'middle');
    label.textContent = node.term;
    group.append(circle, label);
    svg.append(group);
  });
  return svg;
}

function buildAnalysisTermTreeChart(rawEdges) {
  const edges = (Array.isArray(rawEdges) ? rawEdges : []).slice(0, 60);
  const weights = new Map();
  edges.forEach(edge => {
    const weight = Math.max(0, Number(edge.jaccard) || 0);
    weights.set(String(edge.term_a), (weights.get(String(edge.term_a)) || 0) + weight);
    weights.set(String(edge.term_b), (weights.get(String(edge.term_b)) || 0) + weight);
  });
  const nodeIds = [...weights.entries()].sort((a, b) => b[1] - a[1]).slice(0, 16).map(item => item[0]);
  const nodeSet = new Set(nodeIds);
  const candidates = edges
    .filter(edge => nodeSet.has(String(edge.term_a)) && nodeSet.has(String(edge.term_b)))
    .sort((a, b) => Number(b.jaccard || 0) - Number(a.jaccard || 0));
  const parent = new Map(nodeIds.map(id => [id, id]));
  const find = id => {
    let value = id;
    while (parent.get(value) !== value) value = parent.get(value);
    let cursor = id;
    while (parent.get(cursor) !== cursor) {
      const next = parent.get(cursor);
      parent.set(cursor, value);
      cursor = next;
    }
    return value;
  };
  const treeEdges = [];
  candidates.forEach(edge => {
    const source = String(edge.term_a);
    const target = String(edge.term_b);
    const sourceRoot = find(source);
    const targetRoot = find(target);
    if (sourceRoot === targetRoot) return;
    parent.set(targetRoot, sourceRoot);
    treeEdges.push({...edge, source, target});
  });
  const adjacency = new Map(nodeIds.map(id => [id, []]));
  treeEdges.forEach(edge => {
    adjacency.get(edge.source).push({id: edge.target, edge});
    adjacency.get(edge.target).push({id: edge.source, edge});
  });
  const components = [];
  const componentSeen = new Set();
  nodeIds.forEach(id => {
    if (componentSeen.has(id)) return;
    const values = [];
    const queue = [id];
    componentSeen.add(id);
    while (queue.length) {
      const current = queue.shift();
      values.push(current);
      (adjacency.get(current) || []).forEach(item => {
        if (!componentSeen.has(item.id)) {
          componentSeen.add(item.id);
          queue.push(item.id);
        }
      });
    }
    components.push(values);
  });
  const positions = new Map();
  const directedEdges = [];
  let leafCursor = 0;
  let maxDepth = 0;
  const place = (id, from, depth) => {
    maxDepth = Math.max(maxDepth, depth);
    const children = (adjacency.get(id) || []).filter(item => item.id !== from);
    const childPositions = children.map(item => {
      directedEdges.push({source: id, target: item.id, edge: item.edge});
      return place(item.id, id, depth + 1);
    });
    const y = childPositions.length
      ? childPositions.reduce((sum, value) => sum + value, 0) / childPositions.length
      : 54 + leafCursor++ * 66;
    positions.set(id, {x: 80 + depth * 178, y, depth});
    return y;
  };
  components
    .sort((a, b) => b.length - a.length)
    .forEach(component => {
      const root = [...component].sort((a, b) => (weights.get(b) || 0) - (weights.get(a) || 0))[0];
      place(root, '', 0);
      leafCursor += .55;
    });
  const width = Math.max(760, 185 + maxDepth * 178);
  const height = Math.max(310, 95 + leafCursor * 66);
  const svg = analysisSvgElement('svg', {
    class: 'analysis-term-tree', viewBox: `0 0 ${width} ${height}`, role: 'img', tabindex: '0'
  });
  svg.append(
    analysisSvgElement('title', {}, '共起語の関連ツリー'),
    analysisSvgElement('desc', {}, 'Jaccard係数が強い辺を優先して循環を除いた最大重み全域木です。語の因果関係や階層を示すものではありません。')
  );
  directedEdges.forEach(item => {
    const source = positions.get(item.source);
    const target = positions.get(item.target);
    const middle = (source.x + target.x) / 2;
    const path = analysisSvgElement('path', {
      d: `M ${source.x + 62} ${source.y} C ${middle} ${source.y}, ${middle} ${target.y}, ${target.x - 62} ${target.y}`,
      class: 'analysis-tree-edge', 'vector-effect': 'non-scaling-stroke'
    });
    path.append(analysisSvgElement('title', {}, `${item.source} × ${item.target} / Jaccard ${Number(item.edge.jaccard || 0).toFixed(3)}`));
    svg.append(path);
  });
  positions.forEach((position, id) => {
    const group = analysisSvgElement('g', {class: `analysis-tree-node${position.depth === 0 ? ' root' : ''}`});
    const label = id.length > 11 ? `${id.slice(0, 10)}…` : id;
    group.append(
      analysisSvgElement('rect', {x: position.x - 62, y: position.y - 22, width: 124, height: 44, rx: 11}),
      analysisSvgElement('text', {x: position.x, y: position.y + 4, 'text-anchor': 'middle'}, label),
      analysisSvgElement('title', {}, `${id} / 接続強度合計 ${(weights.get(id) || 0).toFixed(3)}`)
    );
    svg.append(group);
  });
  return svg;
}

function buildAnalysisCooccurrenceExplorer(edges) {
  const module = analysisElement('div', 'analysis-chart-module');
  const toolbar = analysisElement('div', 'analysis-chart-toolbar');
  const explanation = analysisElement('div', 'analysis-chart-explanation');
  explanation.append(
    analysisElement('strong', '', '語の結びつきを探索する'),
    analysisElement('span', '', '全体像はネットワーク、経路を追うときは関連ツリーが見やすくなります。')
  );
  const switcher = analysisElement('div', 'analysis-chart-switch');
  switcher.setAttribute('role', 'group');
  switcher.setAttribute('aria-label', '共起グラフの表示');
  const networkButton = analysisElement('button', 'active', 'ネットワーク');
  const treeButton = analysisElement('button', '', '関連ツリー');
  [networkButton, treeButton].forEach(button => button.type = 'button');
  switcher.append(networkButton, treeButton);
  toolbar.append(explanation, switcher);
  const stage = analysisElement('div', 'analysis-chart-stage analysis-network-stage');
  const note = analysisElement('p', 'analysis-chart-note');
  module.append(toolbar, stage, note);
  const render = mode => {
    const treeMode = mode === 'tree';
    networkButton.classList.toggle('active', !treeMode);
    treeButton.classList.toggle('active', treeMode);
    networkButton.setAttribute('aria-pressed', String(!treeMode));
    treeButton.setAttribute('aria-pressed', String(treeMode));
    stage.replaceChildren(treeMode ? buildAnalysisTermTreeChart(edges) : buildAnalysisCooccurrenceChart(edges));
    note.textContent = treeMode
      ? 'Jaccard係数が強い結びつきを優先し、循環を除いて表示しています。左右の位置は概念上の上下関係を意味しません。'
      : '円が大きい語ほど、表示中の他の語とのJaccard係数合計が大きいことを示します。';
  };
  networkButton.addEventListener('click', () => render('network'));
  treeButton.addEventListener('click', () => render('tree'));
  render('network');
  return module;
}

function groupAnalysisDependencies(dependencies) {
  const groups = new Map();
  (Array.isArray(dependencies) ? dependencies : []).forEach(item => {
    const key = `${item.segment_id || '—'}::${item.sentence_id || 1}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  });
  return [...groups.entries()].map(([key, rows]) => {
    rows.sort((a, b) => Number(a.token_id || 0) - Number(b.token_id || 0));
    return {key, rows, label: `発話 ${rows[0].segment_id || '—'}・文 ${rows[0].sentence_id || 1}: ${rows.map(item => item.surface || '').join('').slice(0, 42)}`};
  });
}

function buildAnalysisDependencyTree(rows) {
  const visibleRows = (Array.isArray(rows) ? rows : []).slice(0, 28);
  const nodes = new Map(visibleRows.map(item => [Number(item.token_id), {...item}]));
  const children = new Map([...nodes.keys()].map(id => [id, []]));
  const roots = [];
  nodes.forEach((item, id) => {
    const head = Number(item.head_token_id || 0);
    if (!head || head === id || !nodes.has(head)) roots.push(id);
    else children.get(head).push(id);
  });
  children.forEach(values => values.sort((a, b) => a - b));
  const positions = new Map();
  const renderedEdges = [];
  const visited = new Set();
  let leafCursor = 0;
  let maxDepth = 0;
  const place = (id, depth, trail = new Set()) => {
    if (trail.has(id)) return 54 + leafCursor++ * 112;
    if (visited.has(id)) return (positions.get(id) || {}).x || 54 + leafCursor++ * 112;
    visited.add(id);
    maxDepth = Math.max(maxDepth, depth);
    const nextTrail = new Set(trail).add(id);
    const childIds = (children.get(id) || []).filter(child => !nextTrail.has(child));
    const childPositions = childIds.map(child => {
      renderedEdges.push({source: id, target: child});
      return place(child, depth + 1, nextTrail);
    });
    const x = childPositions.length
      ? childPositions.reduce((sum, value) => sum + value, 0) / childPositions.length
      : 64 + leafCursor++ * 112;
    positions.set(id, {x, depth});
    return x;
  };
  const orderedRoots = roots.length ? roots : [...nodes.keys()].slice(0, 1);
  orderedRoots.forEach(root => place(root, 0));
  nodes.forEach((item, id) => {
    if (!visited.has(id)) place(id, 0);
  });
  const width = Math.max(760, 128 + Math.max(1, leafCursor - 1) * 112);
  const height = Math.max(270, 126 + maxDepth * 94);
  const svg = analysisSvgElement('svg', {
    class: 'analysis-dependency-tree', viewBox: `0 0 ${width} ${height}`, role: 'img', tabindex: '0'
  });
  svg.append(
    analysisSvgElement('title', {}, '文の係り受けツリー'),
    analysisSvgElement('desc', {}, 'ROOTを上に置き、係り先から係る語へ線を伸ばしています。各ノードには表層形、依存関係、品詞を表示します。')
  );
  renderedEdges.forEach(edge => {
    const source = positions.get(edge.source);
    const target = positions.get(edge.target);
    if (!source || !target) return;
    const sourceY = 46 + source.depth * 94;
    const targetY = 46 + target.depth * 94;
    const middleY = (sourceY + targetY) / 2;
    svg.append(analysisSvgElement('path', {
      d: `M ${source.x} ${sourceY + 27} C ${source.x} ${middleY}, ${target.x} ${middleY}, ${target.x} ${targetY - 27}`,
      class: 'analysis-dependency-edge', 'vector-effect': 'non-scaling-stroke'
    }));
  });
  positions.forEach((position, id) => {
    const item = nodes.get(id) || {};
    const y = 46 + position.depth * 94;
    const isRoot = !Number(item.head_token_id || 0) || Number(item.head_token_id) === id;
    const group = analysisSvgElement('g', {class: `analysis-dependency-node${isRoot ? ' root' : ''}`});
    const surface = String(item.surface || '—');
    group.append(
      analysisSvgElement('rect', {x: position.x - 48, y: y - 27, width: 96, height: 54, rx: 11}),
      analysisSvgElement('text', {x: position.x, y: y - 3, 'text-anchor': 'middle', class: 'surface'}, surface.length > 9 ? `${surface.slice(0, 8)}…` : surface),
      analysisSvgElement('text', {x: position.x, y: y + 15, 'text-anchor': 'middle', class: 'meta'}, `${isRoot ? 'ROOT' : item.dependency || 'dep'} · ${item.upos || 'X'}`),
      analysisSvgElement('title', {}, `${surface} / 原形 ${item.lemma || '—'} / 係り先 ${item.head_surface || 'ROOT'}`)
    );
    svg.append(group);
  });
  if (rows.length > visibleRows.length) {
    svg.append(analysisSvgElement('text', {x: width - 16, y: height - 14, 'text-anchor': 'end', class: 'analysis-tree-truncation'}, `先頭${visibleRows.length}語を表示`));
  }
  return svg;
}

function buildAnalysisDependencyExplorer(dependencies, compact) {
  const groups = groupAnalysisDependencies(dependencies).slice(0, compact ? 12 : 30);
  const module = analysisElement('div', 'analysis-dependency-explorer');
  const toolbar = analysisElement('div', 'analysis-tree-toolbar');
  const field = analysisElement('label');
  field.append(analysisElement('span', '', '表示する文'));
  const select = document.createElement('select');
  groups.forEach((group, index) => select.add(new Option(group.label, String(index))));
  field.append(select);
  const controls = analysisElement('div', 'analysis-tree-pager');
  const previous = analysisElement('button', '', '← 前の文');
  const next = analysisElement('button', '', '次の文 →');
  [previous, next].forEach(button => button.type = 'button');
  controls.append(previous, next);
  toolbar.append(field, controls);
  const stage = analysisElement('div', 'analysis-tree-stage');
  const status = analysisElement('p', 'analysis-chart-note');
  module.append(toolbar, stage, status);
  const render = rawIndex => {
    const index = Math.min(Math.max(0, Number(rawIndex) || 0), Math.max(0, groups.length - 1));
    select.value = String(index);
    const group = groups[index];
    stage.replaceChildren(buildAnalysisDependencyTree(group.rows));
    previous.disabled = index === 0;
    next.disabled = index === groups.length - 1;
    status.textContent = `${index + 1} / ${groups.length}文・${group.rows.length}語。線は係り先から係る語へ向かう依存構造です。`;
  };
  select.addEventListener('change', () => render(select.value));
  previous.addEventListener('click', () => render(Number(select.value) - 1));
  next.addEventListener('click', () => render(Number(select.value) + 1));
  render(0);
  return module;
}

function buildAnalysisCorrelationTable(rows) {
  const computed = rows.filter(item => item.status === 'computed' && Number.isFinite(Number(item.coefficient)));
  const variables = [];
  const labels = new Map();
  computed.forEach(item => {
    [[item.variable_a, item.label_a], [item.variable_b, item.label_b]].forEach(([id, label]) => {
      if (!labels.has(id)) variables.push(id);
      labels.set(id, label || id);
    });
  });
  const values = new Map();
  computed.forEach(item => {
    values.set(`${item.variable_a}::${item.variable_b}`, item);
    values.set(`${item.variable_b}::${item.variable_a}`, item);
  });
  const wrap = analysisElement('div', 'analysis-correlation-wrap');
  const table = analysisElement('table', 'analysis-correlation-table');
  const head = analysisElement('thead');
  const headRow = analysisElement('tr');
  headRow.append(analysisElement('th', '', '変数'));
  variables.forEach(id => {
    const th = analysisElement('th', '', labels.get(id));
    th.title = labels.get(id);
    headRow.append(th);
  });
  head.append(headRow);
  const body = analysisElement('tbody');
  variables.forEach(rowId => {
    const row = analysisElement('tr');
    row.append(analysisElement('th', '', labels.get(rowId)));
    variables.forEach(columnId => {
      const diagonal = rowId === columnId;
      const item = values.get(`${rowId}::${columnId}`);
      const coefficient = diagonal ? 1 : item ? Number(item.coefficient) : NaN;
      const cell = analysisElement('td', 'analysis-correlation-cell', Number.isFinite(coefficient) ? coefficient.toFixed(2) : '—');
      if (Number.isFinite(coefficient)) {
        const strength = Math.abs(coefficient);
        cell.style.setProperty('--correlation-strength', strength.toFixed(3));
        cell.classList.add(coefficient < 0 ? 'negative' : 'positive');
        cell.title = diagonal
          ? `${labels.get(rowId)}（同一変数）`
          : `${labels.get(rowId)} × ${labels.get(columnId)}: r = ${coefficient.toFixed(3)}, ${analysisPValueText(item.p_value)}, N = ${item.n || 0}`;
      }
      row.append(cell);
    });
    body.append(row);
  });
  table.append(head, body);
  wrap.append(table);
  return wrap;
}

function buildAnalysisCorrelationExplorer(correlations) {
  const methods = [...new Set((Array.isArray(correlations) ? correlations : []).filter(item => item.status === 'computed').map(item => item.method))];
  const module = analysisElement('div', 'analysis-chart-module');
  const toolbar = analysisElement('div', 'analysis-chart-toolbar');
  const explanation = analysisElement('div', 'analysis-chart-explanation');
  explanation.append(
    analysisElement('strong', '', '変数間の相関を俯瞰する'),
    analysisElement('span', '', '色の濃さが関連の強さ、緑が正、紫が負の相関です。')
  );
  const switcher = analysisElement('div', 'analysis-chart-switch');
  switcher.setAttribute('role', 'group');
  switcher.setAttribute('aria-label', '相関係数の種類');
  const buttons = new Map();
  methods.forEach(method => {
    const button = analysisElement('button', '', method);
    button.type = 'button';
    buttons.set(method, button);
    switcher.append(button);
  });
  toolbar.append(explanation, switcher);
  const stage = analysisElement('div', 'analysis-correlation-stage');
  const legend = analysisElement('div', 'analysis-correlation-legend');
  legend.append(
    analysisElement('span', '', '−1 強い負'),
    analysisElement('i'),
    analysisElement('span', '', '+1 強い正')
  );
  const note = analysisElement('p', 'analysis-chart-note', '相関は因果関係を示しません。発話単位の探索値として原文・散布図・標本数も確認してください。');
  module.append(toolbar, stage, legend, note);
  const render = method => {
    buttons.forEach((button, key) => {
      const active = key === method;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    stage.replaceChildren(buildAnalysisCorrelationTable(correlations.filter(item => item.method === method)));
  };
  buttons.forEach((button, method) => button.addEventListener('click', () => render(method)));
  render(methods.includes('Pearson') ? 'Pearson' : methods[0]);
  return module;
}

function analysisSectionHeading(anchor, eyebrow, titleText, description) {
  const section = analysisElement('section', 'analysis-section-heading wide');
  section.dataset.analysisAnchor = anchor;
  section.append(
    analysisElement('span', '', eyebrow),
    analysisElement('h2', '', titleText),
    analysisElement('p', '', description)
  );
  return section;
}

function buildAnalysisNavigation() {
  const nav = analysisElement('nav', 'analysis-insight-nav');
  nav.setAttribute('aria-label', '分析ダッシュボード内の移動');
  [
    ['overview', '概要'],
    ['conversation', '会話推移'],
    ['language', '言語構造'],
    ['statistics', '統計'],
    ['exports', '出力・検証']
  ].forEach(([anchor, label], index) => {
    const button = analysisElement('button', index === 0 ? 'active' : '', label);
    button.type = 'button';
    button.dataset.analysisJump = anchor;
    if (index === 0) button.setAttribute('aria-current', 'true');
    nav.append(button);
  });
  return nav;
}

function syncAnalysisNavigationToScroll() {
  analysisNavigationFrame = 0;
  if (!analysisCard || analysisCard.hidden || analysisState.mode !== 'automatic') return;
  const mobile = window.matchMedia('(max-width: 959px)').matches;
  const content = mobile ? analysisMobileContent : analysisDesktopContent;
  if (!content) return;
  const anchors = [...content.querySelectorAll('[data-analysis-anchor]')];
  if (!anchors.length) return;
  const threshold = mobile ? 235 : 105;
  let activeAnchor = anchors[0].dataset.analysisAnchor;
  anchors.forEach(anchor => {
    if (anchor.getBoundingClientRect().top <= threshold) activeAnchor = anchor.dataset.analysisAnchor;
  });
  content.querySelectorAll('[data-analysis-jump]').forEach(button => {
    const active = button.dataset.analysisJump === activeAnchor;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'true');
    else button.removeAttribute('aria-current');
  });
}

function scheduleAnalysisNavigationSync() {
  if (analysisNavigationFrame) return;
  analysisNavigationFrame = window.requestAnimationFrame(syncAnalysisNavigationToScroll);
}

function appendResearchAnalysis(grid, compact) {
  const research = (analysisState.data && analysisState.data.research) || {};
  const linguistics = research.linguistics || {};
  const statistics = research.statistics || {};
  const engine = linguistics.engine || {};
  const coverage = linguistics.coverage || {};

  const morphologyPanel = analysisCardPanel('使われた言葉の種類（形態素・品詞）', 'automatic', 'morphemes', true);
  const engineNotice = analysisElement('div', `analysis-engine-notice ${engine.status || 'fallback'}`);
  engineNotice.append(
    analysisElement('strong', '', `${engine.morphology || '解析器未確認'} / ${engine.syntax || '構文解析未確認'}`),
    analysisElement('p', '', engine.message || '解析状態を確認できませんでした。')
  );
  morphologyPanel.body.append(engineNotice);
  const morphologyMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(morphologyMetrics, '形態素', `${coverage.token_count || 0}件`);
  appendAnalysisMetric(morphologyMetrics, '内容語', `${coverage.content_token_count || 0}件`);
  appendAnalysisMetric(morphologyMetrics, '文', `${coverage.sentence_count || 0}件`);
  appendAnalysisMetric(morphologyMetrics, '係り受け', `${coverage.dependency_count || 0}件`);
  morphologyPanel.body.append(morphologyMetrics);
  const posRows = Array.isArray(linguistics.pos_frequency) ? linguistics.pos_frequency : [];
  const maxPos = Math.max(1, ...posRows.map(item => Number(item.count) || 0));
  posRows.slice(0, compact ? 7 : 12).forEach(item => appendAnalysisBar(
    morphologyPanel.body,
    [item.upos, item.pos_detail].filter(Boolean).join(' / '),
    100 * (Number(item.count) || 0) / maxPos,
    `${item.count || 0}件 / ${analysisNumberText(item.percent, 1, '%')}`,
    '#2F80ED'
  ));
  const morphologyExports = analysisElement('div', 'analysis-inline-exports');
  [
    ['dependencies', '係り受けCSV'],
    ['pos_frequency', '品詞頻度CSV']
  ].forEach(([dataset, label]) => {
    const link = analysisExportLink(label, dataset, 'analysis-inline-export');
    if (link) morphologyExports.append(link);
  });
  morphologyPanel.body.append(morphologyExports);
  grid.append(morphologyPanel.panel);

  const termsPanel = analysisCardPanel('よく使われた重要語（TF・DF）', 'automatic', 'term_frequency');
  const terms = Array.isArray(linguistics.term_frequency) ? linguistics.term_frequency : [];
  const maxTerm = Math.max(1, ...terms.map(item => Number(item.term_frequency) || 0));
  terms.slice(0, compact ? 10 : 15).forEach(item => appendAnalysisBar(
    termsPanel.body,
    item.term,
    100 * (Number(item.term_frequency) || 0) / maxTerm,
    `TF ${item.term_frequency || 0} / DF ${item.document_frequency || 0} / ${item.upos || '—'}`,
    '#6C8B3C'
  ));
  if (!terms.length) termsPanel.body.append(analysisElement('p', 'analysis-no-data', '内容語を抽出できませんでした。解析器の状態と原文を確認してください。'));
  termsPanel.body.append(analysisElement('p', 'analysis-caption', 'TFは総出現回数、DFはその語を含む発話数です。頻度は重要性を意味しません。'));
  grid.append(termsPanel.panel);

  const cooccurrencePanel = analysisCardPanel('一緒に使われる言葉のつながり（共起）', 'automatic', 'cooccurrence', true);
  const cooccurrence = Array.isArray(linguistics.cooccurrence) ? linguistics.cooccurrence : [];
  if (cooccurrence.length) {
    cooccurrencePanel.body.append(buildAnalysisCooccurrenceExplorer(cooccurrence));
  } else {
    cooccurrencePanel.body.append(analysisElement('p', 'analysis-no-data', `同じ発話で${coverage.cooccurrence_min_count || 2}回以上共起する語の組み合わせがありません。`));
  }
  cooccurrencePanel.body.append(analysisElement('p', 'analysis-caption', `発話を文書単位とし、上位${coverage.cooccurrence_top_terms || 60}語からJaccard係数を計算しています。関係の意味は原文で確認してください。`));
  grid.append(cooccurrencePanel.panel);

  const dependencies = Array.isArray(linguistics.dependency_preview) ? linguistics.dependency_preview : [];
  const syntaxPanel = analysisCardPanel('文章内の言葉のつながり（係り受け）', 'automatic', 'dependencies', true);
  if (dependencies.length) {
    syntaxPanel.body.append(buildAnalysisDependencyExplorer(dependencies, compact));
    const details = analysisElement('details', 'analysis-table-details');
    details.append(analysisElement('summary', '', '係り受けの表データを確認'));
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['発話', '語', '原形', '品詞', '関係', '係り先'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    dependencies.slice(0, compact ? 12 : 30).forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.segment_id),
        analysisElement('td', '', item.surface),
        analysisElement('td', '', item.lemma),
        analysisElement('td', '', item.upos),
        analysisElement('td', '', item.dependency),
        analysisElement('td', '', item.head_token_id ? `${item.head_surface} (#${item.head_token_id})` : 'ROOT')
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    details.append(wrap);
    syntaxPanel.body.append(details);
  } else {
    syntaxPanel.body.append(analysisElement('p', 'analysis-no-data', '係り受けデータがありません。GiNZAとja-ginzaの導入状態を確認してください。'));
  }
  grid.append(syntaxPanel.panel);

  grid.append(analysisSectionHeading(
    'statistics', '03 / STATISTICS', '統計で比較する',
    '発話単位の分布、変数間の関連、群間差を順に確認します。p値だけでなく効果量・標本数・前提条件も併記します。'
  ));

  const correlations = Array.isArray(statistics.correlations) ? statistics.correlations : [];
  const computedCorrelations = correlations.filter(item => item.status === 'computed');
  const correlationPanel = analysisCardPanel('指標どうしの関係（相関）', 'automatic', 'correlations', true);
  if (computedCorrelations.length) {
    correlationPanel.body.append(buildAnalysisCorrelationExplorer(correlations));
  } else {
    correlationPanel.body.append(analysisElement('p', 'analysis-no-data', '相関を計算できる変数または標本数が不足しています。'));
  }
  grid.append(correlationPanel.panel);

  const descriptives = (Array.isArray(statistics.descriptives) ? statistics.descriptives : [])
    .filter(item => item.scope === 'overall');
  const statsPanel = analysisCardPanel('会話データの基本統計', 'automatic', 'descriptives', true);
  if (descriptives.length) {
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['変数', 'N', '平均', '標準偏差', '中央値', '最小', '最大'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    descriptives.forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.label || item.variable),
        analysisElement('td', '', item.n || 0),
        analysisElement('td', '', analysisNumberText(item.mean, 3)),
        analysisElement('td', '', analysisNumberText(item.standard_deviation, 3)),
        analysisElement('td', '', analysisNumberText(item.median, 3)),
        analysisElement('td', '', analysisNumberText(item.minimum, 3)),
        analysisElement('td', '', analysisNumberText(item.maximum, 3))
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    statsPanel.body.append(wrap);
  } else statsPanel.body.append(analysisElement('p', 'analysis-no-data', '記述統計を計算できる発話がありません。'));
  statsPanel.body.append(analysisElement('p', 'analysis-caption', `分析単位: ${statistics.analysis_unit || '発話'} / 比較軸: ${statistics.group_variable === 'role' ? '役割' : '話者'}。欠損値は変数ごとに除外します。`));
  grid.append(statsPanel.panel);

  const tests = Array.isArray(statistics.tests) ? statistics.tests : [];
  const crosstabs = Array.isArray(statistics.crosstabs) ? statistics.crosstabs : [];
  const selectedTerms = Array.isArray(statistics.selected_terms) ? statistics.selected_terms : [];
  const selectedTermPanel = analysisCardPanel('手動選択単語のクロス集計＋カイ二乗検定', 'configured', 'crosstabs', true);
  if (selectedTerms.length) {
    selectedTerms.slice(0, compact ? 8 : 20).forEach(term => {
      const columnVariable = `selected_term:${term}`;
      const rows = crosstabs.filter(item => item.column_variable === columnVariable);
      const test = tests.find(item => item.family === 'クロス集計' && item.outcome_label === `単語「${term}」`);
      const article = analysisElement('article', 'analysis-selected-term-result');
      article.append(analysisElement('h4', '', `「${term}」 × ${statistics.group_variable === 'role' ? '役割' : '話者'}`));
      if (rows.length) {
        const wrap = analysisElement('div', 'analysis-table-wrap');
        const table = analysisElement('table', 'analysis-table');
        const head = analysisElement('thead');
        const headRow = analysisElement('tr');
        ['比較群', '出現', '度数', '行%', '列%'].forEach(value => headRow.append(analysisElement('th', '', value)));
        head.append(headRow);
        const body = analysisElement('tbody');
        rows.forEach(item => {
          const row = analysisElement('tr');
          row.append(
            analysisElement('td', '', item.row_value),
            analysisElement('td', '', item.column_value),
            analysisElement('td', '', item.count || 0),
            analysisElement('td', '', analysisNumberText(item.row_percent, 1, '%')),
            analysisElement('td', '', analysisNumberText(item.column_percent, 1, '%'))
          );
          body.append(row);
        });
        table.append(head, body);
        wrap.append(table);
        article.append(wrap);
      }
      if (test && test.status === 'computed') {
        article.append(analysisElement(
          'p',
          test.significant_0_05 ? 'analysis-term-test-summary significant' : 'analysis-term-test-summary',
          `Pearson χ²(${test.df1}) = ${analysisNumberText(test.statistic, 3)}, p ${analysisPValueText(test.p_value)}, Cramér's V = ${analysisNumberText(test.effect_size, 3)}, N = ${test.n || 0}`
        ));
      } else {
        article.append(analysisElement('p', 'analysis-term-test-summary unavailable', '比較群または「あり／なし」の一方が不足しているため検定は未計算です。'));
      }
      selectedTermPanel.body.append(article);
    });
  } else {
    selectedTermPanel.body.append(analysisElement('p', 'analysis-no-data', '「設定・手動」画面で単語を選び、検定を実行してください。'));
  }
  selectedTermPanel.body.append(analysisElement('p', 'analysis-caption', '発話単位の探索的検定です。同じ話者の発話は独立でない可能性があり、多重検定補正も行っていません。'));
  grid.append(selectedTermPanel.panel);

  const testsPanel = analysisCardPanel('グループ間の違いと効果の大きさ', 'automatic', 'statistical_tests', true);
  const computedTests = tests.filter(item => item.status === 'computed');
  if (computedTests.length) {
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table analysis-stat-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['検定', '対象', 'N', '統計量', 'p値', '効果量'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    computedTests.slice(0, compact ? 10 : 24).forEach(item => {
      const row = analysisElement('tr', item.significant_0_05 ? 'analysis-stat-significant' : '');
      row.append(
        analysisElement('td', '', item.test),
        analysisElement('td', '', item.outcome_label || item.outcome),
        analysisElement('td', '', item.n || 0),
        analysisElement('td', '', analysisNumberText(item.statistic, 3)),
        analysisElement('td', '', analysisPValueText(item.p_value)),
        analysisElement('td', '', item.effect_name ? `${item.effect_name} = ${analysisNumberText(item.effect_size, 3)}` : '—')
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    testsPanel.body.append(wrap);
  } else testsPanel.body.append(analysisElement('p', 'analysis-no-data', '比較群または標本数が不足しているため、推測統計を計算していません。'));
  const unavailableCount = tests.filter(item => item.status !== 'computed').length;
  testsPanel.body.append(analysisElement('p', 'analysis-caption', `発話の独立性を仮定しにくいため探索的な値です。p値だけで結論を出さず、効果量・標本数・前提条件を確認してください。未計算 ${unavailableCount}件。`));
  grid.append(testsPanel.panel);

  const crosstabsPanel = analysisCardPanel('項目の組み合わせ比較（クロス集計）', 'automatic', 'crosstabs', true);
  if (crosstabs.length) {
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['表', '行', '列', '度数', '行%', '列%'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    crosstabs.slice(0, compact ? 16 : 40).forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.table_label),
        analysisElement('td', '', item.row_value),
        analysisElement('td', '', item.column_value),
        analysisElement('td', '', item.count || 0),
        analysisElement('td', '', analysisNumberText(item.row_percent, 1, '%')),
        analysisElement('td', '', analysisNumberText(item.column_percent, 1, '%'))
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    crosstabsPanel.body.append(wrap);
  } else crosstabsPanel.body.append(analysisElement('p', 'analysis-no-data', 'クロス集計できるデータがありません。'));
  grid.append(crosstabsPanel.panel);

  grid.append(analysisSectionHeading(
    'exports', '04 / OUTPUT & REVIEW', '出力して検証する',
    '標準出力のExcel、再分析用CSV、手法と限界をまとめています。論文利用前に原文・欠損・解析器の状態を確認してください。'
  ));

  grid.append(analysisExportDirectory('研究分析データの出力', 'automatic', [
    ['xlsx', 'Excelブック（標準出力）'],
    ['segments_all', '発話データ CSV'],
    ['morphemes', '形態素 CSV'],
    ['dependencies', '構文・係り受け CSV'],
    ['pos_frequency', '品詞頻度 CSV'],
    ['term_frequency', '語彙頻度 CSV'],
    ['cooccurrence', '共起 CSV'],
    ['descriptives', '記述統計 CSV'],
    ['frequencies', '度数分布 CSV'],
    ['crosstabs', 'クロス集計 CSV'],
    ['statistical_tests', '統計検定 CSV'],
    ['correlations', '相関 CSV'],
    ['analysis_methods', '分析手法・出典 CSV']
  ]));

  const methodsPanel = analysisCardPanel('分析方法と結果を見るときの注意', 'automatic', 'analysis_methods', true);
  const methods = Array.isArray(research.methods) ? research.methods : [];
  methods.forEach(item => {
    const article = analysisElement('article', 'analysis-method-item');
    article.append(
      analysisElement('strong', '', `${item.category}: ${item.method}`),
      analysisElement('p', '', `${item.engine || '内蔵'} ${item.engine_version || ''} / ${item.description || ''}`)
    );
    if (item.source_url && String(item.source_url).startsWith('https://')) {
      const link = analysisElement('a', '', item.source_title || '公式資料');
      link.href = item.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      article.append(link);
    }
    methodsPanel.body.append(article);
  });
  const limitations = Array.isArray(research.limitations) ? research.limitations : [];
  if (limitations.length) {
    const details = analysisElement('details', 'analysis-cautions');
    details.append(analysisElement('summary', '', '論文利用前に確認する限界'));
    const list = analysisElement('ul');
    limitations.forEach(value => list.append(analysisElement('li', '', value)));
    details.append(list);
    methodsPanel.body.append(details);
  }
  grid.append(methodsPanel.panel);
}

function buildAnalysisScopeSwitch() {
  const switcher = analysisElement('section', 'analysis-scope-switch');
  switcher.setAttribute('aria-label', '分析対象の単位');
  [
    ['overall', 'インタビュー全体', '会話全体の流れ・構造・統計を確認'],
    ['speakers', '話者ごと', '個人の発話量・語彙・属性を確認']
  ].forEach(([scope, titleText, description]) => {
    const active = analysisState.automaticScope === scope;
    const button = analysisElement('button', active ? 'active' : '');
    button.type = 'button';
    button.dataset.analysisScope = scope;
    button.setAttribute('aria-pressed', String(active));
    button.append(
      analysisElement('strong', '', titleText),
      analysisElement('span', '', description)
    );
    switcher.append(button);
  });
  return switcher;
}

function analysisSpeakerAttributeValue(metric, key) {
  const profile = metric && typeof metric.profile === 'object' ? metric.profile : {};
  if (key === 'role') return speakerRoleLabels[metric.role] || metric.role || '';
  if (key === 'tags') return (Array.isArray(profile.tags) ? profile.tags : []).join('・');
  if (key.startsWith('custom:')) {
    const attributes = profile.attributes && typeof profile.attributes === 'object' ? profile.attributes : {};
    return String(attributes[key.slice(7)] || '').trim();
  }
  return String(profile[key] || '').trim();
}

function analysisSpeakerAttributeDimensions(speakers) {
  const fixed = [
    ['role', '役割'],
    ['organization', '組織'],
    ['department', '部署'],
    ['job_title', '役職'],
    ['conditions', '会話固有条件'],
    ['tags', 'タグ']
  ];
  const customKeys = new Set();
  speakers.forEach(metric => {
    const profile = metric && typeof metric.profile === 'object' ? metric.profile : {};
    const attributes = profile.attributes && typeof profile.attributes === 'object' ? profile.attributes : {};
    Object.keys(attributes).forEach(key => customKeys.add(key));
  });
  const candidates = [
    ...fixed,
    ...[...customKeys].sort((a, b) => a.localeCompare(b, 'ja')).map(key => [`custom:${key}`, key])
  ];
  return candidates
    .map(([key, label]) => ({
      key,
      label,
      values: [...new Set(speakers.map(metric => analysisSpeakerAttributeValue(metric, key)).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b, 'ja', {numeric: true, sensitivity: 'base'}))
    }))
    .filter(dimension => dimension.values.length);
}

function sortedAnalysisSpeakers(speakers, sortKey) {
  const values = [...speakers];
  const nameCompare = (a, b) => String(a.speaker_name || a.speaker).localeCompare(
    String(b.speaker_name || b.speaker), 'ja', {numeric: true, sensitivity: 'base'}
  );
  if (sortKey === 'speaker_name') return values.sort(nameCompare);
  if (sortKey === 'speaker_label') {
    return values.sort((a, b) => String(a.speaker).localeCompare(String(b.speaker), 'ja', {numeric: true}));
  }
  if (sortKey.startsWith('attribute:')) {
    const attributeKey = sortKey.slice(10);
    return values.sort((a, b) => {
      const valueA = analysisSpeakerAttributeValue(a, attributeKey);
      const valueB = analysisSpeakerAttributeValue(b, attributeKey);
      if (!valueA && valueB) return 1;
      if (valueA && !valueB) return -1;
      return valueA.localeCompare(valueB, 'ja', {numeric: true, sensitivity: 'base'}) || nameCompare(a, b);
    });
  }
  return values.sort((a, b) => Number(b.speaking_seconds || 0) - Number(a.speaking_seconds || 0) || nameCompare(a, b));
}

function buildAnalysisSpeakerTimelineChart(metric, bins) {
  const module = analysisElement('div', 'analysis-chart-module');
  const explanation = analysisElement('div', 'analysis-chart-explanation');
  explanation.append(
    analysisElement('strong', '', `${metric.speaker_name || metric.speaker}の発話タイミング`),
    analysisElement('span', '', '各時間帯にこの話者が発話した秒数を示します。')
  );
  const stage = analysisElement('div', 'analysis-chart-stage');
  stage.append(buildAnalysisLineSvg([{
    id: metric.speaker,
    label: metric.speaker_name || metric.speaker,
    color: safeAnalysisColor(metric.color),
    values: bins.map(bin => Number(((bin.speakers || []).find(item => String(item.speaker) === String(metric.speaker)) || {}).seconds) || 0)
  }], bins));
  const legend = analysisElement('div', 'analysis-chart-legend');
  const entry = analysisElement('span');
  const marker = analysisElement('i');
  marker.style.backgroundColor = safeAnalysisColor(metric.color);
  entry.append(marker, document.createTextNode(metric.speaker_name || metric.speaker));
  legend.append(entry);
  module.append(explanation, stage, legend, analysisElement('p', 'analysis-chart-note', '折れ線が0の時間帯は、この話者の発話が記録されていない区間です。'));
  return module;
}

function analysisMedian(values) {
  const sorted = values.map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function renderSpeakerAnalysis(compact) {
  const fragment = document.createDocumentFragment();
  const data = analysisState.data || {};
  const automatic = data.automatic || {};
  const speakers = Array.isArray(automatic.speaker_metrics) ? automatic.speaker_metrics : [];
  if (!speakers.length) {
    fragment.append(analysisElement('p', 'analysis-no-data analysis-speaker-empty', '話者ごとの分析に利用できる発話データがありません。'));
    return fragment;
  }

  const dimensions = analysisSpeakerAttributeDimensions(speakers);
  const allowedSorts = new Set(['speaking_desc', 'speaker_name', 'speaker_label', ...dimensions.map(item => `attribute:${item.key}`)]);
  if (!allowedSorts.has(analysisState.speakerSort)) analysisState.speakerSort = 'speaking_desc';
  const activeDimension = analysisState.speakerSort.startsWith('attribute:')
    ? dimensions.find(item => item.key === analysisState.speakerSort.slice(10)) : null;
  if (analysisState.speakerAttributeFilter && (!activeDimension || !activeDimension.values.includes(analysisState.speakerAttributeFilter))) {
    analysisState.speakerAttributeFilter = '';
  }
  const sortedSpeakers = sortedAnalysisSpeakers(speakers, analysisState.speakerSort);
  const visibleSpeakers = analysisState.speakerAttributeFilter && activeDimension
    ? sortedSpeakers.filter(item => analysisSpeakerAttributeValue(item, activeDimension.key) === analysisState.speakerAttributeFilter)
    : sortedSpeakers;
  const selected = visibleSpeakers.find(item => String(item.speaker) === String(analysisState.selectedSpeaker))
    || visibleSpeakers[0];
  if (selected) analysisState.selectedSpeaker = String(selected.speaker);

  const toolbar = analysisElement('section', 'analysis-speaker-toolbar');
  const toolbarIntro = analysisElement('div', 'analysis-speaker-toolbar-intro');
  toolbarIntro.append(
    analysisElement('span', '', 'SPEAKER ANALYSIS'),
    analysisElement('h2', '', '話者を並べ替えて個別に確認'),
    analysisElement('p', '', dimensions.length
      ? `登録済み属性 ${dimensions.length}項目を利用できます。属性順では同じ値の話者をまとめて表示します。`
      : '話者名・ラベル・発話量で並べ替えられます。話者管理で属性を付けると属性順も選択できます。')
  );
  const controls = analysisElement('div', 'analysis-speaker-sort-controls');
  const sortLabel = analysisElement('label');
  sortLabel.append(analysisElement('span', '', '並べ替え'));
  const sortSelect = document.createElement('select');
  [
    ['speaking_desc', '発話時間が長い順'],
    ['speaker_name', '話者名順'],
    ['speaker_label', '話者ラベル順']
  ].forEach(([value, label]) => sortSelect.add(new Option(label, value)));
  dimensions.forEach(item => sortSelect.add(new Option(`属性：${item.label}`, `attribute:${item.key}`)));
  sortSelect.value = analysisState.speakerSort;
  sortSelect.addEventListener('change', () => {
    analysisState.speakerSort = sortSelect.value;
    analysisState.speakerAttributeFilter = '';
    renderAnalysisWorkspace();
  });
  sortLabel.append(sortSelect);
  controls.append(sortLabel);
  if (activeDimension) {
    const filterLabel = analysisElement('label');
    filterLabel.append(analysisElement('span', '', `${activeDimension.label}で絞り込み`));
    const filterSelect = document.createElement('select');
    filterSelect.add(new Option('すべての属性値', ''));
    activeDimension.values.forEach(value => filterSelect.add(new Option(`${value}（${speakers.filter(item => analysisSpeakerAttributeValue(item, activeDimension.key) === value).length}人）`, value)));
    filterSelect.value = analysisState.speakerAttributeFilter;
    filterSelect.addEventListener('change', () => {
      analysisState.speakerAttributeFilter = filterSelect.value;
      analysisState.selectedSpeaker = '';
      renderAnalysisWorkspace();
    });
    filterLabel.append(filterSelect);
    controls.append(filterLabel);
  }
  const exportLink = analysisExportLink('話者別集計CSV', 'speakers', 'analysis-inline-export');
  if (exportLink) controls.append(exportLink);
  toolbar.append(toolbarIntro, controls);
  fragment.append(toolbar);

  const workspace = analysisElement('div', 'analysis-speaker-dashboard');
  const browser = analysisElement('aside', 'analysis-speaker-browser');
  const browserHeading = analysisElement('header');
  browserHeading.append(
    analysisElement('strong', '', `話者 ${visibleSpeakers.length} / ${speakers.length}人`),
    analysisElement('span', '', activeDimension ? `${activeDimension.label}順` : 'クリックして個別分析を表示')
  );
  browser.append(browserHeading);
  const list = analysisElement('div', 'analysis-speaker-list');
  let previousGroup = null;
  visibleSpeakers.forEach(metric => {
    const groupValue = activeDimension
      ? analysisSpeakerAttributeValue(metric, activeDimension.key) || '未設定' : '';
    if (activeDimension && groupValue !== previousGroup) {
      list.append(analysisElement('div', 'analysis-speaker-group-label', `${activeDimension.label}：${groupValue}`));
      previousGroup = groupValue;
    }
    const active = selected && String(metric.speaker) === String(selected.speaker);
    const button = analysisElement('button', active ? 'active' : '');
    button.type = 'button';
    button.dataset.analysisSpeakerId = metric.speaker;
    button.setAttribute('aria-pressed', String(active));
    button.style.setProperty('--speaker-color', safeAnalysisColor(metric.color));
    const identity = analysisElement('span', 'analysis-speaker-list-identity');
    identity.append(
      analysisElement('i'),
      analysisElement('strong', '', metric.speaker_name || metric.speaker)
    );
    const detail = activeDimension
      ? `${groupValue} / ${formatTime(metric.speaking_seconds || 0)}`
      : `${speakerRoleLabels[metric.role] || metric.role || '役割未設定'} / ${formatTime(metric.speaking_seconds || 0)}`;
    button.append(identity, analysisElement('small', '', detail));
    list.append(button);
  });
  if (!visibleSpeakers.length) list.append(analysisElement('p', 'analysis-no-data', 'この属性値に該当する話者はいません。'));
  browser.append(list);
  workspace.append(browser);

  const detail = analysisElement('section', 'analysis-speaker-detail');
  detail.setAttribute('aria-label', '選択した話者の分析');
  if (!selected) {
    detail.append(analysisElement('p', 'analysis-no-data', '左の一覧から話者を選択してください。'));
    workspace.append(detail);
    fragment.append(workspace);
    return fragment;
  }
  const detailHeader = analysisElement('section', 'analysis-speaker-detail-header');
  detailHeader.style.setProperty('--speaker-color', safeAnalysisColor(selected.color));
  const titleGroup = analysisElement('div');
  titleGroup.append(
    analysisElement('span', '', selected.speaker),
    analysisElement('h2', '', selected.speaker_name || selected.speaker),
    analysisElement('p', '', `${speakerRoleLabels[selected.role] || selected.role || '役割未設定'}の発話を、インタビュー全体との比率を保ったまま表示しています。`)
  );
  const profileAttributes = analysisElement('div', 'analysis-speaker-attributes');
  dimensions.forEach(dimension => {
    const value = analysisSpeakerAttributeValue(selected, dimension.key);
    if (!value) return;
    const chip = analysisElement('span');
    chip.append(analysisElement('small', '', dimension.label), document.createTextNode(value));
    profileAttributes.append(chip);
  });
  if (!profileAttributes.childNodes.length) profileAttributes.append(analysisElement('span', 'empty', '登録属性なし'));
  detailHeader.append(titleGroup, profileAttributes);
  detail.append(detailHeader);

  const metrics = analysisElement('div', 'analysis-overview analysis-speaker-overview');
  appendAnalysisMetric(metrics, '発話時間', formatTime(selected.speaking_seconds || 0), analysisNumberText(selected.speaking_percent, 1, '%'));
  appendAnalysisMetric(metrics, '発話回数', `${selected.turn_count || 0}回`, `平均 ${analysisNumberText(selected.average_turn_seconds, 1, '秒')}`);
  appendAnalysisMetric(metrics, '文字数', `${selected.characters || 0}字`, `${analysisNumberText(selected.characters_per_minute, 1)}字/分`);
  appendAnalysisMetric(metrics, '質問候補', `${selected.question_candidates || 0}件`);
  appendAnalysisMetric(metrics, '最初の発話', formatTime(selected.first_start || 0));
  appendAnalysisMetric(metrics, '最後の発話', formatTime(selected.last_end || 0));
  detail.append(metrics);

  const detailGrid = analysisElement('div', 'analysis-grid analysis-speaker-detail-grid');
  const bins = Array.isArray(automatic.time_bins) ? automatic.time_bins : [];
  const timelinePanel = analysisCardPanel('この話者の時間推移', 'automatic', '', true);
  if (bins.length) timelinePanel.body.append(buildAnalysisSpeakerTimelineChart(selected, bins));
  else timelinePanel.body.append(analysisElement('p', 'analysis-no-data', '時間推移を表示できません。'));
  detailGrid.append(timelinePanel.panel);

  const research = data.research || {};
  const linguistics = research.linguistics || {};
  const speakerTermRows = Array.isArray(linguistics.speaker_term_frequency) ? linguistics.speaker_term_frequency : [];
  const speakerTerms = speakerTermRows.find(item => String(item.speaker) === String(selected.speaker)) || {};
  const termsPanel = analysisCardPanel('この話者の内容語', 'automatic');
  const terms = Array.isArray(speakerTerms.terms) ? speakerTerms.terms : [];
  const maxTerm = Math.max(1, ...terms.map(item => Number(item.term_frequency) || 0));
  terms.slice(0, compact ? 10 : 15).forEach(item => appendAnalysisBar(
    termsPanel.body,
    item.term,
    100 * (Number(item.term_frequency) || 0) / maxTerm,
    `TF ${item.term_frequency || 0} / DF ${item.document_frequency || 0} / ${item.upos || '—'}`,
    selected.color
  ));
  if (!terms.length) termsPanel.body.append(analysisElement('p', 'analysis-no-data', 'この話者の内容語を抽出できませんでした。'));
  termsPanel.body.append(analysisElement('p', 'analysis-caption', `内容語 ${speakerTerms.content_token_count || 0}件 / 異なり語 ${speakerTerms.unique_term_count || 0}件。GiNZA/Sudachiの解析結果を話者内で再集計しています。`));
  detailGrid.append(termsPanel.panel);

  const distributionPanel = analysisCardPanel('話者内の発話分布', 'automatic');
  const speakerSegments = (Array.isArray(data.segments) ? data.segments : [])
    .filter(item => String(item.speaker) === String(selected.speaker) && !item.excluded);
  const durations = speakerSegments.map(item => Number(item.duration) || 0);
  const distributionMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(distributionMetrics, '中央値', analysisNumberText(analysisMedian(durations), 2, '秒'));
  appendAnalysisMetric(distributionMetrics, '最長発話', analysisNumberText(Math.max(0, ...durations), 2, '秒'));
  appendAnalysisMetric(distributionMetrics, '質問候補率', analysisNumberText(100 * speakerSegments.filter(item => item.question_candidate).length / Math.max(1, speakerSegments.length), 1, '%'));
  appendAnalysisMetric(distributionMetrics, '内容語多様性', speakerTerms.content_token_count
    ? analysisNumberText(100 * Number(speakerTerms.unique_term_count || 0) / Number(speakerTerms.content_token_count), 1, '%') : '—');
  distributionPanel.body.append(distributionMetrics, analysisElement('p', 'analysis-caption', '話者内の記述値です。話者間の優劣や発言の重要性を示すものではありません。'));
  detailGrid.append(distributionPanel.panel);

  const emotionPanel = analysisCardPanel('感情推定・手動コード', 'automatic');
  const emotionCounts = selected.emotion_counts && typeof selected.emotion_counts === 'object' ? selected.emotion_counts : {};
  const codeCounts = selected.code_counts && typeof selected.code_counts === 'object' ? selected.code_counts : {};
  const codeLabels = new Map(((data.manual || {}).codebook || []).map(item => [String(item.id), item.label || item.id]));
  const summaryRows = [
    ...Object.entries(emotionCounts).map(([label, count]) => [`感情推定 / ${label}`, count]),
    ...Object.entries(codeCounts).map(([id, count]) => [`手動コード / ${codeLabels.get(String(id)) || id}`, count])
  ].sort((a, b) => Number(b[1]) - Number(a[1]));
  summaryRows.forEach(([label, count]) => {
    const row = analysisElement('div', 'analysis-list-row');
    row.append(analysisElement('strong', '', label), analysisElement('span', '', `${count}件`));
    emotionPanel.body.append(row);
  });
  if (!summaryRows.length) emotionPanel.body.append(analysisElement('p', 'analysis-no-data', '感情推定または手動コードの集計はありません。'));
  emotionPanel.body.append(analysisElement('p', 'analysis-caption', '感情はモデル推定、コードは研究者による付与です。両者を同じ尺度として比較しないでください。'));
  detailGrid.append(emotionPanel.panel);

  const transitionPanel = analysisCardPanel('この話者との話者交替', 'automatic', '', true);
  const transitions = (Array.isArray(automatic.transitions) ? automatic.transitions : [])
    .filter(item => String(item.from_speaker) === String(selected.speaker) || String(item.to_speaker) === String(selected.speaker))
    .sort((a, b) => Number(b.count || 0) - Number(a.count || 0));
  if (transitions.length) {
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['方向', '相手話者', '回数', '平均間隔', '重なり候補'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    transitions.slice(0, compact ? 10 : 20).forEach(item => {
      const outgoing = String(item.from_speaker) === String(selected.speaker);
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', outgoing ? 'この話者 → 相手' : '相手 → この話者'),
        analysisElement('td', '', outgoing ? item.to_name || item.to_speaker : item.from_name || item.from_speaker),
        analysisElement('td', '', item.count || 0),
        analysisElement('td', '', analysisNumberText(item.average_gap_seconds, 2, '秒')),
        analysisElement('td', '', item.overlap_candidates || 0)
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    transitionPanel.body.append(wrap);
  } else transitionPanel.body.append(analysisElement('p', 'analysis-no-data', '他の話者との交替データがありません。'));
  transitionPanel.body.append(analysisElement('p', 'analysis-caption', '話者交替の回数は影響・同意・対立を意味しません。前後の発話を確認してください。'));
  detailGrid.append(transitionPanel.panel);

  const utterancePanel = analysisCardPanel('この話者の発話一覧', 'automatic', '', true);
  const utteranceList = analysisElement('div', 'analysis-speaker-utterances');
  speakerSegments.slice(0, compact ? 12 : 30).forEach(item => {
    const article = analysisElement('article', 'analysis-speaker-utterance');
    article.append(
      analysisElement('time', '', `${formatTime(item.start || 0)}–${formatTime(item.end || 0)}`),
      analysisElement('p', '', item.text || '（本文なし）')
    );
    utteranceList.append(article);
  });
  if (!speakerSegments.length) utteranceList.append(analysisElement('p', 'analysis-no-data', '表示できる発話がありません。'));
  utterancePanel.body.append(utteranceList);
  if (speakerSegments.length > (compact ? 12 : 30)) {
    utterancePanel.body.append(analysisElement('p', 'analysis-limit-note', `表示負荷を抑えるため先頭${compact ? 12 : 30}件を表示しています。全件は発話データCSVまたはExcelで確認できます。`));
  }
  detailGrid.append(utterancePanel.panel);
  detail.append(detailGrid);
  workspace.append(detail);
  fragment.append(workspace);
  return fragment;
}

function renderAutomaticAnalysis(compact) {
  const fragment = document.createDocumentFragment();
  const data = analysisState.data || {};
  const automatic = data.automatic || {};
  const overview = automatic.overview || {};
  const speakerScope = analysisState.automaticScope === 'speakers';
  const intro = analysisElement('div', 'analysis-result-intro');
  intro.dataset.analysisAnchor = 'overview';
  intro.append(
    analysisElement('span', 'analysis-kind automatic', '自動集計'),
    analysisElement('h2', '', speakerScope
      ? '話者ごとの会話データ分析'
      : '会話全体の分析結果'),
    analysisElement('p', '', speakerScope
      ? '話者を選び、発話量・時間推移・内容語・話者交替・登録属性を個別に確認します。属性は比較や並べ替えのための記述情報です。'
      : '保存済みの全発話から、会話全体の流れ・言語構造・統計を計算します。重要性、影響力、合意や感情を確定するものではありません。')
  );
  fragment.append(intro, buildAnalysisScopeSwitch());

  if (speakerScope) {
    fragment.append(renderSpeakerAnalysis(compact));
    return fragment;
  }

  const metrics = analysisElement('div', 'analysis-overview');
  appendAnalysisMetric(metrics, '会話時間', formatTime(overview.session_duration || 0));
  appendAnalysisMetric(metrics, '対象発話', `${overview.included_segment_count || 0}件`, `全${overview.segment_count || 0}件`);
  appendAnalysisMetric(metrics, '話者', `${overview.speaker_count || 0}人`);
  appendAnalysisMetric(metrics, '参加者', `${overview.participant_count || 0}人`, '司会除外設定を反映');
  appendAnalysisMetric(metrics, '総発話時間', formatTime(overview.total_speaking_seconds || 0));
  fragment.append(metrics);

  const observations = Array.isArray(automatic.observations) ? automatic.observations : [];
  if (observations.length) {
    const box = analysisElement('section', 'analysis-observations');
    box.append(analysisElement('h3', '', '確認候補'));
    observations.forEach(item => {
      const row = analysisElement('article', item.level === 'attention' ? 'attention' : 'info');
      row.append(analysisElement('strong', '', item.label || '確認候補'), analysisElement('p', '', item.message || ''));
      box.append(row);
    });
    fragment.append(box);
  }

  fragment.append(buildAnalysisNavigation());

  const grid = analysisElement('div', 'analysis-grid');
  grid.append(analysisSectionHeading(
    'conversation', '01 / CONVERSATION FLOW', '会話の流れを見る',
    'まず時間推移と話者別の参加量を見て、次に話者交替・無音・重なりの候補を確認します。'
  ));
  const speakers = Array.isArray(automatic.speaker_metrics) ? automatic.speaker_metrics : [];
  const timelinePanel = analysisCardPanel('発話量の変化（時間別）', 'automatic', 'timeline', true);
  const bins = Array.isArray(automatic.time_bins) ? automatic.time_bins : [];
  if (bins.length) timelinePanel.body.append(buildAnalysisTimelineChart(bins, speakers));
  else timelinePanel.body.append(analysisElement('p', 'analysis-no-data', '時間推移を表示できる発話がありません。'));
  grid.append(timelinePanel.panel);

  const speakerPanel = analysisCardPanel('話者ごとの発話量', 'automatic', 'speakers', true);
  if (!speakers.length) {
    speakerPanel.body.append(analysisElement('p', 'analysis-no-data', '発話データがありません。'));
  } else {
    speakers.forEach(item => {
      appendAnalysisBar(
        speakerPanel.body,
        item.speaker_name || item.speaker || '話者',
        item.speaking_percent,
        `${analysisNumberText(item.speaking_percent, 1, '%')} / ${formatTime(item.speaking_seconds || 0)} / ${item.turn_count || 0}回`,
        item.color
      );
    });
  }
  grid.append(speakerPanel.panel);

  const balancePanel = analysisCardPanel('参加者の発言バランス', 'automatic');
  const balance = automatic.balance || {};
  const balanceMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(balanceMetrics, '均等度', analysisNumberText((Number(balance.normalized_evenness) || 0) * 100, 1, '%'), '100%に近いほど均等');
  appendAnalysisMetric(balanceMetrics, '最大比率', analysisNumberText(balance.max_participant_percent, 1, '%'), balance.max_participant_name || '—');
  appendAnalysisMetric(balanceMetrics, 'Gini係数', analysisNumberText(balance.gini, 3), '0に近いほど均等');
  balancePanel.body.append(balanceMetrics, analysisElement('p', 'analysis-caption', '発言量の偏りを示す記述値です。発言の重要性や場への影響力は表しません。'));
  grid.append(balancePanel.panel);

  const moderatorPanel = analysisCardPanel('司会者と参加者の発言関係', 'automatic');
  const moderator = automatic.moderator || {};
  const moderatorMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(moderatorMetrics, '司会発話比率', moderator.assigned ? analysisNumberText(moderator.speaking_percent, 1, '%') : '役割未設定');
  appendAnalysisMetric(moderatorMetrics, '質問候補', `${moderator.question_candidates || 0}件`);
  appendAnalysisMetric(moderatorMetrics, '参加者応答', `${moderator.participant_responses || 0}件`);
  appendAnalysisMetric(moderatorMetrics, '参加者間遷移', `${moderator.participant_to_participant_transitions || 0}件`);
  moderatorPanel.body.append(moderatorMetrics, analysisElement('p', 'analysis-caption', '質問・応答は表記と話者遷移からの候補です。進行品質の評価ではありません。'));
  grid.append(moderatorPanel.panel);

  const transitionsPanel = analysisCardPanel('発言者の交替パターン', 'automatic', 'transitions', true);
  const transitions = Array.isArray(automatic.transitions) ? automatic.transitions : [];
  if (transitions.length) {
    const tableWrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['前の話者', '次の話者', '回数', '平均間隔', '重なり候補'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    transitions.slice(0, compact ? 8 : 20).forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.from_name || item.from_speaker),
        analysisElement('td', '', item.to_name || item.to_speaker),
        analysisElement('td', '', item.count || 0),
        analysisElement('td', '', analysisNumberText(item.average_gap_seconds, 2, '秒')),
        analysisElement('td', '', item.overlap_candidates || 0)
      );
      body.append(row);
    });
    table.append(head, body);
    tableWrap.append(table);
    transitionsPanel.body.append(tableWrap, analysisElement('p', 'analysis-caption', '遷移回数は影響関係や同意を意味しません。'));
  } else transitionsPanel.body.append(analysisElement('p', 'analysis-no-data', '話者交替のデータがありません。'));
  grid.append(transitionsPanel.panel);

  const gapsPanel = analysisCardPanel('沈黙・同時発話の候補', 'automatic', 'gaps');
  const longGaps = Array.isArray(automatic.long_gaps) ? automatic.long_gaps : [];
  const overlaps = Array.isArray(automatic.overlap_candidates) ? automatic.overlap_candidates : [];
  const gapSummary = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(gapSummary, '長い無音候補', `${longGaps.length}件`);
  appendAnalysisMetric(gapSummary, '重なり候補', `${overlaps.length}件`);
  gapsPanel.body.append(gapSummary);
  const overlapExport = analysisExportLink('重なりCSV', 'overlaps', 'analysis-inline-export');
  if (overlapExport) gapsPanel.body.append(overlapExport);
  gapsPanel.body.append(analysisElement('p', 'analysis-caption', '沈黙・遮り・熱意などの意味は音声と文脈を確認して判断してください。'));
  grid.append(gapsPanel.panel);

  const emotionPanel = analysisCardPanel('声から推定した感情の分布', 'automatic', 'emotions');
  const emotions = Array.isArray(automatic.emotions) ? automatic.emotions : [];
  if (emotions.length) {
    emotions.slice(0, compact ? 10 : 20).forEach(item => {
      const row = analysisElement('div', 'analysis-list-row');
      const emotionLabel = [
        item.speaker_name || item.speaker,
        item.model_name || item.model || '感情モデル',
        item.label || item.emotion
      ].filter(Boolean).join(' / ');
      row.append(
        analysisElement('strong', '', emotionLabel),
        analysisElement('span', '', `${item.count || 0}件 / ${formatTime(item.seconds || 0)}`)
      );
      emotionPanel.body.append(row);
    });
  } else emotionPanel.body.append(analysisElement('p', 'analysis-no-data', '音声感情分析が未実行、または利用できる推定値がありません。'));
  emotionPanel.body.append(analysisElement('p', 'analysis-caption', 'モデル推定は本人の感情を確定するものではありません。'));
  grid.append(emotionPanel.panel);

  const groups = Array.isArray(automatic.groups) ? automatic.groups : [];
  if (groups.length) {
    const groupsPanel = analysisCardPanel('話者グループの比較', 'configured', 'groups');
    groups.forEach(item => appendAnalysisBar(
      groupsPanel.body, item.group || '未設定', item.speaking_percent,
      `${item.speaker_count || 0}人 / ${item.turn_count || 0}回 / ${formatTime(item.speaking_seconds || 0)}`,
      '#9B51E0'
    ));
    grid.append(groupsPanel.panel);
  }

  grid.append(analysisSectionHeading(
    'language', '02 / LANGUAGE STRUCTURE', '語と構文を探索する',
    '特徴語から全体像をつかみ、形態素・共起関係・文ごとの係り受けへ段階的に掘り下げます。'
  ));
  const keywordsPanel = analysisCardPanel('会話でよく使われた特徴語', 'automatic', 'keywords');
  const keywords = Array.isArray(automatic.keywords) ? automatic.keywords : [];
  const maxKeyword = Math.max(1, ...keywords.map(item => Number(item.count) || 0));
  if (keywords.length) {
    keywords.slice(0, compact ? 10 : 15).forEach(item => appendAnalysisBar(
      keywordsPanel.body, item.term, 100 * (Number(item.count) || 0) / maxKeyword, `${item.count || 0}回`, '#6C8B3C'
    ));
  } else keywordsPanel.body.append(analysisElement('p', 'analysis-no-data', '特徴語候補を抽出できませんでした。'));
  keywordsPanel.body.append(analysisElement('p', 'analysis-caption', '出現頻度による簡易候補で、研究テーマを自動決定するものではありません。'));
  grid.append(keywordsPanel.panel);

  appendResearchAnalysis(grid, compact);

  const qualityPanel = analysisCardPanel('分析に使ったデータの確認', 'automatic');
  const quality = automatic.data_quality || {};
  const qualityList = analysisElement('div', 'analysis-quality-list');
  [
    ['話者未判定の発話', `${quality.unknown_speaker_segments || 0}件`],
    ['本文が空の発話', `${quality.empty_text_segments || 0}件`],
    ['時間が0秒の発話', `${quality.zero_duration_segments || 0}件`],
    ['時刻が不正な発話', `${quality.invalid_time_segments || 0}件`],
    ['感情データ範囲', analysisNumberText(quality.emotion_coverage_percent, 1, '%')],
    ['分析から除外', `${quality.excluded_segments || 0}件`]
  ].forEach(([label, value]) => {
    const row = analysisElement('div', 'analysis-list-row');
    row.append(analysisElement('span', '', label), analysisElement('strong', '', value));
    qualityList.append(row);
  });
  qualityPanel.body.append(qualityList);
  grid.append(qualityPanel.panel);
  grid.append(analysisExportDirectory('自動分析データの出力', 'automatic', [
    ['summary', '概要 CSV'],
    ['observations', '確認候補 CSV'],
    ['speakers', '話者別発話量 CSV'],
    ['transitions', '話者遷移 CSV'],
    ['gaps', '無音候補 CSV'],
    ['overlaps', '重なり候補 CSV'],
    ['keywords', '特徴語候補 CSV'],
    ['emotions', '感情推定 CSV'],
    ['timeline', '時間推移 CSV'],
    ['groups', '属性比較 CSV']
  ]));
  fragment.append(grid);

  const cautions = Array.isArray(data.cautions) ? data.cautions : [];
  if (cautions.length) {
    const details = analysisElement('details', 'analysis-cautions');
    details.append(analysisElement('summary', '', '分析値を読むときの注意'));
    const list = analysisElement('ul');
    cautions.forEach(value => list.append(analysisElement('li', '', value)));
    details.append(list);
    fragment.append(details);
  }
  return fragment;
}

function analysisField(labelText, control, noteText = '') {
  const label = analysisElement('label', 'field analysis-field');
  label.append(analysisElement('span', '', labelText), control);
  if (noteText) label.append(analysisElement('small', '', noteText));
  return label;
}

function analysisGroupByOptions() {
  const options = {
    none: '比較しない',
    role: '会話役割',
    organization: '組織',
    department: '部署',
    job_title: '役職'
  };
  const automatic = analysisState.data && analysisState.data.automatic || {};
  const speakers = Array.isArray(automatic.speaker_metrics) ? automatic.speaker_metrics : [];
  analysisSpeakerAttributeDimensions(speakers)
    .filter(dimension => dimension.key.startsWith('custom:'))
    .forEach(dimension => {
      const key = dimension.key.slice('custom:'.length);
      options[`attribute:${key}`] = `事前アンケート：${dimension.label}`;
    });
  const current = String(analysisState.config.group_by || '');
  if (current.startsWith('attribute:') && !options[current]) {
    options[current] = `事前アンケート：${current.slice('attribute:'.length)}`;
  }
  return options;
}

function analysisConfigControl(field, type = 'text', options = null) {
  const value = analysisState.config[field];
  let control;
  if (type === 'textarea') {
    control = document.createElement('textarea');
    control.rows = field === 'research_question' || field === 'analyst_memo' ? 4 : 2;
    control.value = value || '';
  } else if (type === 'select') {
    control = document.createElement('select');
    Object.entries(options || {}).forEach(([optionValue, label]) => control.add(new Option(label, optionValue)));
    control.value = value === undefined || value === null ? '' : String(value);
  } else {
    control = document.createElement('input');
    control.type = type;
    if (type === 'checkbox') control.checked = Boolean(value);
    else control.value = value === undefined || value === null ? '' : String(value);
  }
  control.dataset.analysisConfig = field;
  return control;
}

function analysisTermCrosstabSelector(compact) {
  const container = analysisElement('div', 'analysis-term-selector');
  const selected = Array.isArray(analysisState.config.crosstab_terms)
    ? analysisState.config.crosstab_terms
    : [];
  const input = analysisConfigControl('crosstab_terms', 'text');
  input.placeholder = '例：改善, 価格, 使いやすい';
  container.append(
    analysisField(
      'クロス集計＋カイ二乗検定をする単語',
      input,
      'カンマ・読点・改行区切り。最大30語。発話ごとの「あり／なし」と統計の比較軸を集計します。'
    )
  );

  const candidates = (((analysisState.data || {}).research || {}).linguistics || {}).term_frequency || [];
  const candidateWrap = analysisElement('div', 'analysis-term-candidates');
  candidateWrap.append(analysisElement('span', '', '頻出語から選択'));
  candidates.slice(0, compact ? 16 : 30).forEach(item => {
    const term = String(item.term || '').trim();
    if (!term) return;
    const button = analysisElement('button', selected.includes(term) ? 'active' : '', term);
    button.type = 'button';
    button.dataset.analysisCrosstabTerm = term;
    button.setAttribute('aria-pressed', selected.includes(term) ? 'true' : 'false');
    candidateWrap.append(button);
  });
  if (!candidates.length) candidateWrap.append(analysisElement('small', '', '候補語は分析実行後に表示されます。'));

  const action = analysisElement('button', 'primary-button small analysis-run-term-test', '選択した単語で検定を実行');
  action.type = 'button';
  action.dataset.analysisRunTermCrosstab = 'true';
  container.append(candidateWrap, action);
  return container;
}

function analysisCodebookEditor(compact) {
  const container = analysisElement('div', 'analysis-codebook');
  const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
  if (!codebook.length) {
    container.append(analysisElement('p', 'analysis-no-data', 'コードはまだありません。研究質問に沿ってコード名と定義を追加してください。'));
  }
  codebook.forEach((code, index) => {
    const card = analysisElement(compact ? 'details' : 'article', 'analysis-code-card');
    if (compact) {
      const summary = analysisElement('summary');
      const swatch = analysisElement('i');
      swatch.style.backgroundColor = safeAnalysisColor(code.color, speakerThemeColors[index % speakerThemeColors.length]);
      summary.append(swatch, analysisElement('strong', '', code.label || `コード ${index + 1}`));
      card.append(summary);
    }
    const body = analysisElement('div', 'analysis-code-body');
    const top = analysisElement('div', 'analysis-code-top');
    const color = document.createElement('input');
    color.type = 'color';
    color.value = safeAnalysisColor(code.color, speakerThemeColors[index % speakerThemeColors.length]);
    color.dataset.analysisCodeId = code.id;
    color.dataset.analysisCodeField = 'color';
    color.setAttribute('aria-label', `${code.label || `コード ${index + 1}`}の色`);
    const label = document.createElement('input');
    label.type = 'text';
    label.maxLength = 120;
    label.value = code.label || '';
    label.placeholder = 'コード名';
    label.dataset.analysisCodeId = code.id;
    label.dataset.analysisCodeField = 'label';
    const remove = analysisElement('button', 'analysis-remove-code', '削除');
    remove.type = 'button';
    remove.dataset.analysisRemoveCode = code.id;
    remove.setAttribute('aria-label', `${code.label || `コード ${index + 1}`}を削除`);
    top.append(color, label, remove);
    body.append(top);
    [
      ['description', '定義', 'このコードに含める意味・判断基準'],
      ['include_example', '含める例', '該当する発話の例'],
      ['exclude_example', '含めない例', '似ているが除外する発話の例']
    ].forEach(([field, caption, placeholder]) => {
      const textarea = document.createElement('textarea');
      textarea.rows = field === 'description' ? 3 : 2;
      textarea.maxLength = field === 'description' ? 4000 : 2000;
      textarea.value = code[field] || '';
      textarea.placeholder = placeholder;
      textarea.dataset.analysisCodeId = code.id;
      textarea.dataset.analysisCodeField = field;
      body.append(analysisField(caption, textarea));
    });
    card.append(body);
    container.append(card);
  });
  const add = analysisElement('button', 'secondary-button analysis-add-code', '＋ コードを追加');
  add.type = 'button';
  add.dataset.analysisAddCode = 'true';
  container.append(add);
  return container;
}

function analysisAnnotation(segmentId) {
  if (!analysisState.annotations[segmentId] || typeof analysisState.annotations[segmentId] !== 'object') {
    analysisState.annotations[segmentId] = {
      codes: [], interaction_tags: [], memo: '', important: false, excluded: false
    };
  }
  return analysisState.annotations[segmentId];
}

function analysisSegmentMatches(segment) {
  const query = analysisState.segmentQuery.trim().toLocaleLowerCase();
  const annotation = analysisState.annotations[segment.id] || {};
  const annotated = Boolean(
    (annotation.codes || []).length
    || (annotation.interaction_tags || []).length
    || annotation.memo
    || annotation.important
    || annotation.excluded
  );
  if (analysisState.annotatedOnly && !annotated) return false;
  if (!query) return true;
  return `${segment.speaker_name || ''} ${segment.speaker || ''} ${segment.text || ''}`
    .toLocaleLowerCase().includes(query);
}

function renderAnalysisSegmentItems(list, compact) {
  list.replaceChildren();
  const segments = Array.isArray(analysisState.data.segments) ? analysisState.data.segments : [];
  const visible = segments.filter(analysisSegmentMatches);
  const limit = compact ? 100 : 200;
  const count = analysisElement('p', 'analysis-segment-count', `表示 ${Math.min(visible.length, limit)} / 該当 ${visible.length} / 全 ${segments.length}発話`);
  list.append(count);
  if (!visible.length) {
    list.append(analysisElement('p', 'analysis-no-data', '条件に一致する発話がありません。'));
    return;
  }
  const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
  const interactionTags = ((analysisState.data.manual || {}).interaction_tags || []);
  visible.slice(0, limit).forEach(segment => {
    const annotation = analysisState.annotations[segment.id] || {
      codes: [], interaction_tags: [], memo: '', important: false, excluded: false
    };
    const card = analysisElement('article', 'analysis-segment-card');
    card.dataset.analysisSegmentCard = segment.id;
    const header = analysisElement('header');
    const meta = analysisElement('div');
    const speaker = analysisElement('strong', '', segment.speaker_name || segment.speaker || '話者未判定');
    speaker.style.borderColor = safeAnalysisColor(segment.color);
    meta.append(
      analysisElement('span', 'analysis-segment-time', `${formatTime(segment.start || 0)}–${formatTime(segment.end || 0)}`),
      speaker
    );
    const status = analysisElement('div', 'analysis-segment-status');
    if (annotation.important) status.append(analysisElement('span', 'important', '重要引用'));
    if (annotation.excluded) status.append(analysisElement('span', 'excluded', '分析除外'));
    header.append(meta, status);
    const quote = analysisElement('p', 'analysis-segment-text', segment.text || '（本文なし）');
    card.append(header, quote);

    const codeGroup = analysisElement('fieldset', 'analysis-chip-group');
    codeGroup.append(analysisElement('legend', '', 'テーマコード'));
    if (!codebook.length) codeGroup.append(analysisElement('p', 'analysis-inline-note', '先にコードブックへコードを追加してください。'));
    codebook.forEach(code => {
      const label = analysisElement('label', 'analysis-code-chip');
      label.style.setProperty('--code-color', safeAnalysisColor(code.color));
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = (annotation.codes || []).includes(code.id);
      input.dataset.analysisSegmentId = segment.id;
      input.dataset.analysisAnnotationField = 'codes';
      input.dataset.analysisAnnotationValue = code.id;
      label.append(input, analysisElement('span', '', code.label));
      codeGroup.append(label);
    });
    card.append(codeGroup);

    const interactionGroup = analysisElement('details', 'analysis-interaction-group');
    interactionGroup.append(analysisElement('summary', '', '相互作用タグを確認・設定'));
    const chips = analysisElement('div', 'analysis-chip-group inline');
    interactionTags.forEach(tag => {
      const label = analysisElement('label', 'analysis-interaction-chip');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = (annotation.interaction_tags || []).includes(tag.id);
      input.dataset.analysisSegmentId = segment.id;
      input.dataset.analysisAnnotationField = 'interaction_tags';
      input.dataset.analysisAnnotationValue = tag.id;
      label.append(input, analysisElement('span', '', tag.label));
      chips.append(label);
    });
    interactionGroup.append(chips);
    card.append(interactionGroup);

    const flags = analysisElement('div', 'analysis-annotation-flags');
    [
      ['important', '重要引用として残す'],
      ['excluded', 'この発話を自動集計から除外']
    ].forEach(([field, labelText]) => {
      const label = analysisElement('label');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = Boolean(annotation[field]);
      input.dataset.analysisSegmentId = segment.id;
      input.dataset.analysisAnnotationField = field;
      label.append(input, analysisElement('span', '', labelText));
      flags.append(label);
    });
    card.append(flags);
    const memo = document.createElement('textarea');
    memo.rows = compact ? 2 : 3;
    memo.maxLength = 5000;
    memo.value = annotation.memo || '';
    memo.placeholder = 'この発話の意味、文脈、例外、解釈メモ';
    memo.dataset.analysisSegmentId = segment.id;
    memo.dataset.analysisAnnotationField = 'memo';
    card.append(analysisField('発話メモ', memo));
    list.append(card);
  });
  if (visible.length > limit) {
    list.append(analysisElement('p', 'analysis-limit-note', `表示負荷を抑えるため先頭${limit}件を表示しています。検索で対象を絞り込んでください。`));
  }
}

function analysisCodingWorkspace(compact) {
  const container = analysisElement('div', 'analysis-coding-workspace');
  const toolbar = analysisElement('div', 'analysis-coding-toolbar');
  const search = document.createElement('input');
  search.type = 'search';
  search.value = analysisState.segmentQuery;
  search.placeholder = '発話本文・話者を検索';
  search.dataset.analysisSegmentQuery = 'true';
  const annotatedLabel = analysisElement('label', 'mini-check');
  const annotated = document.createElement('input');
  annotated.type = 'checkbox';
  annotated.checked = analysisState.annotatedOnly;
  annotated.dataset.analysisAnnotatedOnly = 'true';
  annotatedLabel.append(annotated, analysisElement('span', '', '設定済みだけ'));
  toolbar.append(analysisField('発話を検索', search), annotatedLabel);
  const list = analysisElement('div', 'analysis-segment-list');
  list.dataset.analysisSegmentList = compact ? 'mobile' : 'desktop';
  renderAnalysisSegmentItems(list, compact);
  container.append(toolbar, list);
  return container;
}

function renderManualSummary(container, compact) {
  const manual = analysisState.data.manual || {};
  const checks = Array.isArray(manual.context_checks) ? manual.context_checks : [];
  const readiness = analysisCardPanel('分析前の確認', 'configured', 'context');
  const checkGrid = analysisElement('div', 'analysis-check-grid');
  checks.forEach(item => {
    const row = analysisElement('div', item.ready ? 'ready' : 'missing');
    row.append(
      analysisElement('span', '', item.ready ? '✓' : '!'),
      analysisElement('strong', '', item.label),
      analysisElement('small', '', item.ready ? '設定済み' : '要設定')
    );
    checkGrid.append(row);
  });
  readiness.body.append(checkGrid);
  container.append(readiness.panel);

  const codeMetrics = Array.isArray(manual.code_metrics) ? manual.code_metrics : [];
  const interactionSummary = Array.isArray(manual.interaction_summary) ? manual.interaction_summary : [];
  if (codeMetrics.length || interactionSummary.some(item => item.count)) {
    const summary = analysisCardPanel('手動コードの集計', 'manual', 'codes', true);
    if (codeMetrics.length) {
      codeMetrics.forEach(item => appendAnalysisBar(
        summary.body,
        item.label,
        Math.min(100, Number(item.segment_count || 0) * 10),
        `${item.segment_count || 0}発話 / ${item.speaker_count || 0}人 / 重要引用 ${item.important_count || 0}件`,
        item.color
      ));
    }
    const tags = analysisElement('div', 'analysis-interaction-summary');
    interactionSummary.filter(item => item.count).forEach(item => {
      const chip = analysisElement('span', '', `${item.label} ${item.count}件`);
      tags.append(chip);
    });
    if (tags.childNodes.length) summary.body.append(tags);
    container.append(summary.panel);
  }

  const matrix = Array.isArray(manual.case_code_matrix) ? manual.case_code_matrix : [];
  const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
  if (matrix.length && codebook.length && !compact) {
    const matrixPanel = analysisCardPanel('話者×テーマコード', 'manual', 'case_matrix', true);
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table analysis-matrix');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    headRow.append(analysisElement('th', '', '話者'));
    codebook.forEach(code => headRow.append(analysisElement('th', '', code.label)));
    head.append(headRow);
    const body = analysisElement('tbody');
    matrix.forEach(rowData => {
      const row = analysisElement('tr');
      row.append(analysisElement('th', '', rowData.speaker_name || rowData.speaker));
      const counts = new Map((rowData.codes || []).map(item => [item.code_id, item.count]));
      codebook.forEach(code => {
        const value = Number(counts.get(code.id)) || 0;
        const cell = analysisElement('td', value ? 'has-value' : '', value);
        cell.style.setProperty('--matrix-strength', String(Math.min(1, value / 5)));
        row.append(cell);
      });
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    matrixPanel.body.append(wrap);
    container.append(matrixPanel.panel);
  }
}

function renderManualAnalysis(compact) {
  const fragment = document.createDocumentFragment();
  const manual = (analysisState.data && analysisState.data.manual) || {};
  const intro = analysisElement('div', 'analysis-result-intro manual');
  intro.append(
    analysisElement('span', 'analysis-kind manual', '要設定・要確認'),
    analysisElement('h2', '', compact ? '設定・手動分析' : '研究目的に沿った設定と手動コーディング'),
    analysisElement('p', '', 'テーマ、合意・対立、沈黙の意味は自動確定できません。定義を作り、発話を読み、根拠と解釈を保存してください。')
  );
  fragment.append(intro);
  const orphanedCount = Number(manual.orphaned_annotation_count) || 0;
  if (orphanedCount > 0) {
    const warning = analysisElement('div', 'analysis-orphan-warning');
    warning.setAttribute('role', 'status');
    warning.append(
      analysisElement('strong', '', '参照先のない注釈があります'),
      analysisElement('p', '', `文字起こし編集で参照先がなくなった注釈が${orphanedCount}件あります。JSONには復旧用に保持されています。`)
    );
    fragment.append(warning);
  }

  const summaryGrid = analysisElement('div', 'analysis-grid manual-summary-grid');
  renderManualSummary(summaryGrid, compact);
  const importantQuotes = (analysisState.data.segments || []).filter(segment => {
    const annotation = analysisState.annotations[segment.id] || {};
    return annotation.important && !annotation.excluded;
  });
  if (importantQuotes.length) {
    const quotesPanel = analysisCardPanel('重要引用', 'manual', 'important_quotes', true);
    importantQuotes.slice(0, compact ? 5 : 12).forEach(segment => {
      const quote = analysisElement('blockquote', 'analysis-important-quote');
      quote.append(
        analysisElement('p', '', segment.text || '（本文なし）'),
        analysisElement('footer', '', `${segment.speaker_name || segment.speaker} / ${formatTime(segment.start || 0)}–${formatTime(segment.end || 0)}`)
      );
      quotesPanel.body.append(quote);
    });
    summaryGrid.append(quotesPanel.panel);
  }
  summaryGrid.append(analysisExportDirectory('手動分析データの出力', 'manual', [
    ['context', '入力・確認状況 CSV'],
    ['codes', 'コード集計 CSV'],
    ['coded_segments', 'コード済み発話 CSV'],
    ['interactions', '相互作用タグ CSV'],
    ['case_matrix', '話者×コード CSV'],
    ['important_quotes', '重要引用 CSV']
  ]));
  fragment.append(summaryGrid);

  const settingsPanel = analysisCardPanel('分析条件', 'configured', '', true);
  const settingsGrid = analysisElement('div', 'analysis-settings-grid');
  settingsGrid.append(
    analysisField('研究質問', analysisConfigControl('research_question', 'textarea'), '分析で明らかにしたい問いを記録します。'),
    analysisField('分析単位', analysisConfigControl('analysis_unit', 'select', {
      turn: '発話単位'
    })),
    analysisField(
      '比較軸',
      analysisConfigControl('group_by', 'select', analysisGroupByOptions()),
      '話者管理とリンク済みの事前アンケート項目も回答群ごとの比較に使えます。'
    ),
    analysisField('長い無音の基準（秒）', analysisConfigControl('long_gap_seconds', 'number')),
    analysisField('重なり候補の基準（秒）', analysisConfigControl('overlap_seconds', 'number')),
    analysisField('低参加候補の基準（%）', analysisConfigControl('low_participation_percent', 'number')),
    analysisField('時間帯の幅（秒）', analysisConfigControl('time_bin_seconds', 'number')),
    analysisField('特徴語から除外する語', analysisConfigControl('stop_words', 'text'), 'カンマ区切りで入力します。'),
    analysisField('Sudachi分割単位', analysisConfigControl('morph_split_mode', 'select', {
      A: 'A（短単位）', B: 'B（中間）', C: 'C（長単位・既定）'
    }), 'GiNZA利用時はモデル側の設定を記録します。'),
    analysisField('共起の最小発話数', analysisConfigControl('cooccurrence_min_count', 'number')),
    analysisField('共起へ使う上位語数', analysisConfigControl('cooccurrence_top_terms', 'number')),
    analysisField('統計の比較軸', analysisConfigControl('statistics_group_by', 'select', {
      speaker: '話者', role: '会話役割'
    }), '同一会話内の発話は独立でない可能性があります。')
  );
  const excludeModerator = analysisElement('label', 'check-row analysis-setting-check');
  excludeModerator.append(
    analysisConfigControl('exclude_moderator', 'checkbox'),
    analysisElement('span', '', '参加バランスから司会・観察役を除外する')
  );
  settingsGrid.append(excludeModerator);
  settingsPanel.body.append(settingsGrid, analysisTermCrosstabSelector(compact));

  const speakerExclusions = analysisElement('fieldset', 'analysis-speaker-exclusions');
  speakerExclusions.append(analysisElement('legend', '', '分析から除外する話者'));
  const uniqueSpeakers = new Map();
  (analysisState.data.segments || []).forEach(segment => {
    if (!uniqueSpeakers.has(segment.speaker)) uniqueSpeakers.set(segment.speaker, segment.speaker_name || segment.speaker);
  });
  uniqueSpeakers.forEach((name, speaker) => {
    const label = analysisElement('label');
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = (analysisState.config.excluded_speakers || []).includes(speaker);
    input.dataset.analysisExcludedSpeaker = speaker;
    label.append(input, analysisElement('span', '', name));
    speakerExclusions.append(label);
  });
  settingsPanel.body.append(speakerExclusions);
  fragment.append(settingsPanel.panel);

  const codebookPanel = analysisCardPanel('コードブック', 'configured', '', true);
  codebookPanel.body.append(
    analysisElement('p', 'analysis-section-help', 'コードの意味と含む／含まない例を先に定義すると、複数人でも判断を揃えやすくなります。'),
    analysisCodebookEditor(compact)
  );
  fragment.append(codebookPanel.panel);

  const codingPanel = analysisCardPanel('発話ごとのコード・相互作用・メモ', 'manual', 'coded_segments', true);
  codingPanel.body.append(
    analysisElement('p', 'analysis-section-help', 'タグは観察記録です。合意や発言抑制などの意味は、前後の発話や音声を確認して設定してください。'),
    analysisCodingWorkspace(compact)
  );
  fragment.append(codingPanel.panel);

  const interpretationPanel = analysisCardPanel('研究者の解釈', 'manual', '', true);
  const interpretationGrid = analysisElement('div', 'analysis-interpretation-grid');
  interpretationGrid.append(
    analysisField('分析メモ', analysisConfigControl('analyst_memo', 'textarea'), 'テーマ、例外事例、少数意見、次に確認する点を記録します。'),
    analysisField('確認状態', analysisConfigControl('interpretation_status', 'select', {
      draft: '下書き・要確認', reviewed: '確認済み'
    }))
  );
  interpretationPanel.body.append(interpretationGrid);
  fragment.append(interpretationPanel.panel);

  const saveBar = analysisElement('div', 'analysis-save-bar');
  const saveText = analysisElement('div');
  saveText.append(
    analysisElement('strong', '', analysisState.dirty ? '未保存の変更があります' : '分析設定は保存済みです'),
    analysisElement('span', '', '保存すると自動集計とExcel・CSV・JSONも更新されます。')
  );
  saveText.firstElementChild.dataset.analysisSaveState = 'true';
  const save = analysisElement('button', 'primary-button small', analysisState.dirty ? '設定とコードを保存' : '保存済み');
  save.type = 'button';
  save.dataset.analysisSave = 'true';
  save.disabled = !analysisState.dirty;
  saveBar.append(saveText, save);
  fragment.append(saveBar);
  return fragment;
}

function syncAnalysisControls(source, selector, predicate) {
  document.querySelectorAll(selector).forEach(control => {
    if (control === source || !predicate(control)) return;
    if (source.type === 'checkbox') control.checked = source.checked;
    else control.value = source.value;
  });
}

function updateAnalysisConfigFromControl(control) {
  const field = control.dataset.analysisConfig;
  if (!field) return false;
  let value;
  if (control.type === 'checkbox') value = control.checked;
  else if (control.type === 'number') {
    const number = Number(control.value);
    value = Number.isFinite(number) ? number : analysisState.config[field];
  } else if (field === 'stop_words' || field === 'crosstab_terms') {
    value = control.value.split(/[,、\n]/).map(item => item.trim()).filter(Boolean);
  } else value = control.value;
  analysisState.config[field] = value;
  syncAnalysisControls(control, '[data-analysis-config]', peer => peer.dataset.analysisConfig === field);
  setAnalysisDirty(true);
  return true;
}

function updateAnalysisCodeFromControl(control) {
  const codeId = control.dataset.analysisCodeId;
  const field = control.dataset.analysisCodeField;
  if (!codeId || !field) return false;
  const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
  const code = codebook.find(item => item.id === codeId);
  if (!code) return false;
  code[field] = field === 'color' ? safeAnalysisColor(control.value) : control.value;
  syncAnalysisControls(control, '[data-analysis-code-id]', peer => (
    peer.dataset.analysisCodeId === codeId && peer.dataset.analysisCodeField === field
  ));
  setAnalysisDirty(true);
  return true;
}

function updateAnalysisAnnotationFromControl(control) {
  const segmentId = control.dataset.analysisSegmentId;
  const field = control.dataset.analysisAnnotationField;
  if (!segmentId || !field) return false;
  const annotation = analysisAnnotation(segmentId);
  const itemValue = control.dataset.analysisAnnotationValue;
  if (field === 'codes' || field === 'interaction_tags') {
    const values = Array.isArray(annotation[field]) ? annotation[field] : [];
    annotation[field] = control.checked
      ? [...new Set([...values, itemValue])]
      : values.filter(value => value !== itemValue);
  } else if (field === 'important' || field === 'excluded') annotation[field] = control.checked;
  else annotation[field] = control.value;
  syncAnalysisControls(control, '[data-analysis-annotation-field]', peer => (
    peer.dataset.analysisSegmentId === segmentId
    && peer.dataset.analysisAnnotationField === field
    && peer.dataset.analysisAnnotationValue === itemValue
  ));
  setAnalysisDirty(true);
  return true;
}

function refreshAnalysisSegmentLists() {
  document.querySelectorAll('[data-analysis-segment-list]').forEach(list => {
    renderAnalysisSegmentItems(list, list.dataset.analysisSegmentList === 'mobile');
  });
}

async function saveAnalysis() {
  if (!analysisState.itemId || !analysisState.data || analysisSaveInProgress) return;
  analysisSaveInProgress = true;
  setAnalysisDirty(true, false);
  setAlert(document.querySelector('#analysis-message'), '');
  const savedItemId = analysisState.itemId;
  const saveGeneration = analysisMutationGeneration;
  try {
    const item = analysisState.data.item || {};
    const response = await apiFetch(`/api/library/${encodeURIComponent(savedItemId)}/analysis`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        source_revision: Number(item.revision_count || 0),
        analysis_revision: Number(item.analysis_revision || 0),
        config: analysisState.config,
        annotations: analysisState.annotations
      })
    });
    const payload = await readJsonResponse(response);
    if (!response.ok) throw new Error(payload.error || '分析設定を保存できませんでした。');
    const data = payload.analysis && typeof payload.analysis === 'object' ? payload.analysis : payload;
    analysisSaveInProgress = false;
    const hasLaterChanges = analysisState.itemId === savedItemId
      && analysisMutationGeneration !== saveGeneration;
    if (analysisState.itemId === savedItemId && !hasLaterChanges) {
      analysisState.data = data;
      analysisState.config = deepCopy(data.config || {});
      analysisState.annotations = deepCopy(data.annotations || {});
      if (analysisTermRunRequested) analysisState.mode = 'automatic';
      analysisTermRunRequested = false;
      setAnalysisDirty(false);
      renderAnalysisWorkspace();
      setAlert(document.querySelector('#analysis-message'), '分析設定、手動コード、解釈メモを保存し、集計と出力データを更新しました。');
    } else if (analysisState.itemId === savedItemId) {
      if (analysisState.data && analysisState.data.item && data.item) {
        analysisState.data.item.revision_count = data.item.revision_count;
        analysisState.data.item.analysis_revision = data.item.analysis_revision;
        analysisState.data.item.analysis_updated_at = data.item.analysis_updated_at;
      }
      setAnalysisDirty(true, false);
      setAlert(document.querySelector('#analysis-message'), '保存開始後の追加変更が残っています。内容を確認して、もう一度保存してください。', true);
    }
  } catch (error) {
    analysisSaveInProgress = false;
    analysisTermRunRequested = false;
    setAnalysisDirty(true, false);
    setAlert(document.querySelector('#analysis-message'), error.message, true);
  }
}

listen(analysisItemSelect, 'change', () => loadAnalysisItem(analysisItemSelect.value));
listen(document.querySelector('#analysis-refresh-button'), 'click', () => {
  if (!analysisState.itemId) return;
  if (analysisState.dirty && !window.confirm('未保存の分析設定と手動コードを破棄して再集計しますか？')) return;
  loadAnalysisItem(analysisState.itemId, {discardDirty: true});
});

listen(analysisCard, 'click', event => {
  const scope = event.target.closest('[data-analysis-scope]');
  if (scope) {
    analysisState.automaticScope = scope.dataset.analysisScope === 'speakers' ? 'speakers' : 'overall';
    renderAnalysisWorkspace();
    return;
  }
  const selectedSpeaker = event.target.closest('[data-analysis-speaker-id]');
  if (selectedSpeaker) {
    analysisState.selectedSpeaker = selectedSpeaker.dataset.analysisSpeakerId || '';
    const mobile = window.matchMedia('(max-width: 959px)').matches;
    renderAnalysisWorkspace();
    if (mobile) {
      window.requestAnimationFrame(() => {
        const detail = analysisCard.querySelector('.analysis-mobile-layout .analysis-speaker-detail');
        if (!detail) return;
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        detail.scrollIntoView({behavior: reducedMotion ? 'auto' : 'smooth', block: 'start'});
      });
    }
    return;
  }
  const jump = event.target.closest('[data-analysis-jump]');
  if (jump) {
    const content = jump.closest('.analysis-content');
    const target = content && content.querySelector(`[data-analysis-anchor="${jump.dataset.analysisJump}"]`);
    if (target) {
      content.querySelectorAll('[data-analysis-jump]').forEach(button => {
        const active = button === jump;
        button.classList.toggle('active', active);
        button.setAttribute('aria-current', active ? 'true' : 'false');
      });
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      target.scrollIntoView({behavior: reducedMotion ? 'auto' : 'smooth', block: 'start'});
    }
    return;
  }
  const mode = event.target.closest('[data-analysis-mode]');
  if (mode) {
    setAnalysisMode(mode.dataset.analysisMode);
    return;
  }
  const save = event.target.closest('[data-analysis-save]');
  if (save) {
    saveAnalysis();
    return;
  }
  const runTermCrosstab = event.target.closest('[data-analysis-run-term-crosstab]');
  if (runTermCrosstab) {
    const terms = Array.isArray(analysisState.config.crosstab_terms) ? analysisState.config.crosstab_terms : [];
    if (!terms.length) {
      setAlert(document.querySelector('#analysis-message'), '検定する単語を1つ以上入力または選択してください。', true);
      return;
    }
    analysisTermRunRequested = true;
    saveAnalysis();
    return;
  }
  const termChoice = event.target.closest('[data-analysis-crosstab-term]');
  if (termChoice) {
    const term = String(termChoice.dataset.analysisCrosstabTerm || '').trim();
    const selected = new Set(Array.isArray(analysisState.config.crosstab_terms) ? analysisState.config.crosstab_terms : []);
    if (selected.has(term)) selected.delete(term);
    else if (selected.size < 30) selected.add(term);
    analysisState.config.crosstab_terms = [...selected];
    setAnalysisDirty(true);
    renderAnalysisWorkspace();
    return;
  }
  const addCode = event.target.closest('[data-analysis-add-code]');
  if (addCode) {
    const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
    const id = self.crypto && self.crypto.randomUUID
      ? `code_${self.crypto.randomUUID().replaceAll('-', '').slice(0, 16)}`
      : `code_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
    codebook.push({
      id,
      label: `新しいコード ${codebook.length + 1}`,
      description: '', include_example: '', exclude_example: '',
      color: speakerThemeColors[codebook.length % speakerThemeColors.length]
    });
    analysisState.config.codebook = codebook;
    setAnalysisDirty(true);
    renderAnalysisWorkspace();
    const target = analysisCard.querySelector(`[data-analysis-code-id="${id}"][data-analysis-code-field="label"]`);
    if (target) {
      target.focus();
      target.select();
    }
    return;
  }
  const removeCode = event.target.closest('[data-analysis-remove-code]');
  if (removeCode) {
    const codeId = removeCode.dataset.analysisRemoveCode;
    const code = (analysisState.config.codebook || []).find(item => item.id === codeId);
    const applied = Object.values(analysisState.annotations).some(item => (item.codes || []).includes(codeId));
    if (applied && !window.confirm(`「${code ? code.label : 'このコード'}」と発話への付与を削除しますか？`)) return;
    analysisState.config.codebook = (analysisState.config.codebook || []).filter(item => item.id !== codeId);
    Object.values(analysisState.annotations).forEach(item => {
      item.codes = (item.codes || []).filter(value => value !== codeId);
    });
    setAnalysisDirty(true);
    renderAnalysisWorkspace();
  }
});

listen(analysisCard, 'input', event => {
  const control = event.target;
  if (updateAnalysisConfigFromControl(control)) return;
  if (updateAnalysisCodeFromControl(control)) return;
  if (updateAnalysisAnnotationFromControl(control)) return;
  if (control.dataset.analysisSegmentQuery !== undefined) {
    analysisState.segmentQuery = control.value;
    syncAnalysisControls(control, '[data-analysis-segment-query]', () => true);
    refreshAnalysisSegmentLists();
    return;
  }
  if (control.dataset.analysisAnnotatedOnly !== undefined) {
    analysisState.annotatedOnly = control.checked;
    syncAnalysisControls(control, '[data-analysis-annotated-only]', () => true);
    refreshAnalysisSegmentLists();
    return;
  }
  const speaker = control.dataset.analysisExcludedSpeaker;
  if (speaker !== undefined) {
    const excluded = new Set(analysisState.config.excluded_speakers || []);
    if (control.checked) excluded.add(speaker); else excluded.delete(speaker);
    analysisState.config.excluded_speakers = [...excluded];
    syncAnalysisControls(control, '[data-analysis-excluded-speaker]', peer => peer.dataset.analysisExcludedSpeaker === speaker);
    setAnalysisDirty(true);
  }
});

window.addEventListener('scroll', scheduleAnalysisNavigationSync, {passive: true});
window.addEventListener('resize', scheduleAnalysisNavigationSync, {passive: true});

const requestedParameters = new URLSearchParams(window.location.search);
const requestedView = requestedParameters.get('view');
const requestedSectionValue = requestedParameters.get('section');
const requestedAnalysisSection = ['overview', 'conversation', 'language', 'statistics', 'exports'].includes(requestedSectionValue)
  ? requestedSectionValue : '';
showView(['new', 'library', 'speakers', 'analysis'].includes(requestedView) ? requestedView : 'new');
