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

# 사용자별 처리 상태 관리 (중복 요청 방지)
user_processing = {}

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
        # 부트캠프 관련 질문이 아닌 경우 빠른 응답
        if not is_bootcamp_related(message):
            return """안녕하세요! 저는 *AI 부트캠프 전용 FAQ 봇* 입니다. 🤖

현재 질문해주신 내용은 부트캠프와 직접적인 관련이 없는 것 같습니다.

*저에게 물어보실 수 있는 주제들:*
• 출결 관리 (출석, 결석, 지각, 조퇴)
• 데일리 미션 및 과제 제출
• 캡스톤 프로젝트 관련
• 피어세션 운영 방식
• 커리큘럼 및 세션 일정
• 수료 기준 및 평가 방식
• LMS 사용법 및 행정 처리

*부트캠프 관련 질문* 이 있으시면 언제든지 물어보세요! 
그 외의 질문은 운영진에게 직접 문의해주시기 바랍니다. 😊"""
        
        # 사용자별 Thread 가져오기 또는 생성
        thread_id = get_or_create_thread(user_id)
        if not thread_id:
            return "❌ Thread 생성에 실패했습니다."
        
        # System instructions 강화된 메시지 생성
        enhanced_message = f"""[AI 부트캠프 FAQ 봇 - 엄격한 모드]

🎯 **중요:** 반드시 다음 지침을 준수하세요:
1. AI 부트캠프 관련 질문만 답변 (출결, 과제, 캡스톤, 피어세션, 커리큘럼, 수료기준 등)
2. 부트캠프와 무관한 질문은 즉시 "운영진에게 문의해주세요"로 안내
3. 불확실한 정보는 추측하지 말고 운영진 문의 안내
4. 간결하고 정확한 답변 (2문단 이내)

📝 **사용자 질문:** {message}

위 질문이 AI 부트캠프(출결, 데일리미션, 캡스톤, 피어세션, 커리큘럼, 수료기준, 과제제출, LMS, 행정처리)와 관련이 없다면, 바로 "해당 질문은 AI 부트캠프와 관련이 없어 답변드릴 수 없습니다. 운영진에게 문의해주세요."라고 응답하세요."""
        
        # Thread에 강화된 메시지 추가
        openai_client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=enhanced_message
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
                    
                    # 응답 후처리: 부트캠프 무관한 내용이 포함된 경우 필터링
                    processed_response = post_process_response(clean_response, message)
                    return processed_response
                    
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

def is_bootcamp_related(message):
    """부트캠프 관련 질문인지 빠르게 판단하는 함수"""
    bootcamp_keywords = [
        '부트캠프', '출결', '출석', '결석', '지각', '조퇴', '외출',
        '데일리', '미션', '캡스톤', '프로젝트', '피어세션', '피어', 
        '커리큘럼', '세션', '과제', '제출', 'LMS', '수료', '수강',
        '행정', '운영', '마감', '평가', '점수', '감점', '가점',
        '일정', '시간표', '휴강', '보강', '멘토', '튜터', '강의',
        '실습', '과정', '교육', '학습', '진도', '복습', '예습'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in bootcamp_keywords)

def post_process_response(response, original_question):
    """Assistant 응답을 후처리하여 부트캠프 관련성 확인"""
    
    # 이미 운영진 문의 안내가 포함된 경우 그대로 반환
    if "운영진에게 문의" in response or "부트캠프와 관련이 없" in response:
        return response
    
    # 부트캠프 무관한 답변을 나타내는 키워드들
    non_bootcamp_indicators = [
        '일반적으로', '보통', '대부분', '일반적인 경우',
        '프로그래밍 언어', '개발 도구', '기술 스택',
        '날씨', '음식', '여행', '게임', '영화', '음악',
        '건강', '운동', '취미', '스포츠', '뉴스'
    ]
    
    # 부트캠프 관련 키워드가 응답에 포함되어 있는지 확인
    bootcamp_response_keywords = [
        '출결', '데일리', '캡스톤', '피어세션', '수료', '과제',
        'LMS', '부트캠프', '운영진', '멘토', '튜터', '세션'
    ]
    
    response_lower = response.lower()
    
    # 부트캠프 관련 키워드가 전혀 없고, 무관한 키워드가 있다면 필터링
    has_bootcamp_keywords = any(keyword in response_lower for keyword in bootcamp_response_keywords)
    has_non_bootcamp_keywords = any(keyword in response_lower for keyword in non_bootcamp_indicators)
    
    if not has_bootcamp_keywords and has_non_bootcamp_keywords:
        return """죄송합니다. 해당 질문은 *AI 부트캠프와 직접적인 관련이 없는 것*으로 판단됩니다. 🤖

*저에게 문의하실 수 있는 주제:*
• 출결 관리 (출석, 결석, 지각, 조퇴)
• 데일리 미션 및 과제 제출
• 캡스톤 프로젝트 진행 방식
• 피어세션 운영 방법
• 커리큘럼 및 세션 일정
• 수료 기준 및 평가
• LMS 사용법

*부트캠프 외의 질문*은 운영진에게 직접 문의해주시기 바랍니다.
도움이 필요하면 언제든지 물어보세요! 😊"""
    
    # 응답이 너무 길고 부트캠프 관련성이 의심스러운 경우
    if len(response) > 500 and not has_bootcamp_keywords:
        return """답변이 너무 길어 *부트캠프와 관련이 없는 내용*일 가능성이 높습니다. 🤖

정확한 답변을 위해 *운영진에게 직접 문의*해주시거나, 
*부트캠프 관련 구체적인 키워드*를 포함하여 다시 질문해주세요.

*예시:* "출결 규정", "데일리 미션 제출", "캡스톤 프로젝트 일정" 등

도움이 필요하면 언제든지 물어보세요! 😊"""
    
    # 정상적인 부트캠프 관련 응답으로 판단되면 그대로 반환
    return response

