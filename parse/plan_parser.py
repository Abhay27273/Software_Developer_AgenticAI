import json
import re
import json5 # Used for more lenient JSON parsing
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from models.plan import Plan
from models.task import Task
from models.enums import TaskStatus
from utils.toon_parser import TOONParser

logger = logging.getLogger(__name__)

# REMOVED: Global RAW_PLAN_DIR definition and its mkdir call.
# This path will now be passed into the PlanParser constructor.

class PlanParser:
    """Class for plan parsing utilities, initialized with a base output directory."""

    def __init__(self, base_output_dir: Path):
        """
        Initializes the PlanParser with a base directory for output files.
        This base_output_dir should be the GENERATED_CODE_ROOT from main.py.
        """
        self.base_output_dir = base_output_dir
        self.raw_plan_dir = self.base_output_dir / "plans" / "raw"
        self.parsed_plan_dir = self.base_output_dir / "plans" / "parsed"

        # Ensure these specific directories exist when the parser is initialized
        try:
            self.raw_plan_dir.mkdir(parents=True, exist_ok=True)
            self.parsed_plan_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"PlanParser initialized. Raw plans at: {self.raw_plan_dir}, Parsed plans at: {self.parsed_plan_dir}")
        except Exception as e:
            logger.error(f"Failed to create plan directories under {self.base_output_dir}: {e}", exc_info=True)
            # Depending on severity, you might want to re-raise or handle gracefully.
            # For now, we log and allow the app to continue, but file operations might fail.


    @staticmethod
    def clean_and_parse(text: str) -> Dict[str, Any]:
        """
        Smart parser that handles both TOON and JSON formats.
        Prioritizes TOON for token efficiency, falls back to JSON for compatibility.
        
        Args:
            text: Raw LLM response (TOON or JSON format)
        
        Returns:
            Parsed plan dictionary
        """
        text = text.strip()
        original_text_preview = text[:500].replace('\n', '\\n') + ('...' if len(text) > 500 else '')
        logger.debug(f"Attempting to parse plan. Original text start: {original_text_preview}")
        
        # Check if it's TOON format (most efficient)
        if TOONParser.is_toon_format(text):
            logger.info("🎯 Detected TOON format, parsing for token efficiency...")
            try:
                parsed = TOONParser.parse_toon_to_dict(text)
                # Calculate token savings
                import json as json_module
                json_equivalent = json_module.dumps(parsed, ensure_ascii=False)
                savings = TOONParser.estimate_token_savings(len(json_equivalent), len(text))
                logger.info(f"💰 Token savings: ~{savings['saved_tokens_est']} tokens ({savings['savings_percent']}% reduction)")
                return parsed
            except Exception as e:
                logger.warning(f"TOON parsing failed: {e}, falling back to JSON")
        
        # Check if it's JSON format
        if TOONParser.is_json_format(text):
            logger.info("📋 Detected JSON format, parsing with legacy parser...")
            return PlanParser._parse_json_legacy(text)
        
        # Try to detect and extract format automatically
        logger.warning("⚠️ Format unclear, attempting both parsers...")
        
        # Try TOON first (more efficient if it works)
        try:
            parsed = TOONParser.parse_toon_to_dict(text)
            logger.info("✅ Successfully parsed as TOON")
            return parsed
        except Exception:
            logger.debug("TOON parsing attempt failed, trying JSON")
        
        # Try JSON as fallback
        try:
            parsed = PlanParser._parse_json_legacy(text)
            logger.info("✅ Successfully parsed as JSON")
            return parsed
        except Exception as e:
            raise ValueError(f"Could not parse content as TOON or JSON: {e}")

    @staticmethod
    def _parse_json_legacy(text: str) -> Dict[str, Any]:
        """
        Legacy JSON parsing logic (kept for backward compatibility).
        This version is more aggressive in trying to isolate a single JSON object.
        """
        original_text_preview = text[:500].replace('\n', '\\n') + ('...' if len(text) > 500 else '')
        logger.debug(f"Attempting to clean JSON. Original text start: {original_text_preview}")

        # Step 1: Aggressively try to find a JSON object enclosed by `{...}`
        # This regex looks for the first '{' and tries to match until the corresponding '}'
        # and then ensures there isn't significant non-whitespace data after it.
        # This is tricky because JSON can be nested, but for a single root object, it's a good start.
        match = re.search(r'\{.*\}', text, re.DOTALL)
        json_str = ""
        if match:
            json_str = match.group(0)
            logger.debug(f"Regex found potential JSON block. Start: {json_str[:200].replace('\n', '\\n')}...")
        else:
            # If no full {..} block found, try to extract between first { and last }
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and start < end:
                json_str = text[start:end + 1]
                logger.debug(f"Fallback: Extracted from first '{{' to last '}}'. Start: {json_str[:200].replace('\n', '\\n')}...")
            else:
                raise ValueError("No complete JSON object-like structure found in response.")

        # Step 2: Remove common LLM markdown artifacts (though we prompt against them)
        json_str = re.sub(r'```(?:json)?\s*', '', json_str, flags=re.IGNORECASE).strip()
        json_str = re.sub(r'\s*```\s*$', '', json_str).strip() # Remove closing fence

        # Step 3: Basic syntactic cleanup that json5 can handle, but helps ensure validity
        # Remove trailing commas before a closing bracket or brace. json5 handles this, but good to normalize.
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

        # Normalize invisible characters, remove anything below ASCII 32 except newlines/tabs
        json_str = "".join(c for c in json_str if ord(c) >= 32 or c in "\n\r\t")

        logger.debug(f"After initial cleaning and balancing: {json_str[:200].replace('\n', '\\n')}...")

        # Step 4: Final parsing attempt with json5 first, then standard json
        try:
            # Use json5 for more relaxed parsing first
            parsed_data = json5.loads(json_str)
            logger.info("Successfully parsed with json5.")
        except json.JSONDecodeError as json_err:
            logger.warning(f"json5 failed, trying json.loads. Error: {json_err}")
            try:
                parsed_data = json.loads(json_str)
                logger.info("Successfully parsed with standard json.")
            except json.JSONDecodeError as standard_json_err:
                logger.error(f"Failed with both json5 and json.loads. Standard JSON Error: {standard_json_err}")
                raise standard_json_err # Re-raise the original JSON error
        except Exception as e:
            logger.error(f"Unexpected error during final parsing: {e}")
            raise e # Re-raise other exceptions

        # Return parsed data directly (not as string)
        logger.debug(f"Final cleaned JSON: {str(parsed_data)[:200].replace('\n', '\\n')}...")
        return parsed_data
    
    @staticmethod
    def clean_json_string(text: str) -> str:
        """
        DEPRECATED: Use clean_and_parse() instead.
        Kept for backward compatibility.
        """
        result = PlanParser._parse_json_legacy(text)
        return json.dumps(result, ensure_ascii=False)

    def parse_plan_file(self, file_path: Path) -> Optional[Plan]:
        """Read raw plan file and return structured Plan object."""
        try:
            raw_text = file_path.read_text(encoding="utf-8")
            plan_data = self.clean_and_parse(raw_text)  # Use new unified parser

            # Validate minimal fields
            if not all(k in plan_data for k in ['plan_title', 'plan_description', 'tasks']):
                raise ValueError("Missing one of: plan_title, plan_description, tasks in parsed plan data.")

            # Parse tasks
            tasks = []
            for i, t in enumerate(plan_data['tasks'], 1):
                try:
                    task = Task(
                        id=t.get("id", f"task_{i:03d}"), # Ensure 'id' is always present, use formatted default
                        title=t.get("title", "Untitled Task"),
                        description=t.get("description", ""),
                        priority=int(t.get("priority", 5)),
                        status=TaskStatus.PENDING,
                        dependencies=t.get("dependencies", []),
                        estimated_hours=float(t.get("estimated_hours", 0.0)), # Default to float 0.0
                        complexity=t.get("complexity", "medium"),
                        agent_type=t.get("agent_type", "dev_agent")
                    )
                    tasks.append(task)
                except Exception as e:
                    # Log the problematic task data for debugging
                    logger.warning(f"Failed to parse task {i} due to: {e}. Task data: {t}")
                    # Decide if you want to skip this task or fail the whole plan
                    # For now, we continue but warn. If critical, re-raise.

            if not tasks and plan_data['tasks']: # If plan_data['tasks'] had items but none were valid
                 logger.warning("No valid tasks could be parsed from the LLM response, even though tasks array was present.")
                 # Optionally raise an error here if a plan must have tasks
                 # raise ValueError("No valid tasks could be parsed from the LLM response.")

            # Extract UUID from file name for plan ID
            plan_id_from_file = file_path.stem.replace("plan_", "").replace("_raw", "")

            return Plan(
                id=plan_id_from_file,
                title=plan_data['plan_title'],
                description=plan_data['plan_description'],
                tasks=tasks
            )

        except Exception as e:
            logger.error(f"Failed to parse plan from {file_path.name}: {e}", exc_info=True) # Add exc_info=True for full traceback
            return None

    def parse_all_raw_plans(self):
        """Parse all *_raw.txt plans in the directory and save them as both TOON and JSON."""
        # Ensure RAW_PLAN_DIR exists (it should have been created in __init__)
        self.raw_plan_dir.mkdir(parents=True, exist_ok=True) # Redundant but safe check
        
        for file in self.raw_plan_dir.glob("plan_*_raw.txt"):
            logger.info(f"Attempting to parse raw plan file: {file.name}")
            plan = self.parse_plan_file(file) # Use self.parse_plan_file
            if plan:
                plan_dict = plan.to_dict()
                
                # Save as TOON format for token efficiency
                toon_output_path = self.parsed_plan_dir / f"plan_{plan.id}.toon"
                try:
                    toon_content = TOONParser.serialize_plan_to_toon(plan_dict)
                    toon_output_path.write_text(toon_content, encoding="utf-8")
                    logger.info(f"✅ Parsed and saved as TOON: {toon_output_path.name}")
                except Exception as e:
                    logger.error(f"Failed to save TOON plan {toon_output_path.name}: {e}")
                
                # Also save as JSON for backward compatibility
                json_output_path = self.parsed_plan_dir / f"plan_{plan.id}.json"
                try:
                    with open(json_output_path, "w", encoding="utf-8") as f:
                        json.dump(plan_dict, f, indent=2, ensure_ascii=False)
                    logger.info(f"✅ Also saved as JSON: {json_output_path.name}")
                except Exception as e:
                    logger.error(f"Failed to save JSON plan {json_output_path.name}: {e}")
            else:
                logger.warning(f"⚠️ Skipped invalid plan file: {file.name}")