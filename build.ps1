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

# Read the official app version ("version" in package.json inside app.asar) -
# the same number the app reports at runtime. Best effort: failure to read it
# never blocks the install.
function Read-AppVersionFromAsar {
    param([string]$AsarPath)
    $fs = [IO.File]::OpenRead($AsarPath)
    try {
        $br = New-Object IO.BinaryReader($fs)
        [void]$br.ReadBytes(4)             # pickle framing
        $headerTotal = $br.ReadUInt32()    # asar header total size
        [void]$br.ReadUInt32()             # header payload size
        $jsonLen = $br.ReadUInt32()        # JSON index length
        # Parse the full index and take the TOP-LEVEL package.json entry
        # (subdirectory files share the name but are not the app manifest).
        # PS 5.1's built-in ConvertFrom-Json caps input at 2 MB; this index
        # is ~4 MB, so use JavaScriptSerializer with the limit lifted.
        Add-Type -AssemblyName System.Web.Extensions | Out-Null
        $ser = New-Object Web.Script.Serialization.JavaScriptSerializer
        $ser.MaxJsonLength = [int]::MaxValue
        $index = $ser.DeserializeObject([Text.Encoding]::UTF8.GetString($br.ReadBytes([int]$jsonLen)))
        $entry = $index['files']['package.json']
        if (-not $entry) { return $null }
        $fs.Position = 8 + $headerTotal + [int64]$entry['offset']
        $pkg = $ser.DeserializeObject([Text.Encoding]::UTF8.GetString($br.ReadBytes([int]$entry['size'])))
        return $pkg['version']
    }
    finally { $fs.Dispose() }
}

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

$appVersion = $null
try { $appVersion = Read-AppVersionFromAsar (Join-Path $tmp 'app\resources\app.asar') } catch { $appVersion = $null }
if ($appVersion) {
    Write-Host "      Official app version: $appVersion"
}
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
