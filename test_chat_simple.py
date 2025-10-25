"""
Streamlined WebSocket Chat System Test Suite - Focused Testing
"""

import socketio
import time
import requests
import uuid
from datetime import datetime

SERVER_URL = 'http://localhost:8000'

print("=" * 80)
print("WEBSOCKET CHAT SYSTEM - COMPREHENSIVE TEST REPORT")
print("=" * 80)
print(f"Test Execution Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
print(f"Server URL: {SERVER_URL}")
print("=" * 80)

# Test counters
total_tests = 0
passed_tests = 0
failed_tests = 0
test_start_time = time.time()

def print_test_header(test_name):
    print(f"\n{'=' * 80}")
    print(f"Test: {test_name}")
    print('=' * 80)

def print_test_result(status, duration, result, error=None):
    global total_tests, passed_tests, failed_tests
    total_tests += 1
    symbol = "PASS" if status == "PASS" else "✗ FAIL"
    print(f"Status: {symbol}")
    print(f"Duration: {duration:.3f}s")
    print(f"Result: {result}")
    if error:
        print(f"ERROR: {error}")
    if status == "PASS":
        passed_tests += 1
    else:
        failed_tests += 1

try:
    # TEST 1: Basic Connection
    print_test_header("1. Basic Connection Test")
    test_start = time.time()
    try:
        sio = socketio.Client()
        nickname_assigned = []

        @sio.on('nickname_assigned')
        def on_nickname(data):
            nickname_assigned.append(data['nickname'])

        sio.connect(SERVER_URL)
        time.sleep(0.5)

        if sio.connected and len(nickname_assigned) > 0:
            nickname = nickname_assigned[0]
            if nickname.startswith('user-') and len(nickname) == 13:
                print_test_result("PASS", time.time() - test_start,
                                f"Successfully connected. Nickname: {nickname}")
            else:
                print_test_result("FAIL", time.time() - test_start,
                                f"Invalid nickname format: {nickname}",
                                f"Expected format 'user-XXXXXXXX'")
        else:
            print_test_result("FAIL", time.time() - test_start,
                            "Failed to connect or receive nickname",
                            "Connection timeout or no nickname event")

        sio.disconnect()
    except Exception as e:
        print_test_result("FAIL", time.time() - test_start,
                        "Exception occurred", str(e))

    # TEST 2: Join Room
    print_test_header("2. Join Room Test")
    test_start = time.time()
    try:
        sio = socketio.Client()
        room_joined_data = []

        @sio.on('nickname_assigned')
        def on_nickname(data):
            pass

        @sio.on('room_joined')
        def on_room_joined(data):
            room_joined_data.append(data)

        sio.connect(SERVER_URL)
        time.sleep(0.3)

        room_id = f"test-{uuid.uuid4().hex[:6]}"
        sio.emit('join_room', {'roomId': room_id})
        time.sleep(0.5)

        if len(room_joined_data) > 0:
            data = room_joined_data[0]
            if data.get('roomId') == room_id and 'history' in data and 'userCount' in data:
                print_test_result("PASS", time.time() - test_start,
                                f"Successfully joined room '{room_id}' with {data['userCount']} user(s)")
            else:
                print_test_result("FAIL", time.time() - test_start,
                                "Room joined but data incomplete",
                                f"Data: {data}")
        else:
            print_test_result("FAIL", time.time() - test_start,
                            "Did not receive room_joined event",
                            "No response from server")

        sio.disconnect()
    except Exception as e:
        print_test_result("FAIL", time.time() - test_start,
                        "Exception occurred", str(e))

    # TEST 3: Send and Receive Message
    print_test_header("3. Message Send/Receive Test")
    test_start = time.time()
    try:
        # Create two clients
        sio1 = socketio.Client()
        sio2 = socketio.Client()

        messages_1 = []
        messages_2 = []
        nicknames = []

        @sio1.on('nickname_assigned')
        def on_nick1(data):
            nicknames.append(('sio1', data['nickname']))

        @sio2.on('nickname_assigned')
        def on_nick2(data):
            nicknames.append(('sio2', data['nickname']))

        @sio1.on('new_message')
        def on_msg1(msg):
            messages_1.append(msg)

        @sio2.on('new_message')
        def on_msg2(msg):
            messages_2.append(msg)

        # Connect both
        sio1.connect(SERVER_URL)
        sio2.connect(SERVER_URL)
        time.sleep(0.5)

        # Both join same room
        room_id = f"test-{uuid.uuid4().hex[:6]}"
        sio1.emit('join_room', {'roomId': room_id})
        sio2.emit('join_room', {'roomId': room_id})
        time.sleep(0.5)

        # Clear messages
        messages_1.clear()
        messages_2.clear()

        # Send message from client 1
        test_msg = f"Test message {uuid.uuid4().hex[:6]}"
        sio1.emit('send_message', {'roomId': room_id, 'text': test_msg})
        time.sleep(0.5)

        # Count user messages (not system messages)
        user_msgs_1 = [m for m in messages_1 if m.get('message_type') == 'user']
        user_msgs_2 = [m for m in messages_2 if m.get('message_type') == 'user']

        if len(user_msgs_1) >= 1 and len(user_msgs_2) >= 1:
            msg = user_msgs_1[0]
            if msg.get('text') == test_msg and 'timestamp' in msg:
                print_test_result("PASS", time.time() - test_start,
                                f"Message successfully sent and received by both clients: '{test_msg}'")
            else:
                print_test_result("FAIL", time.time() - test_start,
                                "Message content mismatch",
                                f"Expected: '{test_msg}', Got: '{msg.get('text')}'")
        else:
            print_test_result("FAIL", time.time() - test_start,
                            "Messages not received by all clients",
                            f"Client1: {len(user_msgs_1)} messages, Client2: {len(user_msgs_2)} messages")

        sio1.disconnect()
        sio2.disconnect()
    except Exception as e:
        print_test_result("FAIL", time.time() - test_start,
                        "Exception occurred", str(e))

    # TEST 4: Room Isolation
    print_test_header("4. Message Room Isolation Test")
    test_start = time.time()
    try:
        sio_a = socketio.Client()
        sio_b = socketio.Client()
        sio_c = socketio.Client()

        messages_a = []
        messages_b = []
        messages_c = []

        @sio_a.on('nickname_assigned')
        def on_na(data): pass
        @sio_b.on('nickname_assigned')
        def on_nb(data): pass
        @sio_c.on('nickname_assigned')
        def on_nc(data): pass

        @sio_a.on('new_message')
        def on_ma(msg): messages_a.append(msg)
        @sio_b.on('new_message')
        def on_mb(msg): messages_b.append(msg)
        @sio_c.on('new_message')
        def on_mc(msg): messages_c.append(msg)

        # Connect all
        sio_a.connect(SERVER_URL)
        sio_b.connect(SERVER_URL)
        sio_c.connect(SERVER_URL)
        time.sleep(0.5)

        # A and B in room1, C in room2
        room1 = f"room1-{uuid.uuid4().hex[:6]}"
        room2 = f"room2-{uuid.uuid4().hex[:6]}"

        sio_a.emit('join_room', {'roomId': room1})
        sio_b.emit('join_room', {'roomId': room1})
        sio_c.emit('join_room', {'roomId': room2})
        time.sleep(0.5)

        # Clear messages
        messages_a.clear()
        messages_b.clear()
        messages_c.clear()

        # A sends message in room1
        test_msg = f"Room1 only message {uuid.uuid4().hex[:6]}"
        sio_a.emit('send_message', {'roomId': room1, 'text': test_msg})
        time.sleep(0.5)

        # Check isolation
        user_msgs_a = [m for m in messages_a if m.get('message_type') == 'user']
        user_msgs_b = [m for m in messages_b if m.get('message_type') == 'user']
        user_msgs_c = [m for m in messages_c if m.get('message_type') == 'user']

        a_has_msg = any(m.get('text') == test_msg for m in user_msgs_a)
        b_has_msg = any(m.get('text') == test_msg for m in user_msgs_b)
        c_has_msg = any(m.get('text') == test_msg for m in user_msgs_c)

        if a_has_msg and b_has_msg and not c_has_msg:
            print_test_result("PASS", time.time() - test_start,
                            "Room isolation working correctly. Room1 users received message, Room2 user did not.")
        else:
            print_test_result("FAIL", time.time() - test_start,
                            "Room isolation failed",
                            f"A: {a_has_msg}, B: {b_has_msg}, C: {c_has_msg} (should be False)")

        sio_a.disconnect()
        sio_b.disconnect()
        sio_c.disconnect()
    except Exception as e:
        print_test_result("FAIL", time.time() - test_start,
                        "Exception occurred", str(e))

    # TEST 5: Message History
    print_test_header("5. Message History Test")
    test_start = time.time()
    try:
        sio1 = socketio.Client()
        sio2 = socketio.Client()

        room_data = []

        @sio1.on('nickname_assigned')
        def on_n1(data): pass
        @sio2.on('nickname_assigned')
        def on_n2(data): pass

        @sio2.on('room_joined')
        def on_rj(data):
            room_data.append(data)

        # Connect first client
        sio1.connect(SERVER_URL)
        time.sleep(0.3)

        room_id = f"test-{uuid.uuid4().hex[:6]}"
        sio1.emit('join_room', {'roomId': room_id})
        time.sleep(0.3)

        # Send 3 messages
        msgs = [f"Msg {i}" for i in range(3)]
        for msg in msgs:
            sio1.emit('send_message', {'roomId': room_id, 'text': msg})
            time.sleep(0.1)

        time.sleep(0.3)

        # Second client joins and should receive history
        sio2.connect(SERVER_URL)
        time.sleep(0.3)
        sio2.emit('join_room', {'roomId': room_id})
        time.sleep(0.5)

        if len(room_data) > 0:
            history = room_data[0].get('history', [])
            user_messages = [m for m in history if m.get('message_type') == 'user']
            history_texts = [m.get('text') for m in user_messages]

            all_present = all(msg in history_texts for msg in msgs)

            if all_present and len(user_messages) == 3:
                print_test_result("PASS", time.time() - test_start,
                                f"New user received complete history: {len(history)} total messages ({len(user_messages)} user messages)")
            else:
                print_test_result("FAIL", time.time() - test_start,
                                "History incomplete",
                                f"Expected 3 messages, got {len(user_messages)}. All present: {all_present}")
        else:
            print_test_result("FAIL", time.time() - test_start,
                            "No room_joined event received",
                            "Unable to verify history")

        sio1.disconnect()
        sio2.disconnect()
    except Exception as e:
        print_test_result("FAIL", time.time() - test_start,
                        "Exception occurred", str(e))

    # TEST 6: Empty Message Rejection
    print_test_header("6. Empty Message Rejection Test")
    test_start = time.time()
    try:
        sio1 = socketio.Client()
        sio2 = socketio.Client()

        messages_1 = []
        messages_2 = []

        @sio1.on('nickname_assigned')
        def on_n1(data): pass
        @sio2.on('nickname_assigned')
        def on_n2(data): pass

        @sio1.on('new_message')
        def on_m1(msg): messages_1.append(msg)
        @sio2.on('new_message')
        def on_m2(msg): messages_2.append(msg)

        # Connect
        sio1.connect(SERVER_URL)
        sio2.connect(SERVER_URL)
        time.sleep(0.3)

        room_id = f"test-{uuid.uuid4().hex[:6]}"
        sio1.emit('join_room', {'roomId': room_id})
        sio2.emit('join_room', {'roomId': room_id})
        time.sleep(0.5)

        messages_1.clear()
        messages_2.clear()

        # Try to send empty and whitespace messages
        sio1.emit('send_message', {'roomId': room_id, 'text': ''})
        time.sleep(0.2)
        sio1.emit('send_message', {'roomId': room_id, 'text': '   '})
        time.sleep(0.2)

        # Send valid message
        sio1.emit('send_message', {'roomId': room_id, 'text': 'Valid'})
        time.sleep(0.3)

        # Count user messages
        user_msgs_1 = [m for m in messages_1 if m.get('message_type') == 'user']
        user_msgs_2 = [m for m in messages_2 if m.get('message_type') == 'user']

        if len(user_msgs_1) == 1 and len(user_msgs_2) == 1:
            if user_msgs_1[0].get('text') == 'Valid':
                print_test_result("PASS", time.time() - test_start,
                                "Empty messages correctly rejected, only valid message broadcast")
            else:
                print_test_result("FAIL", time.time() - test_start,
                                "Message content incorrect",
                                f"Expected 'Valid', got '{user_msgs_1[0].get('text')}'")
        else:
            print_test_result("FAIL", time.time() - test_start,
                            "Wrong number of messages received",
                            f"Expected 1 message each, got Client1: {len(user_msgs_1)}, Client2: {len(user_msgs_2)}")

        sio1.disconnect()
        sio2.disconnect()
    except Exception as e:
        print_test_result("FAIL", time.time() - test_start,
                        "Exception occurred", str(e))

    # TEST 7: Leave Room
    print_test_header("7. Leave Room Test")
    test_start = time.time()
    try:
        sio1 = socketio.Client()
        sio2 = socketio.Client()

        messages_2 = []

        @sio1.on('nickname_assigned')
        def on_n1(data): pass
        @sio2.on('nickname_assigned')
        def on_n2(data): pass

        @sio2.on('new_message')
        def on_m2(msg): messages_2.append(msg)

        # Connect both
        sio1.connect(SERVER_URL)
        sio2.connect(SERVER_URL)
        time.sleep(0.3)

        room_id = f"test-{uuid.uuid4().hex[:6]}"
        sio1.emit('join_room', {'roomId': room_id})
        sio2.emit('join_room', {'roomId': room_id})
        time.sleep(0.5)

        messages_2.clear()

        # Client 1 leaves
        sio1.emit('leave_room', {'roomId': room_id})
        time.sleep(0.5)

        # Check for leave system message
        system_msgs = [m for m in messages_2 if m.get('message_type') == 'system']
        has_leave_msg = any('퇴장' in m.get('text', '') for m in system_msgs)

        if has_leave_msg:
            print_test_result("PASS", time.time() - test_start,
                            "Leave message received by remaining user")
        else:
            print_test_result("FAIL", time.time() - test_start,
                            "Leave message not received",
                            f"System messages: {[m.get('text') for m in system_msgs]}")

        sio1.disconnect()
        sio2.disconnect()
    except Exception as e:
        print_test_result("FAIL", time.time() - test_start,
                        "Exception occurred", str(e))

    # TEST 8: Empty Room Cleanup
    print_test_header("8. Empty Room Cleanup Test")
    test_start = time.time()
    try:
        sio = socketio.Client()

        @sio.on('nickname_assigned')
        def on_n(data): pass

        sio.connect(SERVER_URL)
        time.sleep(0.3)

        room_id = f"test-cleanup-{uuid.uuid4().hex[:6]}"
        sio.emit('join_room', {'roomId': room_id})
        time.sleep(0.3)

        # Check room exists
        stats_before = requests.get(f"{SERVER_URL}/stats").json()
        room_exists_before = any(r['room_id'] == room_id for r in stats_before.get('rooms', []))

        # Leave room
        sio.emit('leave_room', {'roomId': room_id})
        time.sleep(0.5)

        # Check room deleted
        stats_after = requests.get(f"{SERVER_URL}/stats").json()
        room_exists_after = any(r['room_id'] == room_id for r in stats_after.get('rooms', []))

        if room_exists_before and not room_exists_after:
            print_test_result("PASS", time.time() - test_start,
                            f"Room '{room_id}' was properly deleted after last user left")
        else:
            print_test_result("FAIL", time.time() - test_start,
                            "Room cleanup did not work",
                            f"Before: {room_exists_before}, After: {room_exists_after}")

        sio.disconnect()
    except Exception as e:
        print_test_result("FAIL", time.time() - test_start,
                        "Exception occurred", str(e))

    # TEST 9: Concurrent Users
    print_test_header("9. Concurrent Users Test")
    test_start = time.time()
    try:
        clients = []
        for i in range(5):
            sio = socketio.Client()
            @sio.on('nickname_assigned')
            def on_n(data): pass
            clients.append(sio)

        # Connect all
        for sio in clients:
            sio.connect(SERVER_URL)
        time.sleep(0.5)

        room_id = f"test-concurrent-{uuid.uuid4().hex[:6]}"

        # All join same room
        for sio in clients:
            sio.emit('join_room', {'roomId': room_id})
        time.sleep(0.7)

        all_connected = all(sio.connected for sio in clients)

        if all_connected:
            print_test_result("PASS", time.time() - test_start,
                            f"All 5 clients successfully connected and joined room")
        else:
            connected_count = sum(1 for sio in clients if sio.connected)
            print_test_result("FAIL", time.time() - test_start,
                            "Not all clients connected",
                            f"Connected: {connected_count}/5")

        for sio in clients:
            sio.disconnect()
    except Exception as e:
        print_test_result("FAIL", time.time() - test_start,
                        "Exception occurred", str(e))

    # TEST 10: Special Characters
    print_test_header("10. Special Characters Test")
    test_start = time.time()
    try:
        sio1 = socketio.Client()
        sio2 = socketio.Client()

        messages_2 = []

        @sio1.on('nickname_assigned')
        def on_n1(data): pass
        @sio2.on('nickname_assigned')
        def on_n2(data): pass

        @sio2.on('new_message')
        def on_m2(msg): messages_2.append(msg)

        sio1.connect(SERVER_URL)
        sio2.connect(SERVER_URL)
        time.sleep(0.3)

        room_id = f"test-{uuid.uuid4().hex[:6]}"
        sio1.emit('join_room', {'roomId': room_id})
        sio2.emit('join_room', {'roomId': room_id})
        time.sleep(0.5)

        messages_2.clear()

        # Test special characters
        test_msgs = [
            "Hello World",
            "한글 테스트",
            "Special: @#$%"
        ]

        for msg in test_msgs:
            sio1.emit('send_message', {'roomId': room_id, 'text': msg})
            time.sleep(0.1)

        time.sleep(0.3)

        user_msgs = [m for m in messages_2 if m.get('message_type') == 'user']
        received_texts = [m.get('text') for m in user_msgs]

        all_match = all(msg in received_texts for msg in test_msgs)

        if all_match and len(user_msgs) == len(test_msgs):
            print_test_result("PASS", time.time() - test_start,
                            f"All {len(test_msgs)} messages with special characters transmitted correctly")
        else:
            print_test_result("FAIL", time.time() - test_start,
                            "Special character handling failed",
                            f"Expected {len(test_msgs)}, got {len(user_msgs)}. Match: {all_match}")

        sio1.disconnect()
        sio2.disconnect()
    except Exception as e:
        print_test_result("FAIL", time.time() - test_start,
                        "Exception occurred", str(e))

except KeyboardInterrupt:
    print("\n\nTest execution interrupted by user.")
except Exception as e:
    print(f"\n\nFATAL ERROR: {str(e)}")

# Final Summary
total_duration = time.time() - test_start_time

print("\n" + "=" * 80)
print("OVERALL SUMMARY")
print("=" * 80)
print(f"Total Test Cases: {total_tests}")
print(f"Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)" if total_tests > 0 else "Passed: 0")
print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)" if total_tests > 0 else "Failed: 0")
print(f"Total Duration: {total_duration:.2f} seconds")
print("")

if failed_tests == 0:
    print("All tests passed! The system is functioning correctly.")
    print("\nRECOMMENDATIONS:")
    print("  - Consider adding load testing with 50+ concurrent users")
    print("  - Test network latency scenarios")
    print("  - Add stress testing for message throughput")
    print("  - Implement automated regression testing")
else:
    print(f"\n{failed_tests} test(s) failed. Review the errors above.")
    print("\nRECOMMENDATIONS:")
    print("  - Fix failing tests before deployment")
    print("  - Review error handling for edge cases")
    print("  - Verify message format validations")

print("\n" + "=" * 80)
print("END OF REPORT")
print("=" * 80 + "\n")
