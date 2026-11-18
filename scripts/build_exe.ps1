# 本地打包成单文件 exe
# 用法：pwsh -File scripts/build_exe.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[1/4] 检查 Python 环境" -ForegroundColor Cyan
python --version
if ($LASTEXITCODE -ne 0) { throw "需要 Python 3.9+" }

Write-Host "[2/4] 安装依赖" -ForegroundColor Cyan
python -m pip install --upgrade pip | Out-Null
python -m pip install .
python -m pip install pyinstaller

Write-Host "[3/4] 打包" -ForegroundColor Cyan
python -m PyInstaller --onefile --name MacPlan --console --clean launcher.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }

Write-Host "[4/4] 冒烟测试" -ForegroundColor Cyan
& ".\dist\MacPlan.exe" --help | Select-Object -First 5

Write-Host "`n产物：$root\dist\MacPlan.exe" -ForegroundColor Green
