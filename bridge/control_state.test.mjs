import {test} from 'node:test';
import assert from 'node:assert/strict';
import {applyPatches,activeTurn,scopedRequests,asyncQuestionRequests} from './control_state.mjs';
test('snapshot plus array patches track removal, replacement and insertion',()=>{
 const s={requests:[{id:'one'},{id:'two'}],turns:[]};
 applyPatches(s,[{op:'remove',path:['requests',0]},{op:'replace',path:['requests',0,'id'],value:'three'},{op:'add',path:['turns',0],value:{turnId:'t1',status:'inProgress'}}]);
 assert.deepEqual(s.requests,[{id:'three'}]);assert.equal(activeTurn(s),'t1');
 applyPatches(s,[{op:'replace',path:['turns',0,'status'],value:'interrupted'}]);assert.equal(activeTurn(s),null);
});
test('canonical history and live turns share the original active turn',()=>{
 const s={turnHistory:{kind:'canonical',history:{entitiesByKey:{a:{turnId:'a',status:'completed'},b:{turnId:'b',status:'inProgress'}},islands:[{entries:[{value:'a'},{value:'b'}]}]}},turns:[]};
 assert.equal(activeTurn(s),'b');s.turns.push({turnId:'b',status:'completed'});assert.equal(activeTurn(s),null);
});
test('request projection excludes other conversations',()=>{
 assert.equal(scopedRequests({requests:[{params:{threadId:'one'}},{params:{threadId:'two'}}]},'one').length,1);
});
test('invalid patch paths fail before mutating prototypes',()=>{
 assert.throws(()=>applyPatches({},[{op:'add',path:['__proto__','bad'],value:true}]));assert.equal({}.bad,undefined);
 assert.throws(()=>applyPatches({},[{op:'replace',path:['missing','child'],value:1}]));
});
const questions=()=>({id:'thread',turns:[{turnId:'t',status:'inProgress',items:[{type:'agentMessage',id:'call-1',questions:[{title:'选一个',options:['一','二']},{title:'填写地址',options:null}]}]}]});
test('async assistant questions use the native question identity and remain individually answerable',()=>{
 const q=asyncQuestionRequests(questions(),'thread');assert.equal(q.length,2);
 assert.equal(q[0].method,'watch/asyncQuestion');assert.equal(q[0].params.questions[0].id,JSON.stringify(['request_user_input_async','call-1',0]));
 assert.deepEqual(q[0].params.questions[0].options.map(o=>o.label),['一','二']);
 assert.equal(q[1].params.questions[0].isOther,true);assert.deepEqual(q[1].params.questions[0].options,[]);
 assert.deepEqual(asyncQuestionRequests(questions(),'different'),[]);
});
test('accepted native answers remove their question while other questions remain',()=>{
 for(const kind of ['userMessage','steeringUserMessage']){
  const s=questions(),id=JSON.stringify(['request_user_input_async','call-1',0]);
  const text='<send_user_message_question_reply>\n'+JSON.stringify([{questionItemId:id,question:'选一个',answer:'二'}])+'\n</send_user_message_question_reply>';
  s.turns[0].items.push({type:kind,status:'accepted',[kind==='userMessage'?'content':'input']:[{type:'text',text}]});
  const q=asyncQuestionRequests(s,'thread');assert.equal(q.length,1);assert.equal(q[0].params.questions[0].question,'填写地址');
 }
});
test('old and interrupted turns never resurrect unanswered questions',()=>{
 const s=questions();s.turns.push({turnId:'next',status:'inProgress',items:[]});assert.deepEqual(asyncQuestionRequests(s,'thread'),[]);
 s.turns.pop();s.turns[0].status='interrupted';assert.deepEqual(asyncQuestionRequests(s,'thread'),[]);
});
test('canonical questions and completed turns work without native approval requests',()=>{
 const s=questions(),turn=s.turns[0];turn.status='completed';s.turns=[];
 s.turnHistory={kind:'canonical',history:{entitiesByKey:{t:turn},islands:[{entries:[{value:'t'}]}]}};
 assert.equal(asyncQuestionRequests(s,'thread').length,2);
 turn.items.push({type:'userMessage',content:[{type:'text',text:'<send_user_message_question_reply>broken</send_user_message_question_reply>'}]});
 assert.equal(asyncQuestionRequests(s,'thread').length,2);
});
