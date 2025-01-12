YouTubeTranscriptApi.http_handler = ProxyRequestHandler()#!/bin/bash

# Просмотр логов systemd
echo "=== Логи systemd ==="
sudo journalctl -u youtube-transcriber -n 50 --no-pager

# Просмотр логов приложения
echo -e "\n=== Логи приложения ==="
tail -n 50 /home/YouTubeTranscriber/logs/bot_*.log
