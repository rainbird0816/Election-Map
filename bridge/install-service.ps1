# 텔레그램 브리지 봇을 Windows 작업 스케줄러에 등록한다.
#   - 로그인 시 자동 시작
#   - 콘솔창 숨김(-WindowStyle Hidden)
#   - 비정상 종료 시 1분 간격으로 자동 재시작(최대 999회)
#   - 노트북 배터리 상태와 무관하게 동작
#
# 사용:  관리자 권한 불필요. PowerShell 에서
#          cd "E:\Korea Election\bridge"; .\install-service.ps1
# 제거:  .\uninstall-service.ps1

$ErrorActionPreference = 'Stop'
$TaskName = 'KoreaElectionTelegramBridge'
$BridgeDir = $PSScriptRoot
$RunScript = Join-Path $BridgeDir 'run.ps1'
$EnvFile = Join-Path $BridgeDir '.env'

# --- 사전 점검 ---
if (-not (Test-Path $EnvFile)) {
  Write-Warning ".env 파일이 없습니다: $EnvFile"
  Write-Host  "  먼저 'Copy-Item .env.example .env' 후 토큰/chat ID를 채우세요." -ForegroundColor Yellow
}
else {
  $envText = Get-Content $EnvFile -Raw
  if ($envText -notmatch '(?m)^\s*TELEGRAM_BOT_TOKEN\s*=\s*\S') {
    Write-Warning ".env 에 TELEGRAM_BOT_TOKEN 값이 비어 있습니다. 채운 뒤 다시 등록하세요."
  }
}

$psExe = Join-Path $PSHOME 'powershell.exe'
$action = New-ScheduledTaskAction -Execute $psExe `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$RunScript`"" `
  -WorkingDirectory $BridgeDir

# 현재 로그인 사용자 컨텍스트에서 로그인 시 실행 (claude 인증은 사용자 프로필에 있으므로 필수)
$user = "$env:USERDOMAIN\$env:USERNAME"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -RestartCount 999 `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
  -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Principal $principal -Settings $settings -Force | Out-Null

Write-Host ""
Write-Host "[완료] 작업 '$TaskName' 등록됨." -ForegroundColor Green
Write-Host "  - 로그인 시 자동 시작 / 비정상 종료 시 1분 후 자동 재시작 / 콘솔 숨김"
Write-Host ""
Write-Host "지금 바로 시작하려면:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
Write-Host "상태 확인:        Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo"
Write-Host "중지:             Stop-ScheduledTask  -TaskName $TaskName"
Write-Host "제거:             .\uninstall-service.ps1"
