"""
Test script to identify issues in the fine-tuning service implementation.
"""

import os
import sys
import tempfile
import json

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
    
    # Create a test JSONL file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        # Valid JSONL format
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
        print(f"  JSONL validation: size={size}, errors={errors}")
        assert size == 2, f"Expected 2 records, got {size}"
        assert len(errors) == 0, f"Expected no errors, got {errors}"
    finally:
        os.unlink(jsonl_file)
    
    # Create a test CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("role,content\n")
        f.write("user,Hello\n")
        f.write("assistant,Hi there!\n")
        csv_file = f.name
    
    try:
        size, errors = validate_dataset_format(csv_file)
        print(f"  CSV validation: size={size}, errors={errors}")
        assert size == 2, f"Expected 2 records, got {size}"
        assert len(errors) == 0, f"Expected no errors, got {errors}"
    finally:
        os.unlink(csv_file)
    
    print("  ✓ Dataset validation tests passed")

def test_modelfile_creation():
    """Test Modelfile creation function."""
    print("\nTesting Modelfile creation...")
    
    # Create a test dataset
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps({
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ]
        }) + "\n")
        dataset_file = f.name
    
    try:
        modelfile = create_modelfile(
            base_model="llama3.2:latest",
            dataset_path=dataset_file,
            epochs=3,
            learning_rate=0.0001,
            batch_size=4
        )
        
        print("  Generated Modelfile:")
        print("  " + "-" * 40)
        for line in modelfile.split('\n'):
            print(f"  {line}")
        print("  " + "-" * 40)
        
        # Check basic structure
        assert "FROM llama3.2:latest" in modelfile
        assert "PARAMETER learning_rate 0.0001" in modelfile
        assert "PARAMETER num_epoch 3" in modelfile
        assert "PARAMETER batch_size 4" in modelfile
        assert "TEMPLATE" in modelfile
        
        # Check if training data is included
        assert "user: Hello" in modelfile
        assert "assistant: Hi there!" in modelfile
        
        print("  ✓ Modelfile creation test passed")
        
    except Exception as e:
        print(f"  ✗ Modelfile creation failed: {e}")
        raise
    finally:
        os.unlink(dataset_file)

def test_modelfile_issues():
    """Identify potential issues with the Modelfile format."""
    print("\nAnalyzing Modelfile format issues...")
    
    # The current implementation puts training data in TEMPLATE
    # This is likely incorrect for Ollama fine-tuning
    
    print("  Issue 1: Training data in TEMPLATE section")
    print("    - TEMPLATE in Ollama Modelfile is for chat templates, not training data")
    print("    - Fine-tuning requires a different approach")
    
    print("  Issue 2: Missing SYSTEM instruction")
    print("    - Modelfiles often need SYSTEM instruction for context")
    
    print("  Issue 3: Parameter names might be incorrect")
    print("    - Should verify Ollama's actual parameter names for fine-tuning")

def main():
    """Run all tests."""
    print("=" * 60)
    print("Fine-tuning Service Analysis")
    print("=" * 60)
    
    try:
        test_dataset_validation()
        test_modelfile_creation()
        test_modelfile_issues()
        
        print("\n" + "=" * 60)
        print("SUMMARY:")
        print("=" * 60)
        print("1. Dataset validation works correctly")
        print("2. Modelfile generation has structural issues:")
        print("   - Training data should not be in TEMPLATE section")
        print("   - Need to verify correct Ollama fine-tuning approach")
        print("3. Missing comprehensive error handling tests")
        print("4. No integration tests with actual Ollama")
        
    except Exception as e:
        print(f"\n✗ Tests failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
