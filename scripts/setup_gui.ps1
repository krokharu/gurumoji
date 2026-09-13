# Requires Windows PowerShell 5.1 or PowerShell 7 on Windows.
# This bootstrapper uses only built-in WinForms so it can run before Python exists.

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$script:Root = Split-Path -Parent $PSScriptRoot
$script:TokenFile = Join-Path $script:Root 'config\tokens.json'
$script:RunBatch = Join-Path $script:Root 'run.bat'
$script:ActiveProcess = $null
$script:ActiveOutput = $null
$script:ActiveTitle = ''

function Get-JsonSettings {
    $settings = [ordered]@{}
    if (-not (Test-Path -LiteralPath $script:TokenFile)) {
        return $settings
    }
    try {
        $raw = Get-Content -LiteralPath $script:TokenFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -eq $raw) { return $settings }
        foreach ($property in $raw.PSObject.Properties) {
            $settings[$property.Name] = $property.Value
        }
        return $settings
    } catch {
        throw "tokens.json を読み込めません: $($_.Exception.Message)"
    }
}

function Get-SettingText {
    param(
        [System.Collections.IDictionary]$Settings,
        [string]$Name,
        [string]$Fallback = ''
    )
    if ($Settings.Contains($Name) -and $null -ne $Settings[$Name]) {
        return [string]$Settings[$Name]
    }
    return $Fallback
}

function Set-SettingValue {
    param(
        [System.Collections.IDictionary]$Settings,
        [string]$Name,
        [string]$Value
    )
    $Settings[$Name] = $Value.Trim()
}

function Save-JsonSettings {
    param([System.Collections.IDictionary]$Settings)
    $directory = Split-Path -Parent $script:TokenFile
    $temporary = Join-Path $directory ('.tokens-{0}.tmp' -f [guid]::NewGuid().ToString('N'))
    try {
        $content = $Settings | ConvertTo-Json -Depth 20
        [System.IO.File]::WriteAllText(
            $temporary,
            $content + [Environment]::NewLine,
            [System.Text.UTF8Encoding]::new($false)
        )
        Move-Item -LiteralPath $temporary -Destination $script:TokenFile -Force
    } finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        }
    }
}

function Find-SupportedPython {
    $versions = @('3.12', '3.13', '3.11', '3.10')
    $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonLauncher) {
        foreach ($version in $versions) {
            $output = @(& $pythonLauncher.Source ("-$version") -c "import struct,sys; print('.'.join(map(str, sys.version_info[:3])) if struct.calcsize('P') == 8 else '')" 2>$null)
            if ($LASTEXITCODE -eq 0 -and $output -and $output[0].ToString().Trim()) {
                return "Python $($output[0].ToString().Trim()) (py -$version)"
            }
        }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        $output = @(& $python.Source -c "import struct,sys; print('.'.join(map(str, sys.version_info[:3])) if (3, 10) <= sys.version_info[:2] < (3, 14) and struct.calcsize('P') == 8 else '')" 2>$null)
        if ($LASTEXITCODE -eq 0 -and $output -and $output[0].ToString().Trim()) {
            return "Python $($output[0].ToString().Trim()) (python)"
        }
    }
    return ''
}

function Get-EnvironmentReport {
    $python = Find-SupportedPython
    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    $venvPython = Join-Path $script:Root '.venv\Scripts\python.exe'
    $tokenState = if (Test-Path -LiteralPath $script:TokenFile) { '設定ファイルあり' } else { '未作成' }
    $lines = @(
        $(if ($python) { "Python: OK — $python" } else { 'Python: 未検出（3.10〜3.13 / 64 bit が必要）' }),
        $(if ($ffmpeg) { "FFmpeg: OK — $($ffmpeg.Source)" } else { 'FFmpeg: 未検出' }),
        $(if (Test-Path -LiteralPath $venvPython) { "アプリ環境: OK — $venvPython" } else { 'アプリ環境: 未作成' }),
        "tokens.json: $tokenState"
    )
    return ($lines -join [Environment]::NewLine)
}

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = @($machine, $user, $env:Path) -join ';'
}

