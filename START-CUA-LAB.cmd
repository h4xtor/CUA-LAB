@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START-CUA-LAB.ps1"
if errorlevel 1 pause
