import asyncio, httpx
from . import config
async def ask_ai(text):
    if config.AI_PROVIDER=="echo": return "LINE AI echo: "+text
    if config.AI_PROVIDER=="claude-cli": return await run_cli(["claude","-p",text])
    if config.AI_PROVIDER=="gemini-cli": return await run_cli(["gemini","-p",text])
    payload={"model":config.MODEL_NAME,"messages":[{"role":"user","content":text}]}
    headers={"Authorization":"Bearer "+config.HTTP_LLM_API_KEY} if config.HTTP_LLM_API_KEY else {}
    async with httpx.AsyncClient(timeout=60) as c:
        r=await c.post(config.HTTP_LLM_ENDPOINT,json=payload,headers=headers); r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]
async def run_cli(cmd):
    p=await asyncio.create_subprocess_exec(*cmd,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE); out,err=await p.communicate(); return out.decode().strip() if p.returncode==0 else err.decode(errors="replace")[-1000:]
