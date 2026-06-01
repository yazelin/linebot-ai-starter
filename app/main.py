from fastapi import FastAPI, Request, Header, HTTPException
from .line import verify_signature, handle_events
app=FastAPI(title="LINE Bot AI Starter")
@app.get("/health")
def health(): return {"ok":True}
@app.post("/webhook/line")
async def webhook(request:Request, x_line_signature:str=Header(default="")):
    body=await request.body()
    if not verify_signature(body,x_line_signature): raise HTTPException(403,"Invalid LINE signature")
    await handle_events(await request.json()); return {"ok":True}