function Normalize-LmStudioUrl {
    param([string]$Value)
    $raw = $Value.Trim()
    if (-not $raw) { return 'http://127.0.0.1:1234/v1' }
    try {
        $uri = [System.Uri]$raw
    } catch {
        throw 'LM Studio URLの形式が正しくありません。'
    }
    $path = $uri.AbsolutePath.TrimEnd('/')
    $parsedIp = $null
    $isIpAddress = [System.Net.IPAddress]::TryParse(
        $uri.Host.Trim(@([char]'[', [char]']')),
        [ref]$parsedIp
    )
    $isAllowedLoopback = $isIpAddress -and (
        [System.Net.IPAddress]::Loopback.Equals($parsedIp) -or
        [System.Net.IPAddress]::IPv6Loopback.Equals($parsedIp)
    )
    if (
        -not $uri.IsAbsoluteUri -or
        $uri.Scheme -notin @('http', 'https') -or
        -not $isAllowedLoopback -or
        $uri.IsDefaultPort -or
        $uri.Port -lt 1 -or
        $uri.Port -gt 65535 -or
        $uri.Query -or
        $uri.Fragment -or
        $path -notin @('', '/v1')
    ) {
        throw 'LM Studio URLは http://127.0.0.1:1234/v1 または http://[::1]:1234/v1 のように、このPCのループバックだけを指定してください。'
    }
    $authority = if ($parsedIp.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetworkV6) {
        '[::1]:{0}' -f $uri.Port
    } else {
        '127.0.0.1:{0}' -f $uri.Port
    }
    return ('{0}://{1}/v1' -f $uri.Scheme, $authority)
}

