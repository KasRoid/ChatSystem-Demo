# WebSocket 채팅 시스템 (ChatSystem-Demo)

Python 기반의 간단한 로컬 WebSocket 채팅 서버와 단일 HTML 파일 클라이언트로 구성된 실습용 실시간 채팅 시스템입니다.

## 🎯 핵심 철학

**최소 의존성, 최대 단순성**

- 로컬 실습용 시스템 (인증, DB, 배포 등 복잡한 요소 제외)
- 메모리 기반 데이터 저장
- 단일 파일 클라이언트 (빌드 과정 불필요)

## 🏗️ 기술 스택

### Backend
- **FastAPI**: HTTP 서버 및 정적 파일 제공
- **python-socketio**: WebSocket 실시간 통신
- **uvicorn**: ASGI 서버

### Frontend
- **Vanilla JavaScript**: 순수 자바스크립트
- **socket.io-client**: WebSocket 클라이언트 (CDN)
- **HTML/CSS**: 단일 파일 구성

## 📁 프로젝트 구조

```
ChatSystem-Demo/
├── chat-server/
│   ├── server.py           # 메인 서버 로직
│   ├── requirements.txt    # Python 패키지 목록
│   └── public/
│       └── index.html      # 클라이언트 파일
├── strategy.md             # 구현 전략 문서
├── .gitignore
└── README.md
```

## 🚀 시작하기

### 1. 가상환경 생성 (권장)

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

서버가 성공적으로 시작되면 다음과 같은 메시지가 표시됩니다:

```
INFO:     Uvicorn running on http://localhost:8000
INFO:     Started server process
```

### 4. 클라이언트 접속

브라우저에서 http://localhost:8000 을 열어 채팅 시스템에 접속합니다.

## 🎮 사용 방법

1. **Room 입장**
   - Room ID를 입력하고 "입장" 버튼 클릭
   - 같은 Room ID로 입장한 사용자들끼리 채팅 가능

2. **메시지 전송**
   - 메시지 입력 후 "전송" 버튼 클릭
   - 또는 `Enter` 키로 전송 (줄바꿈은 `Shift + Enter`)

3. **다중 사용자 테스트**
   - 새 탭 또는 시크릿 모드에서 동일 URL 접속
   - 같은 Room ID로 입장하여 실시간 채팅 확인

## ✨ 주요 기능

- ✅ **실시간 메시지 전송**: Socket.IO 기반 양방향 통신
- ✅ **Room 기반 채팅**: 여러 채팅방 생성 및 관리
- ✅ **자동 닉네임 생성**: UUID 기반 고유 닉네임
- ✅ **메시지 히스토리**: 최근 50개 메시지 저장 및 전달
- ✅ **자동 재연결**: 연결 끊김 시 마지막 Room 자동 복구
- ✅ **시스템 메시지**: 입장/퇴장 알림
- ✅ **빈 방 자동 정리**: 사용자 없는 방 자동 삭제

## 📚 학습 목표

이 프로젝트를 통해 다음을 학습할 수 있습니다:

- WebSocket 실시간 통신 원리
- Socket.IO Room 개념과 브로드캐스트 메커니즘
- 클라이언트-서버 이벤트 기반 통신 패턴
- 재연결 및 상태 관리 로직
- FastAPI와 python-socketio 통합

## 🔧 개발 환경

- Python 3.8 이상
- 모던 웹 브라우저 (Chrome, Firefox, Safari 등)

## 📝 참고 문서

- [strategy.md](./strategy.md) - 상세한 구현 전략 및 단계별 가이드
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Socket.IO 공식 문서](https://socket.io/docs/)

## 📄 라이선스

이 프로젝트는 학습 및 실습 목적으로 제작되었습니다.
