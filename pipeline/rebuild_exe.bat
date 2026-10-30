@echo off
rem Rebuild app\CHRH Video\CHRH Video.exe after changing pipeline\*.py.
rem Close the program first (a running copy locks the folder).
rem Needs Python 3.12 + pip install --user -r pipeline\requirements.txt, and ffmpeg (winget install Gyan.FFmpeg).
cd /d "%~dp0.."
python -m PyInstaller --noconfirm --windowed --onedir --name "CHRH Video" --paths pipeline --distpath app --workpath work\pyi_build --specpath work\pyi_build --collect-data pocketsphinx --collect-binaries pocketsphinx --collect-binaries onnxruntime --hidden-import faces --hidden-import cv2 --hidden-import autoplan --hidden-import contact --hidden-import autotag --exclude-module librosa --exclude-module numba --exclude-module scipy --exclude-module matplotlib --exclude-module sklearn --exclude-module pandas --exclude-module tokenizers pipeline\app.py
if errorlevel 1 ( echo BUILD FAILED & pause & exit /b 1 )
rem PyInstaller empties the output folder: copy ffmpeg/ffprobe (full build with libass + vidstab) back into bin\
if not exist "app\CHRH Video\bin" mkdir "app\CHRH Video\bin"
for %%F in (ffmpeg.exe ffprobe.exe) do (
  if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\%%F" ( copy /y "%LOCALAPPDATA%\Microsoft\WinGet\Links\%%F" "app\CHRH Video\bin\" >nul ) else ( for %%P in (%%F) do if not "%%~$PATH:P"=="" copy /y "%%~$PATH:P" "app\CHRH Video\bin\" >nul )
)
"app\CHRH Video\CHRH Video.exe" --selftest scripts\topics_0929.txt
type work\app.log | findstr /c:"selftest"
pause
