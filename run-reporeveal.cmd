@echo off
setlocal
cd /d "%~dp0"

echo RepoReveal has been renamed to RepoRip.
echo Starting RepoRip...
call "%~dp0run-reporip.cmd"
