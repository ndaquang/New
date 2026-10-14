@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Danh thiep
rem Lần đầu: tạo môi trường Python riêng và cài thư viện (mất khoảng 5-10 phút).
if not exist ".venv\Scripts\python.exe" (
  echo Dang tao moi truong Python...
  py -3.11 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (
    echo Khong tim thay Python 3.11. Hay cai tu https://www.python.org/downloads/release/python-3119/
    pause
    exit /b 1
  )
)
if not exist ".venv\.da-cai" (
  echo Dang cai thu vien (chi lam 1 lan)...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || (pause & exit /b 1)
  echo ok> ".venv\.da-cai"
)
".venv\Scripts\python.exe" DanhThiep.py %*
if errorlevel 1 pause
