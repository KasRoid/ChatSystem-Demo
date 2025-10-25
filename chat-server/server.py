"""
FastAPI + SocketIO Real-time Chat Server

A production-ready WebSocket chat server implementation with room management,
message history, and automatic session handling.

Architecture:
- FastAPI for HTTP endpoints and static file serving
- python-socketio for WebSocket real-time communication
- In-memory data structures for rooms and sessions
- Automatic nickname generation and session lifecycle management
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Deque
from collections import deque, defaultdict
from dataclasses import dataclass, field, asdict

import socketio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


# ============================================================================
# Configuration
# ============================================================================

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MAX_MESSAGE_HISTORY = 50  # Maximum messages to keep per room
HOST = "0.0.0.0"
PORT = 8000


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Message:
    """
    Represents a chat message with metadata.

    Attributes:
        id: Unique message identifier
        sender: Nickname of the message sender
        text: Message content
        timestamp: ISO 8601 formatted timestamp
        message_type: Type of message ('user' or 'system')
    """
    id: str
    sender: str
    text: str
    timestamp: str
    message_type: str = "user"  # 'user' or 'system'

    def to_dict(self) -> dict:
        """Convert message to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class Session:
    """
    Represents a user session connected via SocketIO.

    Attributes:
        session_id: SocketIO session identifier
        nickname: Unique nickname assigned to the user
        current_room: Current room the user is in (None if not in a room)
        connected_at: Timestamp when the session was created
    """
    session_id: str
    nickname: str
    current_room: Optional[str] = None
    connected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Room:
    """
    Represents a chat room with users and message history.

    Attributes:
        room_id: Unique room identifier
        users: Set of session IDs currently in the room
        messages: Message history (limited to MAX_MESSAGE_HISTORY)
        created_at: Timestamp when the room was created
    """
    room_id: str
    users: set = field(default_factory=set)
    messages: Deque[Message] = field(default_factory=lambda: deque(maxlen=MAX_MESSAGE_HISTORY))
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_user(self, session_id: str) -> None:
        """Add a user to the room."""
        self.users.add(session_id)

    def remove_user(self, session_id: str) -> None:
        """Remove a user from the room."""
        self.users.discard(session_id)

    def add_message(self, message: Message) -> None:
        """Add a message to the room history (automatically maintains size limit)."""
        self.messages.append(message)

    def get_message_history(self) -> List[dict]:
        """Get all messages in the room as a list of dictionaries."""
        return [msg.to_dict() for msg in self.messages]

    def is_empty(self) -> bool:
        """Check if the room has no users."""
        return len(self.users) == 0


# ============================================================================
# In-Memory Data Storage
# ============================================================================

# Global data structures for managing rooms and sessions
rooms: Dict[str, Room] = {}  # room_id -> Room object
sessions: Dict[str, Session] = {}  # session_id -> Session object
session_to_room: Dict[str, str] = {}  # session_id -> current room_id


# ============================================================================
# Helper Functions
# ============================================================================

def generate_nickname() -> str:
    """
    Generate a unique, user-friendly nickname.

    Format: user-{first 8 chars of UUID}
    Example: user-a1b2c3d4

    Returns:
        A unique nickname string
    """
    unique_id = str(uuid.uuid4())[:8]
    return f"user-{unique_id}"


def get_current_timestamp() -> str:
    """
    Get current timestamp in ISO 8601 format.

    Returns:
        ISO 8601 formatted timestamp string
    """
    return datetime.utcnow().isoformat() + "Z"


def create_system_message(text: str) -> Message:
    """
    Create a system message (e.g., user joined/left notifications).

    Args:
        text: The system message text

    Returns:
        A Message object with type 'system'
    """
    return Message(
        id=str(uuid.uuid4()),
        sender="System",
        text=text,
        timestamp=get_current_timestamp(),
        message_type="system"
    )


def get_or_create_room(room_id: str) -> Room:
    """
    Get an existing room or create a new one if it doesn't exist.

    Args:
        room_id: The room identifier

    Returns:
        The Room object
    """
    if room_id not in rooms:
        rooms[room_id] = Room(room_id=room_id)
        logger.info(f"Created new room: {room_id}")
    return rooms[room_id]


def cleanup_empty_room(room_id: str) -> None:
    """
    Delete a room if it has no users.

    Args:
        room_id: The room identifier to check and potentially delete
    """
    if room_id in rooms and rooms[room_id].is_empty():
        del rooms[room_id]
        logger.info(f"Deleted empty room: {room_id}")


def cleanup_session(session_id: str) -> None:
    """
    Clean up all data associated with a session.

    Args:
        session_id: The session identifier to clean up
    """
    # Remove from sessions
    if session_id in sessions:
        del sessions[session_id]

    # Remove from session_to_room mapping
    if session_id in session_to_room:
        del session_to_room[session_id]

    logger.info(f"Cleaned up session: {session_id}")


