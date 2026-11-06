"""Project and conversation presentation based only on desktop-supplied metadata."""
import ntpath


def local_projects(value):
    return [{'id':p['projectId'],'name':p.get('label') or '未命名项目','path':p.get('path')}
            for p in value.get('projects',[]) if p.get('projectKind')=='local' and p.get('hostId')=='local']


def project_for_thread(summary,projects):
    project_id=summary.get('projectId')
    if project_id:
        return next((p for p in projects if p['id']==project_id),{'id':project_id,'name':'未识别项目','path':None})
    cwd=summary.get('cwd')
    if not isinstance(cwd,str) or not ntpath.isabs(cwd):return None
    cwd=ntpath.normcase(ntpath.normpath(cwd))
    matches=[]
    for p in projects:
        path=p.get('path')
        if not isinstance(path,str) or not ntpath.isabs(path):continue
        path=ntpath.normcase(ntpath.normpath(path))
        if cwd==path or cwd.startswith(path.rstrip('\\')+'\\'):matches.append((len(path),p))
    return max(matches,key=lambda item:item[0])[1] if matches else None


def thread_status(summary,metadata=None):
    status=summary.get('status')
    details=metadata.get('status',{}) if metadata else {}
    if isinstance(details,dict):
        status=details.get('type') or status
        flags=details.get('activeFlags') or []
    else:flags=[]
    unread=summary.get('isUnread') if isinstance(summary.get('isUnread'),bool) else None
    waiting=status in ('waitingOnApproval','waitingOnUserInput') or any(f in flags for f in ('waitingOnApproval','waitingOnUserInput'))
    if waiting:code,label='waiting','等你回复'
    elif status=='active':code,label='running','运行中'
    elif unread is True:code,label='unread','有新回复'
    elif status=='notLoaded':code,label='idle','未运行'
    elif status in ('idle','completed'):code,label='idle','空闲'
    else:code,label='unknown','状态未知'
    return {'status':code,'statusLabel':label,'busy':code in ('running','waiting'),'unread':unread}
