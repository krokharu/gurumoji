const form = document.querySelector('#job-form');
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
const showLibraryButton = document.querySelector('#show-library-button');
const showNewButton = document.querySelector('#show-new-button');
const showSpeakersButton = document.querySelector('#show-speakers-button');
const showAnalysisButton = document.querySelector('#show-analysis-button');
const segmentEditor = document.querySelector('#segment-editor');
const speakerEditor = document.querySelector('#speaker-editor');
const mediaReview = document.querySelector('#media-review');
const mediaPlayerHost = document.querySelector('#media-player-host');
const bootSplash = document.querySelector('#boot-splash');
const aiOptionInputs = [cleanTranscript, detectNames, createOutline].filter(Boolean);

let currentJobId = null;
let currentJob = null;
let pollTimer = null;
let mediaPlayer = null;
let selectedSegmentId = null;
let playbackStopAt = null;
let libraryTimer = null;
let thumbnailTimer = null;
let thumbnailRequestId = 0;
let jobRunning = false;
let currentMobileStep = 1;
let speakerRegistry = [];
let speakerRegistryDeletedIds = new Set();
let speakerRegistryLoaded = false;
let speakerRegistryDirty = false;
let libraryRequestController = null;
let libraryRequestSequence = 0;
let trainingStatusLoaded = false;
let analysisCatalogLoaded = false;
let analysisCatalog = [];
let analysisRequestController = null;
let analysisRequestSequence = 0;
let analysisSaveInProgress = false;
const analysisState = {
  itemId: '',
  mode: 'automatic',
  data: null,
  config: {},
  annotations: {},
  dirty: false,
  segmentQuery: '',
  annotatedOnly: false
};
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
startBootSequence();

