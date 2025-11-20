"""
Code Modifier Module using LangGraph for stateful code modification workflow.

This module provides safe code modification capabilities with:
- AST-based code parsing and understanding
- Intelligent modification planning
- Safe application of changes
- Syntax validation
- Diff generation
- Rollback capability
"""

import os
import ast
import json
import logging
import difflib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

# LangGraph imports
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from utils.llm_setup import ask_llm, LLMError

logger = logging.getLogger(__name__)

# Model configuration
CODE_MODIFIER_MODEL = os.getenv("CODE_MODIFIER_MODEL", "gemini-2.5-pro")


class ModificationState(str, Enum):
    """States in the code modification workflow."""
    PARSE = "parse"
    PLAN = "plan"
    VALIDATE_PLAN = "validate_plan"
    APPLY = "apply"
    VALIDATE_CODE = "validate_code"
    GENERATE_DIFF = "generate_diff"
    COMPLETE = "complete"
    ROLLBACK = "rollback"
    FAILED = "failed"


@dataclass
class CodeFile:
    """Represents a code file with its content and metadata."""
    path: str
    content: str
    language: str
    ast_tree: Optional[Any] = None
    backup_content: Optional[str] = None


@dataclass
class ModificationPlan:
    """Plan for modifying code."""
    file_path: str
    changes: List[Dict[str, Any]]
    rationale: str
    risk_level: str  # 'low', 'medium', 'high'
    affected_functions: List[str] = field(default_factory=list)
    affected_classes: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ModificationResult:
    """Result of a code modification operation."""
    success: bool
    modified_files: Dict[str, str]
    diff: str
    validation_errors: List[str] = field(default_factory=list)
    rollback_available: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowState(TypedDict):
    """State for the LangGraph workflow."""
    # Input
    modification_request: str
    file_path: str
    original_content: str
    
    # Intermediate state
    parsed_ast: Optional[Dict[str, Any]]
    code_structure: Optional[Dict[str, Any]]
    modification_plan: Optional[ModificationPlan]
    plan_validation: Optional[Dict[str, Any]]
    modified_content: Optional[str]
    syntax_valid: bool
    validation_errors: List[str]
    diff: Optional[str]
    
    # Control flow
    current_state: str
    should_rollback: bool
    error_message: Optional[str]
    
    # Output
    result: Optional[ModificationResult]


