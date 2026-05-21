<#
.SYNOPSIS
  Repository-local bridge for asking Claude Code to read, create, or edit files.

.DESCRIPTION
  This script is meant to be reused from any Codex window opened on this
  repository. It invokes the local `claude` CLI with a repository-scoped
  workflow:

  - Read mode: read/search/list the working directory.
  - Write mode: create or edit files under the working directory.
  - Review mode: inspect repository changes and report risks.

  The script does not bypass Codex or Claude Code approval systems. It gives
  Claude Code a repository-scoped prompt and tool list, then prints changed
  files so Codex can review the resulting diff.

.EXAMPLES
  .\codex-claude-docs.ps1 -Mode Read -Prompt "Summarize the repository structure."

  .\codex-claude-docs.ps1 -Mode Write -Prompt "Implement the requested code change and update tests."

  .\codex-claude-docs.ps1 -Mode Review -Prompt "Review the current diff for correctness."

  .\codex-claude-docs.ps1 -Mode Write -PromptFile .\claude-task.md
#>

[CmdletBinding()]
param(
  [ValidateSet("Read", "Write", "Review")]
  [string]$Mode = "Read",

  [string]$Prompt,

  [string]$PromptFile,

  [string[]]$ExtraReadDir = @(),

  [switch]$Interactive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepoDir {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PathValue,

    [Parameter(Mandatory = $true)]
    [string]$RepoRoot
  )

  $candidate = if ([System.IO.Path]::IsPathRooted($PathValue)) {
    $PathValue
  } else {
    Join-Path $RepoRoot $PathValue
  }

  if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
    throw "Directory does not exist: $PathValue"
  }

  $resolvedRoot = (Resolve-Path -LiteralPath $RepoRoot).Path.TrimEnd("\", "/")
  $resolvedPath = (Resolve-Path -LiteralPath $candidate).Path.TrimEnd("\", "/")
  $rootWithSeparator = $resolvedRoot + [System.IO.Path]::DirectorySeparatorChar

  if (
    $resolvedPath -ne $resolvedRoot -and
    -not $resolvedPath.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)
  ) {
    throw "Refusing directory outside repository: $resolvedPath"
  }

  return $resolvedPath
}

function Get-TaskText {
  param(
    [string]$InlinePrompt,
    [string]$FilePath,
    [string]$RepoRoot
  )

  if ([string]::IsNullOrWhiteSpace($InlinePrompt) -and [string]::IsNullOrWhiteSpace($FilePath)) {
    throw "Provide -Prompt or -PromptFile."
  }

  if (-not [string]::IsNullOrWhiteSpace($InlinePrompt) -and -not [string]::IsNullOrWhiteSpace($FilePath)) {
    throw "Use either -Prompt or -PromptFile, not both."
  }

  if (-not [string]::IsNullOrWhiteSpace($InlinePrompt)) {
    return $InlinePrompt
  }

  $candidate = if ([System.IO.Path]::IsPathRooted($FilePath)) {
    $FilePath
  } else {
    Join-Path $RepoRoot $FilePath
  }

  if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
    throw "Prompt file does not exist: $FilePath"
  }

  return Get-Content -LiteralPath $candidate -Raw
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$bridgeDir = Join-Path $repoRoot ".codex_claude_bridge"

$claudeCommand = Get-Command claude -ErrorAction SilentlyContinue
if ($null -eq $claudeCommand) {
  throw "The `claude` command was not found on PATH."
}

$allowedDirs = New-Object System.Collections.Generic.List[string]
$allowedDirs.Add((Resolve-RepoDir -PathValue "." -RepoRoot $repoRoot))

foreach ($extra in $ExtraReadDir) {
  $extraResolved = Resolve-RepoDir -PathValue $extra -RepoRoot $repoRoot
  if (-not $allowedDirs.Contains($extraResolved)) {
    $allowedDirs.Add($extraResolved)
  }
}

$userTask = Get-TaskText -InlinePrompt $Prompt -FilePath $PromptFile -RepoRoot $repoRoot

if (-not (Test-Path -LiteralPath $bridgeDir -PathType Container)) {
  New-Item -ItemType Directory -Path $bridgeDir | Out-Null
}

$writePolicy = if ($Mode -eq "Write") {
  "You may create or edit files under the repository working directory."
} else {
  "Do not create, edit, delete, or move files."
}

$systemTask = @"
You are Claude Code being invoked from Codex through codex-claude-docs.ps1.

Repository root: $repoRoot
Mode: $Mode

Scope:
- You may read files under the repository working directory.
- $writePolicy
- Do not edit files outside the repository working directory.
- Do not edit git metadata.
- Do not run package installs, network downloads, git write operations, deletes, resets, or cleanup commands unless the user explicitly requested them.
- If the request needs broader access, stop and explain the exact path and reason.
- Keep the final response concise. Include files changed, files read, and any assumptions.

User task:
$userTask
"@

$tools = switch ($Mode) {
  "Read" { "Read,Glob,Grep,LS" }
  "Review" { "Read,Glob,Grep,LS" }
  "Write" { "Read,Write,Edit,MultiEdit,Glob,Grep,LS" }
}

$permissionMode = if ($Mode -eq "Write") { "acceptEdits" } else { "default" }
$runDir = if ($Mode -eq "Write") { $repoRoot } else { $bridgeDir }

$claudeArgs = @()
if (-not $Interactive) {
  $claudeArgs += "--print"
  $claudeArgs += "--output-format"
  $claudeArgs += "text"
}

$claudeArgs += "--permission-mode"
$claudeArgs += $permissionMode
$claudeArgs += "--tools"
$claudeArgs += $tools

if ($allowedDirs.Count -gt 0) {
  $claudeArgs += "--add-dir"
  foreach ($allowedDir in $allowedDirs) {
    $claudeArgs += $allowedDir
  }
}

$claudeArgs += "--"
$claudeArgs += $systemTask

Push-Location $runDir
try {
  & claude @claudeArgs
  $exitCode = $LASTEXITCODE
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "Codex review checkpoint"
Write-Host "Repository: $repoRoot"
Write-Host "Mode: $Mode"
Write-Host "Claude exit code: $exitCode"

if (Get-Command git -ErrorAction SilentlyContinue) {
  $changedFiles = git -C $repoRoot status --porcelain
  if ($changedFiles) {
    Write-Host ""
    Write-Host "Changed files:"
    $changedFiles | ForEach-Object { Write-Host "  $_" }

    $outsideRepo = @(
      $changedFiles |
        ForEach-Object { $_.Substring(3).Replace("\", "/") } |
        Where-Object { $_ -like "../*" -or $_ -match "^[A-Za-z]:/" }
    )

    if ($outsideRepo.Count -gt 0) {
      Write-Warning "Changes outside the repository are present. Review before keeping them."
      $outsideRepo | ForEach-Object { Write-Warning "Outside repository: $_" }
    }
  } else {
    Write-Host "No git-tracked changes detected."
  }
}

exit $exitCode
