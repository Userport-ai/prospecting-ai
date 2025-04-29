"""
Dependency Graph Service for Custom Columns.

This service manages dependency relationships between custom columns,
provides cycle detection, and topological sorting to determine the
order in which columns should be generated.
"""

import logging
from typing import List, Dict, Set, Tuple, Optional

from app.models.custom_column import CustomColumn, CustomColumnDependency

logger = logging.getLogger(__name__)


class DependencyGraphService:
    """Service for managing dependencies between custom columns."""

    @classmethod
    def would_create_cycle(cls, dependent_id: str, required_id: str) -> bool:
        """
        Check if adding the dependency dependent_id -> required_id would
        create a cycle in the graph by checking if a path already exists
        from required_id back to dependent_id using the dependency links.
        """
        logger.debug(f"Checking for cycle: {dependent_id} -> {required_id}")
        # Ensure IDs are strings and lowercase for consistent comparison
        str_dependent_id = str(dependent_id).lower()
        str_required_id = str(required_id).lower()

        # 1. Check for self-dependency
        if str_dependent_id == str_required_id:
            logger.debug(f"Self-dependency detected: {str_dependent_id}")
            return True

        # 2. Check if the exact dependency already exists.
        #    If it exists, adding it again doesn't *create* a new cycle.
        if CustomColumnDependency.objects.filter(
                dependent_column_id=dependent_id,
                required_column_id=required_id,
                deleted_at__isnull=True # Also consider soft-deleted dependencies
        ).exists():
            logger.debug(f"Dependency {dependent_id} -> {required_id} already exists. Not creating a new cycle.")
            return False # Adding existing edge doesn't CREATE a cycle

        # 3. Check for direct reverse dependency (B -> A exists when adding A -> B)
        #    This is an efficient check for the simplest cycle.
        if CustomColumnDependency.objects.filter(
                dependent_column_id=required_id,
                required_column_id=dependent_id,
                deleted_at__isnull=True # Also consider soft-deleted dependencies
        ).exists():
            logger.debug(f"Direct reverse dependency detected: {required_id} -> {dependent_id} exists.")
            return True

        # 4. Check for indirect cycle: Does a path already exist from required_id
        #    back to dependent_id in the *dependency* graph (Dep -> Req)?
        logger.debug(f"Checking for existing dependency path from {str_required_id} to {str_dependent_id}...")

        # Fetch all non-deleted existing dependencies
        all_dependencies_tuples = CustomColumnDependency.objects.filter(
            deleted_at__isnull=True
        ).values_list(
            'dependent_column_id', 'required_column_id'
        )

        # Build the DEPENDENCY graph (Dependent -> list of Required)
        dependency_graph = {} # Maps Dependent -> [Required]
        all_nodes = set()

        for dep_col_id, req_col_id in all_dependencies_tuples:
            # Ensure UUIDs are converted to strings before lowercasing
            s_dep_id = str(dep_col_id).lower()
            s_req_id = str(req_col_id).lower()
            all_nodes.add(s_dep_id)
            all_nodes.add(s_req_id)

            if s_dep_id not in dependency_graph:
                dependency_graph[s_dep_id] = []
            # Map: Dependent -> [Required]
            dependency_graph[s_dep_id].append(s_req_id)


        # Perform DFS starting from required_id, following DEPENDENCY links (Dep -> Req),
        # searching for dependent_id. If we find dependent_id, it means Req -> ... -> Dep path exists.
        visited = set()
        # Start traversal from the node that would be required (required_id)
        stack = [str_required_id]

        while stack:
            current_node = stack.pop()

            # If we reach the node that wants to depend (dependent_id),
            # it means a path required_id -> ... -> dependent_id exists using the
            # chain of dependencies (X depends on Y depends on Z...).
            # Adding the edge dependent_id -> required_id would complete the cycle.
            if current_node == str_dependent_id:
                logger.debug(f"Existing dependency path found from {str_required_id} to {str_dependent_id}. Cycle detected.")
                return True # Found the path that forms a cycle.

            if current_node in visited:
                continue
            visited.add(current_node)

            # Explore nodes that the current_node DEPENDS ON.
            # Follow the edges in the Dep -> [Req] graph.
            if current_node in dependency_graph: # Check if current_node HAS dependencies listed
                # Iterate through nodes that current_node requires (its neighbours in Dep->Req graph)
                for neighbor_required_node in dependency_graph[current_node]:
                    if neighbor_required_node not in visited:
                        stack.append(neighbor_required_node)
            # else: current_node has no dependencies listed in the graph

        # If DFS completes without finding dependent_id
        logger.debug(f"No existing dependency path found from {str_required_id} to {str_dependent_id}. No indirect cycle created.")
        return False

    
    @classmethod
    def get_dependencies(cls, column_id: str) -> List[str]:
        """
        Get IDs of all columns that the specified column directly depends on.
        
        Args:
            column_id: ID of the column
            
        Returns:
            List of column IDs that this column directly depends on
        """
        dependencies = CustomColumnDependency.objects.filter(
            dependent_column_id=column_id
        ).values_list('required_column_id', flat=True)
        
        # Convert UUID objects to strings
        return [str(dep_id) for dep_id in dependencies]
    
    @classmethod
    def get_dependents(cls, column_id: str) -> List[str]:
        """
        Get IDs of all columns that directly depend on the specified column.
        
        Args:
            column_id: ID of the column
            
        Returns:
            List of column IDs that directly depend on this column
        """
        dependents = CustomColumnDependency.objects.filter(
            required_column_id=column_id
        ).values_list('dependent_column_id', flat=True)
        
        # Convert UUID objects to strings
        return [str(dep_id) for dep_id in dependents]
    
    @classmethod
    def get_all_dependencies(cls, column_id: str) -> Set[str]:
        """
        Get IDs of all columns that the specified column depends on,
        directly or indirectly.
        
        Args:
            column_id: ID of the column
            
        Returns:
            Set of column IDs that this column depends on (directly or indirectly)
        """
        all_deps = set()
        visited = set()
        to_visit = [str(column_id)]  # Ensure we're working with strings
        
        while to_visit:
            current = to_visit.pop()
            
            if current in visited:
                continue
                
            visited.add(current)
            
            # Skip the root node in the results
            if current != str(column_id):
                all_deps.add(current)
            
            # Add direct dependencies
            direct_deps = cls.get_dependencies(current)
            to_visit.extend(direct_deps)
        
        return all_deps
    
    @classmethod
    def get_all_dependents(cls, column_id: str) -> Set[str]:
        """
        Get IDs of all columns that depend on the specified column,
        directly or indirectly.
        
        Args:
            column_id: ID of the column
            
        Returns:
            Set of column IDs that depend on this column (directly or indirectly)
        """
        all_deps = set()
        visited = set()
        to_visit = [str(column_id)]  # Ensure we're working with strings
        
        while to_visit:
            current = to_visit.pop()
            
            if current in visited:
                continue
                
            visited.add(current)
            
            # Skip the root node in the results
            if current != str(column_id):
                all_deps.add(current)
            
            # Add direct dependents
            direct_deps = cls.get_dependents(current)
            to_visit.extend(direct_deps)
        
        return all_deps
    
    @classmethod
    def build_dependency_graph(cls, column_ids: List[str]) -> Dict[str, List[str]]:
        """
        Build a dependency graph for the given column IDs.
        
        Args:
            column_ids: List of column IDs to include in the graph
            
        Returns:
            Dictionary mapping column IDs to lists of their dependencies
        """
        # Ensure all column_ids are strings
        str_column_ids = [str(col_id) for col_id in column_ids]
        graph = {col_id: [] for col_id in str_column_ids}
        
        # Get all dependencies for each column
        for col_id in str_column_ids:
            deps = cls.get_dependencies(col_id)
            # Only include dependencies that are in our column_ids list
            graph[col_id] = [dep for dep in deps if dep in str_column_ids]
        
        return graph
    
    @classmethod
    def topological_sort(cls, column_ids: List[str]) -> List[str]:
        """
        Sort columns in topological order (dependencies first).
        
        Args:
            column_ids: List of column IDs to sort
            
        Returns:
            List of column IDs in topological order (dependencies first)
            
        Raises:
            ValueError: If the graph contains a cycle
        """
        # Build dependency graph
        graph = cls.build_dependency_graph(column_ids)
        
        # Track visited status for each node
        visited = {node: False for node in graph}
        temp_visited = {node: False for node in graph}
        
        sorted_columns = []
        
        def dfs(node):
            # If node is temporarily visited, we've found a cycle
            if temp_visited[node]:
                cycle_path = []
                for k, v in temp_visited.items():
                    if v:
                        cycle_path.append(k)
                logger.error(f"Dependency cycle detected: {', '.join(cycle_path)}")
                raise ValueError(f"Dependency cycle detected among columns: {', '.join(cycle_path)}")
            
            # If node hasn't been visited yet
            if not visited[node]:
                # Mark as temporarily visited
                temp_visited[node] = True
                
                # Visit all dependencies first
                for dep in graph[node]:
                    dfs(dep)
                
                # Mark as permanently visited
                visited[node] = True
                temp_visited[node] = False
                
                # Add to result
                sorted_columns.append(node)
        
        # Visit all nodes
        for node in graph:
            if not visited[node]:
                dfs(node)
        
        # Reverse to get correct order (dependencies first)
        return list(sorted_columns)
    
    @classmethod
    def get_missing_dependencies(cls, column_id: str, available_values: List[str]) -> List[str]:
        """
        Get dependencies of a column that don't have values available.
        
        Args:
            column_id: ID of the column to check
            available_values: List of column IDs that have values available
            
        Returns:
            List of dependency column IDs that don't have values available
        """
        # Ensure column_id is a string
        str_column_id = str(column_id)
        
        # Ensure all available_values are strings
        str_available_values = [str(val) for val in available_values]
        
        dependencies = cls.get_dependencies(str_column_id)
        return [dep for dep in dependencies if dep not in str_available_values]