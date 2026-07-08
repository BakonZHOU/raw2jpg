
@echo off
echo =========================================
echo 正在打包相机照片极速筛选工具...
echo =========================================

REM 清理旧的打包文件
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 使用 spec 文件打包（推荐方式，支持图标等高级配置）
pyinstaller build.spec

echo.
echo =========================================
echo 打包完成！
echo 可执行文件在 dist 目录中
echo =========================================
pause
