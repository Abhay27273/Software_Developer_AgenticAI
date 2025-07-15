import json
import re
import logging
from pathlib import Path
from typing import Optional
from models.plan import Plan
from models.task import Task
from models.enums import TaskStatus

logger = logging.getLogger(__name__)

RAW_PLAN_DIR = Path("/workspaces/Software_Developer_AgenticAI/generated_code/plans")

class PlanParser:
    """Parent class for plan parsing utilities."""

    @staticmethod
    def clean_json_string(text: str) -> str:
        """Clean and normalize LLM response to make it valid JSON."""
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end == -1:
            raise ValueError("No valid JSON object found in response")
        json_str = text[start:end+1]
        json_str = re.sub(r'```json\s*|\s*```', '', json_str)
        json_str = re.sub(r'(\w+)(?=\s*:)', r'"\1"', json_str)  # quote unquoted keys
        json_str = json_str.replace("'", '"')                   # single → double quotes
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)      # remove trailing commas
        return json_str

    @staticmethod
    def parse_plan_file(file_path: Path) -> Optional[Plan]:
        """Read raw plan file and return structured Plan object."""
        try:
            raw_text = file_path.read_text(encoding="utf-8")
            cleaned = PlanParser.clean_json_string(raw_text)
            plan_data = json.loads(cleaned)

            # Validate minimal fields
            if not all(k in plan_data for k in ['plan_title', 'plan_description', 'tasks']):
                raise ValueError("Missing one of: plan_title, plan_description, tasks")

            # Parse tasks
            tasks = []
            for i, t in enumerate(plan_data['tasks'], 1):
                try:
                    task = Task(
                        id=t.get("id", f"task_{i:03}"),
                        title=t.get("title", "Untitled Task"),
                        description=t.get("description", ""),
                        priority=int(t.get("priority", 5)),
                        status=TaskStatus.PENDING,
                        dependencies=t.get("dependencies", []),
                        estimated_hours=float(t.get("estimated_hours", 0)),
                        complexity=t.get("complexity", "medium"),
                        agent_type=t.get("agent_type", "dev_agent")
                    )
                    tasks.append(task)
                except Exception as e:
                    logger.warning(f"Failed to parse task {i}: {e}")

            if not tasks:
                raise ValueError("No valid tasks found")

            return Plan(
                id=file_path.stem.replace("plan_", "").replace("_raw", ""),
                title=plan_data['plan_title'],
                description=plan_data['plan_description'],
                tasks=tasks
            )

        except Exception as e:
            logger.error(f"Failed to parse plan from {file_path.name}: {e}")
            return None

    @staticmethod
    def parse_all_raw_plans():
        """Parse all *_raw.txt plans in the directory and save them as JSON."""
        for file in RAW_PLAN_DIR.glob("plan_*_raw.txt"):
            plan = PlanParser.parse_plan_file(file)
            if plan:
                output_path = RAW_PLAN_DIR / f"plan_{plan.id}.json"
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(plan.to_dict(), f, indent=2, ensure_ascii=False)
                logger.info(f"✅ Parsed and saved: {output_path.name}")
            else:
                logger.warning(f"⚠️ Skipped invalid plan file: {file.name}")

# Module-level function for compatibility
def parse_plan(file_path: Path) -> Optional[Plan]:
    """Parse a plan file and return a Plan object (for import convenience)."""
    return PlanParser.parse_plan_file(file_path)
