// State projection for the desktop's versioned follower coordination protocol.
export function applyPatches(state, patches) {
  for (const patch of patches) {
    const path=patch.path;
    if(!Array.isArray(path)||path.some(p=>['__proto__','constructor','prototype'].includes(String(p))))throw Error('Invalid desktop patch path');
    if(!path.length){if(patch.op==='remove')throw Error('Cannot remove state');state=structuredClone(patch.value);continue;}
    let parent=state;
    for(const key of path.slice(0,-1)){if(parent==null||!Object.hasOwn(parent,key))throw Error('Missing desktop patch parent');parent=parent[key];}
    const key=path.at(-1);
    if(patch.op==='remove'){if(Array.isArray(parent))parent.splice(Number(key),1);else delete parent[key];}
    else if(patch.op==='add'&&Array.isArray(parent))parent.splice(Number(key),0,structuredClone(patch.value));
    else if(patch.op==='add'||patch.op==='replace')parent[key]=structuredClone(patch.value);
    else throw Error('Unsupported desktop patch operation');
  }
  return state;
}
export function activeTurn(state) {
  const history=state.turnHistory?.kind==='canonical'?state.turnHistory.history:null;
  const ordered=history?(history.islands??[]).flatMap(i=>(i.entries??[]).map(e=>history.entitiesByKey?.[e.value]).filter(Boolean)):[];
  const turns=new Map(ordered.filter(t=>t.turnId).map(t=>[t.turnId,t]));
  for(const t of state.turns??[])if(t.turnId)turns.set(t.turnId,t);
  const latest=[...turns.values()].at(-1);
  return latest?.status==='inProgress'?latest.turnId:null;
}
export function scopedRequests(state, threadId) {
  return (state.requests??[]).filter(r=>r.params?.threadId===threadId);
}
export function asyncQuestionRequests(state,threadId) {
  if(state.id!==threadId)return [];
  const history=state.turnHistory?.kind==='canonical'?state.turnHistory.history:null;
  const ordered=history?(history.islands??[]).flatMap(i=>(i.entries??[]).map(e=>history.entitiesByKey?.[e.value]).filter(Boolean)):[];
  const turns=new Map(ordered.filter(t=>t.turnId).map(t=>[t.turnId,t]));
  for(const turn of state.turns??[])if(turn.turnId)turns.set(turn.turnId,turn);
  const all=[...turns.values()],latest=all.at(-1),answered=new Set();
  for(const turn of all)for(const item of turn.items??[]) {
    if(item.type!=='userMessage'&&!(item.type==='steeringUserMessage'&&item.status==='accepted'))continue;
    const text=(item.content??item.input??[]).filter(c=>c.type==='text').map(c=>c.text??'').join('\n');
    const start='<send_user_message_question_reply>',end='</send_user_message_question_reply>',index=text.lastIndexOf(start);
    if(index<0||!text.trimEnd().endsWith(end))continue;
    try {const value=JSON.parse(text.slice(index+start.length,text.lastIndexOf(end)));
      for(const reply of Array.isArray(value)?value:[value])if(typeof reply.questionItemId==='string')answered.add(reply.questionItemId);
    }catch { /* Ordinary user messages are never interpreted as answers. */ }
  }
  if(!latest||['interrupted','failed'].includes(latest.status))return [];
  const requests=[];
  for(const item of latest.items??[])if(item.type==='agentMessage'&&typeof item.id==='string') {
    for(const [index,q] of (item.questions??[]).entries()) {
      if(typeof q.title!=='string')continue;
      const id=JSON.stringify(['request_user_input_async',item.id,index]);
      if(answered.has(id))continue;
      requests.push({id:'async:'+id,method:'watch/asyncQuestion',params:{threadId,turnId:latest.turnId,itemId:item.id,
        questions:[{id,question:q.title,required:true,isOther:true,options:(q.options??[]).filter(o=>typeof o==='string').map(label=>({label,description:''}))}]}});
    }
  }
  return requests;
}
