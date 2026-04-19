#!/usr/bin/env bash
# PreToolUse hook: 위험한 Bash 명령어 실행 전 차단
# exit 2 → Claude에게 차단 메시지 전달
# exit 0 → 정상 통과

COMMAND="${CLAUDE_TOOL_INPUT_command:-}"

# ── 차단 패턴 목록 ────────────────────────────────────────────

BLOCKED=false
REASON=""

# DB 테이블/데이터베이스 드롭
if echo "$COMMAND" | grep -qiE "(DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE\s+TABLE)"; then
  BLOCKED=true
  REASON="DB 테이블/데이터베이스 삭제 명령어가 감지됨. 데이터 복구 불가."
fi

# 학습된 모델 파일 강제 삭제
if echo "$COMMAND" | grep -qE "rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(.*/)?(models)/"; then
  BLOCKED=true
  REASON="models/ 디렉토리 강제 삭제 감지. 학습된 모델이 모두 손실됨."
fi

# .claude 설정 강제 삭제
if echo "$COMMAND" | grep -qE "rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(.*/)?.claude/"; then
  BLOCKED=true
  REASON=".claude/ 디렉토리 강제 삭제 감지. 에이전트 설정 및 메모리가 모두 손실됨."
fi

# force push
if echo "$COMMAND" | grep -qE "git\s+push\s+.*(--force|-f)"; then
  BLOCKED=true
  REASON="git force push 감지. 원격 히스토리를 덮어씀."
fi

# hard reset
if echo "$COMMAND" | grep -qE "git\s+reset\s+--hard"; then
  BLOCKED=true
  REASON="git reset --hard 감지. 커밋되지 않은 모든 변경사항이 손실됨."
fi

# ── 결과 출력 ────────────────────────────────────────────────

if [ "$BLOCKED" = true ]; then
  echo ""
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  🛑  BASH GUARD — 실행 차단                                  ║"
  echo "╠══════════════════════════════════════════════════════════════╣"
  printf "║  이유: %-55s║\n" "$REASON"
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║  차단된 명령어:                                               ║"
  printf "║  %-61s║\n" "${COMMAND:0:60}"
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║  실행이 필요하다면 사용자에게 직접 확인 요청                   ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
  echo ""
  exit 2
fi

exit 0
