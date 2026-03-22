@echo off
setlocal

cd /d "%~dp0"

where dotnet >nul 2>nul
if errorlevel 1 (
    echo [.NET SDK not found]
    echo Install .NET 8 SDK with Windows Desktop support, then run this script again.
    pause
    exit /b 1
)

echo [1/3] Restoring project...
dotnet restore "src\GraduationDesign.App\GraduationDesign.App.csproj" -p:NuGetAudit=false -p:RestoreIgnoreFailedSources=true
if errorlevel 1 goto :fail

echo [2/3] Building project...
dotnet build "src\GraduationDesign.App\GraduationDesign.App.csproj" -c Debug --no-restore -p:NuGetAudit=false
if errorlevel 1 goto :fail

echo [3/3] Running application...
dotnet run --project "src\GraduationDesign.App\GraduationDesign.App.csproj" -c Debug --no-build
exit /b %errorlevel%

:fail
echo.
echo Build or restore failed.
pause
exit /b 1
