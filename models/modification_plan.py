"""
ModificationPlan: Represents a plan for modifying an existing project.

This module defines the data structures for modification plans, including
affected files, proposed changes, risk assessment, and effort estimation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class ModificationStatus(Enum):
    """Status of a modification plan."""
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class CodeChange:
    """Represents a specific code change in a file."""
    file_path: str
    change_type: str  # 'add', 'modify', 'delete'
    description: str
    before_snippet: Optional[str] = None
    after_snippet: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None


@dataclass
class ModificationPlan:
    """
    Complete plan for modifying a project.
    
    Contains all information needed to understand, review, and execute
    a modification to an existing codebase.
    """
    # Identification
    id: str
    project_id: str
    request: str  # Original modification request
    
    # Analysis results
    affected_files: List[str]
    changes: List[CodeChange]
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    risk_score: float  # 0.0 to 1.0
    
    # Effort estimation
    estimated_hours: float
    complexity: str  # 'simple', 'medium', 'complex'
    
    # Human-readable explanation
    summary: str
    detailed_explanation: str
    impact_description: str
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    testing_requirements: List[str] = field(default_factory=list)
    
    # Status tracking
    status: ModificationStatus = ModificationStatus.PENDING_APPROVAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    
    # Execution tracking
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert ModificationPlan to dictionary for serialization."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "request": self.request,
            "affected_files": self.affected_files,
            "changes": [
                {
                    "file_path": c.file_path,
                    "change_type": c.change_type,
                    "description": c.description,
                    "before_snippet": c.before_snippet,
                    "after_snippet": c.after_snippet,
                    "line_start": c.line_start,
                    "line_end": c.line_end
                }
                for c in self.changes
            ],
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "estimated_hours": self.estimated_hours,
            "complexity": self.complexity,
            "summary": self.summary,
            "detailed_explanation": self.detailed_explanation,
            "impact_description": self.impact_description,
            "recommendations": self.recommendations,
            "testing_requirements": self.testing_requirements,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by": self.approved_by,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ModificationPlan':
        """Create ModificationPlan from dictionary."""
        changes = [
            CodeChange(
                file_path=c["file_path"],
                change_type=c["change_type"],
                description=c["description"],
                before_snippet=c.get("before_snippet"),
                after_snippet=c.get("after_snippet"),
                line_start=c.get("line_start"),
                line_end=c.get("line_end")
            )
            for c in data.get("changes", [])
        ]
        
        return cls(
            id=data["id"],
            project_id=data["project_id"],
            request=data["request"],
            affected_files=data.get("affected_files", []),
            changes=changes,
            risk_level=data.get("risk_level", "medium"),
            risk_score=data.get("risk_score", 0.5),
            estimated_hours=data.get("estimated_hours", 0.0),
            complexity=data.get("complexity", "medium"),
            summary=data.get("summary", ""),
            detailed_explanation=data.get("detailed_explanation", ""),
            impact_description=data.get("impact_description", ""),
            recommendations=data.get("recommendations", []),
            testing_requirements=data.get("testing_requirements", []),
            status=ModificationStatus(data.get("status", "pending_approval")),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            approved_at=datetime.fromisoformat(data["approved_at"]) if data.get("approved_at") else None,
            approved_by=data.get("approved_by"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error_message=data.get("error_message")
        )
    
    def get_summary_text(self) -> str:
        """Get a formatted summary of the modification plan."""
        lines = [
            f"Modification Plan: {self.id}",
            f"Status: {self.status.value}",
            f"Risk Level: {self.risk_level.upper()} (score: {self.risk_score:.2f})",
            f"Estimated Effort: {self.estimated_hours} hours",
            f"Complexity: {self.complexity}",
            "",
            "Summary:",
            self.summary,
            "",
            f"Affected Files ({len(self.affected_files)}):",
        ]
        
        for filepath in self.affected_files:
            lines.append(f"  - {filepath}")
        
        if self.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for rec in self.recommendations:
                lines.append(f"  - {rec}")
        
        return "\n".join(lines)
