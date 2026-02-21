"""
Unit tests for the console models.
"""

from django.test import TestCase
from django.db.utils import IntegrityError
from django.utils import timezone

from console.models import ChatSession, ChatMessage


class TestChatSessionModel(TestCase):
    """Test the ChatSession model."""
    
    def test_create_chat_session(self):
        """Test creating a chat session."""
        session = ChatSession.objects.create(
            title="Test Chat",
            model="llama3.2:latest"
        )
        
        self.assertIsNotNone(session.pk)
        self.assertEqual(session.title, "Test Chat")
        self.assertEqual(session.model, "llama3.2:latest")
        self.assertIsNotNone(session.created_at)
        
    def test_chat_session_default_title(self):
        """Test chat session with default title."""
        session = ChatSession.objects.create(
            model="llama3.2:latest"
        )
        
        self.assertEqual(session.title, "New chat")
        
    def test_chat_session_string_representation(self):
        """Test string representation of chat session."""
        session = ChatSession.objects.create(
            title="Test Chat",
            model="llama3.2:latest"
        )
        
        expected_str = f"Test Chat (llama3.2:latest)"
        self.assertEqual(str(session), expected_str)
        
    def test_chat_session_ordering(self):
        """Test that chat sessions are ordered by creation date (newest first)."""
        # Create sessions in reverse chronological order
        session1 = ChatSession.objects.create(
            title="First",
            model="model1"
        )
        
        # Simulate time passing
        import time
        time.sleep(0.01)
        
        session2 = ChatSession.objects.create(
            title="Second",
            model="model2"
        )
        
        # Query sessions
        sessions = ChatSession.objects.all()
        
        # Should be ordered by created_at descending (newest first)
        self.assertEqual(sessions[0], session2)
        self.assertEqual(sessions[1], session1)
        
    def test_chat_session_messages_relationship(self):
        """Test the relationship between ChatSession and ChatMessage."""
        session = ChatSession.objects.create(
            title="Test Chat",
            model="llama3.2:latest"
        )
        
        # Create messages for the session
        message1 = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_USER,
            content="Hello"
        )
        message2 = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_ASSISTANT,
            content="Hi there!"
        )
        
        # Test forward relationship
        self.assertEqual(message1.session, session)
        self.assertEqual(message2.session, session)
        
        # Test reverse relationship
        messages = session.messages.all()
        self.assertEqual(messages.count(), 2)
        self.assertIn(message1, messages)
        self.assertIn(message2, messages)
        
    def test_chat_session_cascade_delete(self):
        """Test that deleting a session also deletes its messages."""
        session = ChatSession.objects.create(
            title="Test Chat",
            model="llama3.2:latest"
        )
        
        # Create messages for the session
        ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_USER,
            content="Hello"
        )
        ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_ASSISTANT,
            content="Hi there!"
        )
        
        # Check messages exist
        self.assertEqual(ChatMessage.objects.count(), 2)
        
        # Delete the session
        session.delete()
        
        # Messages should also be deleted
        self.assertEqual(ChatMessage.objects.count(), 0)


