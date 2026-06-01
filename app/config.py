import os
from dotenv import load_dotenv
load_dotenv()
LINE_CHANNEL_SECRET=os.getenv("LINE_CHANNEL_SECRET","")
LINE_CHANNEL_ACCESS_TOKEN=os.getenv("LINE_CHANNEL_ACCESS_TOKEN","")
AI_PROVIDER=os.getenv("AI_PROVIDER","echo")
HTTP_LLM_ENDPOINT=os.getenv("HTTP_LLM_ENDPOINT","")
HTTP_LLM_API_KEY=os.getenv("HTTP_LLM_API_KEY","")
MODEL_NAME=os.getenv("MODEL_NAME","gpt-4o-mini")
