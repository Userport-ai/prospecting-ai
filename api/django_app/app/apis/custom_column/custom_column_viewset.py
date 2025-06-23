import logging
import uuid

from rest_framework import serializers
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.apis.common import TenantScopedViewSet
from app.models import Lead, Account
from app.models.custom_column import (
    CustomColumn, LeadCustomColumnValue, AccountCustomColumnValue,
    CustomColumnDependency
)
from app.models.serializers.custom_column_serializer import (
    CustomColumnSerializer, LeadCustomColumnValueSerializer, AccountCustomColumnValueSerializer,
    DependencySerializer
)
from app.permissions import HasRole, UserRole
from app.services.dependency_graph_service import DependencyGraphService
from app.utils.custom_column_utils import (
    get_entity_context_data, get_column_config, trigger_custom_column_generation
)

logger = logging.getLogger(__name__)


class CustomColumnDependencyViewSet(TenantScopedViewSet):
    """ViewSet for managing dependencies between custom columns."""
    
    queryset = CustomColumnDependency.objects.all()
    serializer_class = DependencySerializer
    
    def get_permissions(self):
        """Return the permissions that this view requires."""
        return [HasRole(allowed_roles=[
            UserRole.TENANT_ADMIN.value,
            UserRole.INTERNAL_ADMIN.value
        ])]
    
    def perform_create(self, serializer):
        """Create a new dependency, checking for cycles."""
        dependent_column = serializer.validated_data['dependent_column']
        required_column = serializer.validated_data['required_column']
        dependent_id = dependent_column.id
        required_id = required_column.id
        
        # Log the dependency being created
        logger.debug(f"Creating dependency: {dependent_id} -> {required_id}")
        
        # First, check if columns are the same
        if dependent_id == required_id:
            logger.error(f"Self-reference detected: {dependent_id}")
            raise serializers.ValidationError({
                "error": "A column cannot depend on itself"
            })
        
        # Check if entity types match
        if dependent_column.entity_type != required_column.entity_type:
            logger.error(f"Entity type mismatch: {dependent_column.entity_type} != {required_column.entity_type}")
            raise serializers.ValidationError({
                "error": "Dependencies can only be created between columns of the same entity type"
            })
            
        # Check for direct cycle (A -> B and B -> A)
        reverse_dependency_exists = CustomColumnDependency.objects.filter(
            dependent_column=required_column,
            required_column=dependent_column
        ).exists()
        
        if reverse_dependency_exists:
            logger.error(f"Direct cycle detected: {required_id} -> {dependent_id} already exists")
            raise serializers.ValidationError({
                "error": "This dependency would create a circular reference"
            })
        
        # Check for indirect cycles using the dependency graph service
        if DependencyGraphService.would_create_cycle(str(dependent_id), str(required_id)):
            logger.error(f"Indirect cycle detected between {dependent_id} and {required_id}")
            raise serializers.ValidationError({
                "error": "This dependency would create a circular reference"
            })
        
        # Set tenant from the dependent column
        serializer.validated_data['tenant'] = dependent_column.tenant
        
        # Create the dependency
        logger.debug(f"No cycle detected, creating dependency: {dependent_id} -> {required_id}")
        super().perform_create(serializer)


