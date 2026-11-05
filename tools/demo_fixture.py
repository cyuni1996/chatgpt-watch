"""Loopback-only showcase with fictional data. Never connects to Codex or executes tasks."""
import argparse
import hashlib
import json
from pathlib import Path
import ssl
import sys

from aiohttp import web

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge'))
from server import identity

TOKEN = 'demo-only-token'
SESSION = 'showcase-session'


class Demo:
    def __init__(self):
        self.mode = 'idle'
        self.settings = {}
        self.events = []
        self.project = {'id': 'demo-project', 'name': '生活灵感', 'path': 'C:/demo/ideas'}
        self.messages = [
            {'id': 'demo-user', 'role': 'user', 'text': '帮我安排一个轻松的周末。'},
            {'id': 'demo-assistant', 'role': 'assistant', 'phase': 'final',
             'text': '上午去公园散步，下午逛展。\n留一点时间，做喜欢的小项目。'},
        ]

    def state(self):
        approval = {'token': 'demo-confirmation', 'title': '选择周末安排',
                    'details': '演示数据，不会执行电脑任务。',
                    'questions': [{'id': 'plan', 'question': '你更喜欢哪一种？', 'required': True,
                                   'options': [{'label': '公园散步'}, {'label': '参观展览'}]}],
                    'actions': [{'id': 'answer', 'label': '提交选择'}, {'id': 'cancel', 'label': '取消'}]}
        return {'id': SESSION, 'threadId': 'demo-chat', 'title': '周末计划 · 演示',
                'projectId': self.project['id'], 'projectName': self.project['name'],
                'connected': True, 'busy': self.mode == 'busy', 'canInterrupt': self.mode == 'busy',
                'turnId': 'demo-turn' if self.mode == 'busy' else None,
                'approvals': [approval] if self.mode == 'approval' else [],
                'waitingOnApproval': self.mode == 'approval', 'settings': self.settings,
                'messages': self.messages, 'hasOlder': False, 'pinned': False, 'archived': False,
                'capabilities': {'recognition': False, 'synthesis': False}, 'error': ''}

    async def api(self, request):
        path = request.path
        if request.headers.get('Authorization') != 'Bearer ' + TOKEN:
            raise web.HTTPUnauthorized()
        if path == '/api/state':
            return web.json_response(self.state())
        if path == '/api/projects':
            return web.json_response({'projects': [self.project]})
        if path == '/api/models':
            return web.json_response({'models': [
                {'id': 'demo-balanced', 'name': '演示模型 · 均衡', 'default': True, 'defaultEffort': 'medium', 'efforts': ['low', 'medium', 'high']},
                {'id': 'demo-fast', 'name': '演示模型 · 快速', 'defaultEffort': 'low', 'efforts': ['low', 'medium']},
            ]})
        if path == '/api/usage':
            return web.json_response({'groups': [{'name': '演示额度（虚构）', 'windows': [
                {'windowDurationMins': 10080, 'remainingPercent': 82, 'usedPercent': 18, 'resetsAt': None}]}],
                'updatedAt': '2026-11-05T00:00:00Z', 'availableResetCount': None})
        if path == '/api/conversations':
            names = ['周末计划 · 演示', '手表上的小灵感', '读书清单', '下一次旅行', '界面设计笔记']
            chats = [{'threadId': 'demo-chat' if i == 0 else 'demo-chat-' + str(i), 'title': name,
                      'projectId': self.project['id'], 'projectName': self.project['name'],
                      'status': 'idle', 'statusLabel': '空闲', 'busy': False, 'unread': i == 1,
                      'pinned': i == 0, 'archived': False} for i, name in enumerate(names)]
            return web.json_response({'conversations': chats, 'projects': [self.project], 'nextCursor': None})
        if request.method != 'POST':
            raise web.HTTPForbidden()
        data = await request.json()
        self.events.append({'path': path})
        if path == '/api/conversations/status':
            return web.json_response({'states': {key: {'status': 'idle', 'statusLabel': '空闲', 'busy': False} for key in data.get('threadIds', [])}})
        if path == '/api/session/settings':
            self.settings = {'model': data.get('model'), 'thinking': data.get('thinking')}
            return web.json_response(self.state())
        if path == '/api/interrupt':
            if self.mode != 'busy' or data.get('turnId') != 'demo-turn':
                raise web.HTTPConflict()
            self.mode = 'idle'
            return web.json_response({'state': self.state(), 'result': {}})
        if path == '/api/approval':
            if self.mode != 'approval' or data.get('token') != 'demo-confirmation':
                raise web.HTTPConflict()
            self.mode = 'idle'
            return web.json_response({'state': self.state()})
        if path == '/api/session/link':
            return web.json_response(self.state())
        # Do not simulate sending, rename, archive, desktop navigation or speech.
        raise web.HTTPForbidden(text='Showcase is read-only except isolated demo controls')

    async def stage(self, request):
        mode = request.match_info['mode']
        if mode not in ('idle', 'busy', 'approval'):
            raise web.HTTPBadRequest()
        self.mode = mode
        return web.json_response({'mode': mode})


def make_demo():
    demo = Demo()
    app = web.Application()
    app.router.add_get('/fixture/stage/{mode}', demo.stage)
    app.router.add_route('*', '/api/{tail:.*}', demo.api)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18767)
    parser.add_argument('--directory', type=Path, default=ROOT / '.local' / 'showcase')
    args = parser.parse_args()
    _, cert, key = identity(args.directory)
    pairing = {'computerId': 'showcase-computer', 'computerName': '演示电脑', 'token': TOKEN,
               'url': 'https://127.0.0.1:' + str(args.port),
               'certificateSha256': hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text(encoding='utf8'))).hexdigest()}
    (args.directory / 'pairing.json').write_text(json.dumps(pairing), encoding='utf8')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert, key)
    web.run_app(make_demo(), host='127.0.0.1', port=args.port, ssl_context=context, access_log=None)


if __name__ == '__main__':
    main()
