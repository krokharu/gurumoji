function renderProgress(job) {
  lastProgressJob = job;
  if (typeof renderAiFinishingActivity === 'function') renderAiFinishingActivity(job);
  const progress = Number(job.progress || 0);
  const fallbackStage = fallbackProgressStage(job, progress);
  const hasCurrentStage = Boolean(job.stage_label)
    && !(job.stage === 'queued' && job.status === 'running' && progress > 0);
  const stageLabel = hasCurrentStage ? job.stage_label : fallbackStage.label;
  const stageProgress = Math.max(0, Math.min(100, Number(
    hasCurrentStage ? job.stage_progress : fallbackStage.progress
  ) || 0));
  if (typeof renderProgressJourney === 'function') renderProgressJourney(job, {label: stageLabel, progress: stageProgress, estimated: !hasCurrentStage});
  const active = ['admitting', 'queued', 'running', 'committing'].includes(job.status);
  const activityLabels = {
    admitting: '受付中', queued: '開始待ち', running: '処理中', committing: '保存中',
    completed: '完了', failed: 'エラー', cancelled: '中止'
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
  document.querySelector('#progress-message').textContent = job.status === 'completed' ? 'すべての処理が完了し、結果を保存しました。' : job.message || '';
  document.querySelector('#progress-log').textContent = (job.logs || []).join('\n');
  renderAiTokenUsage('#progress-ai-usage', job.ai_usage);
  const titles = {admitting: '受付中', queued: '開始待ち', running: '文字起こし中', committing: '結果を保存中', completed: '処理完了', failed: 'エラー', cancelled: '中止しました'};
  document.querySelector('#progress-title').textContent = titles[job.status] || '処理中';
  document.querySelector('#progress-message').style.color = ['failed', 'cancelled'].includes(job.status) ? '#913733' : '';
  updateJobChip(job);
  syncCreateViewState();
}

function updateFacetSelect(select, values, allLabel) {
  const selected = select.value;
  select.replaceChildren(new Option(allLabel, ''));
  values.forEach(value => select.add(new Option(value, value)));
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

function updateLibraryGroupSelect(select, groups, {includeAll = false, includeUngrouped = false} = {}) {
  if (!select) return;
  const selected = select.value;
  select.replaceChildren();
  if (includeAll) select.add(new Option('すべてのフォルダー', ''));
  if (includeAll || includeUngrouped) select.add(new Option('未分類', includeAll ? '__ungrouped__' : ''));
  groups.forEach(group => select.add(new Option(`${group.name}（${group.item_count || 0}件）`, group.id)));
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

async function assignLibraryItemGroup(item, select) {
  const previous = item.group_id || '';
  select.disabled = true;
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(item.id)}/group`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({group_id: select.value})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'フォルダーを変更できませんでした。');
    await loadLibrary();
  } catch (error) {
    select.value = previous;
    select.disabled = false;
    setAlert(document.querySelector('#library-message'), error.message, true);
  }
}

function renderLibraryGroupManager() {
  if (!libraryGroupList) return;
  libraryGroupList.replaceChildren();
  if (!libraryGroups.length) {
    const empty = document.createElement('p');
    empty.className = 'library-group-empty';
    empty.textContent = 'フォルダーはまだありません。上の欄から作成できます。';
    libraryGroupList.append(empty);
    return;
  }
  libraryGroups.forEach(group => {
    const row = document.createElement('div');
    row.className = 'library-group-row';
    const field = document.createElement('label');
    field.className = 'field';
    const label = document.createElement('span');
    label.textContent = `${group.item_count || 0}件`;
    const input = document.createElement('input');
    input.type = 'text';
    input.maxLength = 80;
    input.value = group.name;
    input.setAttribute('aria-label', `${group.name}のフォルダー名`);
    field.append(label, input);
    const save = document.createElement('button');
    save.type = 'button';
    save.className = 'secondary-button compact-button';
    save.textContent = '名前を保存';
    save.addEventListener('click', async () => {
      save.disabled = true;
      try {
        const response = await apiFetch(`/api/library/groups/${encodeURIComponent(group.id)}`, {
          method: 'PUT', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name: input.value})
        });
        const data = await readJsonResponse(response);
        if (!response.ok) throw new Error(data.error || 'フォルダー名を変更できませんでした。');
        await loadLibrary();
        renderLibraryGroupManager();
        setAlert(libraryGroupMessage, 'フォルダー名を変更しました。');
      } catch (error) {
        save.disabled = false;
        setAlert(libraryGroupMessage, error.message, true);
      }
    });
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'secondary-button danger compact-button';
    remove.textContent = '削除';
    remove.addEventListener('click', async () => {
      const count = Number(group.item_count || 0);
      const note = count ? `\n所属する${count}件のデータは「未分類」に戻ります。` : '';
      if (!window.confirm(`フォルダー「${group.name}」を削除しますか？${note}\n処理済みデータ本体は削除されません。`)) return;
      remove.disabled = true;
      try {
        const response = await apiFetch(`/api/library/groups/${encodeURIComponent(group.id)}`, {method: 'DELETE'});
        const data = await readJsonResponse(response);
        if (!response.ok) throw new Error(data.error || 'フォルダーを削除できませんでした。');
        await loadLibrary();
        renderLibraryGroupManager();
        setAlert(libraryGroupMessage, `「${group.name}」を削除しました。`);
      } catch (error) {
        remove.disabled = false;
        setAlert(libraryGroupMessage, error.message, true);
      }
    });
    row.append(field, save, remove);
    libraryGroupList.append(row);
  });
}

function libraryFilterState() {
  return {
    keyword: document.querySelector('#library-keyword').value.trim(),
    speaker: document.querySelector('#library-speaker').value,
    emotion: document.querySelector('#library-emotion').value,
    group: document.querySelector('#library-group').value,
    data_group: document.querySelector('#library-data-group')?.value || '',
    tag: document.querySelector('#library-tag')?.value || '',
    sort: document.querySelector('#library-sort').value,
    recorded_from: document.querySelector('#library-recorded-from')?.value || '',
    recorded_to: document.querySelector('#library-recorded-to')?.value || '',
    media_duration_min: document.querySelector('#library-media-duration-min')?.value || '',
    media_duration_max: document.querySelector('#library-media-duration-max')?.value || ''
  };
}

function updateLibraryFilterState() {
  const state = libraryFilterState();
  const conditions = [];
  if (state.keyword) conditions.push(`「${state.keyword}」`);
  if (state.speaker) conditions.push(`話者: ${state.speaker}`);
  if (state.emotion) conditions.push(`感情: ${state.emotion}`);
  if (state.data_group) conditions.push(`分析グループ: ${document.querySelector('#library-data-group').selectedOptions[0].textContent}`);
  if (state.tag) conditions.push(`タグ: ${document.querySelector('#library-tag').selectedOptions[0].textContent}`);
  if (state.recorded_from) conditions.push(`収録日: ${state.recorded_from}以降`);
  if (state.recorded_to) conditions.push(`収録日: ${state.recorded_to}以前`);
  if (state.media_duration_min) conditions.push(`メディア: ${state.media_duration_min}秒以上`);
  if (state.media_duration_max) conditions.push(`メディア: ${state.media_duration_max}秒以下`);
  if (state.group) {
    const group = document.querySelector('#library-group');
    conditions.push(`フォルダー: ${group.options[group.selectedIndex].text}`);
  }
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
  const hasTime = item => item.duration !== null && item.duration !== undefined && item.duration !== ''
    && typeof item.duration !== 'boolean' && Number.isFinite(Number(item.duration)) && Number(item.duration) >= 0;
  const known = items.filter(hasTime);
  const duration = known.reduce((sum, item) => sum + Number(item.duration), 0);
  const missing = items.filter(item => !hasTime(item) || item.missing_time_turn_count > 0).length;
  const speakers = new Set(items.flatMap(item => item.speakers || []));
  const latest = items.reduce((value, item) => {
    const updated = String(item.updated_at || '');
    return updated > value ? updated : value;
  }, '');
  const values = {
    '#library-total-metric': String(items.length),
    '#library-duration-metric': !items.length ? '—' : !known.length ? '時刻不明'
      : missing ? `時刻あり計 ${formatTime(duration)} / 欠測あり${missing}件` : formatTime(duration),
    '#library-speaker-metric': String(speakers.size),
    '#library-updated-metric': latest ? formatDate(latest) : '—'
  };
  Object.entries(values).forEach(([selector, value]) => {
    const element = document.querySelector(selector);
    if (element) element.textContent = value;
  });
}

// DATA-01: deleted conversations wait in the trash until restored, purged or expired.
async function loadLibraryTrash() {
  const panel = document.querySelector('#library-trash');
  if (!panel) return;
  const list = panel.querySelector('[data-trash-list]');
  try {
    const response = await apiFetch('/api/library/trash', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'ゴミ箱を読み込めませんでした。');
    const entries = data.entries || [];
    const days = Number(data.retention_days || 0);
    panel.querySelector('[data-trash-summary]').textContent = `（${entries.length}件・${formatBytes(data.total_bytes || 0)}）`;
    panel.querySelector('[data-trash-note]').textContent = days
      ? `削除した会話はここに移り、${days}日後に自動で完全に削除されます。それまでは復元できます。`
      : '削除した会話はここに移り、完全に削除するまで残ります（自動削除なし）。';
    list.replaceChildren();
    if (!entries.length) {
      list.textContent = 'ゴミ箱は空です。';
      return;
    }
    entries.forEach(entry => {
      const row = document.createElement('div');
      row.className = 'library-trash-row';
      const label = document.createElement('span');
      label.textContent = `${entry.source_name || entry.item_id} / 削除 ${formatDate(entry.deleted_at)}`
        + `${entry.expires_at ? ` / 自動削除 ${formatDate(entry.expires_at)}` : ''} / ${formatBytes(entry.bytes || 0)}`;
      const restore = document.createElement('button');
      restore.type = 'button';
      restore.className = 'secondary-button compact-button';
      restore.textContent = '復元';
      restore.disabled = !entry.restorable;
      restore.addEventListener('click', () => changeLibraryTrash(entry, 'restore'));
      const purge = document.createElement('button');
      purge.type = 'button';
      purge.className = 'secondary-button compact-button danger';
      purge.textContent = '完全に削除';
      purge.addEventListener('click', () => changeLibraryTrash(entry, 'purge'));
      row.append(label, restore, purge);
      list.append(row);
    });
  } catch (error) {
    list.textContent = error.message;
  }
}

async function changeLibraryTrash(entry, action) {
  const name = entry.source_name || entry.item_id;
  if (action === 'purge' && !window.confirm(`「${name}」をゴミ箱から完全に削除しますか？\n元に戻せません。`)) return;
  const message = document.querySelector('#library-message');
  try {
    const url = `/api/library/trash/${encodeURIComponent(entry.id)}${action === 'restore' ? '/restore' : ''}`;
    const response = await apiFetch(url, {method: action === 'restore' ? 'POST' : 'DELETE'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '操作できませんでした。');
    if (action === 'restore') await loadLibrary(); else await loadLibraryTrash();
    setAlert(message, `「${name}」：${data.message}`);
  } catch (error) {
    setAlert(message, error.message, true);
  }
}

async function loadLibrary(pageOffset = 0) {
  const list = document.querySelector('#library-list');
  const message = document.querySelector('#library-message');
  setAlert(message, '');
  updateLibraryFilterState();
  const state = libraryFilterState();
  const filterKey = JSON.stringify(state);
  libraryPageOffset = filterKey === libraryPageFilter && Number.isInteger(pageOffset) ? pageOffset : 0;
  libraryPageFilter = filterKey;
  const params = new URLSearchParams(state);
  params.set('limit', '50'); params.set('offset', String(libraryPageOffset));
  // Preserve the existing unfiltered request shape for offline fixtures and clients.
  ['recorded_from', 'recorded_to', 'media_duration_min', 'media_duration_max', 'data_group', 'tag'].forEach(key => {
    if (state[key] === '') params.delete(key);
  });
  if (libraryRequestController) libraryRequestController.abort();
  libraryRequestController = new AbortController();
  const requestId = ++libraryRequestSequence;
  list.setAttribute('aria-busy', 'true');
  renderLibraryLoading();
  try {
    const response = await apiFetch(`/api/library?${params}`, {signal: libraryRequestController.signal});
    const data = await readJsonResponse(response);
    if (requestId !== libraryRequestSequence) return;
    if (!response.ok) throw new Error(data.error || '処理済みデータの一覧を取得できません。');
    updateFacetSelect(document.querySelector('#library-speaker'), data.facets.speakers || [], 'すべての話者');
    updateFacetSelect(document.querySelector('#library-emotion'), data.facets.emotions || [], 'すべての感情');
    libraryGroups = Array.isArray(data.groups) ? data.groups : [];
    document.dispatchEvent(new CustomEvent('gurumoji-library-catalog', {detail: data}));
    updateLibraryGroupSelect(document.querySelector('#library-group'), libraryGroups, {includeAll: true});
    const items = data.items || [];
    document.querySelector('#library-count').textContent = `${data.total}件中 ${libraryPageOffset + (items.length ? 1 : 0)}〜${libraryPageOffset + items.length}件を表示`;
    const pager = document.querySelector('#library-pagination');
    if (pager) {
      pager.replaceChildren();
      const previous = contentButton('前の50件', () => loadLibrary(Math.max(0, libraryPageOffset - 50)));
      previous.disabled = libraryPageOffset === 0;
      const next = contentButton('次の50件', () => loadLibrary(libraryPageOffset + 50));
      next.disabled = !data.pagination?.has_more;
      pager.append(previous, next);
    }
    renderLibraryOverview(items);
    renderLibraryItems(items);
    updateLibraryFilterState();
    loadLibraryTrash();
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
  const grouped = document.querySelector('#library-sort').value === 'group';
  const visibleGroupCounts = items.reduce((counts, item) => {
    const key = item.group_id || '__ungrouped__';
    counts.set(key, (counts.get(key) || 0) + 1);
    return counts;
  }, new Map());
  let previousGroupKey = null;
  items.forEach(item => {
    const groupKey = item.group_id || '__ungrouped__';
    if (grouped && groupKey !== previousGroupKey) {
      const heading = document.createElement('div');
      heading.className = 'library-group-heading';
      const name = document.createElement('strong');
      name.textContent = item.group_name || '未分類';
      const count = document.createElement('span');
      count.textContent = `${visibleGroupCounts.get(groupKey) || 0}件`;
      heading.append(name, count);
      list.append(heading);
      previousGroupKey = groupKey;
    }
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
      `収録日 ${item.media_created_at ? String(item.media_created_at).slice(0, 10) : '不明'}`,
      `メディア ${item.media_duration_seconds == null ? '不明' : item.media_duration_seconds < 1 ? `${item.media_duration_seconds}秒` : formatTime(item.media_duration_seconds)}`,
      `最終時刻 ${analysisEndpointText(item.duration, item.timed_turn_count, item.missing_time_turn_count)}`,
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
    if (item.group_name) {
      const chip = document.createElement('span');
      chip.className = 'library-chip group';
      chip.textContent = item.group_name;
      chips.append(chip);
    }
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
    const groupLabel = document.createElement('label');
    groupLabel.className = 'library-group-assignment';
    const groupLabelText = document.createElement('span');
    groupLabelText.className = 'visually-hidden';
    groupLabelText.textContent = `${item.source_name}のフォルダー`;
    const groupSelect = document.createElement('select');
    groupSelect.setAttribute('aria-label', `${item.source_name}のフォルダー`);
    updateLibraryGroupSelect(groupSelect, libraryGroups, {includeUngrouped: true});
    groupSelect.value = item.group_id || '';
    groupSelect.addEventListener('click', event => event.stopPropagation());
    groupSelect.addEventListener('change', () => assignLibraryItemGroup(item, groupSelect));
    groupLabel.append(groupLabelText, groupSelect);
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
    actions.append(groupLabel, analyze, remove);
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

function clearLibraryFilters() {
  document.querySelector('#library-keyword').value = '';
  document.querySelector('#library-speaker').value = '';
  document.querySelector('#library-emotion').value = '';
  document.querySelector('#library-group').value = '';
  document.querySelector('#library-sort').value = 'updated_desc';
  ['#library-recorded-from', '#library-recorded-to', '#library-media-duration-min', '#library-media-duration-max', '#library-data-group', '#library-tag'].forEach(selector => {
    const input = document.querySelector(selector);
    if (input) input.value = '';
  });
  updateLibraryFilterState();
  loadLibrary();
}

function setLibraryFiltersOpen(open) {
  if (!libraryCard) return;
  libraryCard.classList.toggle('filters-open', open);
  const toggle = document.querySelector('#library-filter-toggle');
  if (toggle) toggle.setAttribute('aria-expanded', String(open));
}

async function loadLibraryGroupManager() {
  setAlert(libraryGroupMessage, '読み込み中…');
  try {
    const response = await apiFetch('/api/library?limit=1&offset=0');
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'フォルダーを取得できませんでした。');
    libraryGroups = Array.isArray(data.groups) ? data.groups : [];
    renderLibraryGroupManager();
    setAlert(libraryGroupMessage, '');
  } catch (error) {
    setAlert(libraryGroupMessage, error.message, true);
  }
}

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
  if (!['openai', 'google', 'lmstudio'].includes(normalizedProvider)) return;
  const label = {
    openai: 'OpenAI',
    google: 'Google Gemini',
    lmstudio: String(tokenConfigSnapshot.local_llm_label || 'LM Studio（ローカル）')
  }[normalizedProvider];
  if (normalizedProvider !== 'lmstudio' && !tokenConfigSnapshot[normalizedProvider]) {
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

async function openLibraryItem(itemId) {
  const requestSequence = ++resultRequestSequence;
  try {
    const response = await apiFetch(`/api/library/${itemId}`);
    const data = await readJsonResponse(response);
    if (requestSequence !== resultRequestSequence) return;
    if (!response.ok) throw new Error(data.error || 'データを開けませんでした。');
    renderResult(data);
  } catch (error) {
    if (requestSequence === resultRequestSequence) {
      setAlert(document.querySelector('#library-message'), error.message, true);
    }
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
  if (deletingLibraryItems.has(itemId)) return;
  if (!window.confirm(`「${name}」を処理済みデータから削除しますか？\n会話と保存メディアはゴミ箱に移り、保持期間を過ぎると自動で完全に削除されます。それまではゴミ箱から復元できます。出力ファイルと学習履歴は残ります。`)) return;
  deletingLibraryItems.add(itemId);
  const fromResult = currentJobId === itemId && !resultCard.hidden;
  const message = document.querySelector(fromResult ? '#save-message' : '#library-message');
  const suspendedPlayer = currentJobId === itemId ? mediaPlayer : null;
  const suspendedTime = suspendedPlayer?.currentTime || 0;
  const suspendedSource = suspendedPlayer?.getAttribute('src');
  if (fromResult && deleteRecordButton) deleteRecordButton.disabled = true;
  setAlert(message, 'ゴミ箱へ移動しています…');
  try {
    if (suspendedPlayer) {
      suspendedPlayer.pause();
      suspendedPlayer.removeAttribute('src');
      suspendedPlayer.load();
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
      `「${name}」をゴミ箱に移しました。${cleanupWarning}${recoveryNote}`,
      Boolean(cleanupWarning || recoveryNote)
    );
  } catch (error) {
    if (suspendedPlayer && suspendedSource && currentJobId === itemId) {
      suspendedPlayer.src = suspendedSource;
      suspendedPlayer.addEventListener('loadedmetadata', () => { suspendedPlayer.currentTime = suspendedTime; }, {once: true});
      suspendedPlayer.load();
    }
    setAlert(message, error.message, true);
  } finally {
    deletingLibraryItems.delete(itemId);
    if (fromResult && deleteRecordButton) deleteRecordButton.disabled = false;
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

function meetingPriorityLabel(priority) {
  return ({high: '高', medium: '中', low: '低', unspecified: '未設定'})[priority] || '未設定';
}

function meetingPriorityClass(priority) {
  return ['high', 'medium', 'low'].includes(priority) ? priority : 'unspecified';
}

function appendMeetingMetric(container, label, count, total, className = '') {
  const row = document.createElement('div');
  row.className = `meeting-metric-row${className ? ` ${className}` : ''}`;
  const heading = document.createElement('span');
  heading.textContent = label;
  const bar = document.createElement('i');
  bar.style.width = `${total ? Math.max(4, Math.round((Number(count) || 0) / total * 100)) : 0}%`;
  const value = document.createElement('b');
  value.textContent = String(Number(count) || 0);
  row.append(heading, bar, value);
  container.append(row);
}

function applyMeetingObsidianStatus(data) {
  if (!meetingObsidianStatus || !meetingObsidianSaveButton || !meetingObsidianOpenLink) return;
  const state = data && data.status ? data.status : 'unprepared';
  meetingObsidianStatus.dataset.state = state;
  meetingObsidianStatus.textContent = data?.message || '会議議事録はObsidianに未保存です。';
  meetingObsidianSaveButton.textContent = state === 'stale' ? '更新版をObsidianに保存'
    : state === 'completed' ? 'Obsidianに保存済み' : 'Obsidianに保存';
  meetingObsidianOpenLink.hidden = !data?.uri;
  if (data?.uri) meetingObsidianOpenLink.href = data.uri;
}

async function loadMeetingObsidianStatus(jobId) {
  // The panel is absent while the Obsidian integration is withdrawn.
  if (!meetingObsidianStatus) return;
  const generation = ++meetingObsidianStatusGeneration;
  applyMeetingObsidianStatus({status: 'checking', message: 'Obsidianの保存状態を確認しています…'});
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(jobId)}/meeting-obsidian`);
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'Obsidianの保存状態を確認できませんでした。');
    if (generation !== meetingObsidianStatusGeneration || currentJobId !== jobId) return;
    applyMeetingObsidianStatus(data);
  } catch (error) {
    if (generation !== meetingObsidianStatusGeneration || currentJobId !== jobId) return;
    applyMeetingObsidianStatus({status: 'error', message: error.message});
  }
}

