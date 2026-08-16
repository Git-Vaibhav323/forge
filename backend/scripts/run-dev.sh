#!/usr/bin/env bash
# Run all ForgeData backend processes (gateway + microservices).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
fi

uvicorn services.project_service.main:app --reload --port 8001 &
PID1=$!
uvicorn services.file_service.main:app --reload --port 8002 &
PID2=$!
uvicorn services.question_service.main:app --reload --port 8003 &
PID3=$!
uvicorn services.evidence_service.main:app --reload --port 8004 &
PID4=$!
uvicorn gateway.main:app --reload --port 8000 &
PID5=$!

trap 'kill $PID1 $PID2 $PID3 $PID4 $PID5 2>/dev/null' EXIT
wait
