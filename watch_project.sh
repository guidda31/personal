#!/bin/bash

WATCH_DIR="/home/guidda/.openclaw/workspace/project"

echo "📦 Existing JSON files"
echo "===================================="

find "$WATCH_DIR" -type f -name "*.json" | while read -r file; do
  echo "📨 $file"
  jq . "$file" 2>/dev/null || cat "$file"
  echo
done

echo "👀 Now watching for changes..."
echo "===================================="

inotifywait -m -r \
  -e close_write,create,move \
  --format '%w%f' \
  "$WATCH_DIR" | while read -r path; do

    case "$path" in
      *.json)
        echo "📨 JSON UPDATE: $path"
        echo "------------------------------------"
        jq . "$path" 2>/dev/null || cat "$path"
        echo
        ;;
    esac

done
