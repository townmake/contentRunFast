# 联调验收：选品 Listing 只读 → 本系统 import-from-xuanpin
# 用法（在仓库根目录）:
#   .\scripts\verify_xuanpin_import.ps1 -ListingId 2 -McpKey "mcp_xxx"
# 或先在 .env 写好 XUANPIN_MCP_API_KEY，再:
#   .\scripts\verify_xuanpin_import.ps1 -ListingId 2

param(
  [int]$ListingId = 2,
  [string]$McpKey = "",
  [string]$XuanpinBase = "http://127.0.0.1:8000",
  [string]$OptBase = "http://127.0.0.1:8100",
  [string]$Username = "",
  [string]$Password = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"

function Get-EnvValue([string]$name) {
  if (-not (Test-Path $envFile)) { return "" }
  $line = Get-Content $envFile | Where-Object { $_ -match "^$name=" } | Select-Object -First 1
  if (-not $line) { return "" }
  return ($line -split "=", 2)[1].Trim()
}

if (-not $McpKey) {
  $McpKey = Get-EnvValue "XUANPIN_MCP_API_KEY"
}
if (-not $McpKey -or $McpKey -eq "mcp_your_key_here") {
  Write-Host "ERROR: 请传入 -McpKey 或在 .env 填写真实 XUANPIN_MCP_API_KEY" -ForegroundColor Red
  exit 1
}

$headers = @{
  Authorization = "Bearer $McpKey"
  Accept        = "application/json"
}

Write-Host "`n=== 1) 选品 GET listing #$ListingId ===" -ForegroundColor Cyan
try {
  $listing = Invoke-RestMethod -Uri "$XuanpinBase/product-development/api/open/listings/$ListingId/" -Headers $headers
} catch {
  Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
  if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
  exit 1
}
if (-not $listing.success) {
  Write-Host "FAIL: success=false $($listing.error)" -ForegroundColor Red
  exit 1
}
$detail = if ($listing.listing) { $listing.listing } else { $listing }
Write-Host ("OK title={0} images={1} brief_id={2}" -f `
  ($(if ($detail.title) { $detail.title } else { $detail.listing_title })), `
  (@($detail.listing_image_urls).Count), `
  $detail.stakeholder_brief_id)

Write-Host "`n=== 2) 选品 images / content / faqs ===" -ForegroundColor Cyan
foreach ($path in @(
  "images",
  "content-production",
  "faqs"
)) {
  $url = "$XuanpinBase/product-development/api/open/listings/$ListingId/$path/"
  try {
    $r = Invoke-RestMethod -Uri $url -Headers $headers
    Write-Host ("OK  /{0}/ success={1}" -f $path, $r.success)
  } catch {
    Write-Host ("WARN /{0}/ → {1}" -f $path, $_.Exception.Message) -ForegroundColor Yellow
  }
}

Write-Host "`n=== 3) 本系统 health ===" -ForegroundColor Cyan
try {
  $health = Invoke-RestMethod -Uri "$OptBase/api/health/"
  Write-Host "OK $($health | ConvertTo-Json -Compress)"
} catch {
  Write-Host "FAIL: 本系统未启动。请先: cd backend; .\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8100" -ForegroundColor Red
  exit 1
}

if (-not $Username) {
  Write-Host "`n跳过 HTTP import（未提供 -Username/-Password）。改用 Django shell 导入…" -ForegroundColor Yellow
  $py = @"
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from apps.catalog.services import import_from_xuanpin, serialize_product
r = import_from_xuanpin(listing_id=$ListingId, ml_site='MLB')
p = r['product']
print('created=', r['created'], 'product_id=', p.id)
print(serialize_product(p))
"@
  Push-Location (Join-Path $root "backend")
  $py | .\.venv\Scripts\python.exe manage.py shell
  Pop-Location
  Write-Host "`nDONE" -ForegroundColor Green
  exit 0
}

Write-Host "`n=== 4) 本系统 import-from-xuanpin ===" -ForegroundColor Cyan
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
# 先拿 CSRF / 登录 session（SessionAuthentication）
$loginPage = Invoke-WebRequest -Uri "$OptBase/admin/login/" -SessionVariable session -UseBasicParsing
$csrf = ($loginPage.InputFields | Where-Object { $_.name -eq "csrfmiddlewaretoken" }).value
$loginBody = @{
  username = $Username
  password = $Password
  csrfmiddlewaretoken = $csrf
  next = "/admin/"
}
Invoke-WebRequest -Uri "$OptBase/admin/login/" -WebSession $session -Method POST -Body $loginBody -ContentType "application/x-www-form-urlencoded" -UseBasicParsing | Out-Null

$csrf2 = $session.Cookies.GetCookies($OptBase) | Where-Object { $_.Name -eq "csrftoken" } | Select-Object -ExpandProperty Value
$importHeaders = @{
  "Content-Type" = "application/json"
  "X-CSRFToken"  = $csrf2
  "Referer"      = "$OptBase/"
}
$body = @{ listing_id = $ListingId; ml_site = "MLB" } | ConvertTo-Json
$imported = Invoke-RestMethod -Uri "$OptBase/api/products/import-from-xuanpin/" -WebSession $session -Method POST -Headers $importHeaders -Body $body
Write-Host ($imported | ConvertTo-Json -Depth 6)

if (-not $imported.success) {
  Write-Host "FAIL import" -ForegroundColor Red
  exit 1
}

$pid_ = $imported.product.id
$detail2 = Invoke-RestMethod -Uri "$OptBase/api/products/$pid_/" -WebSession $session
Write-Host "`n=== 5) 详情摘要 ===" -ForegroundColor Cyan
$ctx = $detail2.product.xuanpin_context
Write-Host ("product_id={0} listing_id={1} title={2} images={3} brief_keys={4}" -f `
  $detail2.product.id, `
  $detail2.product.xuanpin_listing_id, `
  $ctx.title, `
  @($ctx.image_urls).Count, `
  (($ctx.brief | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name) -join ","))

Write-Host "`nDONE" -ForegroundColor Green
