#!/bin/bash
# Bấm đúp để mở TĐH Chemistry trên máy này (chỉ máy này truy cập được).
cd "$(dirname "$0")" || exit 1
(sleep 2 && open "http://localhost:8700") &
exec python3 server.py --port 8700
