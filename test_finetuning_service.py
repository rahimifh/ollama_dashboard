"""
Test script to verify fine-tuning service functionality.
"""

import os
import sys
import tempfile
import json
import csv

# Add the project to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ollama_dashboard.settings')

import django
django.setup()

from console.services.finetuning import (
    validate_dataset_format,
    create_modelfile,
    FineTuningError
)

def test_dataset_validation():
    """Test dataset validation function."""
    print("Testing dataset validation...")
    
    # Test 1: Valid JSONL file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps({
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ]
        }) + "\n")
        f.write(json.dumps({
            "messages": [
                {"role": "user", "content": "What's your name?"},
                {"role": "assistant", "content": "I'm an AI assistant."}
            ]
        }) + "\n")
        jsonl_file = f.name
    
    try:
        size, errors = validate_dataset_format(jsonl_file)
        print(f"  ✓ JSONL validation: size={size}, errors={errors}")
        assert size == 2, f"Expected 2 records, got {size}"
        assert len(errors) == 0, f"Expected no errors, got {errors}"
    finally:
        os.unlink(jsonl_file)
    
    # Test 2: Valid CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("role,content\n")
        f.write("user,Hello\n")
        f.write("assistant,Hi there!\n")
        csv_file = f.name
    
    try:
        size, errors = validate_dataset_format(csv_file)
        print(f"  ✓ CSV validation: size={size}, errors={errors}")
        assert size == 2, f"Expected 2 records, got {size}"
        assert len(errors) == 0, f"Expected no errors, got {errors}"
    finally:
        os.unlink(csv_file)
    
    # Test 3: Invalid JSONL file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write('{"invalid": "format"}\n')
        invalid_jsonl = f.name
    
    try:
        size, errors = validate_dataset_format(invalid_jsonl)
        print(f"  ✓ Invalid JSONL validation: size={size}, errors={len(errors)} errors")
        assert len(errors) > 0, "Expected validation errors for invalid JSONL"
    finally:
        os.unlink(invalid_jsonl)
    
    # Test 4: Invalid CSV file (missing columns)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("wrong,columns\n")
        f.write("value1,value2\n")
        invalid_csv = f.name
    
    try:
        size, errors = validate_dataset_format(invalid_csv)
        print(f"  ✓ Invalid CSV validation: size={size}, errors={len(errors)} errors")
        assert len(errors) > 0, "Expected validation errors for invalid CSV"
    finally:
        os.unlink(invalid_csv)
    
    print("  All dataset validation tests passed!")

def test_modelfile_creation():
    """Test Modelfile creation function."""
    print("\nTesting Modelfile creation...")
    
    modelfile = create_modelfile(
        base_model="llama3.2:latest",
        system_prompt="You are a helpful assistant."
    )
    
    print("  Generated Modelfile:")
    print("  " + "-" * 40)
    for line in modelfile.split('\n'):
        if line:
            print(f"  {line}")
    print("  " + "-" * 40)
    
    # Check basic structure
    assert "FROM llama3.2:latest" in modelfile
    assert "SYSTEM" in modelfile
    assert "You are a helpful assistant." in modelfile
    
    print("  ✓ Modelfile creation test passed")

def test_modelfile_without_system_prompt():
    """Test Modelfile creation without system prompt."""
    print("\nTesting Modelfile creation without system prompt...")
    
    modelfile = create_modelfile(
        base_model="mistral:latest"
    )
    
    assert "FROM mistral:latest" in modelfile
    assert "SYSTEM" not in modelfile  # No system prompt should be included
    
    print("  ✓ Modelfile without system prompt test passed")

def test_error_handling():
    """Test error handling."""
    print("\nTesting error handling...")
    
    # Test FineTuningError
    error = FineTuningError("Test error", job_id=123)
    assert str(error) == "Test error (job_id=123)"
    
    error2 = FineTuningError("Another error")
    assert str(error2) == "Another error"
    
    print("  ✓ Error handling tests passed")

def main():
    """Run all tests."""
    print("=" * 60)
    print("Fine-tuning Service Verification")
    print("=" * 60)
    
    try:
        test_dataset_validation()
        test_modelfile_creation()
        test_modelfile_without_system_prompt()
        test_error_handling()
        
        print("\n" + "=" * 60)
        print("SUMMARY:")
        print("=" * 60)
        print("✓ All core fine-tuning service functions work correctly")
        print("✓ Dataset validation handles both JSONL and CSV formats")
        print("✓ Modelfile generation works with and without system prompts")
        print("✓ Error handling is properly implemented")
        print("\nNote: Integration tests with actual training backend")
        print("      would require llama-finetune to be installed.")
        
    except Exception as e:
        print(f"\n✗ Tests failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())