class CodeModifier:
    """
    LangGraph-based code modifier that safely modifies existing code.
    
    Uses a stateful workflow to:
    1. Parse and understand existing code
    2. Plan modifications intelligently
    3. Validate the plan
    4. Apply changes safely
    5. Validate modified code
    6. Generate diffs
    7. Support rollback
    """
    
    def __init__(self, model: str = CODE_MODIFIER_MODEL):
        """
        Initialize the CodeModifier.
        
        Args:
            model: LLM model to use for code analysis and modification
        """
        self.model = model
        self.workflow = self._build_workflow()
        logger.info(f"CodeModifier initialized with model: {model}")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow for code modification."""
        workflow = StateGraph(WorkflowState)
        
        # Add nodes for each state
        workflow.add_node("parse", self._parse_code)
        workflow.add_node("plan", self._plan_modification)
        workflow.add_node("validate_plan", self._validate_plan)
        workflow.add_node("apply", self._apply_modification)
        workflow.add_node("validate_code", self._validate_modified_code)
        workflow.add_node("generate_diff", self._generate_diff)
        workflow.add_node("complete", self._complete)
        workflow.add_node("rollback", self._rollback)
        
        # Set entry point
        workflow.set_entry_point("parse")
        
        # Add edges
        workflow.add_edge("parse", "plan")
        workflow.add_edge("plan", "validate_plan")
        
        # Conditional edge from validate_plan
        workflow.add_conditional_edges(
            "validate_plan",
            self._should_proceed_with_modification,
            {
                "apply": "apply",
                "rollback": "rollback"
            }
        )
        
        workflow.add_edge("apply", "validate_code")
        
        # Conditional edge from validate_code
        workflow.add_conditional_edges(
            "validate_code",
            self._is_code_valid,
            {
                "generate_diff": "generate_diff",
                "rollback": "rollback"
            }
        )
        
        workflow.add_edge("generate_diff", "complete")
        workflow.add_edge("complete", END)
        workflow.add_edge("rollback", END)
        
        return workflow.compile()
    
    async def modify_code(
        self,
        file_path: str,
        original_content: str,
        modification_request: str
    ) -> ModificationResult:
        """
        Modify code using the LangGraph workflow.
        
        Args:
            file_path: Path to the file being modified
            original_content: Original file content
            modification_request: Natural language description of desired changes
            
        Returns:
            ModificationResult with success status, modified content, and diff
        """
        logger.info(f"Starting code modification for {file_path}")
        logger.info(f"Request: {modification_request}")
        
        # Initialize workflow state
        initial_state: WorkflowState = {
            "modification_request": modification_request,
            "file_path": file_path,
            "original_content": original_content,
            "parsed_ast": None,
            "code_structure": None,
            "modification_plan": None,
            "plan_validation": None,
            "modified_content": None,
            "syntax_valid": False,
            "validation_errors": [],
            "diff": None,
            "current_state": ModificationState.PARSE.value,
            "should_rollback": False,
            "error_message": None,
            "result": None
        }
        
        try:
            # Execute workflow
            final_state = await self.workflow.ainvoke(initial_state)
            
            # Return result
            if final_state.get("result"):
                return final_state["result"]
            else:
                # Workflow failed
                return ModificationResult(
                    success=False,
                    modified_files={},
                    diff="",
                    validation_errors=final_state.get("validation_errors", []),
                    rollback_available=False,
                    metadata={"error": final_state.get("error_message", "Unknown error")}
                )
                
        except Exception as e:
            logger.error(f"Code modification failed: {e}", exc_info=True)
            return ModificationResult(
                success=False,
                modified_files={},
                diff="",
                validation_errors=[str(e)],
                rollback_available=False,
                metadata={"error": str(e)}
            )
    
    async def _parse_code(self, state: WorkflowState) -> WorkflowState:
        """Parse existing code to understand its structure."""
        logger.info("Parsing code structure...")
        
        try:
            file_path = state["file_path"]
            content = state["original_content"]
            
            # Determine language from file extension
            language = self._detect_language(file_path)
            
            # Parse based on language
            if language == "python":
                parsed_ast, code_structure = self._parse_python_code(content)
            elif language in ["javascript", "typescript"]:
                # For JS/TS, use LLM to understand structure
                code_structure = await self._parse_with_llm(content, language)
                parsed_ast = None
            else:
                # Generic parsing with LLM
                code_structure = await self._parse_with_llm(content, language)
                parsed_ast = None
            
            state["parsed_ast"] = parsed_ast
            state["code_structure"] = code_structure
            state["current_state"] = ModificationState.PLAN.value
            
            logger.info(f"Code parsing complete. Found {len(code_structure.get('functions', []))} functions, "
                       f"{len(code_structure.get('classes', []))} classes")
            
        except Exception as e:
            logger.error(f"Code parsing failed: {e}", exc_info=True)
            state["should_rollback"] = True
            state["error_message"] = f"Failed to parse code: {str(e)}"
            state["validation_errors"].append(str(e))
        
        return state
    
    async def _plan_modification(self, state: WorkflowState) -> WorkflowState:
        """Generate a modification plan using LLM."""
        logger.info("Planning code modifications...")
        
        try:
            modification_request = state["modification_request"]
            code_structure = state["code_structure"]
            original_content = state["original_content"]
            
            # Create prompt for LLM
            prompt = self._create_planning_prompt(
                modification_request,
                code_structure,
                original_content
            )
            
            # Get modification plan from LLM
            system_prompt = """You are an expert software engineer specializing in code refactoring and modification.
