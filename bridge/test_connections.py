import hashlib,json,tempfile,sys,unittest
from pathlib import Path
from aiohttp.test_utils import TestClient,TestServer
from connections import Connections,public_url,verification_code
from server import Companion,make_app
from test_sync import FakeDesktop

class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.now=100
        self.config={'computerId':'pc-one','computerName':'测试电脑','port':8766,'certificateSha256':'a'*64}
        self.connection=Connections(self.config,self.tmp.name,clock=lambda:self.now)
        async def noop(app):pass
        self.connection.start=noop
        companion=Companion('legacy-secret',self.tmp.name,desktop=FakeDesktop())
        async def speech(*a,**kw):return {}
        companion.run_speech=speech
        self.client=TestClient(TestServer(make_app(companion,self.connection)));await self.client.start_server()
        self.admin={'Authorization':'Bearer '+self.connection.data['adminToken']}
        self.claim='random-watch-claim-secret-256-bits'
        self.data={'requestId':'request-for-watch-one','claimHash':hashlib.sha256(self.claim.encode()).hexdigest(),'deviceName':'手表','mode':'lan','url':'https://192.168.1.2:8766'}
    async def asyncTearDown(self):await self.client.close();self.tmp.cleanup()
    async def open(self):
        r=await self.client.post('/api/connect/admin/window',json={'open':True},headers=self.admin);self.assertEqual(r.status,200)
    async def enroll(self):
        await self.open();r=await self.client.post('/api/connect/requests',json=self.data);self.assertEqual(r.status,200)
        r=await self.client.post('/api/connect/admin/decide',json={'requestId':self.data['requestId'],'approve':True},headers=self.admin);self.assertEqual(r.status,200)
        r=await self.client.get('/api/connect/requests/'+self.data['requestId'],headers={'Authorization':'Bearer '+self.claim});return await r.json()
    async def test_enrollment_requires_operator_and_claim_and_does_not_expose_tokens(self):
        self.assertEqual((await self.client.post('/api/connect/requests',json=self.data)).status,403)
        info=await (await self.client.get('/api/connect/info')).json();self.assertNotIn('token',info)
        self.assertEqual((await self.client.post('/api/connect/admin/window',json={'open':True},headers={'Authorization':'Bearer legacy-secret'})).status,403)
        await self.open();await self.client.post('/api/connect/requests',json=self.data)
        pending=await (await self.client.get('/api/connect/admin/pending',headers=self.admin)).json()
        item=pending['requests'][0];self.assertNotIn('claimHash',item);self.assertNotIn('token',item)
        self.assertEqual(item['code'],verification_code('pc-one','a'*64,'lan',self.data['url'],self.data['requestId'],self.data['claimHash']))
        path='/api/connect/requests/'+self.data['requestId']
        self.assertEqual((await self.client.get(path)).status,404)
        result=await (await self.client.get(path,headers={'Authorization':'Bearer '+self.claim})).json()
        self.assertEqual(result,{'state':'waiting'})
        conflict=dict(self.data,claimHash='b'*64)
        self.assertEqual((await self.client.post('/api/connect/requests',json=conflict)).status,409)
    async def test_device_token_persists_and_revocation_blocks_chat_but_not_other_clients(self):
        result=await self.enroll();token=result['token'];headers={'Authorization':'Bearer '+token}
        self.assertEqual((await self.client.get('/api/sessions',headers=headers)).status,200)
        self.assertEqual((await self.client.get('/api/sessions',headers={'Authorization':token})).status,401)
        self.assertEqual((await self.client.get('/api/connect/admin/pending',headers=headers)).status,403)
        text=(Path(self.tmp.name)/'paired-devices.json').read_text();self.assertNotIn(token,text)
        reopened=Connections(self.config,self.tmp.name);self.assertTrue(reopened.authorized(token))
        device=next(iter(self.connection.data['devices']))
        await self.client.post('/api/connect/admin/revoke',json={'deviceId':device},headers=self.admin)
        self.assertEqual((await self.client.get('/api/sessions',headers=headers)).status,401)
        self.assertEqual((await self.client.get('/api/sessions',headers={'Authorization':'Bearer legacy-secret'})).status,200)
    async def test_expiry_denial_and_request_limit_do_not_grant_access(self):
        await self.open()
        for i in range(5):
            self.assertEqual((await self.client.post('/api/connect/requests',json=dict(self.data,requestId='request-number-%03d'%i))).status,200)
        self.assertEqual((await self.client.post('/api/connect/requests',json=self.data)).status,429)
        rid='request-number-000'
        await self.client.post('/api/connect/admin/decide',json={'requestId':rid,'approve':False},headers=self.admin)
        r=await self.client.get('/api/connect/requests/'+rid,headers={'Authorization':'Bearer '+self.claim})
        self.assertEqual((await r.json())['state'],'denied');self.assertEqual(self.connection.data['devices'],{})
        self.now+=181
        self.assertEqual((await self.client.get('/api/connect/requests/'+rid,headers={'Authorization':'Bearer '+self.claim})).status,404)
        self.assertEqual((await self.client.post('/api/connect/requests',json=self.data)).status,403)
    async def test_public_pairing_requires_configured_exact_https_origin(self):
        await self.open();d=dict(self.data,mode='public',url='https://watch.example.com')
        self.assertEqual((await self.client.post('/api/connect/requests',json=d)).status,403)
        (Path(self.tmp.name)/'public-endpoint.json').write_text(json.dumps({'url':'https://watch.example.com','originPort':8767}))
        self.assertEqual((await self.client.post('/api/connect/requests',json=dict(d,url='https://other.example.com'))).status,403)
        self.assertEqual((await self.client.post('/api/connect/requests',json=dict(d,url='http://watch.example.com'))).status,400)
        self.assertEqual((await self.client.post('/api/connect/requests',json=d)).status,200)
        self.assertEqual((await self.client.post('/api/connect/admin/window',json={'open':True},headers=self.admin|{'Origin':'https://evil.example'})).status,403)
    async def test_pairing_identity_and_url_are_bound_into_verification(self):
        code=verification_code('pc-one','a'*64,'lan',self.data['url'],self.data['requestId'],self.data['claimHash'])
        self.assertNotEqual(code,verification_code('pc-one','b'*64,'lan',self.data['url'],self.data['requestId'],self.data['claimHash']))
        self.assertNotEqual(code,verification_code('pc-one','a'*64,'public','https://evil.example',self.data['requestId'],self.data['claimHash']))
        self.assertNotEqual(code,verification_code('pc-one','a'*64,'lan',self.data['url'],'another-request-id',self.data['claimHash']))
    async def test_malformed_requests_rejected_and_finished_claim_cannot_redeem_again(self):
        await self.open()
        for bad in [[],{},dict(self.data,url={}),dict(self.data,claimHash='short')]:
            self.assertEqual((await self.client.post('/api/connect/requests',json=bad)).status,400)
        await self.enroll();path='/api/connect/requests/'+self.data['requestId']
        self.assertEqual((await self.client.post(path+'/finish',json={},headers={'Authorization':'Bearer '+self.claim})).status,200)
        self.assertEqual((await self.client.get(path,headers={'Authorization':'Bearer '+self.claim})).status,404)

class PublicConfigTests(unittest.TestCase):
    def test_public_domain_rejects_credentials_ips_paths_and_nonstandard_ports(self):
        for value in ['http://watch.example.com','https://127.0.0.1','https://user:pass@watch.example.com','https://watch.example.com/api','https://watch.example.com?token=x','https://watch.example.com:8766','https://watch.local']:
            with self.assertRaises(ValueError):public_url(value)
        self.assertEqual(public_url('https://WATCH.example.com/'),'https://watch.example.com')
    def test_tunnel_configuration_is_loopback_only_and_blocks_administration(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
        from configure_public import tunnel_config
        value=tunnel_config('https://watch.example.com','11111111-1111-4111-8111-111111111111',Path(self.id()+'.json'),8767)
        self.assertIn('http://127.0.0.1:8767',value);self.assertNotIn('noTLSVerify',value)
        self.assertLess(value.index('/api/connect/admin/'),value.index('http://127.0.0.1'))
        self.assertTrue(value.endswith('  - service: http_status:404\n'))

if __name__=='__main__':unittest.main()
