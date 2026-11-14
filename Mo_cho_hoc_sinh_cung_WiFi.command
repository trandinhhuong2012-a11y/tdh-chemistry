#!/bin/bash
# Bấm đúp để mở TĐH Chemistry cho các máy cùng mạng Wi-Fi truy cập.
# Địa chỉ cho học sinh được in ra ở cửa sổ này (dạng http://192.168.x.x:8700).
cd "$(dirname "$0")" || exit 1
(sleep 2 && open "http://localhost:8700") &
exec python3 server.py --port 8700 --lan