Your task is to create a detailed, safe modification plan for existing code.

Respond with a JSON object containing:
{
    "changes": [
        {
            "type": "modify_function" | "add_function" | "modify_class" | "add_import" | "modify_variable",
            "target": "name of function/class/variable",
            "action": "detailed description of the change",
            "line_range": [start_line, end_line] (if applicable),
            "new_code": "the new code to insert/replace"
        }
    ],
    "rationale": "explanation of why these changes are needed",
    "risk_level": "low" | "medium" | "high",
    "affected_functions": ["list", "of", "affected", "functions"],
    "affected_classes": ["list", "of", "affected", "classes"],
    "dependencies": ["list", "of", "new", "dependencies"]
}

Ensure changes preserve existing functionality unless explicitly requested to change it."""
            
            response = await ask_llm(
                user_prompt=prompt,
                system_prompt=system_prompt,
                model=self.model,
                temperature=0.2
            )
            
            # Parse response
            plan_data = self._parse_json_response(response)
            
            # Create ModificationPlan object
            modification_plan = ModificationPlan(
                file_path=state["file_path"],
                changes=plan_data.get("changes", []),
                rationale=plan_data.get("rationale", ""),
                risk_level=plan_data.get("risk_level", "medium"),
                affected_functions=plan_data.get("affected_functions", []),
                affected_classes=plan_data.get("affected_classes", []),
                dependencies=plan_data.get("dependencies", [])
            )
            
            state["modification_plan"] = modification_plan
            state["current_state"] = ModificationState.VALIDATE_PLAN.value
            
            logger.info(f"Modification plan created: {len(modification_plan.changes)} changes, "
                       f"risk level: {modification_plan.risk_level}")
            
        except Exception as e:
            logger.error(f"Planning failed: {e}", exc_info=True)
            state["should_rollback"] = True
            state["error_message"] = f"Failed to create modification plan: {str(e)}"
            state["validation_errors"].append(str(e))
        
        return state
    
    async def _validate_plan(self, state: WorkflowState) -> WorkflowState:
        """Validate the modification plan for safety."""
        logger.info("Validating modification plan...")
        
        try:
            modification_plan = state["modification_plan"]
            code_structure = state["code_structure"]
            
            validation_result = {
                "is_safe": True,
                "warnings": [],
                "errors": []
            }
            
            # Check 1: Verify affected functions/classes exist
            existing_functions = set(code_structure.get("functions", []))
            existing_classes = set(code_structure.get("classes", []))
            
            for func in modification_plan.affected_functions:
                if func not in existing_functions:
                    validation_result["warnings"].append(
                        f"Function '{func}' not found in existing code"
                    )
            
            for cls in modification_plan.affected_classes:
                if cls not in existing_classes:
                    validation_result["warnings"].append(
                        f"Class '{cls}' not found in existing code"
                    )
            
            # Check 2: Assess risk level
            if modification_plan.risk_level == "high":
                validation_result["warnings"].append(
                    "High-risk modification detected. Extra validation recommended."
                )
            
            # Check 3: Validate change types
            valid_change_types = [
                "modify_function", "add_function", "modify_class",
                "add_class", "add_import", "modify_variable", "add_variable"
            ]
            
            for change in modification_plan.changes:
                if change.get("type") not in valid_change_types:
                    validation_result["errors"].append(
                        f"Invalid change type: {change.get('type')}"
                    )
                    validation_result["is_safe"] = False
            
            # Check 4: Ensure new_code is provided for each change
            for i, change in enumerate(modification_plan.changes):
                if not change.get("new_code"):
                    validation_result["errors"].append(
                        f"Change {i+1} missing 'new_code' field"
                    )
                    validation_result["is_safe"] = False
            
            state["plan_validation"] = validation_result
            state["current_state"] = ModificationState.APPLY.value if validation_result["is_safe"] else ModificationState.ROLLBACK.value
            
            if not validation_result["is_safe"]:
                state["should_rollback"] = True
                state["error_message"] = "Plan validation failed: " + "; ".join(validation_result["errors"])
                state["validation_errors"].extend(validation_result["errors"])
            
            logger.info(f"Plan validation complete. Safe: {validation_result['is_safe']}, "
                       f"Warnings: {len(validation_result['warnings'])}, "
                       f"Errors: {len(validation_result['errors'])}")
            
        except Exception as e:
            logger.error(f"Plan validation failed: {e}", exc_info=True)
            state["should_rollback"] = True
            state["error_message"] = f"Plan validation error: {str(e)}"
            state["validation_errors"].append(str(e))
        
        return state
    
    async def _apply_modification(self, state: WorkflowState) -> WorkflowState:
        """Apply the modification plan to the code."""
        logger.info("Applying code modifications...")
        
        try:
            original_content = state["original_content"]
            modification_plan = state["modification_plan"]
            
            # Use LLM to apply modifications intelligently
            prompt = self._create_application_prompt(
                original_content,
                modification_plan
            )
            
            system_prompt = """You are an expert software engineer applying code modifications.