function startBootSequence() {
  if (!bootSplash) {
    document.body.classList.remove('booting');
    return;
  }
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.setTimeout(() => {
    bootSplash.classList.add('is-leaving');
    document.body.classList.remove('booting');
    window.setTimeout(() => {
      bootSplash.hidden = true;
      bootSplash.setAttribute('aria-hidden', 'true');
    }, reducedMotion ? 50 : 720);
  }, reducedMotion ? 120 : 1700);
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

function deepCopy(value) {
  return JSON.parse(JSON.stringify(value));
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

function showSourceThumbnail(path, name = '') {
  if (!sourcePreview || !sourceThumbnail || !sourcePreviewMessage) return;
  const value = String(path || '').trim();
  if (!isVideoSource(value)) {
    hideSourcePreview();
    return;
  }
  const requestId = ++thumbnailRequestId;
  sourcePreview.hidden = false;
  sourcePreview.classList.remove('loaded');
  sourceThumbnail.hidden = true;
  sourcePreviewMessage.textContent = `${name || value.split(/[\\/]/).pop()} のサムネイルを作成しています…`;
  sourceThumbnail.onload = () => {
    if (requestId !== thumbnailRequestId) return;
    sourcePreview.classList.add('loaded');
    sourceThumbnail.hidden = false;
    sourcePreviewMessage.textContent = name || value;
  };
  sourceThumbnail.onerror = () => {
    if (requestId !== thumbnailRequestId) return;
    sourcePreview.classList.remove('loaded');
    sourceThumbnail.hidden = true;
    sourcePreviewMessage.textContent = 'サムネイルを作成できませんでした。動画として開けるファイルか確認してください。';
  };
  sourceThumbnail.src = `/api/source-thumbnail?path=${encodeURIComponent(value)}&_=${Date.now()}`;
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

function showView(view) {
  const leavingSpeakerManagement = view !== 'speakers'
    && speakerRegistryCard
    && !speakerRegistryCard.hidden
    && speakerRegistryDirty;
  if (leavingSpeakerManagement && !window.confirm('話者管理に未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  const leavingAnalysis = view !== 'analysis'
    && analysisCard
    && !analysisCard.hidden
    && analysisState.dirty;
  if (leavingAnalysis && !window.confirm('分析設定または手動コードに未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  const library = view === 'library';
  const create = view === 'new';
  const speakers = view === 'speakers';
  const analysis = view === 'analysis';
  if (libraryCard) libraryCard.hidden = !library;
  if (speakerRegistryCard) speakerRegistryCard.hidden = !speakers;
  if (analysisCard) analysisCard.hidden = !analysis;
  if (form) form.hidden = !create;
  if (library || create || speakers || analysis) {
    if (mediaPlayer) mediaPlayer.pause();
    if (resultCard) resultCard.hidden = true;
    if (progressCard && (!currentJobId || !pollTimer)) progressCard.hidden = true;
  }
  if (showLibraryButton) showLibraryButton.classList.toggle('active', library);
  if (showNewButton) showNewButton.classList.toggle('active', create);
  if (showSpeakersButton) showSpeakersButton.classList.toggle('active', speakers);
  if (showAnalysisButton) showAnalysisButton.classList.toggle('active', analysis);
  if (showLibraryButton) showLibraryButton.setAttribute('aria-selected', String(library));
  if (showNewButton) showNewButton.setAttribute('aria-selected', String(create));
  if (showSpeakersButton) showSpeakersButton.setAttribute('aria-selected', String(speakers));
  if (showAnalysisButton) showAnalysisButton.setAttribute('aria-selected', String(analysis));
  if (library && libraryCard) loadLibrary();
  if (speakers && speakerRegistryCard) loadSpeakerRegistry();
  if (analysis && analysisCard) loadAnalysisCatalog();
  if (create) renderMobileWizard();
  return true;
}

listen(showLibraryButton, 'click', () => showView('library'));
listen(showNewButton, 'click', () => showView('new'));
listen(showSpeakersButton, 'click', () => showView('speakers'));
listen(showAnalysisButton, 'click', () => showView('analysis'));

window.addEventListener('beforeunload', event => {
  if (!speakerRegistryDirty && !analysisState.dirty) return;
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
    consent_status: 'unknown',
    recording_consent: 'unknown',
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

function setSpeakerRegistryDirty(dirty = true) {
  speakerRegistryDirty = dirty;
  const metric = document.querySelector('#registry-dirty-metric');
  if (metric) {
    metric.textContent = dirty ? '未保存' : '保存済み';
    metric.classList.toggle('unsaved', dirty);
  }
  if (speakerRegistrySaveState) {
    speakerRegistrySaveState.textContent = dirty ? '未保存の変更があります' : '保存済み';
    speakerRegistrySaveState.classList.toggle('unsaved', dirty);
  }
  if (speakerRegistrySaveButton) speakerRegistrySaveButton.disabled = !dirty;
  if (speakerRegistryCard) speakerRegistryCard.classList.toggle('has-unsaved', dirty);
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
    const response = await fetch('/api/speakers', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '話者管理データを取得できませんでした。');
    speakerRegistry = Array.isArray(data.speakers) ? data.speakers : [];
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
  const consented = active.filter(record => (
    record.consent_status === 'granted' && record.recording_consent === 'granted'
  ));
  const values = {
    '#registry-total-metric': speakerRegistry.length,
    '#registry-active-metric': active.length,
    '#registry-consent-metric': consented.length
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
  attributes.placeholder = '年齢層=30代; 性別=女性';
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
    cell.colSpan = 15;
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
    appendSheetCell(row, makeSheetSelect(record, 'consent_status', consentLabels, {label: `${speakerRecordName(record)}の研究同意`, afterChange: updateSpeakerRegistryOverview}));
    appendSheetCell(row, makeSheetSelect(record, 'recording_consent', consentLabels, {label: `${speakerRecordName(record)}の録音同意`, afterChange: updateSpeakerRegistryOverview}));
    appendSheetCell(row, makeSheetSelect(record, 'confidentiality_status', consentLabels, {label: `${speakerRecordName(record)}の守秘同意`}));
    appendSheetCell(row, makeSheetInput(record, 'tags', {wide: true, label: `${speakerRecordName(record)}のタグ`}));
    appendSheetCell(row, makeAttributesControl(record, `${speakerRecordName(record)}の追加属性`));
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
    summary.textContent = '所属・同意・詳細を編集';
    const detailGrid = document.createElement('div');
    detailGrid.className = 'speaker-card-grid details';
    detailGrid.append(
      createSpeakerCardField('組織', makeSheetInput(record, 'organization', {label: '組織', afterInput: refreshIdentity})),
      createSpeakerCardField('部署', makeSheetInput(record, 'department', {label: '部署'})),
      createSpeakerCardField('役職', makeSheetInput(record, 'job_title', {label: '役職', afterInput: refreshIdentity})),
      createSpeakerCardField('研究同意', makeSheetSelect(record, 'consent_status', consentLabels, {label: '研究同意', afterChange: updateSpeakerRegistryOverview})),
      createSpeakerCardField('録音同意', makeSheetSelect(record, 'recording_consent', consentLabels, {label: '録音同意', afterChange: updateSpeakerRegistryOverview})),
      createSpeakerCardField('守秘同意', makeSheetSelect(record, 'confidentiality_status', consentLabels, {label: '守秘同意'})),
      createSpeakerCardField('タグ', makeSheetInput(record, 'tags', {label: 'タグ', placeholder: '例：顧客, 管理職'}), true),
      createSpeakerCardField('追加属性', makeAttributesControl(record, '追加属性'), true),
      createSpeakerCardField('備考', makeSheetInput(record, 'notes', {multiline: true, label: '備考'}), true)
    );
    details.append(summary, detailGrid);

    const footer = document.createElement('footer');
    const consent = document.createElement('span');
    consent.className = 'speaker-card-consent';
    consent.textContent = `研究 ${consentLabels[record.consent_status] || '未確認'} / 録音 ${consentLabels[record.recording_consent] || '未確認'}`;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'sheet-delete';
    remove.textContent = 'この話者を削除';
    remove.addEventListener('click', () => removeSpeakerRecord(record));
    footer.append(consent, remove);

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
  const count = document.querySelector('#speaker-registry-count');
  if (count) count.textContent = `${visible.length}人を表示（登録 ${speakerRegistry.length}人）`;
}

async function saveSpeakerRegistry() {
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
  if (button) button.disabled = true;
  try {
    const response = await fetch('/api/speakers', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        speakers: speakerRegistry,
        delete_ids: [...speakerRegistryDeletedIds]
      })
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '話者管理データを保存できませんでした。');
    speakerRegistry = data.speakers || [];
    speakerRegistryDeletedIds.clear();
    setSpeakerRegistryDirty(false);
    renderSpeakerRegistry();
    setAlert(document.querySelector('#speaker-registry-message'), `${speakerRegistry.length}人の話者情報を保存しました。`);
    if (currentJob && !resultCard.hidden) renderSpeakerEditor();
  } catch (error) {
    setAlert(document.querySelector('#speaker-registry-message'), error.message, true);
  } finally {
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
  try {
    const response = await fetch('/api/speakers/import', {method: 'POST', body});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'CSVを取り込めませんでした。');
    speakerRegistry = data.speakers || [];
    speakerRegistryLoaded = true;
    speakerRegistryDeletedIds.clear();
    setSpeakerRegistryDirty(false);
    renderSpeakerRegistry();
    setAlert(document.querySelector('#speaker-registry-message'), `${data.imported_count}行を取り込み、話者管理へ保存しました。未知の列は追加属性として保持しています。`);
  } catch (error) {
    setAlert(document.querySelector('#speaker-registry-message'), error.message, true);
  } finally {
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
    const response = await fetch('/api/select-input', {method: 'POST', cache: 'no-store'});
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
    const response = await fetch('/api/config', {cache: 'no-store', signal: controller.signal});
    const data = await readJsonResponse(response);
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

function setRunning(running) {
  if (!form) return;
  jobRunning = running;
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

listen(form, 'submit', async event => {
  event.preventDefault();
  setAlert(formError, '');
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
  setRunning(true);
  resultCard.hidden = true;
  progressCard.hidden = false;
  progressCard.scrollIntoView({behavior: 'smooth', block: 'start'});
  try {
    const response = await fetch('/api/jobs', {method: 'POST', body: jobFormData});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '処理を開始できませんでした。');
    currentJobId = data.id;
    renderProgress(data);
    pollTimer = window.setInterval(pollJob, 1200);
  } catch (error) {
    setRunning(false);
    progressCard.hidden = true;
    setAlert(formError, error.message, true);
  }
});

async function pollJob() {
  if (!currentJobId) return;
  try {
    const response = await fetch(`/api/jobs/${currentJobId}`);
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '進捗を取得できません。');
    renderProgress(data);
    if (['completed', 'failed', 'cancelled'].includes(data.status)) {
      window.clearInterval(pollTimer);
      pollTimer = null;
      setRunning(false);
      cancelButton.disabled = true;
      if (data.status === 'completed') renderResult(data);
    }
  } catch (error) {
    window.clearInterval(pollTimer);
    pollTimer = null;
    setRunning(false);
    document.querySelector('#progress-message').textContent = error.message;
  }
}

function renderProgress(job) {
  const progress = Number(job.progress || 0);
  document.querySelector('#progress-number').textContent = `${progress}%`;
  document.querySelector('#progress-bar').style.width = `${progress}%`;
  document.querySelector('#progress-message').textContent = job.message || '';
  document.querySelector('#progress-log').textContent = (job.logs || []).join('\n');
  const titles = {queued: '開始待ち', running: '文字起こし中', completed: '処理完了', failed: 'エラー', cancelled: '中止しました'};
  document.querySelector('#progress-title').textContent = titles[job.status] || '処理中';
  document.querySelector('#progress-message').style.color = ['failed', 'cancelled'].includes(job.status) ? '#913733' : '';
}

listen(cancelButton, 'click', async () => {
  if (!currentJobId) return;
  cancelButton.disabled = true;
  try {
    const response = await fetch(`/api/jobs/${currentJobId}/cancel`, {method: 'POST'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error);
    document.querySelector('#progress-message').textContent = '中止を要求しました…';
  } catch (error) {
    document.querySelector('#progress-message').textContent = error.message;
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
    const response = await fetch(`/api/library?${params}`, {signal: libraryRequestController.signal});
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
    open.className = 'primary-button small library-open-button';
    open.type = 'button';
    open.textContent = '開いて編集';
    open.setAttribute('aria-label', `${item.source_name}を開いて編集`);
    open.addEventListener('click', () => openLibraryItem(item.id));
    const remove = document.createElement('button');
    remove.className = 'library-delete-button';
    remove.type = 'button';
    remove.textContent = '削除';
    remove.setAttribute('aria-label', `${item.source_name}を削除`);
    remove.addEventListener('click', () => deleteLibraryItem(item.id, item.source_name));
    actions.append(open, remove);
    card.append(media, body, actions);
    list.append(card);
  });
}

async function loadTrainingStatus() {
  const container = document.querySelector('#training-status');
  if (trainingStatusLoaded) return;
  trainingStatusLoaded = true;
  try {
    const response = await fetch('/api/training');
    const data = await readJsonResponse(response);
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
  } catch (_) {
    trainingStatusLoaded = false;
    container.textContent = '';
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
    const response = await fetch('/api/library', {
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
    const response = await fetch(`/api/library/${itemId}`);
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'データを開けませんでした。');
    renderResult(data);
  } catch (error) {
    setAlert(document.querySelector('#library-message'), error.message, true);
  }
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
    const response = await fetch(`/api/library/${itemId}`, {method: 'DELETE'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '削除できませんでした。');
    if (currentJobId === itemId) {
      currentJobId = null;
      currentJob = null;
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
    setAlert(document.querySelector('#library-message'), `「${name}」を削除しました。`);
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
  if (!sections.length) { view.hidden = true; return; }
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
  currentJobId = job.id;
  document.querySelector('#result-title').textContent = job.source_name || '確認・手動編集';
  const outputDirectory = document.querySelector('#result-output-dir');
  if (outputDirectory) {
    outputDirectory.textContent = job.output_dir ? `実行フォルダー　${job.output_dir}` : '';
    outputDirectory.hidden = !job.output_dir;
  }
  renderDownloads(job.files);
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
  if (speakerRegistryCard) speakerRegistryCard.hidden = true;
  if (analysisCard) analysisCard.hidden = true;
  form.hidden = true;
  progressCard.hidden = true;
  resultCard.hidden = false;
  showLibraryButton.classList.add('active');
  showNewButton.classList.remove('active');
  if (showSpeakersButton) showSpeakersButton.classList.remove('active');
  if (showAnalysisButton) showAnalysisButton.classList.remove('active');
  showLibraryButton.setAttribute('aria-selected', 'true');
  showNewButton.setAttribute('aria-selected', 'false');
  if (showSpeakersButton) showSpeakersButton.setAttribute('aria-selected', 'false');
  if (showAnalysisButton) showAnalysisButton.setAttribute('aria-selected', 'false');
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
    '#session-confidentiality': ['confidentiality_notes', ''],
    '#session-field-notes': ['field_notes', '']
  };
  Object.entries(fields).forEach(([selector, [key, fallback]]) => {
    const element = document.querySelector(selector);
    if (element) element.value = profile[key] || fallback;
  });
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
  currentJob.session_profile = {
    session_type: read('#session-type') || 'focus_group',
    session_date: read('#session-date'),
    location: read('#session-location'),
    objective: read('#session-objective'),
    moderator_guide: read('#session-guide'),
    group_conditions: read('#session-conditions'),
    confidentiality_notes: read('#session-confidentiality'),
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
      consent_status: 'unknown',
      recording_consent: 'unknown',
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
    control.addEventListener('change', () => onChange(control.value));
  } else {
    if (type !== 'textarea') control.type = type === 'color' ? 'color' : 'text';
    control.value = value || '';
    control.addEventListener('input', () => onChange(control.value));
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
    const missingConsent = participants.filter(profile => !['granted', 'not_required'].includes(profile.consent_status));
    const missingRecording = profiles.filter(profile => !['granted', 'not_required'].includes(profile.recording_consent));
    if (missingConsent.length) add(`研究同意 未確認 ${missingConsent.length}人`, 'error');
    if (missingRecording.length) add(`録音同意 未確認 ${missingRecording.length}人`, 'error');
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
  head.innerHTML = '<tr><th>音声話者</th><th>表示名</th><th>テーマカラー</th><th>グローバル話者</th><th>会話役割</th><th>組織</th><th>部署</th><th>役職</th><th>研究同意</th><th>録音同意</th><th>参加状態</th><th>会話固有条件</th><th>メモ</th><th>発言量</th></tr>';
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
        profile.consent_status = record.consent_status || 'unknown';
        profile.recording_consent = record.recording_consent || 'unknown';
        profile.conditions = attributesToText(record.attributes);
        currentJob.speaker_names[label] = profile.display_name;
      }
      renderSpeakerEditor();
      updateSpeakerBadges();
    });
    appendSheetCell(row, globalSelect);
    appendSheetCell(row, conversationControl('select', profile.session_role, speakerRoleLabels, value => {
      profile.session_role = value;
      renderSpeakerInsights(metrics);
    }));
    ['organization', 'department', 'job_title'].forEach(key => {
      appendSheetCell(row, conversationControl('input', profile[key], null, value => { profile[key] = value; }));
    });
    appendSheetCell(row, conversationControl('select', profile.consent_status, consentLabels, value => {
      profile.consent_status = value;
      renderSpeakerInsights(metrics);
    }));
    appendSheetCell(row, conversationControl('select', profile.recording_consent, consentLabels, value => {
      profile.recording_consent = value;
      renderSpeakerInsights(metrics);
    }));
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
  '#session-conditions', '#session-confidentiality', '#session-field-notes'
].forEach(selector => {
  listen(document.querySelector(selector), 'input', captureSessionProfile);
});
listen(document.querySelector('#session-type'), 'change', () => {
  captureSessionProfile();
  if (currentJob) renderSpeakerInsights(speakerMetrics());
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
    start.addEventListener('change', () => { segment.start = Math.max(0, Number(start.value) || 0); renderSegments(); });
    const end = document.createElement('input');
    end.type = 'number'; end.min = '0'; end.step = '0.01'; end.value = Number(segment.end || 0).toFixed(2);
    end.addEventListener('change', () => { segment.end = Math.max(0, Number(end.value) || 0); renderSegments(); });
    const speakerInput = document.createElement('input');
    speakerInput.type = 'text'; speakerInput.maxLength = 80; speakerInput.value = segment.speaker || 'UNKNOWN';
    speakerInput.addEventListener('change', () => {
      segment.speaker = speakerInput.value.trim() || 'UNKNOWN';
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
      renderSegments();
    });
    fields.append(createField('開始（秒）', start), createField('終了（秒）', end), createField('話者ラベル', speakerInput), createField('くしなだ感情', emotionSelect));
    const textarea = document.createElement('textarea');
    textarea.value = segment.text || '';
    textarea.setAttribute('aria-label', `${speaker.textContent}の発話`);
    textarea.addEventListener('input', () => { segment.text = textarea.value; });
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
  try {
    const response = await fetch(`/api/library/${currentJobId}`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        source_name: currentJob.source_name,
        speaker_names: currentJob.speaker_names,
        segments: payloadSegments,
        session_profile: currentJob.session_profile,
        speaker_profiles: currentJob.speaker_profiles
      })
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '保存できませんでした。');
    renderResult(data);
    const learning = data.learning_events
      ? `修正差分 ${data.learning_events} 件を、くしなだ学習用データへ追加しました。`
      : '新しい修正差分はありませんでした。';
    const warning = [data.output_warning, data.learning_warning].filter(Boolean).join(' ');
    setAlert(document.querySelector('#save-message'), `編集内容と出力ファイルを保存しました。${learning}${warning}`, Boolean(warning));
    loadTrainingStatus();
  } catch (error) {
    setAlert(message, error.message, true);
  } finally {
    saveButton.disabled = false;
  }
});

listen(deleteRecordButton, 'click', () => {
  if (currentJobId && currentJob) deleteLibraryItem(currentJobId, currentJob.source_name);
});

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

function setAnalysisDirty(dirty) {
  analysisState.dirty = Boolean(dirty);
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
    const response = await fetch('/api/library?sort=updated_desc', {cache: 'no-store'});
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
    const response = await fetch(`/api/library/${encodeURIComponent(nextId)}/analysis`, {
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
  setAnalysisDirty(analysisState.dirty);
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

function buildAnalysisTimelineChart(bins) {
  const namespace = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(namespace, 'svg');
  svg.classList.add('analysis-timeline-chart');
  svg.setAttribute('viewBox', '0 0 720 230');
  svg.setAttribute('role', 'img');
  const title = document.createElementNS(namespace, 'title');
  title.textContent = '時間帯別の発話量';
  const description = document.createElementNS(namespace, 'desc');
  description.textContent = '各時間帯の発話秒数を棒の高さで表しています。';
  svg.append(title, description);
  const values = (bins || []).map(item => Math.max(0, Number(item.speaking_seconds) || 0));
  const max = Math.max(1, ...values);
  const count = Math.max(1, values.length);
  const plotX = 44;
  const plotY = 16;
  const plotWidth = 652;
  const plotHeight = 168;
  [0, .5, 1].forEach(ratio => {
    const line = document.createElementNS(namespace, 'line');
    const y = plotY + plotHeight * (1 - ratio);
    line.setAttribute('x1', String(plotX));
    line.setAttribute('x2', String(plotX + plotWidth));
    line.setAttribute('y1', String(y));
    line.setAttribute('y2', String(y));
    line.setAttribute('class', 'analysis-chart-grid');
    svg.append(line);
  });
  values.forEach((value, index) => {
    const slot = plotWidth / count;
    const height = plotHeight * value / max;
    const rect = document.createElementNS(namespace, 'rect');
    rect.setAttribute('x', String(plotX + index * slot + Math.min(5, slot * .12)));
    rect.setAttribute('y', String(plotY + plotHeight - height));
    rect.setAttribute('width', String(Math.max(2, slot - Math.min(10, slot * .24))));
    rect.setAttribute('height', String(height));
    rect.setAttribute('rx', '4');
    rect.setAttribute('class', 'analysis-chart-bar');
    const tooltip = document.createElementNS(namespace, 'title');
    const item = bins[index] || {};
    tooltip.textContent = `${formatTime(item.start || 0)}–${formatTime(item.end || 0)}: ${value.toFixed(1)}秒`;
    rect.append(tooltip);
    svg.append(rect);
  });
  const startLabel = document.createElementNS(namespace, 'text');
  startLabel.setAttribute('x', String(plotX));
  startLabel.setAttribute('y', '216');
  startLabel.textContent = bins.length ? formatTime(bins[0].start || 0) : '00:00';
  const endLabel = document.createElementNS(namespace, 'text');
  endLabel.setAttribute('x', String(plotX + plotWidth));
  endLabel.setAttribute('y', '216');
  endLabel.setAttribute('text-anchor', 'end');
  endLabel.textContent = bins.length ? formatTime(bins[bins.length - 1].end || 0) : '00:00';
  svg.append(startLabel, endLabel);
  return svg;
}

function renderAutomaticAnalysis(compact) {
  const fragment = document.createDocumentFragment();
  const data = analysisState.data || {};
  const automatic = data.automatic || {};
  const overview = automatic.overview || {};
  const intro = analysisElement('div', 'analysis-result-intro');
  intro.append(
    analysisElement('span', 'analysis-kind automatic', '自動集計'),
    analysisElement('h2', '', compact ? '会話の自動分析' : 'グループインタビューの自動分析'),
    analysisElement('p', '', '保存済みの発話時刻・話者・テキストから機械的に計算した値です。重要性、影響力、合意や感情を確定するものではありません。')
  );
  fragment.append(intro);

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

  const grid = analysisElement('div', 'analysis-grid');
  const speakerPanel = analysisCardPanel('話者別の発話量', 'automatic', 'speakers', true);
  const speakers = Array.isArray(automatic.speaker_metrics) ? automatic.speaker_metrics : [];
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

  const balancePanel = analysisCardPanel('参加バランス', 'automatic');
  const balance = automatic.balance || {};
  const balanceMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(balanceMetrics, '均等度', analysisNumberText((Number(balance.normalized_evenness) || 0) * 100, 1, '%'), '100%に近いほど均等');
  appendAnalysisMetric(balanceMetrics, '最大比率', analysisNumberText(balance.max_participant_percent, 1, '%'), balance.max_participant_name || '—');
  appendAnalysisMetric(balanceMetrics, 'Gini係数', analysisNumberText(balance.gini, 3), '0に近いほど均等');
  balancePanel.body.append(balanceMetrics, analysisElement('p', 'analysis-caption', '発言量の偏りを示す記述値です。発言の重要性や場への影響力は表しません。'));
  grid.append(balancePanel.panel);

  const moderatorPanel = analysisCardPanel('司会と参加者の関係', 'automatic');
  const moderator = automatic.moderator || {};
  const moderatorMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(moderatorMetrics, '司会発話比率', moderator.assigned ? analysisNumberText(moderator.speaking_percent, 1, '%') : '役割未設定');
  appendAnalysisMetric(moderatorMetrics, '質問候補', `${moderator.question_candidates || 0}件`);
  appendAnalysisMetric(moderatorMetrics, '参加者応答', `${moderator.participant_responses || 0}件`);
  appendAnalysisMetric(moderatorMetrics, '参加者間遷移', `${moderator.participant_to_participant_transitions || 0}件`);
  moderatorPanel.body.append(moderatorMetrics, analysisElement('p', 'analysis-caption', '質問・応答は表記と話者遷移からの候補です。進行品質の評価ではありません。'));
  grid.append(moderatorPanel.panel);

  const timelinePanel = analysisCardPanel('時間帯別の発話量', 'automatic', 'timeline', true);
  const bins = Array.isArray(automatic.time_bins) ? automatic.time_bins : [];
  if (bins.length) timelinePanel.body.append(buildAnalysisTimelineChart(bins));
  else timelinePanel.body.append(analysisElement('p', 'analysis-no-data', '時間推移を表示できる発話がありません。'));
  grid.append(timelinePanel.panel);

  const transitionsPanel = analysisCardPanel('話者の遷移', 'automatic', 'transitions', true);
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

  const gapsPanel = analysisCardPanel('無音・発話重なり候補', 'automatic', 'gaps');
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

  const keywordsPanel = analysisCardPanel('特徴語候補', 'automatic', 'keywords');
  const keywords = Array.isArray(automatic.keywords) ? automatic.keywords : [];
  const maxKeyword = Math.max(1, ...keywords.map(item => Number(item.count) || 0));
  if (keywords.length) {
    keywords.slice(0, compact ? 10 : 15).forEach(item => appendAnalysisBar(
      keywordsPanel.body, item.term, 100 * (Number(item.count) || 0) / maxKeyword, `${item.count || 0}回`, '#6C8B3C'
    ));
  } else keywordsPanel.body.append(analysisElement('p', 'analysis-no-data', '特徴語候補を抽出できませんでした。'));
  keywordsPanel.body.append(analysisElement('p', 'analysis-caption', '出現頻度による簡易候補で、研究テーマを自動決定するものではありません。'));
  grid.append(keywordsPanel.panel);

  const emotionPanel = analysisCardPanel('音声感情の分布', 'automatic', 'emotions');
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
    const groupsPanel = analysisCardPanel('設定した属性による比較', 'configured', 'groups');
    groups.forEach(item => appendAnalysisBar(
      groupsPanel.body, item.group || '未設定', item.speaking_percent,
      `${item.speaker_count || 0}人 / ${item.turn_count || 0}回 / ${formatTime(item.speaking_seconds || 0)}`,
      '#9B51E0'
    ));
    grid.append(groupsPanel.panel);
  }

  const qualityPanel = analysisCardPanel('データ確認', 'automatic');
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
    analysisField('比較軸', analysisConfigControl('group_by', 'select', {
      none: '比較しない', role: '会話役割', organization: '組織', department: '部署', job_title: '役職'
    })),
    analysisField('長い無音の基準（秒）', analysisConfigControl('long_gap_seconds', 'number')),
    analysisField('重なり候補の基準（秒）', analysisConfigControl('overlap_seconds', 'number')),
    analysisField('低参加候補の基準（%）', analysisConfigControl('low_participation_percent', 'number')),
    analysisField('時間帯の幅（秒）', analysisConfigControl('time_bin_seconds', 'number')),
    analysisField('特徴語から除外する語', analysisConfigControl('stop_words', 'text'), 'カンマ区切りで入力します。')
  );
  const excludeModerator = analysisElement('label', 'check-row analysis-setting-check');
  excludeModerator.append(
    analysisConfigControl('exclude_moderator', 'checkbox'),
    analysisElement('span', '', '参加バランスから司会・観察役を除外する')
  );
  settingsGrid.append(excludeModerator);

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
  settingsPanel.body.append(settingsGrid, speakerExclusions);
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
    analysisElement('span', '', '保存すると自動集計とCSV・JSONも更新されます。')
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
  } else if (field === 'stop_words') {
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
  setAnalysisDirty(true);
  setAlert(document.querySelector('#analysis-message'), '');
  try {
    const item = analysisState.data.item || {};
    const response = await fetch(`/api/library/${encodeURIComponent(analysisState.itemId)}/analysis`, {
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
    analysisState.data = data;
    analysisState.config = deepCopy(data.config || {});
    analysisState.annotations = deepCopy(data.annotations || {});
    analysisSaveInProgress = false;
    setAnalysisDirty(false);
    renderAnalysisWorkspace();
    setAlert(document.querySelector('#analysis-message'), '分析設定、手動コード、解釈メモを保存し、集計と出力データを更新しました。');
  } catch (error) {
    analysisSaveInProgress = false;
    setAnalysisDirty(true);
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

showView('new');
