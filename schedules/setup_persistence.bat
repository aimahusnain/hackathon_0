@echo off
REM ========================================
REM AI Employee - Process Manager Setup
REM ========================================
REM
REM This sets up the AI Employee to run 24/7
REM with automatic restart on failure
REM
REM Options:
REM   1. PM2 (Recommended) - Cross-platform, easy monitoring
REM   2. Windows Task Scheduler - Native Windows option
REM   3. Python Watchdog - Custom solution
REM
echo ========================================
echo AI Employee Process Manager Setup
echo ========================================
echo.

REM Check if PM2 is installed
where pm2 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OPTION 1] PM2 detected - Recommended for 24/7 operation
    echo.
    echo Starting watchers with PM2...
    pm2 start python --name "gmail-watcher" --interpreter python3 Watchers/gmail_watcher.py
    pm2 start python --name "whatsapp-watcher" --interpreter python3 Watchers/whatsapp_watcher.py
    pm2 start python --name "approval-watcher" --interpreter python3 Watchers/approval_watcher.py
    pm2 start python --name "orchestrator" --interpreter python3 orchestrator.py
    pm2 save
    pm2 startup
    echo.
    echo ========================================
    echo AI Employee is now running 24/7!
    echo Monitor with: pm2 status
    echo View logs: pm2 logs
    echo Stop all: pm2 stop all
    echo ========================================
    goto :end
)

echo PM2 not found. Please install:
echo   npm install -g pm2
echo.
echo Or use Windows Task Scheduler option:
echo   1. Open Task Scheduler (taskschd.msc)
echo   2. Import: schedules\ai_employee_task.xml
echo.

:end
pause
