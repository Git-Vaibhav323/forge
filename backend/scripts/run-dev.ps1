# Run all ForgeData backend services in this window (no extra consoles).
# Usage (from backend/):  .\scripts\run-dev.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# Stop prior Start-Job workers from an earlier run in this session.
Get-Job -ErrorAction SilentlyContinue | Stop-Job -ErrorAction SilentlyContinue
Get-Job -ErrorAction SilentlyContinue | Remove-Job -ErrorAction SilentlyContinue

function Stop-Port([int]$Port) {
  Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

foreach ($port in 8000, 8001, 8002, 8003, 8004, 8005, 8006, 8007, 8008) {
  Stop-Port $port
}

# --reload leaves orphan python3.11 workers on Windows; clear them before starting.
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match "uvicorn" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 1

# --reload with Start-Job leaves orphan python3.11 workers on Windows.
$project  = Start-Job { Set-Location $using:PWD; python -m uvicorn services.project_service.main:app --port 8001 }
$file     = Start-Job { Set-Location $using:PWD; python -m uvicorn services.file_service.main:app --port 8002 }
$question = Start-Job { Set-Location $using:PWD; python -m uvicorn services.question_service.main:app --port 8003 }
$evidence = Start-Job { Set-Location $using:PWD; python -m uvicorn services.evidence_service.main:app --port 8004 }
$review   = Start-Job { Set-Location $using:PWD; python -m uvicorn services.review_service.main:app --port 8005 }
$relation = Start-Job { Set-Location $using:PWD; python -m uvicorn services.relationship_service.main:app --port 8006 }
$vision   = Start-Job { Set-Location $using:PWD; python -m uvicorn services.vision_service.main:app --port 8007 }
$generate = Start-Job { Set-Location $using:PWD; python -m uvicorn services.generation_service.main:app --port 8008 }
$gateway  = Start-Job { Set-Location $using:PWD; python -m uvicorn gateway.main:app --port 8000 }

Write-Host "project  :8001  job $($project.Id)"
Write-Host "file     :8002  job $($file.Id)"
Write-Host "question :8003  job $($question.Id)"
Write-Host "evidence :8004  job $($evidence.Id)"
Write-Host "review   :8005  job $($review.Id)"
Write-Host "relation :8006  job $($relation.Id)"
Write-Host "vision   :8007  job $($vision.Id)"
Write-Host "generate :8008  job $($generate.Id)"
Write-Host "gateway  :8000  job $($gateway.Id)"
Write-Host ""
Write-Host "Wait ~10s for all services to bind, then:"
Write-Host "  curl http://127.0.0.1:8000/api/projects"
Write-Host "Stop with: Get-Job | Stop-Job; Get-Job | Remove-Job"
