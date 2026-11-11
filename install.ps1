# mama installer for Windows. Paste into PowerShell:
#
#   irm https://raw.githubusercontent.com/ringku1/claude-mama/main/install.ps1 | iex
#
# It installs what's missing (Git for Windows, Python 3.8+) with winget, downloads mama to
# %USERPROFILE%\.claude\skills\mama (%CLAUDE_CONFIG_DIR%\skills\mama when that is set), and registers its hooks with Claude Code.
# Run the same line again to update.
# Remove:  $env:MAMA_UNINSTALL=1; irm https://raw.githubusercontent.com/ringku1/claude-mama/main/install.ps1 | iex
$ErrorActionPreference = 'Stop'

$Repo = if ($env:MAMA_REPO) { $env:MAMA_REPO } else { 'https://github.com/ringku1/claude-mama.git' }
$ClaudeDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE '.claude' }
$Dest = Join-Path $ClaudeDir 'skills\mama'
$env:GIT_TERMINAL_PROMPT = '0'  # a bad URL fails instead of asking for a password

function Say($msg) { Write-Host "mama: $msg" }
function Fail($msg) { throw "mama: $msg" }  # throw, not exit: exit would close the window under `irm | iex`

# Windows PowerShell 5.1 turns a native command's stderr into a terminating error under 'Stop';
# run git / python with 'Continue' so a failure reaches our own message, not a raw error record.
function Quiet([scriptblock]$Block) {
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { (& $Block 2>&1 | Out-String) } finally { $ErrorActionPreference = $old }
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Find-Python {
    # the py launcher first; `python` may be the Microsoft Store stub, which only opens the Store
    foreach ($cmd in @(@('py', '-3'), @('python'), @('python3'))) {
        if (-not (Get-Command $cmd[0] -ErrorAction SilentlyContinue)) { continue }
        $rest = @($cmd | Select-Object -Skip 1)
        try {
            $exe = & $cmd[0] @rest -c 'import sys; assert sys.version_info >= (3, 8); print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) { return ($exe | Select-Object -Last 1).Trim() }
        } catch { }
    }
    return $null
}

function Has-Git { [bool](Get-Command git -ErrorAction SilentlyContinue) }

function Install-Package($id, $name) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail "please install $name (https://www.python.org/downloads/ or https://git-scm.com/download/win), then paste the same command again."
    }
    Say "installing $name"
    winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
    Refresh-Path
}

if ($env:MAMA_UNINSTALL) {
    $py = Find-Python
    if (Test-Path $Dest) {
        if ($py) { Quiet { & $py (Join-Path $Dest 'install.py') --remove } | Out-Null }
        Remove-Item -Recurse -Force $Dest
    }
    Remove-Item Env:MAMA_UNINSTALL
    Say 'removed. Your goal notes in each project (.claude\mama) and ~\.claude\mama are kept.'
    return
}

if (-not (Has-Git)) { Install-Package 'Git.Git' 'Git for Windows' }
if (-not (Has-Git)) { Fail 'git still is not available - open a new PowerShell window and paste the same command again.' }
$py = Find-Python
if (-not $py) { Install-Package 'Python.Python.3.12' 'Python 3'; $py = Find-Python }
if (-not $py) { Fail 'Python still is not available - open a new PowerShell window and paste the same command again.' }

New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
if (Test-Path (Join-Path $Dest '.git')) {
    Say 'updating'
    $changed = Quiet { git -C $Dest status --porcelain }
    if ($LASTEXITCODE -eq 0 -and $changed.Trim()) { Fail "files in $Dest were changed locally, so it wasn't updated. Run  git -C `"$Dest`" stash  (or remove the folder), then paste the command again." }
    Quiet { git -C $Dest fetch -q } | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "couldn't reach the mama repository - check your internet connection and paste the command again." }
    Quiet { git -C $Dest merge -q --ff-only '@{upstream}' } | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "$Dest has local commits (or is off its branch), so it wasn't updated. Remove the folder (or reset it), then paste the command again." }
} else {
    if (Test-Path $Dest) {
        $old = "$Dest.old-$(Get-Date -Format yyyyMMddHHmmss)"
        Move-Item $Dest $old
        Say "moved the previous $Dest to $old"
    }
    Say 'downloading'
    $err = Quiet { git clone -q $Repo $Dest }
    if ($LASTEXITCODE -ne 0) {
        if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
        if ($err -match 'not found|does not exist|Authentication') { Fail "couldn't download $Repo - it doesn't exist or isn't public." }
        Fail "couldn't download $Repo - check your internet connection and paste the command again."
    }
}

$out = Quiet { & $py (Join-Path $Dest 'install.py') }
if ($LASTEXITCODE -ne 0) {
    $last = (($out.Trim() -split "`r?`n") | Select-Object -Last 1) -replace '^mama: ', ''
    Fail "registering the hooks failed: $last"
}
Say 'ready. Restart Claude Code, open your project, and type:  /mama <what you want done>'
