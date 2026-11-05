"""Async client for the currently running desktop's bundled App Tools gateway."""
import asyncio
import contextlib
import json
import os
from pathlib import Path
import shutil


class RpcError(RuntimeError):
    pass


async def available_models():
    """Read account model metadata, without creating a conversation or a turn."""
    executable = shutil.which('codex')
    if not executable:
        raise RpcError('电脑没有找到 Codex 模型目录')
    env = os.environ.copy()
    for name in ('CODEX_THREAD_ID', 'CODEX_SESSION_ID', 'CODEX_PARENT_THREAD_ID'):
        env.pop(name, None)
    proc = await asyncio.create_subprocess_exec(executable, 'app-server', '--stdio', env=env,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        creationflags=0x08000000 if os.name == 'nt' else 0, limit=8*1024*1024)
    async def write(value):
        proc.stdin.write((json.dumps(value)+'\n').encode()); await proc.stdin.drain()
    async def response(key):
        while line := await asyncio.wait_for(proc.stdout.readline(), 15):
            value = json.loads(line)
            if value.get('id') == key:
                if 'error' in value: raise RpcError(value['error'].get('message', '无法读取模型目录'))
                return value.get('result', {})
        raise RpcError('模型目录连接提前关闭')
    try:
        await write({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'watch_model_catalog', 'version': '0.3.0'}}})
        await response(1)
        await write({'method': 'initialized'})
        await write({'id': 2, 'method': 'model/list', 'params': {'limit': 100, 'includeHidden': False}})
        value = await response(2)
        return [{'id': m.get('model') or m['id'], 'name': m.get('displayName') or m['id'],
                 'default': m.get('isDefault', False), 'defaultEffort': m.get('defaultReasoningEffort'),
                 'efforts': [e['reasoningEffort'] for e in m.get('supportedReasoningEfforts', [])]}
                for m in value.get('data', []) if not m.get('hidden')]
    finally:
        if proc.stdin: proc.stdin.close()
        try:
            await asyncio.wait_for(proc.communicate(), 3)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()


class DesktopClient:
    def __init__(self, transport='desktop_transport.mjs'):
        self.transport = transport
        self.proc = None
        self.reader = None
        self.sequence = 0
        self.pending = {}
        self.ready = False
        self.lock = asyncio.Lock()

    async def start(self):
        async with self.lock:
            if self.ready and self.proc.returncode is None:
                return
            if self.proc and self.proc.returncode is None:
                await self.call('catalog', timeout=15, start=False)
                self.ready = True
                return
            node = shutil.which('node')
            if not node:
                raise RpcError('电脑缺少 Node.js，请安装后启动连接服务')
            self.proc = await asyncio.create_subprocess_exec(
                node, str(Path(__file__).with_name(self.transport)),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, limit=16*1024*1024,
                creationflags=0x08000000 if os.name == 'nt' else 0)
            self.reader = asyncio.create_task(self.read())
            await self.call('catalog', timeout=15, start=False)
            self.ready = True

    async def call(self, method, params=None, caller=None, call_id=None, timeout=35, start=True):
        if start:
            await self.start()
        self.sequence += 1
        key = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[key] = future
        message = {'id': key, 'method': method, 'params': params or {}, 'callerThreadId': caller, 'callId': call_id}
        try:
            self.proc.stdin.write((json.dumps(message, ensure_ascii=False)+'\n').encode('utf-8'))
            await self.proc.stdin.drain()
            return await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(key, None)

    async def read(self):
        proc = self.proc
        try:
            while line := await proc.stdout.readline():
                value = json.loads(line)
                future = self.pending.get(value.get('id'))
                if not future or future.done():
                    continue
                if 'error' in value:
                    future.set_exception(RpcError(value['error']['message']))
                else:
                    future.set_result(value.get('result', {}))
        except (ValueError, OSError, asyncio.CancelledError):
            pass
        finally:
            if self.proc is proc:
                self.ready = False
                for future in self.pending.values():
                    if not future.done():
                        future.set_exception(RpcError('电脑 Codex 连接已断开，请打开后重试'))

    async def close(self):
        self.ready = False
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self.proc.wait(), 3)
            if self.proc.returncode is None:
                self.proc.kill()
        if self.reader:
            self.reader.cancel()
