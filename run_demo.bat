@echo off
setlocal

:: Get the directory where the script is located
set "BASE_DIR=%~dp0"
cd /d "%BASE_DIR%"

echo ============================================================
echo    TEMPESTDROP // Optical Air-Gap Exfiltration Suite
echo    Advanced System Hackathon 2026
echo ============================================================
echo.

:: ── JDK 21 Detection ──
if exist "C:\Program Files\Microsoft\jdk-21.0.10.7-hotspot\bin\java.exe" (
    set "JAVA_HOME=C:\Program Files\Microsoft\jdk-21.0.10.7-hotspot"
) else (
    echo [!] JDK 21 not found. Checking JAVA_HOME...
    if "%JAVA_HOME%"=="" (
        echo [ERROR] JAVA_HOME is not set. Install JDK 21 first.
        pause
        exit /b 1
    )
)
set "PATH=%JAVA_HOME%\bin;%PATH%"
echo [OK] Using JDK: %JAVA_HOME%
echo.

echo [1/4] Starting Python DSP Backend...
start "TempestDrop Python DSP" cmd /c "cd /d "%BASE_DIR%" && python py_dsp\dsp_engine.py"

echo [2/4] Awaiting Backend Initialization (5s)...
timeout /t 5 /nobreak > nul

echo [3/4] Starting Java C2 Dashboard (JavaFX 21 via Maven)...
start "TempestDrop Java C2" cmd /c "cd /d "%BASE_DIR%java_ui" && mvnw.cmd javafx:run"

echo [4/4] Starting C# Infection Orchestrator...
start "TempestDrop C# Infector" cmd /c "cd /d "%BASE_DIR%" && cs_infector\bin\Debug\net9.0\cs_infector_new.exe"

echo.
echo [+] ALL SYSTEMS ONLINE.
echo [+] JDK 21 LTS ^| JavaFX 21.0.2 ^| Manchester 10 Baud
echo [+] MONITOR THE JAVA C2 DASHBOARD FOR STEALTH EXFILTRATION.
echo.
pause
