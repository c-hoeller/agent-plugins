:<<'CMDBLOCK'
@echo off
REM ============================================================================
REM Warden cross-platform hook wrapper — polyglot Windows .cmd / Unix shell.
REM
REM Architecture:
REM   - This file is BOTH a Windows .cmd batch script AND a POSIX shell script.
REM   - The actual hook logic lives in extensionless sibling scripts (e.g.
REM     "session-start") so this wrapper is reusable for future hooks and so
REM     Claude Code's Windows ".sh"-auto-detection (which would prepend "bash")
REM     never interferes.
REM   - On Windows: cmd.exe runs the batch block below, locates bash.exe (Git
REM     for Windows / MSYS2 / Cygwin), and execs the named hook script.
REM   - On POSIX: /bin/sh treats the batch block as a single-quoted heredoc to
REM     ':' (discarded). The quoting prevents any parameter / command / arithmetic
REM     expansion in the body, which is critical because the block contains cmd
REM     syntax that would otherwise be interpreted by sh.
REM
REM Line endings: this file MUST be CRLF on Windows (cmd.exe garbles LF-only
REM .cmd files — @echo off does not take effect, output is mangled). The sh
REM side tolerates CRLF because:
REM   - the unquoted heredoc terminator includes the trailing \r in its
REM     definition AND in each body line, so terminator matching is consistent;
REM   - the exec line ends with a comment (#...) that absorbs the trailing \r
REM     so the path argument to bash never has a stray carriage return.
REM .gitattributes pins this file to eol=crlf to enforce the invariant on every
REM checkout.
REM
REM Falls back to silent exit 0 when no bash is found — the plugin still works
REM (the per-tenet skills auto-load), it just skips the always-on Charter.
REM ============================================================================
setlocal
if "%~1"=="" (
    echo run-hook.cmd: missing script name >&2
    exit /b 1
)
set "HOOK_DIR=%~dp0"
if exist "C:\Program Files\Git\bin\bash.exe" (
    "C:\Program Files\Git\bin\bash.exe" "%HOOK_DIR%%~1" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)
if exist "C:\Program Files (x86)\Git\bin\bash.exe" (
    "C:\Program Files (x86)\Git\bin\bash.exe" "%HOOK_DIR%%~1" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)
where bash >nul 2>nul
if %ERRORLEVEL% equ 0 (
    bash "%HOOK_DIR%%~1" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)
exit /b 0
CMDBLOCK
script="$1"; shift; exec bash "$(dirname "$0")/$script" "$@" #polyglot:absorbs-trailing-CR-on-CRLF-checkouts