# ============================================================================
# SocketIO Server Setup
# ============================================================================

# Create SocketIO server with async mode for ASGI compatibility
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',  # Allow all origins for local development
    logger=True,
    engineio_logger=False  # Reduce verbosity
)


# ============================================================================
# SocketIO Event Handlers
# ============================================================================

@sio.event
async def connect(sid: str, environ: dict):
    """
    Handle new client connections.

    Actions:
    1. Generate a unique nickname for the user
    2. Create a session object
    3. Store session data
    4. Send nickname to the client

    Args:
        sid: SocketIO session ID
        environ: WSGI environment dictionary
    """
    try:
        # Generate unique nickname
        nickname = generate_nickname()

        # Create and store session
        session = Session(
            session_id=sid,
            nickname=nickname
        )
        sessions[sid] = session

        logger.info(f"Client connected: {sid} (nickname: {nickname})")

        # Send nickname to client
        await sio.emit('nickname_assigned', {'nickname': nickname}, room=sid)

    except Exception as e:
        logger.error(f"Error in connect handler: {e}", exc_info=True)


@sio.event
async def disconnect(sid: str):
    """
    Handle client disconnections.

    Actions:
    1. Leave current room if in one
    2. Clean up session data

    Args:
        sid: SocketIO session ID
    """
    try:
        logger.info(f"Client disconnecting: {sid}")

        # Check if user is in a room
        if sid in session_to_room:
            room_id = session_to_room[sid]

            # Leave the room (this will handle all cleanup)
            await leave_room({'roomId': room_id}, sid)

        # Clean up session
        cleanup_session(sid)

    except Exception as e:
        logger.error(f"Error in disconnect handler: {e}", exc_info=True)


@sio.event
async def join_room(sid: str, data: dict):
    """
    Handle room join requests.

    Actions:
    1. Validate room ID
    2. Get or create the room
    3. Add user to the room
    4. Join SocketIO room for broadcasting
    5. Send system message to other users
    6. Send message history to the joining user

    Args:
        sid: SocketIO session ID
        data: Dictionary containing 'roomId'
    """
    try:
        room_id = data.get('roomId')

        # Validate room ID
        if not room_id or not isinstance(room_id, str):
            logger.warning(f"Invalid room ID from {sid}: {room_id}")
            await sio.emit('error', {'message': 'Invalid room ID'}, room=sid)
            return

        # Get session
        if sid not in sessions:
            logger.error(f"Session not found for {sid}")
            await sio.emit('error', {'message': 'Session not found'}, room=sid)
            return

        session = sessions[sid]
        nickname = session.nickname

        # Leave current room if in one
        if session.current_room:
            await leave_room({'roomId': session.current_room}, sid)

        # Get or create room
        room = get_or_create_room(room_id)

        # Add user to room
        room.add_user(sid)
        session.current_room = room_id
        session_to_room[sid] = room_id

        # Join SocketIO room (for broadcasting)
        await sio.enter_room(sid, room_id)

        logger.info(f"{nickname} ({sid}) joined room: {room_id}")

        # Create and broadcast system message
        join_message = create_system_message(f"{nickname} 님이 입장했습니다")
        room.add_message(join_message)

        # Broadcast to all users in the room (including the joiner)
        await sio.emit('new_message', join_message.to_dict(), room=room_id)

        # Send message history to the joining user
        history = room.get_message_history()
        await sio.emit('room_joined', {
            'roomId': room_id,
            'nickname': nickname,
            'history': history,
            'userCount': len(room.users)
        }, room=sid)

    except Exception as e:
        logger.error(f"Error in join_room handler: {e}", exc_info=True)
        await sio.emit('error', {'message': 'Failed to join room'}, room=sid)


@sio.event
async def send_message(sid: str, data: dict):
    """
    Handle message sending.

    Actions:
    1. Validate message data
    2. Check if user is in a room
    3. Create message object
    4. Add to room history
    5. Broadcast to all users in the room

    Args:
        sid: SocketIO session ID
        data: Dictionary containing 'roomId' and 'text'
    """
    try:
        room_id = data.get('roomId')
        text = data.get('text')

        # Validate message data
        if not room_id or not text:
            logger.warning(f"Invalid message data from {sid}")
            await sio.emit('error', {'message': 'Invalid message data'}, room=sid)
            return

        # Validate text is a string and not empty after stripping
        if not isinstance(text, str) or not text.strip():
            logger.warning(f"Empty message from {sid}")
            return

        # Get session and room
        if sid not in sessions:
            logger.error(f"Session not found for {sid}")
            await sio.emit('error', {'message': 'Session not found'}, room=sid)
            return

        session = sessions[sid]

        # Verify user is in the room
        if session.current_room != room_id:
            logger.warning(f"{session.nickname} tried to send message to room {room_id} but is not in it")
            await sio.emit('error', {'message': 'You are not in this room'}, room=sid)
            return

        # Verify room exists
        if room_id not in rooms:
            logger.error(f"Room not found: {room_id}")
            await sio.emit('error', {'message': 'Room not found'}, room=sid)
            return

        room = rooms[room_id]

        # Create message
        message = Message(
            id=str(uuid.uuid4()),
            sender=session.nickname,
            text=text.strip(),
            timestamp=get_current_timestamp(),
            message_type="user"
        )

        # Add to room history
        room.add_message(message)

        logger.info(f"Message from {session.nickname} in {room_id}: {text[:50]}...")

        # Broadcast to all users in the room
        await sio.emit('new_message', message.to_dict(), room=room_id)

    except Exception as e:
        logger.error(f"Error in send_message handler: {e}", exc_info=True)
        await sio.emit('error', {'message': 'Failed to send message'}, room=sid)


