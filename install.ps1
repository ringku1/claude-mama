# mama installer for Windows. Paste into PowerShell:
#
#   irm https://raw.githubusercontent.com/ringku1/claude-mama/main/install.ps1 | iex
#
# It installs what's missing (Git for Windows, Python 3.8+) with winget, downloads mama to
# %USERPROFILE%\.claude\skills\mama, and registers its hooks with Claude Code.
# Run the same line again to update.
# Remove:  $env:MAMA_UNINSTALL=1; irm https://raw.githubusercontent.com/ringku1/claude-mama/main/install.ps1 | iex
$ErrorActionPreference = 'Stop'

$Repo = if ($env:MAMA_REPO) { $env:MAMA_REPO } else { 'https://github.com/ringku1/claude-mama.git' }
$Dest = Join-Path $env:USERPROFILE '.claude\skills\mama'

function Say($msg) { Write-Host "mama: $msg" }
function Fail($msg) { throw "mama: $msg" }  # throw, not exit: exit would close the window under `irm | iex`

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
        if ($py) { & $py (Join-Path $Dest 'install.py') --remove | Out-Null }
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
    git -C $Dest pull --ff-only -q
    if ($LASTEXITCODE -ne 0) { Fail "couldn't update $Dest (local changes?). Remove it and paste the command again." }
} else {
    if (Test-Path $Dest) {
        $old = "$Dest.old-$(Get-Date -Format yyyyMMddHHmmss)"
        Move-Item $Dest $old
        Say "moved the previous $Dest to $old"
    }
    Say 'downloading'
    git clone -q $Repo $Dest
    if ($LASTEXITCODE -ne 0) { Fail 'download failed - check your internet connection and paste the command again.' }
}

& $py (Join-Path $Dest 'install.py') | Out-Null
if ($LASTEXITCODE -ne 0) { Fail ('registering the hooks failed - run: py "' + (Join-Path $Dest 'install.py') + '"') }
Say 'ready. Restart Claude Code, open your project, and type:  /mama <what you want done>'