Given the original code and a modification plan, generate the complete modified code.

CRITICAL REQUIREMENTS:
1. Preserve all existing functionality unless explicitly asked to change it
2. Maintain code style and formatting
3. Keep all imports and dependencies
4. Ensure proper indentation
5. Add comments explaining significant changes
6. Return ONLY the complete modified code, no explanations

The output should be valid, executable code that can replace the original file."""
            
            modified_content = await ask_llm(
                user_prompt=prompt,
                system_prompt=system_prompt,
                model=self.model,
                temperature=0.1  # Low temperature for precise code generation
            )
            
            # Clean up the response (remove markdown code blocks if present)
            modified_content = self._clean_code_response(modified_content)
            
            state["modified_content"] = modified_content
            state["current_state"] = ModificationState.VALIDATE_CODE.value
            
            logger.info("Code modifications applied successfully")
            
        except Exception as e:
            logger.error(f"Failed to apply modifications: {e}", exc_info=True)
            state["should_rollback"] = True
            state["error_message"] = f"Failed to apply modifications: {str(e)}"
            state["validation_errors"].append(str(e))
        
        return state
    
    async def _validate_modified_code(self, state: WorkflowState) -> WorkflowState:
        """Validate the modified code for syntax errors."""
        logger.info("Validating modified code...")
        
        try:
            modified_content = state["modified_content"]
            file_path = state["file_path"]
            language = self._detect_language(file_path)
            
            validation_errors = []
            
            # Syntax validation based on language
            if language == "python":
                try:
                    ast.parse(modified_content)
                    logger.info("Python syntax validation passed")
                except SyntaxError as e:
                    validation_errors.append(f"Python syntax error: {str(e)}")
                    logger.error(f"Python syntax error: {e}")
            
            elif language in ["javascript", "typescript"]:
                # For JS/TS, we'd need a JS parser or use LLM validation
                # For now, do basic checks
                if not modified_content.strip():
                    validation_errors.append("Modified code is empty")
            
            # Additional validation: Check if code is significantly different
            if modified_content == state["original_content"]:
                validation_errors.append("Modified code is identical to original")
            
            # Check if code is too short (might indicate generation failure)
            if len(modified_content) < len(state["original_content"]) * 0.5:
                validation_errors.append("Modified code is significantly shorter than original (possible generation error)")
            
            state["validation_errors"].extend(validation_errors)
            state["syntax_valid"] = len(validation_errors) == 0
            state["current_state"] = ModificationState.GENERATE_DIFF.value if state["syntax_valid"] else ModificationState.ROLLBACK.value
            
            if not state["syntax_valid"]:
                state["should_rollback"] = True
                state["error_message"] = "Code validation failed: " + "; ".join(validation_errors)
            
            logger.info(f"Code validation complete. Valid: {state['syntax_valid']}")
            
        except Exception as e:
            logger.error(f"Code validation failed: {e}", exc_info=True)
            state["should_rollback"] = True
            state["error_message"] = f"Code validation error: {str(e)}"
            state["validation_errors"].append(str(e))
            state["syntax_valid"] = False
        
        return state
    
    async def _generate_diff(self, state: WorkflowState) -> WorkflowState:
        """Generate a diff showing changes."""
        logger.info("Generating diff...")
        
        try:
            original_content = state["original_content"]
            modified_content = state["modified_content"]
            file_path = state["file_path"]
            
            # Generate unified diff
            original_lines = original_content.splitlines(keepends=True)
            modified_lines = modified_content.splitlines(keepends=True)
            
            diff = difflib.unified_diff(
                original_lines,
                modified_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm=''
            )
            
            diff_text = '\n'.join(diff)
            
            state["diff"] = diff_text
            state["current_state"] = ModificationState.COMPLETE.value
            
            logger.info(f"Diff generated ({len(diff_text)} characters)")
            
        except Exception as e:
            logger.error(f"Diff generation failed: {e}", exc_info=True)
            state["error_message"] = f"Diff generation error: {str(e)}"
            # Don't rollback for diff generation failure
        
        return state
    
    async def _complete(self, state: WorkflowState) -> WorkflowState:
        """Complete the modification workflow successfully."""
        logger.info("Completing code modification...")
        
        result = ModificationResult(
            success=True,
            modified_files={state["file_path"]: state["modified_content"]},
            diff=state.get("diff", ""),
            validation_errors=[],
            rollback_available=True,
            metadata={
                "modification_plan": state["modification_plan"].__dict__ if state["modification_plan"] else {},
                "timestamp": datetime.now().isoformat()
            }
        )
        
        state["result"] = result
        state["current_state"] = ModificationState.COMPLETE.value
        
        logger.info("Code modification completed successfully")
        
        return state
    
    async def _rollback(self, state: WorkflowState) -> WorkflowState:
        """Rollback the modification due to errors."""
        logger.info("Rolling back code modification...")
        
        result = ModificationResult(
            success=False,
            modified_files={},
            diff="",
            validation_errors=state.get("validation_errors", []),
            rollback_available=False,
            metadata={
                "error": state.get("error_message", "Unknown error"),
                "timestamp": datetime.now().isoformat()
            }
        )
        
        state["result"] = result
        state["current_state"] = ModificationState.ROLLBACK.value
        
        logger.info(f"Code modification rolled back: {state.get('error_message')}")
        
        return state
    
    # Conditional edge functions
    def _should_proceed_with_modification(self, state: WorkflowState) -> str:
        """Determine if we should proceed with modification or rollback."""
        if state.get("should_rollback"):
            return "rollback"
        
        plan_validation = state.get("plan_validation", {})
        if not plan_validation.get("is_safe", False):
            return "rollback"
        
        return "apply"
    
    def _is_code_valid(self, state: WorkflowState) -> str:
        """Determine if modified code is valid."""
        if state.get("syntax_valid", False):
            return "generate_diff"
        return "rollback"
    
    # Helper methods
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.rb': 'ruby',
            '.php': 'php'
        }
        
        return language_map.get(ext, 'unknown')
    
    def _parse_python_code(self, content: str) -> Tuple[Optional[ast.AST], Dict[str, Any]]:
        """Parse Python code using AST."""
        try:
            tree = ast.parse(content)
            
            # Extract structure
            functions = []
            classes = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        imports.extend([alias.name for alias in node.names])
                    else:
                        imports.append(node.module or "")
            
            structure = {
                "functions": functions,
                "classes": classes,
                "imports": imports,
                "language": "python"
            }
            
            return tree, structure
            
        except SyntaxError as e:
            logger.error(f"Failed to parse Python code: {e}")
            return None, {"functions": [], "classes": [], "imports": [], "language": "python"}
    
    async def _parse_with_llm(self, content: str, language: str) -> Dict[str, Any]:
        """Parse code structure using LLM for non-Python languages."""
        prompt = f"""Analyze this {language} code and extract its structure.

