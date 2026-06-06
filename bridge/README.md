# 텔레그램 ↔ Claude Code 양방향 제어 브리지

텔레그램에서 메시지를 보내면 **Claude Code(헤드리스 모드)** 가 그 지시를 이 저장소에서 수행하고,
결과를 다시 텔레그램으로 회신합니다. 외부 의존성 없이 Node 내장 모듈만 사용합니다.

```
텔레그램 앱  ──(지시)──▶  이 브리지(롱폴링)  ──▶  claude -p  ──(작업 수행)──▶  저장소
     ▲                                                                          │
     └──────────────────────────(완료 결과·오류)───────────────────────────────┘
```

---

## 1. 봇 만들기 (BotFather)

1. 텔레그램에서 **@BotFather** 를 검색해 대화 시작.
2. `/newbot` 입력 → 봇 이름과 사용자명(`*_bot` 으로 끝나야 함) 지정.
3. BotFather 가 주는 **토큰**(예: `123456789:AAH...`)을 복사.

## 2. 환경설정

```powershell
cd "E:\Project\Application\Korea Election\bridge"
Copy-Item .env.example .env
```

`.env` 를 열어 `TELEGRAM_BOT_TOKEN` 에 위에서 받은 토큰을 붙여넣습니다.
(`TELEGRAM_CHAT_ID` 는 다음 단계에서 채웁니다.)

## 3. 내 chat ID 알아내기 (발견 모드)

`TELEGRAM_CHAT_ID` 를 비워둔 채 봇을 실행하면 "발견 모드"로 동작합니다.

```powershell
npm start
```

그 상태에서 텔레그램으로 **내 봇에게 아무 메시지나** 보내면, 봇이
`당신의 chat ID 는 다음과 같습니다: 12345678` 형식으로 응답합니다.
이 숫자를 복사해 `.env` 의 `TELEGRAM_CHAT_ID` 에 넣고 봇을 재시작합니다(Ctrl+C 후 `npm start`).

이제부터는 **그 chat ID 만** 명령을 내릴 수 있습니다(보안).

## 4. 사용

봇에게 평소처럼 메시지를 보내면 됩니다. 예:

> 개관 페이지 상단 탭 순서를 바꿔줘
> 빌드가 깨지는지 확인해줘
> 방금 커밋한 변경사항 요약해줘

작업 맥락은 자동으로 이어집니다(`--continue`).

### 명령어

| 명령 | 설명 |
|------|------|
| `/new` | 새 대화로 시작(맥락 초기화) |
| `/cancel` (`/stop`) | 진행 중인 작업 중단 / 대기열 비우기 |
| `/status` | 현재 상태(작업 중/대기열/세션/작업폴더) |
| `/help` | 도움말 |

---

## ⚠️ 보안 주의

- 기본 권한 모드는 `skip`(`--dangerously-skip-permissions`)입니다. 즉 봇은 **이 저장소에서
  파일 편집·삭제·셸 명령 실행 등 무엇이든 자동 승인** 합니다. 텔레그램으로 보낸 지시가
  곧바로 실행되므로, **반드시 본인 chat ID 로만 제한**(`TELEGRAM_CHAT_ID`)된 상태로 사용하세요.
- 봇 토큰과 `.env` 는 절대 커밋·공유하지 마세요(이미 `.gitignore` 처리됨).
- 더 보수적으로 쓰려면 `.env` 의 `CLAUDE_PERMISSION=acceptEdits` 로 바꾸면 파일 편집만
  자동 승인하고 위험한 셸 명령은 거부됩니다(대신 일부 작업이 막힐 수 있음).

## 상시 구동 (작업 스케줄러)

PC가 켜져 있는 동안 항상 봇이 돌도록 Windows 작업 스케줄러에 등록합니다.
**로그인 시 자동 시작 · 비정상 종료 시 1분 후 자동 재시작 · 콘솔창 숨김**으로 동작합니다.

> 먼저 위 1~3단계로 `.env`(토큰 + chat ID)를 채워둔 상태여야 합니다.

```powershell
cd "E:\Project\Application\Korea Election\bridge"
.\install-service.ps1            # 작업 등록 (관리자 권한 불필요)
Start-ScheduledTask -TaskName KoreaElectionTelegramBridge   # 지금 바로 시작
```

| 작업 | 명령 |
|------|------|
| 상태 확인 | `Get-ScheduledTask -TaskName KoreaElectionTelegramBridge \| Get-ScheduledTaskInfo` |
| 시작 | `Start-ScheduledTask -TaskName KoreaElectionTelegramBridge` |
| 중지 | `Stop-ScheduledTask -TaskName KoreaElectionTelegramBridge` |
| 제거 | `.\uninstall-service.ps1` |

- 작업은 **현재 로그인 사용자 권한**으로 실행됩니다(Claude 인증 정보가 사용자 프로필에
  있으므로 필수). 비밀번호 저장이 필요 없습니다.
- `.env` 를 수정했다면 작업을 한 번 중지 후 다시 시작해야 반영됩니다.
- **로그인 전(부팅 직후)에도** 돌리려면 작업 스케줄러 GUI에서 해당 작업의 보안 옵션을
  "사용자의 로그온 여부에 관계없이 실행"으로 바꾸면 됩니다(이때는 비밀번호 입력이 필요).

### 수동 실행(스케줄러 없이)

테스트나 일회성으로는 터미널에서 직접 띄워도 됩니다:

```powershell
cd "E:\Project\Application\Korea Election\bridge"; npm start
```
