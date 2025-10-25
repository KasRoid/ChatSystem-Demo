# Testing Guide - FastAPI + SocketIO Chat Server

## 구현 완료 내역

### 1. 구현된 파일 경로

- **서버**: `/Users/sdy/Downloads/ChatSystem-Demo/chat-server/server.py` (649 lines)
- **클라이언트**: `/Users/sdy/Downloads/ChatSystem-Demo/chat-server/public/index.html` (443 lines)
- **의존성**: `/Users/sdy/Downloads/ChatSystem-Demo/chat-server/requirements.txt`

### 2. 구현된 주요 기능

#### 서버 기능 (server.py)

**데이터 구조**
- `Message` 클래스: 메시지 객체 (id, sender, text, timestamp, message_type)
- `Session` 클래스: 사용자 세션 관리 (session_id, nickname, current_room, connected_at)
- `Room` 클래스: 채팅방 관리 (room_id, users, messages, created_at)
- 메모리 기반 저장소: rooms, sessions, session_to_room 딕셔너리

**SocketIO 이벤트 핸들러**
1. **connect**:
   - UUID 기반 닉네임 자동 생성 (형식: `user-{uuid[:8]}`)
   - 세션 생성 및 저장
   - 클라이언트에 닉네임 전달

2. **join_room**:
   - Room 검증 및 자동 생성
   - 사용자 추가 및 SocketIO room 입장
   - 시스템 메시지 브로드캐스트 ("{nickname} 님이 입장했습니다")
   - 메시지 히스토리 전송 (최근 50개)
   - 참여자 수 전달

3. **send_message**:
   - 메시지 검증 (빈 메시지, 잘못된 형식 체크)
   - 타임스탬프 자동 추가 (ISO 8601 형식)
   - Room의 모든 사용자에게 브로드캐스트
   - 메시지 히스토리에 저장 (deque로 최근 50개 자동 유지)

4. **leave_room**:
   - Room에서 사용자 제거
   - 시스템 메시지 브로드캐스트 ("{nickname} 님이 퇴장했습니다")
   - 빈 방 자동 삭제
   - 세션 상태 업데이트

5. **disconnect**:
   - 현재 Room에서 자동 퇴장
   - 세션 정리

**HTTP 엔드포인트**
- `GET /`: index.html 제공
- `GET /health`: 서버 상태 체크 (active_rooms, active_sessions)
- `GET /stats`: 상세 통계 (room별 user count, message count)

**추가 구현 사항**
- 완벽한 타입 힌팅 (Type hints)
- 상세한 에러 핸들링 및 로깅
- CORS 설정 (로컬 개발 지원)
- 메모리 효율적인 데이터 구조 (deque로 자동 크기 제한)
- Production-ready 코드 구조 (dataclasses, docstrings, 모듈화)

#### 클라이언트 기능 (index.html)

**UI 컴포넌트**
- 연결 상태 표시 (온라인/오프라인)
- 닉네임 표시
- Room 입장/퇴장 버튼
- 메시지 목록 (자동 스크롤)
- 메시지 입력창

**SocketIO 이벤트 처리**
- 자동 연결 및 재연결
- 닉네임 수신 및 표시
- Room 입장/퇴장 처리
- 실시간 메시지 수신 및 표시
- 메시지 히스토리 로드

**UX 기능**
- Enter 키로 메시지 전송
- Shift+Enter로 줄바꿈
- 내 메시지 우측 정렬 (파란색)
- 다른 사용자 메시지 좌측 정렬 (흰색)
- 시스템 메시지 중앙 정렬 (노란색)
- 마지막 방 자동 저장/복원 (localStorage)
- 탭 종료 시 자동 퇴장

---

## 테스트 방법

### 1. 서버 실행

```bash
# 1. chat-server 디렉토리로 이동
cd /Users/sdy/Downloads/ChatSystem-Demo/chat-server

# 2. 가상환경 활성화 (이미 설정되어 있다면)
source ../venv/bin/activate  # macOS/Linux
# 또는
../venv/Scripts/activate  # Windows

# 3. 의존성 설치 확인
pip install -r requirements.txt

# 4. 서버 실행
python server.py
```

**예상 출력:**
```
============================================================
Starting Real-time Chat Server
Host: 0.0.0.0
Port: 8000
Access the chat at: http://localhost:8000
============================================================
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 2. 클라이언트 접속

**방법 1: 브라우저에서 직접 접속**
1. 브라우저를 열고 `http://localhost:8000` 접속
2. Room ID 입력 (예: `room1`)
3. "입장" 버튼 클릭
4. 메시지 입력 및 전송

**방법 2: 다중 사용자 테스트**
1. 첫 번째 브라우저 탭에서 `http://localhost:8000` 접속
2. Room ID `room1` 입력 후 입장
3. 새 탭(또는 시크릿 모드)에서 다시 `http://localhost:8000` 접속
4. 같은 Room ID `room1` 입력 후 입장
5. 양쪽에서 메시지 주고받기

### 3. 기능 테스트 체크리스트

