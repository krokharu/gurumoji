/* Standalone Knowledge Control Center development UI. */
(() => {
  "use strict";

  const bootstrapNode = document.getElementById("kc-bootstrap");
  const bootstrap = JSON.parse(bootstrapNode?.textContent || "{}");
  const state = {
    experts: bootstrap.experts || [],
    models: bootstrap.models || [],
    tasks: [],
    trace: null,
    playbackTimer: null,
    playbackIndex: 0,
    advancingTasks: new Map(),
    batchRunning: false,
    a100Plan: new Map(),
    openResults: new Set(),
    localLlmState: "not_checked",
    connection: null,
    errorCursor: null,
    errorLoading: false,
  };
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  async function requestJson(url, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body) headers.set("Content-Type", "application/json");
    if ((options.method || "GET").toUpperCase() !== "GET") headers.set("X-Knowledge-Console-Request", "1");
    const response = await fetch(url, {...options, headers});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  }

  function showAlert(message, kind = "success") {
    const alert = $("#kc-alert");
    alert.textContent = message;
    alert.className = `kc-alert ${kind}`;
    alert.hidden = false;
    window.clearTimeout(showAlert.timer);
    if (kind !== "error") showAlert.timer = window.setTimeout(() => { alert.hidden = true; }, 5000);
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("ja-JP");
  }

  function fillSelect(select, items) {
    select.replaceChildren(...items.map((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.name;
      return option;
    }));
  }

  function statusBadge(status, simulated = false, qualityState = null) {
    // A simulated playback is not a real A100 result, so it is labelled apart from "完了".
    if (status === "succeeded" && simulated) {
      const span = document.createElement("span");
      span.className = "kc-badge muted";
      span.textContent = "模擬完了";
      span.title = "シミュレーションで完了。A100実モデルでは未実行です。";
      return span;
    }
    if (!simulated && qualityState && ["succeeded", "failed"].includes(status)) {
      const span = document.createElement("span");
      const labels = {unverified: "応答受信・未評価", evidence_checked: "引用照合済み・要評価",
        needs_input: "入力不足", invalid: "根拠要確認"};
      span.className = "kc-badge warning";
      span.textContent = status === "failed" && qualityState === "unverified" ? "失敗" : labels[qualityState] || "要評価";
      if (status === "failed" && qualityState === "evidence_checked") span.textContent = "目標未達（引用照合済み）";
      return span;
    }
    const label = {
      draft: "下書き", queued: "待機中", running: "実行中", succeeded: "完了", failed: "失敗",
      accepted: "受理済み", not_started: "未推論",
    }[status] || status;
    const span = document.createElement("span");
    span.className = `kc-badge ${status === "succeeded" || status === "accepted" ? "success" : status === "running" ? "cyan" : status === "failed" ? "warning" : "muted"}`;
    span.textContent = label;
    return span;
  }

  function renderSummary(summary) {
    $("#kc-runtime-gpu").textContent = summary.runtime.gpu;
    $("#kc-runtime-state").textContent = summary.runtime.state === "not_connected" ? "接続待ち" : summary.runtime.state;
    $("#kc-runtime-session").textContent = new Date((summary.runtime.session_seconds || 0) * 1000).toISOString().slice(11, 19);
    $("#kc-runtime-heartbeat").textContent = formatDate(summary.runtime.heartbeat);
    $("#kc-task-count").textContent = String(summary.counts.tasks);
    $("#kc-pack-count").textContent = String(summary.counts.packs);
    const averageProgress = summary.counts.average_progress || 0;
    $("#kc-task-progress").style.width = `${averageProgress}%`;
    $("#kc-task-progress-label").textContent = `${averageProgress}%`;
    $("#kc-budget-state").textContent = String(summary.budget.state || "unknown").toUpperCase();
    $("#kc-budget-message").textContent = summary.budget.message;
    $("#kc-last-updated").textContent = `更新 ${new Date().toLocaleTimeString("ja-JP")}`;
    if (state.connection) renderRuntimeConnection(state.connection);
  }

  function renderRuntimeConnection(connection) {
    const badge = $("#kc-runtime-state");
    const starting = connection.state === "starting";
    badge.textContent = connection.connected ? "接続済み" : starting ? "起動中" : "未接続";
    badge.className = `kc-badge ${connection.connected ? "success" : starting ? "cyan" : "warning"}`;
    $("#kc-runtime-gpu").textContent = connection.gpu || "A100";
    $("#kc-runtime-session").textContent = connection.session_id?.slice(0, 12) || "—";
    $("#kc-runtime-heartbeat").textContent = formatDate(connection.heartbeat_at || connection.checked_at);
  }

  function renderExperts(experts) {
    const body = $("#kc-expert-body");
    body.replaceChildren(...experts.map((expert) => {
      const row = document.createElement("tr");
      const values = [
        expert.name,
        `${expert.approved_claims} / 候補 ${expert.candidate_claims}`,
        `${expert.coverage}%`,
      ];
      values.forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      });
      const score = document.createElement("td");
      const scoreChip = document.createElement("span");
      scoreChip.className = "kc-score";
      scoreChip.textContent = String(expert.score);
      score.appendChild(scoreChip);
      row.appendChild(score);
      const inference = document.createElement("td");
      inference.appendChild(statusBadge(expert.latest_run_state));
      row.appendChild(inference);
      const count = document.createElement("td");
      count.textContent = `${expert.run_count}回`;
      row.appendChild(count);
      return row;
    }));
  }

  function renderTasks(tasks) {
    state.tasks = tasks;
    const list = $("#kc-task-list");
    $("#kc-task-empty").hidden = tasks.length > 0;
    list.replaceChildren(...tasks.map((task) => {
      const card = document.createElement("article");
      card.className = `kc-task ${task.status}`;
      card.dataset.taskId = task.task_id;
      const info = document.createElement("div");
      const title = document.createElement("h4");
      title.textContent = task.title;
      const meta = document.createElement("div");
      meta.className = "kc-task-meta";
      const expert = state.experts.find((item) => item.id === task.expert_id)?.name || task.expert_id;
      const model = state.models.find((item) => item.id === task.model_id)?.name || task.model_id;
      [`#${String(task.position).padStart(2, "0")}`, expert, task.actor.toUpperCase(), model, `${task.run_count}回`, `rev.${task.revision}`].forEach((value) => {
        const span = document.createElement("span");
        span.textContent = value;
        meta.appendChild(span);
      });
      const pill = scorePill(task);
      if (pill) meta.appendChild(pill);
      const progress = document.createElement("div");
      progress.className = "kc-task-progress";
      const phase = document.createElement("span");
      phase.className = "kc-task-progress-label";
      phase.textContent = task.phase || "未実行";
      const percent = document.createElement("span");
      percent.className = "kc-task-progress-value";
      percent.textContent = `${task.progress || 0}%`;
      const track = document.createElement("div");
      track.className = "kc-progress";
      track.setAttribute("role", "progressbar");
      track.setAttribute("aria-label", `${task.title}の進捗`);
      track.setAttribute("aria-valuemin", "0");
      track.setAttribute("aria-valuemax", "100");
      track.setAttribute("aria-valuenow", String(task.progress || 0));
      const fill = document.createElement("i");
      fill.style.width = `${task.progress || 0}%`;
      track.appendChild(fill);
      progress.append(phase, percent, track);
      info.append(title, meta, progress);
      const actions = document.createElement("div");
      actions.className = "kc-task-actions";
      actions.appendChild(statusBadge(task.status, task.simulation, task.quality_state));
      const run = document.createElement("button");
      run.className = "kc-button primary";
      run.type = "button";
      run.textContent = task.status === "succeeded" ? "再実行" : "実行";
      run.dataset.executeTask = task.task_id;
      run.disabled = task.status === "running" || state.batchRunning;
      actions.appendChild(run);
      card.append(info, actions);
      return card;
    }));
    const a100Count = tasks.filter((task) => task.actor === "a100").length;
    const pendingCount = pendingA100Tasks(tasks).length;
    [$("#kc-run-all"), $("#kc-run-a100-batch")].forEach((batchButton) => {
      batchButton.disabled = state.batchRunning || pendingCount === 0;
      if (!state.batchRunning) {
        batchButton.textContent = a100Count > 0 && pendingCount === 0 ? "A100は全件応答受信済み" : "A100を一括実行";
      }
      batchButton.title = a100Count > 0 && pendingCount === 0
        ? "A100タスクはすべて応答受信済みです。内容の品質は別途評価してください。"
        : "";
    });
    renderA100Tasks(tasks);
    renderA100Status();
  }

  function element(tag, className = "", text = null) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = String(text);
    return node;
  }

  // Current/best score of a repeating task and how it stands against the target.
  function scoreState(task) {
    if (task.target_score == null) return null;
    const history = (Array.isArray(task.score_history) ? task.score_history : [])
      .filter((attempt) => Number.isFinite(attempt.score));
    const attempts = history.length
      ? history
      : (Array.isArray(task.result?.attempts) ? task.result.attempts : []);
    const latest = attempts.length ? attempts[attempts.length - 1].score : task.score;
    const scores = attempts.map((attempt) => attempt.score).filter(Number.isFinite);
    const best = scores.length ? Math.max(...scores) : (Number.isFinite(task.result?.score) ? task.result.score : latest);
    const target = task.target_score;
    const finished = task.status !== "running";
    let tone = "pending";
    if (Number.isFinite(best) && best >= target) tone = "met";
    else if (finished && Number.isFinite(best)) tone = "missed";
    else if (Number.isFinite(latest)) tone = "below";
    return {
      target,
      latest: Number.isFinite(latest) ? latest : null,
      best: Number.isFinite(best) ? best : null,
      attempts,
      iteration: attempts.length || task.iteration || 0,
      maxIterations: task.max_iterations,
      interrupted: task.result?.interrupted === true,
      tone,
    };
  }

  function scoreStatusText(score, running) {
    if (score.interrupted) return score.best == null ? "処理停止・採点結果なし" : `処理停止・採点済みの最高${score.best}点（停止した試行は未採点）`;
    if (score.tone === "met") return `✓ 目標達成(${score.best}点 ≥ 目標${score.target}点)`;
    if (score.tone === "missed") return `✕ 目標未達・最高${score.best}点(あと${score.target - score.best}点)`;
    if (score.tone === "below") return `▲ 目標まであと${score.target - score.latest}点${running ? "・改善して再実行" : ""}`;
    return running ? "… 1回目の採点待ち" : "未実行";
  }

  // Compact "72 / 80点" chip for task lists.
  function scorePill(task) {
    const score = scoreState(task);
    if (!score) return null;
    const pill = element("span", `kc-score-pill ${score.tone}`);
    pill.append(
      element("b", "", score.latest == null ? "—" : score.latest),
      element("span", "", ` / ${score.target}点`),
      element("small", "", ` ${score.iteration}/${score.maxIterations}回`),
    );
    pill.title = scoreStatusText(score, task.status === "running");
    return pill;
  }

  function buildScorePanel(task) {
    const score = scoreState(task);
    const running = task.status === "running";
    const panel = element("section", `kc-score-panel ${score.tone}`);
    panel.setAttribute("aria-label", `${task.title}のスコア`);

    const figures = element("div", "kc-score-figures");
    const figure = (label, value, unit, className = "") => {
      const box = element("div", className);
      const strong = element("strong", "", value);
      strong.appendChild(element("span", "", unit));
      box.append(element("small", "", label), strong);
      return box;
    };
    figures.append(
      figure(score.interrupted ? "直近の採点結果" : "現在のスコア", score.latest == null ? "—" : score.latest, "点", "current"),
      figure("目標", score.target, "点", "target"),
      figure("反復", score.iteration, ` / ${score.maxIterations}回`),
    );

    // Gauge: 0–100 with the latest score as fill, the best as a tick, the target as a line.
    const gauge = element("div", "kc-score-gauge");
    gauge.setAttribute("role", "meter");
    gauge.setAttribute("aria-valuemin", "0");
    gauge.setAttribute("aria-valuemax", "100");
    gauge.setAttribute("aria-valuenow", String(score.latest ?? 0));
    gauge.setAttribute("aria-valuetext", scoreStatusText(score, running));
    const fill = element("i", "kc-score-fill");
    fill.style.width = `${score.latest ?? 0}%`;
    gauge.appendChild(fill);
    if (score.best != null && score.best !== score.latest) {
      const best = element("u", "kc-score-best");
      best.style.left = `${score.best}%`;
      best.title = `最高 ${score.best}点`;
      gauge.appendChild(best);
    }
    const targetLine = element("b", "kc-score-target-line");
    targetLine.style.left = `${score.target}%`;
    targetLine.appendChild(element("span", "", `目標 ${score.target}`));
    gauge.appendChild(targetLine);
    const scale = element("div", "kc-score-scale");
    ["0", "50", "100"].forEach((value) => scale.appendChild(element("span", "", value)));

    const status = element("p", "kc-score-status", scoreStatusText(score, running));

    // One column per allowed attempt: filled with its score, empty while not yet run.
    const attempts = element("ol", "kc-score-attempts");
    attempts.style.setProperty("--kc-target", `${score.target}%`);
    for (let index = 0; index < score.maxIterations; index += 1) {
      const attempt = score.attempts[index];
      const item = element("li", attempt ? (attempt.score >= score.target ? "met" : "below") : "empty");
      const column = element("div", "kc-score-column");
      const bar = element("i");
      bar.style.height = attempt ? `${Math.max(attempt.score, 2)}%` : "0";
      column.appendChild(bar);
      item.append(
        element("b", "", attempt ? attempt.score : running && index === score.attempts.length ? "…" : "—"),
        column,
        element("small", "", `${index + 1}回目`),
      );
      item.title = attempt
        ? `${index + 1}回目: ${attempt.score}点(${attempt.scorer === "local_llm" ? "Local LLM" : "A100"}採点)${attempt.feedback ? `\n改善点: ${attempt.feedback}` : ""}`
        : `${index + 1}回目: 未実行`;
      attempts.appendChild(item);
    }

    panel.append(figures, gauge, scale, status, attempts);
    const lastFeedback = score.attempts.length ? score.attempts[score.attempts.length - 1].feedback : "";
    if (lastFeedback && score.tone !== "met") {
      const feedback = element("p", "kc-score-feedback");
      feedback.append(element("b", "", "次の改善点 "), document.createTextNode(lastFeedback));
      panel.appendChild(feedback);
    }
    return panel;
  }

  // Mirrors the server plan: a real A100 success is done; simulated playback is not.
  function pendingA100Tasks(tasks) {
    return tasks.filter((task) => task.actor === "a100" && !(task.status === "succeeded" && !task.simulation));
  }

  function renderA100Tasks(tasks) {
    const a100Tasks = tasks.filter((task) => task.actor === "a100");
    $("#kc-a100-count").textContent = String(a100Tasks.length);
    $("#kc-a100-running").textContent = String(a100Tasks.filter((task) => task.status === "running").length);
    $("#kc-a100-completed").textContent = String(a100Tasks.filter((task) => task.status === "succeeded" && !task.simulation).length);
    // Finished tasks move to a collapsed section so the board lists only remaining work.
    const pending = pendingA100Tasks(a100Tasks);
    const done = a100Tasks.filter((task) => !pending.includes(task));
    const empty = $("#kc-a100-empty");
    empty.hidden = pending.length > 0;
    empty.textContent = a100Tasks.length > 0
      ? "未受信のA100タスクはありません。「応答受信済み」から結果と評価状態を確認できます。"
      : "A100担当のタスクはありません。";
    $("#kc-a100-done").hidden = done.length === 0;
    $("#kc-a100-done-count").textContent = String(done.length);
    $("#kc-a100-pending-count").textContent = `${pending.length}件`;
    // Running work first, then the saved order.
    const ordered = [...pending].sort((a, b) => (b.status === "running") - (a.status === "running") || a.position - b.position);
    $("#kc-a100-task-board").replaceChildren(...ordered.map(buildA100Card));
    $("#kc-a100-done-board").replaceChildren(...done.map(buildA100Card));
  }

  function buildA100Card(task) {
    const running = task.status === "running";
    const progressValue = task.progress || 0;
    const card = element("article", `kc-card kc-a100-task ${task.status}`);
    card.dataset.taskId = task.task_id;

    const header = element("header", "kc-a100-task-head");
    const heading = element("div", "kc-a100-task-title");
    const expert = state.experts.find((item) => item.id === task.expert_id)?.name || task.expert_id;
    const model = state.models.find((item) => item.id === task.model_id)?.name || task.model_id;
    heading.append(
      element("small", "", `#${String(task.position).padStart(2, "0")} · ${expert} · ${model}`),
      element("h3", "", task.title),
    );
    const actions = element("div", "kc-a100-task-actions");
    const run = element("button", `kc-button ${running ? "ghost" : "primary"}`, task.status === "succeeded" ? "再実行" : running ? "実行中…" : "実行");
    run.type = "button";
    run.dataset.executeTask = task.task_id;
    run.disabled = running || state.batchRunning;
    actions.append(statusBadge(task.status, task.simulation, task.quality_state), run);
    header.append(heading, actions);

    // Progress: the current phase in words, the percentage, and one thick bar.
    const progress = element("section", "kc-a100-progress");
    const progressHead = element("div", "kc-a100-progress-head");
    progressHead.append(
      element("b", "", (task.quality_state === "evidence_checked" && task.status === "succeeded" ? "応答受信・引用照合済み" : task.phase) || "未実行"),
      element("strong", "", `${progressValue}%`),
    );
    const track = element("div", "kc-progress");
    track.setAttribute("role", "progressbar");
    track.setAttribute("aria-label", `${task.title}の進捗`);
    track.setAttribute("aria-valuenow", String(progressValue));
    track.setAttribute("aria-valuemin", "0");
    track.setAttribute("aria-valuemax", "100");
    const fill = element("i");
    fill.style.width = `${progressValue}%`;
    track.appendChild(fill);
    progress.append(progressHead, track);

    const planItem = state.a100Plan.get(task.task_id);
    const decision = element("div", "kc-a100-decision");
    const decisionBadge = element("span", `kc-badge ${task.decision_mode === "local_llm" ? "violet" : "cyan"}`,
      task.decision_mode === "local_llm" ? "LOCAL LLM" : "PROGRAM");
    const advice = element("div");
    advice.append(
      element("b", "", planItem?.focus || (task.decision_mode === "local_llm" ? "意味判断を実行前に取得" : "固定ルールで処理")),
      element("small", "", planItem?.reason || (task.decision_mode === "local_llm" ? "順番と安全判定には関与しません" : "再現可能な判定を使用します")),
    );
    decision.append(decisionBadge, advice);

    const body = element("div", "kc-a100-task-body");
    const left = element("div", "kc-a100-task-main");
    // Not-yet-run tasks stay compact: an empty 0% bar carries no information.
    const idle = !running && progressValue === 0 && task.target_score == null;
    if (idle) card.classList.add("idle"); else left.appendChild(progress);
    left.appendChild(decision);
    body.appendChild(left);
    if (task.target_score != null) {
      card.classList.add("has-score");
      body.appendChild(buildScorePanel(task));
    }
    card.append(header, body);

    if (task.error_message) {
      card.appendChild(element("div", "kc-a100-result kc-a100-error", task.error_message));
    }
    if (task.result?.quality) {
      const quality = task.result.quality;
      card.appendChild(element("div", "kc-a100-result", [quality.reason, ...(quality.missing_inputs || [])].join("\n")));
    }
    if (task.result?.content) {
      const result = element("details", "kc-a100-result-details");
      result.open = state.openResults.has(task.task_id);
      result.addEventListener("toggle", () => {
        if (result.open) state.openResults.add(task.task_id); else state.openResults.delete(task.task_id);
      });
      result.appendChild(element("summary", "", task.result.interrupted ? "停止した試行の出力を表示（未採点）" : "A100の出力を表示"));
      result.appendChild(element("div", "kc-a100-result", task.result.content));
      card.appendChild(result);
    }
    if (task.result?.best_attempt?.content) {
      const best = task.result.best_attempt;
      const details = element("details", "kc-a100-result-details");
      details.appendChild(element("summary", "", `保存した最良成果物（${best.iteration}回目・${best.score}点）`));
      details.appendChild(element("div", "kc-a100-result", best.content));
      card.appendChild(details);
    }
    return card;
  }

  function renderActivity(connection) {
    const jobs = Array.isArray(connection.jobs) ? connection.jobs : [];
    const badge = $("#kc-activity-state");
    const [label, tone] = connection.connected
      ? (jobs.length ? [`処理中 ${jobs.length}件`, "cyan"] : ["待機中", "success"])
      : ({
        starting: ["起動中", "cyan"],
        worker_failed: ["停止(エラー)", "warning"],
        stale: ["停止", "warning"],
      }[connection.state] || ["未接続", "muted"]);
    badge.textContent = label;
    badge.className = `kc-badge ${tone}`;
    $("#kc-activity-summary").textContent = connection.connected
      ? (jobs.length ? `${jobs.length}件のタスクを推論しています。` : "タスクを待っています。")
      : connection.message;
    const titleOf = (job) => job.title
      || state.tasks.find((task) => task.task_id === job.task_id)?.title
      || job.job_id;
    $("#kc-activity-jobs").replaceChildren(...jobs.map((job) => {
      const item = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = titleOf(job);
      const elapsed = document.createElement("span");
      elapsed.dataset.runningSeconds = String(job.running_seconds || 0);
      item.append(name, elapsed);
      return item;
    }));
    const count = (value) => (Number.isInteger(value) ? `${value}件` : "—");
    $("#kc-activity-pending").textContent = count(connection.pending_count);
    $("#kc-activity-completed").textContent = count(connection.completed_count);
    $("#kc-activity-failed").textContent = count(connection.failed_count);
    const gpu = connection.gpu_memory;
    $("#kc-activity-gpu").textContent = gpu
      ? `${gpu.used_mib.toLocaleString()} / ${gpu.total_mib.toLocaleString()} MiB` : "—";
    const gpuPercent = gpu && gpu.total_mib ? Math.round(gpu.used_mib / gpu.total_mib * 100) : 0;
    $("#kc-activity-gpu-bar").style.width = `${gpuPercent}%`;
    $("#kc-activity-gpu-bar").parentElement.setAttribute("aria-valuenow", String(gpuPercent));
    const last = connection.last_completed;
    $("#kc-activity-last").textContent = last
      ? `直近: ${titleOf(last)} ${last.ok ? "完了" : "失敗"} · ${last.seconds}秒`
        + (last.tokens_per_second ? ` · ${last.tokens_per_second} tok/s` : "")
        + (last.ok ? "" : ` · ${last.error}`)
      : "";
    state.activityHeartbeatAt = connection.heartbeat_at ? Date.parse(connection.heartbeat_at) : null;
    tickActivity();
  }

  // Counts elapsed time up locally between checks; no extra requests are made.
  function tickActivity() {
    const heartbeatAt = state.activityHeartbeatAt;
    const sinceHeartbeat = heartbeatAt ? Math.max(0, (Date.now() - heartbeatAt) / 1000) : 0;
    const format = (seconds) => {
      const total = Math.floor(seconds);
      return total >= 60 ? `${Math.floor(total / 60)}分${String(total % 60).padStart(2, "0")}秒` : `${total}秒`;
    };
    $$("#kc-activity-jobs [data-running-seconds]").forEach((element) => {
      element.textContent = `${format(Number(element.dataset.runningSeconds) + sinceHeartbeat)} 経過`;
    });
    renderA100Status();
    const busy = activeA100Run();
    $("#kc-activity-updated").textContent = heartbeatAt
      ? `A100からの最終更新: ${format(sinceHeartbeat)}前(A100は30秒ごとに送信 · この画面は${busy ? "30秒" : "5分"}ごとに確認)`
      : "";
  }

  // One summary of the A100 worker, shown on every view (top bar and sidebar).
  function a100Status() {
    const connection = state.connection;
    const submitted = state.tasks.filter((task) => task.actor === "a100" && task.status === "running" && !task.simulation).length;
    if (!connection) return {tone: "muted", label: "A100 接続を確認中", short: "確認中"};
    if (!connection.connected) {
      const [tone, label] = {
        starting: ["cyan", "A100 起動中"],
        worker_failed: ["danger", "A100 停止(エラー)"],
        stale: ["warning", "A100 応答なし"],
      }[connection.state] || ["warning", "A100 未接続"];
      return {tone, label, short: label.replace("A100 ", ""), submitted};
    }
    const running = Array.isArray(connection.jobs) ? connection.jobs.length : 0;
    const slots = Number.isInteger(connection.parallel_slots) ? connection.parallel_slots : null;
    const slotText = slots ? ` ${running}/${slots}枠` : ` ${running}件`;
    if (running >= 2) return {tone: "active", label: `A100 並列実行中${slotText}`, short: `並列実行中 ${running}件`, submitted};
    if (running === 1) return {tone: "active", label: `A100 実行中${slotText}`, short: "実行中 1件", submitted};
    if (submitted > 0 || connection.pending_count > 0) {
      return {tone: "cyan", label: "A100 受付待ち", short: "受付待ち", submitted};
    }
    return {tone: "success", label: "A100 待機中", short: "接続済み・待機中", submitted};
  }

  function renderA100Status() {
    const status = a100Status();
    const connection = state.connection;
    const pill = $("#kc-a100-status");
    pill.className = `kc-a100-status ${status.tone}`;
    $("#kc-a100-status-label").textContent = status.label;
    const format = (seconds) => (seconds >= 60 ? `${Math.floor(seconds / 60)}分前` : `${Math.floor(seconds)}秒前`);
    const parts = [];
    if (connection?.connected) parts.push("接続済み");
    if (status.submitted) parts.push(`送信中タスク ${status.submitted}件`);
    if (Number.isInteger(connection?.pending_count) && connection.pending_count > 0) parts.push(`Worker待ち ${connection.pending_count}件`);
    const seenAt = state.activityHeartbeatAt || (connection?.checked_at ? Date.parse(connection.checked_at) : null);
    if (seenAt) parts.push(`${connection?.connected ? "最終応答" : "確認"} ${format(Math.max(0, (Date.now() - seenAt) / 1000))}`);
    $("#kc-a100-status-detail").textContent = parts.join(" · ") || "—";
    pill.title = `${status.label}${connection?.message ? `\n${connection.message}` : ""}\nクリックでA100タスク画面へ`;
    $("#kc-a100-foot-dot").className = `kc-dot ${status.tone}`;
    $("#kc-a100-foot-label").textContent = status.short;
  }

  function activeA100Run() {
    return state.tasks.some((task) => task.actor === "a100" && task.status === "running" && !task.simulation);
  }

  function renderConnectionResult(connection) {
    state.connection = connection;
    renderRuntimeConnection(connection);
    renderActivity(connection);
    if (state.setup) renderSetup(state.setup);
    const target = connection.target ? ` · ${connection.target}` : "";
    $$(".kc-connection-result").forEach((panel) => {
      const badge = $("[data-connection-badge]", panel);
      panel.hidden = false;
      panel.className = `kc-connection-result ${connection.connected ? "success" : "warning"}`;
      badge.className = `kc-badge ${connection.connected ? "success" : "warning"}`;
      badge.textContent = connection.connected ? "CONNECTED" : "NOT CONNECTED";
      $("[data-connection-title]", panel).textContent = connection.message;
      $("[data-connection-detail]", panel).textContent = `${formatDate(connection.checked_at)}${target} · 接続状態: ${connection.state}`;
    });
  }

  const eventLabels = {
    "task.created": "タスクを作成",
    "task.seeded": "初期タスクを作成",
    "task.queued": "実行キューへ追加",
    "task.running": "タスク実行開始",
    "task.progressed": "タスク進捗を更新",
    "knowledge.accessed": "知識ブロックへアクセス",
    "task.succeeded": "タスク実行完了",
    "task.failed": "タスク実行失敗",
    "runtime.failed": "A100接続エラー",
    "api.failed": "操作エラー",
    "knowledge.block_accessed": "知識ブロックを参照",
  };

  function renderEvents(events) {
    const list = $("#kc-event-list");
    const latest = events.slice(-20).reverse();
    list.replaceChildren(...latest.map((event) => {
      const item = document.createElement("li");
      const title = document.createElement("b");
      title.textContent = eventLabels[event.event_type] || event.event_type;
      const detail = document.createElement("span");
      detail.textContent = `${formatDate(event.occurred_at)} · ${event.entity_id.slice(0, 8)}`;
      item.append(title, detail);
      return item;
    }));
  }

  async function loadErrorHistory(older = false) {
    if (state.errorLoading || (older && state.errorCursor == null)) return;
    state.errorLoading = true;
    $("#kc-error-refresh").disabled = true;
    $("#kc-error-older").disabled = true;
    try {
      const cursor = older ? `&before=${state.errorCursor}` : "";
      const payload = await requestJson(`/api/knowledge-console/events?errors_only=1&limit=50${cursor}`);
      const list = $("#kc-error-history");
      if (!older) list.replaceChildren();
      for (const event of [...payload.events].reverse()) {
        const detail = event.payload || {};
        const item = element("li");
        const log = element("details");
        const context = detail.title || event.entity_id;
        log.appendChild(element("summary", "", `${formatDate(event.occurred_at)} · ${eventLabels[event.event_type] || event.event_type} · ${context}`));
        const run = detail.run_count != null ? `実行 ${detail.run_count}回目 · 反復 ${detail.iteration ?? 0}回目` : "";
        const phase = detail.phase || detail.state || [detail.method, detail.status].filter(Boolean).join(" ");
        log.appendChild(element("p", "kc-muted", [run, phase].filter(Boolean).join(" · ")));
        log.appendChild(element("div", "kc-a100-result", detail.message || "詳細なし"));
        item.appendChild(log);
        list.appendChild(item);
      }
      state.errorCursor = payload.next_before;
      $("#kc-error-history-status").textContent = list.children.length
        ? `${list.children.length}件を表示（記録は自動削除しません）` : "記録されたエラーはありません。";
    } catch (error) {
      $("#kc-error-history-status").textContent = `履歴を読み込めませんでした: ${error.message}`;
    } finally {
      state.errorLoading = false;
      $("#kc-error-refresh").disabled = false;
      $("#kc-error-older").disabled = state.errorCursor == null;
    }
  }

  async function refresh() {
    $("#kc-refresh").disabled = true;
    try {
      const [summary, experts, tasks, events] = await Promise.all([
        requestJson("/api/knowledge-console/summary"),
        requestJson("/api/knowledge-console/experts"),
        requestJson("/api/knowledge-console/tasks"),
        requestJson("/api/knowledge-console/events?limit=100"),
      ]);
      state.experts = experts.experts;
      state.models = experts.models;
      renderSummary(summary);
      renderExperts(experts.experts);
      renderTasks(tasks.tasks);
      renderEvents(events.events);
      await loadErrorHistory();
      ["#kc-task-expert", "#kc-trace-expert"].forEach((id) => fillSelect($(id), state.experts));
      ["#kc-task-model", "#kc-trace-model"].forEach((id) => fillSelect($(id), state.models));
      tasks.tasks.filter((task) => task.status === "running").forEach((task) => {
        void startTaskProgress(task).catch(() => {});
      });
    } catch (error) {
      showAlert(error.message, "error");
    } finally {
      $("#kc-refresh").disabled = false;
    }
  }

  function switchView(name) {
    $$(".kc-nav-item").forEach((button) => {
      const selected = button.dataset.view === name;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-selected", String(selected));
    });
    $$(".kc-view").forEach((view) => {
      const selected = view.id === `kc-${name}`;
      view.classList.toggle("active", selected);
      view.hidden = !selected;
    });
    history.replaceState(null, "", `#${name}`);
  }

  async function createTask(event) {
    event.preventDefault();
    try {
      await requestJson("/api/knowledge-console/tasks", {
        method: "POST",
        body: JSON.stringify({
          title: $("#kc-task-title").value,
          expert_id: $("#kc-task-expert").value,
          actor: $("#kc-task-actor").value,
          model_id: $("#kc-task-model").value,
          decision_mode: $("#kc-task-decision").value,
          target_score: $("#kc-task-target").value || null,
          max_iterations: $("#kc-task-max-iterations").value || null,
        }),
      });
      $("#kc-task-dialog").close();
      showAlert("タスクを保存しました。実行前の下書きです。");
      await refresh();
    } catch (error) {
      showAlert(error.message, "error");
    }
  }

  async function executeTask(button) {
    const task = state.tasks.find((item) => item.task_id === button.dataset.executeTask);
    if (!task) return;
    button.disabled = true;
    button.textContent = "接続確認中…";
    try {
      const connection = await checkRuntimeConnection();
      if (!connection.connected) {
        openSetupDialog();
        throw new Error(`${connection.message} 「接続設定」の手順を確認してください。`);
      }
      showAlert("Colab A100実モデルへの接続を確認しました。タスクを送信します。", "success");
      button.textContent = "A100へ送信中…";
      const planItem = state.a100Plan.get(task.task_id);
      const payload = await requestJson(`/api/knowledge-console/tasks/${encodeURIComponent(task.task_id)}/execute`, {
        method: "POST",
        body: JSON.stringify({revision: task.revision, simulation: false, focus: planItem?.focus || ""}),
      });
      state.tasks = state.tasks.map((item) => item.task_id === task.task_id ? payload.task : item);
      renderTasks(state.tasks);
      showAlert("A100実モデルへ送信しました。応答待ちです。", "success");
      void startTaskProgress(payload.task).catch(() => {});
      void autoCheckConnection();
    } catch (error) {
      showAlert(error.message, "error");
      button.disabled = false;
      button.textContent = "実行";
    }
  }

  function wait(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  function startTaskProgress(initialTask) {
    const taskId = initialTask.task_id;
    if (state.advancingTasks.has(taskId)) return state.advancingTasks.get(taskId);
    const progressPromise = advanceTaskUntilComplete(taskId).finally(() => {
      state.advancingTasks.delete(taskId);
    });
    state.advancingTasks.set(taskId, progressPromise);
    return progressPromise;
  }

  async function advanceTaskUntilComplete(taskId) {
    let completed = false;
    try {
      while (true) {
        const current = state.tasks.find((item) => item.task_id === taskId);
        if (!current || current.status !== "running") break;
        await wait(reducedMotion ? 120 : 760);
        const latest = state.tasks.find((item) => item.task_id === taskId);
        if (!latest || latest.status !== "running") break;
        const payload = await requestJson(`/api/knowledge-console/tasks/${encodeURIComponent(taskId)}/advance`, {
          method: "POST",
          body: JSON.stringify({revision: latest.revision}),
        });
        state.tasks = state.tasks.map((item) => item.task_id === taskId ? payload.task : item);
        renderTasks(state.tasks);
        if (payload.task.status === "succeeded") {
          completed = true;
          break;
        }
        if (payload.task.status === "failed") {
          throw new Error(payload.task.error_message || "A100実推論に失敗しました。");
        }
      }
    } catch (error) {
      showAlert(`進捗更新に失敗しました: ${error.message}`, "error");
      await refresh();
      throw error;
    }
    if (completed) {
      showAlert("Colab A100実モデルの推論が完了し、応答を保存しました。", "success");
    }
    await refresh();
  }

  async function checkRuntimeConnection() {
    const payload = await requestJson("/api/knowledge-console/runtime/check", {
      method: "POST",
      body: JSON.stringify({purpose: "ordered_batch", simulation: false}),
    });
    renderConnectionResult(payload.connection);
    await loadErrorHistory();
    return payload.connection;
  }

  async function checkConnectionFromButton() {
    const buttons = $$(".kc-check-connection");
    buttons.forEach((button) => {
      button.disabled = true;
      button.textContent = "確認中…";
    });
    try {
      const connection = await checkRuntimeConnection();
      showAlert(connection.message, connection.connected ? "success" : "warning");
    } catch (error) {
      showAlert(`接続確認に失敗しました: ${error.message}`, "error");
    } finally {
      buttons.forEach((button) => {
        button.disabled = false;
        button.textContent = "接続確認";
      });
    }
  }

  function renderSetup(setup) {
    state.setup = setup;
    const connected = Boolean(state.connection?.connected);
    const done = {
      client: setup.oauth_client,
      auth: setup.drive_authorized,
      notebook: Boolean(state.notebookPublished),
      worker: connected,
    };
    const order = ["client", "auth", "notebook", "worker"];
    const current = order.find((step) => !done[step] && (step !== "notebook" || !setup.drive_authorized));
    order.forEach((step) => {
      const item = $(`[data-setup-step="${step}"]`);
      if (!item) return;
      item.classList.toggle("done", done[step]);
      item.classList.toggle("current", step === current || (step === "worker" && setup.drive_authorized && !connected));
    });
    $("#kc-setup-authorize").disabled = !setup.oauth_client;
    $("#kc-setup-notebook").disabled = !setup.drive_authorized;
    $("#kc-setup-open-colab").href = setup.notebook_url;
    $("#kc-setup-colab-link").href = setup.notebook_url;
    const incomplete = !setup.oauth_client || (!setup.drive_authorized && setup.queue_mode !== "manual");
    $$(".kc-open-setup").forEach((button) => {
      button.classList.toggle("needs-setup", incomplete);
      button.title = incomplete ? "未完了の接続設定があります" : "";
    });
    const detail = $("#kc-setup-worker-detail");
    if (connected) {
      detail.textContent = `接続済み: ${state.connection.gpu || "A100"} · session ${state.connection.session_id?.slice(0, 12) || "—"}`;
    } else if (setup.queue_mode === "manual") {
      detail.textContent = "手動設定を使用中です。";
    } else if (state.connection?.message && setup.drive_authorized) {
      detail.textContent = state.connection.state === "worker_failed"
        ? state.connection.message
        : `${state.connection.message}(5分ごとに自動確認・「接続確認」ですぐ確認)`;
    }
  }

  function openSetupDialog() {
    const dialog = $("#kc-setup-dialog");
    if (!dialog.open) dialog.showModal();
    void loadSetup().catch(() => {});
  }

  async function loadSetup() {
    const payload = await requestJson("/api/knowledge-console/setup/status");
    renderSetup(payload.setup);
    return payload.setup;
  }

  async function runSetupAction(button, busyLabel, action) {
    const label = button.textContent;
    button.disabled = true;
    button.textContent = busyLabel;
    try {
      await action();
    } catch (error) {
      showAlert(error.message, "error");
    } finally {
      button.textContent = label;
      if (state.setup) renderSetup(state.setup); else button.disabled = false;
    }
  }

  async function uploadOAuthClient(event) {
    const input = event.target;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    const button = $('label[for="kc-oauth-file"]');
    button.textContent = "保存中…";
    try {
      let clientJson;
      try {
        clientJson = JSON.parse(await file.text());
      } catch (_error) {
        throw new Error("選択したファイルはJSONではありません。");
      }
      const payload = await requestJson("/api/knowledge-console/setup/oauth-client", {
        method: "POST",
        body: JSON.stringify({client_json: clientJson}),
      });
      renderSetup(payload.setup);
      showAlert("OAuthクライアントを保存しました。次に「認可する」を押してください。", "success");
    } catch (error) {
      showAlert(error.message, "error");
    } finally {
      button.textContent = "JSONを選択";
    }
  }

  function authorizeDrive(event) {
    return runSetupAction(event.currentTarget, "ブラウザで許可してください…", async () => {
      const payload = await requestJson("/api/knowledge-console/setup/authorize", {method: "POST", body: "{}"});
      renderSetup(payload.setup);
      showAlert("Google Driveを認可しました。", "success");
      await autoCheckConnection();
    });
  }

  function publishNotebook(event) {
    return runSetupAction(event.currentTarget, "反映中…", async () => {
      const payload = await requestJson("/api/knowledge-console/setup/notebook", {method: "POST", body: "{}"});
      state.notebookPublished = true;
      renderSetup(payload.setup);
      showAlert(payload.created
        ? "Driveに自分用のWorkerノートブックを作成しました。「Colabで開く」から実行してください。"
        : "DriveのWorkerノートブックを最新版に更新しました。", "success");
    });
  }

  // While the page is open, notice a newly started Colab worker without a click.
  const AUTO_CHECK_INTERVAL_MS = 5 * 60 * 1000;
  const ACTIVE_CHECK_INTERVAL_MS = 30 * 1000;
  window.setInterval(tickActivity, 1000);
  async function autoCheckConnection() {
    window.clearTimeout(state.autoCheckTimer);
    try {
      const setup = state.setup || await loadSetup();
      if (setup.drive_authorized || setup.queue_mode === "manual") {
        const wasConnected = Boolean(state.connection?.connected);
        if (!document.hidden) {
          const connection = await checkRuntimeConnection();
          if (connection.connected && !wasConnected) {
            showAlert("Colab A100 Workerを検出し、接続しました。", "success");
          }
        }
      }
    } catch (_error) {
      // A failed background check is shown on the next manual check.
    } finally {
      if (state.setup) renderSetup(state.setup);
      // While real A100 tasks run, follow the worker's 30-second status updates.
      const delay = activeA100Run() ? ACTIVE_CHECK_INTERVAL_MS : AUTO_CHECK_INTERVAL_MS;
      state.autoCheckTimer = window.setTimeout(autoCheckConnection, delay);
    }
  }

  async function applyBridgeConfiguration() {
    const button = $("#kc-apply-bridge");
    const label = button.textContent;
    button.disabled = true;
    button.textContent = "Google認可・接続確認中…";
    try {
      let configuration;
      try {
        configuration = JSON.parse($("#kc-bridge-json").value.trim());
      } catch (_error) {
        throw new Error("Colabに表示されたDrive Queue設定JSONを貼り付けてください。");
      }
      const payload = await requestJson("/api/knowledge-console/runtime/configure", {
        method: "POST",
        body: JSON.stringify(configuration),
      });
      renderConnectionResult(payload.connection);
      if (!payload.connection.connected) throw new Error(payload.connection.message);
      $("#kc-bridge-json").value = "";
      await loadSetup();
      showAlert("Drive Queue経由でColab A100 Workerへ接続しました。実モデル送信を開始できます。", "success");
    } catch (error) {
      showAlert(`Drive Queue設定に失敗しました: ${error.message}`, "error");
    } finally {
      button.disabled = false;
      button.textContent = label;
    }
  }

  async function runA100TasksInOrder(requestedTaskIds = null) {
    if (state.batchRunning) return;
    const requested = Array.isArray(requestedTaskIds) ? new Set(requestedTaskIds) : null;
    const pending = pendingA100Tasks(state.tasks).filter((task) => !requested || requested.has(task.task_id));
    if (pending.length === 0) {
      showAlert("未完了のA100タスクはありません。完了済みタスクは個別の「再実行」で実行できます。", "success");
      return requested ? {ok: false, message: "生成した目標タスクを読み込めませんでした。再読込してください。"} : {ok: true, executed: 0};
    }
    let outcome = {ok: false, message: "自動実行を完了できませんでした。"};
    state.batchRunning = true;
    renderTasks(state.tasks);
    const batchButtons = [$("#kc-run-all"), $("#kc-run-a100-batch")];
    batchButtons.forEach((button) => { button.textContent = "Colab接続を確認中…"; });
    try {
      const connection = await checkRuntimeConnection();
      if (!connection.connected) {
        openSetupDialog();
        throw new Error(`${connection.message} 「接続設定」の手順を確認してください。`);
      }
      showAlert("Colab A100実モデルへの接続を確認しました。実行計画を作成します。", "success");
      batchButtons.forEach((button) => { button.textContent = "Local LLMで実行計画を作成中…"; });

      const planPayload = await requestJson("/api/knowledge-console/a100/plan", {
        method: "POST",
        body: JSON.stringify({simulation: false}),
      });
      state.localLlmState = planPayload.local_llm.state;
      state.a100Plan = new Map(planPayload.plan.map((item) => [item.task_id, item]));
      renderTasks(state.tasks);
      const scopedPlan = planPayload.plan.filter((item) => !requested || requested.has(item.task_id));
      const executable = scopedPlan.filter((item) => item.program_gate.approved && item.action === "execute");
      const heldCount = scopedPlan.length - executable.length;
      if (executable.length === 0) {
        const reasons = [...new Set(planPayload.plan.map((item) => item.reason))];
        throw new Error(`実行可能なA100タスクがありません（${reasons.join(" / ") || "A100タスクなし"}）。`);
      }
      const llmLabel = state.localLlmState === "connected" ? "Local LLM判断を反映" : "Local LLM未接続・既定方針";
      showAlert(`${llmLabel}。${executable.length}件を保存順に投入します${heldCount ? `（${heldCount}件保留）` : ""}。`, state.localLlmState === "connected" ? "success" : "warning");

      // Submit every task in saved order first; the Colab worker runs several at once.
      const progress = [];
      let finished = 0;
      const showFinished = () => {
        batchButtons.forEach((button) => { button.textContent = `A100処理中 ${finished} / ${executable.length}`; });
      };
      for (let index = 0; index < executable.length; index += 1) {
        const taskId = executable[index].task_id;
        batchButtons.forEach((button) => { button.textContent = `A100へ投入 ${index + 1} / ${executable.length}`; });
        let task = state.tasks.find((item) => item.task_id === taskId);
        if (!task) continue;
        if (task.status !== "running") {
          const payload = await requestJson(`/api/knowledge-console/tasks/${encodeURIComponent(taskId)}/execute`, {
            method: "POST",
            body: JSON.stringify({
              revision: task.revision,
              simulation: false,
              focus: executable[index].focus || "",
            }),
          });
          task = payload.task;
          state.tasks = state.tasks.map((item) => item.task_id === taskId ? task : item);
          renderTasks(state.tasks);
        }
        progress.push(startTaskProgress(task).finally(() => {
          finished += 1;
          showFinished();
        }));
      }
      showFinished();
      void autoCheckConnection();
      const outcomes = await Promise.allSettled(progress);
      const failed = outcomes.filter((outcome) => outcome.status === "rejected").length;
      if (failed) throw new Error(`${failed}件のA100タスクが失敗しました。`);
      showAlert(`A100実モデルで${executable.length}件の実行が完了しました。`, "success");
      outcome = {ok: true, executed: executable.length};
    } catch (error) {
      showAlert(`一括実行を停止しました: ${error.message}`, "error");
      outcome = {ok: false, message: error.message};
    } finally {
      state.batchRunning = false;
      await refresh();
      renderTasks(state.tasks);
    }
    return outcome;
  }

  function clearTrace() {
    window.clearTimeout(state.playbackTimer);
    state.playbackIndex = 0;
    $$(".kc-pipeline-stage, .kc-pipeline-link").forEach((element) => {
      element.classList.remove("active", "visited");
    });
    $("#kc-trace-events").replaceChildren();
    $("#kc-trace-progress").style.width = "0%";
    $("#kc-trace-step").textContent = "0 / 0";
    $("#kc-trace-result").hidden = true;
  }

  function appendTraceEvent(event) {
    const list = $("#kc-trace-events");
    const item = document.createElement("li");
    const title = document.createElement("b");
    const block = $(`[data-block-id="${CSS.escape(event.payload.block_id)}"]`);
    const blockName = block?.querySelector("b")?.textContent || event.payload.block_id;
    title.textContent = `${event.payload.step}. ${blockName}`;
    const detail = document.createElement("span");
    detail.textContent = "knowledge.block_accessed";
    item.append(title, detail);
    list.appendChild(item);
  }

  function finishTrace() {
    const result = state.trace.result;
    const panel = $("#kc-trace-result");
    $("p", panel).textContent = result.summary;
    const contribution = $("#kc-contribution");
    contribution.replaceChildren(...result.contribution.map((entry) => {
      const row = document.createElement("div");
      row.className = "kc-contribution-row";
      const label = document.createElement("span");
      label.textContent = entry.label;
      const bar = document.createElement("i");
      bar.style.width = `${entry.value}%`;
      const value = document.createElement("b");
      value.textContent = `${entry.value}%`;
      row.append(label, bar, value);
      return row;
    }));
    panel.hidden = false;
  }

  function playbackStep() {
    if (!state.trace) return;
    const events = state.trace.events;
    $$(".kc-pipeline-stage.active, .kc-pipeline-link.active").forEach((element) => {
      element.classList.remove("active");
      element.classList.add("visited");
    });
    if (state.playbackIndex >= events.length) {
      finishTrace();
      $("#kc-trace-play").textContent = "↻ もう一度";
      return;
    }
    const event = events[state.playbackIndex];
    const block = $(`[data-block-id="${CSS.escape(event.payload.block_id)}"]`);
    block?.classList.add("active");
    block?.scrollIntoView({behavior: reducedMotion ? "auto" : "smooth", block: "nearest", inline: "center"});
    if (state.playbackIndex > 0) {
      $(`[data-link-index="${state.playbackIndex}"]`)?.classList.add("active");
    }
    appendTraceEvent(event);
    state.playbackIndex += 1;
    const percent = Math.round(state.playbackIndex / events.length * 100);
    $("#kc-trace-progress").style.width = `${percent}%`;
    $("#kc-trace-step").textContent = `${state.playbackIndex} / ${events.length}`;
    if (reducedMotion) {
      playbackStep();
    } else {
      state.playbackTimer = window.setTimeout(playbackStep, 620);
    }
  }

  function playTrace() {
    if (!state.trace) return;
    clearTrace();
    $("#kc-trace-play").textContent = "再生中…";
    playbackStep();
  }

  async function createTrace(event) {
    event.preventDefault();
    const submit = $("button[type='submit']", event.currentTarget);
    submit.disabled = true;
    try {
      const payload = await requestJson("/api/knowledge-console/traces", {
        method: "POST",
        body: JSON.stringify({
          question: $("#kc-trace-question").value,
          expert_id: $("#kc-trace-expert").value,
          model_id: $("#kc-trace-model").value,
        }),
      });
      state.trace = payload.trace;
      $("#kc-trace-id").textContent = `Trace ${state.trace.trace_id.slice(0, 12)} · ${formatDate(state.trace.created_at)}`;
      $("#kc-trace-play").disabled = false;
      playTrace();
    } catch (error) {
      showAlert(error.message, "error");
    } finally {
      submit.disabled = false;
    }
  }

  $$(".kc-nav-item").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
  $("#kc-refresh").addEventListener("click", refresh);
  $("#kc-error-refresh").addEventListener("click", () => loadErrorHistory());
  $("#kc-error-older").addEventListener("click", () => loadErrorHistory(true));
  $("#kc-a100-status").addEventListener("click", () => switchView("a100"));
  $("#kc-goal-show-a100").addEventListener("click", () => { switchView("a100"); void refresh(); });
  document.addEventListener("kc-goals-updated", () => { void refresh(); });
  $("#kc-run-all").addEventListener("click", () => { void runA100TasksInOrder(); });
  $("#kc-run-a100-batch").addEventListener("click", () => { void runA100TasksInOrder(); });
  document.addEventListener("kc-run-goal-tasks", (event) => {
    const detail = event.detail || {};
    void (async () => {
      await refresh();
      return runA100TasksInOrder(detail.taskIds);
    })().then((result) => {
      document.dispatchEvent(new CustomEvent("kc-goal-tasks-finished", {
        detail: {goalId: detail.goalId, ...(result || {ok: false, message: "自動実行を開始できませんでした。"})},
      }));
    });
  });
  $("#kc-apply-bridge").addEventListener("click", applyBridgeConfiguration);
  $("#kc-oauth-file").addEventListener("change", uploadOAuthClient);
  $("#kc-setup-authorize").addEventListener("click", authorizeDrive);
  $("#kc-setup-notebook").addEventListener("click", publishNotebook);
  $$(".kc-open-setup").forEach((button) => button.addEventListener("click", openSetupDialog));
  $("#kc-close-setup").addEventListener("click", () => $("#kc-setup-dialog").close());
  $$(".kc-check-connection").forEach((button) => button.addEventListener("click", checkConnectionFromButton));
  $("#kc-open-task").addEventListener("click", () => $("#kc-task-dialog").showModal());
  $("#kc-close-task").addEventListener("click", () => $("#kc-task-dialog").close());
  $("#kc-cancel-task").addEventListener("click", () => $("#kc-task-dialog").close());
  $("#kc-task-form").addEventListener("submit", createTask);
  $("#kc-task-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-execute-task]");
    if (button) executeTask(button);
  });
  ["#kc-a100-task-board", "#kc-a100-done-board"].forEach((selector) => {
    $(selector).addEventListener("click", (event) => {
      const button = event.target.closest("[data-execute-task]");
      if (button) executeTask(button);
    });
  });
  $("#kc-trace-form").addEventListener("submit", createTrace);
  $("#kc-trace-play").addEventListener("click", playTrace);
  switchView(["#trace", "#a100", "#goals"].includes(location.hash) ? location.hash.slice(1) : "dashboard");
  refresh();
  void autoCheckConnection();
})();
