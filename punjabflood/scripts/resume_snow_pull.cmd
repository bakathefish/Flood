@echo off
rem One-shot resume of the Bhakra snow pull after Open-Meteo's daily quota reset.
rem Retries hourly (up to 12 times) while the daily limit is still exhausted, then runs
rem verify and report so the snowmelt verdict is on disk. Log: data\raw\rain\snow_pull_resume.log
cd /d "%~dp0.."
set LOG=data\raw\rain\snow_pull_resume.log
set /a tries=0
:again
set /a tries+=1
echo === attempt %tries% at %date% %time% >> %LOG%
python scripts\pull_snow_bhakra.py >> %LOG% 2>&1
if exist data\raw\rain\bhakra_melt_daily.csv goto done
if %tries% geq 12 goto fail
timeout /t 3600 /nobreak > nul
goto again
:done
echo === pull done at %date% %time%, running verify >> %LOG%
python -m punjabflood.cli verify >> %LOG% 2>&1
echo === verify exit %errorlevel%, running report >> %LOG%
python -m punjabflood.cli report >> %LOG% 2>&1
echo === report exit %errorlevel% at %date% %time% >> %LOG%
exit /b 0
:fail
echo === gave up after %tries% attempts at %date% %time% >> %LOG%
exit /b 1
