"""
Unit tests for the Ollama service.
"""

import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.conf import settings

from console.services.ollama import (
    OllamaError,
    get_version,
    list_models,
    list_running_models,
    delete_model,
    pull_model_stream,
    chat_stream,
    ensure_list_of_messages,
)


class TestOllamaError(TestCase):
    """Test the OllamaError exception class."""
    
    def test_ollama_error_basic(self):
        """Test basic OllamaError creation."""
        error = OllamaError("Test error")
        self.assertEqual(error.message, "Test error")
        self.assertIsNone(error.status_code)
        self.assertIsNone(error.details)
        
    def test_ollama_error_with_status(self):
        """Test OllamaError with status code."""
        error = OllamaError("Test error", status_code=404)
        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.status_code, 404)
        
    def test_ollama_error_with_details(self):
        """Test OllamaError with details."""
        details = {"key": "value"}
        error = OllamaError("Test error", details=details)
        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.details, details)
        
    def test_ollama_error_str_representation(self):
        """Test string representation of OllamaError."""
        error = OllamaError("Test error")
        self.assertEqual(str(error), "Test error")
        
        error_with_status = OllamaError("Test error", status_code=500)
        self.assertEqual(str(error_with_status), "Test error (status=500)")


class TestOllamaService(TestCase):
    """Test the Ollama service functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock settings
        self.settings_patcher = patch('console.services.ollama.settings')
        self.mock_settings = self.settings_patcher.start()
        self.mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"
        self.mock_settings.OLLAMA_REQUEST_TIMEOUT_SECONDS = 60
        
    def tearDown(self):
        """Clean up after tests."""
        self.settings_patcher.stop()
    
    @patch('console.services.ollama.requests.get')
    def test_get_version_success(self, mock_get):
        """Test successful version retrieval."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"version": "0.1.20"}
        mock_get.return_value = mock_response
        
        version = get_version()
        
        self.assertEqual(version, "0.1.20")
        mock_get.assert_called_once_with(
            "http://localhost:11434/api/version",
            timeout=60.0
        )
    
    @patch('console.services.ollama.requests.get')
    def test_get_version_connection_error(self, mock_get):
        """Test version retrieval with connection error."""
        import requests
        mock_get.side_effect = requests.RequestException("Connection refused")
        
        with self.assertRaises(OllamaError) as context:
            get_version()
            
        self.assertIn("Unable to connect to Ollama", str(context.exception))
        
    @patch('console.services.ollama.requests.get')
    def test_get_version_http_error(self, mock_get):
        """Test version retrieval with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal server error"}
        mock_response.text = "Internal server error"
        mock_get.return_value = mock_response
        
        with self.assertRaises(OllamaError) as context:
            get_version()
            
        self.assertEqual(context.exception.status_code, 500)
        
    @patch('console.services.ollama.requests.get')
    def test_list_models_success(self, mock_get):
        """Test successful model listing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.2:latest", "size": 4096},
                {"name": "mistral:latest", "size": 8192},
            ]
        }
        mock_get.return_value = mock_response
        
        result = list_models()
        
        self.assertEqual(result, {
            "models": [
                {"name": "llama3.2:latest", "size": 4096},
                {"name": "mistral:latest", "size": 8192},
            ]
        })
        mock_get.assert_called_once_with(
            "http://localhost:11434/api/tags",
            timeout=60.0
        )
    
    @patch('console.services.ollama.requests.get')
    def test_list_running_models_success(self, mock_get):
        """Test successful running models listing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.2:latest", "size": 4096, "digest": "abc123"},
            ]
        }
        mock_get.return_value = mock_response
        
        result = list_running_models()
        
        self.assertEqual(result, {
            "models": [
                {"name": "llama3.2:latest", "size": 4096, "digest": "abc123"},
            ]
        })
        mock_get.assert_called_once_with(
            "http://localhost:11434/api/ps",
            timeout=60.0
        )
    
    @patch('console.services.ollama.requests.delete')
    def test_delete_model_success(self, mock_delete):
        """Test successful model deletion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response
        
        # Should not raise an exception
        delete_model("llama3.2:latest")
        
        mock_delete.assert_called_once_with(
            "http://localhost:11434/api/delete",
            json={"model": "llama3.2:latest"},
            timeout=60.0
        )
    
    @patch('console.services.ollama.requests.delete')
    def test_delete_model_failure(self, mock_delete):
        """Test model deletion failure."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Model not found"}
        mock_response.text = "Model not found"
        mock_delete.return_value = mock_response
        
        with self.assertRaises(OllamaError) as context:
            delete_model("nonexistent:latest")
            
        self.assertEqual(context.exception.status_code, 404)
        
    def test_pull_model_stream_generator(self):
        """Test the pull model stream generator (mocked)."""
        # This is a complex test that would require mocking the streaming response
        # For now, we'll test the function signature and basic behavior
        self.assertTrue(callable(pull_model_stream))
        
    def test_chat_stream_generator(self):
        """Test the chat stream generator (mocked)."""
        # This is a complex test that would require mocking the streaming response
        # For now, we'll test the function signature and basic behavior
        self.assertTrue(callable(chat_stream))
        
    def test_ensure_list_of_messages_valid(self):
        """Test message validation with valid input."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        
        result = ensure_list_of_messages(messages)
        
        self.assertEqual(result, messages)
        
    def test_ensure_list_of_messages_invalid_type(self):
        """Test message validation with invalid type."""
        messages = ["not a dict"]
        
        with self.assertRaises(OllamaError) as context:
            ensure_list_of_messages(messages)
            
        self.assertIn("Invalid message object", str(context.exception))
        
    def test_ensure_list_of_messages_missing_fields(self):
        """Test message validation with missing required fields."""
        messages = [{"role": "user"}]  # Missing content
        
        with self.assertRaises(OllamaError) as context:
            ensure_list_of_messages(messages)
            
        self.assertIn("Message missing required fields", str(context.exception))
        
    def test_ensure_list_of_messages_generator(self):
        """Test message validation with a generator."""
        def message_generator():
            yield {"role": "user", "content": "Hello"}
            yield {"role": "assistant", "content": "Hi"}
        
        result = ensure_list_of_messages(message_generator())
        
        self.assertEqual(result, [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ])


