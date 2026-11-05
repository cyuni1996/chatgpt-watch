import asyncio
import copy
import json
from pathlib import Path
import tempfile
import unittest
from aiohttp.test_utils import TestClient, TestServer
from desktop import RpcError
from server import Companion, make_app, identity
from controls import DesktopControls, fingerprint
from test_controls import FakeControlClient, approval

def turn(key, user, answer='', status='completed', timestamp=1):
    items = [{'id': 'u-'+key, 'type': 'userMessage', 'content': [{'type': 'text', 'text': user}]}]
    if answer:
        items.append({'id': 'a-'+key, 'type': 'agentMessage', 'text': answer, 'phase': 'final_answer'})
    return {'id': key, 'status': status, 'startedAt': timestamp, 'error': None, 'items': items}

class FakeDesktop:
    ready = True
    def __init__(self):
        self.calls = []
        self.turns = [turn('one', 'desktop question', 'desktop answer')]
        self.status = 'idle'
        self.raise_after_send = False
        self.offline = False
        self.older = None
        self.title = 'Shared chat'
        self.pinned = False
        self.archived = False
        self.usage = {'ordinaryUsageAllowed':True,'rateLimits':{'limitId':'codex','primary':{'usedPercent':53,'windowDurationMins':10080,'resetsAt':1793988152}}}
    async def start(self): pass
    async def close(self): pass
    async def call(self, method, params=None, **kwargs):
        self.calls.append((method, params))
        if self.offline: raise RpcError('desktop closed')
        if method == 'list_projects': return {'projects':getattr(self,'projects',[])}
        if method == 'read_thread':
            turns = self.older if params.get('cursor') else self.turns
            return {'thread': {'id': params['threadId'], 'title': self.title, 'updatedAt': 100, 'status': {'type': self.status}}, 'turns': copy.deepcopy(turns), 'page': {'hasMore': bool(self.older) and not params.get('cursor'), 'nextCursor': 'older' if self.older and not params.get('cursor') else None}}
        if method in ('send_message_to_thread', 'create_thread'):
            self.turns.insert(0, turn('sent', params['prompt'], status='inProgress', timestamp=2))
            self.status = 'active'
            if self.raise_after_send: raise RpcError('connection closed after desktop accepted prompt')
            return {'threadId': 'shared-thread'}
        if method == 'list_threads':
            item = {'id': 'shared-thread', 'title': self.title, 'hostId': 'local', 'status': self.status, 'kind': 'codex'}
            return {'threads': [item] if bool(params.get('archived')) == self.archived else [], 'pinnedThreads': [item] if self.pinned else []}
        if method == 'set_thread_title': self.title = params['title']; return {}
        if method == 'move_thread_to_sidebar_section': self.pinned = params['sectionId'] == 'pinned'; return {}
        if method == 'set_thread_archived': self.archived = params['archived']; return {}
        if method == 'navigate_to_codex_page': return {}
        if method == 'get_usage_limits': return copy.deepcopy(self.usage)
        raise AssertionError('Unexpected desktop operation: '+method)

class CompanionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.desktop = FakeDesktop()
        self.companion = Companion('test-token', self.tmp.name, desktop=self.desktop)
        self.session = next(iter(self.companion.sessions.values()))
        self.session['threadId'] = 'shared-thread'
        self.companion.anchor = 'shared-thread'
        async def speech(*args, **kwargs): return {'recognition': True, 'synthesis': True}
        self.companion.run_speech = speech
        self.client = TestClient(TestServer(make_app(self.companion)))
        await self.client.start_server()
        self.headers = {'Authorization': 'Bearer test-token'}
    async def asyncTearDown(self):
        await self.client.close()
        self.tmp.cleanup()

    async def test_auth_and_cross_site_denied(self):
        self.assertEqual((await self.client.get('/api/state')).status, 401)
        self.assertEqual((await self.client.get('/api/state', headers=self.headers)).status, 200)
        self.assertEqual((await self.client.post('/api/session/new', json={}, headers=self.headers | {'Origin': 'https://unrelated.example'})).status, 403)

    async def test_control_http_projects_pending_request_and_submits_once(self):
        req=approval(command='echo safe')
        native=FakeControlClient([req]);self.companion.controls=DesktopControls(native)
        response=await self.client.get('/api/state',headers=self.headers)
        state=await response.json()
        self.assertTrue(state['canInterrupt']);self.assertTrue(state['waitingOnApproval'])
        self.assertEqual(state['approvals'][0]['token'],fingerprint(req))
        self.assertNotIn('requestJson',state)
        payload={'sessionId':self.session['id'],'token':fingerprint(req),'action':'accept'}
        response=await self.client.post('/api/approval',json=payload,headers=self.headers)
        self.assertEqual(response.status,200)
        self.assertEqual((await response.json())['state']['approvals'],[])
        response=await self.client.post('/api/approval',json=payload,headers=self.headers)
        self.assertEqual(response.status,200)
        self.assertEqual(sum(m=='respond' for m,p in native.calls),1)
        self.assertFalse(any(m in ('send_message_to_thread','create_thread') for m,p in self.desktop.calls))

    async def test_control_http_requires_explicit_session_and_turn(self):
        native=FakeControlClient();self.companion.controls=DesktopControls(native)
        self.assertEqual((await self.client.post('/api/interrupt',json={'turnId':'turn-1'},headers=self.headers)).status,400)
        self.assertEqual((await self.client.post('/api/interrupt',json={'sessionId':self.session['id']},headers=self.headers)).status,400)
        response=await self.client.post('/api/interrupt',json={'sessionId':self.session['id'],'turnId':'turn-1'},headers=self.headers)
        self.assertEqual(response.status,200)
        self.assertEqual([p for m,p in native.calls if m=='interrupt'],[{'threadId':'shared-thread','turnId':'turn-1'}])

    async def test_usage_endpoint_reads_desktop_cache_and_explicit_refresh(self):
        self.assertEqual((await self.client.get('/api/usage')).status,401)
        first=await self.client.get('/api/usage',headers=self.headers)
        self.assertEqual(first.status,200);self.assertEqual((await first.json())['groups'][0]['windows'][0]['remainingPercent'],47)
        await self.client.get('/api/usage',headers=self.headers)
        self.assertEqual(sum(m=='get_usage_limits' for m,p in self.desktop.calls),1)
        self.desktop.usage['rateLimits']['primary']['usedPercent']=54
        refreshed=await self.client.get('/api/usage?refresh=1',headers=self.headers)
        self.assertEqual((await refreshed.json())['groups'][0]['windows'][0]['remainingPercent'],46)
        self.assertEqual(sum(m=='get_usage_limits' for m,p in self.desktop.calls),2)
        self.assertFalse(any(m in ('send_message_to_thread','create_thread','consume_usage_reset') for m,p in self.desktop.calls))

    async def test_usage_offline_returns_marked_stale_data_or_clear_error(self):
        self.desktop.offline=True
        response=await self.client.get('/api/usage',headers=self.headers)
        self.assertEqual(response.status,503)
        self.desktop.offline=False
        good=await self.client.get('/api/usage',headers=self.headers);stamp=(await good.json())['updatedAt']
        self.desktop.offline=True
        stale=await self.client.get('/api/usage?refresh=1',headers=self.headers);value=await stale.json()
        self.assertTrue(value['stale']);self.assertEqual(value['updatedAt'],stamp)

    async def test_desktop_messages_and_stream_updates_replace_cache(self):
        self.session['messages'] = [{'id': 'stale', 'role': 'assistant', 'text': 'old cache'}]
        await self.companion.refresh(self.session, force=True)
        self.assertEqual([m['text'] for m in self.session['messages']], ['desktop question', 'desktop answer'])
        self.desktop.turns[0]['items'][-1]['text'] = 'updated answer'
        self.desktop.turns.insert(0, turn('two', 'next desktop question', 'new desktop answer', timestamp=2))
        await self.companion.refresh(self.session, force=True)
        self.assertEqual(len(self.session['messages']), 4)
        self.assertEqual(self.session['messages'][-1]['text'], 'new desktop answer')
        self.assertEqual(self.session['messages'][1]['text'], 'updated answer')

    async def test_import_marker_is_hidden_but_real_messages_remain(self):
        self.desktop.turns[0]['items'].append({'id': 'import-marker', 'type': 'agentMessage', 'text': '<EXTERNAL SESSION IMPORTED>'})
        await self.companion.refresh(self.session, force=True)
        self.assertEqual([m['text'] for m in self.session['messages']], ['desktop question', 'desktop answer'])

    async def test_question_reply_shows_question_and_answer_without_internal_metadata(self):
        payload='<send_user_message_question_reply>'+json.dumps([{'questionItemId':'private-routing-id','question':'是否完成确认？','answer':'确认完成'}],ensure_ascii=False)+'</send_user_message_question_reply>'
        self.desktop.turns=[turn('answer',payload,'收到')]
        await self.companion.refresh(self.session,force=True)
        self.assertEqual(self.session['messages'][0]['text'],'是否完成确认？\n确认完成')
        self.assertEqual(self.session['messages'][0]['id'],'u-answer')
        self.assertEqual(self.desktop.turns[0]['items'][0]['content'][0]['text'],payload)

    async def test_null_title_uses_sidebar_name_and_safe_search_fallback(self):
        original = self.desktop.call
        async def metadata_name(method, params=None, **kwargs):
            value = await original(method, params, **kwargs)
            if method == 'read_thread': value['thread']['title'] = None
            return value
        self.desktop.call = metadata_name
        await self.companion.refresh(self.session, force=True)
        self.assertEqual(self.session['title'], 'Shared chat')
        self.desktop.title = None
        result = await self.companion.conversations(query='未命名')
        self.assertEqual(result['conversations'][0]['title'], '未命名对话')

    async def test_opening_desktop_archived_history_blocks_send_until_restore(self):
        self.desktop.archived = True
        result = await self.companion.conversations(tab='archived')
        self.assertTrue(result['conversations'][0]['archived'])
        linked = await self.companion.link('shared-thread')
        self.assertTrue(linked['archived'])
        response = await self.client.post('/api/message', json={'text': 'watch', 'requestId': 'archived'}, headers=self.headers)
        self.assertEqual(response.status, 409)
        self.assertFalse(any(name == 'send_message_to_thread' for name,_ in self.desktop.calls))
        await self.companion.manage_conversation('shared-thread','restore')
        await self.companion.refresh(linked, force=True)
        self.assertFalse(linked['archived'])

    async def test_watch_continues_exact_thread_without_branch(self):
        await self.companion.submit(self.session, 'watch question', 'stable-id')
        await asyncio.gather(*list(self.companion.work))
        sends = [(name, params) for name, params in self.desktop.calls if name in ('send_message_to_thread', 'create_thread')]
        self.assertEqual(sends, [('send_message_to_thread', {'threadId': 'shared-thread', 'hostId': 'local', 'prompt': 'watch question'})])
        self.assertEqual(self.session['messages'][-1]['id'], 'u-sent')
        self.assertTrue(self.session['busy'])

    async def test_request_retry_is_not_dispatched_twice(self):
        await self.companion.submit(self.session, 'watch question', 'stable-id')
        await asyncio.gather(*list(self.companion.work))
        await self.companion.submit(self.session, 'watch question', 'stable-id')
        self.assertEqual(sum(name == 'send_message_to_thread' for name, _ in self.desktop.calls), 1)

    async def test_desktop_busy_rejects_watch_send(self):
        self.desktop.status = 'active'
        response = await self.client.post('/api/message', json={'text': 'watch', 'requestId': 'id'}, headers=self.headers)
        self.assertEqual(response.status, 409)
        self.assertFalse(any(name == 'send_message_to_thread' for name, _ in self.desktop.calls))

    async def test_simultaneous_watch_sends_have_one_winner(self):
        results = await asyncio.gather(*[self.client.post('/api/message', json={'text': 'watch', 'requestId': str(i)}, headers=self.headers) for i in range(2)])
        self.assertEqual(sorted(r.status for r in results), [200, 409])
        await asyncio.gather(*list(self.companion.work))
        self.assertEqual(sum(name == 'send_message_to_thread' for name, _ in self.desktop.calls), 1)

    async def test_lost_ack_reconciles_without_replay(self):
        self.desktop.raise_after_send = True
        await self.companion.submit(self.session, 'watch question', 'lost-ack')
        await asyncio.gather(*list(self.companion.work))
        self.assertEqual(self.session['outbox']['lost-ack']['state'], 'unknown')
        await self.companion.refresh(self.session, force=True)
        self.assertEqual(self.session['outbox']['lost-ack']['state'], 'confirmed')
        self.assertEqual(sum(name == 'send_message_to_thread' for name, _ in self.desktop.calls), 1)
        self.assertEqual(sum(m['text'] == 'watch question' for m in self.session['messages']), 1)

    async def test_restart_preserves_thread_and_never_replays_pending(self):
        self.session['outbox']['pending'] = {'text': 'uncertain', 'knownUserIds': [], 'state': 'dispatching'}
        self.companion.save()
        restored = Companion('test-token', self.tmp.name, desktop=self.desktop)
        session = restored.session(self.session['id'])
        self.assertEqual(session['threadId'], 'shared-thread')
        self.assertEqual(session['outbox']['pending']['state'], 'unknown')
        await restored.refresh(session, force=True)
        self.assertFalse(any(name == 'send_message_to_thread' for name, _ in self.desktop.calls))
        self.assertTrue(session['error'])

    async def test_older_page_keeps_latest_messages(self):
        self.desktop.older = [turn('older', 'older question', 'older answer', timestamp=0)]
        await self.companion.refresh(self.session, force=True)
        self.assertTrue(self.session['olderCursor'])
        await self.companion.refresh(self.session, force=True, older=True)
        self.assertEqual([m['text'] for m in self.session['messages']], ['older question', 'older answer', 'desktop question', 'desktop answer'])
        self.assertIsNone(self.session['olderCursor'])

    async def test_oversized_pages_shrink_and_remember_limit_without_losing_forwarded_prompt(self):
        original=self.desktop.call
        async def size_limited(method,params=None,**kwargs):
            if method=='read_thread' and params['turnLimit']>2:
                self.desktop.calls.append((method,dict(params)))
                raise RpcError('Tool response exceeds the size limit. Request fewer turns or omit outputs.')
            return await original(method,params,**kwargs)
        self.desktop.call=size_limited
        self.desktop.turns[0]['items'][0]={'id':'forwarded','type':'functionCallOutput','namespace':'codex_app',
            'name':'send_message_to_thread','output':{'text':'<codex_delegation><input>forwarded question</input></codex_delegation>'}}
        await self.companion.refresh(self.session,force=True)
        reads=[p for name,p in self.desktop.calls if name=='read_thread']
        self.assertEqual([p['turnLimit'] for p in reads],[10,5,2])
        self.assertTrue(all(p['includeOutputs'] and p['maxOutputCharsPerItem']==20000 for p in reads))
        self.assertEqual(self.session['messages'][0]['text'],'forwarded question')
        self.desktop.calls.clear()
        await self.companion.refresh(self.session,force=True)
        self.assertEqual([p['turnLimit'] for name,p in self.desktop.calls if name=='read_thread'],[2])
        self.assertTrue(self.companion.desktop_online)

    async def test_oversized_older_page_retains_cursor_and_recent_messages(self):
        self.desktop.older=[turn('older','older question','older answer',timestamp=0)]
        await self.companion.refresh(self.session,force=True)
        original=self.desktop.call
        async def size_limited(method,params=None,**kwargs):
            if method=='read_thread' and params.get('cursor') and params['turnLimit']>1:
                self.desktop.calls.append((method,dict(params)))
                raise RpcError('Tool response exceeds the size limit.')
            return await original(method,params,**kwargs)
        self.desktop.call=size_limited;self.desktop.calls.clear()
        await self.companion.refresh(self.session,force=True,older=True)
        reads=[p for name,p in self.desktop.calls if name=='read_thread']
        self.assertEqual([p['turnLimit'] for p in reads],[10,5,2,1])
        self.assertTrue(all(p['cursor']=='older' for p in reads))
        self.assertEqual([m['text'] for m in self.session['messages']],
            ['older question','older answer','desktop question','desktop answer'])

    async def test_single_oversized_turn_omits_outputs_with_explicit_notice(self):
        original=self.desktop.call
        async def size_limited(method,params=None,**kwargs):
            if method=='read_thread' and params.get('includeOutputs'):
                self.desktop.calls.append((method,dict(params)))
                raise RpcError('Tool response exceeds the size limit. A single oversized turn cannot be returned by this tool.')
            return await original(method,params,**kwargs)
        self.desktop.call=size_limited
        response=await self.client.get('/api/state',headers=self.headers)
        self.assertEqual(response.status,200)
        state=await response.json()
        self.assertEqual([m['text'] for m in state['messages']],['desktop question','desktop answer'])
        self.assertIn('工具输出过长',state['error'])
        self.assertTrue(state['connected'])
        reads=[p for name,p in self.desktop.calls if name=='read_thread']
        self.assertEqual(len(reads),5)
        self.assertEqual((reads[-1]['turnLimit'],reads[-1]['includeOutputs']),(1,False))

    async def test_non_size_failure_is_not_retried_or_reinterpreted(self):
        async def offline(method,params=None,**kwargs):
            self.desktop.calls.append((method,params))
            raise RpcError('desktop closed')
        self.desktop.call=offline
        with self.assertRaisesRegex(RpcError,'desktop closed'):
            await self.companion.refresh(self.session,force=True)
        self.assertEqual(len(self.desktop.calls),1)

    async def test_link_and_archive_metadata_never_fetch_tool_outputs(self):
        await self.companion.link('another-thread')
        await self.companion.manage_conversation('another-thread','archive')
        metadata=[p for name,p in self.desktop.calls if name=='read_thread' and p.get('maxOutputCharsPerItem')==1]
        self.assertEqual(len(metadata),2)
        self.assertTrue(all(p['includeOutputs'] is False and p['turnLimit']==1 for p in metadata))

    async def test_desktop_revert_removes_stale_watch_messages(self):
        self.desktop.turns.insert(0, turn('removed', 'reverted question', 'reverted answer', timestamp=2))
        await self.companion.refresh(self.session, force=True)
        self.desktop.turns.pop(0)
        await self.companion.refresh(self.session, force=True)
        self.assertEqual([m['text'] for m in self.session['messages']], ['desktop question', 'desktop answer'])

    async def test_desktop_forwarded_user_prompt_is_visible(self):
        self.desktop.turns[0]['items'][0] = {'id': 'forwarded-user', 'type': 'functionCallOutput', 'namespace': 'codex_app', 'name': 'send_message_to_thread', 'output': {'text': '<codex_delegation>\n<source_thread_id>source</source_thread_id>\n<input>forwarded human question</input>\n</codex_delegation>'}}
        await self.companion.refresh(self.session, force=True)
        self.assertEqual(self.session['messages'][0]['role'], 'user')
        self.assertEqual(self.session['messages'][0]['text'], 'forwarded human question')

    async def test_link_desktop_chat_keeps_original_id(self):
        response = await self.client.post('/api/session/link', json={'threadId': 'another-desktop-thread'}, headers=self.headers)
        self.assertEqual(response.status, 200)
        value = await response.json()
        self.assertEqual(value['threadId'], 'another-desktop-thread')
        self.assertEqual(value['messages'][-1]['text'], 'desktop answer')
        self.assertFalse(any(name == 'create_thread' for name, _ in self.desktop.calls))

    async def test_desktop_offline_does_not_fallback_to_another_agent(self):
        self.desktop.offline = True
        response = await self.client.get('/api/state', headers=self.headers)
        self.assertEqual(response.status, 503)
        self.assertFalse(any(name in ('create_thread', 'send_message_to_thread') for name, _ in self.desktop.calls))

    async def test_audio_validation_and_persistent_identity(self):
        result = await self.client.post('/api/transcribe', data=b'not wave', headers=self.headers)
        self.assertEqual(result.status, 400)
        first, _, _ = identity(Path(self.tmp.name))
        second, _, _ = identity(Path(self.tmp.name))
        self.assertEqual(first, second)

    async def test_rename_and_pin_update_shared_desktop_state(self):
        response = await self.client.post('/api/conversation/action',json={'threadId':'shared-thread','action':'rename','title':'  Renamed chat  '},headers=self.headers)
        self.assertEqual(response.status,200)
        self.assertEqual(self.desktop.title,'Renamed chat')
        self.assertEqual(self.session['title'],'Renamed chat')
        response = await self.client.post('/api/conversation/action',json={'threadId':'shared-thread','action':'pin'},headers=self.headers)
        self.assertEqual(response.status,200)
        value = await (await self.client.get('/api/conversations?tab=pinned',headers=self.headers)).json()
        self.assertEqual(value['conversations'][0]['title'],'Renamed chat')
        self.assertTrue(value['conversations'][0]['pinned'])
        await self.client.post('/api/conversation/action',json={'threadId':'shared-thread','action':'unpin'},headers=self.headers)
        value = await (await self.client.get('/api/conversations?tab=pinned',headers=self.headers)).json()
        self.assertEqual(value['conversations'],[])

    async def test_archive_restore_and_active_guard(self):
        data={'threadId':'shared-thread','action':'archive'}
        self.desktop.status='active'
        self.assertEqual((await self.client.post('/api/conversation/action',json=data,headers=self.headers)).status,409)
        self.assertFalse(self.desktop.archived)
        self.desktop.status='idle'
        self.assertEqual((await self.client.post('/api/conversation/action',json=data,headers=self.headers)).status,200)
        value=await (await self.client.get('/api/conversations?tab=archived',headers=self.headers)).json()
        self.assertTrue(value['conversations'][0]['archived'])
        self.assertEqual((await self.client.post('/api/message',json={'text':'blocked','requestId':'archive-send'},headers=self.headers)).status,409)
        await self.client.post('/api/conversation/action',json=data|{'action':'restore'},headers=self.headers)
        self.assertFalse(self.desktop.archived)
        self.assertFalse(self.session['archived'])

    async def test_invalid_management_input_is_not_forwarded(self):
        self.assertEqual((await self.client.post('/api/conversation/action',json={'threadId':'shared-thread','action':'rename','title':' '},headers=self.headers)).status,400)
        self.assertEqual((await self.client.post('/api/conversation/action',json={'threadId':'shared-thread','action':'delete'},headers=self.headers)).status,400)
        self.assertFalse(any(n in ('set_thread_title','set_thread_archived') for n,_ in self.desktop.calls))

    async def test_model_selection_is_validated_and_only_applies_to_next_send(self):
        self.companion.model_catalog=[{'id':'test-model','name':'Test','efforts':['low','high']}]
        self.companion.model_catalog_time=asyncio.get_running_loop().time()
        self.assertEqual((await self.client.post('/api/session/settings',json={'model':'missing','thinking':'high'},headers=self.headers)).status,400)
        self.assertEqual((await self.client.post('/api/session/settings',json={'model':'test-model','thinking':'ultra'},headers=self.headers)).status,400)
        value={'model':'test-model','thinking':'high'}
        self.assertEqual((await self.client.post('/api/session/settings',json=value,headers=self.headers)).status,200)
        self.assertFalse(any(n=='send_message_to_thread' for n,_ in self.desktop.calls))
        await self.companion.submit(self.session,'configured prompt','model-settings')
        await self.companion.set_settings(self.session,None,None)
        await asyncio.gather(*list(self.companion.work))
        sent=next(p for n,p in self.desktop.calls if n=='send_message_to_thread')
        self.assertEqual((sent['model'],sent['thinking']),('test-model','high'))
        self.assertEqual(self.session['settings'],{})

    async def test_followup_uses_existing_desktop_thread(self):
        self.desktop.status='active'
        await self.companion.submit(self.session,'human followup','followup',True)
        await asyncio.gather(*list(self.companion.work))
        sent=next(p for n,p in self.desktop.calls if n=='send_message_to_thread')
        self.assertEqual(sent['threadId'],'shared-thread')
        self.assertFalse(any(n=='create_thread' for n,_ in self.desktop.calls))

    async def test_search_reads_older_pages(self):
        original=self.desktop.call
        async def paged(name,params=None,**kwargs):
            if name=='list_threads' and params.get('mode')=='history':
                if params.get('cursor')=='older': return {'threads':[{'id':'old-chat','title':'Needle in old history','hostId':'local'}],'nextCursor':None}
                return {'threads':[{'id':'new-chat','title':'Unrelated','hostId':'local'}],'nextCursor':'older'}
            return await original(name,params,**kwargs)
        self.desktop.call=paged
        response=await self.client.get('/api/conversations?query=needle',headers=self.headers)
        value=await response.json()
        self.assertEqual([t['threadId'] for t in value['conversations']],['old-chat'])
        self.assertIsNone(value['nextCursor'])

if __name__ == '__main__': unittest.main()
