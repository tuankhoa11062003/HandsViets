@echo off
cd /d D:\N8N\BV_HansViet\Handviets
call .venv\Scripts\python.exe manage.py sync_rss_news --max-items 2 --publish >> logs\rss_sync.log 2>&1
