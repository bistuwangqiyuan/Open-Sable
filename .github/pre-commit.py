import sys
import os

def check_json_import(file_path):
    """Check if 'json' is imported in the file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check for standard import
    if 'import json' not in content:
        return False
    
    # Check for from...import syntax
    if 'from json' not in content:
        return False
    
    return True

if __name__ == '__main__':
    errors = []
    modified_files = [f for f in sys.argv[1:] if os.path.exists(f)]
    
    for file_path in modified_files:
        if not check_json_import(file_path):
            errors.append(f"Missing 'json' import in {file_path}")

    if errors:
        print("Error: Missing imports found!")
        print("=" * 50)
        for error in errors:
            print(error)
        print("=" * 50 + "\n")
        sys.exit(1)
    
    print("✓ All required imports found")
    sys.exit(0)