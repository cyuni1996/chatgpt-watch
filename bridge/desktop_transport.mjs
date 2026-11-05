// Local desktop connection, using the bundled Codex App Tools pipe protocol.
// This process never starts a second Codex runtime or exposes the pipe to the LAN.
import net from 'node:net';
import fs from 'node:fs/promises';
import readline from 'node:readline';
import {randomUUID} from 'node:crypto';

const LIMIT = 8 * 1024 * 1024;
const instanceId = randomUUID();
let socket, connecting, buffer = Buffer.alloc(0), nextId = 1, catalog;
const pending = new Map();
function fail(error) {
  socket?.destroy(); socket = undefined; catalog = undefined; buffer = Buffer.alloc(0);
  for (const {reject, timer} of pending.values()) { clearTimeout(timer); reject(error); }
  pending.clear();
}
function frame(value) {
  const data = Buffer.from(JSON.stringify(value));
  if (data.length > LIMIT) throw Error('Desktop request is too large');
  const header = Buffer.alloc(4); header.writeUInt32LE(data.length);
  return Buffer.concat([header, data]);
}
async function connectPipe(path) {
  return await new Promise((resolve, reject) => {
    const candidate = net.createConnection(path);
    const timer = setTimeout(() => { candidate.destroy(); reject(Error('Desktop connection timed out')); }, 2500);
    candidate.once('error', error => { clearTimeout(timer); reject(error); });
    candidate.once('connect', () => { clearTimeout(timer); resolve(candidate); });
  });
}
async function connect() {
  if (socket && !socket.destroyed) return;
  if (connecting) return connecting;
  connecting = (async () => {
    const paths = new Set();
    if (process.env.CODEX_APP_TOOLS_PIPE_PATH) paths.add(process.env.CODEX_APP_TOOLS_PIPE_PATH);
    if (process.platform === 'win32') {
      const names = await fs.readdir('\\\\.\\pipe\\');
      for (const name of names) if (name.startsWith('codex-app-tools-')) paths.add('\\\\.\\pipe\\' + name);
    }
    for (const path of paths) {
      try { socket = await connectPipe(path); break; } catch { /* Try another live desktop. */ }
    }
    if (!socket) throw Error('请先打开电脑上的 Codex，再重试连接');
    const current = socket;
    socket.on('data', chunk => {
      if (socket !== current) return;
      buffer = Buffer.concat([buffer, chunk]);
      while (buffer.length >= 4) {
        const length = buffer.readUInt32LE(0);
        if (length > LIMIT) { fail(Error('Invalid desktop response length')); return; }
        if (buffer.length < length + 4) break;
        let value;
        try { value = JSON.parse(buffer.subarray(4, length + 4).toString('utf8')); }
        catch { fail(Error('Invalid desktop response')); return; }
        buffer = buffer.subarray(length + 4);
        const request = pending.get(value.id);
        if (!request) continue;
        pending.delete(value.id); clearTimeout(request.timer);
        if (value.error) request.reject(Error(value.error.message)); else request.resolve(value.result);
      }
    });
    socket.on('error', error => { if (socket === current) fail(error); });
    socket.on('close', () => { if (socket === current) fail(Error('电脑 Codex 已断开')); });
  })().finally(() => { connecting = undefined; });
  return connecting;
}
async function request(method, params) {
  await connect();
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(Error('Desktop request timed out; delivery state may be unknown')); }, 30000);
    pending.set(id, {resolve, reject, timer});
    socket.write(frame({jsonrpc: '2.0', id, method, params}));
  });
}
async function tools() {
  if (!catalog) catalog = (await request('tools/list', {threadStartKind: 'all'})).tools;
  return catalog;
}
async function handle(message) {
  if (message.method === 'catalog') return await tools();
  const list = await tools();
  const tool = list.find(item => item.name === message.method);
  if (!tool) throw Error('The desktop does not provide ' + message.method);
  if (!message.callerThreadId) throw Error('A real caller conversation is required');
  const value = await request('tools/call', {
    arguments: message.params ?? {}, callerSource: 'codex', hostId: 'local',
    callId: message.callId ?? `watch-${instanceId}-${message.id}`, namespace: tool.namespace,
    threadId: message.callerThreadId, tool: tool.name,
    turnId: `watch-interaction-${instanceId}-${message.id}`,
  });
  const text = (value.contentItems ?? []).filter(item => item.type === 'inputText').map(item => item.text).join('\n');
  if (!value.success) throw Error(text || 'Desktop operation failed');
  let parsed;
  try { parsed = JSON.parse(text); } catch { return {text}; }
  if (message.method === 'read_thread') {
    for (const turn of parsed.turns ?? []) {
      turn.items = (turn.items ?? []).filter(item => item.type === 'userMessage' || item.type === 'agentMessage' || (item.type === 'functionCallOutput' && item.namespace === 'codex_app' && ['send_message_to_thread', 'create_thread'].includes(item.name)));
    }
  }
  return parsed;
}
const lines = readline.createInterface({input: process.stdin});
lines.on('line', line => {
  let value;
  try { value = JSON.parse(line); } catch { return; }
  handle(value).then(result => process.stdout.write(JSON.stringify({id: value.id, result}) + '\n'))
    .catch(error => process.stdout.write(JSON.stringify({id: value.id, error: {message: error.message}}) + '\n'));
});
lines.on('close', () => { fail(Error('Companion closed')); process.exit(0); });
