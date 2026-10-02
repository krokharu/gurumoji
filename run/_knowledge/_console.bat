@echo off
setlocal EnableExtensions
rem Keep this shortcut on the same launcher, environment, and data directory.
call "%~dp0..\..\run_knowledge_console.bat" %*
exit /b %ERRORLEVEL%
