import asyncio
import copy
import json
import unittest
from aiohttp import web
from controls import DesktopControls, approval_view, approval_response, fingerprint

def approval(method='item/commandExecution/requestApproval',key='req-1',thread='shared-thread',**params):
    return {'id':key,'method':method,'params':{'threadId':thread,'turnId':'turn-1','itemId':'item-1',**params}}

class FakeControlClient:
    def __init__(self,requests=None):
        self.requests=copy.deepcopy(requests or [])
        self.calls=[]
        self.available=True
        self.closed=False
    async def call(self,method,params):
        self.calls.append((method,params))
        if method=='read':return {'available':self.available,'threadId':params['threadId'],'requests':copy.deepcopy(self.requests),'turnId':'turn-1'}
        if method=='respond':
            await asyncio.sleep(.01)
            self.requests=[r for r in self.requests if r['id']!=params['requestId']]
            return {'ok':True,'resolved':True}
        if method=='interrupt':return {'ok':True,'interruptedTurnId':params['turnId']}
        raise AssertionError(method)
    async def close(self):self.closed=True

class ApprovalProjectionTests(unittest.TestCase):
    def test_command_shows_exact_command_cwd_and_reason_without_permanent_grants(self):
        r=approval(command='echo safe',cwd='C:/project',reason='Need confirmation')
        view=approval_view(r)
        self.assertIn('echo safe',view['details']);self.assertIn('C:/project',view['details'])
        self.assertEqual([a['id'] for a in view['actions']],['accept','decline','cancel'])
        self.assertEqual(approval_response(r,'accept'),'accept')
        with self.assertRaises(web.HTTPBadRequest):approval_response(r,'acceptForSession')
    def test_file_approval_includes_actual_proposed_change(self):
        v=approval_view(approval('item/fileChange/requestApproval'),{'changes':[{'path':'a.txt','diff':'+new'}]})
        self.assertIn('a.txt',v['details']);self.assertIn('+new',v['details'])
    def test_network_prompt_is_rendered_as_network_not_shell(self):
        v=approval_view(approval(networkApprovalContext={'host':'example.com','protocol':'https'}))
        self.assertEqual(v['title'],'允许网络访问？');self.assertIn('https://example.com',v['details'])
    def test_permission_grant_is_only_requested_subset_for_current_turn(self):
        r=approval('item/permissions/requestApproval',permissions={'fileSystem':{'write':['C:/test']},'network':{'enabled':True},'extra':'ignored'})
        yes=approval_response(r,'accept');self.assertEqual(yes['scope'],'turn');self.assertNotIn('extra',yes['permissions'])
        self.assertEqual(approval_response(r,'decline')['permissions'],{})
    def test_questions_require_all_answers_and_valid_options(self):
        r=approval('item/tool/requestUserInput',questions=[{'id':'choose','question':'Continue?','options':[{'label':'Allow'},{'label':'Decline'}]},{'id':'text','question':'Why?'}])
        with self.assertRaises(web.HTTPBadRequest):approval_response(r,'answer',{'choose':'Allow'})
        with self.assertRaises(web.HTTPBadRequest):approval_response(r,'answer',{'choose':'Unexpected','text':'ok'})
        self.assertEqual(approval_response(r,'answer',{'choose':'Allow','text':'ok'})['answers']['choose'],{'answers':['Allow']})
        self.assertEqual(approval_response(r,'cancel'),{'answers':{}})
    def test_mcp_form_converts_only_defined_fields_and_checks_required(self):
        r=approval('mcpServer/elicitation/request',mode='form',requestedSchema={'type':'object','properties':{'ok':{'type':'boolean'},'count':{'type':'integer','minimum':1,'maximum':5}},'required':['ok']})
        with self.assertRaises(web.HTTPBadRequest):approval_response(r,'answer',{})
        with self.assertRaises(web.HTTPBadRequest):approval_response(r,'answer',{'ok':'True','count':'7'})
        self.assertEqual(approval_response(r,'answer',{'ok':'True','count':'2','notRequested':'bad'})['content'],{'ok':True,'count':2})
        self.assertEqual(approval_response(r,'decline'),{'action':'decline','content':None})
    def test_external_login_never_offers_blind_acceptance(self):
        r=approval('mcpServer/elicitation/request',mode='url',url='https://example.com/login')
        with self.assertRaises(web.HTTPBadRequest):approval_response(r,'accept')
        self.assertEqual([v['id'] for v in approval_view(r)['actions']],['decline','cancel'])
    def test_tokens_bind_request_content_and_thread(self):
        r=approval(command='one');changed=copy.deepcopy(r);changed['params']['command']='two'
        self.assertNotEqual(fingerprint(r),fingerprint(changed));self.assertNotEqual(fingerprint(r),fingerprint(approval(thread='another')))
        self.assertNotEqual(fingerprint(r,{'diff':'old'}),fingerprint(r,{'diff':'new'}))

class ControlDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_concurrent_approval_is_dispatched_once(self):
        r=approval();client=FakeControlClient([r]);c=DesktopControls(client)
        values=await asyncio.gather(*[c.respond('shared-thread',fingerprint(r),'accept') for _ in range(2)])
        self.assertEqual(sum(m=='respond' for m,p in client.calls),1)
        self.assertTrue(all(v['ok'] for v in values))
    async def test_other_thread_and_stale_payload_are_rejected(self):
        r=approval();client=FakeControlClient([r]);c=DesktopControls(client)
        with self.assertRaises(web.HTTPConflict):await c.respond('different',fingerprint(r),'accept')
        changed=copy.deepcopy(r);changed['params']['reason']='changed';client.requests=[changed]
        with self.assertRaises(web.HTTPConflict):await c.respond('shared-thread',fingerprint(r),'accept')
        self.assertFalse(any(m=='respond' for m,p in client.calls))
    async def test_desktop_resolution_or_offline_does_not_replay_decision(self):
        r=approval();client=FakeControlClient([]);c=DesktopControls(client)
        with self.assertRaises(web.HTTPConflict):await c.respond('shared-thread',fingerprint(r),'accept')
        client.available=False
        with self.assertRaises(web.HTTPServiceUnavailable):await c.respond('shared-thread',fingerprint(r),'accept')
        self.assertFalse(any(m=='respond' for m,p in client.calls))
    async def test_interrupt_requires_specific_turn_and_no_chat_message(self):
        client=FakeControlClient();c=DesktopControls(client)
        with self.assertRaises(web.HTTPBadRequest):await c.interrupt('shared-thread',None)
        await c.interrupt('shared-thread','turn-1')
        self.assertEqual(client.calls,[('interrupt',{'threadId':'shared-thread','turnId':'turn-1'})])
    async def test_opposite_decision_cannot_replace_completed_answer(self):
        r=approval();client=FakeControlClient([r]);c=DesktopControls(client)
        await c.respond('shared-thread',fingerprint(r),'accept')
        with self.assertRaises(web.HTTPConflict):await c.respond('shared-thread',fingerprint(r),'decline')
