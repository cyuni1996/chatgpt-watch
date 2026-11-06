"""HTTPS Wear OS companion sharing the running Codex desktop conversation."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime as dt
import io
import html
import json
import logging
import os
from pathlib import Path
import secrets
import ssl
import tempfile
import uuid
import wave

from aiohttp import web
from desktop import DesktopClient, RpcError, available_models
from controls import DesktopControls, approval_view, approval_response, fingerprint
from usage import usage_view
from projects import local_projects, project_for_thread, thread_status
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[2]
LOCAL = Path(os.environ.get('WATCH_CHAT_HOME', ROOT / '.local'))
LOG = logging.getLogger('watch-chat')


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def question_reply_text(text):
    start,end='<send_user_message_question_reply>','</send_user_message_question_reply>'
    wrapped=text.strip()
    if wrapped.startswith(start) and wrapped.endswith(end):
        try:
            values=json.loads(wrapped[len(start):-len(end)])
            replies=values if isinstance(values,list) else [values]
            if replies and all(isinstance(r,dict) and isinstance(r.get('answer'),str) for r in replies):
                return '\n\n'.join((str(r.get('question','')).strip()+'\n'+r['answer']).strip() for r in replies)
        except (ValueError,TypeError):pass
    return text


def identity(directory=LOCAL):
    directory.mkdir(parents=True, exist_ok=True)
    config_path = directory / 'connection.json'
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding='utf-8'))
    else:
        config = {'token': secrets.token_urlsafe(32), 'port': 8766}
    cert_path, key_path = directory / 'server.pem', directory / 'server-key.pem'
    if not cert_path.exists() or not key_path.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Watch Codex Companion')])
        now = dt.datetime.now(dt.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now-dt.timedelta(minutes=5)).not_valid_after(now+dt.timedelta(days=3650))
                .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                .sign(key, hashes.SHA256()))
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    config['certificateSha256'] = cert.fingerprint(hashes.SHA256()).hex()
    atomic_json(config_path, config)
    return config, cert_path, key_path


class Companion:
    def __init__(self, token, directory=LOCAL, cwd=ROOT, desktop=None, controls=None):
        self.token, self.directory, self.cwd = token, Path(directory), str(cwd)
        self.path = self.directory / 'history.json'
        self.sessions = {}
        self.work = set()
        self.speech_lock = asyncio.Lock()
        self.speech = {'recognition': False, 'synthesis': False}
        self.desktop = desktop or DesktopClient()
        self.controls = controls if controls is not None else (DesktopControls() if desktop is None else None)
        self.control_states = {}
        self.usage_cache = None
        self.usage_time = -30
        self.usage_lock = asyncio.Lock()
        self.sync_locks = {}
        self.send_locks = {}
        self.question_locks = {}
        self.last_refresh = {}
        self.read_turn_limits = {}
        self.project_catalog = None
        self.project_time = -60
        self.project_lock = asyncio.Lock()
        self.thread_summaries = {}
        self.thread_metadata = {}
        self.recent_cache = None
        self.recent_time = -5
        self.recent_lock = asyncio.Lock()
        self.desktop_online = False
        self.model_catalog = None
        self.model_catalog_time = 0
        self.pinned_ids = set()
        self.thread_titles = {}
        self.thread_archived = {}
        self.pins_time = -30
        if self.path.exists():
            self.sessions = json.loads(self.path.read_text(encoding='utf-8')).get('sessions', {})
        self.anchor = next((s['threadId'] for s in self.sessions.values() if s.get('threadId')), None) or os.environ.get('CODEX_THREAD_ID')
        for session in self.sessions.values():
            session.setdefault('turns', {})
            session.setdefault('outbox', {})
            session.setdefault('olderCursor', None)
            session.setdefault('syncInitialized', False)
            session.setdefault('settings', {})
            for outgoing in session['outbox'].values():
                if outgoing['state'] == 'dispatching':
                    outgoing['state'] = 'unknown'
            session['busy'] = False
            session['turnId'] = None
        if not self.sessions:
            self.new_session()

    def save(self):
        atomic_json(self.path, {'sessions': self.sessions, 'schemaVersion': 2})

    def new_session(self, project=None):
        key = str(uuid.uuid4())
        self.sessions[key] = {'id': key, 'threadId': None, 'turnId': None, 'title': '新的对话', 'messages': [], 'turns': {}, 'outbox': {}, 'olderCursor': None, 'syncInitialized': False, 'settings': {}, 'busy': False, 'error': '', 'updatedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'requests': []}
        self.sessions[key].update(projectId=project['id'] if project else None,projectName=project['name'] if project else None)
        self.save()
        return key

    def session(self, key):
        if not key:
            key = max(self.sessions, key=lambda k: self.sessions[k]['updatedAt'])
        if key not in self.sessions:
            raise web.HTTPNotFound(text='对话不存在')
        return self.sessions[key]

    def snapshot(self, session):
        excluded = ('requests', 'turns', 'outbox', 'olderCursor', 'syncInitialized')
        control = self.control_states.get(session['id'], {})
        approvals = [approval_view(r,control.get('contexts',{}).get(str(r['id']))) for r in control.get('requests',[]) if r.get('params',{}).get('threadId') == session.get('threadId') and not (r.get('method')=='watch/asyncQuestion' and 'native-question-'+fingerprint(r) in session['outbox'])]
        return {k: v for k, v in session.items() if k not in excluded} | {
            'error': session.get('error') or ('本页工具输出过长，已省略；完整内容请在电脑查看。' if any(t.get('outputsOmitted') for t in session['turns'].values()) else ''),
            'approvals': approvals, 'canInterrupt': bool(control.get('available') and control.get('turnId')), 'connected': self.desktop_online,
            'controlAvailable': bool(control.get('available')), 'controlError': control.get('error',''),
            'turnId': control.get('turnId'), 'waitingOnApproval': bool(approvals) or session.get('waitingOnApproval',False),
            'busy': bool(session.get('busy') or control.get('turnId')),
            'speech': self.speech, 'syncMode': 'desktop', 'hasOlder': bool(session['olderCursor']),
        }

    async def refresh_control(self, session):
        if not self.controls or not session.get('threadId'):
            self.control_states[session['id']] = {}
            return
        self.control_states[session['id']] = await self.controls.read(session['threadId'])

    async def usage(self, force=False):
        async with self.usage_lock:
            now=asyncio.get_running_loop().time()
            if not force and self.usage_cache and now-self.usage_time<30:return self.usage_cache
            try:
                value=await self.desktop_call('get_usage_limits',{})
                self.usage_cache=usage_view(value);self.usage_time=now
                return self.usage_cache
            except (RpcError,OSError,asyncio.TimeoutError):
                if self.usage_cache:return self.usage_cache|{'stale':True,'error':'暂时无法刷新，以下为上次读取的额度'}
                raise web.HTTPServiceUnavailable(text='暂时无法读取额度，请确认电脑已登录后重试')

    async def start(self, app=None):
        with contextlib.suppress(Exception):
            self.speech = await self.run_speech('status')
        try:
            await self.desktop.start()
            self.desktop_online = True
        except Exception as e:
            LOG.warning('Desktop startup failed: %s', type(e).__name__)

    def launch(self, coro):
        task = asyncio.create_task(coro)
        self.work.add(task)
        task.add_done_callback(self.work.discard)
        return task

    async def desktop_call(self, name, params, session=None, call_id=None):
        caller = (session or {}).get('threadId') or self.anchor
        if not caller:
            raise RpcError('缺少初始桌面对话，请从电脑重新完成首次连接设置')
        try:
            value = await self.desktop.call(name, params, caller=caller, call_id=call_id)
            self.desktop_online = True
            return value
        except Exception:
            self.desktop_online = False
            raise

    @staticmethod
    def messages_from_turn(turn):
        messages = []
        for item in turn.get('items', []):
            kind = item.get('type')
            if kind == 'userMessage':
                text = '\n'.join(c.get('text', '') for c in item.get('content', []) if c.get('type') == 'text')
                if not text and item.get('content'):
                    text = '［图片或附件消息，请在电脑查看］'
                role = 'user'
            elif kind == 'agentMessage':
                text, role = item.get('text', ''), 'assistant'
                if text.strip() == '<EXTERNAL SESSION IMPORTED>':
                    continue
            elif kind == 'functionCallOutput' and item.get('namespace') == 'codex_app' and item.get('name') in ('send_message_to_thread', 'create_thread'):
                output = item.get('output', {})
                wrapped = output.get('text', '') if isinstance(output, dict) else ''
                if not wrapped.startswith('<codex_delegation>') or '<input>' not in wrapped or '</input>' not in wrapped:
                    continue
                text = html.unescape(wrapped.partition('<input>')[2].rpartition('</input>')[0])
                role = 'user'
            else:
                continue
            if not text:
                continue
            if role == 'user':text=question_reply_text(text)
            if item.get('textTruncated'):
                text += '\n［长消息已截取，可在电脑查看全文］'
            messages.append({'id': item['id'], 'role': role, 'text': text, 'phase': item.get('phase'), 'turnId': turn['id']})
        return messages

    def rebuild(self, session):
        turns = sorted(session['turns'].values(), key=lambda t: (t.get('startedAt') or 0, t['id']))
        messages = [m for turn in turns for m in self.messages_from_turn(turn)]
        known_users = {m['id']: m for m in messages if m['role'] == 'user'}
        pending = False
        for request_id, outgoing in session['outbox'].items():
            if outgoing['state'] == 'confirmed':
                continue
            visible_text=question_reply_text(outgoing['text'])
            delivered = any(m['text'] == visible_text and key not in outgoing['knownUserIds'] for key, m in known_users.items())
            if delivered:
                outgoing['state'] = 'confirmed'
                continue
            messages.append({'id': 'watch-'+request_id, 'role': 'user', 'text': visible_text, 'delivery': outgoing['state']})
            pending |= outgoing['state'] in ('dispatching', 'accepted')
        session['messages'] = messages
        session['busy'] = bool(session.get('desktopBusy')) or pending
        if any(o['state'] == 'unknown' for o in session['outbox'].values()):
            session['error'] = '上一条消息发送结果尚未确认，请先在电脑核对；系统不会自动重复发送。'
        elif not session['busy']:
            session['error'] = session.get('desktopError', '')

    async def read_thread_page(self, session, cursor=None):
        """Keep forwarded prompts, while shrinking only oversized read-only pages."""
        thread_id=session['threadId']
        limit=self.read_turn_limits.get(thread_id,10)
        include_outputs=True
        while True:
            params={'threadId':thread_id,'hostId':'local','turnLimit':limit,
                    'maxOutputCharsPerItem':20000,'includeOutputs':include_outputs}
            if cursor:params['cursor']=cursor
            try:
                value=await self.desktop_call('read_thread',params,session)
                self.read_turn_limits[thread_id]=limit
                if not include_outputs:
                    for turn in value.get('turns',[]):turn['outputsOmitted']=True
                return value
            except RpcError as error:
                if 'tool response exceeds the size limit' not in str(error).lower():raise
                if limit>1:limit=max(1,limit//2)
                elif include_outputs:include_outputs=False
                else:raise RpcError('这段对话的单条记录过长，暂时无法在手表读取，请在电脑查看。') from error

    async def read_thread_metadata(self, thread_id):
        return await self.desktop_call('read_thread',{'threadId':thread_id,'hostId':'local',
            'turnLimit':1,'maxOutputCharsPerItem':1,'includeOutputs':False})

    async def projects(self, force=False):
        async with self.project_lock:
            now=asyncio.get_running_loop().time()
            if force or self.project_catalog is None or now-self.project_time>=60:
                self.project_catalog=local_projects(await self.desktop_call('list_projects',{}))
                self.project_time=now
            return self.project_catalog

    async def selected_project(self, project_id):
        if project_id is None:return None
        if not isinstance(project_id,str) or not project_id:raise web.HTTPBadRequest(text='请选择有效项目')
        project=next((p for p in await self.projects(force=True) if p['id']==project_id),None)
        if not project:raise web.HTTPConflict(text='这个项目已不可用，请重新选择项目')
        return project

    async def set_project(self, session, project_id):
        async with self.send_locks.setdefault(session['id'],asyncio.Lock()):
            if session.get('threadId') or session.get('outbox'):
                raise web.HTTPConflict(text='已有电脑会话不能在这里更换项目，请新建聊天')
            project=await self.selected_project(project_id)
            session.update(projectId=project['id'] if project else None,projectName=project['name'] if project else None)
            self.save()

    async def recent_threads(self):
        async with self.recent_lock:
            now=asyncio.get_running_loop().time()
            if self.recent_cache is None or now-self.recent_time>=5:
                self.recent_cache=await self.desktop_call('list_threads',{'limit':50})
                self.recent_time=now
                for summary in self.thread_summaries.values():summary.pop('isUnread',None)
                self.remember_titles(self.recent_cache)
            return self.recent_cache

    async def conversation_states(self, ids):
        if not isinstance(ids,list) or len(ids)>1000 or any(not isinstance(i,str) or len(i)>100 for i in ids):
            raise web.HTTPBadRequest(text='会话编号列表无效')
        self.remember_titles(await self.recent_threads())
        now=asyncio.get_running_loop().time();result={}
        for thread_id in dict.fromkeys(ids):
            summary=self.thread_summaries.get(thread_id,{})
            metadata=None
            if summary.get('status')=='active':
                cached=self.thread_metadata.get(thread_id)
                if cached and now-cached[0]<5:metadata=cached[1]
                else:
                    try:
                        metadata=(await self.read_thread_metadata(thread_id))['thread']
                        self.thread_metadata[thread_id]=(now,metadata)
                    except RpcError:metadata=None
            result[thread_id]=thread_status(summary,metadata)
        return result

    async def refresh(self, session, force=False, older=False):
        if not session['threadId']:
            await self.desktop.start()
            self.desktop_online = True
            self.rebuild(session)
            return
        lock = self.sync_locks.setdefault(session['id'], asyncio.Lock())
        async with lock:
            now = asyncio.get_running_loop().time()
            if not force and now-self.last_refresh.get(session['id'], -10) < .75:
                return
            if older:
                if not session['olderCursor']:
                    return
            value = await self.read_thread_page(session,session['olderCursor'] if older else None)
            thread, page = value['thread'], value.get('page', {})
            previous = json.dumps(session, ensure_ascii=False, sort_keys=True)
            self.thread_metadata[session['threadId']]=(now,thread)
            summary=dict(self.thread_summaries.get(session['threadId'],{}))
            if 'projectId' not in summary and session.get('projectId'):
                summary['projectId']=session['projectId']
            summary.update({k:thread[k] for k in ('projectId','cwd') if k in thread})
            project=project_for_thread(summary,await self.projects())
            session.update(projectId=project['id'] if project else None,projectName=project['name'] if project else None)
            incoming = value.get('turns', [])
            known_before = set(session['turns'])
            if not older:
                incoming_ids = {t['id'] for t in incoming}
                if not page.get('hasMore'):
                    session['turns'] = {}
                elif incoming:
                    cutoff = min((t.get('startedAt') or 0, t['id']) for t in incoming)
                    session['turns'] = {key: t for key, t in session['turns'].items() if key in incoming_ids or (t.get('startedAt') or 0, key) < cutoff}
            for turn in incoming:
                session['turns'][turn['id']] = {k: turn[k] for k in ('id', 'status', 'startedAt', 'error', 'items', 'outputsOmitted') if k in turn}
            gap = bool(incoming) and incoming[-1]['id'] not in known_before
            if not session['syncInitialized'] or older or gap or not page.get('hasMore'):
                session['olderCursor'] = page.get('nextCursor') if page.get('hasMore') else None
            status = thread.get('status', {})
            if now-self.pins_time > 15:
                recent = await self.desktop_call('list_threads', {'limit': 50}, session)
                self.remember_titles(recent)
                self.pinned_ids = {t['id'] for t in recent.get('pinnedThreads', []) if t.get('kind', 'codex') == 'codex' and t.get('hostId', 'local') == 'local'}
                self.pins_time = now
            session['pinned'] = session['threadId'] in self.pinned_ids
            if session['threadId'] in self.thread_archived:
                session['archived'] = self.thread_archived[session['threadId']]
            session['desktopBusy'] = status.get('type') == 'active'
            session['waitingOnApproval'] = 'waitingOnApproval' in status.get('activeFlags', [])
            session['title'] = thread.get('title') or self.thread_titles.get(session['threadId']) or session.get('title') or '未命名对话'
            session['updatedAt'] = dt.datetime.fromtimestamp(thread['updatedAt'], dt.timezone.utc).isoformat() if thread.get('updatedAt') else session['updatedAt']
            session['syncInitialized'] = True
            if not older:
                latest = value.get('turns', [])[:1]
                session['desktopBusy'] |= any(t.get('status') in ('inProgress', 'in_progress', 'running') for t in latest)
                session['desktopError'] = next((t['error'].get('message', '') for t in latest if isinstance(t.get('error'), dict)), '')
            self.rebuild(session)
            self.last_refresh[session['id']] = now
            if previous != json.dumps(session, ensure_ascii=False, sort_keys=True):
                self.save()

    async def submit(self, session, text, request_id, allow_followup=False, async_question=None):
        lock = self.send_locks.setdefault(session['id'], asyncio.Lock())
        async with lock:
            if request_id in session['requests']:
                return
            await self.refresh(session, force=True)
            pending_send = any(o['state'] in ('dispatching', 'accepted') for o in session['outbox'].values())
            if session['busy'] and (not allow_followup or pending_send):
                raise web.HTTPConflict(text='电脑或手表正在回复这段对话，请等本次完成后再发送')
            if session.get('archived'):
                raise web.HTTPConflict(text='这段对话已归档，请先恢复')
            known = [m['id'] for m in session['messages'] if m['role'] == 'user']
            target=None
            if not session.get('threadId'):
                project=await self.selected_project(session.get('projectId'))
                target={'type':'project','projectId':project['id'],'environment':{'type':'local'}} if project else {'type':'projectless','directoryName':'watch-chat'}
            session['requests'].append(request_id)
            session['outbox'][request_id] = {'text': text, 'knownUserIds': known, 'state': 'dispatching', 'settings': dict(session.get('settings', {}))}
            if target:session['outbox'][request_id]['target']=target
            session['error'] = ''
            self.rebuild(session)
            self.save()
            return self.launch(self.dispatch(session, text, request_id, async_question))

    async def respond_control(self,session,token,action,answers):
        async with self.question_locks.setdefault((session['id'],token),asyncio.Lock()):
            key='native-question-'+token
            outgoing=session['outbox'].get(key)
            if outgoing:
                encoded=json.loads(outgoing['text'].partition('>')[2].rpartition('<')[0])
                previous={r['questionItemId']:r['answer'] for r in encoded}
                if action!='answer' or previous!=answers:raise web.HTTPConflict(text='这项回复已提交，不能改选后重复发送')
                if outgoing['state']=='unknown':raise web.HTTPServiceUnavailable(text='回复发送结果待核对；系统不会自动重复提交，请在电脑查看')
                return {'ok':True,'alreadySubmitted':True}
            value=await self.controls.read(session['threadId'],True)
            request=next((r for r in value.get('requests',[]) if r.get('method')=='watch/asyncQuestion' and r.get('params',{}).get('threadId')==session['threadId'] and fingerprint(r)==token),None)
            if request is None:return await self.controls.respond(session['threadId'],token,action,answers)
            response=approval_response(request,action,answers)
            replies=[{'questionItemId':q['id'],'question':q['question'],'answer':response['answers'][q['id']]['answers'][0]} for q in request['params']['questions']]
            prompt='<send_user_message_question_reply>\n'+json.dumps(replies,ensure_ascii=False)+'\n</send_user_message_question_reply>'
            request_id=request['id']
            expected=value.get('requestJson',{}).get(str(request_id)) or json.dumps(request,ensure_ascii=False,separators=(',',':'))
            native_answer={'threadId':session['threadId'],'requestId':request_id,'expectedRequest':expected,'answers':answers}
            task=await self.submit(session,prompt,key,allow_followup=True,async_question=native_answer)
            if task and await task == 'notPending':
                raise web.HTTPConflict(text='问题已处理或内容已改变，请查看最新状态')
            if session['outbox'][key]['state']=='unknown':raise web.HTTPServiceUnavailable(text='回复发送结果待核对；系统不会自动重复提交，请在电脑查看')
            return {'ok':True,'submitted':True}

    async def dispatch(self, session, text, request_id, async_question=None):
        outgoing = session['outbox'][request_id]
        try:
            options = {k: v for k, v in outgoing.get('settings', {}).items() if k in ('model', 'thinking') and v}
            if async_question:
                result=await self.controls.answer_async_question(async_question)
                if result.get('notPending'):
                    session['requests'].remove(request_id)
                    del session['outbox'][request_id]
                    self.rebuild(session)
                    self.save()
                    return 'notPending'
                if not result.get('ok'):
                    raise RpcError('电脑没有确认收到问题答复')
            elif session['threadId']:
                await self.desktop_call('send_message_to_thread', {'threadId': session['threadId'], 'hostId': 'local', 'prompt': text, **options}, session, 'watch-'+request_id)
            else:
                value = await self.desktop_call('create_thread', {'prompt': text, 'title': '手表 · '+text[:24], 'target': outgoing.get('target',{'type':'projectless','directoryName':'watch-chat'}), **options}, session, 'watch-'+request_id)
                thread = value.get('thread', value)
                key = thread.get('threadId') or thread.get('id') or value.get('threadId')
                if not key:
                    raise RpcError('电脑已收到新对话请求，但返回的会话编号未确认，请在电脑查看后选择该会话')
                session['threadId'] = key
                self.anchor = self.anchor or key
            if outgoing['state'] == 'dispatching':
                outgoing['state'] = 'accepted'
            self.save()
            await self.refresh(session, force=True)
        except Exception as e:
            # A timeout may happen after desktop accepted the prompt. Never replay.
            if outgoing['state'] != 'confirmed':
                outgoing['state'] = 'unknown'
            session['error'] = str(e)[:400]
            self.rebuild(session)
            self.save()

    def remember_titles(self, value):
        for item in value.get('threads', []) + value.get('pinnedThreads', []):
            self.thread_summaries.setdefault(item['id'],{}).update(item)
            if item.get('title'):
                self.thread_titles[item['id']] = item['title']

    async def desktop_sessions(self):
        value = await self.desktop_call('list_threads', {'mode': 'history', 'source': 'codex', 'hostId': 'local', 'limit': 50})
        self.remember_titles(value)
        return [{'threadId': t['id'], 'title': t.get('title') or '未命名对话', 'busy': t.get('status') == 'active'} for t in value.get('threads', []) if t.get('hostId', 'local') == 'local']

    async def conversations(self, query='', tab='all', cursor=None, current_session_id=None):
        if tab not in ('all', 'pinned', 'archived'):
            raise web.HTTPBadRequest(text='未知会话分类')
        recent = await self.recent_threads()
        pins = {t['id'] for t in recent.get('pinnedThreads', []) if t.get('kind', 'codex') == 'codex' and t.get('hostId', 'local') == 'local'}
        self.pinned_ids = pins
        self.pins_time = asyncio.get_running_loop().time()
        for session in self.sessions.values():
            if session.get('threadId'): session['pinned'] = session['threadId'] in pins
        if tab == 'pinned':
            data, next_cursor = recent.get('pinnedThreads', []), None
        else:
            data = []
            next_cursor = cursor
            for _ in range(6 if query else 1):
                params = {'mode': 'history', 'source': 'codex', 'hostId': 'local', 'archived': tab == 'archived', 'limit': 50}
                if next_cursor: params['cursor'] = next_cursor
                page = await self.desktop_call('list_threads', params)
                self.remember_titles(page)
                data.extend(page.get('threads', []))
                new_cursor = page.get('nextCursor')
                if not new_cursor or new_cursor == next_cursor:
                    next_cursor = None
                    break
                next_cursor = new_cursor
                if len([t for t in data if query.casefold() in (t.get('title') or '未命名对话').casefold()]) >= 20:
                    break
        self.remember_titles(recent)
        projects=await self.projects()
        current = self.sessions.get(current_session_id) if not cursor and not query else None
        current_id = current.get('threadId') if current else None
        if current_id and all(t['id'] != current_id for t in data):
            archived = self.thread_archived.get(current_id, bool(current.get('archived')))
            if archived == (tab == 'archived') and (tab != 'pinned' or current_id in pins):
                timestamp = dt.datetime.fromisoformat(current['updatedAt']).timestamp()
                data = [*data, {'id': current_id, 'title': current['title'], 'updatedAt': timestamp}]
        statuses=await self.conversation_states([t['id'] for t in data if t.get('kind','codex')=='codex' and t.get('hostId','local')=='local'])
        result = []
        seen = set()
        for t in data:
            if t['id'] in seen or t.get('kind', 'codex') != 'codex' or t.get('hostId', 'local') != 'local' or query.casefold() not in (t.get('title') or '未命名对话').casefold():
                continue
            seen.add(t['id'])
            if tab != 'pinned':
                self.thread_archived[t['id']] = tab == 'archived'
            summary = self.thread_summaries.get(t['id'], t)
            if t['id'] == current_id and 'projectId' not in summary and current.get('projectId'):
                summary = summary | {'projectId': current['projectId']}
            project=project_for_thread(summary,projects)
            result.append({'threadId': t['id'], 'title': t.get('title') or '未命名对话', **statuses[t['id']], 'pinned': t['id'] in pins, 'archived': tab == 'archived', 'projectId': project['id'] if project else None, 'projectName':project['name'] if project else None, 'updatedAt': t.get('updatedAt')})
        for session in self.sessions.values():
            if session.get('threadId') in self.thread_archived:
                session['archived'] = self.thread_archived[session['threadId']]
        self.save()
        if tab != 'archived':
            result.sort(key=lambda t: (not t['pinned'], -(t.get('updatedAt') or 0)))
        return {'conversations': result, 'nextCursor': next_cursor,'projects':projects}

    async def manage_conversation(self, thread_id, action, title=None):
        if not thread_id or len(thread_id) > 100:
            raise web.HTTPBadRequest(text='无效的会话编号')
        if action == 'rename':
            title = str(title or '').strip()
            if not title or len(title) > 200: raise web.HTTPBadRequest(text='名称应为1到200个字符')
            await self.desktop_call('set_thread_title', {'threadId': thread_id, 'title': title})
            self.thread_titles[thread_id] = title
        elif action in ('pin', 'unpin'):
            await self.desktop_call('move_thread_to_sidebar_section', {'threadId': thread_id, 'hostId': 'local', 'sectionId': 'pinned' if action == 'pin' else 'chats'})
        elif action in ('archive', 'restore'):
            state = await self.read_thread_metadata(thread_id)
            if state['thread'].get('status', {}).get('type') == 'active': raise web.HTTPConflict(text='对话仍在处理中，请完成后再归档')
            await self.desktop_call('set_thread_archived', {'threadId': thread_id, 'hostId': 'local', 'archived': action == 'archive'})
            self.thread_archived[thread_id] = action == 'archive'
        else:
            raise web.HTTPBadRequest(text='不支持的会话操作')
        for s in self.sessions.values():
            if s.get('threadId') != thread_id: continue
            if action == 'rename': s['title'] = title
            if action in ('pin', 'unpin'): s['pinned'] = action == 'pin'
            if action in ('archive', 'restore'): s['archived'] = action == 'archive'
        self.save()
        self.pins_time = -30

        self.recent_time = -5

    async def models(self):
        now = asyncio.get_running_loop().time()
        if self.model_catalog is None or now-self.model_catalog_time > 300:
            self.model_catalog = await available_models()
            self.model_catalog_time = now
        return self.model_catalog

    async def set_settings(self, session, model, thinking):
        if not model:
            if thinking: raise web.HTTPBadRequest(text='跟随电脑时无需单独选择思考强度')
            session['settings'] = {}
        else:
            catalog = await self.models()
            selected = next((m for m in catalog if m['id'] == model), None)
            if selected is None: raise web.HTTPBadRequest(text='该模型当前不可用')
            if thinking and thinking not in selected['efforts']: raise web.HTTPBadRequest(text='该模型不支持所选思考强度')
            session['settings'] = {'model': model}
            if thinking: session['settings']['thinking'] = thinking
        self.save()

    async def link(self, thread_id):
        existing = next((s for s in self.sessions.values() if s.get('threadId') == thread_id), None)
        if existing:
            await self.refresh(existing, force=True)
            return existing
        value = await self.read_thread_metadata(thread_id)
        key = self.new_session()
        session = self.sessions[key]
        session['threadId'], session['title'] = thread_id, value['thread'].get('title') or self.thread_titles.get(thread_id) or '未命名对话'
        await self.refresh(session, force=True)
        return session

    async def run_speech(self, mode, path=None, text=None):
        args = ['powershell.exe', '-NoProfile', '-NonInteractive', '-STA', '-ExecutionPolicy', 'Bypass', '-File', str(Path(__file__).with_name('speech.ps1')), '-Mode', mode]
        if path:
            args += ['-Path', str(path)]
        proc = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, creationflags=0x08000000 if os.name == 'nt' else 0)
        try:
            out, err = await asyncio.wait_for(proc.communicate(json.dumps({'text': text}, ensure_ascii=False).encode('utf-8')), 60)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RpcError('语音处理超时，请重试')
        if proc.returncode:
            LOG.warning('Speech %s failed (%s bytes)', mode, len(err))
            raise RpcError('电脑语音引擎暂时不可用，请改用文字输入')
        return json.loads(out.decode('utf-8-sig'))


    async def close(self, app=None):
        for task in list(self.work):
            task.cancel()
        if self.work:
            await asyncio.gather(*self.work, return_exceptions=True)
        await self.desktop.close()
        if self.controls: await self.controls.close()



def make_app(companion, connections=None):
    @web.middleware
    async def security(request, handler):
        if request.headers.get('Origin'):
            raise web.HTTPForbidden(text='不接受浏览器跨站请求')
        if connections and request.path.startswith('/api/connect/'):
            return await handler(request)
        header=request.headers.get('Authorization','')
        bearer=header[7:] if header.startswith('Bearer ') else ''
        if not secrets.compare_digest(request.headers.get('Authorization', ''), 'Bearer '+companion.token) and not (connections and connections.authorized(bearer)):
            raise web.HTTPUnauthorized(text='连接口令不正确，请重新配对')
        try:
            return await handler(request)
        except RpcError as e:
            return web.json_response({'error': str(e)}, status=503)

    app = web.Application(middlewares=[security], client_max_size=1200000)
    if connections:
        connections.routes(app)
        app.on_startup.append(connections.start)
        app.on_cleanup.append(connections.close)

    async def state(request):
        session = companion.session(request.query.get('sessionId'))
        await companion.refresh(session)
        await companion.refresh_control(session)
        return web.json_response(companion.snapshot(session))

    async def sessions(request):
        return web.json_response({'sessions': [{'id': s['id'], 'title': s['title'], 'busy': s['busy']} for s in sorted(companion.sessions.values(), key=lambda s: s['updatedAt'], reverse=True)]})

    async def new_session(request):
        data=await request.json()
        project=await companion.selected_project(data.get('projectId'))
        key=companion.new_session(project)
        return web.json_response({'sessionId':key,'state':companion.snapshot(companion.sessions[key])})

    async def projects(request):
        return web.json_response({'projects':await companion.projects(force=True)})

    async def project(request):
        data=await request.json()
        session=companion.session(data.get('sessionId'))
        await companion.set_project(session,data.get('projectId'))
        return web.json_response(companion.snapshot(session))

    async def conversation_states(request):
        data=await request.json()
        return web.json_response({'states':await companion.conversation_states(data.get('threadIds'))})

    async def message(request):
        data = await request.json()
        text = str(data.get('text', '')).strip()
        request_id = str(data.get('requestId', ''))
        if not text or len(text) > 8000 or not request_id or len(request_id) > 100:
            raise web.HTTPBadRequest(text='消息为空、过长或缺少请求编号')
        session = companion.session(data.get('sessionId'))
        await companion.submit(session, text, request_id, data.get('allowFollowup') is True)
        return web.json_response(companion.snapshot(session))

    async def desktop_sessions(request):
        return web.json_response({'sessions': await companion.desktop_sessions()})

    async def link(request):
        data = await request.json()
        thread_id = str(data.get('threadId', ''))
        if not thread_id or len(thread_id) > 100:
            raise web.HTTPBadRequest(text='无效的电脑会话编号')
        session = await companion.link(thread_id)
        return web.json_response(companion.snapshot(session))

    async def older(request):
        data = await request.json()
        session = companion.session(data.get('sessionId'))
        await companion.refresh(session, force=True, older=True)
        return web.json_response(companion.snapshot(session))

    async def desktop_control(request):
        data = await request.json()
        if not isinstance(data.get('sessionId'),str) or not data['sessionId']:
            raise web.HTTPBadRequest(text='请指定要操作的对话')
        session = companion.session(data['sessionId'])
        if not companion.controls or not session.get('threadId'):
            raise web.HTTPConflict(text='这段对话暂不可控制，请刷新连接')
        if request.path == '/api/interrupt':
            result = await companion.controls.interrupt(session['threadId'],data.get('turnId'))
        else:
            token = data.get('token')
            if not isinstance(token,str) or len(token)!=64:raise web.HTTPBadRequest(text='无效的确认编号')
            result = await companion.respond_control(session,token,data.get('action'),data.get('answers'))
        await companion.refresh(session,force=True)
        await companion.refresh_control(session)
        return web.json_response({'result':result,'state':companion.snapshot(session)})

    async def conversations(request):
        return web.json_response(await companion.conversations(request.query.get('query', '')[:200], request.query.get('tab', 'all'), request.query.get('cursor'), request.query.get('currentSessionId')))

    async def conversation_action(request):
        data = await request.json()
        await companion.manage_conversation(str(data.get('threadId', '')), data.get('action'), data.get('title'))
        return web.json_response({'ok': True})

    async def models(request):
        return web.json_response({'models': await companion.models()})

    async def usage(request):
        return web.json_response(await companion.usage(request.query.get('refresh')=='1'))

    async def settings(request):
        data = await request.json()
        session = companion.session(data.get('sessionId'))
        await companion.set_settings(session, data.get('model'), data.get('thinking'))
        return web.json_response(companion.snapshot(session))

    async def open_on_desktop(request):
        data = await request.json()
        thread_id = str(data.get('threadId', ''))
        if not thread_id or len(thread_id) > 100: raise web.HTTPBadRequest(text='无效的会话编号')
        await companion.desktop_call('navigate_to_codex_page', {'threadId': thread_id})
        return web.json_response({'ok': True})

    async def transcribe(request):
        audio = await request.read()
        try:
            with wave.open(io.BytesIO(audio)) as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000 or wav.getnframes() > 16000*35 or wav.getnframes() < 1600:
                    raise ValueError()
        except (wave.Error, EOFError, ValueError):
            raise web.HTTPBadRequest(text='需要0.1到35秒的16kHz单声道PCM录音')
        async with companion.speech_lock:
            with tempfile.TemporaryDirectory(prefix='watch-speech-') as tmp:
                path = Path(tmp)/'input.wav'
                path.write_bytes(audio)
                result = await companion.run_speech('recognize', path)
        if not result.get('text'):
            return web.json_response({'error': '没有听清，请靠近手表再说一次'}, status=422)
        return web.json_response(result)

    async def speak(request):
        data = await request.json()
        session = companion.session(data.get('sessionId'))
        message = next((m for m in session['messages'] if m['id'] == data.get('messageId') and m['role'] == 'assistant'), None)
        if not message or not message['text']:
            raise web.HTTPBadRequest(text='没有可播放的回复')
        async with companion.speech_lock:
            with tempfile.TemporaryDirectory(prefix='watch-voice-') as tmp:
                path = Path(tmp)/'reply.wav'
                await companion.run_speech('synthesize', path, message['text'][:2000])
                audio = path.read_bytes()
        return web.Response(body=audio, content_type='audio/wav')

    app.add_routes([web.get('/api/state', state), web.get('/api/projects', projects), web.post('/api/session/project', project), web.post('/api/conversations/status', conversation_states), web.get('/api/sessions', sessions), web.post('/api/session/new', new_session), web.post('/api/message', message), web.post('/api/interrupt', desktop_control), web.post('/api/approval', desktop_control), web.get('/api/desktop/sessions', desktop_sessions), web.get('/api/conversations', conversations), web.post('/api/conversation/action', conversation_action), web.post('/api/conversation/open', open_on_desktop), web.get('/api/models', models), web.get('/api/usage', usage), web.post('/api/session/settings', settings), web.post('/api/session/link', link), web.post('/api/history/older', older), web.post('/api/transcribe', transcribe), web.post('/api/speak', speak)])
    app.on_startup.append(companion.start)
    app.on_cleanup.append(companion.close)
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--cwd', default=str(ROOT))
    args = parser.parse_args()
    config, cert, key = identity()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert, key)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    # Authentication and certificate pin stay in ignored .local files, never in the APK.
    from connections import Connections
    config.setdefault('computerId',str(uuid.uuid4()))
    config.setdefault('computerName',__import__('socket').gethostname())
    atomic_json(LOCAL/'connection.json',config)
    connections=Connections(config,LOCAL)
    application=make_app(Companion(config['token'], cwd=args.cwd),connections)
    web.run_app(application, host=args.host, port=args.port, ssl_context=context, access_log=None)
