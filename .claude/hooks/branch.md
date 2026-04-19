# Branch Rules

## 작업 시작 전 반드시 확인

현재 브랜치가 `main` 또는 `dev`이면 바로 작업하지 말고, 아래 규칙에 따라 브랜치를 분기한 뒤 작업한다.

| 작업 종류 | 브랜치 규칙 |
|----------|------------|
| 코드 작업 (기능 추가, 버그 수정) | `feature/{작업명}` 생성 |
| 문서 작업 (md 파일 수정) | `docs/{작업명}` 생성 |
| 리팩토링 | `refactor/{작업명}` 생성 |
| 핫픽스 | `hotfix/{작업명}` 생성 |

## Git Flow

```
feature/* ──┐
docs/*    ──┤──► dev ──► main
hotfix/*  ──┘
```

- PR은 항상 `dev`로 먼저 머지
- `dev → main` 머지는 검증 후 진행
- `main`에 직접 push 금지

## 브랜치 생성 예시

```bash
git checkout -b feature/phase2-retrain
git checkout -b docs/update-roadmap
```
