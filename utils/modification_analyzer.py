"""
ModificationAnalyzer: Analyzes impact of code modifications on existing projects.

This module provides functionality to:
- Understand the scope of requested changes using LLM
- Build dependency graphs from existing codebase
- Identify files that need modification
- Calculate risk scores for proposed changes
"""

import logging
import re
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime

from utils.llm_setup import ask_llm, LLMError

logger = logging.getLogger(__name__)


@dataclass
class FileImpact:
    """Represents the impact on a single file."""
    filepath: str
    impact_level: str  # 'high', 'medium', 'low'
    reason: str
    estimated_changes: int  # Number of lines expected to change
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ImpactAnalysis:
    """Complete impact analysis of a modification request."""
    request: str
    affected_files: List[FileImpact]
    risk_score: float  # 0.0 to 1.0
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    dependency_graph: Dict[str, List[str]]
    estimated_effort_hours: float
    recommendations: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ModificationAnalyzer:
    """
    Analyzes modification requests to understand their impact on existing codebases.
    
    Uses LLM to understand change scope and builds dependency graphs to identify
    all affected files and calculate risk scores.
    """
    
    def __init__(self, llm_model: str = "gemini-2.5-flash"):
        """
        Initialize the ModificationAnalyzer.
        
        Args:
            llm_model: The LLM model to use for analysis
        """
        self.llm_model = llm_model
        logger.info(f"ModificationAnalyzer initialized with model: {llm_model}")
    
    async def analyze_impact(
        self,
        modification_request: str,
        codebase: Dict[str, str],
        project_type: str = "unknown"
    ) -> ImpactAnalysis:
        """
        Analyze the impact of a modification request on the codebase.
        
        Args:
            modification_request: Natural language description of desired changes
            codebase: Dictionary mapping file paths to file contents
            project_type: Type of project (api, web_app, etc.)
        
        Returns:
            ImpactAnalysis object containing complete analysis results
        """
        logger.info(f"Starting impact analysis for modification: {modification_request[:100]}...")
        
        # Step 1: Build dependency graph
        dependency_graph = self._build_dependency_graph(codebase)
        logger.info(f"Built dependency graph with {len(dependency_graph)} nodes")
        
        # Step 2: Use LLM to understand change scope
        affected_files = await self._identify_affected_files(
            modification_request,
            codebase,
            project_type,
            dependency_graph
        )
        logger.info(f"Identified {len(affected_files)} affected files")
        
        # Step 3: Calculate risk score
        risk_score, risk_level = self._calculate_risk_score(
            affected_files,
            dependency_graph,
            codebase
        )
        logger.info(f"Calculated risk: {risk_level} (score: {risk_score:.2f})")
        
        # Step 4: Estimate effort
        estimated_effort = self._estimate_effort(affected_files)
        
        # Step 5: Generate recommendations
        recommendations = self._generate_recommendations(
            affected_files,
            risk_level,
            dependency_graph
        )
        
        return ImpactAnalysis(
            request=modification_request,
            affected_files=affected_files,
            risk_score=risk_score,
            risk_level=risk_level,
            dependency_graph=dependency_graph,
            estimated_effort_hours=estimated_effort,
            recommendations=recommendations
        )
    
    def _build_dependency_graph(self, codebase: Dict[str, str]) -> Dict[str, List[str]]:
        """
        Build a dependency graph from the codebase.
        
        Analyzes import statements and function calls to understand
        which files depend on which other files.
        
        Args:
            codebase: Dictionary mapping file paths to file contents
        
        Returns:
            Dictionary mapping file paths to lists of files they depend on
        """
        dependency_graph = {}
        
        for filepath, content in codebase.items():
            dependencies = set()
            
            # Python imports
            if filepath.endswith('.py'):
                dependencies.update(self._extract_python_imports(content, codebase))
            
            # JavaScript/TypeScript imports
            elif filepath.endswith(('.js', '.jsx', '.ts', '.tsx')):
                dependencies.update(self._extract_js_imports(content, codebase))
            
            # Other file types can be added here
            
            dependency_graph[filepath] = list(dependencies)
        
        return dependency_graph
    
    def _extract_python_imports(self, content: str, codebase: Dict[str, str]) -> Set[str]:
        """Extract Python import dependencies."""
        dependencies = set()
        
        # Match: import module, from module import ...
        import_patterns = [
            r'^\s*import\s+([a-zA-Z0-9_.]+)',
            r'^\s*from\s+([a-zA-Z0-9_.]+)\s+import'
        ]
        
        for line in content.split('\n'):
            for pattern in import_patterns:
                match = re.match(pattern, line)
                if match:
                    module_name = match.group(1)
                    # Convert module name to potential file path
                    potential_paths = [
                        f"{module_name.replace('.', '/')}.py",
                        f"{module_name.replace('.', '/')}/__init__.py"
                    ]
                    for path in potential_paths:
                        if path in codebase:
                            dependencies.add(path)
        
        return dependencies
    
    def _extract_js_imports(self, content: str, codebase: Dict[str, str]) -> Set[str]:
        """Extract JavaScript/TypeScript import dependencies."""
        dependencies = set()
        
        # Match: import ... from '...', require('...')
        import_patterns = [
            r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'require\([\'"]([^\'"]+)[\'"]\)'
        ]
        
        for line in content.split('\n'):
            for pattern in import_patterns:
                matches = re.findall(pattern, line)
                for match in matches:
                    # Resolve relative imports
                    if match.startswith('.'):
                        # Simple resolution - in production would need more sophisticated logic
                        potential_path = match.lstrip('./') + '.js'
                        if potential_path in codebase:
                            dependencies.add(potential_path)
        
        return dependencies
    
    async def _identify_affected_files(
        self,
        modification_request: str,
        codebase: Dict[str, str],
        project_type: str,
        dependency_graph: Dict[str, List[str]]
    ) -> List[FileImpact]:
        """
        Use LLM to identify which files will be affected by the modification.
        
        Args:
            modification_request: Description of desired changes
            codebase: Dictionary of file paths to contents
            project_type: Type of project
            dependency_graph: Dependency relationships between files
        
        Returns:
            List of FileImpact objects describing affected files
        """
        # Prepare codebase summary for LLM
        codebase_summary = self._create_codebase_summary(codebase)
        
        system_prompt = """You are a code analysis expert. Analyze modification requests and identify which files will be affected.

For each affected file, provide:
1. File path
2. Impact level (high/medium/low)
3. Reason for impact
4. Estimated number of lines that will change

Return your analysis in the following format:
FILE: <filepath>
IMPACT: <high|medium|low>
REASON: <explanation>
LINES: <estimated_lines>
---

Be thorough but realistic. Consider:
- Direct changes (files that implement the requested feature)
- Indirect changes (files that depend on modified files)
- Test files that need updates
- Configuration files that may need changes"""

        user_prompt = f"""Analyze this modification request for a {project_type} project:

MODIFICATION REQUEST:
{modification_request}

CODEBASE STRUCTURE:
{codebase_summary}

DEPENDENCY INFORMATION:
{self._format_dependency_info(dependency_graph)}

Identify all files that will be affected by this modification."""

        try:
            response = await ask_llm(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                model=self.llm_model,
                temperature=0.3,
                validate_json=False,
                metadata={
                    "agent": "modification_analyzer",
                    "prompt_name": "identify_affected_files"
                }
            )
            
            # Parse LLM response into FileImpact objects
            affected_files = self._parse_affected_files_response(response, dependency_graph)
            
            return affected_files
            
        except LLMError as e:
            logger.error(f"LLM error during file identification: {e}")
            # Fallback: return conservative estimate
            return self._fallback_file_identification(modification_request, codebase)
    
    def _create_codebase_summary(self, codebase: Dict[str, str]) -> str:
        """Create a concise summary of the codebase structure."""
        summary_lines = []
        
        for filepath, content in sorted(codebase.items()):
            lines = content.split('\n')
            line_count = len(lines)
            
            # Extract key information
            if filepath.endswith('.py'):
                classes = re.findall(r'^\s*class\s+(\w+)', content, re.MULTILINE)
                functions = re.findall(r'^\s*def\s+(\w+)', content, re.MULTILINE)
                summary_lines.append(
                    f"- {filepath} ({line_count} lines): "
                    f"{len(classes)} classes, {len(functions)} functions"
                )
            elif filepath.endswith(('.js', '.jsx', '.ts', '.tsx')):
                functions = re.findall(r'function\s+(\w+)|const\s+(\w+)\s*=.*=>', content)
                summary_lines.append(
                    f"- {filepath} ({line_count} lines): "
                    f"{len(functions)} functions/components"
                )
            else:
                summary_lines.append(f"- {filepath} ({line_count} lines)")
        
        return '\n'.join(summary_lines)
    
    def _format_dependency_info(self, dependency_graph: Dict[str, List[str]]) -> str:
        """Format dependency graph for LLM consumption."""
        lines = []
        for file, deps in sorted(dependency_graph.items()):
            if deps:
                lines.append(f"- {file} depends on: {', '.join(deps)}")
        return '\n'.join(lines) if lines else "No dependencies detected"
    
    def _parse_affected_files_response(
        self,
        response: str,
        dependency_graph: Dict[str, List[str]]
    ) -> List[FileImpact]:
        """Parse LLM response into FileImpact objects."""
        affected_files = []
        
        # Split response into file blocks
        file_blocks = response.split('---')
        
        for block in file_blocks:
            if not block.strip():
                continue
            
            # Extract information using regex
            filepath_match = re.search(r'FILE:\s*(.+)', block)
            impact_match = re.search(r'IMPACT:\s*(high|medium|low)', block, re.IGNORECASE)
            reason_match = re.search(r'REASON:\s*(.+)', block)
            lines_match = re.search(r'LINES:\s*(\d+)', block)
            
            if filepath_match and impact_match:
                filepath = filepath_match.group(1).strip()
                impact_level = impact_match.group(1).lower()
                reason = reason_match.group(1).strip() if reason_match else "No reason provided"
                estimated_changes = int(lines_match.group(1)) if lines_match else 10
                
                # Get dependencies for this file
                dependencies = dependency_graph.get(filepath, [])
                
                affected_files.append(FileImpact(
                    filepath=filepath,
                    impact_level=impact_level,
                    reason=reason,
                    estimated_changes=estimated_changes,
                    dependencies=dependencies
                ))
        
        return affected_files
    
    def _fallback_file_identification(
        self,
        modification_request: str,
        codebase: Dict[str, str]
    ) -> List[FileImpact]:
        """Fallback method when LLM fails - use keyword matching."""
        logger.warning("Using fallback file identification method")
        
        affected_files = []
        keywords = self._extract_keywords(modification_request)
        
        for filepath, content in codebase.items():
            # Simple keyword matching
            matches = sum(1 for keyword in keywords if keyword.lower() in content.lower())
            
            if matches > 0:
                affected_files.append(FileImpact(
                    filepath=filepath,
                    impact_level='medium',
                    reason=f"Contains {matches} keyword(s) from modification request",
                    estimated_changes=20,
                    dependencies=[]
                ))
        
        return affected_files
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        # Remove common words and extract potential identifiers
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', text)
        common_words = {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'have', 'will'}
        return [w for w in words if w.lower() not in common_words]
    
    def _calculate_risk_score(
        self,
        affected_files: List[FileImpact],
        dependency_graph: Dict[str, List[str]],
        codebase: Dict[str, str]
    ) -> Tuple[float, str]:
        """
        Calculate risk score based on multiple factors.
        
        Returns:
            Tuple of (risk_score, risk_level)
        """
        if not affected_files:
            return 0.0, 'low'
        
        # Factor 1: Number of affected files (0-0.3)
        file_count_score = min(len(affected_files) / 20.0, 0.3)
        
        # Factor 2: Impact levels (0-0.3)
        impact_scores = {'high': 1.0, 'medium': 0.5, 'low': 0.2}
        avg_impact = sum(impact_scores.get(f.impact_level, 0.5) for f in affected_files) / len(affected_files)
        impact_score = avg_impact * 0.3
        
        # Factor 3: Total lines changing (0-0.2)
        total_lines = sum(f.estimated_changes for f in affected_files)
        lines_score = min(total_lines / 500.0, 0.2)
        
        # Factor 4: Dependency complexity (0-0.2)
        affected_paths = {f.filepath for f in affected_files}
        # Count how many other files depend on affected files
        dependent_count = sum(
            1 for file, deps in dependency_graph.items()
            if file not in affected_paths and any(dep in affected_paths for dep in deps)
        )
        dependency_score = min(dependent_count / 10.0, 0.2)
        
        # Calculate total risk score
        risk_score = file_count_score + impact_score + lines_score + dependency_score
        
        # Determine risk level
        if risk_score >= 0.7:
            risk_level = 'critical'
        elif risk_score >= 0.5:
            risk_level = 'high'
        elif risk_score >= 0.3:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        return risk_score, risk_level
    
    def _estimate_effort(self, affected_files: List[FileImpact]) -> float:
        """
        Estimate effort in hours based on affected files.
        
        Uses heuristics:
        - High impact file: 2-4 hours
        - Medium impact file: 1-2 hours
        - Low impact file: 0.5-1 hour
        """
        effort_map = {
            'high': 3.0,
            'medium': 1.5,
            'low': 0.75
        }
        
        total_effort = sum(
            effort_map.get(f.impact_level, 1.5) for f in affected_files
        )
        
        # Add overhead for testing and integration (20%)
        total_effort *= 1.2
        
        return round(total_effort, 1)
    
    def _generate_recommendations(
        self,
        affected_files: List[FileImpact],
        risk_level: str,
        dependency_graph: Dict[str, List[str]]
    ) -> List[str]:
        """Generate recommendations based on the analysis."""
        recommendations = []
        
        # Risk-based recommendations
        if risk_level == 'critical':
            recommendations.append(
                "⚠️ CRITICAL RISK: Consider breaking this modification into smaller, "
                "incremental changes to reduce risk."
            )
            recommendations.append(
                "Create comprehensive backup before proceeding with modifications."
            )
        elif risk_level == 'high':
            recommendations.append(
                "⚠️ HIGH RISK: Ensure thorough testing after modifications."
            )
        
        # File-specific recommendations
        high_impact_files = [f for f in affected_files if f.impact_level == 'high']
        if high_impact_files:
            recommendations.append(
                f"Focus testing on {len(high_impact_files)} high-impact file(s): "
                f"{', '.join(f.filepath for f in high_impact_files[:3])}"
            )
        
        # Dependency recommendations
        affected_paths = {f.filepath for f in affected_files}
        dependent_files = [
            file for file, deps in dependency_graph.items()
            if file not in affected_paths and any(dep in affected_paths for dep in deps)
        ]
        if dependent_files:
            recommendations.append(
                f"Test {len(dependent_files)} dependent file(s) that may be indirectly affected."
            )
        
        # General recommendations
        recommendations.append(
            "Run full test suite after modifications to catch regressions."
        )
        recommendations.append(
            "Update documentation to reflect changes."
        )
        
        return recommendations
