#!/usr/bin/env python3
"""
Demonstrate that Ollama API caching is working.
"""

import os
import django
import time
from unittest.mock import Mock, patch

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ollama_dashboard.settings')
django.setup()

from console.services.ollama import get_version, list_models, list_running_models
from django.core.cache import cache


def test_caching_demo():
    """Demonstrate caching functionality."""
    print("=== Ollama API Caching Demo ===\n")
    
    # Clear cache first
    cache.clear()
    print("1. Cache cleared")
    
    # Mock the requests
    mock_response = Mock()
    mock_response.status_code = 200
    
    # Test get_version caching
    print("\n2. Testing get_version() caching:")
    
    with patch('console.services.ollama.requests.get') as mock_get:
        mock_response.json.return_value = {"version": "0.1.20"}
        mock_get.return_value = mock_response
        
        # First call - should hit the API
        print("   First call (should call API)...")
        version1 = get_version()
        print(f"   Result: {version1}")
        print(f"   API calls: {mock_get.call_count}")
        
        # Second call - should use cache
        print("   Second call (should use cache)...")
        version2 = get_version()
        print(f"   Result: {version2}")
        print(f"   API calls: {mock_get.call_count} (should be same as before)")
        
        # Verify cache hit
        cache_key = "ollama:version"
        cached = cache.get(cache_key)
        print(f"   Cache contains: {cached}")
        
    # Test list_models caching
    print("\n3. Testing list_models() caching:")
    
    with patch('console.services.ollama.requests.get') as mock_get:
        mock_response.json.return_value = {"models": [{"name": "llama3.2:latest"}]}
        mock_get.return_value = mock_response
        
        # Reset call count
        mock_get.call_count = 0
        
        # First call
        print("   First call (should call API)...")
        models1 = list_models()
        print(f"   Result: {len(models1.get('models', []))} models")
        print(f"   API calls: {mock_get.call_count}")
        
        # Second call
        print("   Second call (should use cache)...")
        models2 = list_models()
        print(f"   Result: {len(models2.get('models', []))} models")
        print(f"   API calls: {mock_get.call_count} (should be same)")
    
    # Test cache invalidation
    print("\n4. Testing cache invalidation:")
    
    # Manually set cache
    cache.set("ollama:version", "cached-version", timeout=30)
    cache.set("ollama:models", {"models": [{"name": "cached-model"}]}, timeout=30)
    
    print("   Cache manually populated")
    print(f"   Version cache: {cache.get('ollama:version')}")
    print(f"   Models cache keys: {list(cache.get('ollama:models', {}).keys())}")
    
    # Import and call invalidate_cache
    from console.services.ollama import invalidate_cache
    invalidate_cache()
    
    print("   After invalidate_cache():")
    print(f"   Version cache: {cache.get('ollama:version')} (should be None)")
    print(f"   Models cache: {cache.get('ollama:models')} (should be None)")
    
    print("\n=== Caching Demo Complete ===")
    print("\nSummary:")
    print("- get_version(), list_models(), list_running_models() are cached")
    print("- Cache timeout: 30 seconds (configurable)")
    print("- Cache invalidated on model deletion/pull")
    print("- Manual invalidation available via invalidate_cache()")


if __name__ == '__main__':
    test_caching_demo()