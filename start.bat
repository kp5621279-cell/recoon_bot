@echo off
title Recoon Bot
echo Starting Recoon Bot...

:: Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate
) else (
    echo [WARNING] No venv found. Running globally.
)

:: Ensure dependencies are installed and yt-dlp is always up-to-date
pip install -r requirements.txt
pip install -U yt-dlp

:: Run the bot
python bot.py

pause
