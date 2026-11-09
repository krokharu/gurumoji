/* 話者別タイムライン。既存データを表示し、時刻・話者・本文を書き換えない。 */
(() => {
  'use strict';
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const clock = seconds => {
    const value = Math.max(0, Math.floor(seconds || 0));
    const hours = Math.floor(value / 3600);
    return (hours ? String(hours).padStart(2, '0') + ':' : '')
      + String(Math.floor(value / 60) % 60).padStart(2, '0') + ':'
      + String(value % 60).padStart(2, '0');
  };
  const valid = row => Boolean(row && !row.time_unknown
    && typeof row.start === 'number' && Number.isFinite(row.start)
    && typeof row.end === 'number' && Number.isFinite(row.end)
    && row.start >= 0 && row.end >= row.start);
  const color = value => /^#[0-9a-f]{6}$/i.test(value || '') ? value : '#247f60';

  function create(root, callbacks) {
    if (!root) return null;
    const find = id => root.querySelector('#timeline-' + id);
    const viewport = find('viewport'), canvas = find('canvas'), zoom = find('zoom');
    const zoomOut = find('zoom-out'), zoomIn = find('zoom-in'), zoomFit = find('zoom-fit');
    const seek = find('seek'), position = find('position'), notice = find('notice');
    let job = null, duration = 0, mediaDuration = 0, time = 0, selected = null;
    let blocks = [], cursor = null, width = 1, canSeek = false, jobId = null;
    let lastWidth = 0;
    const labelWidth = () => window.matchMedia('(max-width: 600px)').matches ? 104 : 152;
    const reveal = () => {
      const x = time / (duration || 1) * width;
      viewport.scrollLeft = Math.max(0, x - (viewport.clientWidth - labelWidth()) / 2);
    };
    const select = id => {
      selected = id;
      blocks.forEach(item => {
        if (item.kind !== 'segment') return;
        item.node.classList.toggle('is-selected', item.row.id === id);
        item.node.setAttribute('aria-pressed', String(item.row.id === id));
      });
    };
    function updateTime(value, actualDuration, playing = false) {
      time = Number.isFinite(value) ? Math.max(0, value) : 0;
      if (Number.isFinite(actualDuration) && actualDuration > 0 && mediaDuration !== actualDuration) {
        mediaDuration = actualDuration;
        if (job) render(job, selected);
      }
      position.textContent = clock(time) + ' / ' + clock(duration);
      seek.value = String(Math.min(time, duration));
      seek.setAttribute('aria-valuetext', clock(time) + ' / ' + clock(duration));
      if (cursor) cursor.style.left = 'calc(var(--timeline-label-width) + ' + time / (duration || 1) * width + 'px)';
      blocks.forEach(item => item.node.classList.toggle('is-playing', time >= item.row.start && time < item.row.end));
      if (playing && callbacks.follow()) {
        const x = labelWidth() + time / (duration || 1) * width;
        if (x > viewport.scrollLeft + viewport.clientWidth - 28 || x < viewport.scrollLeft + labelWidth()) reveal();
      }
    }
    function seekTo(value, play = false) {
      if (!canSeek) return;
      const target = Math.min(mediaDuration || duration, Math.max(0, value));
      callbacks.seek(target, play);
      updateTime(target, mediaDuration);
    }
    function addRow(label, entries, kind, accent) {
      const row = element('div', 'timeline-row timeline-row-' + kind);
      const heading = element('div', 'timeline-label', label);
      heading.title = label;
      const lane = element('div', 'timeline-lane');
      lane.setAttribute('aria-label', label);
      row.style.setProperty('--timeline-accent', color(accent));
      row.append(heading, lane);
      // 同じ話者内の重複も隠さず、ひとつの話者行の中で段を分ける。
      const ends = [];
      entries.slice().sort((a, b) => a.start - b.start || a.end - b.end).forEach(entry => {
        const displayEnd = Math.max(entry.end, entry.start + 5 / width * duration);
        let level = ends.findIndex(end => end <= entry.start);
        if (level < 0) level = ends.length;
        ends[level] = displayEnd;
        const title = kind === 'outline' ? entry.title || '議題' : entry.text || '（本文なし）';
        const button = element('button', 'timeline-block', title);
        button.type = 'button';
        const accessible = label + ' ' + clock(entry.start) + '–' + clock(entry.end) + ' ' + title;
        button.title = accessible;
        button.setAttribute('aria-label', accessible);
        button.style.left = entry.start / (duration || 1) * 100 + '%';
        button.style.width = Math.max(0, entry.end - entry.start) / (duration || 1) * 100 + '%';
        button.style.top = 6 + level * 34 + 'px';
        if (kind === 'segment') {
          button.dataset.segmentId = String(entry.id);
          button.addEventListener('click', () => {
            callbacks.select(entry.id);
            select(entry.id);
            seekTo(entry.start, true);
          });
        } else {
          button.disabled = !canSeek;
          button.addEventListener('click', () => seekTo(entry.start, true));
        }
        lane.append(button);
        blocks.push({node: button, row: entry, kind});
      });
      lane.style.height = Math.max(46, ends.length * 34 + 12) + 'px';
      if (!entries.length) lane.append(element('span', 'timeline-lane-empty',
        kind === 'outline' ? '時刻付きのアウトラインはまだありません' : '時刻付きの発話はありません'));
      canvas.append(row);
    }
    function render(nextJob, selection = selected) {
      const nextId = nextJob ? String(nextJob.id) : null;
      if (jobId !== nextId) {
        jobId = nextId;
        time = 0; mediaDuration = 0; zoom.value = '1';
        viewport.scrollLeft = 0; viewport.scrollTop = 0;
      }
      job = nextJob; selected = selection;
      const focus = document.activeElement;
      const focusIndex = blocks.findIndex(item => item.node === focus);
      const focused = focusIndex >= 0 ? blocks[focusIndex] : null;
      canvas.replaceChildren(); blocks = []; cursor = null;
      const segments = Array.isArray(job?.segments) ? job.segments : [];
      const timed = segments.filter(valid);
      const result = job?.session_outline?.result;
      const outlineSource = Array.isArray(result?.rows) && result.rows.length
        ? result.rows : (Array.isArray(job?.outline?.sections) ? job.outline.sections : []);
      const outlines = outlineSource.filter(valid);
      duration = [...timed, ...outlines].reduce((end, row) => Math.max(end, row.end), mediaDuration);
      canSeek = Boolean(job?.media_url && duration > 0);
      seek.disabled = !canSeek; seek.max = String(duration);
      find('current').disabled = duration <= 0;
      zoom.disabled = duration <= 0;
      zoomOut.disabled = duration <= 0 || zoom.selectedIndex <= 0;
      zoomIn.disabled = duration <= 0 || zoom.selectedIndex >= zoom.options.length - 1;
      zoomFit.disabled = duration <= 0 || zoom.selectedIndex <= 0;
      const missing = segments.length - timed.length;
      const notes = [];
      if (!segments.length) notes.push('発話はまだありません。');
      if (missing) notes.push('時刻不明・不正な発話 ' + missing + '件は時間軸に表示していません。');
      if (!job?.media_url) notes.push('元の音声・動画がないため、発話の選択のみ利用できます。');
      if (result?.transformer_stale) notes.push('アウトラインのテーマは編集前の分析結果です。');
      if (outlines.length < outlineSource.length) notes.push('時刻不明・不正なアウトラインは時間軸に表示していません。');
      notice.textContent = notes.join(' ');
      notice.hidden = !notes.length;
      const available = viewport.clientWidth > labelWidth() ? viewport.clientWidth - labelWidth() : 240;
      width = Math.min(200000, available * Number(zoom.value));
      canvas.style.setProperty('--timeline-width', width + 'px');
      const ruler = element('div', 'timeline-row timeline-ruler');
      ruler.append(element('div', 'timeline-label', '時間'));
      const axis = element('div', 'timeline-axis');
      axis.setAttribute('aria-label', '時刻をクリックして移動');
      const rawStep = (duration || 1) / Math.max(1, width / 110);
      const power = 10 ** Math.floor(Math.log10(rawStep));
      const step = [1, 2, 5, 10].map(n => n * power).find(n => n >= rawStep);
      canvas.style.setProperty('--timeline-tick', step / (duration || 1) * width + 'px');
      for (let i = 0; i <= (duration ? duration / step : 0); i++) {
        const tick = element('span', 'timeline-tick', clock(i * step));
        tick.style.left = i * step / (duration || 1) * 100 + '%';
        axis.append(tick);
      }
      axis.addEventListener('click', event => {
        const bounds = axis.getBoundingClientRect();
        seekTo((event.clientX - bounds.left) / bounds.width * duration);
      });
      ruler.append(axis); canvas.append(ruler);
      addRow('アウトライン', outlines, 'outline', '#ac792c');
      // Mapで話者IDを扱い、特殊な名前でも別話者として保持する。
      const speakers = new Map();
      segments.forEach(row => {
        const speaker = row.speaker || 'UNKNOWN';
        if (!speakers.has(speaker)) speakers.set(speaker, []);
        if (valid(row)) speakers.get(speaker).push(row);
      });
      speakers.forEach((entries, speaker) => {
        addRow(callbacks.name(speaker), entries, 'segment', callbacks.color(speaker));
      });
      cursor = element('div', 'timeline-playhead');
      cursor.setAttribute('aria-hidden', 'true'); canvas.append(cursor);
      select(selection); updateTime(time);
      if (focused) {
        const replacement = blocks.find(item => item.kind === focused.kind
          && (item.kind === 'segment' ? item.row.id === focused.row.id : item.row === focused.row));
        replacement?.node.focus({preventScroll: true});
      }
    }
    const applyZoom = index => {
      if (!job || duration <= 0) return;
      // 見ている時間帯の中心を保ち、倍率変更で再生位置へ飛ばないようにする。
      const visibleWidth = Math.max(0, viewport.clientWidth - labelWidth());
      const center = (viewport.scrollLeft + visibleWidth / 2) / width;
      zoom.selectedIndex = Math.max(0, Math.min(zoom.options.length - 1, index));
      render(job);
      viewport.scrollLeft = Math.max(0, Math.min(width - visibleWidth, center * width - visibleWidth / 2));
    };
    zoom.addEventListener('change', () => applyZoom(zoom.selectedIndex));
    zoomOut.addEventListener('click', () => applyZoom(zoom.selectedIndex - 1));
    zoomIn.addEventListener('click', () => applyZoom(zoom.selectedIndex + 1));
    zoomFit.addEventListener('click', () => applyZoom(0));
    seek.addEventListener('input', () => seekTo(Number(seek.value)));
    find('current').addEventListener('click', reveal);
    if (window.ResizeObserver) {
      new ResizeObserver(() => {
        if (viewport.clientWidth > 0 && lastWidth !== viewport.clientWidth) {
          lastWidth = viewport.clientWidth;
          if (job) render(job);
        }
      }).observe(viewport);
    }
    return {render, updateTime, select};
  }
  window.GurumojiTimeline = {create};
})();