Code:
```{language}
{content}
```

Respond with a JSON object containing:
{{
    "functions": ["list", "of", "function", "names"],
    "classes": ["list", "of", "class", "names"],
    "imports": ["list", "of", "imports"],
    "language": "{language}"
}}"""
        
        system_prompt = "You are a code analysis expert. Extract code structure accurately."
        
        try:
            response = await ask_llm(
                user_prompt=prompt,
                system_prompt=system_prompt,
                model=self.model,
                temperature=0.1
            )
            
            return self._parse_json_response(response)
            
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            return {"functions": [], "classes": [], "imports": [], "language": language}
    
    def _create_planning_prompt(
        self,
        modification_request: str,
        code_structure: Dict[str, Any],
        original_content: str
    ) -> str:
        """Create prompt for modification planning."""
        return f"""Create a detailed modification plan for the following code change request.

**Modification Request:**
{modification_request}

**Current Code Structure:**
- Functions: {', '.join(code_structure.get('functions', []))}
- Classes: {', '.join(code_structure.get('classes', []))}
- Language: {code_structure.get('language', 'unknown')}

**Original Code:**
```
{original_content[:2000]}  # First 2000 chars
{"..." if len(original_content) > 2000 else ""}
```

Create a modification plan that:
1. Preserves existing functionality unless explicitly asked to change it
2. Maintains code style and conventions
3. Minimizes risk of breaking changes
4. Clearly identifies what will be modified

