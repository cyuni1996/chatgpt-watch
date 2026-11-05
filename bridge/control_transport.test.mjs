import {test} from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import {spawn} from 'node:child_process';
import readline from 'node:readline';
import {randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';

async function fixture(){
 const path='\\\\.\\pipe\\watch-control-test-'+randomUUID();
 const request={id:'approval-1',method:'item/commandExecution/requestApproval',params:{threadId:'shared-thread',turnId:'turn-1',itemId:'command-1',command:'echo TEST'}};
 const state={id:'shared-thread',turns:[{turnId:'turn-1',status:'inProgress',items:[]}],requests:[request],threadRuntimeStatus:{type:'active'}};
 let revision=1;const calls=[],sockets=new Set();
 const server=net.createServer(socket=>{
  sockets.add(socket);socket.on('close',()=>sockets.delete(socket));let buffer=Buffer.alloc(0);
  function send(value){const data=Buffer.from(JSON.stringify(value)),h=Buffer.alloc(4);h.writeUInt32LE(data.length);socket.write(Buffer.concat([h,data]));}
  function snapshot(){send({type:'broadcast',method:'thread-stream-state-changed',version:11,sourceClientId:'owner',params:{conversationId:'shared-thread',hostId:'local',change:{type:'snapshot',revision:revision++,conversationState:state}}});}
  socket.on('data',chunk=>{buffer=Buffer.concat([buffer,chunk]);while(buffer.length>=4){const n=buffer.readUInt32LE(0);if(buffer.length<n+4)break;const msg=JSON.parse(buffer.subarray(4,n+4));buffer=buffer.subarray(n+4);
   if(msg.type==='broadcast'){if(msg.method==='thread-stream-following-changed'&&msg.params.following)snapshot();continue;}
   if(msg.type!=='request')continue;
   calls.push(msg);let result={};
   if(msg.method==='initialize')result={clientId:'watch'};
   else if(msg.method==='thread-owner-discovery')result={supportsUntrustedAppInput:true};
   else if(msg.method==='thread-follower-interrupt-turn'){assert.equal(msg.version,4);assert.equal(msg.params.expectedTurnId,'turn-1');state.turns[0].status='interrupted';result={ok:true,interruptedTurnId:'turn-1'};}
   else if(msg.method==='thread-follower-command-approval-decision'){assert.equal(msg.version,1);state.requests=[];result={ok:true};}
   else throw Error('Unexpected mutation: '+msg.method);
   send({type:'response',requestId:msg.requestId,resultType:'success',method:msg.method,handledByClientId:'owner',result});
  }});
 });
 await new Promise(resolve=>server.listen(path,resolve));
 const child=spawn(process.execPath,[fileURLToPath(new URL('./desktop_control.mjs',import.meta.url)),'--test-pipe',path],{stdio:['pipe','pipe','pipe'],windowsHide:true});
 const pending=new Map();let sequence=0;
 const lines=readline.createInterface({input:child.stdout});lines.on('line',line=>{const r=JSON.parse(line),p=pending.get(r.id);if(!p)return;pending.delete(r.id);clearTimeout(p.timer);r.error?p.reject(Error(r.error.message)):p.resolve(r.result);});
 function call(method,params={}){const id=++sequence;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture timed out')),10000);pending.set(id,{resolve,reject,timer});child.stdin.write(JSON.stringify({id,method,params})+'\n');});}
 async function close(){child.stdin.end();await new Promise(resolve=>child.once('exit',resolve));for(const socket of sockets)socket.destroy();await new Promise(resolve=>server.close(resolve));}
 return {call,close,calls,state,request};
}
test('native transport routes stop to the owner and binds the expected turn',async()=>{
 const f=await fixture();try{
  const read=await f.call('read',{threadId:'shared-thread'});assert.equal(read.turnId,'turn-1');
  const stale=await f.call('interrupt',{threadId:'shared-thread',turnId:'older-turn'});assert.equal(stale.alreadyFinished,true);
  assert.equal(f.calls.filter(c=>c.method==='thread-follower-interrupt-turn').length,0);
  await f.call('interrupt',{threadId:'shared-thread',turnId:'turn-1'});
  const sent=f.calls.find(c=>c.method==='thread-follower-interrupt-turn');assert.equal(sent.targetClientId,'owner');assert.equal(sent.params.mode,'user-stop');
 }finally{await f.close();}
});
test('native transport rejects changed approvals and resolves the original request',async()=>{
 const f=await fixture();try{
  const read=await f.call('read',{threadId:'shared-thread'});
  await assert.rejects(f.call('respond',{threadId:'shared-thread',requestId:'approval-1',expectedRequest:'changed',response:'accept'}),/changed/);
  assert.equal(f.calls.filter(c=>c.method==='thread-follower-command-approval-decision').length,0);
  const result=await f.call('respond',{threadId:'shared-thread',requestId:'approval-1',expectedRequest:read.requestJson['approval-1'],response:'decline'});assert.equal(result.resolved,true);
  const sent=f.calls.find(c=>c.method==='thread-follower-command-approval-decision');assert.equal(sent.params.decision,'decline');assert.equal(sent.params.conversationId,'shared-thread');
  const again=await f.call('respond',{threadId:'shared-thread',requestId:'approval-1',expectedRequest:read.requestJson['approval-1'],response:'accept'});assert.equal(again.alreadyResolved,true);
  assert.equal(f.calls.filter(c=>c.method==='thread-follower-command-approval-decision').length,1);
 }finally{await f.close();}
});
test('simultaneous reads share one owner discovery and subscription',async()=>{
 const f=await fixture();try{
  const values=await Promise.all([f.call('read',{threadId:'shared-thread'}),f.call('read',{threadId:'shared-thread'})]);assert.ok(values.every(v=>v.available));
  assert.equal(f.calls.filter(c=>c.method==='thread-owner-discovery').length,1);
 }finally{await f.close();}
});
