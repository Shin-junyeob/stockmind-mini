#!/usr/bin/env bash
# Stop hook: Claude 세션 종료 시 pytest 자동 실행
# 테스트 실패 시 경고 출력 (세션 종료를 막지는 않음)

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# .venv 또는 시스템 Python 자동 선택
if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
else
  PYTHON="python"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  세션 종료 — 자동 테스트 실행 중..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# DB 없이 실행 가능한 테스트만 대상 (CI와 동일하게 mock 사용 테스트)
cd "$PROJECT_ROOT" || exit 0
PYTHONPATH=src $PYTHON -m pytest tests/ -q --tb=short 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  echo ""
  echo "  ✅ 모든 테스트 통과"
elif [ $EXIT_CODE -eq 5 ]; then
  echo ""
  echo "  ℹ️  실행된 테스트 없음 (tests/ 디렉토리 확인)"
else
  echo ""
  echo "  ❌ 테스트 실패 (exit $EXIT_CODE)"
  echo "  → 커밋 전 pytest tests/ -v 로 상세 확인 권장"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
