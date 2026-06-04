@echo off
REM Whale Finder — double-click to launch the dashboard in your browser.
cd /d "%~dp0"
python -m streamlit run app.py --server.port 8533
pause
