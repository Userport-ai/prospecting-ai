#!/bin/bash

# Define file paths
FILES=(
  "__init__.py"
  "__main__.py"
  "apollo_source.py"
  "config.py"
  "data_models.py"
  "database.py"
  "main.py"
  "research_engine.py"
  "utils.py"
  "workflow.py"
)

# Common trivial comment patterns to remove
PATTERNS=(
  "# Session for API requests"
  "# Extract core fields"
  "# Skip entries without required fields"
  "# Extract industry and description"
  "# Build additional info from remaining fields"
  "# Create ProspectingTarget and add to results"
  "# Create research engine for selling product research"
  "# Run research"
  "# Research the selling product once"
  "# Create workflow with researched selling product"
  "# Create output directory if it doesn't exist"
  "# Central place to configure all timeouts"
  "# Format both the standard filters and Apollo filters for display"
  "# Use Apollo-specific filters for the actual API call"
  "# Using double braces in f-string to escape them - much cleaner solution!"
  "# Try to extract JSON"
  "# Try to find any JSON-like structure if not in code blocks"
  "# Create necessary tables if they don't exist"
  "# Initialize the database and create tables if they don't exist"
)

# Loop through files
for file in "${FILES[@]}"; do
  if [ -f "$file" ]; then
    echo "Processing $file..."
    
    # Remove shebang and encoding lines
    sed -i '' '1,2d' "$file"
    
    # Replace docstrings with single-line versions
    sed -i '' 's/^"""\n\(.*\)\n"""$/"""\1"""/' "$file"
    
    # Remove trivial class/function docstrings
    for pattern in "${PATTERNS[@]}"; do
      escaped_pattern=$(echo "$pattern" | sed 's/\//\\\//g')
      sed -i '' "s/$escaped_pattern//g" "$file"
    done
    
    # Remove redundant class docstrings
    sed -i '' 's/class \([A-Za-z0-9_]*\):\n    """\([A-Za-z0-9 _]*\)"""/class \1:/' "$file"
    
    # Clean up extra blank lines
    sed -i '' '/^$/N;/^\n$/D' "$file"
  else
    echo "File $file not found."
  fi
done

echo "Cleanup complete!"