"""
Dependency Analyzer for determining optimal file build order.

This module analyzes file dependencies (imports) and de        # Clean up imports (remove relative path indicators)
        cleaned_imports = []
        for imp in imports:
            # Store original for later
            original_imp = imp
            
            # Remove leading ./ and ../ but preserve the rest
            while imp.startswith('./') or imp.startswith('../'):
                if imp.startswith('./'):
                    imp = imp[2:]
                elif imp.startswith('../'):
                    imp = imp[3:]
            
            # Remove file extensions only from end of string
            if imp.endswith('.py'):
                imp = imp[:-3]
            elif imp.endswith('.js'):
                imp = imp[:-3]
            elif imp.endswith('.ts'):
                imp = imp[:-3]
            elif imp.endswith('.jsx'):
                imp = imp[:-4]
            elif imp.endswith('.tsx'):
                imp = imp[:-4]
            # Keep .css for asset imports
            
            cleaned_imports.append(imp)ect
build order using topological sorting. Ensures files are built in the right
order to avoid compilation/import errors.

Features:
- Import statement parsing (Python, JS, TS)
- Dependency graph construction
- Topological sort with cycle detection
- Batch grouping for parallel execution
- Circular dependency detection and breaking
"""

import re
import logging
from typing import Dict, List, Set, Tuple, Optional, Any, Union
from pathlib import Path
from collections import defaultdict, deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FileDependency:
    """Represents a file and its dependencies."""
    
    file_path: str
    title: str
    description: str
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    depends_on: Set[str] = field(default_factory=set)
    required_by: Set[str] = field(default_factory=set)
    batch_level: int = -1  # -1 = not assigned yet
    
    def __hash__(self):
        return hash(self.file_path)
    
    def __eq__(self, other):
        return self.file_path == other.file_path


@dataclass
class DependencyBatch:
    """A batch of files that can be built in parallel."""
    
    level: int
    files: List[FileDependency]
    estimated_time: float = 0.0  # Estimated build time in seconds
    
    def __repr__(self):
        return f"Batch {self.level}: {len(self.files)} files"