function renderMeetingMinutes(minutes, jobId) {
  if (!meetingMinutesView) return;
  const data = minutes && typeof minutes === 'object' ? minutes : null;
  const tasks = data && Array.isArray(data.tasks) ? data.tasks : [];
  const decisions = data && Array.isArray(data.decisions) ? data.decisions : [];
  const analysis = data && typeof data.analysis === 'object' && data.analysis ? data.analysis : {};
  const hasMeetingData = data && (tasks.length || decisions.length || Array.isArray(data.summary));
  meetingMinutesView.hidden = !hasMeetingData;
  if (!hasMeetingData) return;

  const prefix = `/api/library/${encodeURIComponent(jobId)}`;
  const exports = [
    ['#meeting-minutes-download', `${prefix}/meeting-minutes.md`],
    ['#meeting-tasks-download', `${prefix}/meeting-tasks.csv`],
    ['#meeting-json-download', `${prefix}/meeting.json`],
  ];
  exports.forEach(([selector, href]) => {
    const link = document.querySelector(selector);
    if (link) link.href = href;
  });

  const method = document.querySelector('#meeting-minutes-method');
  if (method) {
    method.textContent = data.method === 'rule_based_candidate_extraction'
      ? '抽出方法：ルールベースの候補抽出。元発話の時刻を確認してから取り込んでください。'
      : `抽出方法：${data.method || '未記録'}`;
  }
  const summary = document.querySelector('#meeting-minutes-summary');
  summary.replaceChildren();
  (data.summary || []).forEach(text => {
    const item = document.createElement('p');
    item.textContent = text;
    summary.append(item);
  });

  const priorityChart = document.querySelector('#meeting-priority-chart');
  priorityChart.replaceChildren();
  const priorityCounts = analysis.priority_counts || {};
  const priorityTotal = tasks.length || 1;
  [['high', '高'], ['medium', '中'], ['low', '低'], ['unspecified', '未設定']].forEach(([key, label]) => {
    appendMeetingMetric(priorityChart, label, priorityCounts[key], priorityTotal, key);
  });

  const dueSummary = document.querySelector('#meeting-due-summary');
  dueSummary.replaceChildren();
  const dated = tasks.filter(task => task.due_date).length;
  const relative = tasks.filter(task => !task.due_date && task.due_text).length;
  const missing = Math.max(0, tasks.length - dated - relative);
  appendMeetingMetric(dueSummary, '日付あり', dated, tasks.length || 1, 'dated');
  appendMeetingMetric(dueSummary, '期限表現あり', relative, tasks.length || 1, 'relative');
  appendMeetingMetric(dueSummary, '期限未設定', missing, tasks.length || 1, 'missing');

  const speakerChart = document.querySelector('#meeting-speaker-chart');
  speakerChart.replaceChildren();
  const activity = Array.isArray(analysis.speaker_activity) ? analysis.speaker_activity : [];
  const maxSeconds = Math.max(1, ...activity.map(item => Number(item.seconds) || 0));
  activity.slice(0, 6).forEach(item => {
    const row = document.createElement('div');
    row.className = 'meeting-speaker-row';
    const label = document.createElement('span');
    label.textContent = item.speaker || '話者不明';
    const bar = document.createElement('i');
    bar.style.width = `${Math.max(4, Math.round((Number(item.seconds) || 0) / maxSeconds * 100))}%`;
    const value = document.createElement('small');
    value.textContent = `${item.turns || 0}回 / ${formatTime(item.seconds || 0)}`;
    row.append(label, bar, value);
    speakerChart.append(row);
  });
  if (!activity.length) speakerChart.textContent = '発話量データはありません。';

  const taskList = document.querySelector('#meeting-task-list');
  taskList.replaceChildren();
  if (!tasks.length) {
    const empty = document.createElement('p');
    empty.className = 'meeting-empty';
    empty.textContent = 'タスク候補は検出されませんでした。録音中の依頼・担当・期限の表現を確認してください。';
    taskList.append(empty);
  }
  tasks.forEach(task => {
    const card = document.createElement('article');
    card.className = 'meeting-task-card';
    const top = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = task.title || '要確認のタスク候補';
    const priority = document.createElement('span');
    priority.className = `meeting-priority ${meetingPriorityClass(task.priority)}`;
    priority.textContent = `優先度 ${meetingPriorityLabel(task.priority)}`;
    top.append(title, priority);
    const meta = document.createElement('p');
    const due = task.due_date || task.due_text || '未設定';
    meta.textContent = `担当候補: ${task.owner || '未特定'} / 期限: ${due} / 根拠: ${formatTime(task.evidence_start || 0)}`;
    const source = document.createElement('small');
    source.textContent = task.source_text || '';
    card.append(top, meta, source);
    taskList.append(card);
  });

  const decisionList = document.querySelector('#meeting-decision-list');
  decisionList.replaceChildren();
  if (!decisions.length) {
    const empty = document.createElement('p');
    empty.className = 'meeting-empty';
    empty.textContent = '決定事項候補は検出されませんでした。';
    decisionList.append(empty);
  }
  decisions.forEach(decision => {
    const item = document.createElement('article');
    item.className = 'meeting-decision-item';
    const text = document.createElement('p');
    text.textContent = decision.text || '';
    const meta = document.createElement('small');
    meta.textContent = `${decision.speaker || '話者不明'} / ${formatTime(decision.evidence_start || 0)}`;
    item.append(text, meta);
    decisionList.append(item);
  });
  loadMeetingObsidianStatus(jobId);
}

