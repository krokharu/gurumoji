function analysisSegmentMatches(segment) {
  const query = analysisState.segmentQuery.trim().toLocaleLowerCase();
  const annotation = analysisState.annotations[segment.id] || {};
  const annotated = Boolean(
    (annotation.codes || []).length
    || (annotation.interaction_tags || []).length
    || annotation.elicitation && annotation.elicitation !== 'unknown'
    || (annotation.interaction_links || []).length
    || annotation.memo
    || annotation.dialogue_act
    || annotation.importance_score !== undefined && annotation.importance_score !== null
    || annotation.review_score !== undefined && annotation.review_score !== null
    || annotation.sensitivity_score !== undefined && annotation.sensitivity_score !== null
    || annotation.classification_status && annotation.classification_status !== 'unreviewed'
    || annotation.classification_note
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
  const classificationResult = ((analysisState.data.segment_classification || {}).result || {});
  const proposalById = new Map((classificationResult.segments || []).map(row => [String(row.segment_id), row]));
  visible.slice(0, limit).forEach(segment => {
    const annotation = analysisState.annotations[segment.id] || {
      codes: [], interaction_tags: [], elicitation: 'unknown', interaction_links: [],
      dialogue_act: '', importance_score: null, review_score: null, sensitivity_score: null,
      classification_status: 'unreviewed', classification_note: '',
      memo: '', important: false, excluded: false
    };
    const card = analysisElement('article', 'analysis-segment-card');
    card.dataset.analysisSegmentCard = segment.id;
    const header = analysisElement('header');
    const meta = analysisElement('div');
    const speaker = analysisElement('strong', '', segment.speaker_name || segment.speaker || '話者未判定');
    speaker.style.borderColor = safeAnalysisColor(segment.color);
    meta.append(
      analysisElement('span', 'analysis-segment-time', `#${segment.utterance_order || '—'}`),
      analysisElement('span', 'analysis-segment-time', `${formatTime(segment.start || 0)}–${formatTime(segment.end || 0)}`),
      speaker
    );
    const status = analysisElement('div', 'analysis-segment-status');
    if (annotation.important) status.append(analysisElement('span', 'important', '重要引用'));
    if (annotation.excluded) status.append(analysisElement('span', 'excluded', '分析除外'));
    header.append(meta, status);
    const quote = analysisElement('p', 'analysis-segment-text', segment.text || '（本文なし）');
    card.append(header, quote);

    const proposal = proposalById.get(String(segment.id));
    if (proposal) {
      const proposalGrid = analysisElement('div', 'segment-proposal-grid');
      const proposalCard = (label, value, source) => {
        const item = analysisElement('article');
        item.append(analysisElement('strong', '', label), analysisElement('span', '', value || '提案なし'));
        if (source && source.dialogue_act) {
          const apply = analysisElement('button', 'secondary-button small', '手動欄へ反映');
          apply.type = 'button';
          apply.dataset.applyClassificationProposal = source === proposal.llm ? 'llm' : 'template';
          apply.dataset.analysisSegmentId = segment.id;
          item.append(apply);
        }
        return item;
      };
      const scoreText = source => source && source.dialogue_act_label
        ? `${source.dialogue_act_label} / 重要${source.importance_score ?? '—'}・要確認${source.review_score ?? '—'}・機密${source.sensitivity_score ?? '—'}`
        : '';
      proposalGrid.append(
        proposalCard('テンプレート', scoreText(proposal.template), proposal.template),
        proposalCard('Jev', scoreText(proposal.llm), proposal.llm),
        proposalCard('Transformer話題', (proposal.transformer || {}).topic_label || '', null)
      );
      card.append(proposalGrid);
    }

    const classificationControls = analysisElement('div', 'segment-manual-classification');
    const dialogueAct = document.createElement('select');
    dialogueAct.add(new Option('未確定', ''));
    Object.entries(dialogueActLabels).forEach(([value, label]) => dialogueAct.add(new Option(label, value)));
    dialogueAct.value = annotation.dialogue_act || '';
    dialogueAct.dataset.analysisSegmentId = segment.id;
    dialogueAct.dataset.analysisAnnotationField = 'dialogue_act';
    classificationControls.append(analysisField('手動：発話種別', dialogueAct));
    [
      ['importance_score', '手動：重要度'],
      ['review_score', '手動：要確認度'],
      ['sensitivity_score', '手動：機密らしさ']
    ].forEach(([field, label]) => {
      const input = document.createElement('input');
      input.type = 'number'; input.min = '0'; input.max = '100'; input.step = '1';
      input.value = annotation[field] === undefined || annotation[field] === null ? '' : String(annotation[field]);
      input.dataset.analysisSegmentId = segment.id;
      input.dataset.analysisAnnotationField = field;
      classificationControls.append(analysisField(label, input, '0〜100。空欄は未確定。'));
    });
    const classificationStatus = document.createElement('select');
    [['unreviewed', '未確認'], ['draft', '確認途中'], ['reviewed', '確認済み']]
      .forEach(([value, label]) => classificationStatus.add(new Option(label, value)));
    classificationStatus.value = annotation.classification_status || 'unreviewed';
    classificationStatus.dataset.analysisSegmentId = segment.id;
    classificationStatus.dataset.analysisAnnotationField = 'classification_status';
    classificationControls.append(analysisField('判定状態', classificationStatus));
    card.append(classificationControls);

    const classificationNote = document.createElement('textarea');
    classificationNote.rows = 2;
    classificationNote.maxLength = 5000;
    classificationNote.value = annotation.classification_note || '';
    classificationNote.placeholder = '自動提案を採用・修正・保留した根拠';
    classificationNote.dataset.analysisSegmentId = segment.id;
    classificationNote.dataset.analysisAnnotationField = 'classification_note';
    card.append(analysisField('分類確認メモ', classificationNote));

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

    const elicitation = document.createElement('select');
    [
      ['unknown', '不明・未確認'], ['spontaneous', '自発的な発言'],
      ['moderator_prompted', '司会者の質問・働きかけを受けた発言'],
      ['participant_prompted', '他の参加者の働きかけを受けた発言'],
      ['other_prompted', 'その他の働きかけを受けた発言']
    ].forEach(([value, label]) => elicitation.add(new Option(label, value)));
    elicitation.value = annotation.elicitation || 'unknown';
    elicitation.dataset.analysisSegmentId = segment.id;
    elicitation.dataset.analysisAnnotationField = 'elicitation';
    card.append(analysisField('発話のきっかけ', elicitation, '自発か、誰の働きかけを受けたかを記録します。不明は推測で選びません。'));

    const evidenceGroup = analysisElement('details', 'analysis-interaction-group');
    evidenceGroup.append(analysisElement('summary', '', '根拠発話との相互作用リンク'));
    evidenceGroup.append(analysisElement('p', 'analysis-inline-note', '同意・反論・補足・変化は、対象となる発話を選び、根拠メモとともに結びます。単独タグだけからは意見形成を結論づけません。'));
    const linkControls = analysisElement('div', 'analysis-link-controls');
    const target = document.createElement('select');
    target.dataset.analysisInteractionTarget = segment.id;
    target.add(new Option('対象発話を選択', ''));
    const currentIndex = segments.findIndex(item => item.id === segment.id);
    segments.slice(Math.max(0, currentIndex - 12), currentIndex + 13)
      .filter(item => item.id !== segment.id)
      .forEach(item => target.add(new Option(
        `#${item.utterance_order || '—'} ${item.speaker_name || item.speaker}: ${String(item.text || '').slice(0, 42)}`,
        item.id
      )));
    const relation = document.createElement('select');
    relation.dataset.analysisInteractionRelation = segment.id;
    [
      ['response', '応答'], ['agreement', '同意・賛同'], ['disagreement', '不一致・反対'],
      ['differentiation', '立場の差異化'], ['change', '意見の変化'], ['word_use', '言葉の意味の違い'],
      ['repetition', '反復・強調'], ['engagement', '補足・発展']
    ].forEach(([value, label]) => relation.add(new Option(label, value)));
    const evidenceMemo = document.createElement('input');
    evidenceMemo.type = 'text';
    evidenceMemo.maxLength = 2000;
    evidenceMemo.placeholder = '根拠メモ（任意）';
    evidenceMemo.dataset.analysisInteractionMemo = segment.id;
    const addLink = analysisElement('button', 'secondary-button small', 'リンクを追加');
    addLink.type = 'button';
    addLink.dataset.analysisAddInteractionLink = segment.id;
    linkControls.append(target, relation, evidenceMemo, addLink);
    evidenceGroup.append(linkControls);
    const links = Array.isArray(annotation.interaction_links) ? annotation.interaction_links : [];
    if (links.length) {
      const list = analysisElement('ul', 'analysis-link-list');
      const relationLabels = {
        response: '応答', agreement: '同意・賛同', disagreement: '不一致・反対',
        differentiation: '立場の差異化', change: '意見の変化', word_use: '言葉の意味の違い',
        repetition: '反復・強調', engagement: '補足・発展'
      };
      links.forEach((link, index) => {
        const targetSegment = segments.find(item => item.id === link.target_segment_id) || {};
        const label = analysisElement('span', '', `${relationLabels[link.relation] || link.relation}：#${targetSegment.utterance_order || '—'} ${targetSegment.speaker_name || targetSegment.speaker || link.target_segment_id}`);
        const removeLink = analysisElement('button', 'secondary-button small', '削除');
        removeLink.type = 'button';
        removeLink.dataset.analysisRemoveInteractionLink = 'true';
        removeLink.dataset.analysisInteractionSource = segment.id;
        removeLink.dataset.analysisInteractionIndex = String(index);
        const row = analysisElement('li');
        row.append(label, removeLink);
        if (link.evidence_memo) row.append(analysisElement('small', '', link.evidence_memo));
        list.append(row);
      });
      evidenceGroup.append(list);
    }
    card.append(evidenceGroup);

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

function renderTranscriptPreparation() {
  const prepared = analysisState.data.manual?.preparation;
  const panel = analysisCardPanel('文字起こしを分析用データに整える', 'manual', 'prepared_turns', true);
  if (!prepared) return panel.panel;
  const key = `${analysisState.itemId}:${prepared.revision}:${prepared.source_hash}`;
  if (preparationDraft && preparationDirty && preparationDraft.source_hash === prepared.source_hash
      && preparationDraft.key.startsWith(`${analysisState.itemId}:`)) {
    preparationDraft.key = key;
    preparationDraft.revision = prepared.revision;
  }
  if (!preparationDraft || preparationDraft.key !== key) {
    preparationDraft = {key, revision: prepared.revision, source_hash: prepared.source_hash,
      order_verified: prepared.order_verified, participant_count: prepared.participant_count,
      metadata_sources: prepared.metadata_sources || '', review_analysis: false, records: {}};
    prepared.rows.forEach(row => {
      preparationDraft.records[row.segment_id] = Object.fromEntries(
        ['text_status', 'role', 'speaker_verified', 'boundary_verified', 'source_locator', 'source_segment_ids']
          .map(field => [field, deepCopy(row[field])])
      );
    });
  }
  const statusLabels = {draft: '確認途中', confirmed: '本文・区切り確認済みの版', needs_review: '入力変更後・要再確認'};
  panel.body.append(analysisElement('p', '',
    `入力版 ${prepared.input_version ?? '未固定'} / ${statusLabels[prepared.status]}。内容分析の準備: ${prepared.content_ready_count}/${prepared.rows.length}発言、相互作用の準備: ${prepared.interaction_ready_count}/${prepared.rows.length}発言。`));
  panel.body.append(analysisElement('p', 'analysis-section-help',
    '取込原本は上書きしません。本文・話者・区切りは既存の文字起こし編集画面で修正してください。以下は修正した版の確認記録です。音声未照合や話者不明を確認済みとみなさず、資料がない人数は空欄にします。'));
  if (prepared.analysis_needs_review) panel.body.append(analysisElement('p', 'analysis-orphan-warning',
    '既存のコード・相互作用は要再確認です。入力版または確認状態が変わりました。保存するだけでは解除されません。'));
  const exportLink = analysisElement('a', 'analysis-export-link', '原本・全入力版・確認履歴 JSON');
  exportLink.href = `/api/library/${encodeURIComponent(analysisState.itemId)}/preparation/export.json`;
  exportLink.download = '';
  panel.body.append(exportLink);
  const edit = analysisElement('button', 'secondary-button', '文字起こし編集を開く');
  edit.type = 'button';
  edit.addEventListener('click', () => {
    if (preparationDirty || analysisState.dirty) {
      setAlert(document.querySelector('#analysis-message'), '先に準備記録と分析設定を保存してください。', true);
      return;
    }
    openLibraryItem(analysisState.itemId);
  });
  panel.body.append(edit);
  const control = (label, field, options, sid = null) => {
    const object = sid ? preparationDraft.records[sid] : preparationDraft;
    const input = document.createElement(options && typeof options === 'object' ? 'select' : options === 'textarea' ? 'textarea' : 'input');
    if (input.tagName === 'SELECT') Object.entries(options).forEach(([value, text]) => input.append(new Option(text, value)));
    else if (input.tagName === 'INPUT') input.type = options || 'text';
    const value = object[field];
    if (input.type === 'checkbox') input.checked = Boolean(value);
    else input.value = Array.isArray(value) ? value.join(', ') : value ?? '';
    input.dataset.preparationKey = `${sid || 'session'}:${field}`;
    input.addEventListener('input', () => {
      object[field] = input.type === 'checkbox' ? input.checked
        : field === 'participant_count' ? (input.value === '' ? null : Number(input.value))
        : field === 'source_segment_ids' ? input.value.split(',').map(v => v.trim()).filter(Boolean) : input.value;
      preparationDirty = true;
      analysisMutationGeneration += 1;
      document.querySelectorAll('[data-preparation-key]').forEach(peer => {
        if (peer === input || peer.dataset.preparationKey !== input.dataset.preparationKey) return;
        if (input.type === 'checkbox') peer.checked = input.checked;
        else peer.value = input.value;
      });
    });
    return analysisField(label, input);
  };
  panel.body.append(
    control('資料・確認根拠（研究目的・質問票・参加者名簿等の資料名と位置。実名は不要）', 'metadata_sources', 'textarea'),
    control('実際の参加人数（不明は空欄。発言者数とは別）', 'participant_count', 'number'),
    control('保存されている発言の順序を原資料と確認した', 'order_verified', 'checkbox')
  );
  const turns = analysisElement('details');
  turns.append(analysisElement('summary', '', `発言ごとの確認（${prepared.rows.length}件）`));
  prepared.rows.forEach(row => {
    const detail = analysisElement('details', 'analysis-segment-card');
    detail.append(analysisElement('summary', '', `#${row.order} ${row.speaker_id || '話者不明'} / ${row.segment_id}`));
    const text = analysisElement('p', 'analysis-segment-text', row.text);
    text.style.whiteSpace = 'pre-wrap';
    detail.append(text, analysisElement('p', 'analysis-section-help',
      `取込本文: ${row.original_text ?? '対応する取込本文なし'} / 時刻: ${row.start ?? '不明'}–${row.end ?? '不明'}`));
    const fields = analysisElement('div', 'analysis-settings-grid');
    fields.append(
      control('本文確認', 'text_status', {unreviewed: '未確認', transcript_checked: '逐語録を確認（音声未照合）', audio_verified: '音声・動画と照合済み', unclear: '聞き取り不明・要確認'}, row.segment_id),
      control('役割（初期値は不明）', 'role', {unknown: '不明', participant: '参加者', moderator: '司会者', observer: '観察者'}, row.segment_id),
      control('発言者を確認した', 'speaker_verified', 'checkbox', row.segment_id),
      control('一人の発言として区切りを確認した', 'boundary_verified', 'checkbox', row.segment_id),
      control('元資料の位置（行・ページ等）', 'source_locator', 'text', row.segment_id),
      control('分割・結合元の発言ID（カンマ区切り。不明は空欄）', 'source_segment_ids', 'text', row.segment_id)
    );
    detail.append(fields);
    turns.append(detail);
  });
  panel.body.append(turns);
  if (prepared.analysis_needs_review) panel.body.append(control(
    '現在の版で既存のコード・相互作用を研究者が再確認した（明示的に解除）', 'review_analysis', 'checkbox'));
  const message = analysisElement('p', 'analysis-section-help');
  message.setAttribute('role', 'status');
  for (const [label, confirm] of [['確認途中として保存', false], ['本文・区切りを確認して版を確定', true]]) {
    const button = analysisElement('button', 'secondary-button', label);
    button.type = 'button';
    button.dataset.preparationSave = String(confirm);
    button.addEventListener('click', async () => {
      if (preparationSaving) return;
      if (analysisState.dirty) {
        message.textContent = '先に未保存の分析設定・コードを保存してください。';
        return;
      }
      const itemId = analysisState.itemId;
      const payload = {...deepCopy(preparationDraft), confirm};
      const sent = JSON.stringify(preparationDraft);
      preparationSaving = true;
      message.textContent = '保存中…';
      try {
        const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/preparation`, {
          method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
        });
        const result = await readJsonResponse(response);
        if (!response.ok) throw new Error(result.error || '準備記録を保存できませんでした。');
        if (analysisState.itemId !== itemId) return;
        if (JSON.stringify(preparationDraft) !== sent) {
          preparationDraft.revision = result.revision;
          message.textContent = '保存しました。保存中の追加編集があるため、もう一度保存してください。';
          return;
        }
        preparationDirty = false;
        await loadAnalysisItem(itemId, {discardDirty: true});
        setAlert(document.querySelector('#analysis-message'), '準備記録を保存しました。話者・順序の不足は別途表示されます。');
      } catch (error) {
        message.textContent = error.message;
      } finally {
        preparationSaving = false;
      }
    });
    panel.body.append(button);
  }
  panel.body.append(message);
  return panel.panel;
}

function qualitativeCount(value) {
  const count = Number(value);
  return Number.isFinite(count) ? Math.max(0, Math.floor(count)) : 0;
}

function qualitativeEvidenceDetails(segments, {continuous = false} = {}) {
  const details = analysisElement('details', 'qualitative-evidence');
  details.append(analysisElement('summary', '', continuous
    ? `根拠の連続発言を開く（${segments.length}発言・両端とその間）`
    : `該当発言を開く（${segments.length}発言・連続ではない抜粋）`));
  const list = analysisElement('div', 'qualitative-evidence-list');
  const reviews = new Map((analysisState.data.manual?.preparation?.rows || []).map(row => [row.segment_id, row]));
  const codes = new Map((analysisState.data.manual?.codebook || []).map(code => [code.id, code]));
  let offset = 0;
  const more = contentButton('次の40発言を表示', appendNext);
  function appendNext() {
    const batch = segments.slice(offset, offset + 40);
    offset += batch.length;
    batch.forEach(segment => {
      const review = reviews.get(segment.id);
      const textStatus = {unreviewed: '未確認', transcript_checked: '逐語録確認済み・音声未照合',
        audio_verified: '音声照合済み', unclear: '聞き取り不明'}[review?.text_status] || '不明';
      const role = {participant: '参加者', moderator: '司会者', observer: '観察者'}[review?.role] || '役割不明';
      const article = analysisElement('blockquote', 'qualitative-quote');
      article.dataset.qualitativeEvidenceId = segment.id;
      article.append(analysisElement('p', 'qualitative-exact-text', segment.text || '（本文なし）'));
      article.append(analysisElement('p', 'analysis-caption',
        `#${segment.utterance_order ?? '不明'} / ${segment.speaker_name || segment.speaker || '話者不明'} / ${role} / ${segment.id}`));
      article.append(analysisElement('p', 'analysis-caption',
        `本文確認: ${textStatus} / 話者・役割・順序: ${review?.interaction_ready ? '準備記録で確認済み' : '未確認項目あり'}${segment.excluded ? ' / 集計から除外（文脈として表示）' : ''}`));
      const labels = (segment.annotation?.codes || []).map(id => codes.get(id)).filter(Boolean)
        .map(code => [code.label, code.category && `カテゴリー: ${code.category}`, code.theme && `テーマ: ${code.theme}`].filter(Boolean).join(' / '));
      if (labels.length) article.append(analysisElement('p', 'analysis-caption', `内容のコード: ${labels.join('；')}`));
      if (segment.valid_time) article.append(contentButton('元の発言・音声を確認', () => openInsightMedia(segment)));
      else article.append(analysisElement('p', 'analysis-caption', '時刻不明のため音声位置への移動はできません。'));
      list.insertBefore(article, more);
    });
    more.hidden = offset >= segments.length;
  }
  list.append(more);
  details.append(list);
  details.addEventListener('toggle', () => { if (details.open && !offset) appendNext(); });
  return details;
}

function renderInteractionTimeline() {
  const panel = analysisCardPanel('相互作用と意見変化の発言順タイムライン', 'manual', 'interaction_links', true, 'qualitative_coding');
  panel.panel.dataset.interactionTimeline = '';
  const data = analysisState.data;
  const manual = data.manual || {};
  const segments = data.segments || [];
  const lookup = new Map(segments.map((segment, index) => [segment.id, {segment, index}]));
  const links = (manual.interaction_links || []).slice().sort((a, b) =>
    (lookup.get(a.source_segment_id)?.index ?? Infinity) - (lookup.get(b.source_segment_id)?.index ?? Infinity));
  const stale = Boolean(manual.preparation?.analysis_needs_review);
  panel.body.append(analysisElement('p', 'analysis-section-help',
    '保存済みの手動リンクを、応答した発言の順で表示します。矢印は「参照先 → 応答発言」で、因果関係や同調圧力を示しません。間隔は経過時間を表しません。'));
  panel.body.append(analysisElement('p', 'analysis-caption',
    `入力版: ${manual.preparation?.input_version ?? '未固定'} / ${links.length}リンク。リンク件数は支持人数ではありません。意見変更などの判定は研究者の解釈です。`));
  if (stale) panel.body.append(analysisElement('p', 'analysis-orphan-warning',
    '要再確認：根拠の版が変わっています。旧リンクのIDのみ表示し、現在の本文を旧解釈の根拠として結びません。'));
  if (!links.length) {
    panel.body.append(analysisElement('p', 'analysis-no-data', '相互作用リンクは未登録です。「発話ごとのコード・相互作用・メモ」で対象発言と関係を指定して保存すると表示されます。'));
    return panel.panel;
  }
  const filter = document.createElement('select');
  filter.dataset.interactionFilter = '';
  filter.append(new Option('すべての関係', ''));
  const relations = new Map(links.map(link => [link.relation, link.relation_label || link.relation]));
  relations.forEach((label, id) => filter.append(new Option(label, id)));
  panel.body.append(analysisField('関係の種類で絞り込み', filter));
  const count = analysisElement('p', 'analysis-caption');
  count.setAttribute('aria-live', 'polite');
  const list = analysisElement('ol', 'qualitative-timeline');
  let offset = 0;
  let filtered = links;
  const more = contentButton('次の30リンクを表示', appendNext);
  more.dataset.interactionMore = '';
  function appendNext() {
    const batch = filtered.slice(offset, offset + 30);
    offset += batch.length;
    batch.forEach(link => {
      const from = lookup.get(link.target_segment_id);
      const to = lookup.get(link.source_segment_id);
      const unavailable = stale || link.analysis_needs_review || link.status === 'missing_target' || !from || !to;
      const event = analysisElement('li', `qualitative-event${unavailable ? ' needs-review' : ''}`);
      event.dataset.interactionSource = link.source_segment_id;
      event.dataset.interactionRelation = link.relation;
      event.append(analysisElement('strong', 'qualitative-relation', link.relation_label || link.relation));
      if (unavailable) {
        event.append(analysisElement('p', '', `${link.target_segment_id} → ${link.source_segment_id}`));
        event.append(analysisElement('p', 'analysis-caption', !from || !to || link.status === 'missing_target'
          ? '参照先の発言がありません。履歴・JSONを確認してください。'
          : '根拠が要再確認です。準備画面で現在の版との対応を確認してください。'));
      } else {
        const pair = analysisElement('div', 'qualitative-response-pair');
        [from.segment, to.segment].forEach((segment, index) => {
          if (index) pair.append(analysisElement('span', 'qualitative-direction', '応答'));
          const endpoint = analysisElement('div', 'qualitative-endpoint');
          endpoint.append(analysisElement('strong', '', `#${segment.utterance_order ?? '不明'} ${segment.speaker_name || segment.speaker || '話者不明'}`));
          const excerpt = segment.text || '';
          endpoint.append(analysisElement('p', 'qualitative-exact-text', excerpt.length > 160 ? `${excerpt.slice(0, 160)}…（全文は下の根拠）` : excerpt));
          pair.append(endpoint);
        });
        event.append(pair);
        const first = Math.min(from.index, to.index), last = Math.max(from.index, to.index);
        event.append(qualitativeEvidenceDetails(segments.slice(first, last + 1), {continuous: true}));
      }
      if (link.evidence_memo) event.append(analysisElement('p', 'qualitative-interpretation', `研究者の解釈メモ: ${link.evidence_memo}`));
      list.append(event);
    });
    count.textContent = `${filtered.length}リンク中 ${offset}リンクを表示（全体 ${links.length}リンク）`;
    more.hidden = offset >= filtered.length;
  }
  filter.addEventListener('change', () => {
    filtered = links.filter(link => !filter.value || link.relation === filter.value);
    offset = 0;
    list.replaceChildren();
    appendNext();
  });
  panel.body.append(count, list, more);
  appendNext();
  return panel.panel;
}

function renderManualSummary(container, compact) {
  const manual = analysisState.data.manual || {};
  container.append(analysisElement('p', 'analysis-caption qualitative-snapshot-notice',
    manual.preparation?.analysis_needs_review
      ? '要再確認：以下のコード集計・比較表には以前の解釈が含まれます。現在の入力に対する確定結果ではありません。'
      : '図表は保存済みの分析記録です。未保存のコード・リンクの編集は、保存後に反映されます。'));
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

  const plan = manual.focus_group_plan || {};
  if (plan && Object.keys(plan).length) {
    const planPanel = analysisCardPanel('対象データの確認と分析方針', 'configured', 'analysis_plan', true);
    planPanel.body.append(
      analysisElement('p', 'analysis-section-help', `${plan.status || '不明'}：${plan.provisional_assumption || ''}`)
    );
    const inventory = Array.isArray(plan.data_inventory) ? plan.data_inventory : [];
    const missing = inventory.filter(item => item.status === '不明' || item.status === '一部');
    if (missing.length) {
      const list = analysisElement('ul', 'analysis-inline-list');
      missing.forEach(item => list.append(analysisElement('li', '', `${item.item}: ${item.value}`)));
      planPanel.body.append(analysisElement('strong', '', '要確認'), list);
    }
    const methods = Array.isArray(plan.methods) ? plan.methods : [];
    methods.forEach(item => planPanel.body.append(analysisElement(
      'p', 'analysis-list-row', `${item.role}：${item.method}（データ充足: ${item.data_sufficiency}）`
    )));
    const expertBlock = analysisState.data.experts || {};
    if (expertBlock.status === 'unavailable') {
      planPanel.body.append(analysisElement('p', 'analysis-section-help', expertBlock.message || '専門家定義を読み込めません。'));
    }
    (Array.isArray(expertBlock.experts) ? expertBlock.experts : []).forEach(expert => {
      planPanel.body.append(buildExpertDetails(expert));
    });
    if (expertBlock.ai && expertBlock.ai.mode === 'blocked') {
      planPanel.body.append(analysisElement('p', 'analysis-section-help', `AI見解：${expertBlock.ai.reason}`));
    }
    container.append(planPanel.panel);
  }

  const codeMetrics = Array.isArray(manual.code_metrics) ? manual.code_metrics : [];
  const interactionSummary = Array.isArray(manual.interaction_summary) ? manual.interaction_summary : [];
  if (codeMetrics.length || interactionSummary.some(item => item.count)) {
    const summary = analysisCardPanel('手動コードの集計', 'manual', 'codes', true, 'qualitative_coding');
    if (codeMetrics.length) {
      const maximum = codeMetrics.reduce((max, item) => Math.max(max, qualitativeCount(item.segment_count)), 0);
      summary.body.append(analysisElement('p', 'analysis-caption',
        `棒の共通尺度: 0～${maximum}発言（最長の棒＝最大件数）。割合・重要性・支持人数を表しません。同一発言への同一コードは1件、複数コードはそれぞれに計上します。`));
      codeMetrics.forEach(item => {
        const value = qualitativeCount(item.segment_count);
        const row = appendAnalysisBar(summary.body, item.label, maximum ? 100 * value / maximum : 0,
          `${value}発言 / ${qualitativeCount(item.speaker_count)}話者ラベル / ${item.group_count ?? '不明'}グループ / 重要引用 ${qualitativeCount(item.important_count)}件 / ${analysisObservedTimeText(item)}`, item.color);
        row.dataset.qualitativeCode = item.id;
        row.querySelector('.analysis-bar-track').setAttribute('aria-label', `${item.label}: ${value}発言。共通尺度0～${maximum}発言`);
        row.querySelector('.analysis-bar-track i').style.minWidth = '0';
      });
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
  const codebook = Array.isArray(manual.codebook) ? manual.codebook : [];
  if (matrix.length && codebook.length) {
    const matrixPanel = analysisCardPanel('話者×コード（発言件数）', 'manual', 'case_matrix', true, 'qualitative_coding');
    const wrap = analysisElement('div', 'analysis-table-wrap');
    wrap.tabIndex = 0;
    wrap.setAttribute('role', 'region');
    wrap.setAttribute('aria-label', '話者×コード比較表。列が多い場合は横にスクロールできます。');
    const table = analysisElement('table', 'analysis-table analysis-matrix');
    const maximum = matrix.reduce((max, row) => (row.codes || []).reduce(
      (value, code) => Math.max(value, qualitativeCount(code.count)), max), 0);
    matrixPanel.body.append(analysisElement('p', 'analysis-caption', `色の共通尺度: 0～${maximum}発言。件数を押すと該当する発言を開けます。話者ラベルと実際の人数は別です。`));
    const evidence = analysisElement('div', 'qualitative-matrix-evidence');
    evidence.setAttribute('aria-live', 'polite');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    headRow.append(analysisElement('th', '', '話者'));
    codebook.forEach(code => {
      const cell = analysisElement('th', '', code.label);
      cell.scope = 'col';
      headRow.append(cell);
    });
    head.append(headRow);
    const body = analysisElement('tbody');
    matrix.forEach(rowData => {
      const row = analysisElement('tr');
      row.append(analysisElement('th', '', rowData.speaker_name || rowData.speaker));
      const counts = new Map((rowData.codes || []).map(item => [item.code_id, item.count]));
      codebook.forEach(code => {
        const value = qualitativeCount(counts.get(code.id));
        const cell = analysisElement('td', value ? 'has-value' : '');
        cell.style.setProperty('--matrix-strength', String(maximum ? value / maximum : 0));
        if (value) {
          const button = contentButton(String(value), () => {
            evidence.replaceChildren(analysisElement('strong', '', `${rowData.speaker_name || rowData.speaker} × ${code.label}`));
            if (manual.preparation?.analysis_needs_review) {
              evidence.append(analysisElement('p', '', '要再確認：現在の本文を旧コードの根拠として表示できません。'));
              return;
            }
            const matching = (analysisState.data.segments || []).filter(segment => !segment.excluded
              && segment.speaker === rowData.speaker && (segment.annotation?.codes || []).includes(code.id));
            const details = qualitativeEvidenceDetails(matching);
            evidence.append(details);
            details.open = true;
            details.querySelector('summary').focus();
          }, 'qualitative-matrix-button');
          button.setAttribute('aria-label', `${rowData.speaker_name || rowData.speaker}、${code.label}、${value}発言の根拠を開く`);
          cell.append(button);
        } else cell.textContent = '0';
        row.append(cell);
      });
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    matrixPanel.body.append(wrap, evidence);
    container.append(matrixPanel.panel);
  }
  container.append(renderInteractionTimeline());
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
  fragment.append(renderTranscriptPreparation());
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
    const quotesPanel = analysisCardPanel('重要引用', 'manual', 'important_quotes', true, 'qualitative_coding');
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
    ['report', '分析レポート（Markdown）'],
    ['analysis_plan', '分析方針・データ確認 CSV'],
    ['analysis_units', '発言と分析結果の対応表 CSV'],
    ['context', '入力・確認状況 CSV'],
    ['codes', 'コード集計 CSV'],
    ['codebook_history', 'コードブック変更履歴 CSV'],
    ['coded_segments', 'コード済み発話 CSV'],
    ['interactions', '相互作用タグ CSV'],
    ['interaction_links', '相互作用の根拠発話 CSV'],
    ['case_matrix', '話者×コード CSV'],
    ['important_quotes', '重要引用 CSV']
  ]));
  fragment.append(summaryGrid);

  const settingsPanel = analysisCardPanel('分析条件', 'configured', '', true);
  const settingsGrid = analysisElement('div', 'analysis-settings-grid');
  settingsGrid.append(
    analysisField('研究質問', analysisConfigControl('research_question', 'textarea'), '分析で明らかにしたい問いを記録します。'),
    analysisField('主となる分析手法', analysisConfigControl('analysis_method', 'select', {
      auto: '資料に応じて暫定選定', qualitative_content: '質的内容分析', thematic: 'テーマ分析',
      framework: 'フレームワーク分析', scat: 'SCAT', mgta: 'M-GTA', kj: 'KJ法',
      quantitative_text: '計量テキスト分析（補助）', interaction: '相互作用分析'
    }), '分析方針・データ確認CSVで、必要な手順と不足資料を確認できます。'),
    analysisField('手法選定の理由', analysisConfigControl('method_rationale', 'textarea'), '研究目的・データとの対応、得たい結果、限界を研究者が記録します。'),
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

  const codebookPanel = analysisCardPanel('コードブック', 'configured', '', true, 'qualitative_coding');
  codebookPanel.body.append(
    analysisElement('p', 'analysis-section-help', 'コードの意味と含む／含まない例、カテゴリー、テーマを先に定義すると、複数人でも判断を揃えやすくなります。'),
    analysisField('今回のコードブック変更理由', analysisConfigControl('codebook_change_reason', 'textarea'), '追加・修正・削除の理由を記入します。変更時に履歴へ保存されます。'),
    analysisCodebookEditor(compact)
  );
  fragment.append(codebookPanel.panel);

  const codingPanel = analysisCardPanel('発話ごとのコード・相互作用・メモ', 'manual', 'coded_segments', true, 'qualitative_coding');
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
  else if (['importance_score', 'review_score', 'sensitivity_score'].includes(field)) {
    const number = control.value === '' ? null : Number(control.value);
    annotation[field] = Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : null;
  }
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
  const saveContext = captureAnalysisContext();
  analysisSaveOwner = saveContext;
  // Preserve later edits only within this same data/navigation/revision owner.
  const ownsSave = () => analysisSaveOwner === saveContext
    && isAnalysisContextCurrent({...saveContext, mutation: analysisMutationGeneration});
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
    if (!ownsSave()) return;
    if (!response.ok) throw new Error(payload.error || '分析設定を保存できませんでした。');
    const data = payload.analysis && typeof payload.analysis === 'object' ? payload.analysis : payload;
    analysisSaveInProgress = false;
    const hasLaterChanges = analysisState.itemId === savedItemId
      && analysisMutationGeneration !== saveGeneration;
    if (analysisState.itemId === savedItemId && !hasLaterChanges) {
      analysisState.data = data;
      invalidateAnalysisMethodOverview();
      analysisState.config = deepCopy(data.config || {});
      analysisState.annotations = deepCopy(data.annotations || {});
      if (analysisTermRunRequested) analysisState.mode = 'automatic';
      analysisTermRunRequested = false;
      setAnalysisDirty(false);
      renderAnalysisWorkspace();
      onContentAnalysisLoaded();
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
    if (typeof analysisMeasurementRefreshContext === 'function') analysisMeasurementRefreshContext();
  } catch (error) {
    if (!ownsSave()) return;
    analysisSaveInProgress = false;
    analysisTermRunRequested = false;
    setAnalysisDirty(true, false);
    setAlert(document.querySelector('#analysis-message'), error.message, true);
  } finally {
    // An old completion must not release a newer view's save operation.
    if (analysisSaveOwner === saveContext) {
      analysisSaveOwner = null;
      analysisSaveInProgress = false;
      analysisTermRunRequested = false;
      setAnalysisDirty(analysisState.dirty, false);
    }
  }
}

// `?view=` and `?item=` links (Vault links, older bookmarks) still work: they
// resolve to the matching hash route on first load.
function applyRouteFromLocation({fromHistory = false, initial = false} = {}) {
  let route = parseRouteHash(window.location.hash);
  if (!route && initial) {
    const requestedView = requestedParameters.get('view');
    const view = Object.hasOwn(viewRouteHashes, requestedView) ? requestedView : 'new';
    route = {view, itemId: view === 'analysis' ? String(requestedParameters.get('item') || '') : ''};
  }
  if (!route) route = {view: 'new', itemId: ''};
  if (route.view === 'item') {
    if (currentJob && String(currentJob.id) === route.itemId) {
      if (!showView('item', {itemId: route.itemId, replace: initial}) && fromHistory) syncRouteHash(currentRouteHash);
      return;
    }
    if (!confirmLeave({target: 'item', itemId: route.itemId})) {
      if (fromHistory) syncRouteHash(currentRouteHash);
      return;
    }
    const opening = openLibraryItem(route.itemId);
    const requestSequence = resultRequestSequence;
    opening.then(() => {
      // A stale route must not hide newer content or cancel its in-flight request.
      if (requestSequence !== resultRequestSequence) return;
      if (!currentJob || String(currentJob.id) !== route.itemId) showView('library', {replace: true});
    });
    return;
  }
  const opened = showView(route.view, {analysisItemId: route.view === 'analysis' ? route.itemId : '', replace: initial});
  if (!opened && fromHistory) syncRouteHash(currentRouteHash);
}