class DependencyAnalyzer:
    """
    Analyzes task dependencies and determines optimal execution order.
    
    Key Features:
    - Multi-language import parsing (Python, JavaScript, TypeScript)
    - Topological sort for correct build order
    - Circular dependency detection
    - Parallel batch grouping
    - Smart dependency breaking for cycles
    """
    
    # Import patterns for different languages
    PYTHON_IMPORT_PATTERNS = [
        r'^import\s+([\w.]+)',  # import module
        r'^from\s+([\w.]+)\s+import',  # from module import
    ]
    
    JS_TS_IMPORT_PATTERNS = [
        r'import\s+[\'"](.+?)[\'"]',  # Side-effect imports like import './styles.css'
        r'import.*from\s+[\'"](.+?)[\'"]',  # ES6 imports
        r'import\([\'"](.+?)[\'"]\)',  # Dynamic imports
        r'require\([\'"](.+?)[\'"]\)',  # CommonJS require
    ]
    
    def __init__(self):
        """Initialize dependency analyzer."""
        self.files: Dict[str, FileDependency] = {}
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        
        logger.info("📊 DependencyAnalyzer: Initialized")
    
    # ========================================================================
    # Import Parsing
    # ========================================================================
    
    def parse_imports_from_content(
        self,
        content: str,
        file_type: str = "python"
    ) -> List[str]:
        """
        Parse import statements from file content.
        
        Args:
            content: File content
            file_type: File type ('python', 'javascript', 'typescript')
            
        Returns:
            List of imported module names
        """
        imports = []
        
        if file_type == "python":
            patterns = self.PYTHON_IMPORT_PATTERNS
        else:
            patterns = self.JS_TS_IMPORT_PATTERNS
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip comments
            if line.startswith('#') or line.startswith('//'):
                continue
            
            for pattern in patterns:
                matches = re.findall(pattern, line)
                imports.extend(matches)
        
        # Clean up imports (remove relative path indicators)
        cleaned_imports = []
        for imp in imports:
            # Store original for later
            original_imp = imp
            
            # Remove leading ./ and ../ but preserve the rest
            while imp.startswith('./') or imp.startswith('../'):
                if imp.startswith('./'):
                    imp = imp[2:]
                elif imp.startswith('../'):
                    imp = imp[3:]
            
            # Remove file extensions
            imp = imp.replace('.py', '').replace('.js', '').replace('.ts', '').replace('.jsx', '').replace('.tsx', '').replace('.css', '')
            
            # Only add non-empty imports
            if imp:
                cleaned_imports.append(imp)
        
        logger.debug(f"📦 Parsed {len(cleaned_imports)} imports from {file_type} file")
        return cleaned_imports
    
    def extract_dependencies_from_task(self, task: Dict[str, Any]) -> FileDependency:
        """
        Extract dependencies from a task description.
        
        Args:
            task: Task dictionary with title, description, files_to_generate
            
        Returns:
            FileDependency object
        """
        title = task.get('title', '')
        description = task.get('description', '')
        files = task.get('files_to_generate', [])
        
        # Primary file path
        file_path = files[0] if files else title.lower().replace(' ', '_')
        
        # Parse imports from description or code
        imports = []
        code = task.get('code', '')
        if code:
            file_type = self._detect_file_type(file_path)
            imports = self.parse_imports_from_content(code, file_type)
        
        # Create dependency object
        file_dep = FileDependency(
            file_path=file_path,
            title=title,
            description=description,
            imports=imports
        )
        
        logger.info(f"📄 Extracted dependencies for {file_path}: {len(imports)} imports")
        return file_dep
    
    def _detect_file_type(self, file_path: str) -> str:
        """Detect file type from path."""
        if file_path.endswith('.py'):
            return 'python'
        elif file_path.endswith(('.js', '.jsx')):
            return 'javascript'
        elif file_path.endswith(('.ts', '.tsx')):
            return 'typescript'
        return 'python'  # Default
    
    # ========================================================================
    # Dependency Graph Construction
    # ========================================================================
    
    def build_dependency_graph(self, tasks: List[Dict[str, Any]]) -> None:
        """
        Build dependency graph from list of tasks.
        
        Args:
            tasks: List of task dictionaries
        """
        logger.info(f"🔨 Building dependency graph for {len(tasks)} tasks...")
        
        # First pass: Create all file dependencies
        for task in tasks:
            file_dep = self.extract_dependencies_from_task(task)
            self.files[file_dep.file_path] = file_dep
        
        # Second pass: Resolve dependencies
        for file_path, file_dep in self.files.items():
            for imp in file_dep.imports:
                # Find matching file
                dep_file = self._find_dependency_file(imp)
                
                if dep_file and dep_file in self.files:
                    # Add edge: file_path depends on dep_file
                    file_dep.depends_on.add(dep_file)
                    self.files[dep_file].required_by.add(file_path)
                    
                    # Add to graph
                    self.dependency_graph[file_path].add(dep_file)
                    self.reverse_graph[dep_file].add(file_path)
        
        logger.info(
            f"✅ Dependency graph built: "
            f"{len(self.files)} files, "
            f"{sum(len(deps) for deps in self.dependency_graph.values())} edges"
        )
    
    def _find_dependency_file(self, import_name: str) -> Optional[str]:
        """
        Find file path corresponding to import name.
        
        Args:
            import_name: Import statement (e.g., 'utils.cache_manager')
            
        Returns:
            Matching file path or None
        """
        # Try exact match
        if import_name in self.files:
            return import_name
        
        # Try with common extensions
        for ext in ['.py', '.js', '.ts', '']:
            candidate = f"{import_name}{ext}"
            if candidate in self.files:
                return candidate
        
        # Try partial match (module name)
        for file_path in self.files.keys():
            if import_name in file_path or file_path in import_name:
                return file_path
        
        return None
    
    # ========================================================================
    # Topological Sort
    # ========================================================================
    
    def topological_sort(self) -> List[DependencyBatch]:
        """
        Perform topological sort to determine build order.
        
        Returns:
            List of batches, each containing files that can be built in parallel
            
        Raises:
            ValueError: If circular dependencies detected
        """
        logger.info("🔄 Performing topological sort...")
        
        # Detect and break circular dependencies
        cycles = self._detect_cycles()
        if cycles:
            logger.warning(f"⚠️ Found {len(cycles)} circular dependencies, breaking...")
            self._break_cycles(cycles)
        
        # Calculate in-degree for each node
        in_degree = {}
        for file_path in self.files.keys():
            in_degree[file_path] = len(self.dependency_graph.get(file_path, set()))
        
        # Initialize queue with nodes having in-degree 0
        queue = deque([f for f, deg in in_degree.items() if deg == 0])
        
        batches = []
        batch_level = 0
        
        while queue:
            # Current batch = all nodes with in-degree 0
            current_batch_size = len(queue)
            current_batch = []
            
            for _ in range(current_batch_size):
                file_path = queue.popleft()
                file_dep = self.files[file_path]
                file_dep.batch_level = batch_level
                current_batch.append(file_dep)
                
                # Reduce in-degree of dependent nodes
                for dependent in self.reverse_graph.get(file_path, set()):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
            
            if current_batch:
                batch = DependencyBatch(level=batch_level, files=current_batch)
                batches.append(batch)
                batch_level += 1
        
        # Check if all nodes processed
        if sum(1 for f in self.files.values() if f.batch_level == -1) > 0:
            unprocessed = [f.file_path for f in self.files.values() if f.batch_level == -1]
            raise ValueError(
                f"Circular dependency detected! Unprocessed files: {unprocessed}"
            )
        
        max_parallel = max(len(b.files) for b in batches) if batches else 0
        logger.info(
            f"✅ Topological sort complete: {len(batches)} batches, "
            f"max parallelism: {max_parallel}"
        )
        
        return batches
    
    # ========================================================================
    # Circular Dependency Detection
    # ========================================================================
    
    def _detect_cycles(self) -> List[List[str]]:
        """
        Detect circular dependencies using DFS.
        
        Returns:
            List of cycles (each cycle is a list of file paths)
        """
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.dependency_graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Cycle detected
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
            
            rec_stack.remove(node)
        
        for node in self.files.keys():
            if node not in visited:
                dfs(node, [])
        
        return cycles
    
    def _break_cycles(self, cycles: List[List[str]]) -> None:
        """
        Break circular dependencies by removing weakest edges.
        
        Strategy:
        1. For each cycle, find the edge with lowest "weight"
        2. Remove that edge from the dependency graph
        3. Log the broken dependency for manual review
        
        Args:
            cycles: List of detected cycles
        """
        for cycle in cycles:
            if len(cycle) < 2:
                continue
            
            # Find weakest edge (heuristic: shortest file path = less important)
            min_weight = float('inf')
            edge_to_remove = None
            
            for i in range(len(cycle) - 1):
                from_file = cycle[i]
                to_file = cycle[i + 1]
                weight = len(from_file) + len(to_file)
                
                if weight < min_weight:
                    min_weight = weight
                    edge_to_remove = (from_file, to_file)
            
            if edge_to_remove:
                from_file, to_file = edge_to_remove
                
                # Remove edge
                self.dependency_graph[from_file].discard(to_file)
                self.reverse_graph[to_file].discard(from_file)
                self.files[from_file].depends_on.discard(to_file)
                self.files[to_file].required_by.discard(from_file)
                
                logger.warning(
                    f"⚠️ Broke circular dependency: {from_file} → {to_file}\n"
                    f"   Cycle: {' → '.join(cycle)}"
                )
    
    # ========================================================================
    # Analysis & Statistics
    # ========================================================================
    
    def analyze_critical_path(self) -> Tuple[List[str], int]:
        """
        Find the critical path (longest dependency chain).
        
        Returns:
            Tuple of (critical_path_files, path_length)
        """
        max_depth = 0
        critical_path = []
        
        def dfs_depth(node: str, path: List[str]) -> int:
            nonlocal max_depth, critical_path
            
            current_depth = len(path)
            
            dependencies = self.dependency_graph.get(node, set())
            if not dependencies:
                if current_depth > max_depth:
                    max_depth = current_depth
                    critical_path = path.copy()
                return current_depth
            
            max_child_depth = 0
            for dep in dependencies:
                if dep not in path:  # Avoid cycles
                    child_depth = dfs_depth(dep, path + [dep])
                    max_child_depth = max(max_child_depth, child_depth)
            
            return current_depth + max_child_depth
        
        for file_path in self.files.keys():
            if not self.reverse_graph.get(file_path):  # No dependents = leaf node
                dfs_depth(file_path, [file_path])
        
        logger.info(f"🎯 Critical path length: {max_depth} levels")
        return critical_path, max_depth
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get dependency analysis statistics.
        
        Returns:
            Dictionary with analysis stats
        """
        total_files = len(self.files)
        total_dependencies = sum(len(deps) for deps in self.dependency_graph.values())
        
        # Find files with most dependencies
        most_deps = sorted(
            self.files.values(),
            key=lambda f: len(f.depends_on),
            reverse=True
        )[:5]
        
        # Find most required files
        most_required = sorted(
            self.files.values(),
            key=lambda f: len(f.required_by),
            reverse=True
        )[:5]
        
        critical_path, path_length = self.analyze_critical_path()
        
        # Calculate max parallelism (largest batch size after topological sort)
        # Only perform sort if we have files to avoid calling it twice
        max_parallelism = 0
        if total_files > 0:
            # Count files in each level instead of re-running topological sort
            level_counts = {}
            for file_dep in self.files.values():
                level = file_dep.batch_level
                if level >= 0:
                    level_counts[level] = level_counts.get(level, 0) + 1
            max_parallelism = max(level_counts.values()) if level_counts else total_files
        
        return {
            'total_files': total_files,
            'total_dependencies': total_dependencies,
            'avg_dependencies_per_file': total_dependencies / total_files if total_files > 0 else 0,
            'critical_path_length': path_length,
            'critical_path': critical_path,
            'max_parallelism': max_parallelism,
            'most_dependent_files': [
                {'file': f.file_path, 'deps': len(f.depends_on)}
                for f in most_deps
            ],
            'most_required_files': [
                {'file': f.file_path, 'required_by': len(f.required_by)}
                for f in most_required
            ]
        }
    
    def visualize_graph(self) -> str:
        """
        Generate a text visualization of the dependency graph.
        
        Returns:
            String representation of the graph
        """
        lines = ["📊 Dependency Graph Visualization\n" + "=" * 50]
        
        for file_path, file_dep in sorted(self.files.items()):
            lines.append(f"\n📄 {file_path}")
            
            if file_dep.depends_on:
                lines.append(f"   Depends on ({len(file_dep.depends_on)}):")
                for dep in sorted(file_dep.depends_on):
                    lines.append(f"      ← {dep}")
            
            if file_dep.required_by:
                lines.append(f"   Required by ({len(file_dep.required_by)}):")
                for req in sorted(file_dep.required_by):
                    lines.append(f"      → {req}")
        
        return '\n'.join(lines)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Alias for get_statistics() for consistency with other components.
        
        Returns:
            Dictionary with analysis stats
        """
        return self.get_statistics()
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"DependencyAnalyzer("
            f"files={len(self.files)}, "
            f"edges={sum(len(deps) for deps in self.dependency_graph.values())})"
        )


