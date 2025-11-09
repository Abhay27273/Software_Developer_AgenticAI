"""
Token-Oriented Object Notation (TOON) Parser
A compact, token-efficient format for structured data exchange.
Optimized to reduce LLM token usage compared to JSON by ~50-60%.
"""

import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class TOONParser:
    """Parser for Token-Oriented Object Notation (TOON) format."""
    
    # TOON format delimiters
    FIELD_DELIMITER = "|"
    LIST_START = "["
    LIST_END = "]"
    LIST_ITEM_DELIMITER = ","
    
    # Entity type markers
    PLAN_PREFIX = "PLAN<"
    TASK_PREFIX = "TASK<"
    ID_SUFFIX = ">"
    
    @staticmethod
    def _escape_field(value: str) -> str:
        """Escape special characters in field values."""
        if not isinstance(value, str):
            return str(value)
        return value.replace("|", "\\|").replace("\n", "\\n").replace("\r", "\\r")
    
    @staticmethod
    def _unescape_field(value: str) -> str:
        """Unescape special characters in field values."""
        return value.replace("\\|", "|").replace("\\n", "\n").replace("\\r", "\r")
    
    @staticmethod
    def _parse_list(list_str: str) -> List[str]:
        """Parse a list notation like [item1,item2,item3] or []."""
        list_str = list_str.strip()
        if list_str == "[]":
            return []
        
        # Remove brackets
        if list_str.startswith("[") and list_str.endswith("]"):
            list_str = list_str[1:-1]
        
        if not list_str.strip():
            return []
        
        # Split by comma and strip whitespace
        items = [item.strip() for item in list_str.split(",")]
        return [item for item in items if item]  # Filter empty strings
    
    @staticmethod
    def _serialize_list(items: List[str]) -> str:
        """Serialize a list to TOON notation."""
        if not items:
            return "[]"
        return f"[{','.join(str(item) for item in items)}]"
    
    @staticmethod
    def serialize_plan_to_toon(plan_data: Dict[str, Any]) -> str:
        """
        Convert a plan dictionary to TOON format.
        
        Args:
            plan_data: Dictionary with keys: plan_id/id, plan_title/title, plan_description/description, tasks
        
        Returns:
            TOON formatted string
        
        Example Output:
            PLAN<550e8400>|Video Platform MVP|Build core video streaming features
            TASK<001>|Setup FastAPI|Initialize project structure|1|[]|2.0|low|dev_agent
            TASK<002>|Video Upload|Implement video upload endpoint|2|[001]|4.0|medium|dev_agent
        """
        lines = []
        
        # Serialize plan header
        plan_id = plan_data.get("id", plan_data.get("plan_id", "unknown"))
        title = TOONParser._escape_field(plan_data.get("plan_title", plan_data.get("title", "")))
        description = TOONParser._escape_field(plan_data.get("plan_description", plan_data.get("description", "")))
        
        plan_line = f"PLAN<{plan_id}>{TOONParser.FIELD_DELIMITER}{title}{TOONParser.FIELD_DELIMITER}{description}"
        lines.append(plan_line)
        
        # Serialize tasks
        tasks = plan_data.get("tasks", [])
        for task in tasks:
            task_id = task.get("id", "")
            task_title = TOONParser._escape_field(task.get("title", ""))
            task_desc = TOONParser._escape_field(task.get("description", ""))
            priority = str(task.get("priority", 5))
            dependencies = TOONParser._serialize_list(task.get("dependencies", []))
            hours = str(task.get("estimated_hours", 0.0))
            complexity = task.get("complexity", "medium")
            agent_type = task.get("agent_type", "dev_agent")
            
            task_line = (
                f"TASK<{task_id}>{TOONParser.FIELD_DELIMITER}"
                f"{task_title}{TOONParser.FIELD_DELIMITER}"
                f"{task_desc}{TOONParser.FIELD_DELIMITER}"
                f"{priority}{TOONParser.FIELD_DELIMITER}"
                f"{dependencies}{TOONParser.FIELD_DELIMITER}"
                f"{hours}{TOONParser.FIELD_DELIMITER}"
                f"{complexity}{TOONParser.FIELD_DELIMITER}"
                f"{agent_type}"
            )
            lines.append(task_line)
        
        toon_content = "\n".join(lines)
        logger.info(f"📦 Serialized plan to TOON format: {len(toon_content)} chars, {len(lines)} lines")
        return toon_content
    
    @staticmethod
    def parse_toon_to_dict(toon_content: str) -> Dict[str, Any]:
        """
        Parse TOON format string into a plan dictionary.
        
        Args:
            toon_content: TOON formatted string
        
        Returns:
            Dictionary with plan and task data compatible with existing system
        
        Raises:
            ValueError: If TOON format is invalid
        """
        lines = [line.strip() for line in toon_content.split("\n") if line.strip()]
        
        if not lines:
            raise ValueError("Empty TOON content")
        
        plan_data = {}
        tasks = []
        
        for line_num, line in enumerate(lines, 1):
            if line.startswith("PLAN<"):
                # Parse plan header: PLAN<id>|title|description
                plan_match = re.match(r'PLAN<([^>]+)>\|(.+?)\|(.+)', line)
                if plan_match:
                    plan_id, title, description = plan_match.groups()
                    plan_data["id"] = plan_id
                    plan_data["plan_id"] = plan_id
                    plan_data["plan_title"] = TOONParser._unescape_field(title)
                    plan_data["plan_description"] = TOONParser._unescape_field(description)
                    logger.debug(f"Parsed PLAN: {plan_id} - {title}")
                else:
                    logger.warning(f"Line {line_num}: Failed to parse PLAN line: {line}")
            
            elif line.startswith("TASK<"):
                # Parse task line: TASK<id>|title|desc|priority|deps|hours|complexity|agent
                task_match = re.match(r'TASK<([^>]+)>\|(.+)', line)
                if task_match:
                    task_id, fields_str = task_match.groups()
                    fields = fields_str.split(TOONParser.FIELD_DELIMITER)
                    
                    if len(fields) >= 7:
                        try:
                            task = {
                                "id": task_id,
                                "title": TOONParser._unescape_field(fields[0]),
                                "description": TOONParser._unescape_field(fields[1]),
                                "priority": int(fields[2]) if fields[2].strip().isdigit() else 5,
                                "dependencies": TOONParser._parse_list(fields[3]),
                                "estimated_hours": float(fields[4]) if fields[4].replace(".", "").replace("-", "").isdigit() else 0.0,
                                "complexity": fields[5].strip(),
                                "agent_type": fields[6].strip() if len(fields) > 6 else "dev_agent"
                            }
                            tasks.append(task)
                            logger.debug(f"Parsed TASK: {task_id} - {task['title']}")
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Line {line_num}: Error parsing task fields: {e}")
                    else:
                        logger.warning(f"Line {line_num}: Insufficient fields in TASK line (expected 7+, got {len(fields)})")
                else:
                    logger.warning(f"Line {line_num}: Failed to parse TASK line: {line}")
            else:
                # Ignore unknown lines (could be comments or whitespace)
                if line and not line.startswith("#"):
                    logger.debug(f"Line {line_num}: Ignoring unknown line: {line[:50]}")
        
        plan_data["tasks"] = tasks
        
        # Validate parsed data
        if not plan_data.get("plan_title"):
            raise ValueError("TOON parsing failed: No plan_title found")
        
        logger.info(f"✅ Parsed TOON: {plan_data.get('plan_title')} with {len(tasks)} tasks")
        return plan_data
    
    @staticmethod
    def is_toon_format(content: str) -> bool:
        """Check if content is in TOON format by looking for PLAN< marker."""
        return bool(re.search(r'^PLAN<[^>]+>', content.strip(), re.MULTILINE))
    
    @staticmethod
    def is_json_format(content: str) -> bool:
        """Check if content is in JSON format."""
        stripped = content.strip()
        return stripped.startswith("{") or stripped.startswith("[")
    
    @staticmethod
    def estimate_token_savings(json_size: int, toon_size: int) -> Dict[str, Any]:
        """
        Estimate token savings from using TOON vs JSON.
        Rough estimate: 1 token ~= 4 characters for English text.
        """
        json_tokens = json_size // 4
        toon_tokens = toon_size // 4
        saved_tokens = json_tokens - toon_tokens
        savings_percent = (saved_tokens / json_tokens * 100) if json_tokens > 0 else 0
        
        return {
            "json_chars": json_size,
            "toon_chars": toon_size,
            "json_tokens_est": json_tokens,
            "toon_tokens_est": toon_tokens,
            "saved_tokens_est": saved_tokens,
            "savings_percent": round(savings_percent, 1)
        }