def get_assistant_response_sync(message, user_id):
    """OpenAI Assistant로부터 응답 받기 (동기 버전)"""
    try:
        # 부트캠프 관련 질문이 아닌 경우 빠른 응답
        if not is_bootcamp_related(message):
            return """안녕하세요! 저는 AI 부트캠프 전용 FAQ 봇입니다. 🤖

현재 질문해주신 내용은 부트캠프와 직접적인 관련이 없는 것 같습니다.

*저에게 물어보실 수 있는 주제들:*
• 출결 관리 (출석, 결석, 지각, 조퇴)
• 데일리 미션 및 과제 제출
• 캡스톤 프로젝트 관련
• 피어세션 운영 방식
• 커리큘럼 및 세션 일정
• 수료 기준 및 평가 방식
• LMS 사용법 및 행정 처리

부트캠프 관련 질문이 있으시면 언제든지 물어보세요! 
그 외의 질문은 운영진에게 직접 문의해주시기 바랍니다. 😊"""
        
        # 사용자별 Thread 가져오기 또는 생성
        thread_id = get_or_create_thread(user_id)
        if not thread_id:
            return "❌ Thread 생성에 실패했습니다."
        
        # 기존 활성 Run이 있는지 확인하고 대기
        try:
            existing_runs = openai_client.beta.threads.runs.list(thread_id=thread_id, limit=1)
            if existing_runs.data and existing_runs.data[0].status in ['queued', 'in_progress', 'cancelling']:
                logger.info(f"기존 활성 Run 대기 중: {existing_runs.data[0].id}")
                # 기존 Run이 완료될 때까지 대기
                for _ in range(30):  # 30초 대기
                    time.sleep(1)
                    existing_run = openai_client.beta.threads.runs.retrieve(
                        thread_id=thread_id,
                        run_id=existing_runs.data[0].id
                    )
                    if existing_run.status not in ['queued', 'in_progress', 'cancelling']:
                        break
        except Exception as wait_error:
            logger.warning(f"기존 Run 확인 중 오류: {wait_error}")
        
        # System instructions 강화된 메시지 생성
        enhanced_message = f"""[AI 부트캠프 FAQ 봇 - 엄격한 모드]

🎯 **중요:** 반드시 다음 지침을 준수하세요:
1. AI 부트캠프 관련 질문만 답변 (출결, 과제, 캡스톤, 피어세션, 커리큘럼, 수료기준 등)
2. 부트캠프와 무관한 질문은 즉시 "운영진에게 문의해주세요"로 안내
3. 불확실한 정보는 추측하지 말고 운영진 문의 안내
4. 간결하고 정확한 답변 (2문단 이내)

📝 **사용자 질문:** {message}

위 질문이 AI 부트캠프(출결, 데일리미션, 캡스톤, 피어세션, 커리큘럼, 수료기준, 과제제출, LMS, 행정처리)와 관련이 없다면, 바로 "해당 질문은 AI 부트캠프와 관련이 없어 답변드릴 수 없습니다. 운영진에게 문의해주세요."라고 응답하세요."""
        
        # Thread에 강화된 메시지 추가
        openai_client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=enhanced_message
        )
        
        # Run 생성 및 실행 (재시도 로직 추가)
        max_run_attempts = 3
        run = None
        
        for attempt in range(max_run_attempts):
            try:
                run = openai_client.beta.threads.runs.create(
                    thread_id=thread_id,
                    assistant_id=ASSISTANT_ID
                )
                break
            except Exception as run_error:
                if "already has an active run" in str(run_error) and attempt < max_run_attempts - 1:
                    logger.warning(f"Active run 충돌, 재시도 {attempt + 1}/{max_run_attempts}")
                    time.sleep(2)  # 2초 대기 후 재시도
                    continue
                else:
                    raise run_error
        
        if not run:
            return "❌ Run 생성에 실패했습니다."
        
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
                    
                    # 응답 후처리: 부트캠프 무관한 내용이 포함된 경우 필터링
                    processed_response = post_process_response(clean_response, message)
                    return processed_response
                    
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
def handle_mention(event, say, logger):
    """봇이 멘션되었을 때 처리"""
    try:
        user_id = event["user"]
        channel = event["channel"]
        text = event["text"]
        thread_ts = event["ts"]  # 원본 메시지의 타임스탬프 (스레드 생성용)
        
        # 봇 자신이 보낸 메시지는 무시
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return
        
        # 현재 봇이 멘션되었는지 확인
        import re
        bot_user_pattern = r'<@[A-Z0-9]+>'
        mentioned_users = re.findall(bot_user_pattern, text)
        
        # 봇의 실제 사용자 ID 가져오기
        try:
            bot_info = app.client.auth_test()
            bot_user_id = bot_info["user_id"]
            
            # 현재 봇이 멘션되었는지 확인
            is_bot_mentioned = any(f"<@{bot_user_id}>" in mention for mention in mentioned_users)
            if not is_bot_mentioned:
                return
                
        except Exception as auth_error:
            logger.warning(f"봇 인증 확인 오류: {auth_error}")
            # 인증 확인 실패 시 기본 로직 수행
        
        # 봇 멘션 제거하고 실제 메시지만 추출
        clean_text = re.sub(bot_user_pattern, '', text).strip()
        
        logger.info(f"멘션 처리 시작 - 사용자: {user_id}, 메시지: {clean_text}")
        
        # 이미 처리 중인 요청이 있는지 확인
        if user_id in user_processing and user_processing[user_id]:
            say(
                text="⚠️ 이전 질문을 처리하고 있습니다. 잠시만 기다려주세요.",
                thread_ts=thread_ts
            )
            return
        
        if not clean_text:
            say(
                text="안녕하세요! 🤖 무엇을 도와드릴까요?",
                thread_ts=thread_ts
            )
            return
        
        # 처리 상태 설정
        user_processing[user_id] = True
        
        try:
            # 스레드에 로딩 메시지 먼저 보내기
            loading_msg = say(
                text="🤔 AI가 답변을 생성하고 있습니다...",
                thread_ts=thread_ts
            )
            
            # Assistant로부터 응답 받기 (동기 버전 사용)
            response = get_assistant_response_sync(clean_text, user_id)
            
            # 로딩 메시지를 최종 답변으로 업데이트 (mrkdwn 형식 사용)
            app.client.chat_update(
                channel=channel,
                ts=loading_msg["ts"],
                text=f"🤖 {response}",
                mrkdwn=True
            )
            
        finally:
            # 처리 완료 후 상태 해제
            user_processing[user_id] = False
        
    except Exception as e:
        logger.error(f"멘션 처리 오류: {str(e)}")
        # 처리 상태 해제
        if user_id in user_processing:
            user_processing[user_id] = False
        
        say(
            text=f"❌ 오류가 발생했습니다: {str(e)}",
            thread_ts=event.get("ts")
        )

