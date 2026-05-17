@echo off
cd /d C:\Users\18665\OneDrive\桌面\Qoder\video-downloader

:: 备份并修改hosts
copy C:\Windows\System32\drivers\etc\hosts C:\Windows\System32\drivers\etc\hosts.qoder_bak >nul
powershell -Command "$c=Get-Content C:\Windows\System32\drivers\etc\hosts;$n=@();foreach($l in $c){if($l-match'github'-and$l-notmatch'^#'){$n+='#'+$l}else{$n+=$l}};$n|Set-Content C:\Windows\System32\drivers\etc\hosts -Force"

:: 推送
echo Pushing to GitHub...
git push origin main
echo.

:: 恢复
copy C:\Windows\System32\drivers\etc\hosts.qoder_bak C:\Windows\System32\drivers\etc\hosts /y >nul
del C:\Windows\System32\drivers\etc\hosts.qoder_bak

echo Done!
pause