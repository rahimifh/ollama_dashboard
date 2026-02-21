"""
Test suite for the console application.
"""

import os
import sys
import django
from django.test.utils import setup_test_environment
from django.test.runner import DiscoverRunner

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ollama_dashboard.settings')
django.setup()


def run_all_tests():
    """Run all tests for the console application."""
    setup_test_environment()
    
    # Create test runner
    test_runner = DiscoverRunner(
        pattern="test_*.py",
        verbosity=2,
        interactive=True,
        failfast=False,
    )
    
    # Run tests
    failures = test_runner.run_tests(['console'])
    
    return failures


if __name__ == '__main__':
    failures = run_all_tests()
    sys.exit(1 if failures else 0)
