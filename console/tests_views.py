"""
Unit tests for the console views.
"""

import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from console.models import ChatSession, ChatMessage
from console.services import ollama


class TestDashboardViews(TestCase):
    """Test dashboard-related views."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
    def test_dashboard_view_get(self):
        """Test GET request to dashboard."""
        response = self.client.get(reverse('console:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'console/dashboard.html')
        self.assertContains(response, 'Dashboard')
        
    @patch('console.views.ollama.get_version')
    @patch('console.views.ollama.list_models')
    @patch('console.views.ollama.list_running_models')
    def test_dashboard_context_with_ollama(self, mock_running, mock_models, mock_version):
        """Test dashboard context when Ollama is available."""
        # Mock Ollama responses
        mock_version.return_value = "0.1.20"
        mock_models.return_value = {"models": [{"name": "llama3.2:latest"}]}
        mock_running.return_value = {"models": []}
        
        response = self.client.get(reverse('console:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        
        self.assertEqual(context['ollama_version'], "0.1.20")
        self.assertEqual(len(context['models']), 1)
        self.assertEqual(context['models'][0]['name'], "llama3.2:latest")
        self.assertEqual(len(context['running_models']), 0)
        self.assertIsNone(context['error'])
        
    @patch('console.views.ollama.get_version')
    def test_dashboard_context_with_ollama_error(self, mock_version):
        """Test dashboard context when Ollama is not available."""
        # Mock Ollama error
        mock_version.side_effect = ollama.OllamaError("Connection refused")
        
        response = self.client.get(reverse('console:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        
        self.assertIsNone(context['ollama_version'])
        self.assertEqual(len(context['models']), 0)
        self.assertEqual(len(context['running_models']), 0)
        self.assertIsNotNone(context['error'])
        self.assertIn("Connection refused", context['error'])
        
    def test_partial_status_view(self):
        """Test the status partial view."""
        response = self.client.get(reverse('console:partial_status'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'console/_status.html')
        
    def test_partial_models_view(self):
        """Test the models partial view."""
        response = self.client.get(reverse('console:partial_models'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'console/_models_table.html')
        
    def test_partial_running_view(self):
        """Test the running models partial view."""
        response = self.client.get(reverse('console:partial_running'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'console/_running_table.html')


class TestChatViews(TestCase):
    """Test chat-related views."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create a test chat session
        self.session = ChatSession.objects.create(
            title="Test Chat",
            model="llama3.2:latest"
        )
        
        # Create test messages
        self.user_message = ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_USER,
            content="Hello"
        )
        self.assistant_message = ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_ASSISTANT,
            content="Hi there!"
        )
        
    def test_chat_view_get(self):
        """Test GET request to chat page."""
        response = self.client.get(reverse('console:chat'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'console/chat.html')
        
    def test_chat_view_with_session_id(self):
        """Test chat view with specific session ID."""
        url = f"{reverse('console:chat')}?session={self.session.pk}"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        
        self.assertEqual(context['selected_session'], self.session)
        self.assertIn(self.session, context['sessions'])
        self.assertEqual(len(context['messages']), 2)
        
    def test_chat_view_no_sessions(self):
        """Test chat view when no sessions exist."""
        # Delete all sessions
        ChatSession.objects.all().delete()
        
        response = self.client.get(reverse('console:chat'))
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        
        # Should create a new session
        self.assertIsNotNone(context['selected_session'])
        self.assertEqual(len(context['sessions']), 1)
        
    @patch('console.views.ollama.list_models')
    def test_chat_view_with_ollama_error(self, mock_list_models):
        """Test chat view when Ollama models can't be listed."""
        mock_list_models.side_effect = ollama.OllamaError("Connection refused")
        
        response = self.client.get(reverse('console:chat'))
        
        self.assertEqual(response.status_code, 200)
        context = response.context
        
        self.assertIsNotNone(context['ollama_error'])
        self.assertIn("Connection refused", context['ollama_error'])
        
    def test_chat_new_view_post(self):
        """Test creating a new chat session."""
        response = self.client.post(
            reverse('console:chat_new'),
            {'model': 'mistral:latest', 'title': 'New Test Chat'}
        )
        
        self.assertEqual(response.status_code, 302)  # Redirect
        
        # Check that a new session was created
        new_session = ChatSession.objects.filter(title='New Test Chat').first()
        self.assertIsNotNone(new_session)
        self.assertEqual(new_session.model, 'mistral:latest')
        
    def test_chat_new_view_post_defaults(self):
        """Test creating a new chat session with defaults."""
        response = self.client.post(
            reverse('console:chat_new'),
            {}  # Empty POST data
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Should create session with defaults
        new_session = ChatSession.objects.filter(title='New chat').first()
        self.assertIsNotNone(new_session)
        
    def test_chat_set_model_view_post(self):
        """Test updating a chat session's model."""
        response = self.client.post(
            reverse('console:chat_set_model'),
            {
                'session_id': self.session.pk,
                'model': 'new-model:latest'
            }
        )
        
        self.assertEqual(response.status_code, 302)  # Redirect
        
        # Refresh session from database
        self.session.refresh_from_db()
        self.assertEqual(self.session.model, 'new-model:latest')
        
    def test_chat_set_model_view_invalid_session(self):
        """Test updating model for non-existent session."""
        response = self.client.post(
            reverse('console:chat_set_model'),
            {
                'session_id': 99999,  # Non-existent ID
                'model': 'new-model:latest'
            }
        )
        
        self.assertEqual(response.status_code, 302)  # Should redirect
        
    def test_chat_set_model_view_missing_data(self):
        """Test updating model with missing data."""
        response = self.client.post(
            reverse('console:chat_set_model'),
            {}  # Empty POST data
        )
        
        self.assertEqual(response.status_code, 302)  # Should redirect


class TestModelManagementViews(TestCase):
    """Test model management views."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
    @patch('console.views.ollama.delete_model')
    def test_model_delete_view_success(self, mock_delete):
        """Test successful model deletion."""
        response = self.client.post(
            reverse('console:model_delete'),
            {'model': 'llama3.2:latest'}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'console/_models_table.html')
        mock_delete.assert_called_once_with('llama3.2:latest')
        
    def test_model_delete_view_missing_model(self):
        """Test model deletion with missing model parameter."""
        response = self.client.post(
            reverse('console:model_delete'),
            {}  # No model parameter
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)
        
    @patch('console.views.ollama.delete_model')
    def test_model_delete_view_ollama_error(self, mock_delete):
        """Test model deletion when Ollama returns an error."""
        mock_delete.side_effect = ollama.OllamaError("Model not found", status_code=404)
        
        response = self.client.post(
            reverse('console:model_delete'),
            {'model': 'nonexistent:latest'}
        )
        
        self.assertEqual(response.status_code, 502)  # Bad Gateway
        self.assertTemplateUsed(response, 'console/_models_table.html')
        
        # Check error in context
        context = response.context
        self.assertIsNotNone(context['error'])


class TestStreamingAPIViews(TestCase):
    """Test streaming API views."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create a test chat session
        self.session = ChatSession.objects.create(
            title="Test Chat",
            model="llama3.2:latest"
        )
        
    def test_api_models_pull_missing_model(self):
        """Test model pull API with missing model parameter."""
        response = self.client.post(
            reverse('console:api_models_pull'),
            content_type='application/json',
            data=json.dumps({})  # Empty JSON
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['Content-Type'], 'application/x-ndjson')
        
        # Parse NDJSON response from streaming content
        content = b''.join(response.streaming_content).decode()
        lines = content.strip().split('\n')
        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0])
        self.assertIn('error', data)
        
    @patch('console.views.ollama.pull_model_stream')
    def test_api_models_pull_success(self, mock_pull_stream):
        """Test successful model pull API."""
        # Mock the streaming response
        mock_pull_stream.return_value = [
            {"status": "starting"},
            {"status": "success"}
        ]
        
        response = self.client.post(
            reverse('console:api_models_pull'),
            content_type='application/json',
            data=json.dumps({'model': 'llama3.2:latest'})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/x-ndjson')
        self.assertEqual(response['Cache-Control'], 'no-cache')
        
        # Parse NDJSON response from streaming content
        content = b''.join(response.streaming_content).decode()
        lines = content.strip().split('\n')
        self.assertEqual(len(lines), 2)
        
        data1 = json.loads(lines[0])
        data2 = json.loads(lines[1])
        
        self.assertEqual(data1['status'], 'starting')
        self.assertEqual(data2['status'], 'success')
        
    def test_api_chat_stream_missing_parameters(self):
        """Test chat stream API with missing parameters."""
        response = self.client.post(
            reverse('console:api_chat_stream'),
            content_type='application/json',
            data=json.dumps({})  # Empty JSON
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['Content-Type'], 'application/x-ndjson')
        
    def test_api_chat_stream_invalid_session(self):
        """Test chat stream API with invalid session ID."""
        response = self.client.post(
            reverse('console:api_chat_stream'),
            content_type='application/json',
            data=json.dumps({
                'session_id': 99999,  # Non-existent session
                'content': 'Hello'
            })
        )
        
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response['Content-Type'], 'application/x-ndjson')
        
    @patch('console.views.ollama.chat_stream')
    def test_api_chat_stream_success(self, mock_chat_stream):
        """Test successful chat stream API."""
        # Mock the streaming response
        mock_chat_stream.return_value = [
            {"message": {"content": "Hello"}, "done": False},
            {"message": {"content": " there"}, "done": False},
            {"done": True}
        ]
        
        response = self.client.post(
            reverse('console:api_chat_stream'),
            content_type='application/json',
            data=json.dumps({
                'session_id': self.session.pk,
                'content': 'Say hello'
            })
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/x-ndjson')
        self.assertEqual(response['Cache-Control'], 'no-cache')
        
        # Check that a user message was created
        user_message = ChatMessage.objects.filter(
            session=self.session,
            role=ChatMessage.ROLE_USER
        ).first()
        self.assertIsNotNone(user_message)
        self.assertEqual(user_message.content, 'Say hello')
        
        # Parse NDJSON response (would need to handle streaming properly)
        # For now, just check the response structure
        self.assertTrue(response.streaming)


if __name__ == '__main__':
    import unittest
    unittest.main()