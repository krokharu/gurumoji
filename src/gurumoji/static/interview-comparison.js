/* Cross-session comparison deliberately lives beside, rather than inside, a
 * single transcript's analysis state.  It is read-only: opening or comparing
 * sessions never changes their annotations or analysis settings. */
(() => {
  const card = document.querySelector('#interview-comparison-card');
  if (!card) return;

  const baseSelect = document.querySelector('#interview-comparison-base');
  const allowDifferent = document.querySelector('#interview-comparison-allow-different');
  const targets = document.querySelector('#interview-comparison-targets');
  const targetStatus = document.querySelector('#interview-comparison-target-status');
  const runButton = document.querySelector('#interview-comparison-run');
  const selectionStatus = document.querySelector('#interview-comparison-selection');
  const message = document.querySelector('#interview-comparison-message');
  const result = document.querySelector('#interview-comparison-result');
  const refreshButton = document.querySelector('#interview-comparison-refresh');
  let catalog = [];
  let baseId = '';
  let selectedIds = new Set();

  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  };

  const setMessage = (text, error = false) => {
    message.hidden = !text;
    message.textContent = text || '';
    message.classList.toggle('error', Boolean(text && error));
  };

  const itemFor = id => catalog.find(item => item.id === id);
  const sameContent = (base, candidate) => Boolean(
    base && candidate && base.comparison_key && base.comparison_key === candidate.comparison_key
  );
  const timeText = seconds => {
    const value = Math.max(0, Math.round(Number(seconds) || 0));
    const minutes = Math.floor(value / 60);
    return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
  };
  const number = value => new Intl.NumberFormat('ja-JP', {maximumFractionDigits: 1}).format(Number(value) || 0);

  function selectedInOrder() {
    return [baseId, ...catalog.map(item => item.id).filter(id => id !== baseId && selectedIds.has(id))]
      .filter((id, index, values) => id && values.indexOf(id) === index);
  }

  function updateSelectionUi() {
    const selected = selectedInOrder();
    selectionStatus.textContent = `${selected.length}件選択（2〜8件）`;
    runButton.disabled = selected.length < 2 || selected.length > 8;
  }

  function renderTargets() {
    targets.replaceChildren();
    const base = itemFor(baseId);
    if (!base) {
      targetStatus.textContent = '基準インタビューを選択してください。';
      updateSelectionUi();
      return;
    }
    selectedIds = new Set([...selectedIds].filter(id => id === baseId || itemFor(id)));
    selectedIds.add(baseId);
    const candidates = catalog.filter(item => item.id !== base.id && (allowDifferent.checked || sameContent(base, item)));
    const groupLabel = base.comparison_label || '未設定';
    if (allowDifferent.checked) {
      targetStatus.textContent = `全${catalog.length - 1}件から選択できます。異なる内容の回には「異なる内容」と表示されます。`;
    } else if (!base.comparison_key) {
      targetStatus.textContent = '比較グループまたは質問ガイドが未設定のため、同内容の候補を表示できません。会話プロファイルで比較グループを設定してください。';
    } else {
      targetStatus.textContent = `「${groupLabel}」と一致する${candidates.length}件だけを表示しています。`;
    }
    const addTarget = (item, isBase) => {
      const label = element('label', `interview-comparison-target${isBase ? ' base' : ''}`);
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = selectedIds.has(item.id);
      input.disabled = isBase;
      input.dataset.comparisonTarget = item.id;
      const body = element('span', 'interview-comparison-target-body');
      body.append(
        element('strong', '', item.source_name || '名称未設定'),
        element('small', '', `発話 ${item.segment_count || 0}件 / ${item.comparison_label || '比較グループ未設定'}`)
      );
      const badge = element('em', sameContent(base, item) ? 'compatible' : 'different', isBase ? '基準' : sameContent(base, item) ? '同内容' : '異なる内容');
      label.append(input, body, badge);
      targets.append(label);
    };
    addTarget(base, true);
    candidates.forEach(item => addTarget(item, false));
    if (!candidates.length) {
      const empty = element('p', 'interview-comparison-empty', allowDifferent.checked
        ? '比較できる別のインタビューがありません。'
        : '同じ比較グループのインタビューがありません。比較グループを揃えるか、異なる内容も比較するを選択してください。');
      targets.append(empty);
    }
    updateSelectionUi();
  }

  function addMetricTable(parent, interviews) {
    const wrap = element('div', 'interview-comparison-table-wrap');
    const table = element('table', 'interview-comparison-table');
    const head = element('thead');
    const headRow = element('tr');
    ['インタビュー', '対象発話', '参加者', '話者', '発話時間', '抽出語数', '除外発話'].forEach(value => headRow.append(element('th', '', value)));
    head.append(headRow);
    const body = element('tbody');
    interviews.forEach(item => {
      const row = element('tr');
      [
        item.source_name,
        item.included_segment_count,
        item.participant_count,
        item.speaker_count,
        timeText(item.total_speaking_seconds),
        item.term_count,
        item.excluded_segment_count,
      ].forEach(value => row.append(element('td', '', value)));
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    parent.append(wrap);
  }

  function addTermList(parent, rows, kind) {
    if (!rows.length) {
      parent.append(element('p', 'interview-comparison-empty', '該当するデータがありません。2回以上出現する語のみを表示します。'));
      return;
    }
    const list = element('div', 'interview-comparison-term-list');
    rows.forEach(row => {
      const line = element('div', 'interview-comparison-term');
      if (kind === 'common') {
        line.append(element('strong', '', row.term));
        const values = element('span', '');
        row.interviews.forEach(value => {
          const source = itemFor(value.item_id);
          values.append(element('small', '', `${source ? source.source_name : value.item_id}: ${value.count}回 (${number(value.rate_per_1000_terms)}/千語)`));
        });
        line.append(values);
      } else {
        line.append(
          element('strong', '', row.term),
          element('span', '', `${row.source_name}: ${row.count}回 / ${number(row.rate_per_1000_terms)}／千語`),
          element('small', row.difference_per_1000_terms >= 0 ? 'higher' : 'lower', `他回との差 ${row.difference_per_1000_terms >= 0 ? '+' : ''}${number(row.difference_per_1000_terms)}／千語`)
        );
      }
      list.append(line);
    });
    parent.append(list);
  }

  function addCategoricalTable(parent, rows, label) {
    if (!rows.length) {
      parent.append(element('p', 'interview-comparison-empty', '記録済みの比較データがありません。'));
      return;
    }
    const wrap = element('div', 'interview-comparison-table-wrap');
    const table = element('table', 'interview-comparison-table compact');
    const head = element('thead');
    const headRow = element('tr');
    headRow.append(element('th', '', label));
    const interviewIds = selectedInOrder();
    interviewIds.forEach(id => headRow.append(element('th', '', (itemFor(id) || {}).source_name || id)));
    head.append(headRow);
    const body = element('tbody');
    rows.forEach(row => {
      const tableRow = element('tr');
      tableRow.append(element('th', '', row.code || row.emotion || '未設定'));
      interviewIds.forEach(id => {
        const value = (row.interviews || []).find(candidate => candidate.item_id === id) || {};
        tableRow.append(element('td', '', `${value.count || 0}件 (${number(value.rate_per_100_segments)}%)`));
      });
      body.append(tableRow);
    });
    table.append(head, body);
    wrap.append(table);
    parent.append(wrap);
  }

  function panel(title, description) {
    const section = element('section', 'interview-comparison-panel');
    section.append(element('h4', '', title));
    if (description) section.append(element('p', 'interview-comparison-caption', description));
    return section;
  }

  function renderResult(data) {
    result.replaceChildren();
    result.hidden = false;
    const intro = element('div', `interview-comparison-result-intro ${data.mode || ''}`);
    intro.append(
      element('strong', '', data.same_content ? '同内容のインタビュー比較' : '異なる内容を含む探索的比較'),
      element('p', '', data.same_content
        ? '同じ比較グループとして選択された回を、発話量・語・手動コード・感情ラベルで並べています。'
        : '質問や対象条件が異なる可能性を前提に、差の説明ではなく探索の手がかりとして確認してください。')
    );
    result.append(intro);
    const cautions = element('ul', 'interview-comparison-cautions');
    (data.cautions || []).forEach(value => cautions.append(element('li', '', value)));
    result.append(cautions);
    const overview = panel('セッションの比較', '分析から除外した発話は、対象発話と語数に含めていません。');
    addMetricTable(overview, data.interviews || []);
    result.append(overview);
    const common = panel('共通して現れる語', '全ての選択回で2回以上出現した語です。テーマの確定ではありません。');
    addTermList(common, data.common_terms || [], 'common');
    result.append(common);
    const characteristics = panel('回ごとの特徴語', '各回と、残りの選択回を合算した出現率（千語あたり）の差です。');
    addTermList(characteristics, data.characteristic_terms || [], 'characteristic');
    result.append(characteristics);
    const codes = panel('手動コードの比較', '同じラベルのコードを並べます。コード定義が異なる場合は比較しないでください。');
    addCategoricalTable(codes, data.code_comparison || [], 'コード');
    result.append(codes);
    const emotions = panel('感情ラベルの比較', 'モデル名ごとの推定ラベルです。本人の感情を確定するものではありません。');
    addCategoricalTable(emotions, data.emotion_comparison || [], '感情モデル・ラベル');
    result.append(emotions);
  }

  async function loadCatalog() {
    setMessage('');
    refreshButton.disabled = true;
    baseSelect.disabled = true;
    try {
      const response = await fetch('/api/library?sort=updated_desc', {cache: 'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'インタビュー一覧を取得できませんでした。');
      catalog = Array.isArray(data.items) ? data.items : [];
      const preferred = baseId || (document.querySelector('#analysis-item-select') || {}).value;
      baseId = catalog.some(item => item.id === preferred) ? preferred : (catalog[0] || {}).id || '';
      selectedIds = new Set(baseId ? [baseId] : []);
      baseSelect.replaceChildren();
      if (!catalog.length) baseSelect.add(new Option('比較できるデータがありません', ''));
      catalog.forEach(item => baseSelect.add(new Option(item.source_name || item.id, item.id)));
      baseSelect.value = baseId;
      renderTargets();
    } catch (error) {
      catalog = [];
      baseId = '';
      selectedIds.clear();
      targets.replaceChildren();
      setMessage(error.message, true);
      updateSelectionUi();
    } finally {
      refreshButton.disabled = false;
      baseSelect.disabled = !catalog.length;
    }
  }

  async function runComparison() {
    const itemIds = selectedInOrder();
    if (itemIds.length < 2 || itemIds.length > 8) return;
    setMessage('');
    runButton.disabled = true;
    runButton.textContent = '比較を集計中…';
    result.hidden = true;
    try {
      const response = await fetch('/api/library/interview-comparison', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({item_ids: itemIds, allow_different_content: allowDifferent.checked})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'インタビュー比較を生成できませんでした。');
      renderResult(data);
    } catch (error) {
      setMessage(error.message, true);
    } finally {
      runButton.textContent = '選択したインタビューを比較';
      updateSelectionUi();
    }
  }

  baseSelect.addEventListener('change', () => {
    baseId = baseSelect.value;
    selectedIds = new Set(baseId ? [baseId] : []);
    result.hidden = true;
    setMessage('');
    renderTargets();
  });
  allowDifferent.addEventListener('change', () => {
    const base = itemFor(baseId);
    if (!allowDifferent.checked && base) {
      selectedIds = new Set([...selectedIds].filter(id => id === baseId || sameContent(base, itemFor(id))));
    }
    result.hidden = true;
    setMessage('');
    renderTargets();
  });
  targets.addEventListener('change', event => {
    const input = event.target.closest('[data-comparison-target]');
    if (!input) return;
    if (input.checked) {
      if (selectedInOrder().length >= 8) {
        input.checked = false;
        setMessage('比較できるインタビューは8件までです。', true);
        return;
      }
      selectedIds.add(input.dataset.comparisonTarget);
    } else selectedIds.delete(input.dataset.comparisonTarget);
    result.hidden = true;
    updateSelectionUi();
  });
  refreshButton.addEventListener('click', loadCatalog);
  runButton.addEventListener('click', runComparison);
  loadCatalog();
})();
