"""
Manual testing script for the custom column generation with dependencies.

This script tests the column generation orchestration with dependencies.

Run with:
python manage.py shell < app/manual_tests/test_column_generation.py
"""

import uuid
import json
import asyncio
from django.utils import timezone
from app.models.custom_column import CustomColumn, CustomColumnDependency
from app.services.dependency_graph_service import DependencyGraphService
from app.utils.custom_column_utils import trigger_custom_column_generation
from app.models import Tenant, Account

print("Starting manual test of column generation with dependencies...")

# Find or create a tenant
tenant = Tenant.objects.first()
if not tenant:
    tenant = Tenant.objects.create(name="Test Tenant")
    print(f"Created test tenant: {tenant.name}")
else:
    print(f"Using existing tenant: {tenant.name}")

# Find or create a test account
account = Account.objects.filter(tenant=tenant).first()
if not account:
    account = Account.objects.create(
        tenant=tenant,
        name="Test Account",
        website="http://example.com",
        linkedin_url="http://linkedin.com/company/example"
    )
    print(f"Created test account: {account.name}")
else:
    print(f"Using existing account: {account.name}")

# Clean up any previous test columns
CustomColumnDependency.objects.filter(
    dependent_column__name__startswith="Orch Test"
).delete()

CustomColumn.objects.filter(
    name__startswith="Orch Test"
).delete()

# Generate unique suffixes for this test run
import random
test_suffix = f"{random.randint(1000, 9999)}"
print(f"Creating test columns with suffix {test_suffix}...")

# Create test columns with a clear dependency chain
column_a = CustomColumn.objects.create(
    tenant=tenant,
    entity_type=CustomColumn.EntityType.ACCOUNT,
    name=f"Orch Test A {test_suffix}",
    description="First column - Company Industry",
    question="What industry is this company in?",
    response_type=CustomColumn.ResponseType.STRING,
    response_config={"max_length": 100},
    ai_config={"model": "gemini"}
)

column_b = CustomColumn.objects.create(
    tenant=tenant,
    entity_type=CustomColumn.EntityType.ACCOUNT,
    name=f"Orch Test B {test_suffix}",
    description="Second column - Industry Growth",
    question="Based on the company's industry from column A, what is the growth rate of this industry?",
    response_type=CustomColumn.ResponseType.STRING,
    response_config={"max_length": 100},
    ai_config={"model": "gemini"}
)

column_c = CustomColumn.objects.create(
    tenant=tenant,
    entity_type=CustomColumn.EntityType.ACCOUNT,
    name=f"Orch Test C {test_suffix}",
    description="Third column - Opportunity Size",
    question="Based on the industry growth rate from column B, what is the opportunity size for our products?",
    response_type=CustomColumn.ResponseType.STRING,
    response_config={"max_length": 100},
    ai_config={"model": "gemini"}
)

print("Creating dependencies...")
# Create dependencies: B depends on A, C depends on B
dep_b_a = CustomColumnDependency.objects.create(
    tenant=tenant,
    dependent_column=column_b,
    required_column=column_a
)

dep_c_b = CustomColumnDependency.objects.create(
    tenant=tenant,
    dependent_column=column_c,
    required_column=column_b
)

print("\nSorting columns by dependencies...")
column_ids = [str(column_c.id), str(column_a.id), str(column_b.id)]
sorted_ids = DependencyGraphService.topological_sort(column_ids)
print(f"Sorted column IDs: {sorted_ids}")

# Convert back to column objects
id_to_column = {str(col.id): col for col in [column_a, column_b, column_c]}
sorted_columns = [id_to_column[col_id] for col_id in sorted_ids]

print(f"Sorted columns: {[col.name for col in sorted_columns]}")

print("\nSetting up orchestration data...")
# Get the first column and remaining columns
first_column = sorted_columns[0]
remaining_columns = sorted_columns[1:]

# Create orchestration data for the first column
orchestration_data = {
    'next_columns': [str(c.id) for c in remaining_columns],
    'entity_ids': [str(account.id)],
    'batch_size': 1,
    'tenant_id': str(tenant.id)
}

print(f"First column: {first_column.name}")
print(f"Next columns: {[col.name for col in remaining_columns]}")
print(f"Orchestration data: {json.dumps(orchestration_data, indent=2)}")

print("\nTriggering first column generation...")
try:
    # We can't run the async function directly in the script, so we just show how it would be called
    print("In a real application, you would call:")
    print(f"trigger_custom_column_generation(\n" +
          f"    tenant_id='{tenant.id}',\n" +
          f"    column_id='{first_column.id}',\n" +
          f"    entity_ids=['{account.id}'],\n" +
          f"    orchestration_data={orchestration_data}\n" + 
          f")")
    
    print("\nNote: In production, when column A's generation is completed," + 
          " the callback handler will detect the orchestration_data " +
          "and trigger column B's generation, and so on.")
    
except Exception as e:
    print(f"Error: {str(e)}")

print("\nManual test setup complete!")
print("To actually run this in production, use the API endpoint:")
print(f"POST /api/custom_columns/generate-with-dependencies/")
print(f"{{")
print(f"  \"entity_ids\": [\"test_account_uuid\"],")
print(f"  \"column_ids\": [{', '.join([f'\"{c.id}\"' for c in [column_a, column_b, column_c]])}]")
print(f"}}")