function New-WorkerProcess {
    param(
        [string]$Command,
        [hashtable]$Environment = @{}
    )
    $start = [System.Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $env:ComSpec
    $start.Arguments = "/d /c $Command"
    $start.WorkingDirectory = $script:Root
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($entry in $Environment.GetEnumerator()) {
        $start.EnvironmentVariables[$entry.Key] = [string]$entry.Value
    }
    return $start
}

function Start-BackgroundCommand {
    param(
        [string]$Title,
        [string]$Command,
        [hashtable]$Environment = @{}
    )
    if ($null -ne $script:ActiveProcess) {
        [System.Windows.Forms.MessageBox]::Show('別のセットアップ処理が実行中です。完了を待ってください。', 'セットアップ')
        return
    }
    $start = New-WorkerProcess -Command $Command -Environment $Environment
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $start
    $queue = [System.Collections.Concurrent.ConcurrentQueue[string]]::new()
    $onOutput = [System.Diagnostics.DataReceivedEventHandler]{
        param($source, $data)
        if ($null -ne $data.Data) { $queue.Enqueue($data.Data) }
    }
    $process.add_OutputDataReceived($onOutput)
    $process.add_ErrorDataReceived($onOutput)
    if (-not $process.Start()) { throw 'セットアップ処理を開始できませんでした。' }
    $script:ActiveProcess = $process
    $script:ActiveOutput = $queue
    $script:ActiveTitle = $Title
    $buttonCheck.Enabled = $false
    $buttonInstallPrerequisites.Enabled = $false
    $buttonInstallApp.Enabled = $false
    $buttonLaunch.Enabled = $false
    $setupLog.AppendText("`r`n--- $Title を開始 ---`r`n")
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()
    $script:ProcessPollTimer.Start()
}

$form = [System.Windows.Forms.Form]::new()
$form.Text = 'Gurumoji セットアップ'
$form.StartPosition = 'CenterScreen'
$form.MinimumSize = [System.Drawing.Size]::new(820, 700)
$form.Size = [System.Drawing.Size]::new(920, 820)
$form.Font = [System.Drawing.Font]::new('Yu Gothic UI', 9)

$rootPanel = [System.Windows.Forms.TableLayoutPanel]::new()
$rootPanel.Dock = 'Fill'
$rootPanel.AutoScroll = $true
$rootPanel.ColumnCount = 1
$rootPanel.Padding = [System.Windows.Forms.Padding]::new(18)
$form.Controls.Add($rootPanel)

$header = [System.Windows.Forms.Label]::new()
$header.Text = 'Gurumoji — はじめてのセットアップ'
$header.AutoSize = $true
$header.Font = [System.Drawing.Font]::new('Yu Gothic UI', 18, [System.Drawing.FontStyle]::Bold)
$rootPanel.Controls.Add($header)

$description = [System.Windows.Forms.Label]::new()
$description.Text = 'この画面だけで、必要なソフトの確認・アプリ環境の作成・tokens.json の設定を行えます。秘密鍵は画面上で伏せて表示し、ログには書き込みません。'
$description.AutoSize = $true
$description.MaximumSize = [System.Drawing.Size]::new(830, 0)
$description.Margin = [System.Windows.Forms.Padding]::new(3, 6, 3, 12)
$rootPanel.Controls.Add($description)

$environmentGroup = [System.Windows.Forms.GroupBox]::new()
$environmentGroup.Text = '1. 実行環境'
$environmentGroup.Dock = 'Top'
$environmentGroup.AutoSize = $false
$environmentGroup.Height = 155
$environmentGroup.Padding = [System.Windows.Forms.Padding]::new(12)
$rootPanel.Controls.Add($environmentGroup)

$statusBox = [System.Windows.Forms.TextBox]::new()
$statusBox.Location = [System.Drawing.Point]::new(12, 24)
$statusBox.Anchor = 'Top,Left,Right'
$statusBox.Size = [System.Drawing.Size]::new(850, 92)
$statusBox.Multiline = $true
$statusBox.ReadOnly = $true
$statusBox.BorderStyle = 'FixedSingle'
$statusBox.Height = 96
$statusBox.Text = Get-EnvironmentReport
$environmentGroup.Controls.Add($statusBox)

$environmentButtons = [System.Windows.Forms.FlowLayoutPanel]::new()
$environmentButtons.Location = [System.Drawing.Point]::new(12, 124)
$environmentButtons.AutoSize = $true
$environmentButtons.FlowDirection = 'LeftToRight'
$environmentButtons.Padding = [System.Windows.Forms.Padding]::new(0, 10, 0, 0)
$environmentGroup.Controls.Add($environmentButtons)

$buttonCheck = [System.Windows.Forms.Button]::new()
$buttonCheck.Text = '再チェック'
$buttonCheck.AutoSize = $true
$buttonCheck.add_Click({ $statusBox.Text = Get-EnvironmentReport })
$environmentButtons.Controls.Add($buttonCheck)

$buttonInstallPrerequisites = [System.Windows.Forms.Button]::new()
$buttonInstallPrerequisites.Text = 'Python と FFmpeg をインストール'
$buttonInstallPrerequisites.AutoSize = $true
$buttonInstallPrerequisites.add_Click({
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        [System.Windows.Forms.MessageBox]::Show('winget が見つかりません。Microsoft Store の「アプリ インストーラー」を更新するか、Python 3.12 と FFmpeg を手動で導入してください。', 'winget が必要です')
        return
    }
    $command = 'winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements && winget install --id Gyan.FFmpeg -e --source winget --accept-package-agreements --accept-source-agreements'
    Start-BackgroundCommand -Title 'Python と FFmpeg のインストール' -Command $command
})
$environmentButtons.Controls.Add($buttonInstallPrerequisites)

$openHuggingFace = [System.Windows.Forms.Button]::new()
$openHuggingFace.Text = 'Hugging Face の利用条件を開く'
$openHuggingFace.AutoSize = $true
$openHuggingFace.add_Click({
    Start-Process 'https://huggingface.co/pyannote/speaker-diarization-community-1'
    Start-Process 'https://huggingface.co/pyannote/segmentation-3.0'
})
$environmentButtons.Controls.Add($openHuggingFace)

