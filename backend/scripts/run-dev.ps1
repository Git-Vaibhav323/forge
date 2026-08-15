# Run all ForgeData backend services in this window (no extra consoles).
# Usage (from backend/):  .\scripts\run-dev.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Stop-Port([int]$Port) {
  Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

foreach ($port in 8000, 8001, 8002, 8003) {
  Stop-Port $port
}

$project  = Start-Job { Set-Location $using:PWD; python -m uvicorn services.project_service.main:app --reload --port 8001 }
$file     = Start-Job { Set-Location $using:PWD; python -m uvicorn services.file_service.main:app --reload --port 8002 }
$question = Start-Job { Set-Location $using:PWD; python -m uvicorn services.question_service.main:app --reload --port 8003 }
$gateway  = Start-Job { Set-Location $using:PWD; python -m uvicorn gateway.main:app --reload --port 8000 }

Write-Host "project  :8001  job $($project.Id)"
Write-Host "file     :8002  job $($file.Id)"
Write-Host "question :8003  job $($question.Id)"
Write-Host "gateway  :8000  job $($gateway.Id)"
Write-Host "Stop with: Get-Job | Stop-Job; Get-Job | Remove-Job"