#### 기본 기능
- [ ] 서버 연결 시 자동 닉네임 부여 (`user-xxxxxxxx` 형식)
- [ ] 닉네임이 화면에 표시됨
- [ ] Room ID 입력 및 입장 가능
- [ ] 입장 시 시스템 메시지 표시 ("{nickname} 님이 입장했습니다")

#### 메시지 기능
- [ ] 메시지 입력 및 전송 가능
- [ ] 내 메시지는 우측 정렬 (파란색)
- [ ] 다른 사용자 메시지는 좌측 정렬 (흰색)
- [ ] 시스템 메시지는 중앙 정렬 (노란색)
- [ ] 메시지 타임스탬프 표시
- [ ] Enter로 전송, Shift+Enter로 줄바꿈

#### Room 관리
- [ ] 여러 사용자가 같은 Room에 입장 가능
- [ ] 참여자 수 표시 업데이트
- [ ] 메시지 히스토리 로드 (최대 50개)
- [ ] "퇴장" 버튼으로 Room 나가기
- [ ] 퇴장 시 시스템 메시지 표시 ("{nickname} 님이 퇴장했습니다")
- [ ] 빈 방 자동 삭제

#### 연결 관리
- [ ] 연결 상태 표시 (연결됨/연결 끊김)
- [ ] 페이지 새로고침 후 마지막 Room 자동 복원
- [ ] 탭 종료 시 자동 퇴장
- [ ] 네트워크 끊김 후 자동 재연결

### 4. 고급 테스트

#### 동시 접속 테스트
```bash
# 터미널에서 여러 브라우저 실행
open -a "Google Chrome" http://localhost:8000
open -a "Safari" http://localhost:8000
open -a "Firefox" http://localhost:8000
```

#### 서버 상태 확인
```bash
# Health check
curl http://localhost:8000/health

# 상세 통계
curl http://localhost:8000/stats
```

#### 로그 확인
서버 실행 중인 터미널에서 다음 로그들을 확인:
- 클라이언트 연결: `Client connected: {sid} (nickname: {nickname})`
- Room 입장: `{nickname} ({sid}) joined room: {room_id}`
- 메시지 전송: `Message from {nickname} in {room_id}: {text}...`
- Room 퇴장: `{nickname} ({sid}) left room: {room_id}`
- Room 삭제: `Deleted empty room: {room_id}`

### 5. 문제 해결

#### 서버가 시작되지 않을 때
```bash
# 포트 8000이 이미 사용 중인지 확인
lsof -i :8000

# 사용 중이면 프로세스 종료
kill -9 <PID>

# 또는 다른 포트 사용 (server.py 수정)
PORT = 8001  # server.py 상단에서 수정
```

#### 연결이 안 될 때
- 방화벽 설정 확인
- 브라우저 콘솔에서 에러 메시지 확인 (F12)
- 서버 로그에서 에러 확인

#### 메시지가 전송되지 않을 때
- Room에 입장했는지 확인
- 빈 메시지를 보내려고 하지 않는지 확인
- 브라우저 콘솔의 네트워크 탭 확인

---

## 성능 및 제한사항

### 현재 구현의 제한사항
- **메모리 기반 저장**: 서버 재시작 시 모든 데이터 손실
- **메시지 히스토리**: Room당 최대 50개만 유지
- **인증 없음**: 누구나 접속 가능 (로컬 개발용)
- **단일 서버**: 수평 확장 불가 (로드 밸런싱 미지원)

### 권장 동시 접속자 수
- 로컬 개발: 10-20명
- 테스트 환경: 50-100명
- 프로덕션 고려 시: Redis, DB, 세션 클러스터링 필요

---

## 개발 팁

### 디버깅 모드
server.py의 로깅 레벨 변경:
```python
logging.basicConfig(
    level=logging.DEBUG,  # INFO -> DEBUG로 변경
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### 메시지 히스토리 크기 조정
server.py 상단:
```python
MAX_MESSAGE_HISTORY = 100  # 50 -> 100으로 변경
```

### CORS 설정 (프로덕션)
server.py의 CORS 미들웨어:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 다음 단계

### Phase 2 개선 사항 (선택)
1. **닉네임 커스터마이징**: 사용자가 직접 닉네임 설정
2. **Room 목록**: 현재 활성화된 Room 목록 표시
3. **타이핑 인디케이터**: "user-1234 is typing..." 표시
4. **파일 업로드**: 이미지/파일 공유 기능
5. **읽음 표시**: 메시지 읽음/안읽음 표시

### 프로덕션 배포 고려사항
1. **데이터베이스**: PostgreSQL/MongoDB로 영구 저장
2. **Redis**: 세션 관리 및 메시지 캐싱
3. **인증**: JWT 기반 사용자 인증
4. **HTTPS**: SSL/TLS 인증서 설정
5. **모니터링**: Prometheus, Grafana 연동
6. **로드 밸런싱**: Nginx, 멀티 서버 구성

---

## 참고 자료

- FastAPI 공식 문서: https://fastapi.tiangolo.com/
- python-socketio 공식 문서: https://python-socketio.readthedocs.io/
- Socket.IO 클라이언트 문서: https://socket.io/docs/v4/client-api/

---

**구현 완료일**: 2025-10-25
**Python 버전**: 3.13.3
**테스트 환경**: macOS (Darwin 25.0.0)