# ============================================================================
# Helper Functions
# ============================================================================

def analyze_plan_dependencies(plan: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[DependencyBatch]:
    """
    Analyze dependencies in a plan and return build order.
    
    Args:
        plan: Plan dictionary with subtasks OR list of tasks
        
    Returns:
        List of dependency batches for parallel execution
    """
    analyzer = DependencyAnalyzer()
    
    # Extract tasks from plan (handle both dict and list)
    if isinstance(plan, list):
        tasks = plan
    else:
        tasks = plan.get('subtasks', [])
    
    # Build dependency graph
    analyzer.build_dependency_graph(tasks)
    
    # Perform topological sort
    batches = analyzer.topological_sort()
    
    # Log statistics
    stats = analyzer.get_statistics()
    logger.info(
        f"📊 Dependency Analysis Complete:\n"
        f"   Total files: {stats['total_files']}\n"
        f"   Total dependencies: {stats['total_dependencies']}\n"
        f"   Batches: {len(batches)}\n"
        f"   Critical path: {stats['critical_path_length']} levels"
    )
    
    return batches


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Sample tasks
    tasks = [
        {
            'title': 'Main Application',
            'description': 'Main entry point',
            'files_to_generate': ['main.py'],
            'code': 'from config import settings\nfrom app import create_app'
        },
        {
            'title': 'Configuration',
            'description': 'App configuration',
            'files_to_generate': ['config.py'],
            'code': 'import os\nfrom pathlib import Path'
        },
        {
            'title': 'Application Factory',
            'description': 'Flask app factory',
            'files_to_generate': ['app.py'],
            'code': 'from flask import Flask\nfrom routes import api_blueprint'
        },
        {
            'title': 'API Routes',
            'description': 'API endpoints',
            'files_to_generate': ['routes.py'],
            'code': 'from flask import Blueprint\nfrom models import User'
        },
        {
            'title': 'Database Models',
            'description': 'SQLAlchemy models',
            'files_to_generate': ['models.py'],
            'code': 'from flask_sqlalchemy import SQLAlchemy\nfrom config import settings'
        }
    ]
    
    analyzer = DependencyAnalyzer()
    analyzer.build_dependency_graph(tasks)
    
    print(analyzer.visualize_graph())
    print("\n" + "=" * 50)
    
    batches = analyzer.topological_sort()
    for batch in batches:
        print(f"\n{batch}")
        for file_dep in batch.files:
            print(f"  - {file_dep.file_path}")
    
    print("\n" + "=" * 50)
    stats = analyzer.get_statistics()
    print(f"Statistics: {stats}")
