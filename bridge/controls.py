"""Project native desktop approvals into explicit, scoped watch interactions."""
import asyncio
import hashlib
import json
import math
from aiohttp import web
from desktop import DesktopClient, RpcError


def fingerprint(request, context=None):
    value=request if context is None else {'request':request,'context':context}
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def approval_view(request, context=None):
    method=request['method']; p=request.get('params',{})
    result={'token':fingerprint(request,context),'kind':'approval','title':'待确认操作','details':'','actions':[],'questions':[]}
    details=[]
    if p.get('reason'):details.append('原因：'+p['reason'])
    if p.get('cwd'):details.append('位置：'+str(p['cwd']))
    if method=='item/commandExecution/requestApproval':
        net=p.get('networkApprovalContext')
        result['title']='允许网络访问？' if net else '允许执行命令？'
        if net:details.append('访问：'+str(net.get('protocol',''))+'://'+str(net.get('host','')))
        elif p.get('command'):details.append('命令：\n'+p['command'])
        result['actions']=[{'id':'accept','label':'允许这一次'},{'id':'decline','label':'拒绝'},{'id':'cancel','label':'取消本次操作'}]
    elif method=='item/fileChange/requestApproval':
        result['title']='允许修改文件？'
        if p.get('grantRoot'):details.append('请求写入位置：'+p['grantRoot'])
        result['actions']=[{'id':'accept','label':'允许这一次'},{'id':'decline','label':'拒绝'},{'id':'cancel','label':'取消本次操作'}]
    elif method=='item/permissions/requestApproval':
        result['title']='允许本轮访问权限？'
        details.append('申请范围：\n'+json.dumps(p.get('permissions',{}),ensure_ascii=False,indent=2))
        result['actions']=[{'id':'accept','label':'仅允许本轮'},{'id':'decline','label':'不允许'}]
    elif method in ('item/tool/requestUserInput','watch/asyncQuestion'):
        result.update(kind='questions',title='需要你的确认',questions=p.get('questions') or [])
        result['actions']=[{'id':'answer','label':'提交选择'},{'id':'cancel','label':'取消回答'}]
        if method=='watch/asyncQuestion':
            result['title']=(p.get('questions') or [{}])[0].get('question') or '需要你的回复'
            result['actions']=[{'id':'answer','label':'提交回复'}]
    elif method=='mcpServer/elicitation/request':
        result['title']='确认应用操作';details.append(p.get('message',''))
        schema=p.get('requestedSchema',{}); props=schema.get('properties',{}) if isinstance(schema,dict) else {}
        required=schema.get('required',[]) if isinstance(schema,dict) else []
        supported=p.get('mode') in ('form','openai/form','openaiForm')
        questions=[]
        for key,field in props.items():
            typ=field.get('type','string')
            values=field.get('enum')
            if not values and field.get('oneOf') and all('const' in v for v in field['oneOf']):values=[v['const'] for v in field['oneOf']]
            if typ=='boolean':values=[True,False]
            if typ not in ('string','number','integer','boolean') or field.get('format') in ('password','email','uri'):supported=False
            questions.append({'id':key,'header':field.get('title',key),'question':field.get('description',field.get('title',key)), 'required':key in required,'valueType':typ,'values':values,'options':[{'label':str(v),'description':''} for v in values] if values else None})
        result.update(kind='form',questions=questions)
        if supported:result['actions'].append({'id':'answer' if questions else 'accept','label':'确认提交' if questions else '允许这一次'})
        else:details.append('此项包含登录验证或复杂表单，当前手表无法完成。')
        result['actions'] += [{'id':'decline','label':'拒绝'},{'id':'cancel','label':'取消'}]
    else:
        details.append('当前桌面版本尚未开放这类确认：'+method)
    if context and method in ('item/fileChange/requestApproval','item/commandExecution/requestApproval'):
        details.append('操作详情：\n'+json.dumps(context,ensure_ascii=False,indent=2))
    if isinstance(p.get('availableDecisions'),list):
        result['actions']=[a for a in result['actions'] if a['id'] in p['availableDecisions']]
    result['details']='\n\n'.join(details)
    return result


