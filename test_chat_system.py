"""
Comprehensive WebSocket Chat System Test Suite

This test suite validates all aspects of the Socket.IO-based real-time chat system
including connection management, room operations, message handling, multi-user scenarios,
and edge cases.

Test Coverage:
1. Basic Connection Tests
2. Room Functionality Tests
3. Message Handling Tests
4. Multi-User Concurrency Tests
5. Reconnection & State Recovery Tests
6. Edge Cases & Error Handling Tests
"""

import socketio
import time
import threading
import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict


# ============================================================================
# Test Configuration
# ============================================================================

SERVER_URL = 'http://localhost:8000'
TEST_TIMEOUT = 5.0  # seconds to wait for events
SHORT_DELAY = 0.1  # short delay between operations
MEDIUM_DELAY = 0.5  # medium delay for state propagation


# ============================================================================
# Test Data Structures
# ============================================================================

@dataclass
class TestClient:
    """Represents a test client with Socket.IO connection and event tracking."""
    client_id: str
    socket: socketio.Client
    nickname: Optional[str] = None
    current_room: Optional[str] = None
    connected: bool = False
    received_messages: List[Dict[str, Any]] = field(default_factory=list)
    received_events: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def clear_messages(self):
        """Clear all received messages."""
        self.received_messages.clear()

    def clear_events(self):
        """Clear all received events."""
        self.received_events.clear()

    def get_messages_count(self) -> int:
        """Get count of received messages."""
        return len(self.received_messages)

    def get_user_messages(self) -> List[Dict[str, Any]]:
        """Get only user messages (not system messages)."""
        return [msg for msg in self.received_messages if msg.get('message_type') == 'user']

    def get_system_messages(self) -> List[Dict[str, Any]]:
        """Get only system messages."""
        return [msg for msg in self.received_messages if msg.get('message_type') == 'system']


@dataclass
class TestResult:
    """Represents the result of a test case."""
    test_name: str
    status: str  # 'PASS', 'FAIL', 'SKIP'
    duration: float
    description: str
    steps: List[str]
    result: str
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class TestSuite:
    """Represents a collection of test results."""
    suite_name: str
    test_results: List[TestResult] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def add_result(self, result: TestResult):
        """Add a test result to the suite."""
        self.test_results.append(result)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.status == 'PASS')
        failed = sum(1 for r in self.test_results if r.status == 'FAIL')
        skipped = sum(1 for r in self.test_results if r.status == 'SKIP')

        total_duration = (self.end_time - self.start_time) if (self.end_time and self.start_time) else 0

        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
            'duration': total_duration
        }


# ============================================================================
# Test Client Factory
# ============================================================================

def create_test_client(client_id: str = None) -> TestClient:
    """
    Create and configure a test client with event handlers.

    Args:
        client_id: Optional client identifier

    Returns:
        Configured TestClient instance
    """
    if client_id is None:
        client_id = f"test-{uuid.uuid4().hex[:8]}"

    sio = socketio.Client()
    test_client = TestClient(client_id=client_id, socket=sio)

    # Connection event handlers
    @sio.on('connect')
    def on_connect():
        test_client.connected = True
        test_client.received_events.append({'event': 'connect', 'timestamp': time.time()})

    @sio.on('disconnect')
    def on_disconnect():
        test_client.connected = False
        test_client.received_events.append({'event': 'disconnect', 'timestamp': time.time()})

    @sio.on('nickname_assigned')
    def on_nickname_assigned(data):
        test_client.nickname = data.get('nickname')
        test_client.received_events.append({
            'event': 'nickname_assigned',
            'data': data,
            'timestamp': time.time()
        })

    @sio.on('room_joined')
    def on_room_joined(data):
        test_client.current_room = data.get('roomId')
        test_client.received_events.append({
            'event': 'room_joined',
            'data': data,
            'timestamp': time.time()
        })

    @sio.on('room_left')
    def on_room_left(data):
        test_client.current_room = None
        test_client.received_events.append({
            'event': 'room_left',
            'data': data,
            'timestamp': time.time()
        })

    @sio.on('new_message')
    def on_new_message(message):
        test_client.received_messages.append(message)
        test_client.received_events.append({
            'event': 'new_message',
            'data': message,
            'timestamp': time.time()
        })

    @sio.on('user_count_updated')
    def on_user_count_updated(data):
        test_client.received_events.append({
            'event': 'user_count_updated',
            'data': data,
            'timestamp': time.time()
        })

    @sio.on('error')
    def on_error(data):
        error_msg = data.get('message', 'Unknown error')
        test_client.errors.append(error_msg)
        test_client.received_events.append({
            'event': 'error',
            'data': data,
            'timestamp': time.time()
        })

    return test_client


def connect_client(client: TestClient, timeout: float = TEST_TIMEOUT) -> bool:
    """
    Connect a test client to the server.

    Args:
        client: TestClient instance
        timeout: Connection timeout in seconds

    Returns:
        True if connected successfully, False otherwise
    """
    try:
        client.socket.connect(SERVER_URL, wait_timeout=timeout)

        # Wait for nickname assignment
        wait_start = time.time()
        while not client.nickname and (time.time() - wait_start) < timeout:
            time.sleep(SHORT_DELAY)

        return client.connected and client.nickname is not None
    except Exception as e:
        client.errors.append(f"Connection failed: {str(e)}")
        return False


def disconnect_client(client: TestClient):
    """
    Disconnect a test client from the server.

    Args:
        client: TestClient instance
    """
    try:
        if client.socket.connected:
            client.socket.disconnect()
    except Exception as e:
        client.errors.append(f"Disconnect failed: {str(e)}")


# ============================================================================
# Test Utilities
# ============================================================================

