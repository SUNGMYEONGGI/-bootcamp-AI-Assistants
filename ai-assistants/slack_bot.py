import os
import time
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI 클라이언트 초기화
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Assistant ID
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_dhCyBhWrMBqjd83HnjEbWUY5")

# Slack 앱 초기화
app = App(token=os.getenv("SLACK_BOT_TOKEN"))

# 각 사용자별 Thread 관리를 위한 딕셔너리
user_threads = {}

def remove_annotations(message_content):
    """OpenAI 메시지에서 annotations(주석)을 제거하는 함수"""
    if not message_content or not hasattr(message_content, 'text'):
        return ""
    
    text_content = message_content.text
    if not hasattr(text_content, 'value') or not hasattr(text_content, 'annotations'):
        return text_content.value if hasattr(text_content, 'value') else str(text_content)
    
    # 원본 텍스트
    full_text = text_content.value
    
    # annotations가 없으면 원본 반환
    if not text_content.annotations:
        return full_text
    
    # annotations를 뒤에서부터 제거 (인덱스 변화 방지)
    annotations_sorted = sorted(text_content.annotations, 
                               key=lambda x: x.start_index, reverse=True)
    
    clean_text = full_text
    for annotation in annotations_sorted:
        start = annotation.start_index
        end = annotation.end_index
        # annotation 부분을 제거
        clean_text = clean_text[:start] + clean_text[end:]
    
    return clean_text.strip()

def get_or_create_thread(user_id):
    """사용자별 Thread 생성 또는 가져오기"""
    if user_id not in user_threads:
        try:
            thread = openai_client.beta.threads.create()
            user_threads[user_id] = thread.id
            logger.info(f"새 Thread 생성됨 - User: {user_id}, Thread: {thread.id}")
        except Exception as e:
            logger.error(f"Thread 생성 오류: {str(e)}")
            return None
    
    return user_threads[user_id]

async def get_assistant_response(message, user_id):
    """OpenAI Assistant로부터 응답 받기"""
    try:
        # 사용자별 Thread 가져오기 또는 생성
        thread_id = get_or_create_thread(user_id)
        if not thread_id:
            return "❌ Thread 생성에 실패했습니다."
        
        # Thread에 메시지 추가
        openai_client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message
        )
        
        # Run 생성 및 실행
        run = openai_client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID
        )
        
        # Run 완료 대기
        max_attempts = 30  # 30초 타임아웃
        attempts = 0
        
        while run.status in ['queued', 'in_progress', 'cancelling'] and attempts < max_attempts:
            time.sleep(1)
            attempts += 1
            run = openai_client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
        
        if run.status == 'completed':
            # 최신 메시지들 가져오기
            messages = openai_client.beta.threads.messages.list(thread_id=thread_id)
            
            # Assistant의 응답 찾기 (가장 최근 메시지)
            for msg in messages.data:
                if msg.role == "assistant":
                    clean_response = remove_annotations(msg.content[0])
                    return clean_response
                    
        elif run.status == 'failed':
            return f"❌ 처리 중 오류가 발생했습니다: {run.last_error}"
        elif run.status == 'requires_action':
            return "⚠️ 추가 작업이 필요합니다."
        else:
            return f"⚠️ 타임아웃 또는 예상치 못한 상태: {run.status}"
            
    except Exception as e:
        logger.error(f"Assistant 응답 오류: {str(e)}")
        return f"❌ 오류가 발생했습니다: {str(e)}"

    return "❌ 응답을 받지 못했습니다."

@app.event("app_mention")
async def handle_mention(event, say, logger):
    """봇이 멘션되었을 때 처리"""
    try:
        user_id = event["user"]
        channel = event["channel"]
        text = event["text"]
        
        # 봇 멘션 제거하고 실제 메시지만 추출
        # <@U123456789> 형태의 멘션을 제거
        import re
        clean_text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
        
        if not clean_text:
            await say("안녕하세요! 🤖 무엇을 도와드릴까요?")
            return
        
        # 로딩 메시지 먼저 보내기
        loading_msg = await say("🤔 생각 중입니다...")
        
        # Assistant로부터 응답 받기
        response = await get_assistant_response(clean_text, user_id)
        
        # 로딩 메시지 업데이트
        app.client.chat_update(
            channel=channel,
            ts=loading_msg["ts"],
            text=f"💬 **질문:** {clean_text}\n\n🤖 **답변:**\n{response}"
        )
        
    except Exception as e:
        logger.error(f"멘션 처리 오류: {str(e)}")
        await say(f"❌ 오류가 발생했습니다: {str(e)}")