def approval_response(request, action, answers=None):
    view=approval_view(request)
    if action not in {a['id'] for a in view['actions']}:
        raise web.HTTPBadRequest(text='这项操作不支持所选决定，请刷新确认内容')
    method=request['method'];p=request['params']
    if method in ('item/commandExecution/requestApproval','item/fileChange/requestApproval'):return action
    if method=='item/permissions/requestApproval':return {'permissions':{k:v for k,v in p.get('permissions',{}).items() if k in ('fileSystem','network')} if action=='accept' else {},'scope':'turn'}
    if method in ('item/tool/requestUserInput','watch/asyncQuestion'):
        if action=='cancel':return {'answers':{}}
        if not isinstance(answers,dict):raise web.HTTPBadRequest(text='请完成所有问题')
        result={}
        for question in p.get('questions',[]):
            value=answers.get(question['id'])
            if not isinstance(value,str) or not value.strip() or len(value)>8000:raise web.HTTPBadRequest(text='请完成所有问题')
            allowed=[o['label'] for o in question.get('options') or []]
            if allowed and value not in allowed and not question.get('isOther'):raise web.HTTPBadRequest(text='请选择提供的选项')
            result[question['id']]={'answers':[value]}
        return {'answers':result}
    if method=='mcpServer/elicitation/request':
        if action in ('decline','cancel'):return {'action':action,'content':None}
        answers=answers or {};content={}
        schema=p.get('requestedSchema',{})
        for question in view['questions']:
            key=question['id']; value=answers.get(key)
            if value is None or value=='':
                if question['required']:raise web.HTTPBadRequest(text='请完成必填项目')
                continue
            values=question.get('values')
            if values:
                choices=[v for v in values if str(v)==str(value)]
                if not choices:raise web.HTTPBadRequest(text='选项已改变，请重新选择')
                value=choices[0]
            elif question['valueType'] in ('number','integer'):
                try:value=int(value) if question['valueType']=='integer' else float(value)
                except (ValueError,TypeError):raise web.HTTPBadRequest(text='请输入有效数字')
                if not math.isfinite(value):raise web.HTTPBadRequest(text='请输入有效数字')
            elif not isinstance(value,str) or len(value)>8000:raise web.HTTPBadRequest(text='输入内容无效或过长')
            field=schema['properties'][key]
            if isinstance(value,str) and (len(value)<field.get('minLength',0) or len(value)>field.get('maxLength',8000)):raise web.HTTPBadRequest(text='输入长度不符合要求')
            if isinstance(value,(int,float)) and not isinstance(value,bool) and (value<field.get('minimum',float('-inf')) or value>field.get('maximum',float('inf'))):raise web.HTTPBadRequest(text='数字不在允许范围')
            content[key]=value
        return {'action':'accept','content':content}
    raise web.HTTPBadRequest(text='不支持的确认类型')


class DesktopControls:
    def __init__(self, client=None):
        self.client=client or DesktopClient('desktop_control.mjs')
        self.locks={}
        self.completed={}

    async def read(self, thread_id, fresh=False):
        try:return await self.client.call('read',{'threadId':thread_id,'fresh':fresh})
        except (RpcError,OSError,asyncio.TimeoutError) as error:return {'available':False,'requests':[],'error':str(error)}

    async def interrupt(self, thread_id, turn_id):
        if not isinstance(turn_id,str) or not turn_id:raise web.HTTPBadRequest(text='缺少本次回复编号，请刷新')
        async with self.locks.setdefault(thread_id,asyncio.Lock()):
            return await self.client.call('interrupt',{'threadId':thread_id,'turnId':turn_id})

    async def respond(self, thread_id, token, action, answers=None):
        async with self.locks.setdefault(thread_id,asyncio.Lock()):
            old=self.completed.get((thread_id,token))
            if old:
                if old['action']!=action or old['answers']!=answers:raise web.HTTPConflict(text='这项请求已处理，请查看最新状态')
                return {'ok':True,'alreadyResolved':True}
            value=await self.read(thread_id,True)
            if not value.get('available'):raise web.HTTPServiceUnavailable(text='控制连接暂不可用，请稍后刷新')
            request=next((r for r in value.get('requests',[]) if r.get('params',{}).get('threadId')==thread_id and fingerprint(r,value.get('contexts',{}).get(str(r['id'])))==token),None)
            if request is None:raise web.HTTPConflict(text='确认已处理或内容已改变，请查看最新状态')
            response=approval_response(request,action,answers)
            result=await self.client.call('respond',{'threadId':thread_id,'requestId':request['id'],'expectedRequest':value.get('requestJson',{}).get(str(request['id'])) or json.dumps(request,ensure_ascii=False,separators=(',',':')),'expectedContext':value.get('contextJson',{}).get(str(request['id'])),'response':response})
            if result.get('ok') or result.get('alreadyResolved'):
                self.completed[thread_id,token]={'action':action,'answers':answers}
                if len(self.completed)>200:self.completed.pop(next(iter(self.completed)))
            return result

    async def close(self):await self.client.close()