// The planned agenda next to one time-ordered account of what was discussed.
// Titles come from the AI agenda where it exists; the rest is named by theme.
function renderSessionOutline(data, outline) {
  const box = document.querySelector('#session-outline');
  const host = document.querySelector('#session-outline-content');
  const headline = document.querySelector('#session-outline-headline');
  if (!box || !host) return;
  host.replaceChildren();
  const plan = (data && data.plan) || {available: false, items: []};
  // A freshly finished transcription arrives without the joined block; show the
  // agenda it does carry rather than claiming there is no result.
  const sections = outline && Array.isArray(outline.sections) ? outline.sections : [];
  const fallback = !data && sections.length ? {
    available: true, outline_available: true, transformer_available: false,
    rows: sections.map(section => ({
      start: section.start, end: section.end, title: section.title || '議題',
      title_source: 'outline', topics: [], segment_count: 0,
    })),
  } : null;
  const result = (data && data.result) || fallback || {available: false, rows: []};
  const rows = Array.isArray(result.rows) ? result.rows : [];
  const planItems = Array.isArray(plan.items) ? plan.items : [];
  if (headline) {
    const parts = [plan.available ? `予定 ${plan.item_count}項目` : '予定なし'];
    if (plan.available && plan.match === 'manual_topics') parts.push(`話された ${plan.discussed_count}項目`);
    parts.push(rows.length ? `結果 ${rows.length}区間` : '結果なし');
    headline.textContent = parts.join('・');
  }

  if (plan.available) {
    const section = document.createElement('section');
    section.className = 'session-outline-block';
    const head = document.createElement('h3');
    head.textContent = '予定（質問ガイド・議題）';
    section.append(head);
    if (plan.match !== 'manual_topics') {
      const note = document.createElement('p');
      note.className = 'session-outline-note';
      note.textContent = '消化状況は未照合です。「分析・可視化」のTransformerテーマ分析で決め方を「手動で定義する」にし、質問ガイドから取り込んで実行すると、項目ごとの発話数が出ます。';
      section.append(note);
    }
    const list = document.createElement('ol');
    list.className = 'session-outline-plan';
    planItems.forEach(item => {
      const entry = document.createElement('li');
      const text = document.createElement('span');
      text.className = 'session-outline-plan-text';
      text.textContent = item.text || '';
      entry.append(text);
      const statusLabels = {discussed: '話された', not_discussed: '発話の割当なし', unmatched: '未照合'};
      const status = document.createElement('span');
      status.className = `session-outline-status ${item.status || 'unmatched'}`;
      status.textContent = item.status === 'discussed'
        ? `${statusLabels.discussed}（${item.segment_count}発話・${item.speaker_count}人）`
        : statusLabels[item.status] || '未照合';
      entry.append(status);
      list.append(entry);
    });
    section.append(list);
    host.append(section);
  } else {
    const note = document.createElement('p');
    note.className = 'session-outline-note';
    note.textContent = '予定（質問ガイド・議題）は登録されていません。以下は、実際に話された結果と自動アウトラインです。予定は「会話・話者」タブの調査設計で登録できます。';
    host.append(note);
  }

  const section = document.createElement('section');
  section.className = 'session-outline-block';
  const head = document.createElement('h3');
  head.textContent = '結果（時間順）';
  section.append(head);
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.className = 'session-outline-note';
    empty.textContent = '結果はまだありません。AI仕上げのアウトライン、または「分析・可視化」のTransformerテーマ分析を実行すると、ここに時間順で並びます。';
    section.append(empty);
  } else {
    if (result.transformer_stale) {
      const stale = document.createElement('p');
      stale.className = 'session-outline-note warn';
      stale.textContent = 'テーマは実行時点の結果です。その後に本文・話者・除外が変わっています。';
      section.append(stale);
    }
    const list = document.createElement('ol');
    list.className = 'session-outline-rows';
    rows.forEach(row => {
      const entry = document.createElement('li');
      const time = document.createElement('span');
      time.className = 'session-outline-time';
      time.textContent = `${formatTime(row.start)}–${formatTime(row.end)}`;
      const body = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = row.title || '議題';
      const origin = document.createElement('span');
      origin.className = `session-outline-origin ${row.title_source}`;
      origin.textContent = row.title_source === 'outline' ? 'AI議題' : 'テーマ';
      body.append(title, origin);
      const topics = Array.isArray(row.topics) ? row.topics : [];
      if (topics.length) {
        const chips = document.createElement('div');
        chips.className = 'session-outline-topics';
        topics.forEach(topic => {
          const chip = document.createElement('span');
          chip.textContent = `${topic.label || topic.topic_id}（${topic.segment_count}）`;
          chips.append(chip);
        });
        body.append(chips);
      } else if (row.title_source === 'outline') {
        const none = document.createElement('small');
        none.textContent = result.transformer_available
          ? 'この区間にテーマ分類された発話はありません'
          : 'テーマ分析は未実行です';
        body.append(none);
      }
      entry.append(time, body);
      list.append(entry);
    });
    section.append(list);
    const foot = document.createElement('p');
    foot.className = 'session-outline-note';
    foot.textContent = '「AI議題」はAI仕上げが作った議題見出し、「テーマ」は議題のない区間をTransformerの意味クラスタから名付けた候補です。どちらも原文で確認してください。';
    section.append(foot);
    if (result.outline_available) {
      const jump = document.createElement('button');
      jump.type = 'button';
      jump.className = 'secondary-button compact-button';
      jump.textContent = '議題の要点を見る';
      jump.addEventListener('click', () => {
        setItemTab('summary');
        document.querySelector('#outline-view')?.scrollIntoView({block: 'start'});
      });
      section.append(jump);
    }
  }
  host.append(section);
  box.hidden = false;
  // Nothing to read yet: stay out of the way of the editing screen below.
  if (!plan.available && !result.available) box.open = false;
}