$tokenGroup = [System.Windows.Forms.GroupBox]::new()
$tokenGroup.Text = '2. 認証・ローカルLLM設定（必要なものだけ）'
$tokenGroup.Dock = 'Top'
$tokenGroup.AutoSize = $false
$tokenGroup.Height = 350
$tokenGroup.Padding = [System.Windows.Forms.Padding]::new(12)
$tokenGroup.Margin = [System.Windows.Forms.Padding]::new(3, 16, 3, 3)
$rootPanel.Controls.Add($tokenGroup)

$tokenTable = [System.Windows.Forms.TableLayoutPanel]::new()
$tokenTable.Location = [System.Drawing.Point]::new(12, 24)
$tokenTable.Anchor = 'Top,Left,Right'
$tokenTable.AutoSize = $false
$tokenTable.Size = [System.Drawing.Size]::new(850, 190)
$tokenTable.ColumnCount = 2
$tokenTable.ColumnStyles.Add([System.Windows.Forms.ColumnStyle]::new([System.Windows.Forms.SizeType]::Absolute, 220))
$tokenTable.ColumnStyles.Add([System.Windows.Forms.ColumnStyle]::new([System.Windows.Forms.SizeType]::Percent, 100))
$tokenGroup.Controls.Add($tokenTable)

$settings = Get-JsonSettings
function Add-SettingRow {
    param([string]$Label, [string]$Value, [bool]$Secret = $false)
    $row = $tokenTable.RowCount
    $tokenTable.RowCount++
    $name = [System.Windows.Forms.Label]::new()
    $name.Text = $Label
    $name.AutoSize = $true
    $name.Anchor = 'Left'
    $input = [System.Windows.Forms.TextBox]::new()
    $input.Text = $Value
    $input.Dock = 'Fill'
    $input.Margin = [System.Windows.Forms.Padding]::new(4)
    if ($Secret) { $input.UseSystemPasswordChar = $true }
    $tokenTable.Controls.Add($name, 0, $row)
    $tokenTable.Controls.Add($input, 1, $row)
    return $input
}

$hfValue = Get-SettingText $settings 'huggingface_token'
if (-not $hfValue) { $hfValue = Get-SettingText $settings 'hf_token' }
$hfToken = Add-SettingRow 'Hugging Face token（必須）' $hfValue $true
$openAiKey = Add-SettingRow 'OpenAI API key（任意）' (Get-SettingText $settings 'openai_api_key') $true
$googleKey = Add-SettingRow 'Google Gemini API key（任意）' (Get-SettingText $settings 'google_api_key') $true
$lmStudioUrl = Add-SettingRow 'LM Studio URL' (Get-SettingText $settings 'lmstudio_base_url' 'http://127.0.0.1:1234/v1') $false
$lmStudioModel = Add-SettingRow 'LM Studio model（空欄でも可）' (Get-SettingText $settings 'lmstudio_model') $false
$lmStudioKey = Add-SettingRow 'LM Studio API key（認証時のみ）' (Get-SettingText $settings 'lmstudio_api_key') $true

$tokenHelp = [System.Windows.Forms.Label]::new()
$tokenHelp.Text = 'Hugging Face は pyannote の利用条件に同意後の read token が必要です。LM Studio は既定のまま Developer → Start server を有効にし、モデルはアプリ画面上部の LM Studio ライトから選べます。'
$tokenHelp.AutoSize = $true
$tokenHelp.MaximumSize = [System.Drawing.Size]::new(820, 0)
$tokenHelp.Margin = [System.Windows.Forms.Padding]::new(3, 10, 3, 3)
$tokenHelp.Location = [System.Drawing.Point]::new(12, 225)
$tokenGroup.Controls.Add($tokenHelp)

