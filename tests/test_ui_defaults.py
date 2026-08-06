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
        self.assertIn("<h2>AI仕上げ <em>任意</em></h2>", page)
        self.assertIn("<p>TXT は常に作成</p>", page)
        self.assertNotIn("JSON（常時）", page)

    def test_new_job_form_exposes_guided_defaults_and_advanced_settings(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertIn("<h2>新しい文字起こし</h2>", page)
        self.assertIn('id="file-drop-zone"', page)
        self.assertIn("ここへドラッグ＆ドロップ", page)
        self.assertIn("パスと保存先を指定", page)
        self.assertIn("処理装置・話者数・無音判定を手動調整", page)
        self.assertIn('id="setup-ready-state"', page)
        self.assertIn('class="primary-button launch-button"', page)
        self.assertRegex(
            page,
            r'id="start-button"[^>]*type="submit"[^>]*disabled',
        )

    def test_desktop_and_mobile_creation_interfaces_are_separate(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertEqual(page.count('id="job-form"'), 1)
        self.assertIn('class="desktop-create-sidebar desktop-only"', page)
        self.assertIn('class="mobile-create-header mobile-only"', page)
        self.assertIn('id="mobile-wizard-nav"', page)
        self.assertIn('data-mobile-step="1"', page)
        self.assertIn('data-mobile-step="2"', page)
        self.assertEqual(page.count('data-mobile-step="3"'), 2)
        self.assertIn('data-mobile-step="4"', page)
        self.assertIn('data-mobile-review-source', page)
        ids = re.findall(r'\bid="([^"]+)"', page)
        self.assertEqual(len(ids), len(set(ids)))

    def test_ai_provider_selection_enables_all_options_and_json_downloads_are_hidden(self):
        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("listen(aiProvider, 'change', selectDefaultAiOptions);", script)
        self.assertIn(
            "if (aiProvider.value !== 'none')",
            script,
        )
        self.assertIn("aiOptionInputs.forEach(input => { input.checked = true; });", script)
        self.assertIn("if (aiProvider.value === 'none') input.checked = false;", script)
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
        self.assertIn("width: min(calc(100% - 24px), 700px);", styles)
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
        self.assertIn("自己紹介から話者名を再特定", page)
        self.assertIn('role="tabpanel"', page)
        self.assertNotIn("研究同意", page)
        self.assertNotIn("録音同意", page)

        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function renderSpeakerRegistryTable(", script)
        self.assertIn("function renderSpeakerRegistryCards(", script)
        self.assertIn("function setSpeakerRegistryDirty(", script)
        self.assertIn("libraryRequestController.abort()", script)
        self.assertIn("function clearLibraryFilters()", script)
        self.assertIn("function renderSpeakerSurveyAnalysis()", script)
        self.assertIn("function buildSpeakerSurveyCrosstab(", script)
        self.assertIn("function speakerSurveyCorrelation(", script)
        self.assertIn("function analysisGroupByOptions()", script)
        self.assertIn("事前アンケート：", script)
        self.assertIn("function showProcessedDataSection(", script)
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
        self.assertIn("自己紹介から話者を特定・リンク", page)
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
        self.assertIn(".result-context-nav", styles)
        self.assertIn(".result-context-actions", styles)
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
            3,
        )
        self.assertNotIn('id="show-analysis-button"', page)
        self.assertIn('id="processed-data-hub"', page)
        self.assertIn('id="show-library-analysis-button"', page)
        self.assertIn('id="analysis-card"', page)
        self.assertIn('id="result-analysis-button"', page)
        self.assertIn("このデータを分析・可視化", page)
        self.assertIn('class="result-context-nav"', page)
        self.assertIn('id="result-context-name"', page)
        self.assertIn('data-result-destination="library"', page)
        self.assertIn('data-result-destination="analysis"', page)
        self.assertIn('data-result-destination="speakers"', page)
        self.assertIn('<h2 id="analysis-title">会話データの分析結果</h2>', page)
        self.assertIn('class="analysis-desktop-layout desktop-only"', page)
        self.assertIn('class="analysis-mobile-layout mobile-only"', page)
        self.assertIn("自動集計", page)
        self.assertIn("要設定", page)
        self.assertIn("要確認・解釈", page)
        self.assertIn('id="analysis-xlsx-export"', page)
        self.assertIn("Excel（標準出力）", page)
        self.assertIn('id="analysis-json-export"', page)

        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("async function loadAnalysisCatalog(", script)
        self.assertIn("async function loadAnalysisItem(", script)
        self.assertIn("function renderAutomaticAnalysis(", script)
        self.assertIn("function buildAnalysisCooccurrenceChart(", script)
        self.assertIn("function buildAnalysisTimelineChart(", script)
        self.assertIn("function buildAnalysisTermTreeChart(", script)
        self.assertIn("function buildAnalysisDependencyExplorer(", script)
        self.assertIn("function buildAnalysisCorrelationExplorer(", script)
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
        self.assertIn("source_revision:", script)
        self.assertIn("analysis_revision:", script)
        self.assertIn("['coded_segments', 'コード済み発話 CSV']", script)
        self.assertIn("['overlaps', '重なり候補 CSV']", script)
        self.assertIn("['morphemes', '形態素 CSV']", script)
        self.assertIn("['statistical_tests', '統計検定 CSV']", script)
        self.assertNotIn("participant: '参加者単位'", script)
        self.assertNotIn("topic: 'テーマ単位'", script)

        styles = (app.APP_DIRECTORY / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn(".analysis-desktop-layout", styles)
        self.assertIn(".analysis-mobile-layout", styles)
        self.assertIn(".processed-data-tabs", styles)
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
        self.assertIn(".analysis-engine-notice", styles)

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
        run_script = (app.APP_DIRECTORY / "run.bat").read_text(encoding="utf-8")
        emotion_script = (app.APP_DIRECTORY / "setup_emotion.bat").read_text(encoding="utf-8")

        self.assertNotRegex(run_script, r"(?m)^\s*%PYTHON%")
        self.assertNotRegex(emotion_script, r"(?m)^\s*%PYTHON%")
        self.assertIn('"%PYTHON%" app.py', run_script)
        self.assertIn("REQUIREMENTS_HASH", run_script)
        self.assertIn("certutil -hashfile", run_script)
        self.assertIn('"%PYTHON%" -m pip check', run_script)
        self.assertIn("CREATED BY KUROKAWA", run_script)
        self.assertIn("Start-Sleep -Milliseconds 200", run_script)
        self.assertIn("STARTING GURUMOJI...", run_script)
        self.assertIn("CHECKING FOR UPDATES...", run_script)
        self.assertIn("call :check_for_updates", run_script)
        self.assertIn("git fetch --quiet --prune origin", run_script)
        self.assertIn("git pull --ff-only --quiet", run_script)
        self.assertIn("MOJIOKOSI_SKIP_UPDATE_CHECK", run_script)
        self.assertIn("MOJIOKOSI_SKIP_LIBRARY_UPDATE", run_script)
        self.assertIn("--upgrade-strategy only-if-needed", run_script)
        self.assertIn("EMOTION_REQUIREMENTS_HASH", emotion_script)
        self.assertIn('-r "%EMOTION_REQUIREMENTS%"', emotion_script)
        self.assertIn('"%PYTHON%" -m pip check', emotion_script)

    def test_boot_sequence_and_two_level_progress_are_exposed(self):
        response = app.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.decode("utf-8")
        self.assertEqual(app.APP_CREATOR, "Kurokawa")
        self.assertIn('class="boot-credit">CREATED BY KUROKAWA</p>', page)
        self.assertIn("STARTING · CHECKING FOR UPDATES", page)
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
            output_dir=app.APP_DIRECTORY / "output",
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


if __name__ == "__main__":
    unittest.main()
