# CLAUDE.md — Navigation

작업 종류에 따라 아래 경로를 먼저 확인한다.

---

## 작업 시작 전

| 확인 항목 | 경로 |
|----------|------|
| 현재 진행 상황 / 다음 할 일 | `roadmap.md` |
| 브랜치 분기 규칙 | `.claude/hooks/branch.md` |
| 코딩 컨벤션 / ML 규칙 | `.claude/rules/coding.md` |

## 커밋 전

| 확인 항목 | 경로 |
|----------|------|
| 테스트 실행 / 커밋 규칙 / 금지 파일 | `.claude/hooks/commit.md` |

---

## 하네스 구성

| 분류 | 경로 | 설명 |
|------|------|------|
| rules/ | `.claude/rules/coding.md` | 코딩 컨벤션, ML 누수 방지, 모델 파일 규칙 |
| agents/ | `.claude/agents/` | plan-architect / senior-dev-validator / junior-dev-implementer |
| skills/ | `.claude/commands/` | 슬래시 커맨드 `/status` `/fix-p0` `/leakage-check` ※ |
| hooks/ | `.claude/hooks/branch.md` | 브랜치 분기 규칙 |
| hooks/ | `.claude/hooks/commit.md` | 커밋 전 체크리스트 |
| logs/ | `.claude/logs/` | 세션 중 결정 기록, 트러블슈팅 메모 |
| outputs/ | `.claude/outputs/` | leakage-check 결과, 검토 보고서, 분석 결과물 |
| settings | `.claude/settings.json` | 허용/차단 명령어, hook 스크립트 연결 |
| settings | `.claude/settings.local.json` | 개인 MCP 설정 (gitignored, 토큰 포함) |

※ Claude Code는 슬래시 커맨드를 `commands/`에서 읽음. 디렉토리명 변경 불가.

---

## 로컬 개발 명령어

```bash
# DB + API 컨테이너
docker compose up -d db api

# 데이터 수집
PYTHONPATH=src python src/main.py

# ML 전체 학습
PYTHONPATH=src python src/ml/train.py

# 임계값 튜닝
PYTHONPATH=src python src/ml/tune_threshold.py

# 테스트
pytest tests/ -v

# API 로컬 실행
PYTHONPATH=src uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```