@app.event("message")
def handle_direct_message(event, say, logger):
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
            say("안녕하세요! 🤖 무엇을 도와드릴까요?")
            return
        
        # 로딩 메시지
        loading_msg = say("🤔 생각 중입니다...")
        
        # Assistant로부터 응답 받기 (동기 버전 사용)
        response = get_assistant_response_sync(text, user_id)
        
        # 메시지 업데이트 (mrkdwn 형식 사용)
        app.client.chat_update(
            channel=event["channel"],
            ts=loading_msg["ts"],
            text=f"💬 *질문:* {text}\n\n🤖 *답변:*\n{response}",
            mrkdwn=True
        )
        
    except Exception as e:
        logger.error(f"DM 처리 오류: {str(e)}")
        say(f"❌ 오류가 발생했습니다: {str(e)}")

@app.command("/reset_chat")
def handle_reset_command(ack, respond, command):
    """채팅 히스토리 리셋 명령어"""
    ack()
    
    try:
        user_id = command["user_id"]
        
        # 해당 사용자의 Thread 삭제
        if user_id in user_threads:
            del user_threads[user_id]
            respond("🔄 채팅 히스토리가 리셋되었습니다!")
            logger.info(f"Thread 리셋됨 - User: {user_id}")
        else:
            respond("ℹ️ 리셋할 채팅 히스토리가 없습니다.")
            
    except Exception as e:
        logger.error(f"리셋 명령어 오류: {str(e)}")
        respond(f"❌ 리셋 중 오류가 발생했습니다: {str(e)}")