class CustomColumnViewSet(TenantScopedViewSet):
    """ViewSet for managing CustomColumn."""

    queryset = CustomColumn.objects.all()
    serializer_class = CustomColumnSerializer
    filterset_fields = ['entity_type', 'is_active']
    ordering_fields = ['name', 'created_at', 'last_refresh']

    def get_permissions(self):
        """Return the permissions that this view requires."""
        return [HasRole(allowed_roles=[
            UserRole.TENANT_ADMIN.value,
            UserRole.INTERNAL_ADMIN.value
        ])]

    def perform_create(self, serializer):
        """Create a new custom column."""
        try:
            super().perform_create(serializer)
        except IntegrityError as e:
            # Check if it's a unique constraint violation
            if 'unique constraint' in str(e).lower() or 'duplicate key' in str(e).lower():
                # Log the error
                logger.warning(f"Unique constraint violation when creating custom column: {str(e)}")

                # Raise a custom exception that will be caught by exception handler
                raise serializers.ValidationError({
                    "error": "A custom column with this name already exists for this entity type.",
                    "detail": "Please use a different name for your custom column."
                })
            # Re-raise other IntegrityErrors
            raise

    @action(detail=True, methods=['post'])
    def generate_values(self, request, pk=None):
        """Generate values for this custom column and its dependencies(if asked to)."""
        custom_column = self.get_object()

        # Get entity IDs to process
        entity_ids = request.data.get('entity_ids', [])
        if not entity_ids:
            return Response(
                {"error": "No entity IDs provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if we should process dependencies
        process_dependencies = request.data.get('process_dependencies', False)

        if not process_dependencies:
            # Original single-column logic - keep this as is for backward compatibility
            try:
                # Create a unique request ID for idempotency and job_id
                request_id = str(uuid.uuid4())
                job_id = str(uuid.uuid4())

                # Use atomic transaction for all database operations
                with transaction.atomic():
                    # Update column's last_refresh
                    custom_column.last_refresh = timezone.now()
                    custom_column.save(update_fields=['last_refresh', 'updated_at'])

                # Use the utility function to trigger generation
                results = trigger_custom_column_generation(
                    tenant_id=str(request.tenant.id),
                    column_id=str(custom_column.id),
                    entity_ids=entity_ids,
                    request_id=request_id,
                    job_id=job_id
                )

                if not results:
                    return Response(
                        {"error": "Failed to trigger generation"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                result = results[0]  # We only have one result since we specified column_id

                return Response({
                    "message": "Values generation initiated",
                    "job_id": result.get("job_id", job_id),
                    "entity_count": len(entity_ids),
                    "request_id": request_id
                })

            except Exception as e:
                # Log the error with traceback
                logger.error(f"Error triggering custom column generation: {str(e)}", exc_info=True)
                return Response(
                    {"error": f"Failed to trigger generation: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            column_ids = request.data.get('column_ids', [])

            # Ensure the current column is in the list
            if str(custom_column.id) not in column_ids:
                column_ids.append(str(custom_column.id))

            # Set up needed parameters
            modified_data = request.data.copy()
            modified_data['column_ids'] = column_ids
            modified_data['entity_type'] = custom_column.entity_type

            # Create a modified request object
            modified_request = type('ModifiedRequest', (), {})()
            modified_request.data = modified_data
            modified_request.tenant = request.tenant

            # Call the existing method
            return self.generate_with_dependencies(modified_request)

    @action(detail=False, methods=['post'], url_path='generate-values')
    def generate_values_collection(self, request):
        """
        Generate values for multiple columns respecting dependencies.

        This endpoint routes to the existing generate_with_dependencies method
        for backward compatibility and minimal code changes.
        """
        # Simply delegate to the existing method
        return self.generate_with_dependencies(request)

    def generate_with_dependencies(self, request):
        """
        Generate values for multiple columns respecting dependencies.

        Parameters:
            entity_ids: List of entity IDs to process
            column_ids: Optional list of column IDs to process
            entity_type: Optional entity type (used if column_ids not provided)
            batch_size: Batch size for processing (default: 10)
        """
        # Get required parameters
        entity_ids = request.data.get('entity_ids', [])
        column_ids = request.data.get('column_ids', [])
        entity_type = request.data.get('entity_type')
        batch_size = request.data.get('batch_size', 10)

        if not entity_ids:
            return Response(
                {"error": "No entity IDs provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not column_ids and not entity_type:
            return Response(
                {"error": "Either column_ids or entity_type must be provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get initial column set
            if column_ids:
                # Convert to strings for consistency
                column_ids = [str(col_id) for col_id in column_ids]

                # Collect all column IDs, preserving the original order but removing duplicates
                # If a column appears in both original list and as a dependency, the original position is preserved
                all_column_ids = []
                seen = set()

                # Start with the explicitly requested columns (in their original order)
                for col_id in column_ids:
                    if col_id not in seen:
                        all_column_ids.append(col_id)
                        seen.add(col_id)

                # Then add any additional dependencies that weren't in the original list
                for col_id in column_ids:
                    # Get all prerequisites for this column
                    dependencies = DependencyGraphService.get_all_dependencies(col_id)

                    logger.debug("Dependencies for column %s: %s", col_id, dependencies)

                    # Add dependencies if they haven't been seen before
                    for dep_id in dependencies:
                        if dep_id not in seen:
                            all_column_ids.append(dep_id)
                            seen.add(dep_id)

                    # Use the expanded list with duplicates removed
                    logger.info(f"Expanded column list from {len(column_ids)} to {len(all_column_ids)} columns")
                    column_ids = all_column_ids

                # Get the columns from the database
                columns = CustomColumn.objects.filter(
                    id__in=column_ids,
                    tenant=request.tenant
                )
                logger.debug("Columns to process: %s", columns)
            else:
                # Get all active columns for the entity type
                columns = CustomColumn.objects.filter(
                    tenant=request.tenant,
                    entity_type=entity_type,
                    is_active=True,
                    deleted_at__isnull=True
                )

            if not columns.exists():
                return Response(
                    {"message": "No columns found to generate values for"},
                    status=status.HTTP_200_OK
                )

            # Sort the columns based on their dependencies
            sorted_columns = list(columns)
            try:
                sorted_column_ids = DependencyGraphService.topological_sort(
                    [str(c.id) for c in columns]
                )
                # Convert back to model instances
                id_to_column = {str(c.id): c for c in columns}
                sorted_columns = [id_to_column[col_id] for col_id in sorted_column_ids if col_id in id_to_column]
            except Exception as e:
                logger.error(f"Error sorting columns by dependencies: {str(e)}")
                # Continue with unsorted columns if there was an error

            # Make sure we have at least one column
            if not sorted_columns:
                return Response(
                    {"message": "No valid columns found after dependency sorting"},
                    status=status.HTTP_200_OK
                )

            # Create a unique request ID for tracking
            request_id = str(uuid.uuid4())

            # Update last_refresh for all columns
            with transaction.atomic():
                now = timezone.now()
                for col in sorted_columns:
                    col.last_refresh = now
                    col.save(update_fields=['last_refresh', 'updated_at'])

            # Get the first column and remaining columns
            first_column = sorted_columns[0]
            remaining_columns = sorted_columns[1:]

            # Create orchestration data for the first column
            orchestration_data = {
                'next_columns': [str(c.id) for c in remaining_columns],
                'entity_ids': entity_ids,
                'batch_size': batch_size,
                'tenant_id': str(request.tenant.id),
                'request_id': request_id
            }

            # Generate the first column with orchestration data
            job_id = str(uuid.uuid4())
            results = trigger_custom_column_generation(
                tenant_id=str(request.tenant.id),
                column_id=str(first_column.id),
                entity_ids=entity_ids,
                batch_size=batch_size,
                orchestration_data=orchestration_data,
                request_id=request_id,
                job_id=job_id
            )

            return Response({
                "message": f"Started dependency-aware generation for {len(sorted_columns)} columns",
                "columns": [str(c.id) for c in sorted_columns],
                "first_column": str(first_column.id),
                "total_columns": len(sorted_columns),
                "entity_count": len(entity_ids),
                "request_id": request_id,
                "results": results
            })

        except Exception as e:
            logger.error(f"Error in dependency-aware column generation: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to start generation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class LeadCustomColumnValueViewSet(TenantScopedViewSet):
    """ViewSet for managing LeadCustomColumnValue."""

    queryset = LeadCustomColumnValue.objects.all()
    serializer_class = LeadCustomColumnValueSerializer
    filterset_fields = ['column', 'lead', 'status']
    ordering_fields = ['generated_at']

    def get_permissions(self):
        """Return the permissions that this view requires."""
        return [HasRole(allowed_roles=[
            UserRole.USER.value,
            UserRole.TENANT_ADMIN.value,
            UserRole.INTERNAL_ADMIN.value,
            UserRole.INTERNAL_CS.value
        ])]


class AccountCustomColumnValueViewSet(TenantScopedViewSet):
    """ViewSet for managing AccountCustomColumnValue."""

    queryset = AccountCustomColumnValue.objects.all()
    serializer_class = AccountCustomColumnValueSerializer
    filterset_fields = ['column', 'account', 'status']
    ordering_fields = ['generated_at']

    def get_permissions(self):
        """Return the permissions that this view requires."""
        return [HasRole(allowed_roles=[
            UserRole.USER.value,
            UserRole.TENANT_ADMIN.value,
            UserRole.INTERNAL_ADMIN.value,
            UserRole.INTERNAL_CS.value
        ])]