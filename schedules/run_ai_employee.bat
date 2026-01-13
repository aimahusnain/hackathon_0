@echo off
REM AI Employee Scheduler - Windows Task Scheduler Script
REM This script runs the AI Employee Orchestrator
REM
REM Usage: Schedule this script in Windows Task Scheduler
REM
REM Task Scheduler Settings:
REM - Trigger: Daily at 8:00 AM (or your preferred time)
REM - Action: Start a program
REM - Program: path\to\schedules\run_ai_employee.bat
REM - Start in: project root directory

echo ========================================
echo AI Employee Orchestrator
echo Starting at: %date% %time%
echo ========================================

REM Get script directory
SET SCRIPT_DIR=%~dp0
SET PROJECT_ROOT=%SCRIPT_DIR%..

REM Activate virtual environment if exists
if exist "%PROJECT_ROOT%\.venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
)

REM Change to project root
cd /d "%PROJECT_ROOT%"

REM Run the orchestrator
echo Running AI Employee Orchestrator...
python orchestrator.py --once

REM Check for errors
if %ERRORLEVEL% NEQ 0 (
    echo Error occurred! Check logs.
    exit /b %ERRORLEVEL%
)

echo ========================================
echo AI Employee run completed at: %date% %time%
echo ========================================

REM Optional: Generate weekly briefing on Monday
for /f "skip=1 tokens=1" %%a in ('wmic os get localdatetime ^| findstr .') do set dt=%%a&goto :done
:done
set dayOfWeek=%dt:~6,2%
if %dayOfWeek%==1 (
    echo Monday detected - Generating CEO Briefing...
    python -c "from skills.ceo_briefing import generate_weekly_briefing; print(generate_weekly_briefing())"
)

exit /b 0
