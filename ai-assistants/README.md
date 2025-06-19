# 🤖 OpenAI Assistant 슬랙 봇

OpenAI AI Assistants API를 사용하여 슬랙에서 동작하는 지능형 챗봇입니다.

## 🚀 주요 기능

- **OpenAI Assistant API** 기반 지능형 응답
- **사용자별 독립적인 대화 기록** 관리 (각 사용자마다 별도의 Thread)
- **멘션 기반 질문-답변** (@봇이름 질문내용)
- **DM 직접 메시지** 지원
- **슬래시 명령어** 지원 (/help, /reset_chat)
- **실시간 응답 처리** (로딩 메시지 표시)

## 📋 설치 및 설정

### 1. 가상환경 설정 및 패키지 설치

```bash
# 가상환경 활성화 (이미 생성된 경우)
source ../assistant-venv/bin/activate

# 패키지 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
# .env 파일 생성 (이미 생성된 경우 건너뛰기)
cp env_example.txt .env

# .env 파일 편집
nano .env
```

`.env` 파일에서 다음 값들을 실제 값으로 변경하세요:

```bash
# OpenAI API 설정
OPENAI_API_KEY=sk-your-actual-openai-api-key
ASSISTANT_ID=asst_your_assistant_id

# Slack Bot 설정  
SLACK_BOT_TOKEN=xoxb-your-actual-bot-token
SLACK_APP_TOKEN=xapp-your-actual-app-token
```

## 🔧 슬랙 앱 설정 상세 가이드

### 1. 슬랙 앱 생성

