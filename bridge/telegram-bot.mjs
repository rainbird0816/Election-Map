#!/usr/bin/env node
// 텔레그램 ↔ Claude Code 양방향 제어 브리지
//
// 텔레그램에서 보낸 메시지를 Claude Code(헤드리스 모드)에 지시로 전달하고,
// 수행 결과를 다시 텔레그램으로 회신한다. 외부 의존성 없이 Node 내장 모듈만 사용.
//
// 실행:  node bridge/telegram-bot.mjs   (환경변수는 bridge/.env 에서 로드)
//        npm --prefix bridge start      (package.json 의 --env-file 사용)
//
// 필요한 환경변수:
//   TELEGRAM_BOT_TOKEN  : BotFather 가 발급한 봇 토큰 (필수)
//   TELEGRAM_CHAT_ID    : 명령을 허용할 chat ID. 미설정 시 "발견 모드"로 동작하여
//                         아무 메시지에나 chat ID 를 알려준다. 콤마로 여러 개 허용.
//   PROJECT_DIR         : Claude Code 가 작업할 디렉터리 (기본: 이 저장소 루트)
//   CLAUDE_PERMISSION   : 'skip'(기본, --dangerously-skip-permissions) | 'acceptEdits' | 'default'
//   CLAUDE_MODEL        : 모델 지정 (선택)
//   CLAUDE_TIMEOUT_MS   : 단일 작업 최대 실행시간 ms (기본 1800000 = 30분)

import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---------- 설정 ----------
const TOKEN = process.env.TELEGRAM_BOT_TOKEN?.trim();
const ALLOWED = (process.env.TELEGRAM_CHAT_ID || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);
const PROJECT_DIR = resolve(process.env.PROJECT_DIR || resolve(__dirname, '..'));
const PERMISSION = (process.env.CLAUDE_PERMISSION || 'skip').trim();
const MODEL = process.env.CLAUDE_MODEL?.trim();
const TIMEOUT_MS = Number(process.env.CLAUDE_TIMEOUT_MS || 30 * 60 * 1000);
const API = `https://api.telegram.org/bot${TOKEN}`;

if (!TOKEN) {
  console.error('[오류] TELEGRAM_BOT_TOKEN 이 설정되지 않았습니다. bridge/.env 를 확인하세요.');
  process.exit(1);
}

// ---------- 상태 ----------
let offset = 0;            // getUpdates 오프셋
let busy = false;         // Claude 작업 진행 중 여부
let hasSession = false;   // 이어가기(--continue) 가능한 세션 존재 여부
let current = null;       // 진행 중인 child process
const queue = [];         // 대기 중인 {chatId, text}

