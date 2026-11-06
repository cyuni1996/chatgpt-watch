"""Real-watch regression against power_navigation_fixture.py; never sends a chat or approval.

Requires a debuggable APK. Saves/restores every preference and never changes the screen timeout.
"""
import argparse
import hashlib
import json
import re
import ssl
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
APP='org.watchchat.app'
parser=argparse.ArgumentParser()
parser.add_argument('--adb',required=True)
parser.add_argument('--serial',required=True)
parser.add_argument('--phase',choices=['all','power'],default='all')
args=parser.parse_args()
ADB=[args.adb,'-s',args.serial]
OUT=ROOT/'.local/v072-device'
OUT.mkdir(parents=True,exist_ok=True)
results={}
if args.phase=='power' and (OUT/'verification-result.json').exists():
    results=json.loads((OUT/'verification-result.json').read_text(encoding='utf8'))

def adb(*parts):
    value=subprocess.run(ADB+list(parts),capture_output=True,timeout=30)
    if value.returncode:raise RuntimeError(value.stderr.decode(errors='replace'))
    return value.stdout

def fixture(path):
    context=ssl.create_default_context(cafile=str(ROOT/'.local/server.pem'))
    context.check_hostname=False
    with urllib.request.urlopen('https://127.0.0.1:8767/fixture/'+path,context=context,timeout=5) as response:
        return json.load(response)

def dump():
    adb('shell','input','keyevent','KEYCODE_WAKEUP')
    for attempt in range(3):
        try:
            adb('shell','uiautomator','dump','/sdcard/watch-v072.xml')
            return ET.fromstring(adb('shell','cat','/sdcard/watch-v072.xml'))
        except (ET.ParseError,RuntimeError):
            if attempt==2:raise
            time.sleep(.4)

def active():
    focus=adb('shell','dumpsys','window').decode(errors='replace')
    found=re.search(r'mCurrentFocus=(.*)',focus)
    return bool(found and APP in found.group(1))

def has(label):
    return any(n.get('text')==label for n in dump().iter('node'))

