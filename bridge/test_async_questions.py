import asyncio
import json
import html
import unittest
from aiohttp import web
import test_sync
from controls import DesktopControls,fingerprint,approval_view
from test_controls import FakeControlClient,approval
from server import Companion

class AsyncQuestionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_sync.CompanionTests.asyncSetUp
    asyncTearDown=test_sync.CompanionTests.asyncTearDown

    def setup_question(self):
        key=json.dumps(['request_user_input_async','call-real-format',0],separators=(',',':'))
        self.request=approval('watch/asyncQuestion',questions=[{'id':key,'question':'选哪个？','options':[{'label':'一'},{'label':'二'}],'isOther':True}])
        self.native=FakeControlClient([self.request]);self.companion.controls=DesktopControls(self.native)
        self.payload={'sessionId':self.session['id'],'token':fingerprint(self.request),'action':'answer','answers':{key:'二'}}
        return key

    async def test_native_question_can_be_selected_while_assistant_is_working(self):
        key=self.setup_question();self.desktop.status='active'
        await self.companion.refresh_control(self.session)
        view=self.companion.snapshot(self.session)['approvals'][0]
        self.assertEqual(view['questions'][0]['id'],key)
        self.assertEqual([a['id'] for a in view['actions']],['answer'])
        response=await self.client.post('/api/approval',json=self.payload,headers=self.headers)
        self.assertEqual(response.status,200)
        state=(await response.json())['state'];self.assertEqual(state['approvals'],[])
        sent=[p for n,p in self.desktop.calls if n=='send_message_to_thread'];self.assertEqual(len(sent),1)
        encoded=json.loads(sent[0]['prompt'].partition('>')[2].rpartition('<')[0])
        self.assertEqual(encoded,[{'questionItemId':key,'question':'选哪个？','answer':'二'}])
        self.assertEqual(sent[0]['threadId'],'shared-thread')
        self.assertFalse(any(n=='respond' for n,p in self.native.calls))
        self.assertEqual(sum(m['text']=='选哪个？\n二' for m in state['messages']),1)
        self.assertFalse(any('<send_user_message_question_reply>' in m['text'] for m in state['messages']))

    async def test_repeat_answer_is_idempotent_and_different_answer_is_rejected(self):
        key=self.setup_question()
        for _ in range(2):self.assertEqual((await self.client.post('/api/approval',json=self.payload,headers=self.headers)).status,200)
        changed=self.payload|{'answers':{key:'一'}}
        self.assertEqual((await self.client.post('/api/approval',json=changed,headers=self.headers)).status,409)
        self.assertEqual(sum(n=='send_message_to_thread' for n,p in self.desktop.calls),1)

    async def test_real_delegation_receipt_html_escapes_are_decoded_and_confirm_once(self):
        self.setup_question();original=self.desktop.call
        async def delegated(name,params=None,**kwargs):
            result=await original(name,params,**kwargs)
            if name=='send_message_to_thread':
                self.desktop.turns[0]['items']=[{'id':'real-receipt','type':'functionCallOutput','namespace':'codex_app','name':'send_message_to_thread','output':{'text':'<codex_delegation><input>'+html.escape(params['prompt'])+'</input></codex_delegation>'}}]
            return result
        self.desktop.call=delegated
        response=await self.client.post('/api/approval',json=self.payload,headers=self.headers)
        self.assertEqual(response.status,200)
        state=(await response.json())['state']
        self.assertEqual(self.session['outbox']['question-'+self.payload['token']]['state'],'confirmed')
        self.assertEqual([m['text'] for m in state['messages'] if m['role']=='user' and m['id']=='real-receipt'],['选哪个？\n二'])
        self.assertFalse(any(m['id'].startswith('watch-question-') for m in state['messages']))

    async def test_lost_ack_restart_never_replays_and_history_can_confirm_readable_answer(self):
        self.setup_question();self.desktop.raise_after_send=True
        self.assertEqual((await self.client.post('/api/approval',json=self.payload,headers=self.headers)).status,503)
        restored=Companion('test-token',self.tmp.name,desktop=self.desktop,controls=DesktopControls(self.native))
        s=restored.session(self.session['id'])
        with self.assertRaises(web.HTTPServiceUnavailable):await restored.respond_control(s,self.payload['token'],'answer',self.payload['answers'])
        await self.companion.refresh(self.session,force=True)
        self.assertEqual(self.session['outbox']['question-'+self.payload['token']]['state'],'confirmed')
        self.assertEqual((await self.client.post('/api/approval',json=self.payload,headers=self.headers)).status,200)
        self.assertEqual(sum(n=='send_message_to_thread' for n,p in self.desktop.calls),1)
        self.assertEqual(sum(m['text']=='选哪个？\n二' for m in self.session['messages']),1)

    async def test_free_text_supported_but_missing_stale_and_cross_thread_answers_do_not_send(self):
        key=self.setup_question()
        for payload in [self.payload|{'answers':{}},self.payload|{'action':'cancel'},self.payload|{'token':'0'*64}]:
            self.assertIn((await self.client.post('/api/approval',json=payload,headers=self.headers)).status,(400,409))
        self.request['params']['threadId']='another'
        self.native.requests=[self.request]
        self.assertEqual((await self.client.post('/api/approval',json=self.payload,headers=self.headers)).status,409)
        self.assertFalse(any(n=='send_message_to_thread' for n,p in self.desktop.calls))
        self.setup_question();self.payload['answers']={key:'补充的自由回答'}
        self.assertEqual((await self.client.post('/api/approval',json=self.payload,headers=self.headers)).status,200)