Respond with a detailed JSON plan."""
    
    def _create_application_prompt(
        self,
        original_content: str,
        modification_plan: ModificationPlan
    ) -> str:
        """Create prompt for applying modifications."""
        changes_desc = "\n".join([
            f"{i+1}. {change.get('type')}: {change.get('action')}"
            for i, change in enumerate(modification_plan.changes)
        ])
        
        return f"""Apply the following modifications to the code.

**Original Code:**
```
{original_content}
```

**Modification Plan:**
{changes_desc}

**Rationale:**
{modification_plan.rationale}

**Instructions:**
1. Apply all changes from the modification plan
2. Preserve all existing functionality not mentioned in the plan
3. Maintain code style and formatting
4. Keep all necessary imports
5. Ensure proper indentation
6. Add brief comments for significant changes

Generate the complete modified code."""
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1]) if len(lines) > 2 else response
        
        # Remove json language identifier
        if response.startswith("json"):
            response = response[4:].strip()
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response: {response[:500]}")
            raise ValueError(f"Invalid JSON response from LLM: {str(e)}")
    
    def _clean_code_response(self, response: str) -> str:
        """Clean code response from LLM, removing markdown blocks."""
        response = response.strip()
        
        # Remove markdown code blocks
        if response.startswith("```"):
            lines = response.split("\n")
            # Remove first line (```language) and last line (```)
            if len(lines) > 2:
                response = "\n".join(lines[1:-1])
        
        return response.strip()


# Convenience function for direct usage
async def modify_code_file(
    file_path: str,
    original_content: str,
    modification_request: str,
    model: str = CODE_MODIFIER_MODEL
) -> ModificationResult:
    """
    Convenience function to modify a code file.
    
    Args:
        file_path: Path to the file
        original_content: Original file content
        modification_request: Description of desired changes
        model: LLM model to use
        
    Returns:
        ModificationResult
    """
    modifier = CodeModifier(model=model)
    return await modifier.modify_code(file_path, original_content, modification_request)
