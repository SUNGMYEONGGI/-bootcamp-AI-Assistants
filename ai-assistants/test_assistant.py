#!/usr/bin/env python3
"""
OpenAI Assistant 터미널 테스트 스크립트

슬랙 설정 없이도 OpenAI Assistant API를 테스트할 수 있습니다.
"""

import os
import time
import sys
from openai import OpenAI
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# OpenAI 클라이언트 초기화
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    print("✅ OpenAI 클라이언트 초기화 완료")
except Exception as e:
    print(f"❌ OpenAI 클라이언트 초기화 실패: {e}")
    sys.exit(1)

# Assistant ID
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_dhCyBhWrMBqjd83HnjEbWUY5")

# 현재 Thread
current_thread = None

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

def initialize_assistant():
    """Assistant와 Thread 초기화"""
    global current_thread
    
    try:
        print("🔄 Assistant 정보를 가져오는 중...")
        
        # Assistant 정보 가져오기
        assistant_info = client.beta.assistants.retrieve(assistant_id=ASSISTANT_ID)
        print(f"✅ Assistant '{assistant_info.name}' 연결됨")
        print(f"📝 설명: {assistant_info.description}")
        
        # 새로운 Thread 생성
        current_thread = client.beta.threads.create()
        print(f"🆔 Thread ID: {current_thread.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ 초기화 오류: {str(e)}")
        return False

def get_assistant_response(message):
    """OpenAI Assistant로부터 응답 받기"""
    global current_thread
    
    if not current_thread:
        print("❌ Thread가 초기화되지 않았습니다.")
        return None
    
    try:
        print("\n🤔 Assistant가 생각 중입니다...")
        
        # Thread에 메시지 추가
        client.beta.threads.messages.create(
            thread_id=current_thread.id,
            role="user",
            content=message
        )
        
        # Run 생성 및 실행
        run = client.beta.threads.runs.create(
            thread_id=current_thread.id,
            assistant_id=ASSISTANT_ID
        )
        
        print(f"📋 Run ID: {run.id}")
        
        # Run 완료 대기
        max_attempts = 60  # 60초 타임아웃
        attempts = 0
        
        while run.status in ['queued', 'in_progress', 'cancelling'] and attempts < max_attempts:
            print(f"⏳ 상태: {run.status} ({attempts + 1}/{max_attempts})")
            time.sleep(1)
            attempts += 1
            run = client.beta.threads.runs.retrieve(
                thread_id=current_thread.id,
                run_id=run.id
            )
        
        print(f"🏁 최종 상태: {run.status}")
        
        if run.status == 'completed':
            # 최신 메시지들 가져오기
            messages = client.beta.threads.messages.list(thread_id=current_thread.id)
            
            # Assistant의 응답 찾기 (가장 최근 메시지)
            for msg in messages.data:
                if msg.role == "assistant":
                    clean_response = remove_annotations(msg.content[0])
                    return clean_response
                    
        elif run.status == 'failed':
            error_msg = f"❌ 처리 중 오류가 발생했습니다."
            if run.last_error:
                error_msg += f"\n오류 내용: {run.last_error}"
            return error_msg
            
        elif run.status == 'requires_action':
            return "⚠️ 추가 작업이 필요합니다. (Function calling 등)"
            
        else:
            return f"⚠️ 타임아웃 또는 예상치 못한 상태: {run.status}"
            
    except Exception as e:
        return f"❌ 오류가 발생했습니다: {str(e)}"

    return "❌ 응답을 받지 못했습니다."

def reset_conversation():
    """새로운 대화 시작"""
    global current_thread
    
    try:
        current_thread = client.beta.threads.create()
        print(f"🔄 새로운 대화가 시작되었습니다.")
        print(f"🆔 새 Thread ID: {current_thread.id}")
        return True
    except Exception as e:
        print(f"❌ 새 대화 생성 오류: {str(e)}")
        return False

def show_help():
    """도움말 표시"""
    help_text = """
🤖 OpenAI Assistant 터미널 테스트 도구

사용 가능한 명령어:
• 일반 메시지 입력 - Assistant와 대화
• /help - 이 도움말 보기
• /reset - 대화 기록 초기화
• /status - 현재 상태 확인
• /quit 또는 /exit - 프로그램 종료

팁:
• 여러 줄 입력 시 마지막에 빈 줄을 입력하세요
• Ctrl+C로 언제든 종료할 수 있습니다
"""
    print(help_text)

def show_status():
    """현재 상태 표시"""
    print(f"""
📊 현재 상태:
• OpenAI API 키: {'✅ 설정됨' if os.getenv('OPENAI_API_KEY') else '❌ 설정되지 않음'}
• Assistant ID: {ASSISTANT_ID}
• Thread ID: {current_thread.id if current_thread else '❌ 없음'}
""")

def get_multiline_input(prompt):
    """여러 줄 입력 받기"""
    print(f"{prompt} (여러 줄 입력 시 마지막에 빈 줄 입력):")
    lines = []
    while True:
        try:
            line = input()
            if line == "" and lines:  # 빈 줄이고 이미 입력이 있으면 종료
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines).strip()

def main():
    """메인 함수"""
    print("🚀 OpenAI Assistant 터미널 테스트 시작!")
    print("=" * 50)
    
    # 환경변수 확인
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        print("💡 .env 파일에 OPENAI_API_KEY를 설정해주세요.")
        sys.exit(1)
    
    # Assistant 초기화
    if not initialize_assistant():
        print("❌ Assistant 초기화에 실패했습니다.")
        sys.exit(1)
    
    print("\n✨ 대화를 시작할 수 있습니다!")
    print("💡 '/help'를 입력하면 도움말을 볼 수 있습니다.")
    print("-" * 50)
    
    # 대화 루프
    conversation_count = 0
    
    try:
        while True:
            # 사용자 입력
            try:
                user_input = input(f"\n[{conversation_count + 1}] 💬 당신: ").strip()
            except EOFError:
                print("\n👋 대화를 종료합니다.")
                break
            
            # 빈 입력 무시
            if not user_input:
                continue
            
            # 명령어 처리
            if user_input.lower() in ['/quit', '/exit']:
                print("👋 대화를 종료합니다.")
                break
            elif user_input.lower() == '/help':
                show_help()
                continue
            elif user_input.lower() == '/reset':
                if reset_conversation():
                    conversation_count = 0
                continue
            elif user_input.lower() == '/status':
                show_status()
                continue
            elif user_input.lower() == '/multiline':
                user_input = get_multiline_input("여러 줄 메시지를 입력하세요")
                if not user_input:
                    continue
            
            # Assistant 응답 받기
            response = get_assistant_response(user_input)
            
            if response:
                print(f"\n🤖 Assistant:")
                print("-" * 30)
                print(response)
                print("-" * 30)
                conversation_count += 1
            else:
                print("❌ 응답을 받지 못했습니다.")
                
    except KeyboardInterrupt:
        print("\n\n👋 Ctrl+C로 대화를 종료합니다.")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
    
    print("\n🎉 OpenAI Assistant 테스트가 완료되었습니다!")

if __name__ == "__main__":
    main() 