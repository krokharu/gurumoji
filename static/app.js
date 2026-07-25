const form = document.querySelector('#job-form');
const libraryCard = document.querySelector('#library-card');
const speakerRegistryCard = document.querySelector('#speaker-registry-card');
const speakerRegistryBody = document.querySelector('#speaker-registry-body');
const sourcePath = document.querySelector('#source-path');
const inputFile = document.querySelector('#input-file');
const browsePathButton = document.querySelector('#browse-path-button');
const pathDetail = document.querySelector('#path-detail');
const pathError = document.querySelector('#path-error');
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
const cleanTranscript = document.querySelector('#clean-transcript');
const detectNames = document.querySelector('#detect-names');
const createOutline = document.querySelector('#create-outline');
const showLibraryButton = document.querySelector('#show-library-button');
const showNewButton = document.querySelector('#show-new-button');
const showSpeakersButton = document.querySelector('#show-speakers-button');
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
let speakerRegistry = [];
let speakerRegistryDeletedIds = new Set();
let speakerRegistryLoaded = false;
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
  const library = view === 'library';
  const create = view === 'new';
  const speakers = view === 'speakers';
  if (libraryCard) libraryCard.hidden = !library;
  if (speakerRegistryCard) speakerRegistryCard.hidden = !speakers;
  if (form) form.hidden = !create;
  if (library || create || speakers) {
    if (mediaPlayer) mediaPlayer.pause();
    if (resultCard) resultCard.hidden = true;
    if (progressCard && (!currentJobId || !pollTimer)) progressCard.hidden = true;
  }
  if (showLibraryButton) showLibraryButton.classList.toggle('active', library);
  if (showNewButton) showNewButton.classList.toggle('active', create);
  if (showSpeakersButton) showSpeakersButton.classList.toggle('active', speakers);
  if (library && libraryCard) loadLibrary();
  if (speakers && speakerRegistryCard) loadSpeakerRegistry();
}

listen(showLibraryButton, 'click', () => showView('library'));
listen(showNewButton, 'click', () => showView('new'));
listen(showSpeakersButton, 'click', () => showView('speakers'));

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

function makeSheetInput(record, key, {type = 'text', wide = false, multiline = false} = {}) {
  const input = document.createElement(multiline ? 'textarea' : 'input');
  if (!multiline) input.type = type;
  if (wide) input.className = 'cell-wide';
  input.value = Array.isArray(record[key]) ? record[key].join(', ') : (record[key] || '');
  input.addEventListener('input', () => {
    record[key] = key === 'tags'
      ? input.value.split(/[,、;]+/).map(item => item.trim()).filter(Boolean)
      : input.value;
  });
  return input;
}

function makeSheetSelect(record, key, labels) {
  const select = document.createElement('select');
  Object.entries(labels).forEach(([value, label]) => select.add(new Option(label, value)));
  select.value = record[key] || Object.keys(labels)[0];
  select.addEventListener('change', () => { record[key] = select.value; });
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
    if (!response.ok) throw new Error(data.error || '話者台帳を取得できませんでした。');
    speakerRegistry = Array.isArray(data.speakers) ? data.speakers : [];
    speakerRegistryDeletedIds.clear();
    speakerRegistryLoaded = true;
    renderSpeakerRegistry();
    if (currentJob && !resultCard.hidden) renderSpeakerEditor();
    return speakerRegistry;
  } catch (error) {
    setAlert(document.querySelector('#speaker-registry-message'), error.message, true);
    return [];
  }
}

