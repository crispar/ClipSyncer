@echo off
echo Starting ClipboardHistory...
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the application
python main.py

REM If error, pause to see the message
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with error code %ERRORLEVEL%
    pause
)