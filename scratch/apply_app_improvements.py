path = "src/gurumoji/static/app.js"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. syncMediaPlayback 関数の追加と renderMedia への組み込み
# renderMedia(job) の前に syncMediaPlayback を定義し、timeupdate イベントリスナー内で呼び出す
old_render_media = """function renderMedia(job) {
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
}"""

new_render_media = """let activePlaybackSegmentId = null;

function syncMediaPlayback(currentTime) {
  if (!currentJob || !Array.isArray(currentJob.segments)) return;
  const match = currentJob.segments.find(segment => {
    const s = Number(segment.start || 0);
    const e = Number(segment.end || 0);
    return currentTime >= s && currentTime <= e;
  });
  const matchId = match ? match.id : null;
  if (matchId === activePlaybackSegmentId) return;
  activePlaybackSegmentId = matchId;

  document.querySelectorAll('.segment.is-active-playback').forEach(el => {
    el.classList.remove('is-active-playback');
  });

  if (matchId) {
    const target = document.querySelector(`.segment[data-segment-id="${matchId}"]`);
    if (target) {
      target.classList.add('is-active-playback');
      const autoScroll = document.querySelector('#media-autoscroll');
      if (!autoScroll || autoScroll.checked) {
        target.scrollIntoView({behavior: 'smooth', block: 'nearest'});
      }
    }
  }
}

function renderMedia(job) {
  mediaPlayerHost.replaceChildren();
  mediaPlayer = null;
  playbackStopAt = null;
  selectedSegmentId = null;
  activePlaybackSegmentId = null;
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
    syncMediaPlayback(mediaPlayer.currentTime);
  });
  mediaPlayerHost.append(mediaPlayer);
  mediaReview.hidden = false;
}"""

if old_render_media in content:
    content = content.replace(old_render_media, new_render_media, 1)
    print("Updated renderMedia and added syncMediaPlayback")
else:
    print("Warning: old_render_media not found exactly")

# 2. renderSegments 内の row click イベントリスナーの改善
old_click_listener = """    row.append(meta, body);
    row.addEventListener('click', event => {
      if (!event.target.closest('input, textarea, select, button, details') && currentJob.media_url) playSegment(segment.id);
    });"""

new_click_listener = """    row.append(meta, body);
    row.addEventListener('click', event => {
      const isButtonOrDetails = event.target.closest('button, details, select');
      if (isButtonOrDetails) return;

      // 行またはテキストエリアをクリックしたら選択行として展開
      if (selectedSegmentId !== segment.id) {
        selectedSegmentId = segment.id;
        document.querySelectorAll('.segment').forEach(item => {
          item.classList.toggle('selected', item.dataset.segmentId === segment.id);
        });
      }
      // テキストエリア・入力欄自体のクリックでなければメディア再生も連動
      if (!event.target.closest('textarea, input') && currentJob.media_url) {
        playSegment(segment.id);
      }
    });"""

if old_click_listener in content:
    content = content.replace(old_click_listener, new_click_listener, 1)
    print("Updated row click listener for compact/expanded toggle and playback")
else:
    print("Warning: old_click_listener not found exactly")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Finished updating app.js")
