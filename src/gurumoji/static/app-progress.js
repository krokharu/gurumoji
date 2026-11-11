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
    speakerRegistryBaseline = deepCopy(speakerRegistry);
    speakerSaveConflict = false;
    document.querySelector('#speaker-draft-recovery').hidden = true;
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

function downloadUnsavedDraft(kind) {
  if (kind === 'transcript') captureSessionProfile();
  const data = kind === 'transcript'
    ? {schema: 'gurumoji.unsaved-transcript.v1', item_id: currentJobId, base_revision: currentJob?.revision_count, draft: deepCopy(currentJob)}
    : {schema: 'gurumoji.unsaved-speakers.v1', base_revision: speakerRegistryRevision, speakers: deepCopy(speakerRegistry), delete_ids: [...speakerRegistryDeletedIds]};
  const blob = new Blob([JSON.stringify({...data, exported_at: new Date().toISOString()}, null, 2)], {type: 'application/json;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `gurumoji-unsaved-${kind}-${Date.now()}.json`;
  document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function showDraftRecovery(kind) {
  const panel = document.querySelector(kind === 'transcript' ? '#result-draft-recovery' : '#speaker-draft-recovery');
  if (!panel) return;
  panel.hidden = false;
  const count = kind === 'transcript'
    ? (currentJob?.segments || []).filter(segment => JSON.stringify(segment) !== JSON.stringify((currentJobBaseline?.segments || []).find(item => item.id === segment.id))).length
    : speakerRegistry.filter(record => JSON.stringify(record) !== JSON.stringify(speakerRegistryBaseline.find(item => item.id === record.id))).length;
  const deleted = kind === 'transcript' ? (currentJobBaseline?.segments || []).filter(item => !(currentJob?.segments || []).some(segment => segment.id === item.id)).length : speakerRegistryDeletedIds.size;
  panel.querySelector('[data-draft-count]').textContent = `追加・変更 ${count}件 / 削除 ${deleted}件。会話設定も含む未保存内容全体をJSONで退避できます。退避後に再読み込みし、最新の内容と照合してください。自動上書きはしません。`;
  panel.querySelector('button')?.focus();
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
        ? '別の画面で話者管理が更新されています。未保存内容をJSONで退避してから再読み込みしてください。'
        : '話者管理データを保存できませんでした。';
      if (response.status === 409) { speakerSaveConflict = true; showDraftRecovery('speakers'); }
      throw new Error(response.status === 409 ? conflict : (data.error || conflict));
    }
    speakerRegistryRevision = Number(data.registry_revision || speakerRegistryRevision);
    if (speakerRegistryMutationGeneration === saveGeneration) {
      speakerRegistry = data.speakers || [];
      speakerRegistryBaseline = deepCopy(speakerRegistry);
      speakerSaveConflict = false;
      document.querySelector('#speaker-draft-recovery').hidden = true;
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

function cancelSpeakerImport() {
  pendingSpeakerImport = null;
  document.querySelector('#speaker-import-preview').hidden = true;
  document.querySelector('#speaker-csv-input').value = '';
}

function handleInputFileSelection() {
  setAlert(pathError, '');
  const file = inputFile.files && inputFile.files[0];
  if (file) {
    if (!/\.(mp4|m4v|mov|mkv|wav|mp3|m4a|flac)$/i.test(file.name)) {
      inputFile.value = '';
      sourcePath.value = '';
      hideSourcePreview();
      pathDetail.textContent = 'ファイルが選択されていません';
      setAlert(pathError, '対応している動画・音声ファイルを選択してください。', true);
      updateCreateSummary();
      return;
    }
    sourcePath.value = '';
    pathDetail.textContent = browserFilePickerOnly
      ? `${file.name} / ${formatBytes(file.size)} — Colabへ一時アップロードして処理します`
      : `${file.name} / ${formatBytes(file.size)} — Gurumoji実行環境へ一時コピーして処理します`;
    hideSourcePreview();
  } else if (!sourcePath.value.trim()) {
    pathDetail.textContent = 'ファイルが選択されていません';
  }
  updateCreateSummary();
}

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
  document.querySelectorAll(`[data-device-dot="${kind}"]`).forEach(element => {
    element.classList.remove('checking', 'available', 'unavailable');
    element.classList.add(available ? 'available' : 'unavailable');
    element.title = title;
  });
}

function applyMachineProfile(machine, {reset = false} = {}) {
  if (!machine) return;
  lastMachineProfile = machine;
  if (reset) manuallySelectedMachineFields.clear();
  const changes = [];
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
    if (!gpu.cuda_available && select.value === 'cuda') {
      select.value = 'cpu';
      changes.push('選択したGPUを利用できないためCPUに変更しました');
    }
  });

  if (modelSelect && !manuallySelectedMachineFields.has(modelSelect.id) && [...modelSelect.options].some(option => option.value === recommended.model_name)) {
    modelSelect.value = recommended.model_name;
  }
  if (transcriptionDevice && !manuallySelectedMachineFields.has(transcriptionDevice.id) && [...transcriptionDevice.options].some(option => (
    option.value === recommended.device && !option.disabled
  ))) {
    transcriptionDevice.value = recommended.device;
  }
  if (diarizationDevice && !manuallySelectedMachineFields.has(diarizationDevice.id) && [...diarizationDevice.options].some(option => (
    option.value === recommended.diarization_device && !option.disabled
  ))) {
    diarizationDevice.value = recommended.diarization_device;
  }

  if (recommendation) {
    const deviceLabel = recommended.device === 'cuda' ? 'GPU' : 'CPU';
    const diarizationLabel = recommended.diarization_device === 'cuda' ? 'GPU' : 'CPU';
    recommendation.textContent = recommended.model_name
      ? `推奨設定（手動選択を保持）: ${recommended.model_name} / 文字起こし ${deviceLabel} / 話者分離 ${diarizationLabel}。${recommended.reason || ''}`
      : '';
  }
  setAlert(document.querySelector('#machine-selection-message'), [...new Set(changes)].join('。'), Boolean(changes.length));
  syncTranscriptionBackend();
  updateCreateSummary();
}

async function loadConfig() {
  const message = document.querySelector('#token-message');
  if (!message) return;
  configLoadState = 'loading';
  updateCreateSummary();
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await apiFetch('/api/config', {cache: 'no-store', signal: controller.signal});
    const data = await readJsonResponse(response);
    if (!response.ok || !data.ok) throw new Error(data.error || '設定を取得できません');
    tokenConfigSnapshot = data && typeof data === 'object' ? data : {};
    configLoadState = 'loaded';
    applyMachineProfile(data.machine);
    applyObsidianWatcherStatus(data.obsidian_watcher);
    const runtime = data.runtime || {};
    browserFilePickerOnly = Boolean(runtime.browser_upload);
    if (browsePathButton) {
      browsePathButton.dataset.pickerMode = browserFilePickerOnly ? 'browser' : 'native';
      updateBrowseButtonLabel();
    }
    if (!response.ok || !data.ok) throw new Error(data.error || '設定を取得できません');
    const recognized = [];
    const localLlmShortLabel = String(data.local_llm_short_label || 'LM Studio');
    [
      ['hf', 'huggingface', 'Hugging Face'],
      ['openai', 'openai', 'OpenAI'],
      ['google', 'google', 'Google'],
      ['typesafe', 'typesafe', 'TypeSafe Jev'],
      ['lmstudio', 'lmstudio', localLlmShortLabel]
    ].forEach(([id, key, label]) => {
      // The hero pills are hidden on phones; the mobile header repeats them (UX-10).
      document.querySelectorAll(`#status-${id}, [data-status-provider="${id}"]`).forEach(pill => {
        pill.classList.remove('loading', 'ready', 'missing');
        pill.classList.add(data[key] ? 'ready' : 'missing');
        pill.textContent = data[key] ? `${label} ✓` : label;
        const lmStudioStatus = key === 'lmstudio' && data.lmstudio_status && typeof data.lmstudio_status === 'object'
          ? data.lmstudio_status : null;
        pill.title = lmStudioStatus
          ? String(lmStudioStatus.message || '')
          : (data[key] ? '設定済み' : '未設定');
        if (pill.dataset.modelProvider) {
          const currentModel = String(data[`${key}_model`] || '').trim();
          pill.dataset.currentModel = currentModel;
          pill.title = key === 'lmstudio'
            ? `${lmStudioStatus && lmStudioStatus.message || 'ローカルLLMの状態を確認できません。'}${currentModel ? ` 現在: ${currentModel}` : ''}`
            : data[key]
            ? `クリックしてモデルを変更（現在: ${currentModel || 'tokens.json の設定'}）`
            : `${label} APIキーがtokens.jsonに設定されていません`;
        }
      });
      document.querySelectorAll(`[data-provider-model="${key}"]`).forEach(element => {
        element.textContent = String(data[`${key}_model`] || '').trim() || '未設定';
      });
      document.querySelectorAll(`[data-connection-dot="${id}"]`).forEach(dot => {
        dot.classList.toggle('ready', Boolean(data[key]));
        dot.classList.toggle('missing', !data[key]);
      });
      if (data[key]) recognized.push(label);
    });
    const outputDir = document.querySelector('#output-dir');
    if (outputDir) outputDir.placeholder = data.default_output_dir;
    message.textContent = recognized.length
      ? `利用可能: ${recognized.join(' / ')}。発光している項目を使用できます。`
      : 'トークンを認識できません。tokens.json を確認してください。';
    applyLmStudioDefaults(data);
    syncAiFields();
    updateCreateSummary();
  } catch (error) {
    configLoadState = 'error';
    message.textContent = error.name === 'AbortError'
      ? '設定確認がタイムアウトしました。アプリを再起動して http://127.0.0.1:7860 を開き直してください。'
      : error.message;
    message.style.color = '#913733';
  } finally {
    window.clearTimeout(timeoutId);
    updateCreateSummary();
  }
}

