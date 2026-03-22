@echo off
setlocal

cd /d "%~dp0"

where dotnet >nul 2>nul
if errorlevel 1 (
    echo [.NET SDK not found]
    echo Install .NET 8 SDK, then run this script again.
    pause
    exit /b 1
)

echo [1/3] Restoring simulator...
dotnet restore "tools\MeasurementTerminalSimulator\MeasurementTerminalSimulator.csproj" -p:NuGetAudit=false -p:RestoreIgnoreFailedSources=true
if errorlevel 1 goto :fail

echo [2/3] Building simulator...
dotnet build "tools\MeasurementTerminalSimulator\MeasurementTerminalSimulator.csproj" -c Debug --no-restore -p:NuGetAudit=false
if errorlevel 1 goto :fail

echo [3/3] Running simulator...
dotnet run --project "tools\MeasurementTerminalSimulator\MeasurementTerminalSimulator.csproj" -c Debug --no-build
exit /b %errorlevel%

:fail
echo.
echo Simulator build or restore failed.
pause
exit /b 1