$buttonSave = [System.Windows.Forms.Button]::new()
$buttonSave.Text = '設定を保存'
$buttonSave.AutoSize = $true
$buttonSave.Margin = [System.Windows.Forms.Padding]::new(3, 10, 3, 3)
$buttonSave.Location = [System.Drawing.Point]::new(12, 292)
$buttonSave.add_Click({
    try {
        $next = Get-JsonSettings
        Set-SettingValue $next 'huggingface_token' $hfToken.Text
        Set-SettingValue $next 'openai_api_key' $openAiKey.Text
        Set-SettingValue $next 'google_api_key' $googleKey.Text
        Set-SettingValue $next 'lmstudio_base_url' (Normalize-LmStudioUrl $lmStudioUrl.Text)
        Set-SettingValue $next 'lmstudio_model' $lmStudioModel.Text
        Set-SettingValue $next 'lmstudio_api_key' $lmStudioKey.Text
        Save-JsonSettings $next
        $statusBox.Text = Get-EnvironmentReport
        [System.Windows.Forms.MessageBox]::Show('tokens.json に保存しました。', 'セットアップ')
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, '保存できません')
    }
})
$tokenGroup.Controls.Add($buttonSave)

$applicationGroup = [System.Windows.Forms.GroupBox]::new()
$applicationGroup.Text = '3. アプリ環境を作成して起動'
$applicationGroup.Dock = 'Top'
$applicationGroup.AutoSize = $false
$applicationGroup.Height = 145
$applicationGroup.Padding = [System.Windows.Forms.Padding]::new(12)
$applicationGroup.Margin = [System.Windows.Forms.Padding]::new(3, 16, 3, 3)
$rootPanel.Controls.Add($applicationGroup)

$applicationHelp = [System.Windows.Forms.Label]::new()
$applicationHelp.Text = '「アプリ環境を作成」は、このフォルダー内に .venv を作り、必要なPythonパッケージを導入します。初回は大きなダウンロードがあります。Python/FFmpegを今インストールした場合は、この画面を一度閉じて開き直してください。'
$applicationHelp.AutoSize = $true
$applicationHelp.MaximumSize = [System.Drawing.Size]::new(820, 0)
$applicationHelp.Location = [System.Drawing.Point]::new(12, 24)
$applicationGroup.Controls.Add($applicationHelp)

$applicationButtons = [System.Windows.Forms.FlowLayoutPanel]::new()
$applicationButtons.Location = [System.Drawing.Point]::new(12, 88)
$applicationButtons.AutoSize = $true
$applicationButtons.FlowDirection = 'LeftToRight'
$applicationButtons.Padding = [System.Windows.Forms.Padding]::new(0, 10, 0, 0)
$applicationGroup.Controls.Add($applicationButtons)

$buttonInstallApp = [System.Windows.Forms.Button]::new()
$buttonInstallApp.Text = 'アプリ環境を作成'
$buttonInstallApp.AutoSize = $true
$buttonInstallApp.add_Click({
    try {
        if (-not (Test-Path -LiteralPath $script:RunBatch)) { throw 'run.bat が見つかりません。' }
        $next = Get-JsonSettings
        Set-SettingValue $next 'huggingface_token' $hfToken.Text
        Set-SettingValue $next 'openai_api_key' $openAiKey.Text
        Set-SettingValue $next 'google_api_key' $googleKey.Text
        Set-SettingValue $next 'lmstudio_base_url' (Normalize-LmStudioUrl $lmStudioUrl.Text)
        Set-SettingValue $next 'lmstudio_model' $lmStudioModel.Text
        Set-SettingValue $next 'lmstudio_api_key' $lmStudioKey.Text
        Save-JsonSettings $next
        $environment = @{
            MOJIOKOSI_LAUNCH_WORKER = '1'
            MOJIOKOSI_NO_PAUSE = '1'
            MOJIOKOSI_SKIP_UPDATE_CHECK = '1'
            MOJIOKOSI_SETUP_ONLY = '1'
        }
        Start-BackgroundCommand -Title 'アプリ環境の作成' -Command ('call "{0}"' -f $script:RunBatch) -Environment $environment
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'セットアップを開始できません')
    }
})
$applicationButtons.Controls.Add($buttonInstallApp)

