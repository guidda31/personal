#!/bin/bash

WATCH_DIR="/home/guidda/.openclaw/workspace/project"

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