@app.event("message")
async def handle_direct_message(event, say, logger):
    """DM으로 메시지가 왔을 때 처리"""
    # 봇이 보낸 메시지나 멘션 이벤트는 제외
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return
        
    # DM 채널 확인 (채널 타입이 'im'인 경우)
    channel_type = event.get("channel_type")
    if channel_type != "im":
        return
    
    try:
        user_id = event["user"]
        text = event["text"]
        
        if not text.strip():
            await say("안녕하세요! 🤖 무엇을 도와드릴까요?")
            return
        
        # 로딩 메시지
        loading_msg = await say("🤔 생각 중입니다...")
        
        # Assistant로부터 응답 받기
        response = await get_assistant_response(text, user_id)
        
        # 메시지 업데이트
        app.client.chat_update(
            channel=event["channel"],
            ts=loading_msg["ts"],
            text=f"💬 **질문:** {text}\n\n🤖 **답변:**\n{response}"
        )
        
    except Exception as e:
        logger.error(f"DM 처리 오류: {str(e)}")
        await say(f"❌ 오류가 발생했습니다: {str(e)}")

@app.command("/reset_chat")
async def handle_reset_command(ack, respond, command):
    """채팅 히스토리 리셋 명령어"""
    await ack()
    
    try:
        user_id = command["user_id"]
        
        # 해당 사용자의 Thread 삭제
        if user_id in user_threads:
            del user_threads[user_id]
            await respond("🔄 채팅 히스토리가 리셋되었습니다!")
            logger.info(f"Thread 리셋됨 - User: {user_id}")
        else:
            await respond("ℹ️ 리셋할 채팅 히스토리가 없습니다.")
            
    except Exception as e:
        logger.error(f"리셋 명령어 오류: {str(e)}")
        await respond(f"❌ 리셋 중 오류가 발생했습니다: {str(e)}")

@app.command("/help")
async def handle_help_command(ack, respond):
    """도움말 명령어"""
    await ack()
    
    help_text = """
🤖 **AI Assistant 봇 사용법**

**1. 봇 멘션하기:**
   `@assistant_bot 질문 내용` - 채널에서 봇을 멘션하여 질문

**2. 직접 메시지:**
   봇에게 DM으로 직접 메시지 전송

**3. 명령어:**
   • `/reset_chat` - 채팅 히스토리 리셋
   • `/help` - 이 도움말 보기

**특징:**
✅ 각 사용자별로 독립적인 대화 기록 관리
✅ OpenAI Assistant API 기반 지능형 응답
✅ 실시간 응답 처리

문의사항이 있으시면 언제든 멘션해주세요! 🚀
    """
    
    await respond(help_text)

# 앱 시작 이벤트
@app.event("app_home_opened")
async def update_home_tab(client, event, logger):
    """앱 홈 탭이 열렸을 때"""
    try:
        client.views_publish(
            user_id=event["user"],
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": """
🤖 *AI Assistant 봇에 오신 것을 환영합니다!*

이 봇은 OpenAI Assistant API를 기반으로 동작합니다.

*사용 방법:*
• 채널에서 `@assistant_bot` 멘션 후 질문
• 이 봇에게 직접 메시지 전송
• `/help` 명령어로 자세한 도움말 확인

*주요 기능:*
✅ 지능형 질문 답변
✅ 개인별 대화 기록 관리
✅ 실시간 응답

궁금한 것이 있으면 언제든 물어보세요! 🚀
                            """
                        }
                    }
                ]
            }
        )
    except Exception as e:
        logger.error(f"홈 탭 업데이트 오류: {str(e)}")

if __name__ == "__main__":
    # 환경변수 확인
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"다음 환경변수가 설정되지 않았습니다: {missing_vars}")
        exit(1)
    
    logger.info("🚀 AI Assistant 슬랙 봇을 시작합니다...")
    
    # Socket Mode로 앱 실행
    handler = SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
    handler.start() 