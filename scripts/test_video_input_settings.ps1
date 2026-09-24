param(
    [switch]$ReviewWithJev
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = 'python'
}

$env:PYTHONPATH = Join-Path $repoRoot 'src'
$testOutputFile = [System.IO.Path]::GetTempFileName()

function Invoke-PythonCapture([string]$arguments) {
    $stdoutFile = [System.IO.Path]::GetTempFileName()
    $stderrFile = [System.IO.Path]::GetTempFileName()
    try {
        $process = Start-Process -FilePath $python -ArgumentList $arguments `
            -WorkingDirectory $repoRoot -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
        $stdout = Get-Content -LiteralPath $stdoutFile -Raw -ErrorAction SilentlyContinue
        $stderr = Get-Content -LiteralPath $stderrFile -Raw -ErrorAction SilentlyContinue
        return [pscustomobject]@{ ExitCode = $process.ExitCode; Text = ($stdout + $stderr) }
    }
    finally {
        Remove-Item -LiteralPath $stdoutFile, $stderrFile -ErrorAction SilentlyContinue
    }
}

Push-Location $repoRoot
try {
    $testResult = Invoke-PythonCapture '-m unittest tests.test_ui_defaults'
    $testExitCode = $testResult.ExitCode
    Write-Output $testResult.Text
    if ($testExitCode -ne 0) {
        throw "UI regression tests failed with exit code $testExitCode."
    }

    $browserResult = Invoke-PythonCapture 'scripts\browser_video_input_settings_qa.py'
    $browserExitCode = $browserResult.ExitCode
    if ($browserExitCode -ne 0) {
        Write-Output $browserResult.Text
        throw "Browser UI checks failed with exit code $browserExitCode."
    }
    $browserReportPath = Join-Path $repoRoot 'output\design\video-input\browser-qa.json'
    if (-not (Test-Path -LiteralPath $browserReportPath)) {
        throw 'Browser QA report is missing.'
    }
    $browserReport = Get-Content -LiteralPath $browserReportPath -Raw | ConvertFrom-Json
    Write-Output 'Browser QA: PASS (1440x900, 1280x800, 390x844); report saved to output/design/video-input/browser-qa.json.'

    if ($ReviewWithJev) {
        $testSummaryText = $testResult.Text
        $testCount = 0
        if ($testSummaryText -match 'Ran\s+(\d+)\s+tests?') { $testCount = [int]$Matches[1] }
        $evidence = [ordered]@{
            unittest = [ordered]@{ status = 'PASS'; tests_run = $testCount; failures = 0 }
            browser = $browserReport
        }
        $compactEvidence = $evidence | ConvertTo-Json -Depth 8 -Compress
        if ($compactEvidence.Length -gt 4000) {
            throw "Sanitized Jev evidence exceeds the 4,000-character limit ($($compactEvidence.Length))."
        }
        [System.IO.File]::WriteAllText($testOutputFile, $compactEvidence, [System.Text.UTF8Encoding]::new($false))
        $jevResult = Invoke-PythonCapture "scripts\review_video_input_settings_with_jev.py $testOutputFile"
        Write-Output $jevResult.Text
        if ($jevResult.ExitCode -ne 0) {
            throw "Jev QA classification returned exit code $($jevResult.ExitCode)."
        }
    }
}
finally {
    Pop-Location
    Remove-Item -LiteralPath $testOutputFile -ErrorAction SilentlyContinue
}
