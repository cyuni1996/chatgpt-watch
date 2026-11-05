"""Build a self-contained offline showcase; only use reviewed fictional-data media."""
import argparse
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEMPLATE = '''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WatchChat · 实机演示与 AI 安装 / Demo and AI setup</title>
<style>*{box-sizing:border-box}body{margin:0;background:#0e0b18;color:#f3edff;font:16px/1.75 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1120px;margin:auto;padding:44px 28px 60px}.eyebrow{color:#c9abea;letter-spacing:3px;font-size:13px}h1{font-size:clamp(28px,4.8vw,48px);line-height:1.25;margin:14px 0}h2{font-size:23px;margin:0 0 14px}p{color:#c8bbd8}.lead{font-size:18px;max-width:850px}video{width:100%;border-radius:22px;background:#08060e;box-shadow:0 24px 65px #0005;margin:20px 0 10px}.chapters{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 32px}button,.link{font:inherit;border:0;border-radius:12px;padding:10px 15px;background:#322443;color:#f3eaff;cursor:pointer;text-decoration:none;display:inline-block}button:hover,.link:hover{background:#503865}button:focus-visible,a:focus-visible,textarea:focus-visible{outline:3px solid #dcc2ff;outline-offset:4px}.panel{background:#1b1527;border:1px solid #3c2d50;border-radius:22px;padding:26px;margin:22px 0}.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.steps b{display:block;color:#e3c9ff;font-size:19px}.steps p{font-size:14px;margin-bottom:0}.switch{display:flex;gap:8px;margin-bottom:14px}.active,.primary{background:#d5bef7;color:#21172f}.primary:hover{background:#e5d4fc}textarea{width:100%;height:220px;resize:vertical;background:#0e0b18;color:#f3edff;border:1px solid #4d3a64;border-radius:14px;padding:18px;font:15px/1.7 system-ui,"Microsoft YaHei",sans-serif}.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:14px}.muted,footer{color:#a99ab9;font-size:13px}footer{margin-top:32px}code{background:#30223e;padding:2px 6px;border-radius:5px}a{color:#dcc0ff}@media(max-width:700px){main{padding:28px 18px}.steps{grid-template-columns:1fr}.panel{padding:20px}textarea{height:300px}}</style>
<main><div class="eyebrow">CHATGPT-WATCH · WEAR OS × CODEX</div><h1>把电脑里的对话，戴在手腕上。</h1><p class="lead">Continue your desktop conversations on your wrist. 真实手表录屏，展示聊天、历史、模型、停止回复、操作选择与额度入口。</p>
<video id="demo" controls playsinline preload="metadata" poster="data:image/jpeg;base64,__POSTER__"><source src="data:video/mp4;base64,__VIDEO__" type="video/mp4">此浏览器不支持视频播放 / Video playback is not supported.</video>
<p class="muted">53 秒 · 1280 × 720 · 无音轨，配有中英字幕。画面中的聊天、模型和额度均为虚构演示；没有执行真实电脑任务。</p>
<div class="chapters"><button data-time="0">聊天 / Chat</button><button data-time="5">历史与返回 / History</button><button data-time="11.4">模型 / Models</button><button data-time="20.9">详情 / Details</button><button data-time="23.3">设置 / Settings</button><button data-time="29.5">停止 / Stop</button><button data-time="39.1">确认 / Requests</button><button data-time="49.1">额度 / Usage</button></div>
<section class="panel"><h2>告诉 AI，帮你完成安装。</h2><p>Send the request below to a terminal-capable assistant on your Windows computer. 推荐使用目标电脑上的 Codex；纯网页聊天不能代替本机操作。</p><div class="switch"><button id="zh" class="active">中文提示</button><button id="en">English request</button></div><textarea id="prompt" aria-label="可复制的安装请求 / Copyable installation request" readonly></textarea><div class="controls"><button id="copy" class="primary">复制安装请求 / Copy request</button><span id="status" role="status" class="muted"></span></div></section>
<div class="steps"><section class="panel"><b>01 · 检查与下载</b><p>AI 检查电脑依赖，下载签名 APK 并验证 SHA-256。不必先安装完整 Android 构建环境。</p></section><section class="panel"><b>02 · 安装与配对</b><p>你解锁手表、开启无线调试、核对两端的码；AI 完成安装并启动连接服务。</p></section><section class="panel"><b>03 · 只读验收</b><p>读取历史，确认两端能继续同一聊天。没有授权时不发送测试消息或批准真实操作。</p></section></div>
<section class="panel"><h2>项目与说明 / Project links</h2><div class="controls"><a class="link" href="https://github.com/cyuni1996/chatgpt-watch">GitHub 项目</a><a class="link" href="https://github.com/cyuni1996/chatgpt-watch/blob/main/AI_INSTALL.md">中文 AI 指南</a><a class="link" href="https://github.com/cyuni1996/chatgpt-watch/blob/main/AI_INSTALL.en.md">English runbook</a><a class="link" href="https://github.com/cyuni1996/chatgpt-watch/releases/tag/v0.13.0">APK 与校验和</a></div><p class="muted">电脑、Codex 与连接服务需保持运行；锁屏可用，休眠／关机不可用。日常聊天不需要无线调试。此项目为社区项目，与 OpenAI 和手表厂商无官方隶属关系。</p></section>
<footer>自包含离线演示：视频和封面已内嵌，用 Edge／Chrome 直接打开即可播放；项目链接需联网。代码 MIT，角色素材许可另见仓库说明。</footer></main>
<script>
const prompts={zh:'请帮我安装 https://github.com/cyuni1996/chatgpt-watch 。\\n先阅读仓库 AI_INSTALL.md，并按其中流程操作。优先使用 Release 签名 APK，下载后校验 SHA-256，避免安装不需要的 Android 构建环境。\\n检查电脑依赖，连接我的手表、安装应用、启动服务并指导局域网配对。保留已有应用、配对和草稿，不要因签名冲突卸载或清数据，不关闭防火墙。\\n用读取历史验证连接，不发送测试聊天、不批准真实操作。必须由我解锁、开启无线调试、输入配对码或核对连接码时，再简短提示我。完成后告知下次如何启动及实际验证结果。',en:'Please install https://github.com/cyuni1996/chatgpt-watch for me.\\nRead AI_INSTALL.en.md first. Prefer the signed Release APK, verify SHA-256, and avoid an unnecessary Android build toolchain.\\nCheck dependencies, connect my watch, install the app, start the companion and guide LAN pairing. Preserve existing apps, pairing and drafts. Do not uninstall, clear data or disable the firewall.\\nVerify by reading history; do not send test chats or approve live tasks. Explain when I must unlock the watch, enable wireless debugging or compare pairing codes. Finish with next-time startup instructions and actual verification results.'};
const area=document.getElementById('prompt'),status=document.getElementById('status');function lang(key){area.value=prompts[key];document.getElementById('zh').className=key==='zh'?'active':'';document.getElementById('en').className=key==='en'?'active':'';status.textContent=''}lang('zh');document.getElementById('zh').onclick=()=>lang('zh');document.getElementById('en').onclick=()=>lang('en');document.getElementById('copy').onclick=async()=>{try{if(navigator.clipboard)await navigator.clipboard.writeText(area.value);else{area.focus();area.select();if(!document.execCommand('copy'))throw Error('manual')}status.textContent='已复制 / Copied'}catch{area.focus();area.select();status.textContent='已选中，请按 Ctrl+C / Selected; press Ctrl+C'}};for(const button of document.querySelectorAll('[data-time]'))button.onclick=()=>{const v=document.getElementById('demo');v.currentTime=Number(button.dataset.time);v.play().catch(()=>{})};
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', required=True, type=Path)
    parser.add_argument('--poster', required=True, type=Path)
    args = parser.parse_args()
    html = TEMPLATE.replace('__VIDEO__', base64.b64encode(args.video.read_bytes()).decode('ascii')).replace('__POSTER__', base64.b64encode(args.poster.read_bytes()).decode('ascii'))
    (ROOT / 'docs/demo.html').write_text(html, encoding='utf8')
    print('Created docs/demo.html with embedded video and copyable bilingual setup request')


if __name__ == '__main__':
    main()
