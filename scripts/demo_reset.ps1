# Tear down volumes and re-run demo_start.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
docker compose down -v
& (Join-Path $PSScriptRoot "demo_start.ps1")
