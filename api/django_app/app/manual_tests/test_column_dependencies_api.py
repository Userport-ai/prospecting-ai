"""
Tests for custom column dependencies API.

This script provides both Django unit test classes and manual test functions
for testing the custom column dependencies API.

Run with:
python manage.py test app.tests.test_column_dependencies_api
-- OR --
python manage.py shell < app/manual_tests/test_column_dependencies_api.py
"""

import json
import uuid
import requests
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from app.models.custom_column import CustomColumn, CustomColumnDependency
from app.models import Tenant, User, Product, Account
from app.models.users import UserRole


class ColumnDependencyAPITests(TestCase):
    """Tests for the column dependency API endpoints."""

    def setUp(self):
        """Set up test environment."""
        self.client = APIClient()
        
        # Create test tenant
        self.tenant = Tenant.objects.create(name="Test Tenant")
        
        # Create admin user for testing
        self.user = User.objects.create(
            email="test@example.com",
            role=UserRole.INTERNAL_ADMIN.value,
            tenant=self.tenant
        )
        
        # Authenticate the client
        self.client.force_authenticate(user=self.user)
        
        # Create test columns
        self.column_a = CustomColumn.objects.create(
            tenant=self.tenant,
            entity_type=CustomColumn.EntityType.ACCOUNT,
            name="Column A",
            description="First column with no dependencies",
            question="What is A?",
            response_type=CustomColumn.ResponseType.STRING,
            response_config={"max_length": 100},
            ai_config={"model": "gpt-4"}
        )
        
        self.column_b = CustomColumn.objects.create(
            tenant=self.tenant,
            entity_type=CustomColumn.EntityType.ACCOUNT,
            name="Column B",
            description="Second column",
            question="What is B?",
            response_type=CustomColumn.ResponseType.STRING,
            response_config={"max_length": 100},
            ai_config={"model": "gpt-4"}
        )

    def test_create_dependency(self):
        """Test creating a dependency through the API."""
        url = reverse('column-dependencies-list')
        data = {
            'dependent_column': str(self.column_b.id),
            'required_column': str(self.column_a.id)
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        
        # Verify dependency was created
        deps = CustomColumnDependency.objects.filter(
            dependent_column=self.column_b,
            required_column=self.column_a
        )
        self.assertEqual(deps.count(), 1)
    
    def test_prevent_cycle(self):
        """Test that creating a cycle is prevented through the API."""
        # First create B depends on A
        dep = CustomColumnDependency.objects.create(
            tenant=self.tenant,
            dependent_column=self.column_b,
            required_column=self.column_a
        )
        
        # Now try to create A depends on B (would create a cycle)
        url = reverse('column-dependencies-list')
        data = {
            'dependent_column': str(self.column_a.id),
            'required_column': str(self.column_b.id)
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('circular reference', response.data.get('error', ''))
    
    def test_get_dependencies(self):
        """Test getting dependencies for a column."""
        # Create dependency
        dep = CustomColumnDependency.objects.create(
            tenant=self.tenant,
            dependent_column=self.column_b,
            required_column=self.column_a
        )
        
        # Test the endpoint
        url = reverse('custom-columns-dependencies', args=[self.column_b.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['direct_dependencies']), 1)
        self.assertEqual(response.data['direct_dependencies'][0]['id'], str(self.column_a.id))
    
    def test_get_dependents(self):
        """Test getting dependents for a column."""
        # Create dependency
        dep = CustomColumnDependency.objects.create(
            tenant=self.tenant,
            dependent_column=self.column_b,
            required_column=self.column_a
        )
        
        # Test the endpoint
        url = reverse('custom-columns-dependents', args=[self.column_a.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['direct_dependents']), 1)
        self.assertEqual(response.data['direct_dependents'][0]['id'], str(self.column_b.id))


class GenerateWithDependenciesTests(TestCase):
    """Tests for the generate-with-dependencies API endpoint."""

    def setUp(self):
        self.client = APIClient()

        # Create test tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            website="https://test-tenant.example.com"  # Required field
        )

        # Create admin user for testing
        self.user = User.objects.create(
            email="test@example.com",
            role=UserRole.INTERNAL_ADMIN.value,
            tenant=self.tenant
        )

        # Create a test product (required for Account)
        self.product = Product.objects.create(
            tenant=self.tenant,
            name="Test Product",
            description="Test product description",
            persona_role_titles={}  # Required field - empty dict is fine for testing
        )

        # Create a test account
        self.account = Account.objects.create(
            tenant=self.tenant,
            product=self.product,
            name="Test Account"
        )

        # Authenticate the client
        self.client.force_authenticate(user=self.user)

        # Set tenant ID in headers
        self.client.credentials(HTTP_X_TENANT_ID=str(self.tenant.id))

        # Create test columns with dependencies: A <- B <- C
        self.column_a = CustomColumn.objects.create(
            tenant=self.tenant,
            entity_type=CustomColumn.EntityType.ACCOUNT,
            name="Column A",
            description="First column with no dependencies",
            question="What is A?",
            response_type=CustomColumn.ResponseType.STRING,
            response_config={"max_length": 100},
            ai_config={"model": "gpt-4"}
        )

        self.column_b = CustomColumn.objects.create(
            tenant=self.tenant,
            entity_type=CustomColumn.EntityType.ACCOUNT,
            name="Column B",
            description="Second column that depends on A",
            question="What is B based on A?",
            response_type=CustomColumn.ResponseType.STRING,
            response_config={"max_length": 100},
            ai_config={"model": "gpt-4"}
        )

        self.column_c = CustomColumn.objects.create(
            tenant=self.tenant,
            entity_type=CustomColumn.EntityType.ACCOUNT,
            name="Column C",
            description="Third column that depends on B",
            question="What is C based on B?",
            response_type=CustomColumn.ResponseType.STRING,
            response_config={"max_length": 100},
            ai_config={"model": "gpt-4"}
        )

        # Create dependencies
        self.dep_b_a = CustomColumnDependency.objects.create(
            tenant=self.tenant,
            dependent_column=self.column_b,
            required_column=self.column_a
        )

        self.dep_c_b = CustomColumnDependency.objects.create(
            tenant=self.tenant,
            dependent_column=self.column_c,
            required_column=self.column_b
        )


    def test_generate_with_dependencies_endpoint(self):
        """Test the generate with dependencies endpoint."""
        # This test only checks that the endpoint works, not the actual generation
        url = reverse('custom-columns-generate-with-dependencies')
        
        data = {
            'entity_ids': [str(self.account.id)],  # A random entity ID
            'entity_type': CustomColumn.EntityType.ACCOUNT,
            'column_ids': [
                str(self.column_a.id),
                str(self.column_b.id),
                str(self.column_c.id)
            ]
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        
        # Verify columns were sorted correctly in dependency order
        first_column = response.data.get('first_column')
        self.assertEqual(first_column, str(self.column_a.id))
        
        # Columns should be in order: A, B, C
        columns = response.data.get('columns', [])
        self.assertEqual(len(columns), 3)
        self.assertEqual(columns[0], str(self.column_a.id))
        self.assertEqual(columns[1], str(self.column_b.id))
        self.assertEqual(columns[2], str(self.column_c.id))


# E2E Test Functions for manual testing against a running server
# These functions can be run against a local or deployed instance

def api_request(method, endpoint, data=None, base_url="http://localhost:8000/api/v2", headers=None):
    """Make an API request and handle errors."""
    url = f"{base_url}/{endpoint}"
    
    if headers is None:
        # Replace with valid token and tenant for your environment
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer YOUR_TOKEN_HERE",
            "X-Tenant-ID": "YOUR_TENANT_ID_HERE"
        }
    
    if method.lower() == "get":
        response = requests.get(url, headers=headers)
    elif method.lower() == "post":
        response = requests.post(url, headers=headers, json=data)
    elif method.lower() == "put":
        response = requests.put(url, headers=headers, json=data)
    elif method.lower() == "delete":
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")
    
    # Check for errors
    if response.status_code >= 400:
        print(f"API Error ({response.status_code}): {response.text}")
        return None
    
    # Parse JSON response
    try:
        return response.json()
    except:
        print(f"Error parsing JSON: {response.text}")
        return None

def create_test_column(name, entity_type, response_type, headers=None):
    """Create a test custom column."""
    # Generate a random suffix to ensure uniqueness
    suffix = str(uuid.uuid4())[:8]
    full_name = f"{name} {suffix}"
    
    column_data = {
        "name": full_name,
        "description": f"Test column: {full_name}",
        "question": f"What is {full_name}?",
        "entity_type": entity_type,
        "response_type": response_type,
        "context_type": ["entity_profile"],
        "ai_config": {
            "model": "gemini-2.5-pro",
            "temperature": 0.2
        }
    }
    
    # Add response_config based on response_type
    if response_type == "string":
        column_data["response_config"] = {"max_length": 500}
    elif response_type == "enum":
        column_data["response_config"] = {"allowed_values": ["High", "Medium", "Low", "Unknown"]}
    elif response_type == "boolean":
        column_data["response_config"] = {"true_label": "Yes", "false_label": "No"}
    elif response_type == "number":
        column_data["response_config"] = {"min": 0, "max": 100}
    elif response_type == "json_object":
        column_data["response_config"] = {"schema": {"type": "object", "properties": {}}}
    
    # Create the column
    print(f"Creating column: {full_name}")
    result = api_request("post", "custom_columns/", column_data, headers=headers)
    
    if result:
        print(f"Created column: {result['id']} - {result['name']}")
        return result
    return None

def create_dependency(dependent_column_id, required_column_id, headers=None):
    """Create a dependency between two columns."""
    dependency_data = {
        "dependent_column": dependent_column_id,
        "required_column": required_column_id
    }
    
    print(f"Creating dependency: {dependent_column_id} -> {required_column_id}")
    result = api_request("post", "column_dependencies/", dependency_data, headers=headers)
    
    if result:
        print(f"Created dependency: {result['id']}")
        return result
    return None

def get_dependencies(column_id, headers=None):
    """Get dependencies for a column."""
    endpoint = f"custom_columns/{column_id}/dependencies/"
    result = api_request("get", endpoint, headers=headers)
    
    if result:
        print(f"Dependencies for column {column_id}:")
        print("Direct dependencies:")
        for dep in result["direct_dependencies"]:
            print(f"  - {dep['id']} ({dep['name']})")
        print("All dependencies:")
        for dep in result["all_dependencies"]:
            print(f"  - {dep['id']} ({dep['name']})")
        return result
    return None

def get_dependents(column_id, headers=None):
    """Get dependents for a column."""
    endpoint = f"custom_columns/{column_id}/dependents/"
    result = api_request("get", endpoint, headers=headers)
    
    if result:
        print(f"Dependents for column {column_id}:")
        print("Direct dependents:")
        for dep in result["direct_dependents"]:
            print(f"  - {dep['id']} ({dep['name']})")
        print("All dependents:")
        for dep in result["all_dependents"]:
            print(f"  - {dep['id']} ({dep['name']})")
        return result
    return None

def generate_with_dependencies(column_ids, entity_ids, entity_type, headers=None):
    """Generate values for columns respecting dependencies."""
    generation_data = {
        "column_ids": column_ids,
        "entity_ids": entity_ids,
        "entity_type": entity_type,
        "batch_size": 10
    }
    
    print(f"Generating values with dependencies for {len(column_ids)} columns and {len(entity_ids)} entities")
    result = api_request("post", "custom_columns/generate-with-dependencies/", generation_data, headers=headers)
    
    if result:
        print(f"Generation started:")
        print(f"  First column: {result['first_column']}")
        print(f"  All columns: {', '.join(result['columns'])}")
        return result
    return None

def test_cycle_detection(headers=None):
    """Test that cycle detection prevents circular dependencies."""
    print("\nTesting cycle detection:")
    
    # Create three test columns
    column_a = create_test_column("Cycle Test A", "account", "string", headers=headers)
    column_b = create_test_column("Cycle Test B", "account", "string", headers=headers)
    column_c = create_test_column("Cycle Test C", "account", "string", headers=headers)
    
    if not column_a or not column_b or not column_c:
        print("Failed to create test columns for cycle detection")
        return
    
    # Create dependencies: A -> B -> C
    dep_a_b = create_dependency(column_b["id"], column_a["id"], headers=headers)
    dep_b_c = create_dependency(column_c["id"], column_b["id"], headers=headers)
    
    # Verify dependencies were created
    if not dep_a_b or not dep_b_c:
        print("Failed to create dependencies for cycle detection")
        return
    
    # Try to create C -> A (would form a cycle)
    print("\nAttempting to create a cycle C -> A")
    response = api_request("post", "column_dependencies/", {
        "dependent_column": column_a["id"],
        "required_column": column_c["id"]
    }, headers=headers)
    
    if response:
        print("WARNING: Created a cycle - cycle detection failed!")
    else:
        print("Success: Cycle detection prevented the circular dependency")
    
    return column_a, column_b, column_c

def run_e2e_test(headers=None):
    """Run a complete end-to-end test of column dependencies."""
    print("Starting end-to-end test of column dependencies API")
    
    # Test 1: Create columns and dependencies
    print("\n--- Test 1: Create columns and dependencies ---")
    column_a = create_test_column("E2E Test A", "account", "string", headers=headers)
    column_b = create_test_column("E2E Test B", "account", "enum", headers=headers)
    column_c = create_test_column("E2E Test C", "account", "boolean", headers=headers)
    
    if not column_a or not column_b or not column_c:
        print("Failed to create test columns")
        return
    
    # Create dependencies
    dep_b_a = create_dependency(column_b["id"], column_a["id"], headers=headers)
    dep_c_b = create_dependency(column_c["id"], column_b["id"], headers=headers)
    
    # Test 2: Get dependencies and dependents
    print("\n--- Test 2: Get dependencies and dependents ---")
    deps_c = get_dependencies(column_c["id"], headers=headers)
    deps_a = get_dependents(column_a["id"], headers=headers)
    
    # Test 3: Test cycle detection
    print("\n--- Test 3: Test cycle detection ---")
    cycle_test_columns = test_cycle_detection(headers=headers)
    
    # Test 4: Generate with dependencies
    print("\n--- Test 4: Test generation with dependencies ---")
    # Replace with actual entity IDs from your system
    test_entity_ids = ["73e8fa48-858d-4ab7-9e08-1c56e7d9f93c"]
    
    generate_result = generate_with_dependencies(
        [column_a["id"], column_b["id"], column_c["id"]], 
        test_entity_ids, 
        "account",
        headers=headers
    )
    
    print("\nEnd-to-end test complete!")

# Run as standalone script
if __name__ == "__main__":
    print("Running E2E test for custom column dependencies API...")
    print("Warning: This test will create test columns in your database.")
    print("Make sure you're running against the correct environment.")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "",
        "X-Tenant-ID": ""
    }
    
    base_url = "http://localhost:8000/api/v2"  # Update with your API URL
    
    # Update the api_request function to use your base_url
    def wrapped_api_request(method, endpoint, data=None):
        return api_request(method, endpoint, data, base_url, headers)
    
    # Replace api_request with wrapped_api_request in the global scope
    globals()["api_request"] = wrapped_api_request
    
    # Run the E2E test
    run_e2e_test(headers)

    print("\nTo run the test, update the token and tenant ID in this script.")
    print("Then uncomment the test execution code.")