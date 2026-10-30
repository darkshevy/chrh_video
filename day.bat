@echo off
rem One day's batch in one go: record the voice-overs, then plan, render and blur every video in the script file.
rem
rem   day.bat                                  the newest scripts\topics_*.txt
rem   day.bat scripts\topics_1103.txt          that file
rem   day.bat scripts\topics_1103.txt upperdeck    just one video from it
rem
rem Lives in the project folder, next to pipeline\. Double-click it, or run it from PowerShell.
rem The two API keys have to be set once in System Properties -> Environment Variables:
rem   ANTHROPIC_API_KEY   ELEVENLABS_API_KEY
setlocal
cd /d "%~dp0"

set SCRIPTS=%1
if "%SCRIPTS%"=="" for /f "delims=" %%f in ('dir /b /o-d scripts\topics_*.txt 2^>nul') do if not defined SCRIPTS set SCRIPTS=scripts\%%f

if "%SCRIPTS%"=="" (
  echo No script file. Pass one, or put it in scripts\ named topics_MMDD.txt
  goto end
)
if not exist "%SCRIPTS%" (
  echo Not found: %SCRIPTS%
  goto end
)
if "%ANTHROPIC_API_KEY%"=="" echo warning: ANTHROPIC_API_KEY is not set - the planning step will stop
if "%ELEVENLABS_API_KEY%"=="" echo warning: ELEVENLABS_API_KEY is not set - the voice-over step will stop

echo.
echo ===== %SCRIPTS% =====
echo.
echo ----- voice-over --------------------------------------------------
python pipeline\voice.py "%SCRIPTS%" %2 %3 %4 %5
rem A missing or half-recorded mp3 breaks the whole edit: the cuts sit on the aligned words, so there is no
rem point rendering anything until every voice-over is in place.
if errorlevel 1 (
  echo.
  echo The voice-over step failed, so nothing was built. Fix that first.
  goto end
)

echo.
echo ----- plan, render, blur -----------------------------------------
python pipeline\plan_ai.py "%SCRIPTS%" %2 %3 %4 %5
if errorlevel 1 echo.& echo Some videos did not finish - see the list above.

:end
echo.
pause
