"""
Tests for custom column dependencies.

This script tests the dependency graph functionality with or without Django unit test framework.

Run with:
python manage.py test app.tests.test_column_dependencies
-- OR --
python manage.py shell < app/manual_tests/test_dependency_graph.py
"""

import uuid
from django.test import TestCase
from django.db import transaction
from app.models.custom_column import CustomColumn, CustomColumnDependency
from app.services.dependency_graph_service import DependencyGraphService
from app.models import Tenant, User
from django.db import transaction

class DependencyGraphServiceTests(TestCase):
    """Tests for the dependency graph service."""

    def setUp(self):
        """Set up test environment."""
        self.tenant = Tenant.objects.create(name="Test Tenant")
        
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
        
        self.column_d = CustomColumn.objects.create(
            tenant=self.tenant,
            entity_type=CustomColumn.EntityType.ACCOUNT,
            name="Column D",
            description="Another column that depends on A",
            question="What is D based on A?",
            response_type=CustomColumn.ResponseType.STRING,
            response_config={"max_length": 100},
            ai_config={"model": "gpt-4"}
        )
        
        # Create dependencies: B depends on A, C depends on B, D depends on A
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
        
        self.dep_d_a = CustomColumnDependency.objects.create(
            tenant=self.tenant,
            dependent_column=self.column_d,
            required_column=self.column_a
        )

    def test_get_dependencies(self):
        """Test getting direct dependencies."""
        deps = DependencyGraphService.get_dependencies(str(self.column_b.id))
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0], str(self.column_a.id))
        
        deps = DependencyGraphService.get_dependencies(str(self.column_a.id))
        self.assertEqual(len(deps), 0)

    def test_get_dependents(self):
        """Test getting direct dependents."""
        deps = DependencyGraphService.get_dependents(str(self.column_a.id))
        self.assertEqual(len(deps), 2)
        self.assertTrue(str(self.column_b.id) in deps)
        self.assertTrue(str(self.column_d.id) in deps)

    def test_get_all_dependencies(self):
        """Test getting all dependencies (direct and indirect)."""
        all_deps = DependencyGraphService.get_all_dependencies(str(self.column_c.id))
        self.assertEqual(len(all_deps), 2)
        self.assertTrue(str(self.column_a.id) in all_deps)
        self.assertTrue(str(self.column_b.id) in all_deps)

    def test_get_all_dependents(self):
        """Test getting all dependents (direct and indirect)."""
        all_deps = DependencyGraphService.get_all_dependents(str(self.column_a.id))
        self.assertEqual(len(all_deps), 3)
        self.assertTrue(str(self.column_b.id) in all_deps)
        self.assertTrue(str(self.column_c.id) in all_deps)
        self.assertTrue(str(self.column_d.id) in all_deps)

    def test_would_create_cycle(self):
        """Test cycle detection."""
        # Topological order: A, D, B, C
        # This would create a cycle: A -> B -> C -> A
        would_cycle = DependencyGraphService.would_create_cycle(str(self.column_a.id), str(self.column_c.id))
        self.assertTrue(would_cycle)
        
        # This wouldn't create a cycle
        column_e = CustomColumn.objects.create(
            tenant=self.tenant,
            entity_type=CustomColumn.EntityType.ACCOUNT,
            name="Column E",
            description="New column",
            question="What is E?",
            response_type=CustomColumn.ResponseType.STRING,
            response_config={"max_length": 100},
            ai_config={"model": "gpt-4"}
        )
        
        would_cycle = DependencyGraphService.would_create_cycle(str(column_e.id), str(self.column_a.id))
        self.assertFalse(would_cycle)

    def test_topological_sort(self):
        """Test topological sorting of columns."""
        column_ids = [
            str(self.column_a.id),
            str(self.column_b.id),
            str(self.column_c.id),
            str(self.column_d.id)
        ]
        
        sorted_ids = DependencyGraphService.topological_sort(column_ids)
        
        # Check that dependencies come before dependents
        a_idx = sorted_ids.index(str(self.column_a.id))
        b_idx = sorted_ids.index(str(self.column_b.id))
        c_idx = sorted_ids.index(str(self.column_c.id))
        d_idx = sorted_ids.index(str(self.column_d.id))
        
        # A should come before B
        self.assertTrue(a_idx < b_idx)
        
        # B should come before C
        self.assertTrue(b_idx < c_idx)
        
        # A should come before D
        self.assertTrue(a_idx < d_idx)

    def test_create_cycle_prevention(self):
        """Test that creating a cycle is prevented at the model level."""
        with self.assertRaises(Exception):
            # Try to create a cycle
            with transaction.atomic():
                dependency = CustomColumnDependency(
                    tenant=self.tenant,
                    dependent_column=self.column_a,
                    required_column=self.column_c
                )
                dependency.full_clean()  # This should raise the validation error
                dependency.save()

