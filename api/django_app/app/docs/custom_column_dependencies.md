# Custom Column Dependencies

This document explains how to use the custom column dependencies feature to create columns that depend on the values of other columns.

## Overview

Custom column dependencies allow you to define relationships between columns where one column requires the values of another column to be generated first. This enables more complex AI-driven insights that build on each other.

For example:

1. Column A identifies a company's industry
2. Column B (depends on A) analyzes growth trends in that industry
3. Column C (depends on B) recommends sales approaches based on the industry growth trends

The dependencies create a directed acyclic graph (DAG) of columns, which ensures they are generated in the correct order.

## Creating Dependencies

### Via API

To create a dependency between columns, use the `column_dependencies` endpoint:

```
POST /api/column_dependencies/
{
  "dependent_column": "UUID-of-column-that-depends-on-another",
  "required_column": "UUID-of-column-that-must-be-generated-first"
}
```

Example: If Column B depends on Column A, then Column A is the "required_column" and Column B is the "dependent_column".

### Validation and Cycles

The system prevents the creation of cycles in the dependency graph. For example, if:
- B depends on A
- C depends on B

Then creating "A depends on C" would create a cycle (A → B → C → A) and will be rejected.

## Viewing Dependencies

### Get Dependencies for a Column

To see what columns a specific column depends on:

```
GET /api/custom_columns/{column_id}/dependencies/
```

Response:
```json
{
  "direct_dependencies": [
    {
      "id": "UUID",
      "name": "Column A",
      ...
    }
  ],
  "all_dependencies": [
    { ... } // Includes both direct and indirect dependencies
  ]
}
```

### Get Dependents for a Column

To see what columns depend on a specific column:

```
GET /api/custom_columns/{column_id}/dependents/
```

Response:
```json
{
  "direct_dependents": [
    {
      "id": "UUID",
      "name": "Column B",
      ...
    }
  ],
  "all_dependents": [
    { ... } // Includes both direct and indirect dependents
  ]
}
```

## Generating Values with Dependencies

To generate values for multiple columns while respecting their dependencies:

```
POST /api/custom_columns/generate-with-dependencies/
{
  "entity_ids": ["uuid1", "uuid2", ...],
  "column_ids": ["column_uuid1", "column_uuid2", ...]
}
```

Alternatively, you can generate all columns of a specific type:

```
POST /api/custom_columns/generate-with-dependencies/
{
  "entity_ids": ["uuid1", "uuid2", ...],
  "entity_type": "account" // or "lead"
}
```

The system will:

1. Sort the columns based on their dependencies
2. Generate values for the first column (with no dependencies)
3. When that completes, generate values for the next column in the dependency order
4. Continue until all columns are processed

This ensures that each column has access to the values of its dependencies during generation.

## Prompt Usage

When creating a column that depends on other columns, you should reference the dependency columns in your prompt. The values will be available in the context data as:

```
context_data.insights.{column_name}.value
```

For example, if Column B depends on Column A, the prompt for Column B could include:

```
Based on the industry '{context_data.insights.Column A.value}', analyze...
```

The dependency values are automatically included in the context sent to the AI model.

## Best Practices

1. **Keep dependencies simple**: Avoid creating complex dependency chains that are hard to maintain.
2. **Use meaningful column names**: Since column names will be referenced in context, use clear, descriptive names.
3. **Test thoroughly**: After creating dependencies, test the generation to ensure columns correctly use the values from their dependencies.
4. **Consider performance**: Dependent columns must wait for their dependencies to complete, which increases total generation time.
5. **Handle missing values**: Ensure your prompts handle cases where a dependency's value might be missing or low confidence.

## Troubleshooting

- **Cycle detected**: If you receive an error about creating a circular reference, review your dependency relationships to eliminate the cycle.
- **Missing dependency values**: If a column doesn't seem to have access to its dependency values, verify the dependency relationship exists and that the dependent column's generation was triggered after the required column completed.
- **Generation stalling**: If the process appears to stall, check if any columns in the chain failed to generate properly.