function applyObsidianWatcherStatus(watcher) {
  // OBS-09: a watcher that stopped at startup must not look like an idle one.
  if (!watcher || typeof watcher !== 'object' || !watcher.state) return;
  const failed = ['failed', 'polling_failed'].includes(watcher.state);
  // OBS-10: a parent folder opened as a Vault mixes the app's notes into it.
  const warnings = Array.isArray(watcher.warnings) ? watcher.warnings.filter(Boolean) : [];
  document.querySelectorAll('[data-obsidian-watcher-pill]').forEach(pill => {
    pill.classList.remove('loading', 'ready', 'missing');
    pill.classList.add(watcher.state === 'running' && !warnings.length ? 'ready' : failed || warnings.length ? 'missing' : 'loading');
    pill.textContent = watcher.state === 'running' ? 'Obsidian監視 ✓' : 'Obsidian監視';
  });
  document.querySelectorAll('[data-obsidian-watcher-detail]').forEach(detail => {
    detail.textContent = [watcher.message, watcher.detail, ...warnings.map(text => `注意: ${text}`)].filter(Boolean).join(' ');
  });
}

function applyLmStudioDefaults(config) {
  // A ready, explicitly selected local model is an opt-in.  Make the
  // transcription form ready to use it without requiring three more clicks.
  // Do not choose the local server when it is offline or a model was not
  // selected yet: either state would make the default form fail at submission.
  if (!aiProvider || aiProviderManuallySelected || aiProvider.value !== 'none' || !config || !config.lmstudio || !String(config.lmstudio_model || '').trim()) return;
  aiProvider.value = 'lmstudio';
  applyTranscriptFinishingPreset();
  syncAiFields();
  updateCreateSummary();
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
  if (fixedSpeakerCountInput) fixedSpeakerCountInput.disabled = running || !isSpeakerCountFixed();
  if (cancelButton) cancelButton.disabled = !running;
  syncQuietFields();
  syncEmotionFields();
  syncAiFields();
  updateCreateSummary();
  syncCreateViewState();
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
  if (jevCompare) {
    const jevDisabled = disabled || !tokenConfigSnapshot.typesafe;
    if (jevDisabled) jevCompare.checked = false;
    jevCompare.disabled = jevDisabled;
    const row = jevCompare.closest('.check-row');
    if (row) row.classList.toggle('disabled', jevDisabled);
    if (jevConfigStatus) {
      jevConfigStatus.textContent = tokenConfigSnapshot.typesafe
        ? `TypeSafe ${tokenConfigSnapshot.typesafe_model || 'jev-latest'} を使用できます。`
        : 'おすすめのJev判定／Jev比較には tokens.json の typesafe_api_key が必要です。';
    }
  }
  if (typeof syncAiEffortSettings === 'function') syncAiEffortSettings();
}

