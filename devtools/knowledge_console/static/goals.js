/* Goal mode: saved settings, explicit note selection, and LLM-created drafts. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const base = "/api/knowledge-console/goals";
  let current = null;
  let busy = false;
  let assessmentDirty = false;
  let autoRun = null;
  const fields = {title: "title", objective: "objective", target_score: "score",
    target_knowledge: "knowledge", target_compression: "compression",
    target_organization: "organization", target_depth: "depth", target_index: "index",
    max_iterations: "iterations", max_tasks: "task-limit"};
  const depthLabels = ["", "1 · 内容を説明", "2 · 根拠と具体例", "3 · 適用条件と限界"];
  function node(tag, text, className) {
    const result = document.createElement(tag);
    if (text != null) result.textContent = String(text);
    if (className) result.className = className;
    return result;
  }
  function message(text, error = false) {
    $("kc-goal-message").textContent = text;
    $("kc-goal-message").classList.toggle("error", error);
  }
  function renderSliderValues() {
    const formats = {
      knowledge: (value) => `${value}件`, organization: (value) => `${value}%`,
      depth: (value) => depthLabels[Number(value)], index: (value) => `${value}%`,
      score: (value) => `${value}点`,
    };
    Object.entries(formats).forEach(([key, format]) => {
      const input = $("kc-goal-" + key);
      const output = $("kc-goal-" + key + "-output");
      if (input && output) output.value = format(input.value);
    });
  }
  function setAutoStatus(text, tone = "") {
    const status = $("kc-goal-auto-status");
    status.textContent = text;
    status.className = `kc-goal-auto-status ${tone}`.trim();
    $("kc-goal-auto-stop").hidden = !autoRun;
    $("kc-goal-auto-start").disabled = Boolean(autoRun);
  }
  async function request(url, method = "GET", payload) {
    const options = {method, headers: {"X-Knowledge-Console-Request": "1"}};
    if (payload !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(payload);
    }
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }
  async function action(operation) {
    if (busy) return;
    busy = true;
    document.querySelectorAll("#kc-goals button, #kc-goals input, #kc-goals textarea, #kc-goals select").forEach((el) => {
      el.dataset.goalWasDisabled = String(el.disabled); el.disabled = true;
    });
    try { await operation(); }
    catch (error) { message(error.message, true); }
    finally {
      busy = false;
      document.querySelectorAll("#kc-goals [data-goal-was-disabled]").forEach((el) => {
        el.disabled = el.dataset.goalWasDisabled === "true"; delete el.dataset.goalWasDisabled;
      });
      $("kc-goal-add-note").disabled = !current;
      $("kc-goal-auto-start").disabled = Boolean(autoRun);
      $("kc-goal-auto-stop").hidden = !autoRun;
    }
  }
  async function list(selected) {
    const data = await request(base);
    const options = [new Option("新しい目標", ""), ...data.goals.map((g) => new Option(g.title, g.goal_id))];
    $("kc-goal-select").replaceChildren(...options);
    $("kc-goal-select").value = selected || "";
  }
  function render(goal, fillForm = true) {
    current = goal;
    $("kc-goal-work").hidden = !goal;
    $("kc-goal-quick").hidden = !goal;
    $("kc-goal-overview").hidden = !goal;
    $("kc-goal-open-vault").hidden = !goal;
    $("kc-goal-add-note").disabled = !goal;
    $("kc-goal-save").textContent = goal ? "目標設定を保存" : "保存して一時Vaultを作成";
    $("kc-goal-vault-path").textContent = goal?.vault_path || "目標を保存すると、一時Vaultが作成されます。";
    if (!goal) {
      $("kc-goal-form").reset();
      assessmentDirty = false;
      $("kc-goal-artifact-form").reset();
      renderSliderValues();
      return;
    }
    if (fillForm) Object.entries(fields).forEach(([key, suffix]) => { $("kc-goal-" + suffix).value = goal[key]; });
    renderSliderValues();
    $("kc-goal-open-vault").href = goal.obsidian_uri;
    const m = goal.metrics;
    const currentValues = {
      knowledge: `${m.knowledge_count}件`,
      organization: m.organization_rate == null ? "未測定" : `${formatNumber(m.organization_rate)}%`,
      depth: m.depth == null ? "未測定" : `平均 ${formatNumber(m.depth)} · 到達 ${m.depth_reached_count}/${m.scope_count}件`,
      index: m.index_rate == null ? "未測定" : `${formatNumber(m.index_rate)}%`,
      score: goal.artifact_score == null ? "未評価" : `${goal.artifact_score}点`,
    };
    Object.entries(currentValues).forEach(([axis, value]) => {
      const label = document.querySelector(`[data-current-axis="${axis}"]`);
      if (label) label.textContent = `現在 ${value}`;
    });
    renderProgress(goal);
    renderCharts(goal);
    if (fillForm || !assessmentDirty) renderAssessment(goal);
    $("kc-goal-retrieval-results").replaceChildren(...m.retrieval_results.map((c) => {
      const result = node("p", `${c.passed ? "✓ 到達" : "未到達"} · ${c.question}`, "kc-goal-help");
      result.append(node("small", ` ／ 上位候補: ${c.found_ids.map((id) => goal.notes.find((n) => n.note_id === id)?.title || id).join("、") || "なし"}`));
      return result;
    }));
    const evaluation = goal.artifact_evaluation;
    $("kc-goal-artifact-result").textContent = evaluation ?
      `${evaluation.stale ? "再評価が必要（過去の評価）" : "評価済み"} · ${evaluation.score}点 · ${evaluation.scorer} · ${evaluation.rubric}\n${evaluation.feedback}` : "まだ成果物を評価していません。";
    const selected = new Set([...document.querySelectorAll("#kc-goal-notes input:checked")].map((n) => n.value));
    $("kc-goal-notes").replaceChildren(...goal.notes.map((note, index) => {
      const label = node("label", null, "kc-goal-note");
      const check = document.createElement("input"); check.type = "checkbox"; check.value = note.note_id;
      check.checked = selected.size ? selected.has(note.note_id) : index < 3;
      label.append(check, node("span", note.title)); return label;
    }));
    if (!goal.notes.length) $("kc-goal-notes").append(node("p", "知識ノートを追加してください。"));
    $("kc-goal-tasks").replaceChildren(...goal.tasks.map((task) => {
      const card = node("article", null, "kc-goal-task");
      const dimension = {score: "成果物の改善", knowledge: "必要な知識の補充", organization: "整理", depth: "深さ", index: "インデックス", compression: "圧縮（旧タスク）"}[task.proposal.dimension];
      const labels = {draft: "未実行", running: "実行中",
        succeeded: task.quality_state === "evidence_checked" ? "引用照合済み・要評価" : "応答受信・未評価",
        failed: task.quality_state === "needs_input" ? "入力不足" : "要確認"};
      card.append(node("strong", task.title), node("span", `${dimension} · ${labels[task.status] || task.status}`),
        node("p", task.proposal.reason), node("small", task.proposal.focus));
      card.append(node("small", `参照: ${task.proposal.source_ids.map((id) => goal.notes.find((n) => n.note_id === id)?.title || id).join("、")}`));
      if (task.score != null) card.append(node("b", `タスク評価 ${task.score} / 目標 ${task.target_score}点（${task.iteration}/${task.max_iterations}回）`));
      if (task.error_message) card.append(node("p", task.error_message));
      return card;
    }));
    if (!goal.tasks.length) $("kc-goal-tasks").append(node("p", "まだタスクは生成されていません。"));
  }
  function svgNode(tag, attrs = {}, text) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
    if (text != null) el.textContent = text;
    return el;
  }
  function formatNumber(value) { return Number(value.toFixed(1)).toLocaleString("ja-JP"); }
  function formatDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("ja-JP", {month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit"});
  }
  function jumpTo(id) {
    const el = $(id);
    el.scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start"});
    const target = el.matches("input,button,textarea,select") ? el : el.querySelector("input,button,textarea,select");
    if (target && !target.closest("details:not([open])")) target.focus({preventScroll: true});
    else { el.tabIndex = -1; el.focus({preventScroll: true}); }
  }
  function progressAxes(goal) {
    const m = goal.metrics, stale = m.stale_ids.length > 0;
    const depthCount = m.scope_count ? m.depth_reached_count : null;
    const depthNames = ["", "説明", "根拠と具体例", "適用条件と限界"];
    return [
      {key: "knowledge", title: "知識量", value: m.knowledge_count, unit: "件", target: goal.target_knowledge,
        max: Math.max(goal.target_knowledge, m.knowledge_count, 1) * 1.15,
        detail: `目標に必要な対象ノート · Vault全体 ${goal.knowledge_count}件`, action: "対象ノートを選ぶ", to: "kc-goal-assessment-form"},
      {key: "organization", title: "整理", value: m.organization_rate, unit: "%", target: goal.target_organization, max: 100, stale,
        detail: `重複・矛盾・出典を確認済み ${m.organized_count} / ${m.scope_count}件`, action: "整理の不足を確認", to: "kc-goal-assessment-form"},
      {key: "depth", title: "深さ", value: depthCount, unit: "件", target: m.scope_count, max: Math.max(m.scope_count, 1), stale,
        detail: `深さ${goal.target_depth}「${depthNames[goal.target_depth]}」に到達したノート`, action: "深さの不足を確認", to: "kc-goal-assessment-form"},
      {key: "index", title: "インデックス", value: m.index_rate, unit: "%", target: goal.target_index, max: 100,
        detail: `検索成功 ${m.retrieval_results.filter((r) => r.passed).length} / ${m.retrieval_results.length}問`, action: "検索テストを確認", to: "kc-goal-cases"},
      {key: "score", title: "成果物の品質", value: goal.artifact_score, unit: "点", target: goal.target_score, max: 100,
        stale: Boolean(goal.artifact_evaluation?.stale), detail: "実際のプロンプト・成果物・根拠で評価", action: "成果物を評価する", to: "kc-goal-artifact-form"}
    ].map((axis) => ({...axis, met: axis.value != null && !axis.stale && axis.value >= axis.target}));
  }
  function renderProgress(goal) {
    const axes = progressAxes(goal), met = axes.filter((a) => a.met).length;
    const summary = node("div", null, "kc-goal-summary-main");
    summary.append(node("span", "GOAL PROGRESS", "kc-goal-kicker"), node("h3", goal.title));
    summary.append(node("p", goal.goal_reached ? "すべての達成条件を満たしました" : `5つの達成条件のうち ${met}つを満たしています`, "kc-goal-summary-caption"));
    const milestones = node("div", null, "kc-goal-milestones");
    axes.forEach((a) => milestones.append(node("span", `${a.met ? "✓" : a.stale ? "↻" : "○"} ${a.title}`, a.met ? "met" : a.stale ? "stale" : "")));
    summary.append(milestones, node("small", "達成条件は個別に判定。点数の平均ではありません。"));
    const forecast = node("div", null, "kc-goal-forecast");
    forecast.append(node("span", "スコア到達までの予想"), node("strong", goal.forecast_iterations == null ? "まだ推定できません" : goal.forecast_iterations === 0 ? "スコア目標に到達" : `あと約 ${goal.forecast_iterations} 回`),
      node("small", goal.forecast_iterations == null ? "同じ条件で異なる成果物を3回以上評価し、連続した改善が必要です。" : goal.forecast_iterations === 0 ? "ほかの達成条件は左の一覧で確認できます。" : "直近3評価の改善幅からの目安。目標全体の完了予測ではありません。"));
    $("kc-goal-progress-summary").replaceChildren(summary, forecast);
    $("kc-goal-metrics").replaceChildren(...axes.map((a) => {
      const card = node("div", null, `kc-goal-metric ${a.met ? "met" : a.stale ? "stale" : a.value == null ? "unknown" : "pending"}`);
      card.dataset.axis = a.key;
      const heading = node("div", null, "kc-goal-metric-heading");
      heading.append(node("span", a.title), node("span", a.stale ? "再確認" : a.met ? "達成" : a.value == null ? "未評価" : "進行中", "kc-goal-state"));
      const figures = node("div", null, "kc-goal-metric-figures");
      const targetText = a.key === "depth" && a.value == null ? "対象ノートを選択" : `目標 ${a.target}${a.unit}`;
      figures.append(node("strong", a.value == null ? "—" : formatNumber(a.value)), node("span", a.unit), node("small", targetText));
      const svg = svgNode("svg", {viewBox: "0 0 240 22", role: "img", "aria-label": `${a.title}: ${a.stale ? "再確認が必要。" : ""}${a.value == null ? "未評価" : `現在 ${a.value}${a.unit}`}、${targetText}`});
      const width = Math.max(0, Math.min(228, (a.value ?? 0) / a.max * 228));
      const marker = 6 + a.target / a.max * 228;
      svg.append(svgNode("rect", {x: 6, y: 8, width: 228, height: 7, rx: 3.5, fill: "#e9edf3"}),
        svgNode("rect", {x: 6, y: 8, width, height: 7, rx: 3.5, fill: a.stale ? "#9da9ba" : a.met ? "#22816b" : "#526bd6"}));
      if (a.key !== "depth" || a.value != null) svg.append(svgNode("line", {x1: marker, x2: marker, y1: 3, y2: 20, stroke: "#344258", "stroke-width": 2}));
      const gap = a.stale ? "内容の変更を確認してください" : a.value == null ? "評価を記録すると残りを表示" : a.met ? "目標を満たしています" :
        `あと ${formatNumber(Math.max(0, a.target - a.value))}${a.unit === "%" ? "ポイント" : a.unit}${a.key === "depth" ? "で全対象が到達" : ""}`;
      card.append(heading, figures, svg, node("b", gap, "kc-goal-gap"), node("small", a.detail));
      return card;
    }));
    const next = $("kc-goal-next-actions");
    const pending = axes.filter((a) => !a.met).sort((a, b) => Number(Boolean(b.stale)) - Number(Boolean(a.stale)));
    next.replaceChildren(node("h4", goal.goal_reached ? "達成した知識を次の成果物へ" : "次に取り組むこと"));
    if (goal.goal_reached) next.append(node("p", "今回の成果物と根拠を確認して、次の目標を設定できます。"));
    else {
      const selected = pending.slice(0, 3);
      selected.forEach((a, i) => {
        const item = node("div", null, "kc-goal-next-item");
        item.append(node("span", String(i + 1).padStart(2, "0"), "kc-goal-next-number"));
        const button = node("button", `${a.stale ? "変更された内容を再確認" : a.action} →`, "kc-button"); button.type = "button";
        button.addEventListener("click", () => jumpTo(a.to));
        item.append(node("span", a.title), button); next.append(item);
      });
    }
    const omitted = goal.history.filter((h) => !h.comparable).length;
    $("kc-goal-progress-status").textContent = `実線は記録時点の実測値、破線は目標。点を選ぶと数値を確認できます。${omitted ? `条件の異なる${omitted}記録はグラフから除外しています。` : ""}` +
      (goal.metrics.stale_ids.length || goal.artifact_evaluation?.stale ? " 内容変更前の履歴が含まれます。現在の有効な値は上のカードで確認してください。" : "");
  }
  function control(tag, name, value, type) {
    const el = node(tag); el.dataset.field = name;
    if (type) el.type = type;
    if (type === "checkbox") el.checked = Boolean(value);
    else el.value = value == null ? "" : value;
    return el;
  }
  function labeled(text, input) {
    const label = node("label", null, "kc-field"); label.append(node("span", text), input); return label;
  }
  function renderAssessment(goal) {
    assessmentDirty = false;
    const assessment = goal.assessment;
    $("kc-goal-reviews").replaceChildren(...goal.notes.map((note) => {
      const r = assessment.reviews.find((v) => v.note_id === note.note_id);
      const fresh = r && r.sha256 === note.sha256;
      const box = node("details", null, "kc-goal-review"); box.dataset.noteId = note.note_id; box.dataset.sha256 = note.sha256;
      box.append(node("summary", note.title + (r && !fresh ? " · 内容変更・再確認が必要" : "")));
      box.append(labeled("目標に必要な対象ノート", control("input", "scope", assessment.scope_ids.includes(note.note_id), "checkbox")),
        labeled("内容を読み、以下の確認記録を保存する", control("input", "reviewed", fresh, "checkbox")));
      for (const [key, label] of [["duplicates_checked", "重複を確認した"], ["conflicts_checked", "矛盾を確認・明示した"], ["sources_checked", "出典を確認できる"]]) {
        box.append(labeled(label, control("input", key, r?.[key], "checkbox")));
      }
      const depth = control("select", "depth");
      depth.replaceChildren(...["0 · 未整理・説明が不足", "1 · 内容を説明できる", "2 · 根拠と具体例がある", "3 · 適用条件と限界がわかる"].map((label, i) => new Option(label, i)));
      depth.value = r?.depth ?? 0;
      const evidence = control("textarea", "evidence", r?.evidence); evidence.rows = 2; evidence.maxLength = 600;
      box.append(labeled("確認した深さ", depth), labeled("確認した根拠・不足している点（確認記録には必須）", evidence));
      return box;
    }));
    $("kc-goal-cases").replaceChildren();
    assessment.cases.forEach(addCase);
  }
  function addCase(data = {}) {
    if (!current || $("kc-goal-cases").children.length >= 20) return;
    const row = node("div", null, "kc-goal-case");
    const question = control("input", "question", data.question); question.maxLength = 240; question.required = true;
    const terms = control("input", "terms", (data.terms || []).join(" ")); terms.required = true;
    const expected = control("select", "expected_ids"); expected.multiple = true; expected.required = true; expected.size = 3;
    current.notes.forEach((n) => { const option = new Option(n.title, n.note_id); option.selected = data.expected_ids?.includes(n.note_id); expected.append(option); });
    row.append(labeled("想定する質問", question), labeled("検索語（空白区切り・すべて含むノートを検索）", terms), labeled("到達したい対象ノート（最大5件・複数選択可）", expected));
    const remove = node("button", "この質問を削除", "kc-button"); remove.type = "button";
    remove.addEventListener("click", () => { row.remove(); assessmentDirty = true; }); row.append(remove);
    $("kc-goal-cases").append(row);
  }
  function assessmentPayload() {
    const scope_ids = [], reviews = [];
    for (const box of $("kc-goal-reviews").children) {
      const get = (key) => box.querySelector(`[data-field="${key}"]`);
      if (!get("scope").checked) continue;
      scope_ids.push(box.dataset.noteId);
      if (!get("reviewed").checked) continue;
      reviews.push({note_id: box.dataset.noteId, sha256: box.dataset.sha256, depth: Number(get("depth").value),
        evidence: get("evidence").value, ...Object.fromEntries(["duplicates_checked", "conflicts_checked", "sources_checked"].map((k) => [k, get(k).checked]))});
    }
    const cases = [...$("kc-goal-cases").children].map((box) => {
      const get = (key) => box.querySelector(`[data-field="${key}"]`);
      return {question: get("question").value, terms: get("terms").value.trim().split(/\s+/u), expected_ids: [...get("expected_ids").selectedOptions].map((o) => o.value)};
    });
    return {scope_ids, reviews, cases, goal_revision: current.revision, revision: current.assessment_revision};
  }
  function savedSettings() {
    if (!current) return false;
    const unsaved = Object.entries(fields).some(([key, suffix]) => {
      const value = $("kc-goal-" + suffix).value;
      return typeof current[key] === "number" ? Number(value) !== current[key] : value !== current[key];
    });
    if (unsaved) { message("目標値が変更されています。先に目標設定を保存してください。", true); return false; }
    if (assessmentDirty) { message("対象・確認記録が変更されています。先に保存して計測してください。", true); return false; }
    return true;
  }
  function settingsPayload() {
    return Object.fromEntries(Object.entries(fields).map(([key, suffix]) => [key, $("kc-goal-" + suffix).value]));
  }
  async function saveChangedSettings() {
    if (!current) throw new Error("先に目標を保存してください。");
    if (assessmentDirty) throw new Error("対象・確認記録が変更されています。先に保存して計測してください。");
    const payload = settingsPayload();
    const changed = Object.entries(fields).some(([key]) =>
      typeof current[key] === "number" ? Number(payload[key]) !== current[key] : payload[key] !== current[key]);
    if (!changed) return current;
    const data = await request(`${base}/${current.goal_id}`, "PATCH", {...payload, revision: current.revision});
    render(data.goal);
    await list(data.goal.goal_id);
    return data.goal;
  }
  function selectedNoteIds() {
    const checked = [...document.querySelectorAll("#kc-goal-notes input:checked")].map((n) => n.value);
    const fallback = current?.assessment?.scope_ids?.length ? current.assessment.scope_ids : current?.notes?.map((n) => n.note_id) || [];
    return (checked.length ? checked : fallback).slice(0, 3);
  }
  async function measureCurrent() {
    if (!current) throw new Error("先に目標を保存してください。");
    let data;
    if (current.assessment.scope_ids.length && !assessmentDirty) {
      data = await request(`${base}/${current.goal_id}/measure`, "POST", {
        goal_revision: current.revision, revision: current.assessment_revision,
      });
    } else {
      data = await request(`${base}/${current.goal_id}`);
    }
    render(data.goal, false);
    return data.goal;
  }
  async function startAutoGoal() {
    if (autoRun) return;
    await saveChangedSettings();
    autoRun = {goalId: current.goal_id, stopped: false};
    setAutoStatus("現在値を測定しています…", "running");
    try {
      const measured = await measureCurrent();
      if (measured.goal_reached) {
        autoRun = null;
        setAutoStatus("すべての目標値に到達しています。", "done");
        return;
      }
      const note_ids = selectedNoteIds();
      if (!note_ids.length) throw new Error("タスク生成の根拠となる知識ノートを1件以上追加してください。");
      if (autoRun.stopped) throw new Error("自動処理を停止しました。");
      setAutoStatus("スライダーとの差をもとに、内部LLMがタスクを生成しています…", "running");
      const before = new Set(measured.tasks.map((task) => task.task_id));
      const data = await request(`${base}/${measured.goal_id}/generate`, "POST", {note_ids, revision: measured.revision});
      render(data.goal, false);
      const candidates = data.goal.tasks.filter((task) => task.status === "draft" && (!before.has(task.task_id) || data.reused));
      if (!candidates.length) throw new Error("同じ条件のタスクは実行済みです。知識や確認記録を更新して、現在値を再測定してください。");
      setAutoStatus(`${candidates.length}件を生成しました。A100へ送り、各タスクを目標点まで改善します…`, "running");
      document.dispatchEvent(new CustomEvent("kc-run-goal-tasks", {
        detail: {goalId: measured.goal_id, taskIds: candidates.map((task) => task.task_id)},
      }));
      document.dispatchEvent(new Event("kc-goals-updated"));
    } catch (error) {
      autoRun = null;
      setAutoStatus(error.message, "error");
      throw error;
    }
  }
  function renderCharts(goal) {
    const all = goal.history.filter((h) => h.comparable);
    const limit = Number($("kc-goal-history-range").value);
    const slice = (rows) => limit ? rows.slice(-limit) : rows;
    const series = [
      {title: "知識を蓄え、整理する", unit: "件", max: Math.max(goal.target_knowledge, ...all.map((h) => h.metrics.knowledge_count), 1) * 1.15,
        target: goal.target_knowledge, targetLabel: "知識量の目標",
        lines: [["対象ノート", "#4263d5", (h) => h.metrics.knowledge_count], ["整理済み", "#16836b", (h) => h.metrics.organized_count]]},
      {title: `深さ${goal.target_depth}に到達した知識`, unit: "%", max: 100, target: 100, targetLabel: "全対象の到達",
        lines: [["到達したノートの割合", "#8153ad", (h) => h.metrics.scope_count ? h.metrics.depth_reached_count / h.metrics.scope_count * 100 : null]]},
      {title: "必要な知識を見つける", unit: "%", max: 100, target: goal.target_index, targetLabel: "検索到達率の目標", lines: [["検索到達率", "#16836b", (h) => h.metrics.index_rate]]},
      {title: "成果物の品質を高める", unit: "点", max: 100, target: goal.target_score, targetLabel: "スコアの目標", artifact: true, lines: [["総合スコア", "#4263d5", (h) => h.score]]}
    ];
    $("kc-goal-charts").replaceChildren(...series.map((s) => {
      const panel = node("div", null, "kc-goal-chart"); panel.append(node("h4", s.title));
      const rows = slice(s.artifact ? all.filter((h) => h.kind === "artifact") : all);
      const values = rows.map(s.lines[0][2]).filter((v) => v != null);
      if (!values.length) {
        panel.append(node("p", "まだ評価の記録がありません", "kc-goal-chart-empty"), node("small", s.artifact ? "実際の成果物を評価すると、目標との差が分かります。" : "対象と確認記録を保存すると、推移を表示します。"));
        return panel;
      }
      const chartHeader = node("div", null, "kc-goal-chart-values");
      chartHeader.append(node("strong", `${formatNumber(values.at(-1))}${s.unit}`), node("span", `${s.targetLabel} ${s.target}${s.unit}`));
      panel.append(chartHeader);
      const first = values[0], last = values.at(-1), delta = last - first;
      panel.append(node("small", values.length < 2 ? "初回の記録 · 次の評価から変化を表示" : `表示範囲の初回比 ${delta > 0 ? "+" : ""}${formatNumber(delta)}${s.unit === "%" ? "ポイント" : s.unit} · ${rows.length}記録`, "kc-goal-chart-delta"));
      const svg = svgNode("svg", {viewBox: "0 0 480 218", role: "group", "aria-label": `${s.title}の推移。点はキーボードでも選べます。`});
      const x = (i) => rows.length === 1 ? 240 : 42 + i * 400 / (rows.length - 1), y = (v) => 170 - v * 128 / s.max;
      [0, s.max / 2, s.max].forEach((v) => { svg.append(svgNode("line", {x1: 42, x2: 448, y1: y(v), y2: y(v), stroke: "#e1e5ec"}), svgNode("text", {x: 3, y: y(v) + 4, fill: "#637084", "font-size": 11}, formatNumber(v))); });
      svg.append(svgNode("line", {x1: 42, x2: 448, y1: y(s.target), y2: y(s.target), stroke: "#7f8b9e", "stroke-dasharray": "5 5"}),
        svgNode("text", {x: 447, y: y(s.target) - 8, fill: "#526078", "font-size": 11, "text-anchor": "end"}, `目標 ${s.target}${s.unit}`));
      const legend = node("div", null, "kc-goal-chart-legend");
      const readout = node("p", null, "kc-goal-chart-readout"); readout.setAttribute("aria-live", "polite");
      const show = (row) => {
        readout.textContent = `${formatDate(row.created_at)} · 記録 #${row.sequence} ／ ` + s.lines.map(([name, , read]) => `${name} ${read(row) == null ? "未評価" : formatNumber(read(row)) + s.unit}`).join(" · ");
      };
      s.lines.forEach(([name, color, read]) => {
        let previous = null;
        rows.forEach((row, i) => {
          const v = read(row); if (v == null) { previous = null; return; }
          if (previous) svg.append(svgNode("line", {x1: previous[0], y1: previous[1], x2: x(i), y2: y(v), stroke: color, "stroke-width": 2.5}));
          const dot = svgNode("circle", {cx: x(i), cy: y(v), r: 4.5, fill: color, stroke: "#fff", "stroke-width": 1.5, tabindex: 0, role: "button",
            "aria-label": `記録${row.sequence} ${formatDate(row.created_at)} ${name} ${formatNumber(v)}${s.unit}`});
          ["pointerenter", "focus", "click"].forEach((event) => dot.addEventListener(event, () => show(row)));
          dot.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); show(row); } });
          dot.append(svgNode("title", {}, `${formatDate(row.created_at)} ${name}: ${formatNumber(v)}${s.unit}`));
          svg.append(dot); previous = [x(i), y(v)];
        });
        const label = node("span", name); label.style.color = color; legend.append(label);
      });
      const ticks = [...new Set([0, Math.floor((rows.length - 1) / 2), rows.length - 1])];
      ticks.forEach((i) => svg.append(svgNode("text", {x: x(i), y: 197, fill: "#637084", "font-size": 11, "text-anchor": rows.length === 1 ? "middle" : i === 0 ? "start" : i === rows.length - 1 ? "end" : "middle"}, `#${rows[i].sequence} · ${formatDate(rows[i].created_at)}`)));
      show(rows.at(-1));
      panel.append(legend, svg, readout); return panel;
    }));
    const table = node("table");
    const head = node("tr"); ["計測日時", "比較条件", "知識量", "整理済み", "深さ（平均）", "検索到達率", "成果物"].forEach((t) => { const th = node("th", t); th.scope = "col"; head.append(th); }); table.append(head);
    goal.history.forEach((h) => { const row = node("tr"); [h.created_at, h.comparable ? "現在と同じ" : "変更前", h.metrics.knowledge_count, h.metrics.organized_count, h.metrics.depth ?? "未評価", h.metrics.index_rate == null ? "未測定" : `${h.metrics.index_rate}%`, h.score ?? "—"].forEach((v) => row.append(node("td", v))); table.append(row); });
    $("kc-goal-history").replaceChildren(table);
  }
  $("kc-goal-history-range").addEventListener("change", () => { if (current) renderCharts(current); });
  $("kc-goal-form").addEventListener("submit", (event) => {
    event.preventDefault();
    void action(async () => {
      const payload = settingsPayload();
      const data = await request(current ? `${base}/${current.goal_id}` : base, current ? "PATCH" : "POST",
        {...payload, ...(current ? {revision: current.revision} : {})});
      render(data.goal); await list(current.goal_id); message("目標を保存しました。知識ノートを用意してタスクを生成できます。");
    });
  });
  $("kc-goal-note-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!current) return;
    void action(async () => {
      const data = await request(`${base}/${current.goal_id}/notes`, "POST", {
        title: $("kc-goal-note-title").value, content: $("kc-goal-note-content").value});
      render(data.goal, false); $("kc-goal-note-form").reset(); message("一時Vaultに知識ノートを追加しました。");
    });
  });
  $("kc-goal-generate").addEventListener("click", () => {
    if (!savedSettings()) return;
    const note_ids = [...document.querySelectorAll("#kc-goal-notes input:checked")].map((n) => n.value);
    if (!note_ids.length || note_ids.length > 3) { message("参照ノートを1〜3件選択してください。", true); return; }
    void action(async () => {
      message("ローカルLLMがノートと目標からタスクを考えています…");
      const data = await request(`${base}/${current.goal_id}/generate`, "POST", {note_ids, revision: current.revision});
      render(data.goal, false);
      message(data.reused ? "同じ目標・ノートから生成済みのタスクを表示しています。" : `${data.created_count}件のタスクを追加しました。「A100タスクで実行」から開始できます。`);
      document.dispatchEvent(new Event("kc-goals-updated"));
    });
  });
  $("kc-goal-assessment-form").addEventListener("input", () => { assessmentDirty = true; });
  $("kc-goal-assessment-form").addEventListener("change", () => { assessmentDirty = true; });
  $("kc-goal-add-case").addEventListener("click", () => { addCase(); assessmentDirty = true; });
  $("kc-goal-assessment-form").addEventListener("submit", (event) => {
    event.preventDefault(); if (!current) return;
    void action(async () => {
      const data = await request(`${base}/${current.goal_id}/assessment`, "POST", assessmentPayload());
      assessmentDirty = false; render(data.goal, false); message("対象・確認記録を保存し、進捗を計測しました。");
    });
  });
  $("kc-goal-measure").addEventListener("click", () => {
    if (!savedSettings()) return;
    void action(async () => {
      const data = await request(`${base}/${current.goal_id}/measure`, "POST", {goal_revision: current.revision, revision: current.assessment_revision});
      render(data.goal, false); message("保存済みの質問と検索語で再計測しました。");
    });
  });
  $("kc-goal-measure-now").addEventListener("click", () => {
    void action(async () => {
      await saveChangedSettings();
      const goal = await measureCurrent();
      const missing = goal.unmet_dimensions.length;
      message(`現在の5項目を測定しました。目標未達または未評価は${missing}項目です。`);
    });
  });
  $("kc-goal-auto-start").addEventListener("click", () => {
    void action(async () => { await startAutoGoal(); });
  });
  $("kc-goal-auto-stop").addEventListener("click", () => {
    if (!autoRun) return;
    autoRun.stopped = true;
    autoRun = null;
    setAutoStatus("次の自動処理を停止しました。送信済みのタスク結果は保存されます。");
  });
  document.addEventListener("kc-goal-tasks-finished", (event) => {
    if (!autoRun || event.detail?.goalId !== autoRun.goalId) return;
    const run = autoRun;
    autoRun = null;
    void action(async () => {
      const data = await request(`${base}/${run.goalId}`);
      render(data.goal, false);
      if (!event.detail.ok) {
        setAutoStatus(event.detail.message || "自動実行を完了できませんでした。", "error");
        return;
      }
      const pendingReview = data.goal.unmet_dimensions.filter((key) => ["organization", "depth", "index"].includes(key));
      setAutoStatus(data.goal.goal_reached ? "目標に到達しました。" :
        `1サイクル完了。各タスクは設定点まで反復しました。${pendingReview.length ? "整理・深さ・検索は結果を確認して再測定してください。" : "現在値を再測定できます。"}`, "done");
      message("目標タスクの自動実行が完了しました。結果と現在スコアを確認してください。");
    });
  });
  $("kc-goal-artifact-form").addEventListener("submit", (event) => {
    event.preventDefault(); if (!savedSettings()) return;
    const note_ids = [...document.querySelectorAll("#kc-goal-notes input:checked")].map((n) => n.value);
    void action(async () => {
      message("ローカルLLMが実際の成果物と根拠を評価しています…");
      const data = await request(`${base}/${current.goal_id}/evaluate`, "POST", {goal_revision: current.revision,
        revision: current.assessment_revision, note_ids, prompt: $("kc-goal-artifact-prompt").value, artifact: $("kc-goal-artifact-content").value});
      render(data.goal, false); message("成果物の評価を記録しました。改善点を次のタスクに反映できます。");
    });
  });
  $("kc-goal-select").addEventListener("change", () => {
    const id = $("kc-goal-select").value;
    void action(async () => { render(id ? (await request(`${base}/${id}`)).goal : null); message(""); });
  });
  $("kc-goal-new").addEventListener("click", () => { render(null); $("kc-goal-select").value = ""; message(""); });
  $("kc-goal-reload").addEventListener("click", () => { void action(async () => {
    const id = current?.goal_id; await list(id);
    if (id) render((await request(`${base}/${id}`)).goal);
    message("最新のノートと実行状態を読み込みました。");
  }); });
  ["knowledge", "organization", "depth", "index", "score"].forEach((key) => {
    $("kc-goal-" + key).addEventListener("input", renderSliderValues);
  });
  renderSliderValues();
  void action(async () => { await list(); render(null); });
})();