function renderOutline(outline) {
  const view = document.querySelector('#outline-view');
  const content = document.querySelector('#outline-content');
  content.replaceChildren();
  const sections = outline && Array.isArray(outline.sections) ? outline.sections : [];
  const rerunStatus = document.querySelector('#outline-rerun-status');
  if (rerunStatus) rerunStatus.textContent = '';
  if (!sections.length) {
    const empty = document.createElement('p');
    empty.className = 'outline-empty';
    empty.textContent = 'AIアウトラインはまだありません。右上の「アウトラインを再実行」で、保存済みの文字起こしから作成できます。';
    content.append(empty);
    view.hidden = false;
    return;
  }
  if (typeof outline.summary === 'string' && outline.summary.trim()) {
    const overall = document.createElement('section');
    overall.className = 'outline-overall-summary';
    const label = document.createElement('h4');
    label.textContent = '全体要約';
    const text = document.createElement('p');
    text.textContent = outline.summary;
    overall.append(label, text);
    content.append(overall);
  }
  const segments = (currentJob && Array.isArray(currentJob.segments) ? currentJob.segments : [])
    .slice().sort((a, b) => Number(a.start || 0) - Number(b.start || 0));
  const timed = segments.filter(analysisEvidenceTimeValid);
  const mediaLength = mediaPlayer && Number.isFinite(mediaPlayer.duration) ? mediaPlayer.duration : 0;
  const wholeEnd = Math.max(mediaLength, ...timed.map(segment => segment.end), 0);
  if (timed.length) {
    const all = outlineSpeechStats(timed, 0, wholeEnd, true);
    const totals = document.createElement('section');
    totals.className = 'outline-totals';
    const label = document.createElement('h4');
    label.textContent = '全体の発話量・空白時間';
    totals.append(label, outlineStatChips(all));
    if (timed.length < segments.length) {
      const note = document.createElement('small');
      note.textContent = `時刻のない発話 ${segments.length - timed.length}件は時間の集計に含めていません。`;
      totals.append(note);
    }
    content.append(totals);
  }
  // Meetings: decisions found in the minutes are listed up front and again under
  // the agenda item they were made in. They are rule-based candidates.
  const decisions = ((currentJob && currentJob.meeting_minutes && currentJob.meeting_minutes.decisions) || [])
    .filter(item => item && item.text);
  const decisionLine = decision => {
    const line = document.createElement('div');
    line.className = 'outline-decision';
    const play = document.createElement('button');
    play.type = 'button';
    play.className = 'outline-utterance-time';
    play.textContent = formatTime(decision.evidence_start);
    if (decision.evidence_segment_id) play.addEventListener('click', () => playSegment(decision.evidence_segment_id));
    else play.disabled = true;
    const text = document.createElement('span');
    text.textContent = `${decision.speaker ? decision.speaker + '：' : ''}${decision.text}`;
    line.append(play, text);
    return line;
  };
  if (decisions.length) {
    const box = document.createElement('section');
    box.className = 'outline-decisions';
    const label = document.createElement('h4');
    label.textContent = `決まったこと（候補 ${decisions.length}件）`;
    box.append(label);
    decisions.forEach(decision => box.append(decisionLine(decision)));
    const note = document.createElement('small');
    note.textContent = '「決定」「にします」などの表現から自動抽出した候補です。時刻を押すと元の発話を再生します。';
    box.append(note);
    content.append(box);
  }
  sections.forEach((section, index) => {
    const row = document.createElement('details');
    row.className = 'outline-section';
    const sectionDecisions = decisions.filter(item => Number(item.evidence_start) >= (Number(section.start) || 0)
      && (index === sections.length - 1 ? Number(item.evidence_start) <= Number(section.end)
        : Number(item.evidence_start) < Number(section.end)));
    const head = document.createElement('summary');
    const time = document.createElement('span');
    time.className = 'outline-time';
    time.textContent = `${formatTime(section.start)}–${formatTime(section.end)}`;
    const heading = document.createElement('div');
    heading.className = 'outline-section-head';
    const title = document.createElement('h4');
    title.textContent = section.title || '議題';
    heading.append(title);
    const last = index === sections.length - 1;
    const stats = outlineSpeechStats(timed, Number(section.start) || 0, Number(section.end) || 0, last);
    if (timed.length) heading.append(outlineStatChips(stats));
    if (sectionDecisions.length) {
      const badge = document.createElement('span');
      badge.className = 'outline-decision-badge';
      badge.textContent = `決定 ${sectionDecisions.length}`;
      heading.append(badge);
    }
    head.append(time, heading);

    const body = document.createElement('div');
    body.className = 'outline-section-body';
    const list = document.createElement('ul');
    (section.bullets || []).forEach(value => {
      const item = document.createElement('li');
      item.textContent = value;
      list.append(item);
    });
    body.append(list);
    if (sectionDecisions.length) {
      const decided = document.createElement('div');
      decided.className = 'outline-decisions-inline';
      const label = document.createElement('small');
      label.textContent = 'この議題で決まったこと（候補）';
      decided.append(label);
      sectionDecisions.forEach(decision => decided.append(decisionLine(decision)));
      body.append(decided);
    }
    row.append(head, body);
    // The utterances behind the agenda item are built on first open.
    row.addEventListener('toggle', () => {
      if (!row.open || body.querySelector('.outline-utterances')) return;
      const inside = timed.filter(segment => segment.start >= (Number(section.start) || 0)
        && (last ? segment.start <= Number(section.end) : segment.start < Number(section.end)));
      const box = document.createElement('div');
      box.className = 'outline-utterances';
      const caption = document.createElement('small');
      caption.textContent = inside.length ? `この区間の発話（${inside.length}件・時刻を押すと再生）` : 'この区間に時刻付きの発話はありません。';
      box.append(caption);
      inside.forEach(segment => {
        const line = document.createElement('div');
        line.className = 'outline-utterance';
        const play = document.createElement('button');
        play.type = 'button';
        play.className = 'outline-utterance-time';
        play.textContent = formatTime(segment.start);
        play.addEventListener('click', () => playSegment(segment.id));
        const who = document.createElement('strong');
        who.textContent = displaySpeakerName(segment.speaker);
        const text = document.createElement('span');
        text.textContent = segment.text || '';
        line.append(play, who, text);
        box.append(line);
      });
      body.append(box);
    });
    content.append(row);
  });
  view.hidden = false;
}