function selectedTranscriptFinishingMode() {
  const selected = transcriptFinishingModeInputs.find(input => input.checked);
  return selected ? selected.value : 'recommended';
}

function applyTranscriptFinishingModeChange() {
  const mode = selectedTranscriptFinishingMode();
  if (mode === lastTranscriptFinishingMode) return;
  const controls = [cleanTranscript, detectNames, createOutline, jevCompare, finishInObsidian];
  transcriptFinishingPreferences.set(lastTranscriptFinishingMode, controls.map(input => Boolean(input?.checked)));
  const saved = transcriptFinishingPreferences.get(mode);
  applyTranscriptFinishingPreset();
  if (saved) controls.forEach((input, index) => { if (input) input.checked = saved[index]; });
  lastTranscriptFinishingMode = mode;
}

function applyTranscriptFinishingPreset() {
  const mode = selectedTranscriptFinishingMode();
  const hasAi = Boolean(aiProvider && aiProvider.value !== 'none');
  if (cleanTranscript) cleanTranscript.checked = mode === 'advanced' && hasAi;
  if (detectNames) detectNames.checked = mode !== 'off' && hasAi;
  if (createOutline) createOutline.checked = mode === 'advanced' && hasAi;
  // An additional external destination must be an explicit choice.
  if (jevCompare && (mode !== 'advanced' || !hasAi)) jevCompare.checked = false;
  if (finishInObsidian && mode !== 'recommended') finishInObsidian.checked = false;
  document.querySelectorAll('[data-advanced-finishing-only]').forEach(row => {
    row.hidden = mode !== 'advanced';
  });
  document.querySelectorAll('[data-speaker-finishing-option]').forEach(row => {
    row.hidden = mode === 'off';
  });
  if (finishingModeHint) {
    finishingModeHint.textContent = {
      recommended: 'AI仕上げを使う場合は、必要な箇所だけ読みやすく整えます。Obsidianに保存する場合は、あとで仕上げられます。',
      advanced: '文章全体を見直します。話者の確認や比較など、追加の処理も選べます。',
      off: '文章は変更せず、認識結果をそのまま残します。'
    }[mode] || '';
  }
}

