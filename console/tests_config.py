"""
Test configuration for the console application.
"""

import os

# Test database configuration
TEST_DATABASE = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',  # Use in-memory database for tests
    }
}

# Test settings
TEST_SETTINGS = {
    'DEBUG': False,
    'SECRET_KEY': 'test-secret-key-for-testing-only',
    'ALLOWED_HOSTS': ['testserver', 'localhost', '127.0.0.1'],
    'OLLAMA_BASE_URL': 'http://localhost:11434',
    'OLLAMA_REQUEST_TIMEOUT_SECONDS': 1,  # Short timeout for tests
    'CSRF_TRUSTED_ORIGINS': ['http://testserver'],
    # Disable security features for tests
    'SECURE_SSL_REDIRECT': False,
    'SESSION_COOKIE_SECURE': False,
    'CSRF_COOKIE_SECURE': False,
}

# Test environment variables
def setup_test_environment():
    """Set up environment variables for testing."""
    for key, value in TEST_SETTINGS.items():
        os.environ[key] = str(value)