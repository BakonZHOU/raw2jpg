@echo off
echo =========================================
echo 正在打包相机照片极速筛选工具(Qt版)...
echo =========================================

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

pyinstaller 相机照片筛选工具(Qt版).spec

echo.
echo =========================================
echo 打包完成！
echo 可执行文件在 dist 目录中
echo =========================================
pause
