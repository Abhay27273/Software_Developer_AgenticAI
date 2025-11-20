"""
ModificationPlanGenerator: Generates detailed modification plans from impact analysis.

This module creates human-readable modification plans with:
- Clear explanations of what will change
- Before/after code snippets
- Estimated time and complexity
- Testing requirements
"""

import logging
import uuid
import re
from typing import Dict, List, Optional

from models.modification_plan import ModificationPlan, CodeChange, ModificationStatus
from utils.modification_analyzer import ImpactAnalysis, FileImpact
from utils.llm_setup import ask_llm, LLMError

logger = logging.getLogger(__name__)


class ModificationPlanGenerator:
    """
    Generates detailed modification plans from impact analysis.
    
    Takes the output of ModificationAnalyzer and creates a comprehensive
    plan with code snippets, explanations, and actionable steps.
    """
    
    def __init__(self, llm_model: str = "gemini-2.5-flash"):
        """
        Initialize the ModificationPlanGenerator.
        
        Args:
            llm_model: The LLM model to use for plan generation
        """
        self.llm_model = llm_model
        logger.info(f"ModificationPlanGenerator initialized with model: {llm_model}")
    
    async def generate_plan(
        self,
        project_id: str,
        modification_request: str,
        impact_analysis: ImpactAnalysis,
        codebase: Dict[str, str]
    ) -> ModificationPlan:
        """
        Generate a complete modification plan.
        
        Args:
            project_id: ID of the project being modified
            modification_request: Original modification request
            impact_analysis: Results from ModificationAnalyzer
            codebase: Current codebase contents
        
        Returns:
            ModificationPlan with detailed changes and explanations
        """
        logger.info(f"Generating modification plan for project {project_id}")
        
        plan_id = str(uuid.uuid4())
        
        # Generate detailed changes with code snippets
        changes = await self._generate_code_changes(
            modification_request,
            impact_analysis.affected_files,
            codebase
        )
        
        # Generate human-readable explanations
        summary = self._generate_summary(modification_request, impact_analysis)
        detailed_explanation = await self._generate_detailed_explanation(
            modification_request,
            impact_analysis,
            changes
        )
        impact_description = self._generate_impact_description(impact_analysis)
        
        # Determine complexity
        complexity = self._determine_complexity(
            impact_analysis.estimated_effort_hours,
            len(impact_analysis.affected_files),
            impact_analysis.risk_level
        )
        
        # Generate testing requirements
        testing_requirements = self._generate_testing_requirements(
            impact_analysis.affected_files,
            changes
        )
        
        # Create the modification plan
        plan = ModificationPlan(
            id=plan_id,
            project_id=project_id,
            request=modification_request,
            affected_files=[f.filepath for f in impact_analysis.affected_files],
            changes=changes,
            risk_level=impact_analysis.risk_level,
            risk_score=impact_analysis.risk_score,
            estimated_hours=impact_analysis.estimated_effort_hours,
            complexity=complexity,
            summary=summary,
            detailed_explanation=detailed_explanation,
            impact_description=impact_description,
            recommendations=impact_analysis.recommendations,
            testing_requirements=testing_requirements,
            status=ModificationStatus.PENDING_APPROVAL
        )
        
        logger.info(f"Generated modification plan {plan_id} with {len(changes)} changes")
        return plan
    
    async def _generate_code_changes(
        self,
        modification_request: str,
        affected_files: List[FileImpact],
        codebase: Dict[str, str]
    ) -> List[CodeChange]:
        """
        Generate specific code changes with before/after snippets.
        
        Uses LLM to understand what specific changes need to be made
        to each affected file.
        """
        changes = []
        
        for file_impact in affected_files:
            filepath = file_impact.filepath
            
            if filepath not in codebase:
                logger.warning(f"File {filepath} not found in codebase, skipping")
                continue
            
            file_content = codebase[filepath]
            
            # Generate changes for this file
            file_changes = await self._generate_file_changes(
                modification_request,
                filepath,
                file_content,
                file_impact
            )
            
            changes.extend(file_changes)
        
        return changes
    
    async def _generate_file_changes(
        self,
        modification_request: str,
        filepath: str,
        file_content: str,
        file_impact: FileImpact
    ) -> List[CodeChange]:
        """Generate specific changes for a single file."""
        
        system_prompt = """You are a code modification expert. Given a modification request and a file, 
identify the specific changes that need to be made.

For each change, provide:
1. Change type (add/modify/delete)
2. Description of the change
3. Before snippet (current code, if modifying/deleting)
4. After snippet (new code, if adding/modifying)
5. Line numbers (if applicable)

Format your response as:
CHANGE_START
TYPE: <add|modify|delete>
DESCRIPTION: <what is being changed>
BEFORE:
```
<current code or "N/A">
```
AFTER:
```
<new code or "N/A">
```
LINES: <start>-<end> or "N/A"
CHANGE_END

Be specific and include actual code snippets."""

        user_prompt = f"""Modification request: {modification_request}

File: {filepath}
Impact: {file_impact.impact_level}
Reason: {file_impact.reason}

Current file content:
```
{file_content}
```

What specific changes need to be made to this file?"""

        try:
            response = await ask_llm(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                model=self.llm_model,
                temperature=0.3,
                validate_json=False,
                metadata={
                    "agent": "modification_plan_generator",
                    "prompt_name": "generate_file_changes"
                }
            )
            
            # Parse the response into CodeChange objects
            changes = self._parse_code_changes(response, filepath)
            return changes
            
        except LLMError as e:
            logger.error(f"LLM error generating changes for {filepath}: {e}")
            # Return a generic change description
            return [CodeChange(
                file_path=filepath,
                change_type='modify',
                description=f"Modify to implement: {modification_request}",
                before_snippet=None,
                after_snippet=None
            )]
    
    def _parse_code_changes(self, response: str, filepath: str) -> List[CodeChange]:
        """Parse LLM response into CodeChange objects."""
        changes = []
        
        # Split into individual changes
        change_blocks = re.split(r'CHANGE_START', response)
        
        for block in change_blocks:
            if 'CHANGE_END' not in block:
                continue
            
            # Extract change information
            change_type_match = re.search(r'TYPE:\s*(add|modify|delete)', block, re.IGNORECASE)
            description_match = re.search(r'DESCRIPTION:\s*(.+?)(?=BEFORE:|AFTER:|LINES:|CHANGE_END)', block, re.DOTALL)
            before_match = re.search(r'BEFORE:\s*```[^\n]*\n(.*?)```', block, re.DOTALL)
            after_match = re.search(r'AFTER:\s*```[^\n]*\n(.*?)```', block, re.DOTALL)
            lines_match = re.search(r'LINES:\s*(\d+)-(\d+)', block)
            
            if change_type_match and description_match:
                change_type = change_type_match.group(1).lower()
                description = description_match.group(1).strip()
                before_snippet = before_match.group(1).strip() if before_match else None
                after_snippet = after_match.group(1).strip() if after_match else None
                
                # Handle "N/A" values
                if before_snippet and before_snippet.upper() == "N/A":
                    before_snippet = None
                if after_snippet and after_snippet.upper() == "N/A":
                    after_snippet = None
                
                line_start = int(lines_match.group(1)) if lines_match else None
                line_end = int(lines_match.group(2)) if lines_match else None
                
                changes.append(CodeChange(
                    file_path=filepath,
                    change_type=change_type,
                    description=description,
                    before_snippet=before_snippet,
                    after_snippet=after_snippet,
                    line_start=line_start,
                    line_end=line_end
                ))
        
        # If parsing failed, create a generic change
        if not changes:
            changes.append(CodeChange(
                file_path=filepath,
                change_type='modify',
                description="File requires modifications (details to be determined during implementation)",
                before_snippet=None,
                after_snippet=None
            ))
        
        return changes
    
    def _generate_summary(
        self,
        modification_request: str,
        impact_analysis: ImpactAnalysis
    ) -> str:
        """Generate a concise summary of the modification."""
        file_count = len(impact_analysis.affected_files)
        risk = impact_analysis.risk_level
        hours = impact_analysis.estimated_effort_hours
        
        summary = (
            f"This modification will affect {file_count} file(s) "
            f"with a {risk} risk level. "
            f"Estimated effort: {hours} hours. "
            f"Request: {modification_request}"
        )
        
        return summary
    
    async def _generate_detailed_explanation(
        self,
        modification_request: str,
        impact_analysis: ImpactAnalysis,
        changes: List[CodeChange]
    ) -> str:
        """Generate a detailed explanation of what will change and why."""
        
        system_prompt = """You are a technical writer explaining code modifications to developers.
Create a clear, detailed explanation of what changes will be made and why.

Structure your explanation:
1. Overview of the modification
2. Key changes by file
3. How the changes work together
4. Potential impacts on existing functionality

Be clear and technical but accessible."""

        # Prepare change summary
        change_summary = []
        for change in changes[:10]:  # Limit to first 10 for brevity
            change_summary.append(
                f"- {change.file_path}: {change.change_type} - {change.description}"
            )
        
        user_prompt = f"""Modification request: {modification_request}

Impact analysis:
- Risk level: {impact_analysis.risk_level}
- Affected files: {len(impact_analysis.affected_files)}
- Estimated effort: {impact_analysis.estimated_effort_hours} hours

Planned changes:
{chr(10).join(change_summary)}

Provide a detailed explanation of this modification."""

        try:
            explanation = await ask_llm(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                model=self.llm_model,
                temperature=0.4,
                validate_json=False,
                metadata={
                    "agent": "modification_plan_generator",
                    "prompt_name": "generate_explanation"
                }
            )
            return explanation
            
        except LLMError as e:
            logger.error(f"LLM error generating explanation: {e}")
            # Fallback to basic explanation
            return (
                f"This modification implements: {modification_request}\n\n"
                f"It will affect {len(impact_analysis.affected_files)} files "
                f"with {len(changes)} specific changes."
            )
    
    def _generate_impact_description(self, impact_analysis: ImpactAnalysis) -> str:
        """Generate a description of the impact on the codebase."""
        lines = [
            f"Risk Level: {impact_analysis.risk_level.upper()}",
            f"Risk Score: {impact_analysis.risk_score:.2f}/1.0",
            f"Affected Files: {len(impact_analysis.affected_files)}",
            "",
            "File Impact Breakdown:"
        ]
        
        # Group by impact level
        by_level = {'high': [], 'medium': [], 'low': []}
        for file_impact in impact_analysis.affected_files:
            by_level[file_impact.impact_level].append(file_impact)
        
        for level in ['high', 'medium', 'low']:
            files = by_level[level]
            if files:
                lines.append(f"\n{level.upper()} Impact ({len(files)} files):")
                for f in files[:5]:  # Show first 5
                    lines.append(f"  - {f.filepath}: {f.reason}")
                if len(files) > 5:
                    lines.append(f"  ... and {len(files) - 5} more")
        
        return "\n".join(lines)
    
    def _determine_complexity(
        self,
        estimated_hours: float,
        file_count: int,
        risk_level: str
    ) -> str:
        """Determine overall complexity of the modification."""
        
        # Calculate complexity score
        score = 0
        
        # Hours factor
        if estimated_hours > 8:
            score += 2
        elif estimated_hours > 4:
            score += 1
        
        # File count factor
        if file_count > 10:
            score += 2
        elif file_count > 5:
            score += 1
        
        # Risk factor
        if risk_level in ['critical', 'high']:
            score += 2
        elif risk_level == 'medium':
            score += 1
        
        # Determine complexity
        if score >= 5:
            return 'complex'
        elif score >= 3:
            return 'medium'
        else:
            return 'simple'
    
    def _generate_testing_requirements(
        self,
        affected_files: List[FileImpact],
        changes: List[CodeChange]
    ) -> List[str]:
        """Generate specific testing requirements for the modification."""
        requirements = []
        
        # File-based requirements
        test_files = [f for f in affected_files if 'test' in f.filepath.lower()]
        if test_files:
            requirements.append(
                f"Update {len(test_files)} existing test file(s) to reflect changes"
            )
        
        # Change-based requirements
        added_changes = [c for c in changes if c.change_type == 'add']
        if added_changes:
            requirements.append(
                f"Write unit tests for {len(added_changes)} new code addition(s)"
            )
        
        modified_changes = [c for c in changes if c.change_type == 'modify']
        if modified_changes:
            requirements.append(
                f"Run regression tests for {len(modified_changes)} modified component(s)"
            )
        
        # General requirements
        requirements.append("Run full test suite to ensure no regressions")
        requirements.append("Perform manual testing of affected functionality")
        
        # Integration testing
        if len(affected_files) > 3:
            requirements.append(
                "Perform integration testing to verify components work together"
            )
        
        return requirements
