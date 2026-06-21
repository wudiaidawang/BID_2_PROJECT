@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   启动 Redis...
echo ========================================
start "Redis" /MIN "E:\redis\redis-server.exe"

echo  等待 Redis 就绪...
:wait_redis
timeout /t 1 /nobreak >nul
"E:\redis\redis-cli.exe" ping >nul 2>&1
if errorlevel 1 goto wait_redis
echo  Redis 已就绪

echo.
echo ========================================
echo   启动问答服务...
echo ========================================
python main.py

echo.
echo 服务已停止，正在关闭 Redis...
"E:\redis\redis-cli.exe" shutdown
echo 完成
pause
