import re
import unittest

import app


class UiDefaultsTests(unittest.TestCase):
    def test_processing_labels_and_json_visibility(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertIn("おすすめ — ノイズ除去・音量調整・明瞭化", page)
        self.assertIn("<strong>詳細処理</strong>", page)
        self.assertIn(
            "複数回処理やエフェクトを加えて精度を上げます。注意：処理時間が増えます",
            page,
        )
        self.assertIn("文章整形 <em>任意</em>", page)
        self.assertIn('name="transcript_finishing_mode" type="radio" value="recommended" checked', page)
        self.assertIn("TXT は常に作成", page)
        self.assertNotIn("JSON（常時）", page)

    def test_new_job_form_exposes_guided_defaults_and_advanced_settings(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertIn("新しい文字起こし", page)
        self.assertIn('id="file-drop-zone"', page)
        self.assertIn("ここへドラッグ＆ドロップ", page)
        self.assertIn("パスと保存先を指定", page)
        self.assertIn("処理装置・話者数・無音判定", page)
        self.assertIn('id="setup-ready-state"', page)
        # Recognition is the first setting and starts open; other panels open on request.
        self.assertIn('id="settings-summary"', page)
        for panel in ("recognition", "vocabulary", "finishing", "emotion", "output"):
            self.assertIn(f'data-open-panel="{panel}"', page)
            self.assertRegex(page, rf'<details[^>]*data-settings-panel="{panel}"')
        self.assertRegex(page, r'<details[^>]*data-settings-panel="recognition"[^>]*\bopen\b')
        for panel in ("vocabulary", "finishing", "emotion", "output"):
            self.assertNotRegex(page, rf'<details[^>]*data-settings-panel="{panel}"[^>]*\bopen\b')
        self.assertIn('id="flow-steps"', page)
        self.assertIn('class="primary-button launch-button"', page)
        self.assertRegex(page, r'id="finish-in-obsidian"[^>]*checked')
        self.assertIn('id="obsidian-finishing-button"', page)
        self.assertRegex(
            page,
            r'id="start-button"[^>]*type="submit"[^>]*disabled',
        )

    def test_conversation_modes_are_visible_and_apply_presets(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertIn('id="setup-mode"', page)
        self.assertIn('name="conversation_mode" type="radio" value="meeting" checked', page)
        self.assertIn('name="conversation_mode" type="radio" value="group_interview"', page)
        self.assertIn('name="conversation_mode" type="radio" value="chat"', page)
        self.assertIn('id="conversation-mode-hint"', page)
        self.assertIn('<option value="chat">雑談</option>', page)

        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("const conversationModePresets", script)
        self.assertIn("function applyConversationMode", script)
        self.assertIn("group_interview", script)
        self.assertIn("minSpeakers: 3", script)
        self.assertIn("maxSpeakers: 12", script)

        styles = (app.APP_DIRECTORY / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn(".conversation-mode-options", styles)
        self.assertIn(".conversation-mode-option input:checked", styles)

    def test_meeting_mode_has_visual_minutes_and_handoff_actions(self):
        response = app.app.test_client().get("/")
        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertIn('id="meeting-minutes-view"', page)
        self.assertIn('id="meeting-minutes-download"', page)
        self.assertIn('id="meeting-tasks-download"', page)
        self.assertIn('id="meeting-json-download"', page)
        self.assertIn('id="meeting-priority-chart"', page)
        self.assertIn('id="meeting-obsidian-save"', page)
        self.assertIn('id="meeting-obsidian-open"', page)
        self.assertIn('id="meeting-obsidian-status"', page)

        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function renderMeetingMinutes", script)
        self.assertIn("meeting-tasks.csv", script)
        self.assertIn("gurumoji.meeting.v1", script)
        self.assertIn("function loadMeetingObsidianStatus", script)
        self.assertIn("/meeting-obsidian`, {method: 'POST'}", script)

    def test_create_flow_uses_one_stepper_for_desktop_and_phone(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertEqual(page.count('id="job-form"'), 1)
        self.assertEqual(page.count('id="flow-steps"'), 1)
        for step in ("1", "2", "3"):
            self.assertEqual(page.count(f'data-flow-step="{step}"'), 1)
            self.assertEqual(page.count(f'data-flow-section="{step}"'), 1)
        self.assertNotIn('data-flow-section="4"', page)
        self.assertIn('id="mobile-wizard-nav"', page)
        self.assertIn('data-review-source', page)
        self.assertNotIn("desktop-create-sidebar", page)
        self.assertNotIn("mobile-create-header", page)
        self.assertNotIn("quick-flow", page)
        ids = re.findall(r'\bid="([^"]+)"', page)
        self.assertEqual(len(ids), len(set(ids)))

    def test_ai_provider_selection_applies_finishing_mode_and_json_downloads_are_hidden(self):
        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        effort_script = (app.APP_DIRECTORY / "static" / "ai-effort.js").read_text(encoding="utf-8")

        self.assertIn("listen(aiProvider, 'change', selectDefaultAiOptions);", script)
        self.assertIn("function applyTranscriptFinishingPreset()", script)
        self.assertIn("mode === 'advanced' && hasAi", script)
        self.assertIn("mode !== 'off' && hasAi", script)
        self.assertIn("mode === 'advanced' && hasAi && Boolean(tokenConfigSnapshot.typesafe)", script)
        self.assertIn("[['off', 'なし'], ['low', '小'], ['medium', '中'], ['high', '高'], ['ultra', 'MAX']]", effort_script)
        self.assertIn("前を1発話ずつ最大10回", effort_script)
        self.assertIn("前後最大10発話", effort_script)
        self.assertIn("if (aiProvider.value === 'none') input.checked = false;", script)
        self.assertIn("function applyLmStudioDefaults(config)", script)
        self.assertIn("config.lmstudio || !String(config.lmstudio_model || '').trim()", script)
        self.assertIn("applyLmStudioDefaults(data);", script)
        self.assertIn(
            ".filter(file => !String(file.name || '').toLowerCase().endsWith('.json'))",
            script,
        )
        self.assertIn("function updateCreateSummary()", script)
        self.assertIn("listen(fileDropZone, 'drop'", script)
        self.assertIn("window.matchMedia('(max-width: 959px)')", script)
        self.assertIn("browserFilePickerOnly || isMobileWizard()", script)
        self.assertIn("function setMobileStep(", script)

        styles = (app.APP_DIRECTORY / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn("--app-bar-height", styles)
        self.assertIn("@media (min-width: 960px)", styles)
        self.assertIn("@media (max-width: 959px)", styles)

    def test_processed_data_and_speaker_management_have_dedicated_responsive_ux(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertIn(">話者管理</button>", page)
        self.assertNotIn("話者台帳", page)
        self.assertIn('class="library-overview"', page)
        self.assertIn('id="library-filter-panel"', page)
        self.assertIn('id="library-filter-toggle"', page)
        self.assertIn('id="add-record-dialog"', page)
        self.assertIn('class="registry-overview"', page)
        self.assertIn('id="speaker-registry-list"', page)
        self.assertIn('id="registry-save-state"', page)
        self.assertIn('id="speaker-survey-analysis"', page)
        self.assertIn('id="speaker-survey-analysis-content"', page)
        self.assertIn("事前アンケート分析", page)
        self.assertIn("事前アンケート回答", page)
        self.assertIn('id="speaker-identity-provider"', page)
        self.assertIn('id="rerun-speaker-identification"', page)
        self.assertIn("自己紹介から話者を再特定・登録", page)
        self.assertIn('role="tabpanel"', page)
        self.assertNotIn("研究同意", page)
        self.assertNotIn("録音同意", page)

        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function renderSpeakerRegistryTable(", script)
        self.assertIn("function renderSpeakerRegistryCards(", script)
        self.assertIn("function setSpeakerRegistryDirty(", script)
        self.assertIn("libraryRequestController.abort()", script)
        self.assertIn("function clearLibraryFilters()", script)
        self.assertIn("className = 'library-group-heading'", script)
        self.assertIn("function renderSpeakerSurveyAnalysis()", script)
        self.assertIn("function buildSpeakerSurveyCrosstab(", script)
        self.assertIn("function speakerSurveyCorrelation(", script)
        self.assertIn("function analysisGroupByOptions()", script)
        self.assertIn("事前アンケート：", script)
        self.assertIn("function showView(", script)
        self.assertIn("async function rerunSpeakerIdentification()", script)
        self.assertIn("/speaker-identification`, {", script)
        self.assertIn("listen(showLibraryAnalysisButton, 'click'", script)
        self.assertIn("function openAnalysisForItem(itemId)", script)
        self.assertIn("showView('analysis', {analysisItemId: targetItemId})", script)
        self.assertIn("function openResultDestination(destination)", script)
        self.assertIn("openResultDestination(button.dataset.resultDestination)", script)
        self.assertIn("analyze.textContent = '分析・可視化';", script)
        self.assertIn("listen(resultAnalysisButton, 'click'", script)
        self.assertIn("open.className = 'library-card-open';", script)
        self.assertNotIn("open.textContent = '開いて編集';", script)
        self.assertNotIn("話者台帳", script)
        self.assertNotIn("研究同意 未確認", script)
        self.assertNotIn("録音同意 未確認", script)
        self.assertIn("自己紹介から話者を特定・登録", page)
        self.assertIn("候補抽出とリンク再確認を2回処理", page)
        self.assertIn("AI自動生成アウトライン", page)
        self.assertIn('id="session-date-note"', page)
        self.assertIn('id="session-notes-details"', page)
        self.assertNotIn("守秘・同意メモ", page)
        self.assertNotIn('id="session-confidentiality"', page)

        styles = (app.APP_DIRECTORY / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn(".speaker-registry-list { display: none; }", styles)
        self.assertIn(".speaker-management-card", styles)
        self.assertIn(".library-workspace", styles)
        self.assertIn(".library-card-open", styles)
        self.assertIn(".library-card-open:focus-visible", styles)
        self.assertIn(".library-analysis-button", styles)
        self.assertIn(".item-tabs", styles)
        self.assertIn(".item-actions", styles)
        self.assertIn(".speaker-survey-analysis", styles)
        self.assertIn(".speaker-survey-table", styles)
        self.assertIn(".speaker-survey-completeness", styles)
        self.assertIn("@media (min-width: 960px)", styles)
        self.assertIn("@media (max-width: 959px)", styles)

    def test_analysis_has_separate_responsive_workspace_and_manual_boundaries(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertEqual(
            len(re.findall(r'class="[^"]*\bview-tab\b[^"]*"', page)),
            4,
        )
        self.assertIn('id="show-analysis-button"', page)
        self.assertIn('id="processed-data-hub"', page)
        self.assertIn('id="show-library-list-button"', page)
        self.assertIn('id="show-library-analysis-button"', page)
        self.assertIn('id="manage-library-groups-button"', page)
        self.assertIn('id="library-group-dialog"', page)
        self.assertIn('id="library-group"', page)
        self.assertIn('id="analysis-card"', page)
        self.assertIn('id="result-analysis-button"', page)
        self.assertIn('id="analysis-open-item-button"', page)
        self.assertIn('class="item-tabs"', page)
        for tab in ("transcript", "conversation", "summary", "files"):
            self.assertEqual(page.count(f'data-item-tab="{tab}"'), 1)
            self.assertEqual(page.count(f'data-item-panel="{tab}"'), 1)
        self.assertIn('data-result-destination="speakers"', page)
        self.assertIn('<h1 id="analysis-title">会話データの分析結果</h1>', page)
        self.assertIn('class="analysis-desktop-layout desktop-only"', page)
        self.assertIn('class="analysis-mobile-layout mobile-only"', page)
        self.assertIn("自動集計", page)
        self.assertIn("要設定", page)
        self.assertIn("要確認・解釈", page)
        self.assertIn('id="analysis-xlsx-export"', page)
        self.assertIn("Excel（標準出力）", page)
        self.assertIn('id="analysis-json-export"', page)
        self.assertIn('id="analysis-run-button"', page)
        self.assertIn('id="analysis-run-settings-button"', page)
        self.assertIn('id="analysis-run-dialog"', page)
        self.assertIn('id="analysis-execution-view"', page)
        self.assertIn('id="analysis-manual-definition"', page)
        self.assertIn('id="analysis-definition-description"', page)
        self.assertIn('id="analysis-job-chip"', page)
        self.assertIn("自動実行", page)
        self.assertIn("手動実行", page)
        self.assertIn("バックグラウンドで続ける", page)
        self.assertIn("analysis-execution.js", page)

        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("async function loadAnalysisCatalog(", script)
        self.assertIn("async function loadAnalysisItem(", script)
        self.assertIn("function renderAutomaticAnalysis(", script)
        self.assertIn("function buildAnalysisCooccurrenceChart(", script)
        self.assertIn("function buildAnalysisTimelineChart(", script)
        self.assertIn("function buildAnalysisTermTreeChart(", script)
        self.assertIn("function buildAnalysisDependencyExplorer(", script)
        self.assertIn("function buildAnalysisCorrelationExplorer(", script)
        self.assertIn("function buildAnalysisDescriptiveChart(", script)
        self.assertIn("function buildAnalysisFrequencyExplorer(", script)
        self.assertIn("function buildAnalysisEffectChart(", script)
        self.assertIn("function buildAnalysisCrosstabExplorer(", script)
        self.assertIn("function buildAnalysisNavigation(", script)
        self.assertIn("function syncAnalysisNavigationToScroll(", script)
        self.assertIn("function buildAnalysisScopeSwitch(", script)
        self.assertIn("function renderSpeakerAnalysis(", script)
        self.assertIn("function analysisSpeakerAttributeDimensions(", script)
        self.assertIn("data-analysis-speaker-id", script)
        self.assertIn("インタビュー全体", script)
        self.assertIn("で絞り込み", script)
        self.assertIn("prefers-reduced-motion: reduce", script)
        self.assertIn("発話量の変化（時間別）", script)
        self.assertIn("文章内の言葉のつながり（係り受け）", script)
        self.assertIn("指標どうしの関係（相関）", script)
        self.assertIn("function appendResearchAnalysis(", script)
        self.assertIn("const requestedParameters = new URLSearchParams(window.location.search);", script)
        self.assertIn("const requestedView = requestedParameters.get('view');", script)
        self.assertIn("const requestedAnalysisSection", script)
        self.assertIn("function renderManualAnalysis(", script)
        self.assertIn("async function saveAnalysis(", script)
        self.assertIn("function buildSegmentClassificationPanel(", script)
        self.assertIn("async function runSegmentClassification(", script)
        self.assertIn("data-analysis-annotation-field", script)
        self.assertIn("importance_score", script)
        self.assertIn("segment_classification_crosstabs", script)
        self.assertIn("source_revision:", script)
        self.assertIn("analysis_revision:", script)
        self.assertIn("['coded_segments', 'コード済み発話 CSV']", script)
        self.assertIn("['overlaps', '重なり候補 CSV']", script)
        self.assertIn("['morphemes', '形態素 CSV']", script)
        self.assertIn("['statistical_tests', '統計検定 CSV']", script)
        self.assertNotIn("participant: '参加者単位'", script)
        self.assertNotIn("topic: 'テーマ単位'", script)

        execution = (app.APP_DIRECTORY / "static" / "analysis-execution.js").read_text(encoding="utf-8")
        self.assertIn("const analysisExecutionStageDefinitions", execution)
        self.assertIn("function openAnalysisExecutionDialog(", execution)
        self.assertIn("async function analysisExecutionPoll(", execution)
        self.assertIn("async function cancelAnalysisExecution(", execution)
        self.assertIn("async function analysisExecutionPrepareDefinition(", execution)
        self.assertIn("/analysis/pipelines", execution)
        self.assertIn("provider_policy: 'local_only'", execution)

        styles = (app.APP_DIRECTORY / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion", styles)
        self.assertIn(".analysis-desktop-layout", styles)
        self.assertIn(".analysis-mobile-layout", styles)
        self.assertIn(".item-tabs", styles)
        self.assertIn("grid-template-columns: 1fr 1fr", styles)
        self.assertIn(".analysis-save-bar", styles)
        self.assertIn(".analysis-cooccurrence-chart", styles)
        self.assertIn(".analysis-insight-nav", styles)
        self.assertIn(".analysis-scope-switch", styles)
        self.assertIn(".analysis-speaker-dashboard", styles)
        self.assertIn(".analysis-speaker-sort-controls", styles)
        self.assertIn(".analysis-speaker-detail-header", styles)
        self.assertIn(".analysis-line-series", styles)
        self.assertIn(".analysis-term-tree", styles)
        self.assertIn(".analysis-dependency-tree", styles)
        self.assertIn(".analysis-correlation-table", styles)
        self.assertIn(".analysis-distribution-chart", styles)
        self.assertIn(".analysis-effect-chart", styles)
        self.assertIn(".analysis-stacked-bar", styles)
        self.assertIn(".analysis-engine-notice", styles)
        self.assertIn(".segment-proposal-grid", styles)
        self.assertIn(".segment-manual-classification", styles)

    def test_transcript_edits_are_guarded_and_running_jobs_can_reconnect(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertIn(
            'accept=".mp4,.m4v,.mov,.mkv,.wav,.mp3,.m4a,.flac"',
            page,
        )
        self.assertNotIn("audio/*", page)
        self.assertNotIn("video/*", page)

        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("let currentJobDirty = false;", script)
        self.assertIn("let currentJobMutationGeneration = 0;", script)
        self.assertIn("let jobFlowGeneration = 0;", script)
        self.assertIn("let speakerRegistryMutationGeneration = 0;", script)
        self.assertIn("let speakerRegistryRevision = 0;", script)
        self.assertIn("registry_revision: speakerRegistryRevision", script)
        self.assertIn("body.append('registry_revision', String(speakerRegistryRevision))", script)
        self.assertIn("let analysisMutationGeneration = 0;", script)
        self.assertIn("currentJobMutationGeneration !== saveGeneration", script)
        self.assertIn("speakerRegistryMutationGeneration === saveGeneration", script)
        self.assertIn("analysisMutationGeneration !== saveGeneration", script)
        self.assertIn("保存開始後の追加変更が残っています", script)
        self.assertIn("if (!currentJobDirty && !speakerRegistryDirty", script)
        self.assertIn("文字起こし、会話プロファイル、または話者連携に未保存", script)
        self.assertIn("revision_count: Number(currentJob.revision_count || 0)", script)
        self.assertIn("window.sessionStorage.setItem(activeJobStorageKey", script)
        self.assertIn("window.sessionStorage.setItem(pendingSubmissionStorageKey", script)
        self.assertIn("const pendingSubmissionId = storedPendingSubmissionId();", script)
        self.assertIn("storePendingSubmissionId(submissionId);", script)
        self.assertIn("responseStatus >= 400 && responseStatus < 500", script)
        self.assertIn("apiFetch('/api/jobs/active'", script)
        self.assertIn("pollFailureCount += 1;", script)
        self.assertIn("schedulePoll(delay);", script)
        self.assertIn("if (jobRunning) cancelButton.disabled = false;", script)
        self.assertIn("async function recoverSubmittedJob(", script)
        self.assertIn(
            "await recoverSubmittedJob(error.message, submissionId, 0, submissionGeneration);",
            script,
        )
        self.assertIn("'X-Gurumoji-Submission-Id': submissionId", script)
        self.assertIn("encodeURIComponent(submissionId)", script)
        self.assertIn(
            "const confirmedAbsent = absenceConfirmed || confirmedAbsentThisAttempt;",
            script,
        )
        self.assertIn("if (confirmedAbsent) markPendingSubmissionRetryable(submissionId);", script)
        self.assertIn("function pendingSubmissionRetryAllowed(submissionId)", script)
        self.assertIn("? unresolvedSubmissionId\n    : createSubmissionId();", script)
        self.assertIn("['admitting', 'committing'].includes(job.status)", script)
        self.assertNotIn("pendingSubmissionMaxAgeMs", script)
        restore_start = script.index("async function restoreActiveJob()")
        restore_lock = script.index("setRunning(true);", restore_start)
        restore_request = script.index("encodeURIComponent(storedId)", restore_start)
        self.assertLess(restore_lock, restore_request)
        self.assertIn(
            "if (restoreGeneration !== jobFlowGeneration) return;",
            script[restore_start:script.index("async function recoverSubmittedJob(")],
        )
        submit_start = script.index("listen(form, 'submit'")
        unresolved_check = script.index(
            "const unresolvedSubmissionId = storedPendingSubmissionId();",
            submit_start,
        )
        new_submission_id = script.index(
            "const submissionId = retryUnacceptedSubmission",
            submit_start,
        )
        self.assertLess(unresolved_check, new_submission_id)
        self.assertIn(
            "'前回の送信結果がまだ確認できません。',\n"
            "      unresolvedSubmissionId,",
            script[unresolved_check:new_submission_id],
        )
        self.assertIn(
            "if (submissionGeneration !== jobFlowGeneration) return;",
            script[submit_start:script.index("async function pollJob()")],
        )
        self.assertIn("async function fetchPersistedJob(jobId)", script)
        self.assertIn("await fetchPersistedJob(storedId)", script)
        self.assertIn("await fetchPersistedJob(requestedJobId)", script)
        self.assertIn("cancellable || ['admitting', 'committing'].includes(job.status)", script)
        self.assertIn("committing: '結果を保存中'", script)
        self.assertNotIn("setInterval(pollJob", script)
        self.assertIn("headers.set('X-Gurumoji-Request', '1');", script)
        self.assertIn("apiFetch('/api/source-thumbnail', {", script)
        self.assertIn("method: 'POST'", script)
        self.assertIn("URL.revokeObjectURL(sourceThumbnailObjectUrl)", script)
        self.assertNotIn("sourceThumbnail.src = `/api/source-thumbnail?", script)
        self.assertIn("function deleteRecoveryNote(data)", script)
        self.assertIn("Array.isArray(data && data.recovery_paths)", script)
        self.assertIn("const recoveryNote = deleteRecoveryNote(data);", script)
        self.assertIn("${recoveryNote}`", script)
        self.assertIn("Boolean(cleanupWarning || recoveryNote)", script)
        self.assertIn(
            "if (!response.ok) throw new Error(data.error || '学習履歴を確認できませんでした。');",
            script,
        )
        self.assertIn("container.textContent = error.message", script)
        self.assertNotIn("await fetch(", script)
        self.assertEqual(script.count("window.fetch("), 2)

    def test_windows_launchers_quote_python_and_fingerprint_requirements(self):
        run_script = (app.PROJECT_DIRECTORY / "run.bat").read_text(encoding="utf-8")
        launcher_script = (app.PROJECT_DIRECTORY / "scripts" / "run_launcher.ps1").read_text(encoding="utf-8")
        emotion_script = (app.PROJECT_DIRECTORY / "scripts" / "setup_emotion.bat").read_text(encoding="utf-8")

        self.assertNotRegex(run_script, r"(?m)^\s*%PYTHON%")
        self.assertNotRegex(emotion_script, r"(?m)^\s*%PYTHON%")
        self.assertRegex(run_script, r'"%PYTHON%" -u -m gurumoji\.app')
        self.assertIn("REQUIREMENTS_HASH", run_script)
        self.assertIn("certutil -hashfile", run_script)
        self.assertIn('"%PYTHON%" -m pip check', run_script)
        self.assertIn('-File "%~dp0scripts\\run_launcher.ps1"', run_script)
        self.assertIn("MOJIOKOSI_SKIP_UPDATE_CHECK", launcher_script)
        self.assertIn("ensure_visualization_shortcut.ps1", launcher_script)
        self.assertIn("MOJIOKOSI_SKIP_LIBRARY_UPDATE", run_script)
        self.assertIn("--upgrade-strategy only-if-needed", run_script)
        self.assertIn("imageio_ffmpeg.get_ffmpeg_exe()", run_script)
        self.assertIn('"%PROJECT_FFMPEG%"', run_script)
        self.assertIn("EMOTION_REQUIREMENTS_HASH", emotion_script)
        self.assertIn('-r "%EMOTION_REQUIREMENTS%"', emotion_script)
        self.assertIn('"%PYTHON%" -m pip check', emotion_script)

    def test_boot_sequence_and_two_level_progress_are_exposed(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertEqual(app.APP_CREATOR, "Kurokawa")
        self.assertIn('class="boot-credit">CREATED BY KUROKAWA</p>', page)
        self.assertIn("STARTING · LOADING WORKSPACE", page)
        self.assertIn('id="progress-overall-track"', page)
        self.assertIn('id="progress-stage-track"', page)
        self.assertIn('id="progress-stage-bar"', page)
        self.assertIn('id="progress-activity-label"', page)
        self.assertIn('class="resource-monitor"', page)
        self.assertIn('id="monitor-cpu-value"', page)
        self.assertIn('id="monitor-gpu-value"', page)
        self.assertIn('id="monitor-memory-value"', page)
        self.assertIn('id="monitor-read-light"', page)
        self.assertIn('id="monitor-write-light"', page)
        self.assertIn('id="progress-ai-usage"', page)
        self.assertIn('id="result-ai-usage"', page)
        self.assertIn("入力トークン", page)
        self.assertIn("合計トークン", page)

        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("bootSplash.classList.add('show-main')", script)
        self.assertIn("}, 200);", script)
        self.assertIn("function fallbackProgressStage(", script)
        self.assertIn("job.stage_progress", script)
        self.assertIn("progress-stage-bar", script)
        self.assertIn("async function pollSystemActivity()", script)
        self.assertIn("'/api/system/activity'", script)
        self.assertIn("function renderSystemActivity(", script)
        self.assertIn("function renderAiTokenUsage(", script)
        self.assertIn("job.ai_usage", script)

        styles = (app.APP_DIRECTORY / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn(".current-process-panel", styles)
        self.assertIn(".process-activity", styles)
        self.assertIn("@keyframes process-wave", styles)
        self.assertIn("@keyframes process-shimmer", styles)
        self.assertIn(".resource-monitor-grid", styles)
        self.assertIn(".io-light.read.is-active", styles)
        self.assertIn(".io-light.write.is-active", styles)
        self.assertIn(".ai-token-usage", styles)
        self.assertIn(".ai-token-grid", styles)

        job = app.JobRecord(
            id="stage-progress-test",
            source_name="sample.wav",
            output_dir=app.RUNTIME_DIRECTORY / "output",
            write_srt=False,
            write_json=True,
        )
        app.update_job(
            job,
            progress=37,
            stage="transcription",
            stage_label="文字起こし",
            stage_progress=42,
        )
        public = job.public()
        self.assertEqual(public["progress"], 37)
        self.assertEqual(public["stage"], "transcription")
        self.assertEqual(public["stage_label"], "文字起こし")
        self.assertEqual(public["stage_progress"], 42)
        job.ai_usage = {
            "provider": "openai", "model": "gpt-test", "request_count": 2,
            "input_tokens": 100, "output_tokens": 20, "total_tokens": 120,
            "cached_tokens": 0, "reasoning_tokens": 0, "reported": True,
        }
        self.assertEqual(job.public()["ai_usage"]["total_tokens"], 120)

    def test_processed_item_opens_with_the_plan_and_result_outline(self):
        page = app.app.test_client().get("/").data.decode("utf-8")
        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")

        # The block comes before the workspace tabs, so it is the first thing in view.
        self.assertLess(page.index('id="session-outline"'), page.index('class="item-tabs"'))
        self.assertIn('id="session-outline-content"', page)
        self.assertIn("アウトライン（予定と結果）", page)
        self.assertIn("function renderSessionOutline(data, outline)", script)
        self.assertIn("renderSessionOutline(job.session_outline, job.outline);", script)
        # Without a guide the block says so and still shows the result and agenda titles.
        self.assertIn("予定（質問ガイド・議題）は登録されていません。", script)
        self.assertIn("結果（時間順）", script)
        self.assertIn("'AI議題'", script)

    def test_transformer_panel_offers_auto_candidate_and_manual_themes(self):
        script = (app.APP_DIRECTORY / "static" / "analysis-content.js").read_text(encoding="utf-8")

        # The three ways of deciding themes are one control, with their own inputs.
        self.assertIn("['auto', '自動でまとめる'], ['candidate', '候補から選ぶ'], ['manual', '手動で定義する']", script)
        self.assertIn("data-transformer-mode", script.replace("dataset.transformerMode", "data-transformer-mode"))
        self.assertIn("function buildTransformerCandidateList", script)
        self.assertIn("function buildTransformerManualTopics", script)
        # Candidate counts come from the saved run, and the request carries the mode.
        self.assertIn("quality ? result.quality.cluster_candidates : null", script)
        self.assertIn("mode, min_similarity: minSimilarity", script)
        # Manual themes are researcher-owned config, so editing them asks for a save first.
        self.assertIn("analysisState.config.transformer_topics", script)
        self.assertIn("手動で割り当てるには、テーマを2件以上定義して保存してください。", script)
        self.assertIn("テーマの妥当性を確かめた結果ではありません", script)

    def test_registered_ui_ux_fixes_stay_in_place(self):
        page = app.app.test_client().get("/").data.decode("utf-8")
        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        styles = (app.APP_DIRECTORY / "static" / "style.css").read_text(encoding="utf-8")

        # UX-11: deleting lives in its own zone, outside the sticky save bar.
        sticky = re.search(r'<div class="sticky-actions">(.*?)</div>', page, re.S).group(1)
        self.assertNotIn('id="delete-record-button"', sticky)
        self.assertRegex(page, r'class="result-danger-zone"[\s\S]*id="delete-record-button"')
        # UX-12: cancelling a job asks first.
        self.assertRegex(
            script,
            r"listen\(cancelButton, 'click', async \(\) => \{\s*if \(!activeJobId\) return;\s*if \(!window\.confirm\(",
        )
        # UX-14: a mode switch keeps values the user changed by hand.
        self.assertIn("const manuallyEditedModeFields = new Set();", script)
        self.assertIn("if (!manuallyEditedModeFields.has(field.key))", script)
        self.assertIn('id="conversation-mode-reset"', page)
        # UX-17: no font size below the shared minimum.
        self.assertIn("--text-min: .7rem;", styles)
        sizes = [float(value) for value in re.findall(r"font(?:-size)?:[^;]*?(?<![\d.])(0?\.\d+)rem", styles)]
        self.assertEqual([size for size in sizes if size < 0.7], [])
        # UX-23: tab semantics match the markup and support arrow keys.
        self.assertIn('aria-controls="processed-data-hub library-card analysis-card"', page)
        self.assertNotRegex(page, r'id="result-card"[^>]*role="tabpanel"')
        self.assertIn("function syncTabStops()", script)
        self.assertIn("ArrowRight: index + 1", script)
        # UX-24: the focus ring applies at every width, not only on phones.
        self.assertIn(":is(button, a, summary, input, select, textarea, [tabindex]):focus-visible { outline: var(--focus-ring);", styles)
        self.assertNotIn("button:focus-visible, a:focus-visible, summary:focus-visible", styles)
        # UX-06 / UX-07: the main task comes before the secondary panel.
        self.assertLess(page.index('id="analysis-shell"'), page.index('id="interview-comparison-card"'))
        self.assertLess(page.index('id="speaker-registry-body"'), page.index('id="speaker-survey-analysis"'))
        # UX-08: the splash no longer claims an update check and shows once per session.
        self.assertNotIn("CHECKING FOR UPDATES", page)
        self.assertIn("gurumoji.bootSplashSeen", script)
        # UX-10: the connection dialog shows token status at every width.
        self.assertEqual(page.count("data-status-provider="), 5)
        self.assertIn('id="connection-dialog"', page)
        self.assertIn('[data-status-provider="${id}"]', script)
        # UX-04: one name per concept.
        for text in (page, script):
            self.assertNotIn("ライブラリ", text)
            self.assertNotIn("認識と話者分離", text)

    def test_redesigned_navigation_routes_and_item_workspace(self):
        page = app.app.test_client().get("/").data.decode("utf-8")
        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        styles = (app.APP_DIRECTORY / "static" / "style.css").read_text(encoding="utf-8")

        # UX-01: every screen has a hash route and the back button works.
        self.assertIn("function routeHash(view, id = '')", script)
        self.assertIn("function parseRouteHash(hash)", script)
        self.assertIn("window.addEventListener('popstate'", script)
        self.assertIn("window.history.pushState(null, '', hash)", script)
        self.assertIn("applyRouteFromLocation({initial: true});", script)
        # UX-02 / UX-03: one record workspace with tabs; moves live in the header only.
        self.assertIn("function setItemTab(name)", script)
        self.assertNotIn("result-context-nav", page)
        sticky = re.search(r'<div class="sticky-actions">(.*?)</div>', page, re.S).group(1)
        self.assertNotIn("result-analysis-button", sticky)
        self.assertNotIn("new-button", sticky)
        # UX-05: one stepper drives both widths.
        self.assertIn("function renderFlowSteps()", script)
        self.assertNotIn("mobileStepContent[currentMobileStep].title", script)
        # UX-09: compact app bar instead of the hero; hardware lights once per place.
        self.assertIn('class="app-bar"', page)
        self.assertNotIn('class="hero"', page)
        self.assertEqual(page.count('data-hardware="cpu"'), 2)
        self.assertIn('data-device-dot="cpu"', page)
        # UX-16: the progress card belongs to the create screen; the header chip is global.
        self.assertIn('id="job-chip"', page)
        self.assertIn("function updateJobChip(job)", script)
        self.assertIn("let activeJobId = null;", script)
        # The launch review exposes the actual audio AI and CPU/GPU selected for each stage.
        self.assertIn('data-review-transcription', page)
        self.assertIn('data-review-diarization', page)
        self.assertIn('WhisperX (faster-whisper)', script)
        self.assertIn('pyannote.audio', script)
        # Each review card, including its text, is one large actionable button.
        self.assertEqual(page.count('class="launch-review-card"'), 4)
        self.assertNotIn('<div class="launch-review" aria-label="設定内容の確認">\n            <div>', page)
        self.assertIn('.launch-review-card { display: grid;', styles)
        # UX-18 / UX-27: shared palette and content-width buttons by default.
        effort_styles = (app.APP_DIRECTORY / "static" / "ai-effort.css").read_text(encoding="utf-8")
        self.assertNotIn("#315ed0", effort_styles)
        self.assertNotIn("var(--bg", effort_styles)
        self.assertIn(".primary-button { width: auto; margin: 0;", styles)
        # UX-21 / UX-22: no decorative English labels on every card.
        self.assertNotIn('class="eyebrow"', page)
        # Recognition is the first and initially open settings panel; others open on request.
        self.assertIn('id="panel-recognition" class="settings-panel" data-settings-panel="recognition" open', page)
        self.assertIn("function openSettingsPanel(name", script)


if __name__ == "__main__":
    unittest.main()