function selectDefaultAiOptions() {
  if (!aiProvider) return;
  applyTranscriptFinishingPreset();
  syncAiFields();
  updateCreateSummary();
}

function syncFinishingMode() {
  const mode = selectedTranscriptFinishingMode();
  document.querySelectorAll('[data-advanced-finishing-only]').forEach(row => {
    row.hidden = mode !== 'advanced';
  });
  document.querySelectorAll('[data-speaker-finishing-option]').forEach(row => {
    row.hidden = mode === 'off';
  });
}

function syncSidebarPanels() {
  sidebarPanelButtons.forEach(button => {
    const panel = settingsPanels.find(item => item.dataset.settingsPanel === button.dataset.openPanel);
    button.classList.toggle('active', Boolean(panel && panel.open));
  });
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
  if (!activeJobId || !jobRunning) return;
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
  activeJobId = String(job.id);
  storePendingSubmissionId('');
  clearPollTimer();
  renderProgress(job);
  showProgressCard({scroll});
  if (active) {
    storeActiveJobId(activeJobId);
    setRunning(true);
    if (cancelButton) cancelButton.disabled = !cancellable;
    schedulePoll();
    return true;
  }
  storeActiveJobId('');
  activeJobId = null;
  setRunning(false);
  if (cancelButton) cancelButton.disabled = true;
  if (job.status === 'completed') {
    // 完了を確認できるよう処理画面を保ち、結果は利用者の操作で開く。
    completedJob = job;
    syncCreateViewState();
  }
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
      activeJobId = storedId;
      storeActiveJobId(storedId);
      setRunning(true);
      showProgressCard();
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
    showProgressCard();
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
    activeJobId = null;
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
    activeJobId = null;
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
    syncCreateViewState();
    document.dispatchEvent(new CustomEvent('gurumoji-queue-blocked'));
    if (runningView && !runningView.hidden) showView('new');
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

async function pollJob() {
  if (!activeJobId) return;
  const requestedJobId = activeJobId;
  try {
    const response = await apiFetch(`/api/jobs/${encodeURIComponent(requestedJobId)}`, {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (requestedJobId !== activeJobId) return;
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
      activeJobId = null;
      setRunning(false);
      if (cancelButton) cancelButton.disabled = true;
      throw new Error(data.error || '実行中ジョブが見つかりません。アプリを再起動した可能性があります。');
    }
    if (!response.ok) throw new Error(data.error || '進捗を取得できません。');
    pollFailureCount = 0;
    resumeJob(data);
  } catch (error) {
    if (!activeJobId || !jobRunning) {
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
  const visible = ['openai', 'google', 'lmstudio'].includes(provider) && requestCount > 0;
  root.hidden = !visible;
  if (!visible) return;
  const format = value => value == null ? '未計測' : new Intl.NumberFormat('ja-JP').format(Math.max(0, Number(value) || 0));
  const providerElement = root.querySelector('[data-ai-provider]');
  const modelElement = root.querySelector('[data-ai-model]');
  const inputElement = root.querySelector('[data-ai-input]');
  const outputElement = root.querySelector('[data-ai-output]');
  const totalElement = root.querySelector('[data-ai-total]');
  const requestsElement = root.querySelector('[data-ai-requests]');
  if (providerElement) providerElement.textContent = {
    openai: 'OpenAI',
    google: 'Google Gemini',
    lmstudio: String(tokenConfigSnapshot.local_llm_label || 'LM Studio（ローカル）')
  }[provider] || 'AI';
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
  if (unreported) unreported.hidden = Boolean(usage.reported) &&
    [usage.input_tokens, usage.output_tokens, usage.total_tokens].every(value => value != null);
}
