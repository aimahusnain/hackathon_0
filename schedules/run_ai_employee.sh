#!/bin/bash
# AI Employee Scheduler - Linux/Mac Cron Script
# This script runs the AI Employee Orchestrator
#
# Usage: Add to crontab
# crontab -e
#
# Cron Examples:
# Run daily at 8:00 AM:
# 0 8 * * * /path/to/project/schedules/run_ai_employee.sh >> /var/log/ai_employee.log 2>&1
#
# Run every hour:
# 0 * * * * /path/to/project/schedules/run_ai_employee.sh >> /var/log/ai_employee.log 2>&1
#
# Run on Monday at 8:00 AM for weekly briefing:
# 0 8 * * 1 /path/to/project/schedules/run_ai_employee.sh >> /var/log/ai_employee.log 2>&1

echo "========================================"
echo "AI Employee Orchestrator"
echo "Starting at: $(date)"
echo "========================================"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT" || exit 1

# Activate virtual environment if exists
if [ -f ".venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Run the orchestrator
echo "Running AI Employee Orchestrator..."
python orchestrator.py --once

# Check for errors
if [ $? -ne 0 ]; then
    echo "Error occurred! Check logs."
    exit 1
fi

echo "========================================"
echo "AI Employee run completed at: $(date)"
echo "========================================"

# Optional: Generate weekly briefing on Monday
DAY_OF_WEEK=$(date +%u)
if [ "$DAY_OF_WEEK" = "1" ]; then
    echo "Monday detected - Generating CEO Briefing..."
    python -c "from skills.ceo_briefing import generate_weekly_briefing; print(generate_weekly_briefing())"
fi

exit 0
