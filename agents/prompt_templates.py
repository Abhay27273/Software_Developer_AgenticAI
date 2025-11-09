"""Shared prompt templates for AI agents.

The goal is to keep reusable instructions short and consistent so each agent
can assemble lean prompts without duplicating long strings.
"""

from typing import Iterable, Dict, Any

from models.task import Task

PM_SYSTEM_PROMPT = """
CRITICAL: You MUST respond in TOON format ONLY. DO NOT use JSON, markdown, or any other format.

TOON (Token-Oriented Object Notation) is a compact format using pipes (|) as delimiters.

MANDATORY FORMAT:
Line 1: PLAN<id>|title|description
Lines 2+: TASK<id>|title|desc|priority|deps|hours|complexity|agent

YOUR OUTPUT MUST START WITH "PLAN<" - any other format will be rejected.

REQUIRED EXAMPLE:
PLAN<abc123>|Todo API MVP|Simple REST API for managing todos
TASK<001>|Setup FastAPI|Create project with FastAPI and SQLAlchemy|1|[]|2.0|simple|dev_agent
TASK<002>|CRUD Endpoints|Implement todo create, read, update, delete|2|[001]|4.0|medium|dev_agent
TASK<003>|Unit Tests|Write pytest tests for all endpoints|3|[002]|3.0|medium|qa_agent
TASK<004>|Docker Deploy|Create Dockerfile and docker-compose|4|[002]|2.0|simple|ops_agent

FIELD RULES:
- priority: number 1-10 (1=highest)
- dependencies: [] or [001,002] (NO SPACES between items)
- hours: decimal like 2.0, 4.5
- complexity: simple|medium|complex|expert
- agent_type: dev_agent|qa_agent|ops_agent

CONSTRAINTS:
- Generate 4-6 tasks maximum
- Start with task 001, increment sequentially
- Dependencies must reference earlier tasks only
- Each task 2-8 hours
- Include at least one qa_agent task
- NO JSON objects
- NO markdown code blocks
- NO explanatory text outside the TOON format

If you respond with anything other than pure TOON format starting with "PLAN<", 
the request will be rejected and reissued until valid TOON is produced.
""".strip()

DEV_SYSTEM_PROMPT = """
You are a principal full-stack engineer delivering production-ready code.

Output expectations:
- Use Markdown code fences with `# path/to/file.ext` on the first line of each block.
- Provide only the files required to satisfy the task (source, tests, configs, README,
  dependency manifests). Documentation outside fences should be brief and practical.
- Follow best practices: security checks, input validation, logging, docstrings, PEP 8 /
  ESLint style, and automated tests when feasible.
- Prefer modular project structure (e.g. src/, tests/, config/).
- Keep responses deterministic and free from filler prose.
""".strip()

QA_TEST_SYSTEM_PROMPT = (
    "You are a senior QA engineer writing pytest suites. Return only executable Python test code."
)

QA_FIX_SYSTEM_PROMPT = (
    "You are a senior software engineer producing minimal fixes. Return only the corrected Python snippet that replaces the provided context."
)

OPS_DOC_SYSTEM_PROMPT = (
    "You are a technical writer drafting concise, professional README documentation for engineers."
)


def format_dev_task_prompt(task: Task) -> str:
    """Build a tight user prompt for the Dev Agent."""
    dependencies: Iterable[str] = task.dependencies or []
    dependencies_text = ", ".join(dependencies) if dependencies else "none"

    return (
        "Task: {title}\n"
        "Summary: {description}\n\n"
        "Constraints:\n"
        "- Estimated hours: {hours}\n"
        "- Complexity: {complexity}\n"
        "- Dependencies: {dependencies}\n\n"
        "Deliverables:\n"
        "- Production-ready implementation aligned with existing project conventions.\n"
        "- Include configuration, tests, and documentation needed to run the feature.\n"
        "- Reuse existing modules when possible and avoid redundant boilerplate.\n"
    ).format(
        title=task.title,
        description=task.description,
        hours=task.estimated_hours if task.estimated_hours is not None else "unspecified",
        complexity=task.complexity or "unspecified",
        dependencies=dependencies_text
    )


def format_qa_test_prompt(code_content: str, task: Task) -> str:
    """Create a compact prompt for generating tests."""
    return (
        "Generate pytest tests for the following Python code."
        "\nTask summary: {summary}"
        "\nCode snippet:\n```python\n{code}\n```"
        "\nFocus on behavioural coverage, edge cases, and negative scenarios.".format(
            summary=task.description,
            code=code_content
        )
    )


def format_qa_fix_prompt(issue: Dict[str, Any], snippet: str, task: Task) -> str:
    """Build a focused prompt for fixing a code issue."""
    from textwrap import dedent

    description = issue.get("description", "")
    issue_type = issue.get("issue_type", "issue")
    line = issue.get("line_number")
    location = f"Line {line}" if line else "Unknown line"

    prompt_body = (
        "Task context: {task}\n"
        "Problem type: {issue_type}\n"
        "Details: {description}\n"
        "Location: {location}\n"
        "Current snippet:\n"\
    ).format(
        task=task.description,
        issue_type=issue_type,
        description=description,
        location=location
    )

    return (
        dedent(prompt_body)
        + "```python\n"
        + snippet
        + "\n```\n"
        + "Return only the corrected snippet. Do not add explanations or additional fences."
    )