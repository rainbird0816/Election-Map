# 브리지 봇을 숨김 콘솔에서 실행하고 종료될 때까지 대기한다.
# (작업 스케줄러가 이 프로세스를 감시하다가 비정상 종료 시 자동 재시작)
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$node = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $node) { $node = 'C:\Program Files\nodejs\node.exe' }

& $node --env-file=.env telegram-bot.mjs
exit $LASTEXITCODE