@sio.event
async def leave_room(sid: str, data: dict):
    """
    Handle room leave requests.

    Actions:
    1. Validate room ID
    2. Remove user from room
    3. Leave SocketIO room
    4. Send system message to remaining users
    5. Clean up empty room
    6. Update session state

    Args:
        sid: SocketIO session ID
        data: Dictionary containing 'roomId'
    """
    try:
        room_id = data.get('roomId')

        # Validate room ID
        if not room_id:
            logger.warning(f"Invalid room ID for leave from {sid}")
            return

        # Get session
        if sid not in sessions:
            logger.warning(f"Session not found for leave: {sid}")
            return

        session = sessions[sid]
        nickname = session.nickname

        # Check if room exists
        if room_id not in rooms:
            logger.warning(f"Attempted to leave non-existent room: {room_id}")
            return

        room = rooms[room_id]

        # Remove user from room
        room.remove_user(sid)

        # Leave SocketIO room
        await sio.leave_room(sid, room_id)

        # Update session
        session.current_room = None
        if sid in session_to_room:
            del session_to_room[sid]

        logger.info(f"{nickname} ({sid}) left room: {room_id}")

        # Create and broadcast system message to remaining users
        if not room.is_empty():
            leave_message = create_system_message(f"{nickname} 님이 퇴장했습니다")
            room.add_message(leave_message)
            await sio.emit('new_message', leave_message.to_dict(), room=room_id)

            # Update user count for remaining users
            await sio.emit('user_count_updated', {'userCount': len(room.users)}, room=room_id)

        # Clean up empty room
        cleanup_empty_room(room_id)

        # Notify the leaving user
        await sio.emit('room_left', {'roomId': room_id}, room=sid)

    except Exception as e:
        logger.error(f"Error in leave_room handler: {e}", exc_info=True)


# ============================================================================
# FastAPI Application Setup
# ============================================================================

# Create FastAPI app
app = FastAPI(
    title="Real-time Chat Server",
    description="FastAPI + SocketIO WebSocket chat server with room management",
    version="1.0.0"
)

# Configure CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# HTTP Endpoints
# ============================================================================

@app.get("/")
async def serve_index():
    """
    Serve the main HTML client file.

    Returns:
        FileResponse with index.html
    """
    return FileResponse("/Users/sdy/Downloads/ChatSystem-Demo/chat-server/public/index.html")


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.

    Returns:
        Dictionary with server status and statistics
    """
    return {
        "status": "healthy",
        "active_rooms": len(rooms),
        "active_sessions": len(sessions),
        "timestamp": get_current_timestamp()
    }


@app.get("/stats")
async def get_stats():
    """
    Get server statistics.

    Returns:
        Dictionary with detailed server statistics
    """
    room_stats = []
    for room_id, room in rooms.items():
        room_stats.append({
            "room_id": room_id,
            "user_count": len(room.users),
            "message_count": len(room.messages),
            "created_at": room.created_at.isoformat()
        })

    return {
        "total_rooms": len(rooms),
        "total_sessions": len(sessions),
        "rooms": room_stats,
        "timestamp": get_current_timestamp()
    }


# Mount static files directory
app.mount("/static", StaticFiles(directory="/Users/sdy/Downloads/ChatSystem-Demo/chat-server/public"), name="static")


# ============================================================================
# ASGI Application
# ============================================================================

# Wrap FastAPI app with SocketIO ASGI app
socket_app = socketio.ASGIApp(
    sio,
    app,
    socketio_path='socket.io'
)


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    """
    Run the server using Uvicorn.

    Configuration:
    - Host: 0.0.0.0 (accessible from any network interface)
    - Port: 8000
    - Development mode with auto-reload disabled for stability
    """
    logger.info("="*60)
    logger.info("Starting Real-time Chat Server")
    logger.info(f"Host: {HOST}")
    logger.info(f"Port: {PORT}")
    logger.info(f"Access the chat at: http://localhost:{PORT}")
    logger.info("="*60)

    uvicorn.run(
        socket_app,
        host=HOST,
        port=PORT,
        log_level="info"
    )
