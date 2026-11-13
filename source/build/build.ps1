$ErrorActionPreference = "Stop"

$buildRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceRoot = Split-Path -Parent $buildRoot
$appRoot = Split-Path -Parent $sourceRoot
$python = Join-Path $sourceRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "未找到虚拟环境：$python" -ForegroundColor Red
    exit 1
}

$assets = Join-Path $sourceRoot "src\magdsh\assets"

$pyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", "MagDsh",
    "--icon", (Join-Path $assets "MagDsh.ico"),
    "--add-data", ("{0};magdsh/assets" -f (Join-Path $assets "logo.png")),
    "--add-data", ("{0};magdsh/assets" -f (Join-Path $assets "MagDsh.ico")),
    "--paths", (Join-Path $sourceRoot "src"),
    "--distpath", $buildRoot,
    "--workpath", (Join-Path $env:TEMP "MagDshPyInstaller\build"),
    "--specpath", (Join-Path $env:TEMP "MagDshPyInstaller\spec"),
    (Join-Path $buildRoot "run_magdsh.py")
)

& $python @pyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "打包失败，退出码 $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

$distExe = Join-Path $buildRoot "MagDsh.exe"
$rootExe = Join-Path $appRoot "MagDsh.exe"
Copy-Item -LiteralPath $distExe -Destination $rootExe -Force
Write-Host "打包完成：$distExe" -ForegroundColor Green
Write-Host "Copied: $rootExe" -ForegroundColor Green
