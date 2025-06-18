#!/bin/bash

echo "🚀 OpenAI Assistant 터미널 테스트 실행"
echo "======================================"

# 가상환경 활성화 확인
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  가상환경이 활성화되지 않았습니다."
    echo "💡 다음 명령어로 가상환경을 활성화해주세요:"
    echo "   source ../assistant-venv/bin/activate"
    echo ""
    read -p "계속 진행하시겠습니까? (y/N): " confirm
    if [[ $confirm != [yY] ]]; then
        echo "❌ 테스트를 중단합니다."
        exit 1
    fi
fi

# .env 파일 확인
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일이 없습니다."
    echo "💡 env_example.txt를 참고하여 .env 파일을 생성해주세요:"
    echo "   cp env_example.txt .env"
    echo "   # 그리고 .env 파일을 편집하여 API 키를 설정하세요"
    exit 1
fi

# Python 파일 실행
echo "🔄 테스트 스크립트를 실행합니다..."
python test_assistant.py 