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
    const linkedItem = !analysisLinkedItemApplied ? new URLSearchParams(location.search).get('item') : '';
    analysisLinkedItemApplied = true;
    const nextId = linkedItem || (currentExists
      ? analysisState.itemId
      : resultExists ? currentJobId : (analysisCatalog[0] || {}).id || '');
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

async function loadAnalysisItem(itemId, {discardDirty = false, execute = false} = {}) {
  const nextId = String(itemId || '');
  if (!nextId) return;
  if (!discardDirty && hasUnsavedAnalysisChanges()) {
    const leave = window.confirm('分析設定・手動コード・準備記録に未保存の変更があります。破棄してデータを読み込みますか？');
    if (!leave) {
      if (analysisItemSelect) analysisItemSelect.value = analysisState.itemId;
      return;
    }
  }
  const closedFixedViewer = typeof closeFixedAnalysisViewer === 'function' && closeFixedAnalysisViewer();
  const closedAnalysisDialog = typeof closeAnalysisExecutionDialog === 'function' && closeAnalysisExecutionDialog();
  if ((closedFixedViewer || closedAnalysisDialog) && analysisItemSelect?.isConnected && !analysisItemSelect.closest('[hidden]')) analysisItemSelect.focus();
  if (analysisRequestController) analysisRequestController.abort();
  analysisRequestController = new AbortController();
  analysisNavigationGeneration += 1;
  // The former view's request may finish, but it no longer owns these controls.
  analysisSaveOwner = null;
  analysisSaveInProgress = false;
  analysisTermRunRequested = false;
  const requestId = ++analysisRequestSequence;
  const executionView = document.querySelector('#analysis-execution-view');
  if (executionView) executionView.hidden = true;
  analysisState.itemId = nextId;
  analysisState.data = null;
  if (analysisItemSelect) analysisItemSelect.value = nextId;
  updateAnalysisTarget();
  if (analysisCard && !analysisCard.hidden) syncRouteHash(routeHash('analysis', nextId), {replace: true});
  setAnalysisLoading(true);
  setAlert(document.querySelector('#analysis-message'), '');
  try {
    const query = execute ? '?execute=1' : '';
    const response = await apiFetch(`/api/library/${encodeURIComponent(nextId)}/analysis${query}`, {
      cache: 'no-store', signal: analysisRequestController.signal
    });
    const payload = await readJsonResponse(response);
    if (requestId !== analysisRequestSequence) return;
    if (!response.ok) throw new Error(payload.error || '分析データを取得できませんでした。');
    const data = payload.analysis && typeof payload.analysis === 'object' ? payload.analysis : payload;
    analysisState.data = data;
    invalidateAnalysisMethodOverview();
    analysisState.config = deepCopy(data.config || {});
    analysisState.annotations = deepCopy(data.annotations || {});
    preparationDraft = null;
    preparationDirty = false;
    analysisState.segmentQuery = '';
    analysisState.annotatedOnly = false;
    analysisState.speakerAttributeFilter = '';
    analysisState.selectedSpeaker = '';
    setAnalysisDirty(false);
    renderAnalysisWorkspace();
    onContentAnalysisLoaded();
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
  analysisState.mode = ['manual', 'methods'].includes(mode) ? mode : 'automatic';
  renderAnalysisWorkspace();
}

function analysisModeContent(compact) {
  if (analysisState.mode === 'manual') return renderManualAnalysis(compact);
  if (analysisState.mode === 'methods') return renderMethodAnalysis(compact);
  return renderAutomaticAnalysis(compact);
}

function renderAnalysisWorkspace() {
  if (!analysisState.data) return;
  const shell = document.querySelector('#analysis-shell');
  const empty = document.querySelector('#analysis-empty');
  if (analysisState.data.executed === false && analysisState.mode === 'automatic') {
    if (shell) shell.hidden = true;
    if (empty) {
      empty.hidden = false;
      const title = empty.querySelector('strong');
      const desc = empty.querySelector('p');
      if (title) title.textContent = '分析はまだ実行されていません';
      if (desc) desc.textContent = '右上の［分析を実行］ボタンを押すと、発話量・会話構造・形態素・共起・統計検定の分析を開始します。';
      let history = empty.querySelector('.analysis-empty-history');
      if (!history) {
        history = analysisElement('div', 'analysis-empty-history');
        empty.append(history);
      }
      history.replaceChildren(buildAnalysisStorage({readOnly: true}));
    }
    setAnalysisDirty(analysisState.dirty, false);
    refreshAnalysisStorage();
    return;
  }
  document.querySelectorAll('[data-analysis-mode]').forEach(button => {
    const active = button.dataset.analysisMode === analysisState.mode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  updateAnalysisTarget();
  if (analysisDesktopContent) {
    analysisDesktopContent.replaceChildren();
    analysisDesktopContent.append(analysisModeContent(false));
  }
  if (analysisMobileContent) {
    analysisMobileContent.replaceChildren();
    analysisMobileContent.append(analysisModeContent(true));
  }
  if (shell) shell.hidden = false;
  if (empty) empty.hidden = true;
  setAnalysisDirty(analysisState.dirty, false);
  renderKwicResults();
  refreshInsightControls();
  refreshAnalysisStorage();
  restoreAnalysisEvidencePosition();
  scheduleAnalysisNavigationSync();
  if (!analysisInitialSectionApplied && requestedAnalysisSection) {
    analysisInitialSectionApplied = true;
    requestAnimationFrame(() => {
      const content = window.matchMedia('(max-width: 959px)').matches
        ? analysisMobileContent : analysisDesktopContent;
      const target = content && content.querySelector(`[data-analysis-anchor="${requestedAnalysisSection}"]`);
      const jump = content && content.querySelector(`[data-analysis-jump="${requestedAnalysisSection}"]`);
      selectAnalysisPage(requestedAnalysisSection);
      if (jump) {
        content.querySelectorAll('[data-analysis-jump]').forEach(button => button.classList.toggle('active', button === jump));
      }
      if (target) target.scrollIntoView({block: 'start'});
    });
  }
}

function appendResearchAnalysis(grid, compact) {
  const research = (analysisState.data && analysisState.data.research) || {};
  const linguistics = research.linguistics || {};
  const statistics = research.statistics || {};
  const engine = linguistics.engine || {};
  const coverage = linguistics.coverage || {};

  const morphologyPanel = analysisCardPanel('使われた言葉の種類（形態素・品詞）', 'automatic', 'morphemes', true, 'morphology');
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

  const termsPanel = analysisCardPanel('よく使われた言葉（TF・DF）', 'automatic', 'term_frequency', false, 'lexical_frequency');
  const terms = Array.isArray(linguistics.term_frequency) ? linguistics.term_frequency : [];
  const maxTerm = Math.max(1, ...terms.map(item => Number(item.term_frequency) || 0));
  terms.slice(0, compact ? 10 : 15).forEach(item => appendSearchableTermBar(
    termsPanel.body,
    item.term,
    100 * (Number(item.term_frequency) || 0) / maxTerm,
    `TF ${item.term_frequency || 0} / DF ${item.document_frequency || 0} / ${item.upos || '—'}`,
    '#6C8B3C'
  ));
  if (!terms.length) termsPanel.body.append(analysisElement('p', 'analysis-no-data', '内容語を抽出できませんでした。解析器の状態と原文を確認してください。'));
  termsPanel.body.append(analysisElement('p', 'analysis-caption', 'TFは総出現回数、DFはその語を含む発話数です。頻度は重要性を意味しません。'));
  grid.append(termsPanel.panel);

  const cooccurrencePanel = analysisCardPanel('一緒に使われる言葉のつながり（共起）', 'automatic', 'cooccurrence', true, 'cooccurrence');
  const cooccurrence = Array.isArray(linguistics.cooccurrence) ? linguistics.cooccurrence : [];
  if (cooccurrence.length) {
    cooccurrencePanel.body.append(buildAnalysisCooccurrenceExplorer(cooccurrence));
  } else {
    cooccurrencePanel.body.append(analysisElement('p', 'analysis-no-data', `同じ発話で${coverage.cooccurrence_min_count || 2}回以上共起する語の組み合わせがありません。`));
  }
  cooccurrencePanel.body.append(analysisElement('p', 'analysis-caption', `発話を文書単位とし、上位${coverage.cooccurrence_top_terms || 60}語からJaccard係数を計算しています。関係の意味は原文で確認してください。`));
  grid.append(cooccurrencePanel.panel);

  const dependencies = Array.isArray(linguistics.dependency_preview) ? linguistics.dependency_preview : [];
  const syntaxPanel = analysisCardPanel('文章内の言葉のつながり（係り受け）', 'automatic', 'dependencies', true, 'syntax');
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
  const correlationPanel = analysisCardPanel('指標どうしの関係（相関）', 'automatic', 'correlations', true, 'correlation');
  if (computedCorrelations.length) {
    correlationPanel.body.append(buildAnalysisCorrelationExplorer(correlations));
  } else {
    correlationPanel.body.append(analysisElement('p', 'analysis-no-data', '相関を計算できる変数または標本数が不足しています。'));
  }
  grid.append(correlationPanel.panel);

  const descriptives = (Array.isArray(statistics.descriptives) ? statistics.descriptives : [])
    .filter(item => item.scope === 'overall');
  const statsPanel = analysisCardPanel('会話データの基本統計', 'automatic', 'descriptives', true, 'descriptive_statistics');
  if (descriptives.length) {
    statsPanel.body.append(buildAnalysisDescriptiveChart(descriptives));
    const details = analysisElement('details', 'analysis-table-details');
    details.append(analysisElement('summary', '', '記述統計の数値表を確認'));
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['変数', '分析単位・測定単位', 'N', '欠測', '平均', '標準偏差', '中央値', '最小', '最大'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    descriptives.forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.label || item.variable),
        analysisElement('td', '', `${item.analysis_unit || statistics.analysis_unit || '発話'} / ${item.unit || '—'}`),
        analysisElement('td', '', item.n || 0),
        analysisElement('td', '', item.missing ?? '—'),
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
    details.append(wrap);
    statsPanel.body.append(details);
  } else statsPanel.body.append(analysisElement('p', 'analysis-no-data', '記述統計を計算できる発話がありません。'));
  statsPanel.body.append(analysisElement('p', 'analysis-caption', `分析単位: ${statistics.analysis_unit || '発話'} / 比較軸: ${statistics.group_variable === 'role' ? '役割' : '話者'}。欠損値は変数ごとに除外します。`));
  grid.append(statsPanel.panel);

  const frequencies = Array.isArray(statistics.frequencies) ? statistics.frequencies : [];
  const frequencyPanel = analysisCardPanel('カテゴリ別の件数と割合', 'automatic', 'frequencies', true, 'descriptive_statistics');
  if (frequencies.length) {
    frequencyPanel.body.append(buildAnalysisFrequencyExplorer(frequencies, compact));
  } else {
    frequencyPanel.body.append(analysisElement('p', 'analysis-no-data', '割合を可視化できるカテゴリデータがありません。'));
  }
  grid.append(frequencyPanel.panel);

  const tests = Array.isArray(statistics.tests) ? statistics.tests : [];
  const crosstabs = Array.isArray(statistics.crosstabs) ? statistics.crosstabs : [];
  const selectedTerms = Array.isArray(statistics.selected_terms) ? statistics.selected_terms : [];
  const selectedTermPanel = analysisCardPanel('手動選択単語のクロス集計＋カイ二乗検定', 'configured', 'crosstabs', true, 'group_statistics');
  if (selectedTerms.length) {
    selectedTerms.slice(0, compact ? 8 : 20).forEach(term => {
      const columnVariable = `selected_term:${term}`;
      const rows = crosstabs.filter(item => item.column_variable === columnVariable);
      const test = tests.find(item => item.family === 'クロス集計' && (item.term === term || item.outcome === rows[0]?.table_id || item.outcome === columnVariable));
      const matchMode = rows[0]?.match_mode || statistics.crosstab_match_mode || 'normalized';
      const article = analysisElement('article', 'analysis-selected-term-result');
      article.append(analysisElement('h4', '', `「${term}」 × ${statistics.group_variable === 'role' ? '役割' : '話者'} / ${analysisMatchModeLabel(matchMode)}`));
      const evidence = analysisElement('button', 'secondary-button', '同じ一致条件で文脈を確認');
      evidence.type = 'button';
      evidence.addEventListener('click', () => {
        selectAnalysisPage('content');
        if (typeof runKwicSearch === 'function') runKwicSearch({query: term, matchMode, offset: 0});
      });
      article.append(evidence);
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
          'analysis-term-test-summary',
          `Pearson χ²(${test.df1}) = ${analysisNumberText(test.statistic, 3)}, ${analysisPValueText(test.p_value)}, Cramér's V = ${analysisNumberText(test.effect_size, 3)}, N = ${test.n || 0}`
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

  const testsPanel = analysisCardPanel('グループ間の違いと効果の大きさ', 'automatic', 'statistical_tests', true, 'group_statistics');
  const computedTests = tests.filter(item => item.status === 'computed');
  if (computedTests.length) {
    testsPanel.body.append(buildAnalysisEffectChart(computedTests, compact));
    const details = analysisElement('details', 'analysis-table-details');
    details.append(analysisElement('summary', '', '統計検定の数値表を確認'));
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table analysis-stat-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['検定', '対象', '分析単位・測定単位', 'N', '欠測', '統計量', 'p値（未補正）', '効果量'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    computedTests.slice(0, compact ? 10 : 24).forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.test),
        analysisElement('td', '', item.outcome_label || item.outcome),
        analysisElement('td', '', `${item.analysis_unit || '発話'} / ${item.unit || '—'}`),
        analysisElement('td', '', item.n || 0),
        analysisElement('td', '', item.missing ?? '—'),
        analysisElement('td', '', analysisNumberText(item.statistic, 3)),
        analysisElement('td', '', analysisPValueText(item.p_value)),
        analysisElement('td', '', item.effect_name ? `${item.effect_name} = ${analysisNumberText(item.effect_size, 3)}` : '—')
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    details.append(wrap);
    testsPanel.body.append(details);
  } else testsPanel.body.append(analysisElement('p', 'analysis-no-data', '比較群または標本数が不足しているため、推測統計を計算していません。'));
  const unavailableCount = tests.filter(item => item.status !== 'computed').length;
  testsPanel.body.append(analysisElement('p', 'analysis-caption', `発話単位の探索的検定・p値は多重検定未補正です。同じ話者の発話は独立ではない可能性があります。p値だけで結論を出さず、効果量・標本数・欠測と前提条件を確認してください。未計算 ${unavailableCount}件。`));
  grid.append(testsPanel.panel);

  const crosstabsPanel = analysisCardPanel('項目の組み合わせ比較（クロス集計）', 'automatic', 'crosstabs', true, 'group_statistics');
  if (crosstabs.length) {
    crosstabsPanel.body.append(buildAnalysisCrosstabExplorer(crosstabs, compact));
    const details = analysisElement('details', 'analysis-table-details');
    details.append(analysisElement('summary', '', 'クロス集計の数値表を確認'));
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
    details.append(wrap);
    crosstabsPanel.body.append(details);
  } else crosstabsPanel.body.append(analysisElement('p', 'analysis-no-data', 'クロス集計できるデータがありません。'));
  grid.append(crosstabsPanel.panel);

  grid.append(analysisSectionHeading(
    'exports', '04 / OUTPUT & REVIEW', '出力して検証する',
    '標準出力のExcel、再分析用CSV、手法と限界をまとめています。論文利用前に原文・欠損・解析器の状態を確認してください。'
  ));

  const rowLimits = (analysisState.data?.research || {}).row_limits || {};
  const truncatedRows = Object.entries(rowLimits).filter(([, value]) => value.truncated);
  if (truncatedRows.length) grid.append(analysisElement('p', 'analysis-limit-note', `画面用プレビュー: ${truncatedRows.map(([key, value]) => `${key} ${value.returned_rows}/${value.total_rows}行`).join('、')}。全件はCSV/Excel出力で確認してください。`));
  if (coverage.cooccurrence_truncated) grid.append(analysisElement('p', 'analysis-limit-note', `共起の候補集合: 上位${coverage.cooccurrence_top_terms}語 / 最小${coverage.cooccurrence_min_count}発話。共起行 ${coverage.cooccurrence_returned_rows}/${coverage.cooccurrence_total_rows}件。候補制限により会話全体の全関係を表しません。`));
  grid.append(analysisExportDirectory('研究分析データの出力', 'automatic', [
    ['xlsx', 'Excelブック（標準出力）'],
    ['transformer_topics', 'Transformerテーマ CSV'],
    ['transformer_assignments', 'Transformer発話分類 CSV'],
    ['transformer_speakers', 'Transformer話者比較 CSV'],
    ['transformer_timeline', 'Transformer時間推移 CSV'],
    ['transformer_outliers', 'Transformer例外候補 CSV'],
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

function analysisSpeakerRoleText(metric) {
  const label = role => Object.hasOwn(speakerRoleLabels, role) ? speakerRoleLabels[role] : String(role || '役割未設定');
  if (metric?.role_status === 'mixed') {
    const roles = Array.isArray(metric.observed_roles) ? metric.observed_roles.map(label).join('・') : '';
    return roles ? `役割混在（${roles}）` : '役割混在';
  }
  return label(metric?.role);
}

function analysisSpeakerAttributeValue(metric, key) {
  const profile = metric && typeof metric.profile === 'object' ? metric.profile : {};
  if (key === 'role') return analysisSpeakerRoleText(metric);
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
  return values.sort((a, b) => Number(a.speaking_seconds == null) - Number(b.speaking_seconds == null)
    || Number(b.speaking_seconds || 0) - Number(a.speaking_seconds || 0) || nameCompare(a, b));
}

function buildAnalysisSpeakerTimelineChart(metric, bins) {
  const module = analysisElement('div', 'analysis-chart-module');
  const explanation = analysisElement('div', 'analysis-chart-explanation');
  explanation.append(
    analysisElement('strong', '', `${metric.speaker_name || metric.speaker}の発話タイミング`),
    analysisElement('span', '', '各時間帯にこの話者が発話した秒数を示します。')
  );
  if (metric.timed_turn_count === 0 && metric.missing_time_turn_count > 0) {
    module.append(explanation, analysisElement('p', 'analysis-no-data', '時刻付きの発話がないため、この話者の時間推移は表示できません。'));
    return module;
  }
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
  module.append(explanation, stage, legend, analysisElement('p', 'analysis-chart-note', `${analysisObservedTimeText(metric)}。時刻あり発話だけを集計しています。時刻不明の発話は時間帯へ配置できません。`));
  return module;
}

function analysisMedian(values) {
  const sorted = values.map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function analysisDurationSummary(segments) {
  const durations = segments
    .filter(item => item.valid_time === true && item.duration != null && item.duration !== '')
    .map(item => Number(item.duration))
    .filter(value => Number.isFinite(value) && value >= 0);
  return {
    median: analysisMedian(durations),
    longest: durations.length ? Math.max(...durations) : null
  };
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
      ? `${groupValue} / ${analysisObservedTimeText(metric)}`
      : `${analysisSpeakerRoleText(metric)} / ${analysisObservedTimeText(metric)}`;
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
    analysisElement('p', '', `${analysisSpeakerRoleText(selected)}の発話を、インタビュー全体との比率を保ったまま表示しています。`)
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
  appendAnalysisMetric(metrics, '発話時間', analysisObservedTimeText(selected), analysisNumberText(selected.speaking_percent, 1, '%'));
  appendAnalysisMetric(metrics, '発話回数', `${selected.turn_count || 0}回`, `平均 ${analysisNumberText(selected.average_turn_seconds, 1, '秒')}`);
  appendAnalysisMetric(metrics, '文字数', `${selected.characters || 0}字`, `${analysisNumberText(selected.characters_per_minute, 1)}字/分`);
  appendAnalysisMetric(metrics, '質問候補', `${selected.question_candidates || 0}件`);
  appendAnalysisMetric(metrics, '最初の発話', selected.first_start == null ? '—' : formatTime(selected.first_start));
  appendAnalysisMetric(metrics, '最後の発話', selected.last_end == null ? '—' : formatTime(selected.last_end));
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
  terms.slice(0, compact ? 10 : 15).forEach(item => appendSearchableTermBar(
    termsPanel.body,
    item.term,
    100 * (Number(item.term_frequency) || 0) / maxTerm,
    `TF ${item.term_frequency || 0} / DF ${item.document_frequency || 0} / ${item.upos || '—'}`,
    selected.color,
    selected.speaker
  ));
  if (!terms.length) termsPanel.body.append(analysisElement('p', 'analysis-no-data', 'この話者の内容語を抽出できませんでした。'));
  termsPanel.body.append(analysisElement('p', 'analysis-caption', `内容語 ${speakerTerms.content_token_count || 0}件 / 異なり語 ${speakerTerms.unique_term_count || 0}件。GiNZA/Sudachiの解析結果を話者内で再集計しています。`));
  detailGrid.append(termsPanel.panel);

  const distributionPanel = analysisCardPanel('話者内の発話分布', 'automatic');
  const speakerSegments = (Array.isArray(data.segments) ? data.segments : [])
    .filter(item => String(item.speaker) === String(selected.speaker) && !item.excluded);
  const durationSummary = analysisDurationSummary(speakerSegments);
  const distributionMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(distributionMetrics, '中央値', analysisNumberText(durationSummary.median, 2, '秒'));
  appendAnalysisMetric(distributionMetrics, '最長発話', analysisNumberText(durationSummary.longest, 2, '秒'));
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
      : '概要から傾向をつかみ、気になる項目を選んで根拠の発話を確認できます。')
  );
  fragment.append(intro, buildAnalysisScopeSwitch());

  if (speakerScope) {
    fragment.append(renderSpeakerAnalysis(compact));
    return fragment;
  }

  const metrics = analysisElement('div', 'analysis-overview');
  appendAnalysisMetric(metrics, '時刻ありの最終終了位置', analysisEndpointText(overview.session_duration, overview.session_timed_turn_count, overview.session_missing_time_turn_count), '除外を含む全発話の時刻。録音ファイルの全長ではありません');
  appendAnalysisMetric(metrics, '対象発話', `${overview.included_segment_count || 0}件`, `全${overview.segment_count || 0}件`);
  appendAnalysisMetric(metrics, '話者', `${overview.speaker_count || 0}人`);
  appendAnalysisMetric(metrics, '実際の参加者', overview.participant_count === null || overview.participant_count === undefined ? '未登録' : `${overview.participant_count}人`, '研究者が準備画面で登録した人数');
  appendAnalysisMetric(metrics, '観測された参加発言者', overview.observed_participant_count == null ? '不明' : `${overview.observed_participant_count}人`, overview.mixed_role_speaker_count > 0 ? '同じ話者の役割が混在するため人数を確定できません' : 'UNKNOWNを除外・実参加人数とは別');
  appendAnalysisMetric(metrics, '発話時間（時刻あり）', analysisObservedTimeText(overview, 'total_speaking_seconds'));
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

  const summary = analysisElement('section', 'analysis-page');
  summary.dataset.analysisPage = 'overview';
  summary.setAttribute('aria-label', '概要');
  const observationsBox = fragment.querySelector('.analysis-observations');
  if (observationsBox) summary.append(observationsBox);
  summary.append(buildInsightSummary());
  const contentPage = analysisElement('section', 'analysis-page');
  contentPage.dataset.analysisPage = 'content';
  contentPage.setAttribute('aria-label', '内容・文脈検索');
  contentPage.append(buildContentExplorer(), buildSegmentClassificationPanel(compact), buildTransformerAnalysisPanel());
  fragment.append(buildAnalysisNavigation(), summary, contentPage);

  const grid = analysisElement('div', 'analysis-grid');
  grid.append(analysisSectionHeading(
    'conversation', '01 / CONVERSATION FLOW', '会話の流れを見る',
    'まず時間推移と話者別の参加量を見て、次に話者交替・無音・重なりの候補を確認します。'
  ));
  const speakers = Array.isArray(automatic.speaker_metrics) ? automatic.speaker_metrics : [];
  const timelinePanel = analysisCardPanel('発話量の変化（時間別）', 'automatic', 'timeline', true, 'participation');
  const bins = Array.isArray(automatic.time_bins) ? automatic.time_bins : [];
  const allTimeMissing = overview.timed_turn_count === 0 && overview.missing_time_turn_count > 0;
  if (bins.length && !allTimeMissing) timelinePanel.body.append(buildAnalysisTimelineChart(bins, speakers));
  else timelinePanel.body.append(analysisElement('p', 'analysis-no-data', '時刻付きの発話がないため、時間推移を表示できません。'));
  grid.append(timelinePanel.panel);

  const excitementPanel = analysisCardPanel('盛り上がりと議題・話題（時間別）', 'automatic', '', true, 'conversation_dynamics');
  if (allTimeMissing) excitementPanel.body.append(analysisElement('p', 'analysis-no-data', '時刻付きの発話がないため、活発度は算出できません。'));
  else excitementPanel.body.append(buildAnalysisExcitementChart(bins, data.session_outline));
  grid.append(excitementPanel.panel);

  const speakerPanel = analysisCardPanel('話者ごとの発話量', 'automatic', 'speakers', true, 'participation');
  if (!speakers.length) {
    speakerPanel.body.append(analysisElement('p', 'analysis-no-data', '発話データがありません。'));
  } else {
    speakers.forEach(item => {
      appendAnalysisBar(
        speakerPanel.body,
        item.speaker_name || item.speaker || '話者',
        item.speaking_percent,
        `${analysisNumberText(item.speaking_percent, 1, '%')} / ${analysisObservedTimeText(item)} / ${item.turn_count || 0}回`,
        item.color
      );
    });
  }
  grid.append(speakerPanel.panel);

  const balance = automatic.balance || {};
  const balancePanel = analysisCardPanel(balance.denominator === 'observed_speakers' ? '全観測話者の発言バランス' : '参加者の発言バランス', 'automatic', '', false, 'participation');
  const balanceMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(balanceMetrics, '均等度', balance.normalized_evenness == null ? '未計算' : analysisNumberText(Number(balance.normalized_evenness) * 100, 1, '%'), '観測発言者内で100%に近いほど均等');
  appendAnalysisMetric(balanceMetrics, '最大比率', analysisNumberText(balance.max_participant_percent, 1, '%'), balance.max_participant_name || '—');
  appendAnalysisMetric(balanceMetrics, 'Gini係数', analysisNumberText(balance.gini, 3), '0に近いほど均等');
  balancePanel.body.append(balanceMetrics, analysisElement('p', 'analysis-caption', `${balance.denominator_label || '観測された発言者内'} / 分母 ${balance.balance_speaker_count ?? '—'}人。${balance.denominator_note || ''} 時刻欠測 ${balance.missing_time_turn_count ?? '—'}発話。発言量の偏りを示す記述値で、発言の重要性や影響力ではありません。`));
  if (balance.unavailable_reason === 'mixed_roles') balancePanel.body.append(analysisElement('p', 'content-inline-notice', '同じ話者の役割が混在するため、参加者内の割合・均等度は算出できません。全体時間は保持しています。'));
  grid.append(balancePanel.panel);

  const moderatorPanel = analysisCardPanel('司会者と参加者の発言関係', 'automatic', '', false, 'participation');
  const moderator = automatic.moderator || {};
  const moderatorMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(moderatorMetrics, '司会発話比率', moderator.role_aggregation_status === 'mixed' ? '役割混在で算出不可' : moderator.assigned ? analysisNumberText(moderator.speaking_percent, 1, '%') : '役割未設定');
  appendAnalysisMetric(moderatorMetrics, '質問候補', moderator.role_aggregation_status === 'mixed' ? '役割混在で算出不可' : analysisNumberText(moderator.question_candidates, 0, '件'));
  appendAnalysisMetric(moderatorMetrics, '参加者応答', `${moderator.participant_responses || 0}件`);
  appendAnalysisMetric(moderatorMetrics, '参加者間遷移', `${moderator.participant_to_participant_transitions || 0}件`);
  moderatorPanel.body.append(moderatorMetrics, analysisElement('p', 'analysis-caption', '質問・応答は表記と話者遷移からの候補です。進行品質の評価ではありません。'));
  grid.append(moderatorPanel.panel);

  const transitionsPanel = analysisCardPanel('発言者の交替パターン', 'automatic', 'transitions', true, 'conversation_dynamics');
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

  const gapsPanel = analysisCardPanel('沈黙・同時発話の候補', 'automatic', 'gaps', false, 'conversation_dynamics');
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

  const emotionPanel = analysisCardPanel('声から推定した感情の分布', 'automatic', 'emotions', false, 'audio_emotion');
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
        analysisElement('span', '', `${item.count || 0}件 / ${analysisObservedTimeText(item, 'seconds')}`)
      );
      emotionPanel.body.append(row);
    });
  } else emotionPanel.body.append(analysisElement('p', 'analysis-no-data', '音声感情分析が未実行、または利用できる推定値がありません。'));
  emotionPanel.body.append(analysisElement('p', 'analysis-caption', 'モデル推定は本人の感情を確定するものではありません。'));
  grid.append(emotionPanel.panel);

  const groups = Array.isArray(automatic.groups) ? automatic.groups : [];
  if (groups.length) {
    const groupsPanel = analysisCardPanel('話者グループの比較', 'configured', 'groups', false, 'participation');
    groups.forEach(item => appendAnalysisBar(
      groupsPanel.body, item.group || '未設定', item.speaking_percent,
      `${item.speaker_count || 0}人 / ${item.turn_count || 0}回 / ${analysisObservedTimeText(item)}`,
      '#9B51E0'
    ));
    grid.append(groupsPanel.panel);
  }

  grid.append(analysisSectionHeading(
    'language', '02 / LANGUAGE STRUCTURE', '語と構文を探索する',
    '特徴語から全体像をつかみ、形態素・共起関係・文ごとの係り受けへ段階的に掘り下げます。'
  ));
  const keywordsPanel = analysisCardPanel('会話でよく使われた特徴語', 'automatic', 'keywords', false, 'lexical_frequency');
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
  // Keep existing panels and controls mounted when switching sections. This
  // preserves search input, running-job status, and the method view's panels.
  let page;
  [...grid.children].forEach(node => {
    if (node.dataset.analysisAnchor) {
      page = analysisElement('section', 'analysis-page analysis-grid');
      page.dataset.analysisPage = node.dataset.analysisAnchor;
      page.setAttribute('aria-label', node.querySelector('h2')?.textContent || '分析結果');
      fragment.append(page);
    }
    if (page) page.append(node);
  });
  fragment.querySelector('[data-analysis-page="exports"]')?.append(buildAnalysisStorage());
  applyAnalysisPage(fragment, analysisState.automaticPage);

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

function analysisMatchModeLabel(mode) {
  return ({normalized: '正規化語の完全一致', surface: '表層語の完全一致', literal: '本文の部分一致（大文字小文字を区別）'})[mode] || '一致条件未確認';
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

  container.append(analysisField('語の一致条件（文脈検索と共通）', analysisConfigControl('crosstab_match_mode', 'select', {normalized: analysisMatchModeLabel('normalized'), surface: analysisMatchModeLabel('surface'), literal: analysisMatchModeLabel('literal')})));
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
      ['category', 'カテゴリー', '例：利用上の課題'],
      ['theme', 'テーマ', '例：導入を阻む負担']
    ].forEach(([field, caption, placeholder]) => {
      const input = document.createElement('input');
      input.type = 'text';
      input.maxLength = 160;
      input.value = code[field] || '';
      input.placeholder = placeholder;
      input.dataset.analysisCodeId = code.id;
      input.dataset.analysisCodeField = field;
      body.append(analysisField(caption, input));
    });
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
      codes: [], interaction_tags: [], elicitation: 'unknown', interaction_links: [],
      dialogue_act: '', importance_score: null, review_score: null, sensitivity_score: null,
      classification_status: 'unreviewed', classification_note: '',
      memo: '', important: false, excluded: false
    };
  }
  return analysisState.annotations[segmentId];
}