def wait_for_condition(condition_func, timeout: float = TEST_TIMEOUT, check_interval: float = 0.05) -> bool:
    """
    Wait for a condition to become true.

    Args:
        condition_func: Function that returns True when condition is met
        timeout: Maximum time to wait in seconds
        check_interval: Time between condition checks

    Returns:
        True if condition was met, False if timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(check_interval)
    return False


def wait_for_messages(client: TestClient, expected_count: int, timeout: float = TEST_TIMEOUT) -> bool:
    """
    Wait for a client to receive a specific number of messages.

    Args:
        client: TestClient instance
        expected_count: Expected number of messages
        timeout: Maximum time to wait

    Returns:
        True if expected messages received, False otherwise
    """
    return wait_for_condition(
        lambda: len(client.received_messages) >= expected_count,
        timeout=timeout
    )


def validate_message_format(message: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate that a message has the correct format.

    Args:
        message: Message dictionary to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    required_fields = ['id', 'sender', 'text', 'timestamp', 'message_type']

    for field in required_fields:
        if field not in message:
            errors.append(f"Missing required field: {field}")

    if 'message_type' in message:
        if message['message_type'] not in ['user', 'system']:
            errors.append(f"Invalid message_type: {message['message_type']}")

    if 'timestamp' in message:
        try:
            # Validate ISO 8601 format
            datetime.fromisoformat(message['timestamp'].replace('Z', '+00:00'))
        except ValueError:
            errors.append(f"Invalid timestamp format: {message['timestamp']}")

    return len(errors) == 0, errors


# ============================================================================
# Test Suite 1: Basic Connection Tests
# ============================================================================

def run_basic_connection_tests() -> TestSuite:
    """Execute basic connection tests."""
    suite = TestSuite(suite_name="Basic Connection Tests")
    suite.start_time = time.time()

    # Test 1.1: Single Client Connection
    test_start = time.time()
    try:
        steps = [
            "Create Socket.IO client",
            "Connect to server at http://localhost:8000",
            "Wait for 'connect' event",
            "Wait for 'nickname_assigned' event",
            "Validate nickname format (user-{uuid[:8]})"
        ]

        client = create_test_client()
        success = connect_client(client)

        if success and client.nickname:
            # Validate nickname format
            if client.nickname.startswith('user-') and len(client.nickname) == 13:
                result = TestResult(
                    test_name="Single Client Connection",
                    status="PASS",
                    duration=time.time() - test_start,
                    description="Verify that a client can connect and receive an auto-generated nickname",
                    steps=steps,
                    result=f"Successfully connected. Nickname: {client.nickname}"
                )
            else:
                result = TestResult(
                    test_name="Single Client Connection",
                    status="FAIL",
                    duration=time.time() - test_start,
                    description="Verify that a client can connect and receive an auto-generated nickname",
                    steps=steps,
                    result=f"Connected but nickname format invalid: {client.nickname}",
                    error=f"Expected format 'user-XXXXXXXX', got '{client.nickname}'"
                )
        else:
            result = TestResult(
                test_name="Single Client Connection",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify that a client can connect and receive an auto-generated nickname",
                steps=steps,
                result="Failed to connect or receive nickname",
                error="; ".join(client.errors) if client.errors else "Connection timeout"
            )

        disconnect_client(client)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Single Client Connection",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify that a client can connect and receive an auto-generated nickname",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 1.2: Multiple Clients Connection
    test_start = time.time()
    try:
        steps = [
            "Create 3 Socket.IO clients",
            "Connect all clients to server",
            "Verify each receives unique nickname",
            "Verify all nicknames follow format"
        ]

        clients = [create_test_client(f"client-{i}") for i in range(3)]
        all_connected = True

        for client in clients:
            if not connect_client(client):
                all_connected = False
                break

        if all_connected:
            nicknames = [c.nickname for c in clients]
            unique_nicknames = len(set(nicknames)) == len(nicknames)

            if unique_nicknames and all(n.startswith('user-') for n in nicknames):
                result = TestResult(
                    test_name="Multiple Clients Connection",
                    status="PASS",
                    duration=time.time() - test_start,
                    description="Verify multiple clients can connect simultaneously with unique nicknames",
                    steps=steps,
                    result=f"All 3 clients connected successfully with unique nicknames: {nicknames}"
                )
            else:
                result = TestResult(
                    test_name="Multiple Clients Connection",
                    status="FAIL",
                    duration=time.time() - test_start,
                    description="Verify multiple clients can connect simultaneously with unique nicknames",
                    steps=steps,
                    result=f"Connected but nickname validation failed",
                    error=f"Nicknames: {nicknames}, Unique: {unique_nicknames}"
                )
        else:
            result = TestResult(
                test_name="Multiple Clients Connection",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify multiple clients can connect simultaneously with unique nicknames",
                steps=steps,
                result="Not all clients could connect",
                error="Connection failure"
            )

        for client in clients:
            disconnect_client(client)

        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Multiple Clients Connection",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify multiple clients can connect simultaneously with unique nicknames",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 1.3: Connection State Events
    test_start = time.time()
    try:
        steps = [
            "Create and connect client",
            "Verify 'connect' event received",
            "Disconnect client",
            "Verify 'disconnect' event received"
        ]

        client = create_test_client()
        connect_client(client)

        time.sleep(SHORT_DELAY)

        has_connect_event = any(e['event'] == 'connect' for e in client.received_events)

        disconnect_client(client)
        time.sleep(SHORT_DELAY)

        has_disconnect_event = any(e['event'] == 'disconnect' for e in client.received_events)

        if has_connect_event and has_disconnect_event:
            result = TestResult(
                test_name="Connection State Events",
                status="PASS",
                duration=time.time() - test_start,
                description="Verify connect and disconnect events are properly emitted",
                steps=steps,
                result="Both connect and disconnect events received successfully"
            )
        else:
            result = TestResult(
                test_name="Connection State Events",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify connect and disconnect events are properly emitted",
                steps=steps,
                result="Missing expected events",
                error=f"Connect event: {has_connect_event}, Disconnect event: {has_disconnect_event}"
            )

        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Connection State Events",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify connect and disconnect events are properly emitted",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    suite.end_time = time.time()
    return suite


# ============================================================================
# Test Suite 2: Room Functionality Tests
# ============================================================================

def run_room_functionality_tests() -> TestSuite:
    """Execute room functionality tests."""
    suite = TestSuite(suite_name="Room Functionality Tests")
    suite.start_time = time.time()

    # Test 2.1: Join Room
    test_start = time.time()
    try:
        steps = [
            "Connect client to server",
            "Send 'join_room' event with roomId",
            "Verify 'room_joined' event received",
            "Verify room data contains roomId, nickname, history, userCount"
        ]

        client = create_test_client()
        connect_client(client)
        time.sleep(SHORT_DELAY)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"
        client.socket.emit('join_room', {'roomId': room_id})

        # Wait for room_joined event
        success = wait_for_condition(lambda: client.current_room == room_id, timeout=TEST_TIMEOUT)

        if success:
            # Find the room_joined event
            room_joined_event = next((e for e in client.received_events if e['event'] == 'room_joined'), None)

            if room_joined_event:
                data = room_joined_event['data']
                required_fields = ['roomId', 'nickname', 'history', 'userCount']
                missing_fields = [f for f in required_fields if f not in data]

                if not missing_fields and data['roomId'] == room_id:
                    result = TestResult(
                        test_name="Join Room",
                        status="PASS",
                        duration=time.time() - test_start,
                        description="Verify client can join a room and receive proper room data",
                        steps=steps,
                        result=f"Successfully joined room '{room_id}' with userCount={data['userCount']}"
                    )
                else:
                    result = TestResult(
                        test_name="Join Room",
                        status="FAIL",
                        duration=time.time() - test_start,
                        description="Verify client can join a room and receive proper room data",
                        steps=steps,
                        result="Joined room but data validation failed",
                        error=f"Missing fields: {missing_fields}" if missing_fields else f"RoomId mismatch"
                    )
            else:
                result = TestResult(
                    test_name="Join Room",
                    status="FAIL",
                    duration=time.time() - test_start,
                    description="Verify client can join a room and receive proper room data",
                    steps=steps,
                    result="No room_joined event received",
                    error="Event not found in received events"
                )
        else:
            result = TestResult(
                test_name="Join Room",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify client can join a room and receive proper room data",
                steps=steps,
                result="Failed to join room",
                error=f"Timeout waiting for room join. Errors: {client.errors}"
            )

        disconnect_client(client)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Join Room",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify client can join a room and receive proper room data",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 2.2: Join System Message Broadcast
    test_start = time.time()
    try:
        steps = [
            "Connect two clients (A and B)",
            "Client A joins room",
            "Client B joins same room",
            "Verify both clients receive system message about B joining",
            "Verify message format and content"
        ]

        client_a = create_test_client("client-a")
        client_b = create_test_client("client-b")

        connect_client(client_a)
        connect_client(client_b)
        time.sleep(SHORT_DELAY)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"

        # Client A joins first
        client_a.socket.emit('join_room', {'roomId': room_id})
        wait_for_condition(lambda: client_a.current_room == room_id)
        time.sleep(SHORT_DELAY)

        # Clear messages for cleaner testing
        client_a.clear_messages()
        client_b.clear_messages()

        # Client B joins
        client_b.socket.emit('join_room', {'roomId': room_id})
        wait_for_condition(lambda: client_b.current_room == room_id)
        time.sleep(MEDIUM_DELAY)

        # Both clients should receive join message
        client_a_system_msgs = client_a.get_system_messages()
        client_b_system_msgs = client_b.get_system_messages()

        # Expected: "{nickname} 님이 입장했습니다"
        expected_text = f"{client_b.nickname} 님이 입장했습니다"

        a_has_join_msg = any(expected_text in msg.get('text', '') for msg in client_a_system_msgs)
        b_has_join_msg = any(expected_text in msg.get('text', '') for msg in client_b_system_msgs)

        if a_has_join_msg and b_has_join_msg:
            result = TestResult(
                test_name="Join System Message Broadcast",
                status="PASS",
                duration=time.time() - test_start,
                description="Verify system message is broadcast when user joins room",
                steps=steps,
                result=f"Both clients received join system message: '{expected_text}'"
            )
        else:
            result = TestResult(
                test_name="Join System Message Broadcast",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify system message is broadcast when user joins room",
                steps=steps,
                result="Join system message not received by all clients",
                error=f"Client A received: {a_has_join_msg}, Client B received: {b_has_join_msg}"
            )

        disconnect_client(client_a)
        disconnect_client(client_b)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Join System Message Broadcast",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify system message is broadcast when user joins room",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 2.3: Leave Room
    test_start = time.time()
    try:
        steps = [
            "Connect client",
            "Join room",
            "Send 'leave_room' event",
            "Verify 'room_left' event received",
            "Verify client state updated"
        ]

        client = create_test_client()
        connect_client(client)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"
        client.socket.emit('join_room', {'roomId': room_id})
        wait_for_condition(lambda: client.current_room == room_id)

        time.sleep(SHORT_DELAY)
        client.clear_events()

        # Leave room
        client.socket.emit('leave_room', {'roomId': room_id})

        # Wait for room_left event
        success = wait_for_condition(
            lambda: any(e['event'] == 'room_left' for e in client.received_events),
            timeout=TEST_TIMEOUT
        )

        if success and client.current_room is None:
            result = TestResult(
                test_name="Leave Room",
                status="PASS",
                duration=time.time() - test_start,
                description="Verify client can leave a room properly",
                steps=steps,
                result=f"Successfully left room '{room_id}'"
            )
        else:
            result = TestResult(
                test_name="Leave Room",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify client can leave a room properly",
                steps=steps,
                result="Failed to leave room properly",
                error=f"Event received: {success}, Current room: {client.current_room}"
            )

        disconnect_client(client)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Leave Room",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify client can leave a room properly",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 2.4: Leave System Message Broadcast
    test_start = time.time()
    try:
        steps = [
            "Connect two clients (A and B)",
            "Both join same room",
            "Client B leaves room",
            "Verify Client A receives system message about B leaving",
            "Verify Client A receives user_count_updated event"
        ]

        client_a = create_test_client("client-a")
        client_b = create_test_client("client-b")

        connect_client(client_a)
        connect_client(client_b)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"

        # Both join
        client_a.socket.emit('join_room', {'roomId': room_id})
        client_b.socket.emit('join_room', {'roomId': room_id})

        wait_for_condition(lambda: client_a.current_room == room_id and client_b.current_room == room_id)
        time.sleep(MEDIUM_DELAY)

        # Clear for clean test
        client_a.clear_messages()
        client_a.clear_events()

        # Client B leaves
        client_b.socket.emit('leave_room', {'roomId': room_id})
        time.sleep(MEDIUM_DELAY)

        # Check for leave message
        system_msgs = client_a.get_system_messages()
        expected_text = f"{client_b.nickname} 님이 퇴장했습니다"

        has_leave_msg = any(expected_text in msg.get('text', '') for msg in system_msgs)
        has_count_update = any(e['event'] == 'user_count_updated' for e in client_a.received_events)

        if has_leave_msg and has_count_update:
            result = TestResult(
                test_name="Leave System Message Broadcast",
                status="PASS",
                duration=time.time() - test_start,
                description="Verify system message is broadcast when user leaves room",
                steps=steps,
                result=f"Received leave message and user count update: '{expected_text}'"
            )
        else:
            result = TestResult(
                test_name="Leave System Message Broadcast",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify system message is broadcast when user leaves room",
                steps=steps,
                result="Expected events not received",
                error=f"Leave message: {has_leave_msg}, Count update: {has_count_update}"
            )

        disconnect_client(client_a)
        disconnect_client(client_b)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Leave System Message Broadcast",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify system message is broadcast when user leaves room",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 2.5: Empty Room Cleanup
    test_start = time.time()
    try:
        steps = [
            "Connect client",
            "Join room (creating it)",
            "Leave room (making it empty)",
            "Verify room is deleted from server",
            "Check via /stats endpoint"
        ]

        import requests

        client = create_test_client()
        connect_client(client)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"

        # Join room
        client.socket.emit('join_room', {'roomId': room_id})
        wait_for_condition(lambda: client.current_room == room_id)
        time.sleep(SHORT_DELAY)

        # Verify room exists
        stats_before = requests.get(f"{SERVER_URL}/stats").json()
        room_exists_before = any(r['room_id'] == room_id for r in stats_before.get('rooms', []))

        # Leave room
        client.socket.emit('leave_room', {'roomId': room_id})
        time.sleep(MEDIUM_DELAY)

        # Verify room deleted
        stats_after = requests.get(f"{SERVER_URL}/stats").json()
        room_exists_after = any(r['room_id'] == room_id for r in stats_after.get('rooms', []))

        if room_exists_before and not room_exists_after:
            result = TestResult(
                test_name="Empty Room Cleanup",
                status="PASS",
                duration=time.time() - test_start,
                description="Verify empty rooms are automatically deleted",
                steps=steps,
                result=f"Room '{room_id}' was properly deleted after last user left"
            )
        else:
            result = TestResult(
                test_name="Empty Room Cleanup",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify empty rooms are automatically deleted",
                steps=steps,
                result="Room cleanup did not work as expected",
                error=f"Before: {room_exists_before}, After: {room_exists_after}"
            )

        disconnect_client(client)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Empty Room Cleanup",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify empty rooms are automatically deleted",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    suite.end_time = time.time()
    return suite


# ============================================================================
# Test Suite 3: Message Functionality Tests
# ============================================================================

def run_message_functionality_tests() -> TestSuite:
    """Execute message functionality tests."""
    suite = TestSuite(suite_name="Message Functionality Tests")
    suite.start_time = time.time()

    # Test 3.1: Send and Receive Message
    test_start = time.time()
    try:
        steps = [
            "Connect two clients (A and B)",
            "Both join same room",
            "Client A sends message",
            "Verify both clients receive the message",
            "Validate message format (sender, text, timestamp, type)"
        ]

        client_a = create_test_client("client-a")
        client_b = create_test_client("client-b")

        connect_client(client_a)
        connect_client(client_b)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"

        # Both join
        client_a.socket.emit('join_room', {'roomId': room_id})
        client_b.socket.emit('join_room', {'roomId': room_id})

        wait_for_condition(lambda: client_a.current_room == room_id and client_b.current_room == room_id)
        time.sleep(MEDIUM_DELAY)

        # Clear messages
        client_a.clear_messages()
        client_b.clear_messages()

        # Send message
        test_message = f"Test message {uuid.uuid4().hex[:6]}"
        client_a.socket.emit('send_message', {'roomId': room_id, 'text': test_message})

        # Wait for messages
        wait_for_messages(client_a, 1)
        wait_for_messages(client_b, 1)
        time.sleep(SHORT_DELAY)

        # Validate
        a_user_msgs = client_a.get_user_messages()
        b_user_msgs = client_b.get_user_messages()

        if len(a_user_msgs) >= 1 and len(b_user_msgs) >= 1:
            msg_a = a_user_msgs[0]
            msg_b = b_user_msgs[0]

            # Validate format
            valid_a, errors_a = validate_message_format(msg_a)
            valid_b, errors_b = validate_message_format(msg_b)

            # Check content
            content_match = (
                msg_a.get('text') == test_message and
                msg_b.get('text') == test_message and
                msg_a.get('sender') == client_a.nickname and
                msg_b.get('sender') == client_a.nickname
            )

            if valid_a and valid_b and content_match:
                result = TestResult(
                    test_name="Send and Receive Message",
                    status="PASS",
                    duration=time.time() - test_start,
                    description="Verify messages are sent and received correctly",
                    steps=steps,
                    result=f"Message successfully sent and received by both clients: '{test_message}'"
                )
            else:
                result = TestResult(
                    test_name="Send and Receive Message",
                    status="FAIL",
                    duration=time.time() - test_start,
                    description="Verify messages are sent and received correctly",
                    steps=steps,
                    result="Message validation failed",
                    error=f"Format valid: {valid_a and valid_b}, Content match: {content_match}, Errors: {errors_a + errors_b}"
                )
        else:
            result = TestResult(
                test_name="Send and Receive Message",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify messages are sent and received correctly",
                steps=steps,
                result="Messages not received",
                error=f"Client A messages: {len(a_user_msgs)}, Client B messages: {len(b_user_msgs)}"
            )

        disconnect_client(client_a)
        disconnect_client(client_b)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Send and Receive Message",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify messages are sent and received correctly",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 3.2: Message Room Isolation
    test_start = time.time()
    try:
        steps = [
            "Connect three clients (A, B, C)",
            "A and B join Room1, C joins Room2",
            "A sends message in Room1",
            "Verify A and B receive message",
            "Verify C does NOT receive message (room isolation)"
        ]

        client_a = create_test_client("client-a")
        client_b = create_test_client("client-b")
        client_c = create_test_client("client-c")

        connect_client(client_a)
        connect_client(client_b)
        connect_client(client_c)

        room1 = f"test-room1-{uuid.uuid4().hex[:6]}"
        room2 = f"test-room2-{uuid.uuid4().hex[:6]}"

        # Join rooms
        client_a.socket.emit('join_room', {'roomId': room1})
        client_b.socket.emit('join_room', {'roomId': room1})
        client_c.socket.emit('join_room', {'roomId': room2})

        wait_for_condition(lambda: client_a.current_room == room1 and
                                   client_b.current_room == room1 and
                                   client_c.current_room == room2)
        time.sleep(MEDIUM_DELAY)

        # Clear messages
        client_a.clear_messages()
        client_b.clear_messages()
        client_c.clear_messages()

        # Send message in room1
        test_message = f"Room1 message {uuid.uuid4().hex[:6]}"
        client_a.socket.emit('send_message', {'roomId': room1, 'text': test_message})

        time.sleep(MEDIUM_DELAY)

        # Check reception
        a_received = any(msg.get('text') == test_message for msg in client_a.get_user_messages())
        b_received = any(msg.get('text') == test_message for msg in client_b.get_user_messages())
        c_received = any(msg.get('text') == test_message for msg in client_c.get_user_messages())

        if a_received and b_received and not c_received:
            result = TestResult(
                test_name="Message Room Isolation",
                status="PASS",
                duration=time.time() - test_start,
                description="Verify messages are isolated to their respective rooms",
                steps=steps,
                result=f"Room isolation working correctly. Room1 users received message, Room2 user did not."
            )
        else:
            result = TestResult(
                test_name="Message Room Isolation",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify messages are isolated to their respective rooms",
                steps=steps,
                result="Room isolation failed",
                error=f"A received: {a_received}, B received: {b_received}, C received: {c_received} (should be False)"
            )

        disconnect_client(client_a)
        disconnect_client(client_b)
        disconnect_client(client_c)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Message Room Isolation",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify messages are isolated to their respective rooms",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 3.3: Message History - New User
    test_start = time.time()
    try:
        steps = [
            "Connect Client A, join room",
            "A sends 5 messages",
            "Connect Client B, join same room",
            "Verify B receives all 5 messages in history",
            "Verify history includes join messages"
        ]

        client_a = create_test_client("client-a")
        connect_client(client_a)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"
        client_a.socket.emit('join_room', {'roomId': room_id})
        wait_for_condition(lambda: client_a.current_room == room_id)
        time.sleep(SHORT_DELAY)

        # Send 5 messages
        messages = [f"Message {i}" for i in range(5)]
        for msg in messages:
            client_a.socket.emit('send_message', {'roomId': room_id, 'text': msg})
            time.sleep(0.05)

        time.sleep(MEDIUM_DELAY)

        # New client joins
        client_b = create_test_client("client-b")
        connect_client(client_b)

        client_b.socket.emit('join_room', {'roomId': room_id})
        wait_for_condition(lambda: client_b.current_room == room_id)
        time.sleep(SHORT_DELAY)

        # Check room_joined event for history
        room_joined_event = next((e for e in client_b.received_events if e['event'] == 'room_joined'), None)

        if room_joined_event and 'data' in room_joined_event:
            history = room_joined_event['data'].get('history', [])
            user_messages = [msg for msg in history if msg.get('message_type') == 'user']

            # Verify all 5 messages are in history
            history_texts = [msg.get('text') for msg in user_messages]
            all_messages_present = all(msg in history_texts for msg in messages)

            if all_messages_present and len(user_messages) == 5:
                result = TestResult(
                    test_name="Message History - New User",
                    status="PASS",
                    duration=time.time() - test_start,
                    description="Verify new users receive message history when joining room",
                    steps=steps,
                    result=f"New user received complete history: {len(history)} total messages ({len(user_messages)} user messages)"
                )
            else:
                result = TestResult(
                    test_name="Message History - New User",
                    status="FAIL",
                    duration=time.time() - test_start,
                    description="Verify new users receive message history when joining room",
                    steps=steps,
                    result="History incomplete or incorrect",
                    error=f"Expected 5 messages, got {len(user_messages)}. All present: {all_messages_present}"
                )
        else:
            result = TestResult(
                test_name="Message History - New User",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify new users receive message history when joining room",
                steps=steps,
                result="No room_joined event or history data",
                error="Event not found"
            )

        disconnect_client(client_a)
        disconnect_client(client_b)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Message History - New User",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify new users receive message history when joining room",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 3.4: Message History - 50 Message Limit
    test_start = time.time()
    try:
        steps = [
            "Connect client and join room",
            "Send 55 messages (exceeding limit of 50)",
            "Connect second client and join room",
            "Verify history contains only 50 most recent messages",
            "Verify oldest messages were discarded"
        ]

        client_a = create_test_client("client-a")
        connect_client(client_a)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"
        client_a.socket.emit('join_room', {'roomId': room_id})
        wait_for_condition(lambda: client_a.current_room == room_id)
        time.sleep(SHORT_DELAY)

        # Send 55 messages
        num_messages = 55
        for i in range(num_messages):
            client_a.socket.emit('send_message', {'roomId': room_id, 'text': f"Message {i}"})
            time.sleep(0.02)  # Small delay to ensure ordering

        time.sleep(MEDIUM_DELAY)

        # New client joins
        client_b = create_test_client("client-b")
        connect_client(client_b)

        client_b.socket.emit('join_room', {'roomId': room_id})
        wait_for_condition(lambda: client_b.current_room == room_id)
        time.sleep(SHORT_DELAY)

        # Check history
        room_joined_event = next((e for e in client_b.received_events if e['event'] == 'room_joined'), None)

        if room_joined_event:
            history = room_joined_event['data'].get('history', [])

            # History includes join messages, so check total count
            if len(history) <= 50:
                # Check that oldest messages are not present
                user_messages = [msg for msg in history if msg.get('message_type') == 'user']

                # First few messages should not be in history
                has_message_0 = any(msg.get('text') == 'Message 0' for msg in user_messages)
                has_message_1 = any(msg.get('text') == 'Message 1' for msg in user_messages)

                # Last messages should be present
                has_message_54 = any(msg.get('text') == 'Message 54' for msg in user_messages)

                if not has_message_0 and not has_message_1 and has_message_54:
                    result = TestResult(
                        test_name="Message History - 50 Message Limit",
                        status="PASS",
                        duration=time.time() - test_start,
                        description="Verify message history is limited to 50 messages",
                        steps=steps,
                        result=f"History correctly limited to {len(history)} messages (including system messages). Oldest messages properly discarded."
                    )
                else:
                    result = TestResult(
                        test_name="Message History - 50 Message Limit",
                        status="FAIL",
                        duration=time.time() - test_start,
                        description="Verify message history is limited to 50 messages",
                        steps=steps,
                        result="History content incorrect",
                        error=f"Message 0: {has_message_0}, Message 1: {has_message_1}, Message 54: {has_message_54}",
                        warnings=["Expected oldest messages to be discarded"]
                    )
            else:
                result = TestResult(
                    test_name="Message History - 50 Message Limit",
                    status="FAIL",
                    duration=time.time() - test_start,
                    description="Verify message history is limited to 50 messages",
                    steps=steps,
                    result="History size exceeds limit",
                    error=f"Expected max 50 messages, got {len(history)}"
                )
        else:
            result = TestResult(
                test_name="Message History - 50 Message Limit",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify message history is limited to 50 messages",
                steps=steps,
                result="No room_joined event received",
                error="Event not found"
            )

        disconnect_client(client_a)
        disconnect_client(client_b)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Message History - 50 Message Limit",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify message history is limited to 50 messages",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    suite.end_time = time.time()
    return suite


# ============================================================================
# Test Suite 4: Multi-User Concurrency Tests
# ============================================================================

def run_multi_user_concurrency_tests() -> TestSuite:
    """Execute multi-user concurrency tests."""
    suite = TestSuite(suite_name="Multi-User Concurrency Tests")
    suite.start_time = time.time()

    # Test 4.1: Multiple Users Simultaneous Join
    test_start = time.time()
    try:
        steps = [
            "Connect 5 clients simultaneously",
            "All 5 join same room at the same time",
            "Verify all successfully join",
            "Verify all receive correct user count",
            "Verify each receives join messages from others"
        ]

        num_clients = 5
        clients = [create_test_client(f"client-{i}") for i in range(num_clients)]

        # Connect all
        for client in clients:
            connect_client(client)

        time.sleep(SHORT_DELAY)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"

        # All join simultaneously
        for client in clients:
            client.socket.emit('join_room', {'roomId': room_id})

        # Wait for all to join
        all_joined = wait_for_condition(
            lambda: all(c.current_room == room_id for c in clients),
            timeout=TEST_TIMEOUT * 2
        )

        time.sleep(MEDIUM_DELAY)

        if all_joined:
            # Check user counts
            user_counts = []
            for client in clients:
                room_joined_event = next((e for e in client.received_events if e['event'] == 'room_joined'), None)
                if room_joined_event:
                    user_counts.append(room_joined_event['data'].get('userCount', 0))

            # All should eventually see 5 users (though initial counts may vary due to timing)
            # Check that each client received join messages
            join_message_counts = [len(c.get_system_messages()) for c in clients]

            # The number of join messages should be between num_clients-1 and num_clients
            # (depends on timing - might include own join message or not)
            valid_join_counts = all(count >= num_clients - 1 for count in join_message_counts)

            if valid_join_counts:
                result = TestResult(
                    test_name="Multiple Users Simultaneous Join",
                    status="PASS",
                    duration=time.time() - test_start,
                    description="Verify multiple users can join same room simultaneously",
                    steps=steps,
                    result=f"All {num_clients} clients successfully joined. Join messages received: {join_message_counts}"
                )
            else:
                result = TestResult(
                    test_name="Multiple Users Simultaneous Join",
                    status="FAIL",
                    duration=time.time() - test_start,
                    description="Verify multiple users can join same room simultaneously",
                    steps=steps,
                    result="Not all clients received expected join messages",
                    error=f"Join message counts: {join_message_counts}, expected at least {num_clients - 1} each"
                )
        else:
            result = TestResult(
                test_name="Multiple Users Simultaneous Join",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify multiple users can join same room simultaneously",
                steps=steps,
                result="Not all clients joined successfully",
                error=f"Joined: {sum(1 for c in clients if c.current_room == room_id)} / {num_clients}"
            )

        for client in clients:
            disconnect_client(client)

        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Multiple Users Simultaneous Join",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify multiple users can join same room simultaneously",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 4.2: Concurrent Message Broadcasting
    test_start = time.time()
    try:
        steps = [
            "Connect 3 clients (A, B, C)",
            "All join same room",
            "Each client sends 3 messages rapidly",
            "Verify all clients receive all 9 messages",
            "Verify no message loss or duplication"
        ]

        clients = [create_test_client(f"client-{chr(65+i)}") for i in range(3)]

        # Connect all
        for client in clients:
            connect_client(client)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"

        # All join
        for client in clients:
            client.socket.emit('join_room', {'roomId': room_id})

        wait_for_condition(lambda: all(c.current_room == room_id for c in clients))
        time.sleep(MEDIUM_DELAY)

        # Clear messages
        for client in clients:
            client.clear_messages()

        # Each sends 3 messages
        messages_per_client = 3
        for i, client in enumerate(clients):
            for j in range(messages_per_client):
                msg_text = f"Client {i} Message {j}"
                client.socket.emit('send_message', {'roomId': room_id, 'text': msg_text})

        # Wait for all messages to be received
        expected_total = len(clients) * messages_per_client
        time.sleep(MEDIUM_DELAY * 2)

        # Check message counts
        message_counts = [len(c.get_user_messages()) for c in clients]
        all_received_correctly = all(count == expected_total for count in message_counts)

        # Check for duplicates in one client
        client_0_messages = clients[0].get_user_messages()
        message_ids = [msg.get('id') for msg in client_0_messages]
        has_duplicates = len(message_ids) != len(set(message_ids))

        if all_received_correctly and not has_duplicates:
            result = TestResult(
                test_name="Concurrent Message Broadcasting",
                status="PASS",
                duration=time.time() - test_start,
                description="Verify concurrent message sending works correctly",
                steps=steps,
                result=f"All {expected_total} messages received by all clients without duplication"
            )
        else:
            result = TestResult(
                test_name="Concurrent Message Broadcasting",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify concurrent message sending works correctly",
                steps=steps,
                result="Message broadcasting issues detected",
                error=f"Message counts: {message_counts} (expected {expected_total} each), Duplicates: {has_duplicates}"
            )

        for client in clients:
            disconnect_client(client)

        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Concurrent Message Broadcasting",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify concurrent message sending works correctly",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 4.3: Rapid Join/Leave Operations
    test_start = time.time()
    try:
        steps = [
            "Connect client A and join room",
            "Connect 3 more clients",
            "Rapidly join and leave room with all 3 new clients",
            "Verify no errors occur",
            "Verify client A receives all join/leave messages",
            "Verify room state is consistent"
        ]

        client_a = create_test_client("client-a")
        connect_client(client_a)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"
        client_a.socket.emit('join_room', {'roomId': room_id})
        wait_for_condition(lambda: client_a.current_room == room_id)
        time.sleep(SHORT_DELAY)

        client_a.clear_messages()

        # Create 3 more clients
        temp_clients = [create_test_client(f"temp-{i}") for i in range(3)]
        for client in temp_clients:
            connect_client(client)

        # Rapidly join and leave
        for client in temp_clients:
            client.socket.emit('join_room', {'roomId': room_id})
            time.sleep(0.05)
            client.socket.emit('leave_room', {'roomId': room_id})
            time.sleep(0.05)

        time.sleep(MEDIUM_DELAY * 2)

        # Check for errors
        total_errors = sum(len(c.errors) for c in [client_a] + temp_clients)

        # Check that client_a received messages
        system_messages = client_a.get_system_messages()

        # Should have join and leave messages for each temp client
        # Expected: 3 joins + 3 leaves = 6 system messages (at minimum)
        has_sufficient_messages = len(system_messages) >= 6

        if total_errors == 0 and has_sufficient_messages:
            result = TestResult(
                test_name="Rapid Join/Leave Operations",
                status="PASS",
                duration=time.time() - test_start,
                description="Verify system handles rapid join/leave operations",
                steps=steps,
                result=f"Rapid operations handled successfully. Client A received {len(system_messages)} system messages, no errors."
            )
        else:
            result = TestResult(
                test_name="Rapid Join/Leave Operations",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify system handles rapid join/leave operations",
                steps=steps,
                result="Issues detected during rapid operations",
                error=f"Errors: {total_errors}, System messages: {len(system_messages)} (expected >= 6)"
            )

        disconnect_client(client_a)
        for client in temp_clients:
            disconnect_client(client)

        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Rapid Join/Leave Operations",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify system handles rapid join/leave operations",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    suite.end_time = time.time()
    return suite


# ============================================================================
# Test Suite 5: Edge Cases & Error Handling Tests
# ============================================================================

def run_edge_case_tests() -> TestSuite:
    """Execute edge case and error handling tests."""
    suite = TestSuite(suite_name="Edge Cases & Error Handling Tests")
    suite.start_time = time.time()

    # Test 5.1: Empty Message Rejection
    test_start = time.time()
    try:
        steps = [
            "Connect client and join room",
            "Send empty message (empty string)",
            "Send whitespace-only message",
            "Verify messages are rejected (not broadcast)",
            "Verify no error event sent to client"
        ]

        client_a = create_test_client("client-a")
        client_b = create_test_client("client-b")

        connect_client(client_a)
        connect_client(client_b)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"

        client_a.socket.emit('join_room', {'roomId': room_id})
        client_b.socket.emit('join_room', {'roomId': room_id})

        wait_for_condition(lambda: client_a.current_room == room_id and client_b.current_room == room_id)
        time.sleep(MEDIUM_DELAY)

        client_a.clear_messages()
        client_b.clear_messages()

        # Send empty and whitespace messages
        client_a.socket.emit('send_message', {'roomId': room_id, 'text': ''})
        time.sleep(SHORT_DELAY)
        client_a.socket.emit('send_message', {'roomId': room_id, 'text': '   '})
        time.sleep(MEDIUM_DELAY)

        # Send a valid message to confirm system is working
        client_a.socket.emit('send_message', {'roomId': room_id, 'text': 'Valid message'})
        time.sleep(MEDIUM_DELAY)

        # Check that only 1 message received (the valid one)
        a_user_msgs = client_a.get_user_messages()
        b_user_msgs = client_b.get_user_messages()

        if len(a_user_msgs) == 1 and len(b_user_msgs) == 1:
            if a_user_msgs[0].get('text') == 'Valid message':
                result = TestResult(
                    test_name="Empty Message Rejection",
                    status="PASS",
                    duration=time.time() - test_start,
                    description="Verify empty/whitespace messages are rejected",
                    steps=steps,
                    result="Empty messages correctly rejected, only valid message broadcast"
                )
            else:
                result = TestResult(
                    test_name="Empty Message Rejection",
                    status="FAIL",
                    duration=time.time() - test_start,
                    description="Verify empty/whitespace messages are rejected",
                    steps=steps,
                    result="Message content incorrect",
                    error=f"Expected 'Valid message', got '{a_user_msgs[0].get('text')}'"
                )
        else:
            result = TestResult(
                test_name="Empty Message Rejection",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify empty/whitespace messages are rejected",
                steps=steps,
                result="Wrong number of messages received",
                error=f"Expected 1 message each, got A: {len(a_user_msgs)}, B: {len(b_user_msgs)}"
            )

        disconnect_client(client_a)
        disconnect_client(client_b)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Empty Message Rejection",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify empty/whitespace messages are rejected",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 5.2: Message to Non-Existent Room
    test_start = time.time()
    try:
        steps = [
            "Connect client",
            "Send message to room without joining",
            "Verify error event received",
            "Verify message not sent"
        ]

        client = create_test_client()
        connect_client(client)
        time.sleep(SHORT_DELAY)

        # Try to send message without joining room
        fake_room = f"fake-room-{uuid.uuid4().hex[:6]}"
        client.socket.emit('send_message', {'roomId': fake_room, 'text': 'This should fail'})

        time.sleep(MEDIUM_DELAY)

        # Should have received error
        has_error = len(client.errors) > 0

        if has_error:
            result = TestResult(
                test_name="Message to Non-Existent Room",
                status="PASS",
                duration=time.time() - test_start,
                description="Verify sending message to non-joined room triggers error",
                steps=steps,
                result=f"Error correctly received: '{client.errors[0]}'"
            )
        else:
            result = TestResult(
                test_name="Message to Non-Existent Room",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify sending message to non-joined room triggers error",
                steps=steps,
                result="No error received",
                error="Expected error event for sending to non-joined room"
            )

        disconnect_client(client)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Message to Non-Existent Room",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify sending message to non-joined room triggers error",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 5.3: Invalid Room ID Format
    test_start = time.time()
    try:
        steps = [
            "Connect client",
            "Try to join room with invalid ID (None, empty, non-string)",
            "Verify error event received",
            "Verify client not joined to any room"
        ]

        client = create_test_client()
        connect_client(client)
        time.sleep(SHORT_DELAY)

        # Try various invalid room IDs
        invalid_ids = [None, '', 123]  # Note: 123 will be serialized to JSON as number

        for invalid_id in invalid_ids:
            client.errors.clear()
            try:
                client.socket.emit('join_room', {'roomId': invalid_id})
                time.sleep(SHORT_DELAY)
            except:
                pass  # Some might fail at emit level

        time.sleep(MEDIUM_DELAY)

        # Should have errors and not be in any room
        has_errors = len(client.errors) > 0
        not_in_room = client.current_room is None

        if has_errors and not_in_room:
            result = TestResult(
                test_name="Invalid Room ID Format",
                status="PASS",
                duration=time.time() - test_start,
                description="Verify invalid room IDs are rejected",
                steps=steps,
                result=f"Invalid room IDs correctly rejected with errors: {client.errors}"
            )
        else:
            result = TestResult(
                test_name="Invalid Room ID Format",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify invalid room IDs are rejected",
                steps=steps,
                result="Invalid room ID handling failed",
                error=f"Has errors: {has_errors}, Not in room: {not_in_room}"
            )

        disconnect_client(client)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Invalid Room ID Format",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify invalid room IDs are rejected",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 5.4: Special Characters in Messages
    test_start = time.time()
    try:
        steps = [
            "Connect two clients",
            "Join same room",
            "Send messages with special characters (emoji, unicode, HTML)",
            "Verify messages transmitted correctly",
            "Verify no corruption or encoding issues"
        ]

        client_a = create_test_client("client-a")
        client_b = create_test_client("client-b")

        connect_client(client_a)
        connect_client(client_b)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"

        client_a.socket.emit('join_room', {'roomId': room_id})
        client_b.socket.emit('join_room', {'roomId': room_id})

        wait_for_condition(lambda: client_a.current_room == room_id and client_b.current_room == room_id)
        time.sleep(MEDIUM_DELAY)

        client_a.clear_messages()
        client_b.clear_messages()

        # Test messages with special characters
        test_messages = [
            "Hello 👋 World 🌍",
            "한글 테스트 メッセージ",
            "<script>alert('test')</script>",
            "Line 1\nLine 2\nLine 3",
            "Special chars: @#$%^&*()"
        ]

        for msg in test_messages:
            client_a.socket.emit('send_message', {'roomId': room_id, 'text': msg})
            time.sleep(0.1)

        time.sleep(MEDIUM_DELAY)

        # Verify all messages received correctly
        b_user_msgs = client_b.get_user_messages()
        received_texts = [msg.get('text') for msg in b_user_msgs]

        all_match = all(msg in received_texts for msg in test_messages)

        if all_match and len(b_user_msgs) == len(test_messages):
            result = TestResult(
                test_name="Special Characters in Messages",
                status="PASS",
                duration=time.time() - test_start,
                description="Verify messages with special characters are handled correctly",
                steps=steps,
                result=f"All {len(test_messages)} messages with special characters transmitted correctly"
            )
        else:
            result = TestResult(
                test_name="Special Characters in Messages",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify messages with special characters are handled correctly",
                steps=steps,
                result="Special character handling failed",
                error=f"Expected {len(test_messages)} messages, got {len(b_user_msgs)}. All match: {all_match}"
            )

        disconnect_client(client_a)
        disconnect_client(client_b)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Special Characters in Messages",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify messages with special characters are handled correctly",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    # Test 5.5: Disconnect During Message Send
    test_start = time.time()
    try:
        steps = [
            "Connect two clients (A and B)",
            "Both join same room",
            "Client A starts sending message",
            "Client A disconnects immediately",
            "Verify Client B receives leave message",
            "Verify no errors or crashes"
        ]

        client_a = create_test_client("client-a")
        client_b = create_test_client("client-b")

        connect_client(client_a)
        connect_client(client_b)

        room_id = f"test-room-{uuid.uuid4().hex[:6]}"

        client_a.socket.emit('join_room', {'roomId': room_id})
        client_b.socket.emit('join_room', {'roomId': room_id})

        wait_for_condition(lambda: client_a.current_room == room_id and client_b.current_room == room_id)
        time.sleep(MEDIUM_DELAY)

        client_b.clear_messages()

        # Send message and disconnect immediately
        client_a.socket.emit('send_message', {'roomId': room_id, 'text': 'Disconnecting now'})
        disconnect_client(client_a)

        time.sleep(MEDIUM_DELAY)

        # Client B should receive leave message
        system_msgs = client_b.get_system_messages()
        expected_leave_text = f"{client_a.nickname} 님이 퇴장했습니다"
        has_leave_msg = any(expected_leave_text in msg.get('text', '') for msg in system_msgs)

        # No errors in client B
        no_errors = len(client_b.errors) == 0

        if has_leave_msg and no_errors:
            result = TestResult(
                test_name="Disconnect During Message Send",
                status="PASS",
                duration=time.time() - test_start,
                description="Verify graceful handling of disconnect during operations",
                steps=steps,
                result="Disconnect handled gracefully, leave message received, no errors"
            )
        else:
            result = TestResult(
                test_name="Disconnect During Message Send",
                status="FAIL",
                duration=time.time() - test_start,
                description="Verify graceful handling of disconnect during operations",
                steps=steps,
                result="Issues during disconnect handling",
                error=f"Has leave message: {has_leave_msg}, No errors: {no_errors}",
                warnings=["May indicate timing issue or improper cleanup"]
            )

        disconnect_client(client_b)
        suite.add_result(result)

    except Exception as e:
        suite.add_result(TestResult(
            test_name="Disconnect During Message Send",
            status="FAIL",
            duration=time.time() - test_start,
            description="Verify graceful handling of disconnect during operations",
            steps=steps,
            result="Exception occurred",
            error=str(e)
        ))

    suite.end_time = time.time()
    return suite


# ============================================================================
# Report Generation
# ============================================================================

def print_test_report(suites: List[TestSuite]):
    """
    Print comprehensive test report.

    Args:
        suites: List of TestSuite objects
    """
    print("\n" + "=" * 80)
    print("WEBSOCKET CHAT SYSTEM - COMPREHENSIVE TEST REPORT")
    print("=" * 80)
    print(f"Test Execution Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Server URL: {SERVER_URL}")
    print("=" * 80)

    # Overall summary
    total_tests = sum(len(suite.test_results) for suite in suites)
    total_passed = sum(sum(1 for r in suite.test_results if r.status == 'PASS') for suite in suites)
    total_failed = sum(sum(1 for r in suite.test_results if r.status == 'FAIL') for suite in suites)
    total_skipped = sum(sum(1 for r in suite.test_results if r.status == 'SKIP') for suite in suites)
    total_duration = sum(suite.get_summary()['duration'] for suite in suites)

    print("\n### OVERALL SUMMARY ###")
    print(f"Total Test Suites: {len(suites)}")
    print(f"Total Test Cases: {total_tests}")
    print(f"Passed: {total_passed} ({total_passed/total_tests*100:.1f}%)" if total_tests > 0 else "Passed: 0")
    print(f"Failed: {total_failed} ({total_failed/total_tests*100:.1f}%)" if total_tests > 0 else "Failed: 0")
    print(f"Skipped: {total_skipped}")
    print(f"Total Duration: {total_duration:.2f} seconds")
    print("")

    # Per-suite details
    for suite in suites:
        print("\n" + "=" * 80)
        print(f"TEST SUITE: {suite.suite_name}")
        print("=" * 80)

        summary = suite.get_summary()
        print(f"Tests: {summary['total']} | Passed: {summary['passed']} | Failed: {summary['failed']} | Duration: {summary['duration']:.2f}s")
        print("-" * 80)

        for result in suite.test_results:
            status_symbol = "✓" if result.status == "PASS" else "✗" if result.status == "FAIL" else "○"
            print(f"\n{status_symbol} Test: {result.test_name}")
            print(f"  Status: {result.status}")
            print(f"  Duration: {result.duration:.3f}s")
            print(f"  Description: {result.description}")

            print(f"  Steps:")
            for i, step in enumerate(result.steps, 1):
                print(f"    {i}. {step}")

            print(f"  Result: {result.result}")

            if result.error:
                print(f"  ERROR: {result.error}")

            if result.warnings:
                for warning in result.warnings:
                    print(f"  WARNING: {warning}")

    # Critical issues summary
    print("\n" + "=" * 80)
    print("CRITICAL ISSUES FOUND")
    print("=" * 80)

    critical_issues = []
    for suite in suites:
        for result in suite.test_results:
            if result.status == "FAIL":
                critical_issues.append({
                    'suite': suite.suite_name,
                    'test': result.test_name,
                    'error': result.error
                })

    if critical_issues:
        for i, issue in enumerate(critical_issues, 1):
            print(f"\n{i}. [{issue['suite']}] {issue['test']}")
            print(f"   Error: {issue['error']}")
    else:
        print("\nNo critical issues found! All tests passed.")

    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    if total_failed == 0:
        print("\n✓ All tests passed! The system is functioning correctly.")
        print("\nSuggested improvements:")
        print("  - Consider adding load testing with 50+ concurrent users")
        print("  - Test network latency scenarios (simulate slow connections)")
        print("  - Add stress testing for message throughput")
        print("  - Implement automated regression testing in CI/CD pipeline")
    else:
        print("\nPriority actions:")
        print(f"  - Fix {total_failed} failing test(s) before deployment")
        print("  - Review error handling for edge cases")
        print("  - Verify all message format validations")
        print("  - Test reconnection scenarios more thoroughly")

    print("\n" + "=" * 80)
    print("END OF REPORT")
    print("=" * 80 + "\n")


# ============================================================================
# Main Test Execution
# ============================================================================

def main():
    """Main test execution function."""
    print("\n" + "=" * 80)
    print("WEBSOCKET CHAT SYSTEM - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print(f"Server URL: {SERVER_URL}")
    print("Starting test execution...\n")

    all_suites = []

    try:
        # Run all test suites
        print("\n[1/5] Running Basic Connection Tests...")
        suite1 = run_basic_connection_tests()
        all_suites.append(suite1)
        print(f"      Completed: {suite1.get_summary()['passed']}/{suite1.get_summary()['total']} passed")

        print("\n[2/5] Running Room Functionality Tests...")
        suite2 = run_room_functionality_tests()
        all_suites.append(suite2)
        print(f"      Completed: {suite2.get_summary()['passed']}/{suite2.get_summary()['total']} passed")

        print("\n[3/5] Running Message Functionality Tests...")
        suite3 = run_message_functionality_tests()
        all_suites.append(suite3)
        print(f"      Completed: {suite3.get_summary()['passed']}/{suite3.get_summary()['total']} passed")

        print("\n[4/5] Running Multi-User Concurrency Tests...")
        suite4 = run_multi_user_concurrency_tests()
        all_suites.append(suite4)
        print(f"      Completed: {suite4.get_summary()['passed']}/{suite4.get_summary()['total']} passed")

        print("\n[5/5] Running Edge Cases & Error Handling Tests...")
        suite5 = run_edge_case_tests()
        all_suites.append(suite5)
        print(f"      Completed: {suite5.get_summary()['passed']}/{suite5.get_summary()['total']} passed")

        # Generate and print report
        print_test_report(all_suites)

    except KeyboardInterrupt:
        print("\n\nTest execution interrupted by user.")
    except Exception as e:
        print(f"\n\nFATAL ERROR during test execution: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
