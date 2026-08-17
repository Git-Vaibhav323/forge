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
uvicorn services.review_service.main:app --reload --port 8005 &
PID5=$!
uvicorn services.relationship_service.main:app --reload --port 8006 &
PID6=$!
uvicorn services.vision_service.main:app --reload --port 8007 &
PID7=$!
uvicorn services.generation_service.main:app --reload --port 8008 &
PID8=$!
uvicorn gateway.main:app --reload --port 8000 &
PID9=$!

trap 'kill $PID1 $PID2 $PID3 $PID4 $PID5 $PID6 $PID7 $PID8 $PID9 2>/dev/null' EXIT
wait
