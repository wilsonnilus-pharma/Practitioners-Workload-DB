@echo off
TITLE Practitioners Workload DB Launcher
COLOR 0A

echo ============================================
echo         Practitioners Workload DB - Startup
echo ============================================
echo.

:: ── Check Python ──────────────────────────────────────────────────────────
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

:: ── Install dependencies (first run only) ─────────────────────────────────
echo [1/3] Checking dependencies...
python -m pip install -q --pre pandas
python -m pip install -q fastapi "uvicorn[standard]" sqlalchemy alembic "python-jose[cryptography]" bcrypt python-dotenv python-multipart httpx requests plotly streamlit
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies. Check your internet connection.
    pause
    exit /b 1
)
echo       Dependencies OK.
echo.

:: ── Create csv_xml folder if missing ─────────────────────────────────────
IF NOT EXIST "%~dp0csv_xml" (
    mkdir "%~dp0csv_xml"
    echo [INFO] Created csv_xml folder.
)

:: ── Start FastAPI backend ─────────────────────────────────────────────────
echo [2/3] Starting FastAPI backend on http://127.0.0.1:8000 ...
start "Practitioners Workload DB - Backend" /B cmd /c "cd /d %~dp0 && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 > backend.log 2>&1"

:: Wait for backend to become ready
echo       Waiting for backend to start...
timeout /t 4 /nobreak >nul

:: ── Pre-create Streamlit credentials to skip email prompt ──────────────────
SET ST_DIR=%USERPROFILE%\.streamlit
IF NOT EXIST "%ST_DIR%" mkdir "%ST_DIR%"
IF NOT EXIST "%ST_DIR%\credentials.toml" (
    echo [general] > "%ST_DIR%\credentials.toml"
    echo email = "" >> "%ST_DIR%\credentials.toml"
)

:: ── Start Streamlit frontend ──────────────────────────────────────────────
echo [3/3] Starting Streamlit frontend on http://localhost:8501 ...
start "Practitioners Workload DB - Frontend" /B cmd /c "cd /d %~dp0 && echo.|python -m streamlit run frontend\app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false --server.maxUploadSize 500 --theme.base dark --theme.backgroundColor #0f172a --theme.primaryColor #60a5fa --theme.secondaryBackgroundColor #1e293b --theme.textColor #f1f5f9 > frontend.log 2>&1"

echo.
echo ============================================
echo  App is starting...
echo  Backend:  http://127.0.0.1:8000
echo  Frontend: http://localhost:8501
echo  API Docs: http://127.0.0.1:8000/docs
echo.
echo  Default login: admin / admin123
echo  (Change password in production!)
echo ============================================
echo.
echo Opening browser automatically...
timeout /t 3 /nobreak >nul

explorer "http://localhost:8501"
