#!/bin/bash
set -e
PORT=8899
DIR="$HOME/tianyi_radar"
mkdir -p "$DIR"
cd "$DIR"
curl -fsSL -o server.py "https://raw.githubusercontent.com/luoTYX/tianyi-food-radar/main/extras/server/server.py"
pkill -f "python3.*server.py" 2>/dev/null || true
nohup python3 server.py > /tmp/tianyi_radar.log 2>&1 &
sleep 1
curl -s http://localhost:$PORT/api/health && echo " 装好了~" || echo " 失败 看日志: /tmp/tianyi_radar.log"
