// Local-only companion client. Never starts or takes ownership of a conversation.
import net from 'node:net';
import readline from 'node:readline';
import {randomUUID} from 'node:crypto';
import {applyPatches,activeTurn,scopedRequests,asyncQuestionRequests} from './control_state.mjs';
const LIMIT=64*1024*1024, TIMEOUT=6000;
// An isolated named pipe is injectable only by the local transport test runner.
const testPipe=process.argv[2]==='--test-pipe'?process.argv[3]:null;
if(testPipe&&!testPipe.startsWith('\\\\.\\pipe\\watch-control-test-'))throw Error('Invalid isolated test pipe');
const pipePath=testPipe??'\\\\.\\pipe\\codex-ipc';
let socket,connecting,buffer=Buffer.alloc(0),clientId;
const pending=new Map(),subscriptions=new Map(),discoveries=new Map();
function fail(error){socket?.destroy();socket=undefined;clientId=undefined;buffer=Buffer.alloc(0);for(const p of pending.values()){clearTimeout(p.timer);p.reject(error);}pending.clear();for(const s of subscriptions.values()){s.state=null;for(const w of s.waiters??[])w.reject(error);}subscriptions.clear();}
function send(value){const data=Buffer.from(JSON.stringify(value));if(data.length>LIMIT)throw Error('Desktop control frame too large');const header=Buffer.alloc(4);header.writeUInt32LE(data.length);socket.write(Buffer.concat([header,data]));}
function request(method,params,version=1,targetClientId){const requestId=randomUUID();return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(requestId);reject(Error('Desktop control timed out; refresh before retrying'));},TIMEOUT);pending.set(requestId,{resolve,reject,timer});send({type:'request',requestId,sourceClientId:clientId??'initializing-client',version,method,params,targetClientId,timeoutMs:TIMEOUT-500});});}
function following(s,value){send({type:'broadcast',method:'thread-stream-following-changed',version:1,sourceClientId:clientId,targetClientIds:[s.owner],params:{conversationId:s.id,hostId:'local',following:value}});}
function onMessage(msg){
  if(msg.type==='client-discovery-request'){send({type:'client-discovery-response',requestId:msg.requestId,response:{canHandle:false}});return;}
  if(msg.type==='response'){const p=pending.get(msg.requestId);if(!p)return;pending.delete(msg.requestId);clearTimeout(p.timer);if(msg.resultType==='error')p.reject(Error(msg.error));else p.resolve(msg);return;}
  if(msg.type!=='broadcast')return;
  if(msg.method==='client-status-changed'&&msg.params?.status==='disconnected')for(const s of subscriptions.values())if(s.owner===msg.params.clientId){for(const w of s.waiters.splice(0))w.reject(Error('Desktop owner disconnected'));subscriptions.delete(s.id);}
  if(msg.method==='thread-stream-following-status-requested'){const s=subscriptions.get(msg.params?.conversationId);if(s&&s.owner===msg.sourceClientId)following(s,true);}
  if(msg.method!=='thread-stream-state-changed'||msg.version!==11||msg.params?.hostId!=='local')return;
  const s=subscriptions.get(msg.params.conversationId);if(!s||s.owner!==msg.sourceClientId)return;
  const change=msg.params.change;
  try{
    if(change.type==='snapshot'){
      if(change.conversationState?.id!==s.id)throw Error('Desktop state belongs to another conversation');
      s.state=change.conversationState;s.revision=change.revision;
      for(const w of s.waiters.splice(0))w.resolve();
    }else if(change.type==='patches'&&s.state&&s.revision===change.baseRevision){s.state=applyPatches(s.state,change.patches);s.revision=change.revision;}
    else s.state=null;
  }catch{s.state=null;}
}
async function connect(){
 if(socket&&!socket.destroyed&&clientId)return;
 if(connecting)return connecting;
 connecting=(async()=>{
  socket=await new Promise((resolve,reject)=>{const s=net.createConnection(pipePath);const t=setTimeout(()=>{s.destroy();reject(Error('Desktop control unavailable'));},2500);s.once('connect',()=>{clearTimeout(t);resolve(s)});s.once('error',e=>{clearTimeout(t);reject(e)});});
  const current=socket;
  socket.on('data',chunk=>{if(socket!==current)return;buffer=Buffer.concat([buffer,chunk]);while(buffer.length>=4){const n=buffer.readUInt32LE(0);if(n<1||n>LIMIT){fail(Error('Invalid control frame'));return;}if(buffer.length<n+4)break;try{const msg=JSON.parse(buffer.subarray(4,n+4));buffer=buffer.subarray(n+4);onMessage(msg);}catch{fail(Error('Invalid desktop control message'));return;}}});
  socket.on('error',e=>{if(socket===current)fail(e)});socket.on('close',()=>{if(socket===current)fail(Error('Desktop control disconnected'))});
  const reply=await request('initialize',{clientType:'watch-companion'},0);clientId=reply.result.clientId;
 })().finally(()=>{connecting=undefined});return connecting;
}
async function snapshot(s){
 if(s.loading)return s.loading;
 s.loading=loadSnapshot(s).finally(()=>{s.loading=null});return s.loading;
}
async function loadSnapshot(s){
 const promise=new Promise((resolve,reject)=>{const waiter={resolve:()=>{clearTimeout(timer);resolve();},reject:e=>{clearTimeout(timer);reject(e)}};const timer=setTimeout(()=>{s.waiters=s.waiters.filter(w=>w!==waiter);reject(Error('Desktop snapshot timed out'));},TIMEOUT);s.waiters.push(waiter);});
 following(s,false);following(s,true);await promise;
}
async function follow(id,force=false){
 await connect();if(typeof id!=='string'||!id||id.length>100)throw Error('Invalid conversation');
 let s=subscriptions.get(id);
 if(!s){
  if(!discoveries.has(id))discoveries.set(id,(async()=>{
   const owner=await request('thread-owner-discovery',{hostId:'local',conversationId:id});
   const value={id,owner:owner.handledByClientId,state:null,revision:null,waiters:[],used:Date.now()};subscriptions.set(id,value);
   if(subscriptions.size>4){const old=[...subscriptions.values()].filter(x=>x!==value).sort((a,b)=>a.used-b.used)[0];following(old,false);subscriptions.delete(old.id);}
   return value;
  })().finally(()=>discoveries.delete(id)));
  s=await discoveries.get(id);
 }
 s.used=Date.now();
 if(force||!s.state){try{await snapshot(s)}catch(error){subscriptions.delete(id);throw error;}}
 return s;
}
function projection(s){
 const requests=[...scopedRequests(s.state,s.id),...asyncQuestionRequests(s.state,s.id)], turns=[...Object.values(s.state.turnHistory?.history?.entitiesByKey??{}),...(s.state.turns??[])];
 const contexts={};for(const r of requests){if(r.method==='watch/asyncQuestion')continue;const t=turns.find(t=>t.turnId===r.params?.turnId);const item=t?.items?.find(i=>i.id===r.params?.itemId);if(item)contexts[String(r.id)]=item;}
 return {available:true,threadId:s.id,owner:s.owner,revision:s.revision,turnId:activeTurn(s.state),runtime:s.state.threadRuntimeStatus,requests,requestJson:Object.fromEntries(requests.map(r=>[String(r.id),JSON.stringify(r)])),contexts,contextJson:Object.fromEntries(Object.entries(contexts).map(([id,item])=>[id,JSON.stringify(item)]))};
}
async function handle(message){
 const p=message.params??{};
 if(message.method==='catalog'){await connect();return {available:true,protocol:'desktop-follower-v11'};}
 if(message.method==='read'){try{return projection(await follow(p.threadId,!!p.fresh));}catch(error){return {available:false,threadId:p.threadId,error:error.message,requests:[]};}}
 if(message.method==='interrupt'){
  if(!p.turnId)throw Error('Missing expected turn');
  const s=await follow(p.threadId,true);
  if(activeTurn(s.state)!==p.turnId)return {ok:true,alreadyFinished:true};
  const reply=await request('thread-follower-interrupt-turn',{conversationId:s.id,mode:'user-stop',expectedTurnId:p.turnId},4,s.owner);
  return reply.result;
 }
 if(message.method==='answerAsyncQuestion'){
  const s=await follow(p.threadId,true);
  const question=asyncQuestionRequests(s.state,s.id).find(r=>r.id===p.requestId);
  if(!question||JSON.stringify(question)!==p.expectedRequest)return {ok:false,notPending:true};
  const replies=question.params.questions.map(q=>({questionItemId:q.id,question:q.question,answer:p.answers[q.id]}));
  const text='<send_user_message_question_reply>\n'+JSON.stringify(replies)+'\n</send_user_message_question_reply>';
  const clientUserMessageId=randomUUID(), turnTrigger='send_user_message_async_question';
  const input=[{type:'text',text,text_elements:[]}];
  const restoreMessage={id:clientUserMessageId,text,cwd:s.state.cwd,createdAt:Date.now(),
    context:{prompt:text,turnTrigger,addedFiles:[],fileAttachments:[],ideContext:null,imageAttachments:[]},
    responsesapiClientMetadata:{source:'codex'}};
  // Match the desktop composer so the answer participates in its question and timeline state.
  if(activeTurn(s.state)===question.params.turnId){
   await request('thread-follower-steer-turn',{conversationId:s.id,input,restoreMessage,clientUserMessageId,attachments:[]},1,s.owner);
  }else{
   const turnStart={request:{threadId:s.id,input,clientUserMessageId,turnTrigger,responsesapiClientMetadata:{source:'codex'}},
     context:{restoreMessage,attachments:[],inheritThreadSettings:true}};
   await request('thread-follower-start-turn',{conversationId:s.id,turnStart},2,s.owner);
  }
  return {ok:true};
 }
 if(message.method==='respond'){
  const s=await follow(p.threadId,true),r=scopedRequests(s.state,s.id).find(r=>r.id===p.requestId);
  if(!r)return {ok:true,alreadyResolved:true};
  // The bridge validates the displayed request fingerprint and allowed response.
  if(JSON.stringify(r)!==p.expectedRequest)throw Error('Approval changed; refresh and review it again');
  if((projection(s).contextJson[String(r.id)]??null)!==(p.expectedContext??null))throw Error('Operation details changed; refresh and review them again');
  const methods={'item/commandExecution/requestApproval':['thread-follower-command-approval-decision','decision'],'item/fileChange/requestApproval':['thread-follower-file-approval-decision','decision'],'item/permissions/requestApproval':['thread-follower-permissions-request-approval-response','response'],'item/tool/requestUserInput':['thread-follower-submit-user-input','response'],'mcpServer/elicitation/request':['thread-follower-submit-mcp-server-elicitation-response','response']};
  const entry=methods[r.method];if(!entry)throw Error('Unsupported desktop approval');
  const reply=await request(entry[0],{conversationId:s.id,requestId:r.id,[entry[1]]:p.response},1,s.owner);
  await snapshot(s);
  return {...reply.result,resolved:!scopedRequests(s.state,s.id).some(x=>x.id===r.id)};
 }
 throw Error('Unsupported companion control operation');
}
const lines=readline.createInterface({input:process.stdin});
lines.on('line',line=>{let msg;try{msg=JSON.parse(line)}catch{return;}handle(msg).then(result=>process.stdout.write(JSON.stringify({id:msg.id,result})+'\n')).catch(error=>process.stdout.write(JSON.stringify({id:msg.id,error:{message:error.message}})+'\n'));});
lines.on('close',()=>{for(const s of subscriptions.values())if(socket&&!socket.destroyed&&clientId)following(s,false);fail(Error('Companion closed'));process.exit();});
