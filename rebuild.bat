@echo off
echo ============================================
echo   EOBI Wage Calculator - Build Script
echo ============================================
echo.

echo Installing requirements...
pip install -r requirements.txt
pip install pyinstaller customtkinter reportlab pillow

echo.
echo Building executable...
pyinstaller --onefile --windowed --name "EOBI_Wage_Calculator" --icon=logo.ico --add-data "logo.png;." --add-data "employer list.csv;." main.py

echo.
echo ============================================
echo   Build complete! Check the 'dist' folder.
echo ============================================
pause