@app.command("/help")
def handle_help_command(ack, respond):
    """도움말 명령어"""
    ack()
    
    help_text = """
🤖 *AI 부트캠프 FAQ 봇 사용법*

*📚 전용 질문 주제:*
• 출결 관리 (출석, 결석, 지각, 조퇴)
• 데일리 미션 및 과제 제출 
• 캡스톤 프로젝트 진행 방식
• 피어세션 운영 방법
• 커리큘럼 및 세션 일정
• 수료 기준 및 평가 방식
• LMS 사용법 및 행정 처리

*💬 사용 방법:*
*1. 봇 멘션하기 (권장):*
   `@부트캠프_FAQ_봇 출결 규정이 어떻게 되나요?` 
   💡 답변은 자동으로 스레드에 표시됩니다!

*2. 직접 메시지:*
   봇에게 DM으로 직접 메시지 전송

*3. 명령어:*
   • `/reset_chat` - 채팅 히스토리 리셋
   • `/help` - 이 도움말 보기

*⚠️ 중요 안내:*
• *부트캠프 관련 질문만* 답변 가능합니다
• 그 외 질문은 *운영진에게 직접 문의*해주세요
• 불확실한 정보는 추측하지 않고 운영진 문의를 안내합니다

*부트캠프 관련 질문*이 있으시면 언제든 멘션해주세요! 😊
    """
    
    respond(help_text)

# 앱 시작 이벤트
@app.event("app_home_opened")
def update_home_tab(client, event, logger):
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
🤖 *AI 부트캠프 FAQ 봇에 오신 것을 환영합니다!*

이 봇은 *AI 부트캠프 전용 FAQ 봇*입니다.

*📚 답변 가능한 주제:*
• 출결 관리 (출석, 결석, 지각, 조퇴)
• 데일리 미션 및 과제 제출
• 캡스톤 프로젝트 관련
• 피어세션 운영 방식  
• 커리큘럼 및 세션 일정
• 수료 기준 및 평가 방식
• LMS 사용법 및 행정 처리

*💬 사용 방법:*
• 채널에서 `@부트캠프_FAQ_봇` 멘션 후 질문 (스레드로 답변)
• 이 봇에게 직접 메시지 전송
• `/help` 명령어로 자세한 도움말 확인

*⚠️ 중요 안내:*
• *부트캠프 관련 질문만* 답변 가능
• 그 외 질문은 *운영진에게 직접 문의*
• 불확실한 정보는 운영진 문의 안내

*부트캠프 관련 질문*이 있으면 언제든 물어보세요! 😊
                            """
                        }
                    }
                ]
            }
        )
    except Exception as e:
        logger.error(f"홈 탭 업데이트 오류: {str(e)}")

if __name__ == "__main__":
    print("🚀 AI Assistant 슬랙 봇을 시작합니다...")
    print("=" * 50)
    
    # 환경변수 확인
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "OPENAI_API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.startswith("your_") or value.startswith("xoxb-your-") or value.startswith("xapp-your-"):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ 환경변수 설정 오류!")
        print("다음 환경변수들이 올바르게 설정되지 않았습니다:")
        for var in missing_vars:
            current_value = os.getenv(var, "설정되지 않음")
            print(f"  • {var}: {current_value}")
        
        print("\n💡 해결 방법:")
        print("1. .env 파일을 편집하세요:")
        print("   nano .env")
        print("\n2. 다음 값들을 실제 값으로 변경하세요:")
        print("   • OPENAI_API_KEY: OpenAI API 키")
        print("   • SLACK_BOT_TOKEN: xoxb-로 시작하는 슬랙 봇 토큰")
        print("   • SLACK_APP_TOKEN: xapp-로 시작하는 슬랙 앱 토큰")
        print("\n📖 자세한 설정 방법은 README.md 파일을 참고하세요.")
        exit(1)
    
    print("✅ 환경변수 확인 완료")
    
    try:
        # OpenAI API 키 테스트
        assistant_info = openai_client.beta.assistants.retrieve(assistant_id=ASSISTANT_ID)
        print(f"✅ OpenAI Assistant 연결 확인: {assistant_info.name}")
    except Exception as e:
        print(f"❌ OpenAI Assistant 연결 실패: {str(e)}")
        print("💡 OPENAI_API_KEY와 ASSISTANT_ID를 확인해주세요.")
        exit(1)
    
    logger.info("🚀 AI Assistant 슬랙 봇을 시작합니다...")
    
    try:
        # Socket Mode로 앱 실행
        handler = SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
        handler.start()
    except Exception as e:
        print(f"❌ 슬랙 봇 시작 실패: {str(e)}")
        print("💡 슬랙 토큰들이 올바른지 확인해주세요.")
        exit(1) 