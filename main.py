import uvicorn
import os
import io
import requests

from google import genai
from google.genai import types
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
USER_ID = os.getenv("USER_ID")

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
    
    if event.type == 'message':
        api_client = ApiClient(configuration=configuration)
        messaging_api = MessagingApi(api_client)
        
        reply_token = event.reply_token
        user_message = event.message.text
        mention_id = event.source.user_id
        
        if event.source.type == 'group' and mention_id == USER_ID:
            is_group = True
        else: is_group = False
        
        if is_group:
            imin = event.message.mention.mentioness[0].index
            imax = event.message.mention.mentioness[0].length
        
            user_message = user_message.substring(0,imin) + user_message.substring(imax+imin)
        
        quoted_message_id = event.message.quoted_message_id
        
        # print(event)
        
        if event.source.type == 'user' or is_group:
            reply_message = get_genai_response(user_message, file_id=quoted_message_id)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply_message)]
                )
            )
        
def get_genai_response(user_msg: str, file_id: str = None) -> str:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    prompt = f'''Ask: {user_msg}
            Task restrictions:
            - ห้ามใช้เครื่องหมาย ``` (Markdown Code Block) หรือ ** (ตัวหนา) ในการตอบเด็ดขาด
            - ให้ตอบกลับมาเป็นข้อความตัวอักษรธรรมดา (Plain Text) เท่านั้น
            - เอาเฉพาะส่วนเนื้อหาที่เป็นคำตอบโดยตรง ไม่ต้องมีคำเกริ่นนำหรือคำลงท้าย
            - เว้นบรรทัดประโยคต่อประโยค'''
    client = genai.Client(api_key=gemini_api_key)
    
    contents_payload = [prompt]
    
    if file_id:
        url = f'https://api-data.line.me/v2/bot/message/{file_id}/content'
        headers = {
            'Authorization': f'Bearer {CHANNEL_ACCESS_TOKEN}'
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                file_content = response.content
                file_stream = io.BytesIO(file_content)
                
                # LINE จะส่งค่าเช่น 'image/jpeg' หรือ 'application/pdf' มาให้ใน headers เสมอ
                content_type_from_line = response.headers.get('Content-Type')
                
                # อัปโหลดขึ้น Gemini File API
                uploaded_file = client.files.upload(
                    file=file_stream, 
                    config=types.UploadFileConfig(
                        mime_type=content_type_from_line
                    )
                )
                
                contents_payload.append(uploaded_file)
            else:
                print(f"ดาวน์โหลดไฟล์จาก LINE ล้มเหลว Status: {response.status_code}")
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการจัดการไฟล์: {e}")

    # ส่งให้ Gemini ประมวลผล
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents_payload
        )
        if response.text:
            return response.text.strip()
        else:
            return "ขออภัย ฉันไม่สามารถประมวลผลคำขอของคุณได้ในขณะนี้"
    except Exception as e:
        print(f"เกิดข้อผิดพลาดจาก Gemini API: {e}")
        return "เกิดข้อผิดพลาดในการเชื่อมต่อกับระบบ AI"
    
    

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app,port=port,host="0.0.0.0")