def click(label,description=False):
    for _ in range(6):
        tree=dump()
        assert any(n.get('package')==APP for n in tree.iter('node')),'Watch locked or app changed'
        key='content-desc' if description else 'text'
        for node in tree.iter('node'):
            if node.get(key)!=label:continue
            if not description and node.get('clickable')!='true':continue
            a,b,c,d=map(int,re.findall(r'\d+',node.get('bounds','')))
            if 45<(b+d)/2<440 and d-b>10:
                adb('shell','input','tap',str((a+c)//2),str((b+d)//2));time.sleep(.25);return
        adb('shell','input','rotaryencoder','scroll','--axis','SCROLL,-2');time.sleep(.2)
    raise AssertionError('Missing control '+ascii(label))

def start():
    adb('shell','input','keyevent','KEYCODE_WAKEUP')
    adb('shell','am','start','-n',APP+'/.MainActivity')
    for _ in range(15):
        adb('shell','input','keyevent','KEYCODE_WAKEUP')
        if active():return
        time.sleep(.3)
    raise AssertionError('Unlock watch to continue')

def swipe(left=True,edge=False):
    x1,x2=((450,8) if left else (8,450)) if edge else ((380,90) if left else (90,380))
    adb('shell','input','swipe',str(x1),'233',str(x2),'233','350');time.sleep(.4)

def ticks(pid):
    try:
        raw=adb('shell','run-as',APP,'cat','/proc/'+pid+'/stat').decode()
        fields=raw.rsplit(')',1)[1].split()
        return int(fields[11])+int(fields[12])
    except (RuntimeError,ValueError,IndexError):return None

original=adb('exec-out','run-as',APP,'cat','shared_prefs/connection.xml')
(OUT/'verification-original-prefs.xml').write_bytes(original)
prepared=False
try:
    adb('shell','am','force-stop',APP)
    prefs=ET.fromstring(original)
    def setval(name,value,kind='string'):
        node=next((n for n in prefs if n.get('name')==name),None)
        if node is None:node=ET.SubElement(prefs,kind,{'name':name})
        if kind=='boolean':node.set('value',value)
        else:node.text=value
    setval('url','https://127.0.0.1:8767');setval('token','isolated-fixture')
    setval('autoRead','false','boolean')
    setval('pin',hashlib.sha256(ssl.PEM_cert_to_DER_cert((ROOT/'.local/server.pem').read_text())).hexdigest())
    testprefs=OUT/'fixture-prefs.xml'
    testprefs.write_bytes(ET.tostring(prefs,encoding='utf8',xml_declaration=True))
    adb('push',str(testprefs),'/data/local/tmp/watch-v072-prefs.xml')
    adb('shell','run-as',APP,'cp','/data/local/tmp/watch-v072-prefs.xml','shared_prefs/connection.xml')
    prepared=True
    adb('reverse','tcp:8767','tcp:8767')
    start();time.sleep(2)
    assert has('导航与省电测试'),'TLS fixture did not connect'
    if args.phase!='power':
        click('当前对话菜单',True);click('设置');click('操作与手势')
        swipe(left=True)
        assert active() and has('设置'),'Left swipe skipped settings'
        swipe(left=False,edge=True)
        assert active() and has('对话操作'),'System edge swipe skipped menu or exited'
        swipe(left=True)
        assert active() and not has('对话操作')
        results['helpLeftSwipeReturnsSettings']=True
        results['edgeRightSwipeReturnsParentMenu']=True
        click('打开历史对话',True);click('查看账号额度',True)
        assert has('账号额度')
        swipe(left=True,edge=True)
        assert active() and has('全部'),'Usage back did not restore history'
        click('关闭历史对话',True)
        results['usageEdgeLeftSwipeRestoresHistory']=True
        click('当前对话菜单',True);click('设置');click('操作与手势')
        adb('shell','input','swipe','230','360','200','140','350')
        assert active() and has('操作与手势')
        adb('shell','input','keyevent','KEYCODE_BACK');assert has('设置')
        click('返回上一页',True);assert has('对话操作')
        adb('shell','input','keyevent','KEYCODE_BACK')
        assert active() and not has('对话操作')
        results['verticalScrollBackKeyAndHeader']=True
    for _ in range(3):adb('shell','am','start','-n',APP+'/.MainActivity')
    stack=adb('shell','dumpsys','activity','activities').decode(errors='replace')
    assert len([line for line in stack.splitlines() if re.search(r'Hist\s*#',line) and APP+'/' in line])==1
    results['repeatedLaunchSingleActivity']=True
    before=len(fixture('stats')['requests']);time.sleep(16)
    stats=fixture('stats');idle=[r['time'] for r in stats['requests'][before:] if r['path']=='/api/state']
    assert 2<=len(idle)<=4 and all(b-a>=4.5 for a,b in zip(idle,idle[1:]))
    results['idlePollIntervalsSeconds']=[round(b-a,3) for a,b in zip(idle,idle[1:])]
    click('打开历史对话',True)
    time.sleep(6);before=len(fixture('stats')['requests']);time.sleep(22)
    stats=fixture('stats');panel=[r['time'] for r in stats['requests'][before:] if r['path']=='/api/state']
    assert 1<=len(panel)<=3 and all(b-a>=9.5 for a,b in zip(panel,panel[1:]))
    results['panelPollIntervalsSeconds']=[round(b-a,3) for a,b in zip(panel,panel[1:])]
    click('关闭历史对话',True)
    fixture('hold?path=/api/state')
    for _ in range(100):
        if fixture('stats')['active']>0:break
        time.sleep(.15)
    else:raise AssertionError('Held request never started')
    pid=adb('shell','pidof',APP).decode().strip()
    adb('shell','input','keyevent','KEYCODE_HOME')
    for _ in range(60):
        stats=fixture('stats')
        if stats['active']==0:break
        time.sleep(.05)
    assert stats['active']==0 and stats['cancelled']>0,'Background request did not cancel'
    time.sleep(2);count=len(fixture('stats')['requests']);cpu=ticks(pid);time.sleep(12)
    assert len(fixture('stats')['requests'])==count,'Network continued in background'
    after=ticks(pid)
    results['backgroundRequestsDuring12Seconds']=0
    results['backgroundCpuTicksDuring12Seconds']=None if cpu is None or after is None else after-cpu
    results['inFlightRequestCancelled']=True
    services=adb('shell','dumpsys','activity','services',APP).decode(errors='replace')
    assert 'ServiceRecord{' not in services
    results['noRunningServices']=True
    fixture('hold?path=/api/state&enabled=0')
    count=len(fixture('stats')['requests']);start();time.sleep(2)
    assert len(fixture('stats')['requests'])>count
    results['resumeRefreshesImmediately']=True
    swipe(left=True)
    assert not active(),'Root swipe did not exit'
    history=adb('shell','dumpsys','activity','activities').decode(errors='replace')
    assert not any(re.search(r'Hist\s*#',line) and APP+'/' in line for line in history.splitlines())
    count=len(fixture('stats')['requests']);time.sleep(8)
    assert len(fixture('stats')['requests'])==count
    results['rootExitRemovesTaskAndStopsRequests']=True
    results['status']='passed'
except BaseException:
    try:
        adb('shell','screencap','-p','/sdcard/watch-v072-failure.png')
        adb('pull','/sdcard/watch-v072-failure.png',str(OUT/'failure.png'))
        (OUT/'failure-window.txt').write_bytes(adb('shell','dumpsys','window'))
        (OUT/'failure-ui.xml').write_bytes(adb('shell','cat','/sdcard/watch-v072.xml'))
    except Exception:pass
    raise
finally:
    if prepared:
        adb('shell','am','force-stop',APP)
        restore=OUT/'restore-prefs.xml';restore.write_bytes(original)
        adb('push',str(restore),'/data/local/tmp/watch-v072-prefs.xml')
        adb('shell','run-as',APP,'cp','/data/local/tmp/watch-v072-prefs.xml','shared_prefs/connection.xml')
        assert adb('exec-out','run-as',APP,'cat','shared_prefs/connection.xml')==original
        results['originalPreferencesByteIdentical']=True
        adb('reverse','--remove','tcp:8767')
        adb('shell','rm','-f','/data/local/tmp/watch-v072-prefs.xml','/sdcard/watch-v072.xml')
    (OUT/'verification-result.json').write_text(json.dumps(results,indent=2),encoding='utf8')
    print(json.dumps(results))
