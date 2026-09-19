# One-shot setup for the ChatGPT (Codex) desktop app on older Windows 10 builds.
# Compatible with Windows PowerShell 5.1 on Windows 10 1809 (LTSC 2019).
# Usage:
#   .\build.ps1                      # x64 -> %USERPROFILE%\Apps\ChatGPT-Codex + desktop shortcut
#   .\build.ps1 -Arch arm64
#   .\build.ps1 -Destination E:\Apps\ChatGPT-Codex
param(
    [ValidateSet('x64', 'arm64')]
    [string]$Arch = 'x64',
    [string]$Destination = (Join-Path $env:USERPROFILE 'Apps\ChatGPT-Codex'),
    [switch]$NoShortcut
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$url = "https://persistent.oaistatic.com/codex-app-prod/ChatGPT-$Arch.msix"
$tmp = Join-Path $env:TEMP ("codex-msix-" + [guid]::NewGuid().ToString('N').Substring(0, 8))

New-Item -ItemType Directory -Force $tmp | Out-Null
$msix = Join-Path $tmp "ChatGPT-$Arch.msix"

Write-Host "[1/4] Downloading $url"
curl.exe -sL -o $msix $url
if ($LASTEXITCODE -ne 0) { throw "Download failed (curl exit $LASTEXITCODE)" }
Write-Host ("      {0:N0} MB downloaded" -f ((Get-Item $msix).Length / 1MB))

Write-Host "[2/4] Extracting (MSIX is a signed ZIP container)"
& "$env:SystemRoot\System32\tar.exe" -xf $msix -C $tmp
if ($LASTEXITCODE -ne 0) { throw "Extraction failed" }

Write-Host "[3/4] Installing to $Destination"
New-Item -ItemType Directory -Force $Destination | Out-Null
Copy-Item (Join-Path $tmp 'app\*') $Destination -Recurse -Force
Remove-Item $tmp -Recurse -Force

if (-not $NoShortcut) {
    Write-Host "[4/4] Creating desktop shortcut"
    $ws = New-Object -ComObject WScript.Shell
    $lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'ChatGPT (Codex).lnk'))
    $lnk.TargetPath = Join-Path $Destination 'ChatGPT.exe'
    $lnk.WorkingDirectory = $Destination
    $lnk.IconLocation = (Join-Path $Destination 'ChatGPT.exe') + ',0'
    $lnk.Save()
}
else {
    Write-Host "[4/4] Skipped shortcut (-NoShortcut)"
}

Write-Host "Done. Launch: $(Join-Path $Destination 'ChatGPT.exe')"
