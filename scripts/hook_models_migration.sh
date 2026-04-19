#!/usr/bin/env bash
# PostToolUse hook: models.py 수정 시 migration 리마인더
# 편집된 파일이 src/db/models.py인 경우에만 동작

EDITED_FILE="${CLAUDE_TOOL_INPUT_file_path:-}"

if [[ "$EDITED_FILE" == *"src/db/models.py" ]]; then
  echo ""
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  ⚠️  models.py 수정 감지 — Migration 체크리스트              ║"
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║  1. 새 컬럼/테이블을 추가했다면:                              ║"
  echo "║     → src/db/writer.py 의 init_db() 에                      ║"
  echo "║       ALTER TABLE ... ADD COLUMN IF NOT EXISTS 추가했는가?  ║"
  echo "║                                                              ║"
  echo "║  2. BigInteger 사용 여부 확인:                               ║"
  echo "║     → volume 컬럼은 반드시 BigInteger (삼성전자 거래량)       ║"
  echo "║                                                              ║"
  echo "║  3. UniqueConstraint 외 Index 추가 여부:                     ║"
  echo "║     → ticker, date 기반 조회가 많은 테이블은 Index 필요       ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
  echo ""
fi
