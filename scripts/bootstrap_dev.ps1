# 本地初始化后端（Windows PowerShell）
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\backend')
if (-not (Test-Path .venv)) {
  python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (-not (Test-Path ..\.env)) {
  Copy-Item ..\.env.example ..\.env
  Write-Host 'Created ..\.env — please fill XUANPIN / MELI keys'
}
python manage.py migrate
Write-Host 'OK. Run: python manage.py runserver 0.0.0.0:8100'