# Allow running as a standalone script
if __name__ == "__main__":
    print("Starting manual test of dependency graph...")

    # Find or create a tenant
    tenant = Tenant.objects.first()
    if not tenant:
        tenant = Tenant.objects.create(name="Test Tenant")
        print(f"Created test tenant: {tenant.name}")
    else:
        print(f"Using existing tenant: {tenant.name}")

    # Clean up any previous test columns
    CustomColumnDependency.objects.filter(
        dependent_column__name__startswith="Test Dep"
    ).delete()

    CustomColumn.objects.filter(
        name__startswith="Test Dep"
    ).delete()

    # Generate unique suffixes for this test run
    import random
    test_suffix = f"{random.randint(1000, 9999)}"
    print(f"Creating test columns with suffix {test_suffix}...")

    # Create test columns with a clear dependency chain
    column_a = CustomColumn.objects.create(
        tenant=tenant,
        entity_type=CustomColumn.EntityType.ACCOUNT,
        name=f"Test Dep A {test_suffix}",
        description="First column with no dependencies",
        question="What is A?",
        response_type=CustomColumn.ResponseType.STRING,
        response_config={"max_length": 100},
        ai_config={"model": "gpt-4"}
    )

    column_b = CustomColumn.objects.create(
        tenant=tenant,
        entity_type=CustomColumn.EntityType.ACCOUNT,
        name=f"Test Dep B {test_suffix}",
        description="Second column that depends on A",
        question="What is B based on A?",
        response_type=CustomColumn.ResponseType.STRING,
        response_config={"max_length": 100},
        ai_config={"model": "gpt-4"}
    )

    column_c = CustomColumn.objects.create(
        tenant=tenant,
        entity_type=CustomColumn.EntityType.ACCOUNT,
        name=f"Test Dep C {test_suffix}",
        description="Third column that depends on B",
        question="What is C based on B?",
        response_type=CustomColumn.ResponseType.STRING,
        response_config={"max_length": 100},
        ai_config={"model": "gpt-4"}
    )

    column_d = CustomColumn.objects.create(
        tenant=tenant,
        entity_type=CustomColumn.EntityType.ACCOUNT,
        name=f"Test Dep D {test_suffix}",
        description="Fourth column that depends on both A and B",
        question="What is D based on A and B?",
        response_type=CustomColumn.ResponseType.STRING,
        response_config={"max_length": 100},
        ai_config={"model": "gpt-4"}
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

    dep_d_a = CustomColumnDependency.objects.create(
        tenant=tenant,
        dependent_column=column_d,
        required_column=column_a
    )

    dep_d_b = CustomColumnDependency.objects.create(
        tenant=tenant,
        dependent_column=column_d,
        required_column=column_b
    )

    print("Testing dependency graph services...")

    print("\nGetting direct dependencies for column B:")
    deps = DependencyGraphService.get_dependencies(str(column_b.id))
    print(f"Dependencies: {deps}")

    print("\nGetting direct dependencies for column D:")
    deps = DependencyGraphService.get_dependencies(str(column_d.id))
    print(f"Dependencies: {deps}")

    print("\nGetting direct dependents for column A:")
    deps = DependencyGraphService.get_dependents(str(column_a.id))
    print(f"Dependents: {deps}")

    print("\nGetting all dependencies for column C:")
    deps = DependencyGraphService.get_all_dependencies(str(column_c.id))
    print(f"All dependencies: {deps}")

    print("\nTesting topological sort:")
    column_ids = [
        str(column_c.id),
        str(column_a.id),
        str(column_d.id),
        str(column_b.id),
    ]
    print(f"Before sorting: {column_ids}")

    sorted_ids = DependencyGraphService.topological_sort(column_ids)
    print(f"After sorting: {sorted_ids}")

    print("\nTesting cycle detection:")
    print("Would creating D->C create a cycle?")
    would_cycle = DependencyGraphService.would_create_cycle(str(column_d.id), str(column_c.id))
    print(f"Would create cycle: {would_cycle}")

    print("Would creating A->D create a cycle?")
    would_cycle = DependencyGraphService.would_create_cycle(str(column_a.id), str(column_d.id))
    print(f"Would create cycle: {would_cycle}")

    print("\nTrying to create a cycle (this should fail):")
    try:
        with transaction.atomic():
            # Create the dependency instance but don't save it yet
            dep_c_d = CustomColumnDependency(
                tenant=tenant,
                dependent_column=column_c,
                required_column=column_d,
                created_by='test_user',
            )
            # Explicitly call full_clean which will trigger validation
            dep_c_d.full_clean()
            # Only save if validation passes
            dep_c_d.save()
            print("WARNING: Created a dependency that should have formed a cycle!")
    except Exception as e:
        print(f"Expected error: {str(e)}")

    print("\nManual test complete!")