function renderSpeakerRegistry() {
  if (!speakerRegistryBody) return;
  const searchElement = document.querySelector('#speaker-registry-search');
  const roleElement = document.querySelector('#speaker-registry-role-filter');
  const showInactiveElement = document.querySelector('#speaker-registry-show-inactive');
  const query = (searchElement ? searchElement.value : '').trim().toLocaleLowerCase();
  const role = roleElement ? roleElement.value : '';
  const showInactive = !showInactiveElement || showInactiveElement.checked;
  speakerRegistryBody.replaceChildren();
  const visible = speakerRegistry.filter(record => {
    if (!showInactive && !record.active) return false;
    if (role && record.default_role !== role) return false;
    if (!query) return true;
    return JSON.stringify(record).toLocaleLowerCase().includes(query);
  });

  visible.forEach(record => {
    const row = document.createElement('tr');
    row.classList.toggle('inactive', !record.active);
    const active = document.createElement('input');
    active.type = 'checkbox';
    active.checked = record.active !== false;
    active.addEventListener('change', () => {
      record.active = active.checked;
      row.classList.toggle('inactive', !record.active);
    });
    appendSheetCell(row, active);
    appendSheetCell(row, makeSheetInput(record, 'participant_code'));
    appendSheetCell(row, makeSheetInput(record, 'display_name'));
    appendSheetCell(row, makeSheetInput(record, 'pseudonym'));
    appendSheetCell(row, makeSheetSelect(record, 'default_role', speakerRoleLabels));
    appendSheetCell(row, makeSheetInput(record, 'organization'));
    appendSheetCell(row, makeSheetInput(record, 'department'));
    appendSheetCell(row, makeSheetInput(record, 'job_title'));
    appendSheetCell(row, makeSheetSelect(record, 'consent_status', consentLabels));
    appendSheetCell(row, makeSheetSelect(record, 'recording_consent', consentLabels));
    appendSheetCell(row, makeSheetSelect(record, 'confidentiality_status', consentLabels));
    appendSheetCell(row, makeSheetInput(record, 'tags', {wide: true}));
    const attributes = document.createElement('textarea');
    attributes.value = attributesToText(record.attributes);
    attributes.placeholder = '年齢層=30代; 性別=女性';
    attributes.addEventListener('input', () => { record.attributes = textToAttributes(attributes.value); });
    appendSheetCell(row, attributes);
    appendSheetCell(row, makeSheetInput(record, 'notes', {multiline: true}));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'sheet-delete';
    remove.textContent = '削除';
    remove.addEventListener('click', () => {
      if (!window.confirm(`${record.pseudonym || record.display_name || record.participant_code} を台帳から削除しますか？`)) return;
      speakerRegistryDeletedIds.add(record.id);
      speakerRegistry = speakerRegistry.filter(item => item.id !== record.id);
      renderSpeakerRegistry();
    });
    appendSheetCell(row, remove);
    speakerRegistryBody.append(row);
  });
  const count = document.querySelector('#speaker-registry-count');
  if (count) count.textContent = `表示 ${visible.length} / 全 ${speakerRegistry.length} 人`;
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
  const button = document.querySelector('#save-speakers-button');
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
    if (!response.ok) throw new Error(data.error || '話者台帳を保存できませんでした。');
    speakerRegistry = data.speakers || [];
    speakerRegistryDeletedIds.clear();
    renderSpeakerRegistry();
    setAlert(document.querySelector('#speaker-registry-message'), `${speakerRegistry.length}人の話者台帳を保存しました。`);
    if (currentJob && !resultCard.hidden) renderSpeakerEditor();
  } catch (error) {
    setAlert(document.querySelector('#speaker-registry-message'), error.message, true);
  } finally {
    if (button) button.disabled = false;
  }
}

