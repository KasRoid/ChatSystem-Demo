# WebSocket 채팅 시스템

Python FastAPI + Socket.IO 기반 실시간 채팅 서버

## 기술 스택

**Backend**: FastAPI, python-socketio, uvicorn
**Frontend**: Vanilla JavaScript, socket.io-client (CDN)

## 프로젝트 구조

```
ChatSystem-Demo/
├── venv/                   # Python 가상환경
├── chat-server/
│   ├── server.py           # 서버 코드
│   ├── requirements.txt    # 패키지 목록
│   └── public/
│       └── index.html      # 클라이언트
└── README.md
```

## 실행 방법

### 1. 가상환경 생성 및 활성화

```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 2. 패키지 설치

```bash
cd chat-server
pip install -r requirements.txt
```

### 3. 서버 실행

```bash
python server.py
```

실행 후 다음 메시지가 표시됩니다:

```
============================================================
Starting Real-time Chat Server
Host: 0.0.0.0
Port: 8000
Access the chat at: http://localhost:8000
============================================================
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 4. 브라우저 접속

**http://localhost:8000**

## 사용 방법

1. **Room 입장**: Room ID 입력 후 "입장" 버튼 클릭
2. **메시지 전송**: 메시지 입력 후 `Enter` 키 (줄바꿈: `Shift + Enter`)
3. **다중 사용자 테스트**: 새 탭에서 같은 Room ID로 입장

## 주요 기능

- 실시간 메시지 전송 (Socket.IO)
- Room 기반 채팅방
- 자동 닉네임 생성 (user-xxxxxxxx)
- 메시지 히스토리 (최근 50개)
- 자동 재연결
- 입장/퇴장 시스템 메시지
- 빈 방 자동 삭제

## 테스트

테스트 스크립트 실행:

```bash
# 간단한 테스트 (10개)
python test_chat_simple.py

# 전체 테스트 (20+ 개)
python test_chat_system.py
```

테스트 결과: **100% 통과 (10/10)** ✅