class TestOllamaServiceStreaming(TestCase):
    """Test streaming functionality of the Ollama service."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.settings_patcher = patch('console.services.ollama.settings')
        self.mock_settings = self.settings_patcher.start()
        self.mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"
        self.mock_settings.OLLAMA_REQUEST_TIMEOUT_SECONDS = 60
        
    def tearDown(self):
        """Clean up after tests."""
        self.settings_patcher.stop()
    
    @patch('console.services.ollama.requests.post')
    def test_pull_model_stream_success(self, mock_post):
        """Test successful model pull streaming."""
        # Create a mock response with iter_lines method
        mock_response = Mock()
        mock_response.status_code = 200
        
        # Simulate streaming response lines
        lines = [
            b'{"status": "pulling manifest"}\n',
            b'{"status": "downloading", "completed": 100, "total": 1000}\n',
            b'{"status": "success"}\n',
        ]
        mock_response.iter_lines.return_value = lines
        mock_post.return_value = mock_response
        
        # Call the generator function
        generator = pull_model_stream("llama3.2:latest")
        results = list(generator)
        
        # Verify results
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["status"], "pulling manifest")
        self.assertEqual(results[1]["status"], "downloading")
        self.assertEqual(results[1]["completed"], 100)
        self.assertEqual(results[1]["total"], 1000)
        self.assertEqual(results[2]["status"], "success")
        
        # Verify API call
        mock_post.assert_called_once_with(
            "http://localhost:11434/api/pull",
            json={"model": "llama3.2:latest", "stream": True},
            timeout=60.0,
            stream=True
        )
    
    @patch('console.services.ollama.requests.post')
    def test_chat_stream_success(self, mock_post):
        """Test successful chat streaming."""
        # Create a mock response with iter_lines method
        mock_response = Mock()
        mock_response.status_code = 200
        
        # Simulate streaming response lines
        lines = [
            b'{"model": "llama3.2", "message": {"role": "assistant", "content": "Hello"}, "done": false}\n',
            b'{"model": "llama3.2", "message": {"role": "assistant", "content": " there"}, "done": false}\n',
            b'{"model": "llama3.2", "done": true, "total_duration": 500}\n',
        ]
        mock_response.iter_lines.return_value = lines
        mock_post.return_value = mock_response
        
        # Prepare messages
        messages = [
            {"role": "user", "content": "Say hello"}
        ]
        
        # Call the generator function
        generator = chat_stream(model="llama3.2:latest", messages=messages)
        results = list(generator)
        
        # Verify results
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["model"], "llama3.2")
        self.assertEqual(results[0]["message"]["content"], "Hello")
        self.assertEqual(results[1]["message"]["content"], " there")
        self.assertTrue(results[2]["done"])
        
        # Verify API call
        mock_post.assert_called_once_with(
            "http://localhost:11434/api/chat",
            json={
                "model": "llama3.2:latest",
                "messages": messages,
                "stream": True,
            },
            timeout=60.0,
            stream=True
        )
    
    @patch('console.services.ollama.requests.post')
    def test_chat_stream_with_options(self, mock_post):
        """Test chat streaming with additional options."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [b'{"done": true}\n']
        mock_post.return_value = mock_response
        
        messages = [{"role": "user", "content": "Test"}]
        options = {"temperature": 0.7}
        tools = [{"type": "function", "function": {"name": "test"}}]
        
        generator = chat_stream(
            model="llama3.2:latest",
            messages=messages,
            tools=tools,
            options=options,
            keep_alive="5m",
            format="json"
        )
        list(generator)  # Consume the generator
        
        # Verify API call with all options
        mock_post.assert_called_once_with(
            "http://localhost:11434/api/chat",
            json={
                "model": "llama3.2:latest",
                "messages": messages,
                "stream": True,
                "tools": tools,
                "options": options,
                "keep_alive": "5m",
                "format": "json",
            },
            timeout=60.0,
            stream=True
        )


if __name__ == '__main__':
    import unittest
    unittest.main()