class TestChatMessageModel(TestCase):
    """Test the ChatMessage model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.session = ChatSession.objects.create(
            title="Test Chat",
            model="llama3.2:latest"
        )
        
    def test_create_chat_message(self):
        """Test creating a chat message."""
        message = ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_USER,
            content="Hello, world!"
        )
        
        self.assertIsNotNone(message.pk)
        self.assertEqual(message.session, self.session)
        self.assertEqual(message.role, ChatMessage.ROLE_USER)
        self.assertEqual(message.content, "Hello, world!")
        self.assertIsNotNone(message.created_at)
        
    def test_chat_message_role_choices(self):
        """Test all valid role choices."""
        # Test each role
        roles = [
            (ChatMessage.ROLE_SYSTEM, "system"),
            (ChatMessage.ROLE_USER, "user"),
            (ChatMessage.ROLE_ASSISTANT, "assistant"),
            (ChatMessage.ROLE_TOOL, "tool"),
        ]
        
        for role_value, role_display in roles:
            message = ChatMessage.objects.create(
                session=self.session,
                role=role_value,
                content=f"Message as {role_display}"
            )
            
            self.assertEqual(message.role, role_value)
            
            # Check display value
            self.assertEqual(message.get_role_display(), role_display)
        
    def test_chat_message_invalid_role(self):
        """Test that invalid role raises an error."""
        # This should raise an error when saving with invalid role
        message = ChatMessage(
            session=self.session,
            role="invalid_role",  # Not in ROLE_CHOICES
            content="Test message"
        )
        
        # Django will raise ValidationError on full_clean()
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            message.full_clean()
        
    def test_chat_message_string_representation(self):
        """Test string representation of chat message."""
        message = ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_USER,
            content="Hello, this is a test message that is quite long"
        )
        
        # The __str__ method shows first 40 characters
        expected_str = "user: Hello, this is a test message that is qu"
        self.assertEqual(str(message), expected_str)
        
    def test_chat_message_ordering(self):
        """Test that chat messages are ordered by creation date."""
        # Create messages
        message1 = ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_USER,
            content="First message"
        )
        
        # Simulate time passing
        import time
        time.sleep(0.01)
        
        message2 = ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_ASSISTANT,
            content="Second message"
        )
        
        # Query messages
        messages = ChatMessage.objects.filter(session=self.session)
        
        # Should be ordered by created_at ascending (oldest first)
        self.assertEqual(messages[0], message1)
        self.assertEqual(messages[1], message2)
        
    def test_chat_message_required_fields(self):
        """Test that required fields are enforced."""
        # Test missing session
        message = ChatMessage(
            role=ChatMessage.ROLE_USER,
            content="Test message"
        )
        
        with self.assertRaises(IntegrityError):
            message.save()
        
    def test_chat_message_content_can_be_empty(self):
        """Test that message content can be empty string."""
        message = ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_USER,
            content=""  # Empty content
        )
        
        self.assertIsNotNone(message.pk)
        self.assertEqual(message.content, "")
        
    def test_chat_message_long_content(self):
        """Test that long content is stored correctly."""
        long_content = "A" * 10000  # 10KB of text
        
        message = ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_USER,
            content=long_content
        )
        
        self.assertIsNotNone(message.pk)
        self.assertEqual(message.content, long_content)
        
    def test_chat_message_foreign_key_constraint(self):
        """Test foreign key constraint to ChatSession."""
        # Create a message with a non-existent session ID
        message = ChatMessage(
            session_id=99999,  # Non-existent session
            role=ChatMessage.ROLE_USER,
            content="Test message"
        )
        
        # Should raise IntegrityError when trying to save
        with self.assertRaises(IntegrityError):
            message.save()


class TestModelConstants(TestCase):
    """Test model constants and choices."""
    
    def test_role_constants(self):
        """Test that role constants have correct values."""
        self.assertEqual(ChatMessage.ROLE_SYSTEM, "system")
        self.assertEqual(ChatMessage.ROLE_USER, "user")
        self.assertEqual(ChatMessage.ROLE_ASSISTANT, "assistant")
        self.assertEqual(ChatMessage.ROLE_TOOL, "tool")
        
    def test_role_choices_structure(self):
        """Test that ROLE_CHOICES has the correct structure."""
        expected_choices = [
            ("system", "system"),
            ("user", "user"),
            ("assistant", "assistant"),
            ("tool", "tool"),
        ]
        
        self.assertEqual(ChatMessage.ROLE_CHOICES, expected_choices)
        
    def test_meta_options(self):
        """Test model Meta options."""
        # Test ChatSession Meta
        self.assertEqual(ChatSession._meta.ordering, ["-created_at", "-id"])
        
        # Test ChatMessage Meta
        self.assertEqual(ChatMessage._meta.ordering, ["created_at", "id"])


if __name__ == '__main__':
    import unittest
    unittest.main()