import uvicorn
import os

from dotenv import load_dotenv

from fastapi import FastAPI, Header, Request, HTTPException
from pydantic import BaseModel
from typing import List,Dict,Any

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

app = FastAPI()

# class LineWebhookRequest(BaseModel):
#     destination: str
#     events: List[Dict[str, Any]]

load_dotenv()
    
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

configuration = Configuration(
    access_token=CHANNEL_ACCESS_TOKEN
)   
handler = WebhookHandler(channel_secret=CHANNEL_SECRET)

@app.post("/webhook")
async def get_json(request: Request,x_line_signature: str = Header(None)):
    
    if x_line_signature is None:
        raise HTTPException(status_code=400, detail="Missing X-Line-Signature header")
    
    body = await request.body()
    body_str = body.decode("utf-8")
    
    try:
        handler.handle(body_str, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    api_client = ApiClient(configuration=configuration)
    messaging_api = MessagingApi(api_client)
    
    print(event)
    reply_token = event.reply_token
    user_message = event.message.text
    
    reply_message = f"You said: {user_message}"
    
    messaging_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_message)]
        )
    )

if __name__ == "__main__":
    uvicorn.run(app,port=8000,host="0.0.0.0")