listen(document.querySelector('#add-speaker-button'), 'click', () => {
  speakerRegistry.push(blankSpeakerRecord());
  renderSpeakerRegistry();
  if (speakerRegistryBody && speakerRegistryBody.lastElementChild) {
    speakerRegistryBody.lastElementChild.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  }
});
listen(document.querySelector('#save-speakers-button'), 'click', saveSpeakerRegistry);
listen(document.querySelector('#speaker-registry-search'), 'input', renderSpeakerRegistry);
listen(document.querySelector('#speaker-registry-role-filter'), 'change', renderSpeakerRegistry);
listen(document.querySelector('#speaker-registry-show-inactive'), 'change', renderSpeakerRegistry);
listen(document.querySelector('#import-speakers-button'), 'click', () => {
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
    renderSpeakerRegistry();
    setAlert(document.querySelector('#speaker-registry-message'), `${data.imported_count}行を取り込みました。未知の列は追加属性として保持しています。`);
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

listen(sourcePath, 'input', () => {
  setAlert(pathError, '');
  const value = sourcePath.value.trim();
  if (value && inputFile) inputFile.value = '';
  pathDetail.textContent = value
    ? `${value.split(/[\\/]/).pop()} — このパスを直接処理します`
    : 'MP4 / MOV / MKV / WAV / MP3 / M4A / FLAC に対応';
  scheduleSourceThumbnail(value);
});

listen(browsePathButton, 'click', async () => {
  setAlert(pathError, '');
  if (!browsePathButton) return;
  if (browserFilePickerOnly) {
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
  } catch (error) {
    setAlert(pathError, error.message || 'ファイル選択に失敗しました。', true);
  } finally {
    browsePathButton.disabled = false;
    browsePathButton.textContent = browserFilePickerOnly ? '端末からアップロード' : 'ファイルを選択';
  }
});

listen(inputFile, 'change', () => {
  setAlert(pathError, '');
  const file = inputFile.files && inputFile.files[0];
  if (!file) return;
  sourcePath.value = '';
  pathDetail.textContent = browserFilePickerOnly
    ? `${file.name} / ${formatBytes(file.size)} — Colabへ一時アップロードして処理します`
    : `${file.name} / ${formatBytes(file.size)} — このPC内だけで一時コピーして処理します`;
  hideSourcePreview();
});

function setHardwareLight(element, available, availableText, unavailableText, title = '') {
  if (!element) return;
  element.classList.remove('checking', 'available', 'unavailable');
  element.classList.add(available ? 'available' : 'unavailable');
  element.textContent = available ? availableText : unavailableText;
  element.title = title;
}

function applyMachineProfile(machine) {
  if (!machine) return;
  const cpu = machine.cpu || {};
  const gpu = machine.gpu || {};
  const recommended = machine.recommended || {};
  const cpuLight = document.querySelector('#status-cpu');
  const gpuLight = document.querySelector('#status-gpu');
  const summary = document.querySelector('#machine-summary');
  const recommendation = document.querySelector('#machine-recommendation');
  const modelSelect = document.querySelector('#model-name');
  const transcriptionDevice = document.querySelector('#transcription-device');
  const diarizationDevice = document.querySelector('#diarization-device');

  setHardwareLight(
    cpuLight,
    Boolean(cpu.available),
    'CPU 利用可',
    'CPU 利用不可',
    `${cpu.name || 'CPU'} / ${cpu.logical_threads || '?'} threads`
  );
  setHardwareLight(
    gpuLight,
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
      browsePathButton.textContent = browserFilePickerOnly ? '端末からアップロード' : 'ファイルを選択';
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
  [...form.elements].forEach(element => {
    element.disabled = running || element.dataset.alwaysDisabled === 'true';
  });
  if (startButton) startButton.disabled = running;
  if (cancelButton) cancelButton.disabled = !running;
  syncQuietFields();
  syncEmotionFields();
  syncAiFields();
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

listen(boostQuietSpeech, 'change', syncQuietFields);
listen(triplePass, 'change', syncQuietFields);
listen(emotionAnalysis, 'change', syncEmotionFields);
listen(aiProvider, 'change', syncAiFields);
syncQuietFields();
syncEmotionFields();
syncAiFields();

listen(form, 'submit', async event => {
  event.preventDefault();
  setAlert(formError, '');
  if (!sourcePath.value.trim() && !(inputFile && inputFile.files && inputFile.files.length)) {
    setAlert(formError, '処理する音声・動画ファイルを選択してください。', true);
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

async function loadLibrary() {
  const list = document.querySelector('#library-list');
  const message = document.querySelector('#library-message');
  setAlert(message, '');
  const params = new URLSearchParams({
    keyword: document.querySelector('#library-keyword').value.trim(),
    speaker: document.querySelector('#library-speaker').value,
    emotion: document.querySelector('#library-emotion').value,
    sort: document.querySelector('#library-sort').value
  });
  try {
    const response = await fetch(`/api/library?${params}`);
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'ライブラリを取得できません。');
    updateFacetSelect(document.querySelector('#library-speaker'), data.facets.speakers || [], 'すべての話者');
    updateFacetSelect(document.querySelector('#library-emotion'), data.facets.emotions || [], 'すべての感情');
    document.querySelector('#library-count').textContent = `${data.total} 件のデータ`;
    renderLibraryItems(data.items || []);
    loadTrainingStatus();
  } catch (error) {
    list.replaceChildren();
    setAlert(message, error.message, true);
  }
}

function renderLibraryItems(items) {
  const list = document.querySelector('#library-list');
  list.replaceChildren();
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'library-empty';
    empty.textContent = '条件に一致するデータはありません。\n「新しく文字起こし」または「空のデータを追加」から登録できます。';
    list.append(empty);
    return;
  }
  items.forEach(item => {
    const card = document.createElement('article');
    card.className = 'library-item';
    const thumbnail = document.createElement('img');
    thumbnail.className = 'library-thumbnail';
    thumbnail.src = item.thumbnail_url;
    thumbnail.alt = `${item.source_name} のワードクラウド`;
    thumbnail.loading = 'lazy';
    const body = document.createElement('div');
    const title = document.createElement('h3');
    title.textContent = item.source_name;
    const meta = document.createElement('div');
    meta.className = 'library-meta';
    const mediaLabel = item.media_url ? (item.media_kind === 'video' ? '動画あり' : '音声あり') : '元メディアなし';
    meta.textContent = `更新 ${formatDate(item.updated_at)}　発話 ${item.segment_count}件　${formatTime(item.duration)}　${mediaLabel}　修正 ${item.revision_count}回`;
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
    body.append(title, meta, preview, chips);
    const actions = document.createElement('div');
    actions.className = 'library-actions';
    const open = document.createElement('button');
    open.className = 'secondary-button';
    open.type = 'button';
    open.textContent = '開く・編集';
    open.addEventListener('click', () => openLibraryItem(item.id));
    const remove = document.createElement('button');
    remove.className = 'secondary-button danger';
    remove.type = 'button';
    remove.textContent = '削除';
    remove.addEventListener('click', () => deleteLibraryItem(item.id, item.source_name));
    actions.append(open, remove);
    card.append(thumbnail, body, actions);
    list.append(card);
  });
}

async function loadTrainingStatus() {
  const container = document.querySelector('#training-status');
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
    container.textContent = '';
  }
}

['#library-speaker', '#library-emotion', '#library-sort'].forEach(selector => {
  listen(document.querySelector(selector), 'change', loadLibrary);
});
listen(document.querySelector('#library-keyword'), 'input', () => {
  window.clearTimeout(libraryTimer);
  libraryTimer = window.setTimeout(loadLibrary, 250);
});

listen(document.querySelector('#add-record-button'), 'click', async () => {
  const sourceName = window.prompt('追加するデータの名前を入力してください。', '新規文字起こし');
  if (sourceName === null || !sourceName.trim()) return;
  try {
    const response = await fetch('/api/library', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({source_name: sourceName.trim()})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '追加できませんでした。');
    renderResult(data);
  } catch (error) {
    setAlert(document.querySelector('#library-message'), error.message, true);
  }
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
    showView('library');
  } catch (error) {
    setAlert(document.querySelector('#library-message'), error.message, true);
  }
}

function renderDownloads(files) {
  const container = document.querySelector('#download-links');
  container.replaceChildren();
  (files || []).forEach(file => {
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
  form.hidden = true;
  progressCard.hidden = true;
  resultCard.hidden = false;
  showLibraryButton.classList.remove('active');
  showNewButton.classList.remove('active');
  if (showSpeakersButton) showSpeakersButton.classList.remove('active');
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
      globalSelect.add(new Option('削除済みの台帳話者', profile.global_speaker_id));
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

showView('new');
