param(
    [int]$Count = 3,
    [string]$EnvFile = ".env.stress.local.ps1",
    [string]$InputFile = "postppt.json",
    [string]$ProjectNameBase = "postppt_qwen36plus_12w_b3_max",
    [string]$LogDir = ".tmp/ppt-stress",
    [switch]$NoWait
)

$ErrorActionPreference = "Stop"

function Resolve-RepoPath {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return (Resolve-Path $Path).Path
    }
    return (Resolve-Path (Join-Path $script:RepoRoot $Path)).Path
}

function Assert-Secret {
    param([string]$Name)
    $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($value) -or $value -match "^<.*>$" -or $value -match "your-.*key") {
        throw "Missing real value for $Name. Edit $EnvFile first or set it in the current shell."
    }
}

$script:RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $script:RepoRoot

$envPath = if ([System.IO.Path]::IsPathRooted($EnvFile)) {
    $EnvFile
} else {
    Join-Path $script:RepoRoot $EnvFile
}

if (-not (Test-Path $envPath)) {
    throw "Environment file not found: $envPath"
}

. $envPath
$env:PYTHONIOENCODING = if ($env:PYTHONIOENCODING) { $env:PYTHONIOENCODING } else { "utf-8" }

Assert-Secret "DEEPSEEK_API_KEY"
Assert-Secret "DASHSCOPE_API_KEY"

$inputPath = Resolve-RepoPath $InputFile
$python = (Get-Command python -ErrorAction Stop).Source
$claude = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claude) {
    throw "Claude Code CLI was not found in PATH. Install/login to claude before running the live stress test."
}

$logRoot = if ([System.IO.Path]::IsPathRooted($LogDir)) {
    $LogDir
} else {
    Join-Path $script:RepoRoot $LogDir
}
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$runDir = Join-Path (Resolve-Path $logRoot).Path $timestamp
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

Write-Host "Stress run directory: $runDir"
Write-Host "Launching $Count concurrent PPT generation jobs..."

$jobs = @()
for ($i = 1; $i -le $Count; $i++) {
    $suffix = "{0:D2}" -f $i
    $projectName = "${ProjectNameBase}_stress${suffix}"
    $stdout = Join-Path $runDir "stress${suffix}.out.log"
    $stderr = Join-Path $runDir "stress${suffix}.err.log"

    $arguments = @(
        "skills/ppt-master/scripts/api_ppt.py",
        "generate",
        $inputPath,
        "--project-name", $projectName,
        "--renderer", "claude",
        "--planner-provider", "qwen",
        "--notes-provider", "qwen",
        "--qwen-model", "qwen3.6-plus",
        "--qwen-max-tokens", "65536",
        "--cache-prime",
        "--svg-workers", "12",
        "--svg-batch-size", "3",
        "--claude-effort", "max",
        "--claude-timeout", "1200",
        "--claude-retries", "1"
    )

    $process = Start-Process `
        -FilePath $python `
        -ArgumentList $arguments `
        -WorkingDirectory $script:RepoRoot `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru `
        -WindowStyle Hidden

    $jobs += [pscustomobject]@{
        Index = $i
        ProjectName = $projectName
        Pid = $process.Id
        Process = $process
        Stdout = $stdout
        Stderr = $stderr
        StartedAt = Get-Date
    }
}

$jobs | Select-Object Index, ProjectName, Pid, Stdout, Stderr | Format-Table -AutoSize

if ($NoWait) {
    Write-Host "Jobs are running in the background. Inspect logs in $runDir"
    return
}

while ($true) {
    $running = 0
    foreach ($job in $jobs) {
        $job.Process.Refresh()
        if (-not $job.Process.HasExited) {
            $running++
        }
    }

    $now = Get-Date
    $status = foreach ($job in $jobs) {
        $job.Process.Refresh()
        $elapsed = [int]($now - $job.StartedAt).TotalSeconds
        [pscustomobject]@{
            Index = $job.Index
            Pid = $job.Pid
            State = if ($job.Process.HasExited) { "done:$($job.Process.ExitCode)" } else { "running" }
            ElapsedSeconds = $elapsed
            ProjectName = $job.ProjectName
        }
    }
    $status | Format-Table -AutoSize

    if ($running -eq 0) {
        break
    }
    Start-Sleep -Seconds 30
}

Write-Host "Completed. Summarizing projects and rate-limit signals..."

$summary = foreach ($job in $jobs) {
    $projectDir = Get-ChildItem -Path (Join-Path $script:RepoRoot "projects") -Directory -Filter "$($job.ProjectName)_ppt169_*" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    $resultPath = if ($projectDir) { Join-Path $projectDir.FullName "result.json" } else { $null }
    $usagePath = if ($projectDir) { Join-Path $projectDir.FullName "logs/usage.jsonl" } else { $null }

    $ok = $null
    $slides = $null
    $warnings = $null
    if ($resultPath -and (Test-Path $resultPath)) {
        $result = Get-Content $resultPath -Raw | ConvertFrom-Json
        $ok = $result.ok
        $slides = $result.slides
        $warnings = $result.quality_warnings
    }

    $svgCount = 0
    $retryCount = 0
    $failureCount = 0
    if ($usagePath -and (Test-Path $usagePath)) {
        $usage = Get-Content $usagePath | ForEach-Object {
            try { $_ | ConvertFrom-Json } catch { $null }
        }
        $svgUsage = @($usage | Where-Object { $_ -and $_.label -eq "claude_svg" })
        $svgCount = $svgUsage.Count
        $retryCount = @($svgUsage | Where-Object { $_.retrying -eq $true }).Count
        $failureCount = @($svgUsage | Where-Object { $_.failure -eq 1 -or $_.ok -eq $false }).Count
    }

    [pscustomobject]@{
        Index = $job.Index
        ExitCode = $job.Process.ExitCode
        Ok = $ok
        Slides = $slides
        QualityWarnings = $warnings
        ClaudeSvgEntries = $svgCount
        Retries = $retryCount
        Failures = $failureCount
        ProjectDir = if ($projectDir) { $projectDir.FullName } else { "<missing>" }
    }
}

$summary | Format-Table -AutoSize

$scanFiles = @()
$scanFiles += Get-ChildItem -Path $runDir -File -Filter "*.log" -ErrorAction SilentlyContinue
foreach ($job in $jobs) {
    $projectDirs = Get-ChildItem -Path (Join-Path $script:RepoRoot "projects") -Directory -Filter "$($job.ProjectName)_ppt169_*" -ErrorAction SilentlyContinue
    foreach ($projectDir in $projectDirs) {
        $scanFiles += Get-ChildItem -Path (Join-Path $projectDir.FullName "logs") -File -Recurse -ErrorAction SilentlyContinue
    }
}

$rateLimitMatches = $scanFiles |
    Select-String -Pattern "429|rate limit|too many requests|throttl|quota|RateLimit" -CaseSensitive:$false -ErrorAction SilentlyContinue

if ($rateLimitMatches) {
    Write-Host "Potential rate-limit signals:"
    $rateLimitMatches | Select-Object Path, LineNumber, Line | Format-Table -Wrap
} else {
    Write-Host "No obvious rate-limit strings found in run logs."
}
