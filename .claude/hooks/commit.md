# Commit Rules

## 커밋 전 필수 체크

1. `pytest tests/ -v` 실행 → 전부 통과해야 커밋
2. 커밋할 파일에 `.env`, `*.pt`, `*.pkl`, `models/` 포함 여부 확인 (gitignored 대상)

```bash
pytest tests/ -v
git status  # 커밋 대상 파일 확인
```

## 커밋 메시지 컨벤션

```
{type}: {설명}

feat:     새 기능 추가
fix:      버그 수정
docs:     문서 수정
refactor: 코드 리팩토링 (기능 변경 없음)
test:     테스트 추가/수정
chore:    빌드, 설정 변경
```

예시:
```
feat: add prediction_logs table and API logging
fix: correct price_change calculation to close/prev_close - 1
docs: update roadmap with Phase 1 completion
```

## 커밋하면 안 되는 파일

- `.env` (환경변수)
- `models/*.pt`, `models/*.pkl` (학습된 모델 파일)
- `.claude/settings.local.json` (개인 MCP 설정, 토큰 포함)
- `__pycache__/`, `.pytest_cache/`
