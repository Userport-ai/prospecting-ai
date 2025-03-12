#!/usr/bin/env python3
"""
Script to automatically convert standard logging to loguru in the workers folder.
This script will:
1. Scan all Python files in the workers folder
2. Replace standard logging imports with loguru imports
3. Replace logger initialization with loguru import
4. Update logging patterns to match loguru's style
5. Create a backup of each modified file

Run from the project root: python workers/scripts/update_to_loguru.py
"""

import os
import re
import shutil
import sys
from pathlib import Path


def backup_file(file_path):
    """Create a backup of the file."""
    backup_path = f"{file_path}.bak"
    shutil.copy2(file_path, backup_path)
    print(f"Created backup: {backup_path}")


def convert_file(file_path):
    """Convert a single file to use loguru."""
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Skip files that already use loguru
    if 'from utils.loguru_setup import logger' in content:
        print(f"Skipping {file_path}: already using loguru")
        return False
    
    # Create backup before modifying
    backup_file(file_path)
    
    # Replace imports
    new_content = content
    
    # Replace standard logging import
    new_content = re.sub(
        r'import\s+logging\s*?(\n|$)',
        '',
        new_content
    )
    
    # Replace getLogger pattern
    new_content = re.sub(
        r'logger\s*=\s*logging\.getLogger\([\'"]?(?:\w+|\w+\.\w+|__name__)[\'"]?\)',
        '',
        new_content
    )
    
    # Add loguru import if needed
    if 'from utils.loguru_setup import logger' not in new_content:
        # Find the last import statement to add our import after it
        import_matches = list(re.finditer(r'^(?:from|import)\s+\w+', new_content, re.MULTILINE))
        if import_matches:
            last_import = import_matches[-1]
            import_end = last_import.end()
            line_end = new_content.find('\n', import_end)
            if line_end == -1:
                line_end = len(new_content)
            
            new_content = (
                new_content[:line_end + 1] + 
                'from utils.loguru_setup import logger\n' + 
                new_content[line_end + 1:]
            )
        else:
            # No imports found, add at the beginning
            new_content = 'from utils.loguru_setup import logger\n\n' + new_content
    
    # Replace logging.basicConfig and other configuration
    new_content = re.sub(
        r'logging\.basicConfig\([^)]*\)',
        '# Logging configuration is now in utils/loguru_setup.py',
        new_content
    )
    
    # Convert extra parameter to keyword arguments
    new_content = re.sub(
        r'logger\.(debug|info|warning|error|critical|exception)\(([^,]+),\s*extra=({[^}]+})\)',
        lambda m: f'logger.{m.group(1)}({m.group(2)}, **{m.group(3)})',
        new_content
    )
    
    # Write the modified content back to the file
    if new_content != content:
        with open(file_path, 'w') as file:
            file.write(new_content)
        print(f"Updated: {file_path}")
        return True
    else:
        print(f"No changes needed for: {file_path}")
        return False


def scan_directory(directory):
    """Scan a directory for Python files and convert them."""
    converted_count = 0
    skipped_count = 0
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if convert_file(file_path):
                    converted_count += 1
                else:
                    skipped_count += 1
    
    return converted_count, skipped_count


def main():
    """Main function to run the script."""
    if len(sys.argv) > 1:
        workers_dir = sys.argv[1]
    else:
        # Default to workers folder in current project
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        workers_dir = current_dir
    
    if not os.path.isdir(workers_dir):
        print(f"Error: {workers_dir} is not a valid directory")
        sys.exit(1)
    
    print(f"Converting logging to loguru in: {workers_dir}")
    print("Creating backups of all modified files with .bak extension")
    
    converted, skipped = scan_directory(workers_dir)
    
    print("\nConversion complete!")
    print(f"Files converted: {converted}")
    print(f"Files skipped: {skipped}")
    print("\nNext steps:")
    print("1. Test the application to ensure logging works correctly")
    print("2. Review the changes and fix any issues")
    print("3. Remove backup files (.bak) once satisfied with the changes")


if __name__ == "__main__":
    main()