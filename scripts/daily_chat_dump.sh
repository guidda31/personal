#!/usr/bin/env bash
set -euo pipefail

REPO="/home/guidda/.openclaw/workspace"
OUT_DIR="$REPO/project/pm/docs"
KST_NOW="$(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S KST')"
DAY="$(TZ=Asia/Seoul date '+%Y-%m-%d')"
OUT_FILE="$OUT_DIR/chat_dump_${DAY}.txt"

mkdir -p "$OUT_DIR"

{
  echo "[자동 대화 덤프] ${DAY} (Asia/Seoul)"
  echo "생성시각: ${KST_NOW}"
  echo
  echo "=================================================="
  echo "1) 당일 메모"
  echo "=================================================="
  if [[ -f "$REPO/memory/${DAY}.md" ]]; then
    cat "$REPO/memory/${DAY}.md"
  else
    echo "- memory/${DAY}.md 파일 없음"
  fi

  echo
  echo "=================================================="
  echo "2) 프로젝트 역할 대화 로그"
  echo "=================================================="
  if [[ -f "$REPO/project/shared/docs/ROLE_CHAT_LOG.txt" ]]; then
    cat "$REPO/project/shared/docs/ROLE_CHAT_LOG.txt"
  else
    echo "- ROLE_CHAT_LOG.txt 없음"
  fi

  echo
  echo "=================================================="
  echo "3) 프로젝트 역할 산출물(inbox/outbox)"
  echo "=================================================="
  find "$REPO/project" -type f \( -path '*/outbox/*' -o -path '*/inbox/*' \) -name '*.json' | sort | while read -r f; do
    echo
    echo "- 파일: ${f#$REPO/}"
    if command -v jq >/dev/null 2>&1; then
      jq . "$f" 2>/dev/null || cat "$f"
    else
      cat "$f"
    fi
  done

  echo
  echo "=================================================="
  echo "4) Git 변경 요약(최근 커밋 20개)"
  echo "=================================================="
  git -C "$REPO" log --oneline -n 20 || true

  echo
  echo "[끝]"
} > "$OUT_FILE"

# Commit + push
cd "$REPO"
git add "$OUT_FILE"
if ! git diff --cached --quiet; then
  git commit -m "auto: daily chat dump ${DAY}" >/dev/null 2>&1 || true
  git pull --rebase origin master >/dev/null 2>&1 || true
  git push origin master >/dev/null 2>&1 || true
fi

echo "$OUT_FILE"
