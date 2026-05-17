@echo off
chcp 65001
setlocal enabledelayedexpansion

cd /d "C:\Users\18665\OneDrive\桌面\Qoder\video-downloader"

echo [1/4] 备份hosts...
copy "C:\Windows\System32\drivers\etc\hosts" "C:\Windows\System32\drivers\etc\hosts.backup" >nul

echo [2/4] 解除GitHub限制...
powershell -NoProfile -Command "& {$c=Get-Content 'C:\Windows\System32\drivers\etc\hosts';$n=@();foreach($l in $c){if($l-match'github'-and$l-notmatch'^#'){$n+='#'+$l}else{$n+=$l}};$n|Set-Content 'C:\Windows\System32\drivers\etc\hosts' -Force}"

echo [3/4] 刷新DNS...
ipconfig /flushdns >nul

echo [4/4] 推送到GitHub...
git push origin main
set RESULT=%errorlevel%

echo.
echo 恢复hosts...
copy "C:\Windows\System32\drivers\etc\hosts.backup" "C:\Windows\System32\drivers\etc\hosts" /y >nul
del "C:\Windows\System32\drivers\etc\hosts.backup"

echo.
if %RESULT% equ 0 (
    echo 推送成功！
) else (
    echo 推送失败，错误码：%RESULT%
)

pause
