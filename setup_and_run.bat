@echo off
REM ONE-CLICK SETUP & RUN SCRIPT FOR WINDOWS
REM Usage: setup_and_run.bat "Company" "Name" "email@company.com"

echo ==========================================
echo    Email Outreach Tool - Auto Setup
echo ==========================================
echo.

if "%~3"=="" (
    echo Usage: setup_and_run.bat "Company Name" "Recruiter Name" "email@company.com"
    echo.
    echo Example:
    echo   setup_and_run.bat "Google" "John Smith" "john.smith@google.com"
    exit /b 1
)

set COMPANY=%~1
set NAME=%~2
set EMAIL=%~3

REM Check if uv is installed
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Installing uv...
    pip install uv
    echo Done installing uv
) else (
    echo uv already installed
)

REM Install dependencies if .venv doesn't exist
if not exist ".venv" (
    echo.
    echo Installing dependencies...
    uv sync
    echo Done installing dependencies
) else (
    echo Dependencies already installed
)

echo.
echo ==========================================
echo Sending email to: %NAME% at %COMPANY%
echo Email: %EMAIL%
echo ==========================================
echo.

REM Run the email script
.venv\Scripts\python automate_emails.py "%COMPANY%" "%NAME%" "%EMAIL%"

echo.
echo Done! Check Gmail for delivery status.
pause



