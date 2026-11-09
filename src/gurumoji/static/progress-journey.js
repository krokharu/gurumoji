// 工程自身の通知を使い、処理中の動きと完了した工程を表示する。
const progressStageKinds = {
  admitting: ['transfer', 'ファイルを受け付けています'], queued: ['prepare', '処理の開始を待っています'],
  environment: ['prepare', '処理に使う環境を確認しています'], preprocess: ['audio', '音声を聞き取りやすく整えています'],
  transcription: ['transcribe', '音声から文章を作っています'], alignment: ['align', '発話と時刻を合わせています'],
  diarization: ['speakers', '声を話者ごとに分けています'], speaker_assignment: ['speakers', '発話に話者を対応付けています'],
  finishing: ['edit', '文字起こしの文章を整えています'], emotion: ['audio', '声の特徴を調べています'],
  speaker_names: ['speakers', '名前と話者を確認しています'], outline: ['edit', '会話を話題ごとに整理しています'],
  meeting_minutes: ['edit', '議事録とタスク候補をまとめています'], output: ['save', '結果をファイルに保存しています'],
  committing: ['save', '処理結果を保存しています'], completed: ['complete', 'すべての処理が完了しました']
};
const progressMotionTheme = Object.freeze({strokeWidth: 6.5, startup: 640, transition: 360, settle: 280});
const progressMotionSvg = content => `<svg class="gm-motion-scene" viewBox="0 0 260 156" fill="none" stroke="currentColor" stroke-width="${progressMotionTheme.strokeWidth}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path class="motion-shell" pathLength="1" d="M34 10H226Q246 10 246 30V106Q246 126 226 126H103L78 144V126H34Q14 126 14 106V30Q14 10 34 10Z"/><path class="motion-accent" d="M225 24V36M219 30H231"/><g class="motion-stage" transform="translate(10 4)"><g class="motion-symbol">${content}</g></g></svg>`;
const progressMotionScenes = {
  prepare: progressMotionSvg('<circle cx="120" cy="60" r="35" opacity=".6"/><g class="motion-rotate"><path d="M120 25a35 35 0 0 1 35 35"/><circle cx="120" cy="25" r="5" fill="currentColor"/></g><path d="m108 61 8 8 17-19"/>'),
  audio: progressMotionSvg(Array.from({length:9},(_,i)=>`<rect class="motion-wave" x="${43+i*18}" y="${42-(i%3)*5}" width="12" height="${36+(i%3)*10}" rx="4" fill="currentColor" stroke="none" style="--motion-delay:${i*-0.12}s"/>`).join('')),
  transcribe: progressMotionSvg('<rect x="81" y="17" width="94" height="86" rx="10" opacity=".8"/><path class="motion-writing" d="M98 40h56M98 55h40M98 70h56M98 85h30"/><path class="motion-cursor" d="M145 78v14"/><path class="motion-wave" d="M28 57h8l6-16 8 38 8-28 6 6h9"/>'),
  align: progressMotionSvg('<path d="M25 30h190M25 90h190" opacity=".65"/><path d="M45 23v14M95 23v14M145 23v14M195 23v14M45 83v14M95 83v14M145 83v14M195 83v14" opacity=".85"/><rect x="47" y="46" width="44" height="25" rx="5" fill="currentColor" opacity=".18"/><rect x="103" y="46" width="77" height="25" rx="5" fill="currentColor" opacity=".8"/><path class="motion-scan" d="M50 18v84"/>'),
  speakers: progressMotionSvg('<path d="M64 59h112M120 37v48" opacity=".65"/><g class="motion-speaker first"><circle cx="60" cy="40" r="13"/><path d="M35 85c0-28 50-28 50 0"/></g><g class="motion-speaker second"><circle cx="120" cy="27" r="13"/><path d="M95 72c0-28 50-28 50 0"/></g><g class="motion-speaker third"><circle cx="180" cy="40" r="13"/><path d="M155 85c0-28 50-28 50 0"/></g><path d="M89 103h62" opacity=".7"/>'),
  edit: progressMotionSvg('<rect x="65" y="15" width="93" height="91" rx="9" opacity=".7"/><path d="M83 36h53M83 52h38M83 68h51M83 84h27"/><g class="motion-pen"><path d="m132 82 36-36 12 12-36 36-17 5zM161 53l12 12"/></g><path class="motion-spark" d="M190 20v16M182 28h16"/>'),
  save: progressMotionSvg('<path d="M62 87v15h116V87M78 80H62V33h43l12 13h61v34" opacity=".8"/><g class="motion-transfer"><path d="M120 32v47m-15-15 15 15 15-15"/></g><path d="M89 92h62"/>'),
  transfer: progressMotionSvg('<path d="M62 87v15h116V87M78 80H62V33h43l12 13h61v34" opacity=".8"/><g class="motion-transfer"><path d="M120 79V32m-15 15 15-15 15 15"/></g>'),
  complete: progressMotionSvg('<circle cx="120" cy="60" r="39" fill="currentColor" opacity=".12" stroke="none"/><circle cx="120" cy="60" r="34" opacity=".85"/><path class="motion-check" d="m100 60 13 13 27-28" stroke-width="8"/>'),
  failed: progressMotionSvg('<circle cx="120" cy="60" r="36" opacity=".7"/><path d="m107 47 26 26m0-26-26 26" stroke-width="8"/>'),
  cancelled: progressMotionSvg('<circle cx="120" cy="60" r="36" opacity=".7"/><rect x="105" y="45" width="30" height="30" rx="5" fill="currentColor" stroke="none"/>')
};
// 同じ工程の進捗更新では動きを再起動せず、工程変更時だけ切り替える。
const progressMotionControllers = new WeakMap();
function updateProgressMotion(motion, {identity, stage, rawStage = stage, scene, state}) {
  const previous = progressMotionControllers.get(motion);
  const handoff = previous && ['admitting', 'queued'].includes(previous.rawStage)
    && ['running', 'waiting'].includes(previous.state) && ['running', 'waiting'].includes(state);
  const newRun = !previous || (previous.identity !== identity && !handoff);
  const changed = newRun || previous.stage !== stage || previous.scene !== scene || previous.state !== state;
  motion.dataset.scene = scene;
  motion.dataset.state = state;
  if (!changed) { previous.identity = identity; return; }
  if (previous?.timer !== null && previous?.timer !== undefined) window.clearTimeout(previous.timer);
  const controller = {identity, stage, rawStage, scene, state, timer: null};
  progressMotionControllers.set(motion, controller);
  const terminal = ['completed', 'failed', 'cancelled'].includes(state);
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const finish = () => {
    if (progressMotionControllers.get(motion) !== controller) return;
    if (controller.timer !== null) window.clearTimeout(controller.timer);
    motion.querySelectorAll('.motion-outgoing').forEach(node => node.remove());
    motion.querySelectorAll('.motion-entering').forEach(node => node.classList.remove('motion-entering'));
    motion.dataset.cycle = terminal ? 'settled' : state === 'running' ? 'loop' : 'waiting';
    controller.timer = null;
  };
  controller.finish = finish;
  if (newRun || !motion.querySelector('.motion-stage')) {
    motion.innerHTML = progressMotionScenes[scene];
  } else {
    motion.querySelectorAll('.motion-outgoing').forEach(node => node.remove());
    const outgoing = motion.querySelector('.motion-stage > .motion-symbol');
    if (outgoing) { outgoing.classList.remove('motion-entering'); outgoing.classList.add('motion-outgoing'); }
    const template = document.createElement('template');
    template.innerHTML = progressMotionScenes[scene];
    motion.querySelector('.motion-stage').append(template.content.querySelector('.motion-symbol').cloneNode(true));
  }
  const incoming = motion.querySelector('.motion-symbol:not(.motion-outgoing)');
  if (reduced || (newRun && terminal)) { finish(); return; }
  motion.dataset.cycle = newRun ? 'startup' : terminal ? 'settling' : 'transition';
  const duration = newRun ? progressMotionTheme.startup : terminal ? progressMotionTheme.settle : progressMotionTheme.transition;
  motion.style.setProperty('--motion-cycle-duration', `${duration}ms`);
  incoming.classList.add('motion-entering');
  controller.timer = window.setTimeout(finish, duration);
}

const progressMotionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
progressMotionPreference.addEventListener?.('change', event => {
  if (!event.matches) return;
  document.querySelectorAll('.progress-motion').forEach(motion => progressMotionControllers.get(motion)?.finish?.());
});

let progressJourneyJob = null;
let progressJourneyEntries = new Map();
let progressJourneySignature = '';
function renderProgressJourney(job, current) {
  const motion = document.querySelector('#progress-motion');
  const list = document.querySelector('#progress-journey-list');
  if (!motion || !list) return;
  const identity = String(job.id || 'submitting');
  if (progressJourneyJob !== identity) {
    progressJourneyJob = identity;
    progressJourneyEntries = new Map();
    progressJourneySignature = '';
  }
  const terminal = ['completed', 'failed', 'cancelled'].includes(job.status);
  const key = Object.hasOwn(progressStageKinds, job.stage) && !(job.stage === 'queued' && job.status === 'running')
    ? job.stage : job.status === 'committing' ? 'committing' : job.status === 'admitting' ? 'admitting' : current.label;
  const clamp = value => Math.max(0, Math.min(100, Number(value) || 0));
  if (Array.isArray(job.stage_history) && job.stage_history.length) {
    progressJourneyEntries = new Map(job.stage_history.filter(entry => entry && typeof entry.key === 'string').map(entry => [entry.key, {
      key: entry.key, label: String(entry.label || entry.key), progress: clamp(entry.progress),
      status: ['completed', 'failed', 'cancelled', 'pending', 'running'].includes(entry.status) ? entry.status : 'pending'
    }]));
  } else {
    for (const entry of progressJourneyEntries.values()) if (entry.status === 'running' && entry.key !== key) entry.status = 'pending';
    progressJourneyEntries.set(key, {key, label: current.label, progress: clamp(current.progress),
      status: terminal ? job.status : !current.estimated && current.progress >= 100 ? 'completed' : 'running'});
  }
  const state = terminal ? job.status : !current.estimated && current.progress >= 100 ? 'completed' : job.status === 'queued' ? 'waiting' : 'running';
  const kind = Object.hasOwn(progressStageKinds, key) ? progressStageKinds[key] : ['prepare', '処理状況を確認しています'];
  const scene = ['completed', 'failed', 'cancelled'].includes(state) ? state === 'completed' ? 'complete' : state : kind[0];
  updateProgressMotion(motion, {identity, stage: `${key}:${current.label}`, rawStage: key, scene, state});
  document.querySelector('#progress-card').dataset.outcome = String(job.status || 'queued');
  document.querySelector('.current-process-panel').dataset.state = state;
  const statuses = {running: '処理中', completed: '完了', failed: '失敗', cancelled: '中止', pending: '完了未確認'};
  let caption = document.querySelector('#progress-motion-caption');
  if (!caption) {
    caption = document.createElement('p');caption.id = 'progress-motion-caption';caption.className = 'progress-motion-caption';
    document.querySelector('.current-process-body').append(caption);
  }
  caption.textContent = state === 'completed' ? job.status === 'completed' ? '「結果を開く」から内容を確認できます。' : 'この工程は完了しました。' : state === 'failed' ? '処理を停止しました。エラーの内容を確認してください。' : state === 'cancelled' ? '処理は中止されました。' : kind[1];
  const entries = [...progressJourneyEntries.values()];
  const signature = JSON.stringify(entries.map(entry => [entry.key, entry.label, entry.status]));
  if (signature !== progressJourneySignature) {
    progressJourneySignature = signature;
    list.replaceChildren(...entries.map(entry => {
      const item = document.createElement('li');item.className = `progress-journey-step is-${entry.status}`;
      const mark = document.createElement('span');mark.className = 'journey-mark';mark.setAttribute('aria-hidden', 'true');
      mark.textContent = {completed: '✓', running: '●', failed: '!', cancelled: '■', pending: '○'}[entry.status];
      const label = document.createElement('strong');label.textContent = entry.label;
      const badge = document.createElement('span');badge.className = 'journey-state';badge.textContent = statuses[entry.status];
      item.append(mark, label, badge);
      if (entry.status === 'running') item.setAttribute('aria-current', 'step');
      return item;
    }));
  }
  const completed = entries.filter(entry => entry.status === 'completed').length;
  document.querySelector('#progress-journey-summary').textContent = `${completed}工程が完了`;
}
