@echo off
REM ============================================================
REM  Paperhand's Beat Tools - double-click batch tagger
REM  Tags every MP3 in .\input using tags in .\tags,
REM  writing results to .\output and a report to .\reports.
REM
REM  Edit the OPTIONS line below to change interval, jitter, etc.
REM  (e.g.  set OPTIONS=--interval 35 --jitter 4 --before-drop )
REM ============================================================

cd /d "%~dp0"

set OPTIONS=

echo Running Paperhand's Beat Tagger...
python tag_beats.py %OPTIONS%

echo.
echo Finished. Press any key to close.
pause >nul
