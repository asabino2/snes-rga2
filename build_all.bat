@echo off
echo ============================================================================
echo RETROGAMERS AVENTURA 2 (RGA2) - SNES 16-BIT BUILD SYSTEM
echo ============================================================================
cd /d "%~dp0"
python tools\gif_snes_converter.py
if errorlevel 1 exit /b 1
python tools\wav_to_brr.py
if errorlevel 1 exit /b 1
python tools\build_snes_rom.py
if errorlevel 1 exit /b 1
python tools\verify_rom.py
if errorlevel 1 exit /b 1
echo.
echo [SUCESSO] ROMs .smc e binarios de EPROM gerados em snes_rga2\rom\