// ---------- 텔레그램 API ----------
async function tg(method, body) {
  const res = await fetch(`${API}/${method}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(`${method} 실패: ${data.description}`);
  return data.result;
}

// 4096자 제한 → 안전하게 3900자씩 분할 전송
async function send(chatId, text) {
  const MAX = 3900;
  const s = String(text ?? '').trim() || '(빈 응답)';
  for (let i = 0; i < s.length; i += MAX) {
    await tg('sendMessage', { chat_id: chatId, text: s.slice(i, i + MAX) }).catch((e) =>
      console.error('전송 실패:', e.message)
    );
  }
}

async function typing(chatId) {
  await tg('sendChatAction', { chat_id: chatId, action: 'typing' }).catch(() => {});
}

function authorized(chatId) {
  // CHAT_ID 미설정 시(발견 모드)에는 실행을 막고 안내만 한다 → authorized=false 취급
  return ALLOWED.length > 0 && ALLOWED.includes(String(chatId));
}

// ---------- Claude Code 실행 ----------
function runClaude(prompt) {
  return new Promise((done) => {
    const args = ['-p', '--output-format', 'text'];
    if (PERMISSION === 'skip') args.push('--dangerously-skip-permissions');
    else if (PERMISSION === 'acceptEdits') args.push('--permission-mode', 'acceptEdits');
    if (MODEL) args.push('--model', MODEL);
    if (hasSession) args.push('--continue');

    const child = spawn('claude', args, {
      cwd: PROJECT_DIR,
      shell: process.platform === 'win32', // Windows: claude.cmd 해석을 위해 셸 경유
    });
    current = child;

    let out = '';
    let err = '';
    const timer = setTimeout(() => {
      err += `\n[시간초과] ${TIMEOUT_MS}ms 초과로 중단했습니다.`;
      child.kill();
    }, TIMEOUT_MS);

    child.stdout.on('data', (d) => (out += d));
    child.stderr.on('data', (d) => (err += d));
    child.on('error', (e) => {
      clearTimeout(timer);
      current = null;
      done({ ok: false, text: `실행 오류: ${e.message}` });
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      current = null;
      hasSession = true; // 다음 메시지는 --continue 로 맥락 이어가기
      if (code === 0) done({ ok: true, text: out });
      else done({ ok: false, text: (out + '\n' + err).trim() || `종료 코드 ${code}` });
    });

    // 프롬프트는 stdin 으로 전달 → 따옴표/특수문자 이스케이프 문제 회피
    child.stdin.write(prompt);
    child.stdin.end();
  });
}

// ---------- 작업 큐 ----------
async function drain() {
  if (busy || queue.length === 0) return;
  busy = true;
  const { chatId, text } = queue.shift();
  await send(chatId, `🤖 작업을 시작합니다…\n──────────\n${text.slice(0, 200)}`);
  await typing(chatId);
  const keepTyping = setInterval(() => typing(chatId), 5000);
  try {
    const r = await runClaude(text);
    clearInterval(keepTyping);
    const prefix = r.ok ? '✅ 완료\n──────────\n' : '⚠️ 오류\n──────────\n';
    await send(chatId, prefix + r.text);
  } catch (e) {
    clearInterval(keepTyping);
    await send(chatId, `⚠️ 예외: ${e.message}`);
  } finally {
    busy = false;
    setImmediate(drain);
  }
}

// ---------- 메시지 처리 ----------
const HELP = [
  '🤖 Claude Code 텔레그램 제어 봇',
  '',
  '• 그냥 메시지를 보내면 그대로 Claude Code 에 지시로 전달됩니다.',
  '• 작업 맥락은 자동으로 이어집니다(--continue).',
  '',
  '명령어:',
  '/new — 새 대화로 시작(맥락 초기화)',
  '/cancel — 진행 중인 작업 중단',
  '/status — 현재 상태 확인',
  '/help — 이 도움말',
].join('\n');

async function handle(msg) {
  const chatId = msg.chat?.id;
  const text = (msg.text || '').trim();
  if (!chatId || !text) return;

  // 발견 모드: CHAT_ID 미설정 시 chat ID 만 알려준다
  if (ALLOWED.length === 0) {
    await send(
      chatId,
      `👋 당신의 chat ID 는 다음과 같습니다:\n\n${chatId}\n\n` +
        `이 값을 bridge/.env 의 TELEGRAM_CHAT_ID 에 넣고 봇을 재시작하세요.`
    );
    return;
  }

  if (!authorized(chatId)) {
    await send(chatId, `⛔ 허가되지 않은 사용자입니다. (chat ID: ${chatId})`);
    console.warn(`허가되지 않은 접근: ${chatId}`);
    return;
  }

  // 명령어 처리
  if (text === '/start' || text === '/help') return send(chatId, HELP);
  if (text === '/status') {
    return send(
      chatId,
      `상태: ${busy ? '작업 중' : '대기'} | 대기열: ${queue.length} | ` +
        `세션: ${hasSession ? '이어가기 가능' : '새 세션'} | 작업폴더: ${PROJECT_DIR}`
    );
  }
  if (text === '/new') {
    hasSession = false;
    return send(chatId, '🆕 새 대화로 시작합니다. 다음 지시는 새 세션에서 수행됩니다.');
  }
  if (text === '/cancel' || text === '/stop') {
    if (current) {
      current.kill();
      return send(chatId, '🛑 진행 중인 작업을 중단했습니다.');
    }
    queue.length = 0;
    return send(chatId, '대기열을 비웠습니다. (진행 중인 작업 없음)');
  }
  if (text.startsWith('/')) return send(chatId, `알 수 없는 명령어입니다.\n\n${HELP}`);

  // 일반 지시 → 큐에 적재
  queue.push({ chatId, text });
  if (busy) await send(chatId, `⏳ 대기열에 추가했습니다. (앞에 ${queue.length - 1}건)`);
  drain();
}

// ---------- 롱폴링 루프 ----------
async function poll() {
  console.log(`[브리지] 폴링 시작. 작업폴더=${PROJECT_DIR}`);
  console.log(
    ALLOWED.length === 0
      ? '[발견 모드] TELEGRAM_CHAT_ID 미설정 → 메시지를 보내면 chat ID 를 알려줍니다.'
      : `[보안] 허용된 chat ID: ${ALLOWED.join(', ')}`
  );
  // 시작 시 밀린 메시지 비우기
  try {
    const init = await tg('getUpdates', { offset: -1, timeout: 0 });
    if (init.length) offset = init[init.length - 1].update_id + 1;
  } catch (e) {
    console.error('초기화 실패:', e.message);
  }

  while (true) {
    try {
      const updates = await tg('getUpdates', { offset, timeout: 50 });
      for (const u of updates) {
        offset = u.update_id + 1;
        if (u.message) handle(u.message).catch((e) => console.error('처리 오류:', e.message));
      }
    } catch (e) {
      console.error('폴링 오류:', e.message);
      await new Promise((r) => setTimeout(r, 3000));
    }
  }
}

poll();
