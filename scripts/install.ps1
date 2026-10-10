# Usage: powershell -ExecutionPolicy Bypass -File scripts/install.ps1 [-Source PATH_OR_URL]
[CmdletBinding()]
param(
    [string]$Source = ''
)

$ErrorActionPreference = 'Stop'
if (-not $Source) {
    $Source = 'git+https://github.com/Kingsmai/lazy-commit.git'
    if ($PSScriptRoot) {
        $checkout = Split-Path -Parent $PSScriptRoot
        if (Test-Path (Join-Path $checkout 'pyproject.toml')) { $Source = $checkout }
    }
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git is required. Install Git for Windows and run this installer again.'
}

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) {
    $uvBin = $uvCommand.Source
} else {
    $uvDir = if ($env:UV_INSTALL_DIR) { $env:UV_INSTALL_DIR } else { Join-Path $HOME '.local\bin' }
    $uvBin = Join-Path $uvDir 'uv.exe'
    if (-not (Test-Path $uvBin)) {
        $bootstrap = Join-Path ([IO.Path]::GetTempPath()) ([IO.Path]::GetRandomFileName() + '.ps1')
        $previousInstallDir = $env:UV_INSTALL_DIR
        try {
            $env:UV_INSTALL_DIR = $uvDir
            Invoke-WebRequest -UseBasicParsing 'https://astral.sh/uv/install.ps1' -OutFile $bootstrap
            & powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrap
            if ($LASTEXITCODE -ne 0) { throw 'uv installation failed.' }
        } finally {
            $env:UV_INSTALL_DIR = $previousInstallDir
            Remove-Item $bootstrap -ErrorAction SilentlyContinue
        }
    }
}

& $uvBin tool install --python 3.13 --upgrade --reinstall-package lazy-commit $Source
if ($LASTEXITCODE -ne 0) { throw 'lazy-commit installation failed.' }
& $uvBin tool update-shell
if ($LASTEXITCODE -ne 0) { throw 'Could not update PATH.' }
$binDir = & $uvBin tool dir --bin
if ($LASTEXITCODE -ne 0) { throw 'Could not locate the executable directory.' }
& (Join-Path $binDir 'lazy-commit.exe') --version
if ($LASTEXITCODE -ne 0) { throw 'Installation verification failed.' }
Write-Host 'Installed. Open a new terminal and run: lazy-commit --help'
