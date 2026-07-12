@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在打包...
"C:\Users\26748\AppData\Local\Python\pythoncore-3.14-64\Scripts\pyinstaller.exe" "相机照片筛选工具(Qt版).spec"
echo.
echo 打包完成！生成的文件在 dist 目录下
pause
