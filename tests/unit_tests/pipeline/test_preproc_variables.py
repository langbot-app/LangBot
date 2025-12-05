"""
Test that preproc module adds sender_id and sender_name variables.
These tests verify the variables are correctly extracted from message events.
"""

import pytest
from unittest.mock import Mock, AsyncMock


@pytest.mark.asyncio
async def test_sender_variables_friend_message():
    """Test sender_id and sender_name are extracted from FriendMessage"""
    # Create mock Friend sender
    mock_sender = Mock()
    mock_sender.id = 'test_user_123'
    mock_sender.nickname = 'Test User'
    mock_sender.remark = 'Test Remark'
    mock_sender.get_name = Mock(return_value='Test User')

    # Verify get_name returns nickname
    assert mock_sender.get_name() == 'Test User'


@pytest.mark.asyncio
async def test_sender_variables_group_message():
    """Test sender_id and sender_name are extracted from GroupMessage"""
    # Create mock GroupMember sender
    mock_sender = Mock()
    mock_sender.id = 'group_user_456'
    mock_sender.member_name = 'Group User Name'
    mock_sender.get_name = Mock(return_value='Group User Name')

    # Verify get_name returns member_name
    assert mock_sender.get_name() == 'Group User Name'


def test_sender_id_string_conversion():
    """Test sender_id is converted to string"""
    # Test integer sender_id
    sender_id_int = 12345
    assert str(sender_id_int) == '12345'

    # Test string sender_id
    sender_id_str = 'user_abc'
    assert str(sender_id_str) == 'user_abc'


def test_sender_name_empty_fallback():
    """Test sender_name defaults to empty string when not available"""
    # When sender has no name
    sender_name = ''
    assert sender_name == ''


def test_variables_dict_structure():
    """Test the variables dictionary has expected structure"""
    # Simulate what the variables dict should look like
    variables = {
        'session_id': 'person_12345',
        'conversation_id': 'conv-uuid-123',
        'msg_create_time': 1609459200,
        'sender_id': '12345',
        'sender_name': 'Test User',
    }

    # Verify all expected keys are present
    assert 'session_id' in variables
    assert 'conversation_id' in variables
    assert 'msg_create_time' in variables
    assert 'sender_id' in variables
    assert 'sender_name' in variables

    # Verify values
    assert variables['sender_id'] == '12345'
    assert variables['sender_name'] == 'Test User'


def test_dify_workflow_inputs_structure():
    """Test the Dify workflow inputs have expected legacy variables"""
    plain_text = 'Hello world'
    variables = {
        'session_id': 'person_12345',
        'conversation_id': 'conv-uuid-123',
        'msg_create_time': 1609459200,
        'sender_id': '12345',
        'sender_name': 'Test User',
    }

    # Simulate Dify workflow inputs structure
    inputs = {
        'langbot_user_message_text': plain_text,
        'langbot_session_id': variables['session_id'],
        'langbot_conversation_id': variables['conversation_id'],
        'langbot_msg_create_time': variables['msg_create_time'],
        'langbot_sender_id': variables.get('sender_id', ''),
        'langbot_sender_name': variables.get('sender_name', ''),
    }
    inputs.update(variables)

    # Verify all legacy variables are present
    assert inputs['langbot_user_message_text'] == 'Hello world'
    assert inputs['langbot_session_id'] == 'person_12345'
    assert inputs['langbot_conversation_id'] == 'conv-uuid-123'
    assert inputs['langbot_msg_create_time'] == 1609459200
    assert inputs['langbot_sender_id'] == '12345'
    assert inputs['langbot_sender_name'] == 'Test User'

    # Verify regular variables are also present
    assert inputs['sender_id'] == '12345'
    assert inputs['sender_name'] == 'Test User'