$buttonLaunch = [System.Windows.Forms.Button]::new()
$buttonLaunch.Text = 'Gurumoji を起動'
$buttonLaunch.AutoSize = $true
$buttonLaunch.add_Click({
    try {
        if (-not (Test-Path -LiteralPath $script:RunBatch)) { throw 'run.bat が見つかりません。' }
        $next = Get-JsonSettings
        Set-SettingValue $next 'huggingface_token' $hfToken.Text
        Set-SettingValue $next 'openai_api_key' $openAiKey.Text
        Set-SettingValue $next 'google_api_key' $googleKey.Text
        Set-SettingValue $next 'lmstudio_base_url' (Normalize-LmStudioUrl $lmStudioUrl.Text)
        Set-SettingValue $next 'lmstudio_model' $lmStudioModel.Text
        Set-SettingValue $next 'lmstudio_api_key' $lmStudioKey.Text
        Save-JsonSettings $next
        Start-Process -FilePath $env:ComSpec -WorkingDirectory $script:Root -ArgumentList @('/d', '/k', ('call "{0}"' -f $script:RunBatch))
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, '起動できません')
    }
})
$applicationButtons.Controls.Add($buttonLaunch)

$logGroup = [System.Windows.Forms.GroupBox]::new()
$logGroup.Text = 'セットアップログ（秘密鍵は表示しません）'
$logGroup.Dock = 'Top'
$logGroup.Height = 210
$logGroup.Padding = [System.Windows.Forms.Padding]::new(10)
$logGroup.Margin = [System.Windows.Forms.Padding]::new(3, 16, 3, 3)
$rootPanel.Controls.Add($logGroup)

$setupLog = [System.Windows.Forms.TextBox]::new()
$setupLog.Dock = 'Fill'
$setupLog.Multiline = $true
$setupLog.ReadOnly = $true
$setupLog.ScrollBars = 'Both'
$setupLog.WordWrap = $false
$setupLog.Font = [System.Drawing.Font]::new('Consolas', 9)
$logGroup.Controls.Add($setupLog)

$script:ProcessPollTimer = [System.Windows.Forms.Timer]::new()
$script:ProcessPollTimer.Interval = 120
$script:ProcessPollTimer.add_Tick({
    if ($null -eq $script:ActiveProcess -or $null -eq $script:ActiveOutput) {
        $script:ProcessPollTimer.Stop()
        return
    }
    $line = ''
    while ($script:ActiveOutput.TryDequeue([ref]$line)) {
        $setupLog.AppendText($line + [Environment]::NewLine)
    }
    $setupLog.SelectionStart = $setupLog.TextLength
    $setupLog.ScrollToCaret()
    if (-not $script:ActiveProcess.HasExited) { return }
    $script:ActiveProcess.WaitForExit()
    while ($script:ActiveOutput.TryDequeue([ref]$line)) {
        $setupLog.AppendText($line + [Environment]::NewLine)
    }
    $exitCode = $script:ActiveProcess.ExitCode
    $title = $script:ActiveTitle
    $script:ActiveProcess.Dispose()
    $script:ActiveProcess = $null
    $script:ActiveOutput = $null
    $script:ActiveTitle = ''
    $script:ProcessPollTimer.Stop()
    $buttonCheck.Enabled = $true
    $buttonInstallPrerequisites.Enabled = $true
    $buttonInstallApp.Enabled = $true
    $buttonLaunch.Enabled = $true
    $setupLog.AppendText("`r`n$title が終了しました（終了コード: $exitCode）。`r`n")
    Refresh-ProcessPath
    $statusBox.Text = Get-EnvironmentReport
    if ($exitCode -eq 0) {
        [System.Windows.Forms.MessageBox]::Show("$title が完了しました。", 'セットアップ')
    } else {
        [System.Windows.Forms.MessageBox]::Show('ログを確認し、表示されたエラーを解消してから再実行してください。', 'セットアップ')
    }
})

[void]$form.ShowDialog()
