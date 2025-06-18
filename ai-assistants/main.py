import os
import time
import gradio as gr
from openai import OpenAI

# OpenAI 클라이언트 초기화
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")  # 환경변수에서 API 키 가져오기
)

# Assistant ID (이미 만든 Assistant)
ASSISTANT_ID = "asst_dhCyBhWrMBqjd83HnjEbWUY5"

# 전역 변수로 thread와 assistant 정보 저장
current_thread = None
assistant_info = None

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
    global current_thread, assistant_info
    
    try:
        # Assistant 정보 가져오기
        assistant_info = client.beta.assistants.retrieve(assistant_id=ASSISTANT_ID)
        
        # 새로운 Thread 생성
        current_thread = client.beta.threads.create()
        
        return f"✅ Assistant '{assistant_info.name}' 연결됨\n📝 {assistant_info.description}\n🆔 Thread ID: {current_thread.id}"
    
    except Exception as e:
        return f"❌ 초기화 오류: {str(e)}\nAPI 키가 올바르게 설정되어 있는지 확인해주세요."

def chat_with_assistant(message, history):
    """Assistant와 채팅하는 함수"""
    global current_thread
    
    if not current_thread:
        return history + [("시스템 오류", "❌ Thread가 초기화되지 않았습니다. 페이지를 새로고침해주세요.")]
    
    if not message.strip():
        return history
    
    try:
        # 사용자 메시지를 history에 추가
        history = history + [(message, None)]
        
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
        
        # Run 완료 대기
        while run.status in ['queued', 'in_progress', 'cancelling']:
            time.sleep(1)
            run = client.beta.threads.runs.retrieve(
                thread_id=current_thread.id,
                run_id=run.id
            )
        
        if run.status == 'completed':
            # 최신 메시지들 가져오기
            messages = client.beta.threads.messages.list(
                thread_id=current_thread.id
            )
            
            # Assistant의 응답 찾기 (가장 최근 메시지)
            for msg in messages.data:
                if msg.role == "assistant":
                    # annotations(주석) 제거한 깔끔한 응답 생성
                    clean_response = remove_annotations(msg.content[0])
                    # history 업데이트 (마지막 메시지의 응답 부분)
                    history[-1] = (message, clean_response)
                    break
        
        elif run.status == 'failed':
            error_msg = f"❌ 오류 발생: {run.last_error}"
            history[-1] = (message, error_msg)
        
        elif run.status == 'requires_action':
            action_msg = "⚠️ 추가 작업이 필요합니다. (Function calling 등)"
            history[-1] = (message, action_msg)
        
        else:
            status_msg = f"⚠️ 예상치 못한 상태: {run.status}"
            history[-1] = (message, status_msg)
    
    except Exception as e:
        error_msg = f"❌ 오류가 발생했습니다: {str(e)}"
        if history and history[-1][1] is None:
            history[-1] = (message, error_msg)
        else:
            history = history + [(message, error_msg)]
    
    return history

def clear_chat():
    """새로운 대화 시작"""
    global current_thread
    try:
        current_thread = client.beta.threads.create()
        return [], f"🔄 새로운 대화가 시작되었습니다.\n🆔 Thread ID: {current_thread.id}"
    except Exception as e:
        return [], f"❌ 새 대화 생성 오류: {str(e)}"

# Gradio 인터페이스 생성
def create_gradio_app():
    # 초기화 메시지
    init_message = initialize_assistant()
    
    with gr.Blocks(
        title="🤖 OpenAI Assistant 채팅봇",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {
            max-width: 800px !important;
            margin: 0 auto !important;
        }
        .chat-message {
            padding: 10px;
            margin: 5px 0;
            border-radius: 10px;
        }
        .user-message {
            background-color: #007AFF;
            color: white;
            margin-left: 20%;
        }
        .assistant-message {
            background-color: #E5E5EA;
            color: black;
            margin-right: 20%;
        }
        """
    ) as app:
        
        gr.Markdown(
            """
            # 🤖 OpenAI Assistant 채팅봇
            
            카카오톡 스타일의 채팅 인터페이스로 AI Assistant와 대화해보세요!
            """
        )
        
        # 초기화 상태 표시
        status_box = gr.Textbox(
            value=init_message,
            label="🔧 연결 상태",
            interactive=False,
            lines=3
        )
        
        # 채팅 인터페이스
        chatbot = gr.Chatbot(
            value=[],
            label="💬 채팅",
            height=500,
            show_copy_button=True,
            bubble_full_width=False,
            avatar_images=("👤", "🤖")
        )
        
        with gr.Row():
            msg_input = gr.Textbox(
                placeholder="메시지를 입력하세요...",
                label="",
                scale=4,
                container=False
            )
            send_btn = gr.Button("📤 전송", scale=1, variant="primary")
        
        with gr.Row():
            clear_btn = gr.Button("🔄 새 대화", variant="secondary")
            
        # 이벤트 핸들러
        def submit_message(message, history):
            new_history = chat_with_assistant(message, history)
            return new_history, ""
        
        def handle_clear():
            new_history, status = clear_chat()
            return new_history, status
        
        # 전송 버튼 클릭 시
        send_btn.click(
            fn=submit_message,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, msg_input]
        )
        
        # 엔터 키 입력 시
        msg_input.submit(
            fn=submit_message,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, msg_input]
        )
        
        # 새 대화 버튼 클릭 시
        clear_btn.click(
            fn=handle_clear,
            outputs=[chatbot, status_box]
        )
        
        # 사용법 안내
        gr.Markdown(
            """
            ### 📖 사용법
            - 메시지를 입력하고 전송 버튼을 클릭하거나 Enter 키를 눌러 대화하세요
            - "🔄 새 대화" 버튼으로 대화 내역을 초기화할 수 있습니다
            - 대화 내역은 자동으로 저장되며, Assistant가 컨텍스트를 기억합니다
            
            ### ⚙️ 설정 필요사항
            - 환경변수 `OPENAI_API_KEY`가 설정되어 있어야 합니다
            """
        )
    
    return app

if __name__ == "__main__":
    app = create_gradio_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        debug=True
    )