1. [Slack API 웹사이트](https://api.slack.com/apps)에 접속
2. **"Create New App"** 클릭
3. **"From scratch"** 선택
4. 앱 이름 입력 (예: "AI Assistant Bot")
5. 워크스페이스 선택 후 **"Create App"** 클릭

### 2. 봇 사용자 생성 및 권한 설정

1. 왼쪽 메뉴에서 **"OAuth & Permissions"** 클릭
2. **"Scopes"** 섹션의 **"Bot Token Scopes"**에 다음 권한 추가:

   **필수 권한:**
   - `app_mentions:read` - 앱 멘션 읽기
   - `chat:write` - 메시지 전송
   - `chat:write.public` - 공개 채널에 메시지 전송
   - `im:read` - DM 읽기
   - `im:write` - DM 쓰기
   - `im:history` - DM 기록 읽기
   - `users:read` - 사용자 정보 읽기
   - `commands` - 슬래시 명령어 사용

   **선택 권한 (채널에서 사용할 경우):**
   - `channels:history` - 채널 기록 읽기
   - `groups:history` - 그룹 기록 읽기

3. **"Install to Workspace"** 클릭
4. 권한 확인 후 **"Allow"** 클릭
5. **"Bot User OAuth Token"** (xoxb-로 시작)을 복사하여 `.env` 파일의 `SLACK_BOT_TOKEN`에 설정

### 3. Socket Mode 활성화

1. 왼쪽 메뉴에서 **"Socket Mode"** 클릭
2. **"Enable Socket Mode"** 토글을 활성화
3. 토큰 이름 입력 (예: "AI Assistant Socket Token")
4. **"Generate"** 클릭
5. **"App-Level Token"** (xapp-로 시작)을 복사하여 `.env` 파일의 `SLACK_APP_TOKEN`에 설정

### 4. 이벤트 구독 설정

1. 왼쪽 메뉴에서 **"Event Subscriptions"** 클릭
2. **"Enable Events"** 토글을 활성화
3. **"Subscribe to bot events"** 섹션에 다음 이벤트 추가:
   - `app_mention` - 봇 멘션 이벤트
   - `message.im` - DM 메시지 이벤트
   - `app_home_opened` - 앱 홈 열기 이벤트
4. **"Save Changes"** 클릭

### 5. 슬래시 명령어 생성

1. 왼쪽 메뉴에서 **"Slash Commands"** 클릭
2. **"Create New Command"** 클릭
3. 다음 명령어들을 추가:

**Help 명령어:**
- Command: `/help`
- Request URL: 비워둠 (Socket Mode 사용)
- Short Description: `AI Assistant 봇 도움말`
- Usage Hint: (비워둠)

**Reset 명령어:**
- Command: `/reset_chat`
- Request URL: 비워둠 (Socket Mode 사용)
- Short Description: `채팅 히스토리 리셋`
- Usage Hint: (비워둠)

4. 각 명령어 생성 후 **"Save"** 클릭

### 6. App Home 설정

1. 왼쪽 메뉴에서 **"App Home"** 클릭
2. **"Show Tabs"** 섹션에서:
   - **"Home Tab"** 체크
   - **"Messages Tab"** 체크
3. **"Save"** 클릭

## 🤖 OpenAI Assistant 설정

### 1. OpenAI API 키 생성

1. [OpenAI Platform](https://platform.openai.com/)에 접속
2. 오른쪽 상단 **"API keys"** 클릭
3. **"Create new secret key"** 클릭
4. 키 이름 입력 후 **"Create secret key"** 클릭
5. 생성된 키를 복사하여 `.env` 파일의 `OPENAI_API_KEY`에 설정

### 2. Assistant ID 확인

1. [OpenAI Platform](https://platform.openai.com/)에서 **"Assistants"** 메뉴 클릭
2. 사용할 Assistant 선택
3. Assistant ID (asst_로 시작)를 복사하여 `.env` 파일의 `ASSISTANT_ID`에 설정

## 🚀 봇 실행

### 1. 환경변수 확인

```bash
# .env 파일이 올바르게 설정되었는지 확인
cat .env
```

### 2. 봇 실행

```bash
# 슬랙 봇 실행
python slack_bot.py
```

### 3. 성공 메시지 확인

실행 성공 시 다음과 같은 메시지가 출력됩니다:

```
🚀 AI Assistant 슬랙 봇을 시작합니다...
==================================================
✅ 환경변수 확인 완료
✅ OpenAI Assistant 연결 확인: [Assistant 이름]
INFO:__main__:🚀 AI Assistant 슬랙 봇을 시작합니다...
INFO:slack_bolt.App:⚡️ Bolt app is running!
```

## 📖 사용법

### 1. 채널에서 봇 멘션

```
@assistant_bot 파이썬에서 리스트와 튜플의 차이는 무엇인가요?
```

### 2. DM으로 직접 메시지

봇에게 직접 메시지를 보내면 자동으로 응답합니다.

### 3. 슬래시 명령어

- `/help` - 도움말 보기
- `/reset_chat` - 채팅 히스토리 리셋

## 🔍 주요 기능 설명

### 사용자별 Thread 관리

- 각 사용자마다 독립적인 OpenAI Thread 생성
- 대화 컨텍스트가 사용자별로 분리되어 관리
- 개인별 대화 기록 유지

### 실시간 응답 처리

- "🤔 생각 중입니다..." 로딩 메시지 표시
- OpenAI Assistant API 응답 대기
- 답변 완료 시 메시지 업데이트

### 에러 처리

- API 호출 실패 시 적절한 에러 메시지
- 타임아웃 처리 (30초)
- 로깅을 통한 디버깅 지원

## 🛠 트러블슈팅

### 일반적인 문제들

#### 1. "환경변수 설정 오류" 메시지

**증상:**
```
❌ 환경변수 설정 오류!
다음 환경변수들이 올바르게 설정되지 않았습니다:
  • SLACK_BOT_TOKEN: xoxb-your-bot-token-here
```

**해결 방법:**
1. `.env` 파일을 편집하여 실제 토큰 값으로 변경
2. 토큰 앞뒤에 공백이 없는지 확인
3. 따옴표 없이 토큰만 입력

#### 2. "OpenAI Assistant 연결 실패" 메시지

**증상:**
```
❌ OpenAI Assistant 연결 실패: Error code: 401
```

**해결 방법:**
1. OpenAI API 키가 올바른지 확인
2. Assistant ID가 정확한지 확인
3. OpenAI 계정에 충분한 크레딧이 있는지 확인

#### 3. "invalid_auth" 오류

**증상:**
```
SlackApiError: The request to the Slack API failed.
The server responded with: {'ok': False, 'error': 'invalid_auth'}
```

**해결 방법:**
1. 슬랙 토큰들이 올바른지 확인
2. 봇이 워크스페이스에 설치되어 있는지 확인
3. Socket Mode가 활성화되어 있는지 확인

#### 4. 봇이 응답하지 않는 경우

**해결 방법:**
1. 봇이 채널에 초대되었는지 확인
2. 필요한 OAuth 스코프가 설정되었는지 확인
3. 이벤트 구독이 올바르게 설정되었는지 확인

### 로그 확인

봇 실행 시 콘솔에서 자세한 로그를 확인할 수 있습니다:

```bash
INFO:slack_bolt.App:⚡️ Bolt app is running!
INFO:__main__:새 Thread 생성됨 - User: U1234567890, Thread: thread_abc123
INFO:__main__:Thread 리셋됨 - User: U1234567890
```

## 🧪 테스트 도구

### 터미널 테스트

슬랙 설정 없이도 OpenAI Assistant를 테스트할 수 있습니다:

```bash
# 터미널 테스트 실행
python test_assistant.py

# 또는 스크립트 사용
./run_test.sh
```

### 주요 테스트 명령어

- `/help` - 도움말 보기
- `/reset` - 대화 기록 초기화
- `/status` - 현재 상태 확인
- `/quit` - 프로그램 종료

## 📝 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다. 