function formatSpan(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const h = Math.floor(total / 3600), m = Math.floor((total % 3600) / 60), s = total % 60;
  if (h) return `${h}時間${m}分`;
  return m ? `${m}分${String(s).padStart(2, '0')}秒` : `${s}秒`;
}

// Speech is the union of the timed segments inside [from, to], so overlapping
// speakers are not counted twice; silence is whatever is left of the range.
function outlineSpeechStats(timed, from, to, inclusiveEnd) {
  const spans = [];
  let count = 0, characters = 0;
  timed.forEach(segment => {
    const start = Math.max(from, segment.start), end = Math.min(to, segment.end);
    if (end > start) spans.push([start, end]);
    if (segment.start >= from && (inclusiveEnd ? segment.start <= to : segment.start < to)) {
      count += 1;
      characters += String(segment.text || '').length;
    }
  });
  spans.sort((a, b) => a[0] - b[0]);
  let speech = 0, cursor = from;
  spans.forEach(([start, end]) => {
    const from_ = Math.max(start, cursor);
    if (end > from_) { speech += end - from_; cursor = end; }
  });
  const total = Math.max(0, to - from);
  return {total, speech, silence: Math.max(0, total - speech), count, characters};
}

function outlineStatChips(stats) {
  const host = document.createElement('div');
  host.className = 'outline-stats';
  const share = stats.total > 0 ? ` (${Math.round(stats.speech / stats.total * 100)}%)` : '';
  [
    `全体 ${formatSpan(stats.total)}`,
    `発話 ${formatSpan(stats.speech)}${share}`,
    `空白 ${formatSpan(stats.silence)}`,
    `${stats.count}発話・${stats.characters}文字`,
  ].forEach(text => {
    const chip = document.createElement('span');
    chip.textContent = text;
    host.append(chip);
  });
  return host;
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

function renderSpeakerTimeline() {
  if (!window.GurumojiTimeline || !currentJob) return;
  if (!speakerTimelineView) {
    speakerTimelineView = window.GurumojiTimeline.create(document.querySelector('#speaker-timeline'), {
      name: displaySpeakerName,
      color: label => {
        const profiles = currentJob?.speaker_profiles || {};
        return Object.hasOwn(profiles, label) ? profiles[label]?.theme_color : '';
      },
      follow: () => document.querySelector('#media-autoscroll')?.checked !== false,
      select: segmentId => {
        if (!currentJob?.segments.some(segment => segment.id === segmentId)) return;
        // 絞り込みで隠れた発話も、タイムラインから選んで編集できるようにする。
        for (const id of ['segment-keyword', 'segment-speaker-filter', 'segment-emotion-filter', 'segment-jev-filter']) {
          const input = document.getElementById(id);
          if (input) input.value = '';
        }
        selectedSegmentId = segmentId;
        renderSegments();
        selectSegmentForEdit(segmentId);
      },
      seek: (seconds, play) => {
        if (!mediaPlayer) return;
        mediaPlaybackFromTimeline = true;
        playbackStopAt = null;
        const limit = Number.isFinite(mediaPlayer.duration) ? mediaPlayer.duration : seconds;
        mediaPlayer.currentTime = Math.min(seconds, limit);
        document.querySelector('#media-caption').textContent = '再生位置 ' + formatTime(seconds);
        syncMediaPlayback(mediaPlayer.currentTime);
        if (play) {
          const promise = mediaPlayer.play();
          if (promise) promise.catch(() => {});
        }
      }
    });
  }
  speakerTimelineView?.render(currentJob, selectedSegmentId);
  if (mediaPlayer) speakerTimelineView?.updateTime(mediaPlayer.currentTime, mediaPlayer.duration);
}
