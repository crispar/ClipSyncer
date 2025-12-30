@echo off
echo Running ClipboardHistory Tests...
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run tests
python test_app.py

echo.
pause