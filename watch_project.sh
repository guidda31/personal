#!/bin/bash

inotifywait -m -r \
  -e close_write,modify,create,move \
  --format '%w%f %e' \
  project | while read -r path event; do
    echo "📦 EVENT: $event"
    echo "📁 FILE : $path"
    echo "------------------------------------"

    if [ -f "$path" ]; then
      cat "$path"
    fi

    echo
done
