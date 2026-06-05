# 텔레그램 브리지 봇 작업 스케줄러 등록을 제거한다.
$ErrorActionPreference = 'Stop'
$TaskName = 'KoreaElectionTelegramBridge'

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
  Write-Host "등록된 작업 '$TaskName' 이 없습니다." -ForegroundColor Yellow
  return
}

try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction Stop } catch {}
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "[완료] 작업 '$TaskName' 제거됨." -ForegroundColor Green
