"""
Tests for the modification workflow components.

Tests the ModificationAnalyzer, ModificationPlanGenerator, and PM Agent
modification workflow integration.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from utils.modification_analyzer import ModificationAnalyzer, ImpactAnalysis, FileImpact
from utils.modification_plan_generator import ModificationPlanGenerator
from models.modification_plan import ModificationPlan, ModificationStatus
from models.project_context import ProjectContext, ProjectType, ProjectStatus


@pytest.fixture
def sample_codebase():
    """Sample codebase for testing."""
    return {
        "main.py": """
import utils
from models import User

def main():
    user = User("test")
    print(user.name)

if __name__ == "__main__":
    main()
""",
        "models.py": """
class User:
    def __init__(self, name):
        self.name = name
    
    def get_name(self):
        return self.name
""",
        "utils.py": """
def helper_function():
    return "helper"
"""
    }


@pytest.fixture
def sample_project_context():
    """Sample project context for testing."""
    return ProjectContext(
        id="test_project_123",
        name="Test Project",
        type=ProjectType.API,
        status=ProjectStatus.CREATED,
        owner_id="test_user",
        description="A test project",
        codebase={
            "main.py": "print('hello')",
            "utils.py": "def helper(): pass"
        }
    )


class TestModificationAnalyzer:
    """Tests for ModificationAnalyzer class."""
    
    def test_build_dependency_graph(self, sample_codebase):
        """Test building dependency graph from codebase."""
        analyzer = ModificationAnalyzer()
        graph = analyzer._build_dependency_graph(sample_codebase)
        
        assert isinstance(graph, dict)
        assert "main.py" in graph
        # main.py should depend on models.py
        assert any("models" in dep for dep in graph.get("main.py", []))
    
    def test_extract_python_imports(self, sample_codebase):
        """Test extracting Python imports."""
        analyzer = ModificationAnalyzer()
        content = sample_codebase["main.py"]
        dependencies = analyzer._extract_python_imports(content, sample_codebase)
        
        assert isinstance(dependencies, set)
        # Should find models.py dependency
        assert "models.py" in dependencies
    
    def test_calculate_risk_score_low(self):
        """Test risk calculation for low-risk changes."""
        analyzer = ModificationAnalyzer()
        
        affected_files = [
            FileImpact(
                filepath="utils.py",
                impact_level="low",
                reason="Minor utility change",
                estimated_changes=5,
                dependencies=[]
            )
        ]
        
        risk_score, risk_level = analyzer._calculate_risk_score(
            affected_files,
            {"utils.py": []},
            {"utils.py": "content"}
        )
        
        assert 0.0 <= risk_score <= 1.0
        assert risk_level in ['low', 'medium', 'high', 'critical']
    
    def test_calculate_risk_score_high(self):
        """Test risk calculation for high-risk changes."""
        analyzer = ModificationAnalyzer()
        
        affected_files = [
            FileImpact(
                filepath=f"file{i}.py",
                impact_level="high",
                reason="Critical change",
                estimated_changes=50,
                dependencies=[]
            )
            for i in range(10)
        ]
        
        risk_score, risk_level = analyzer._calculate_risk_score(
            affected_files,
            {f"file{i}.py": [] for i in range(10)},
            {f"file{i}.py": "content" for i in range(10)}
        )
        
        assert risk_score > 0.5
        assert risk_level in ['high', 'critical']
    
    def test_estimate_effort(self):
        """Test effort estimation."""
        analyzer = ModificationAnalyzer()
        
        affected_files = [
            FileImpact("file1.py", "high", "reason", 20, []),
            FileImpact("file2.py", "medium", "reason", 10, []),
            FileImpact("file3.py", "low", "reason", 5, [])
        ]
        
        effort = analyzer._estimate_effort(affected_files)
        
        assert effort > 0
        assert isinstance(effort, float)
    
    def test_generate_recommendations(self):
        """Test recommendation generation."""
        analyzer = ModificationAnalyzer()
        
        affected_files = [
            FileImpact("critical.py", "high", "Critical component", 30, []),
            FileImpact("utils.py", "low", "Helper function", 5, [])
        ]
        
        recommendations = analyzer._generate_recommendations(
            affected_files,
            "high",
            {"critical.py": [], "utils.py": []}
        )
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert any("high" in rec.lower() or "risk" in rec.lower() for rec in recommendations)


class TestModificationPlanGenerator:
    """Tests for ModificationPlanGenerator class."""
    
    def test_determine_complexity_simple(self):
        """Test complexity determination for simple changes."""
        generator = ModificationPlanGenerator()
        
        complexity = generator._determine_complexity(
            estimated_hours=2.0,
            file_count=2,
            risk_level="low"
        )
        
        assert complexity == "simple"
    
    def test_determine_complexity_complex(self):
        """Test complexity determination for complex changes."""
        generator = ModificationPlanGenerator()
        
        complexity = generator._determine_complexity(
            estimated_hours=10.0,
            file_count=15,
            risk_level="high"
        )
        
        assert complexity == "complex"
    
    def test_generate_summary(self):
        """Test summary generation."""
        generator = ModificationPlanGenerator()
        
        impact_analysis = ImpactAnalysis(
            request="Add user authentication",
            affected_files=[
                FileImpact("auth.py", "high", "New auth module", 50, []),
                FileImpact("main.py", "medium", "Integration", 20, [])
            ],
            risk_score=0.6,
            risk_level="medium",
            dependency_graph={},
            estimated_effort_hours=5.0,
            recommendations=[]
        )
        
        summary = generator._generate_summary("Add user authentication", impact_analysis)
        
        assert isinstance(summary, str)
        assert "2 file" in summary
        assert "medium" in summary
        assert "5.0 hours" in summary
    
    def test_generate_testing_requirements(self):
        """Test testing requirements generation."""
        generator = ModificationPlanGenerator()
        
        from models.modification_plan import CodeChange
        
        affected_files = [
            FileImpact("auth.py", "high", "New feature", 30, []),
            FileImpact("test_auth.py", "medium", "Test file", 20, [])
        ]
        
        changes = [
            CodeChange("auth.py", "add", "Add authentication", None, "new code"),
            CodeChange("main.py", "modify", "Update imports", "old", "new")
        ]
        
        requirements = generator._generate_testing_requirements(affected_files, changes)
        
        assert isinstance(requirements, list)
        assert len(requirements) > 0
        assert any("test" in req.lower() for req in requirements)


class TestModificationPlanModel:
    """Tests for ModificationPlan model."""
    
    def test_modification_plan_creation(self):
        """Test creating a ModificationPlan."""
        from models.modification_plan import CodeChange
        
        plan = ModificationPlan(
            id="plan_123",
            project_id="project_456",
            request="Add feature X",
            affected_files=["file1.py", "file2.py"],
            changes=[
                CodeChange("file1.py", "add", "Add new function", None, "def new(): pass")
            ],
            risk_level="medium",
            risk_score=0.5,
            estimated_hours=3.0,
            complexity="medium",
            summary="Add feature X to the project",
            detailed_explanation="This will add...",
            impact_description="Affects 2 files"
        )
        
        assert plan.id == "plan_123"
        assert plan.project_id == "project_456"
        assert plan.status == ModificationStatus.PENDING_APPROVAL
        assert len(plan.affected_files) == 2
        assert len(plan.changes) == 1
    
    def test_modification_plan_to_dict(self):
        """Test converting ModificationPlan to dictionary."""
        from models.modification_plan import CodeChange
        
        plan = ModificationPlan(
            id="plan_123",
            project_id="project_456",
            request="Test request",
            affected_files=["file.py"],
            changes=[CodeChange("file.py", "modify", "Change", "old", "new")],
            risk_level="low",
            risk_score=0.2,
            estimated_hours=1.0,
            complexity="simple",
            summary="Summary",
            detailed_explanation="Details",
            impact_description="Impact"
        )
        
        plan_dict = plan.to_dict()
        
        assert isinstance(plan_dict, dict)
        assert plan_dict["id"] == "plan_123"
        assert plan_dict["project_id"] == "project_456"
        assert plan_dict["risk_level"] == "low"
        assert len(plan_dict["changes"]) == 1
    
    def test_modification_plan_from_dict(self):
        """Test creating ModificationPlan from dictionary."""
        data = {
            "id": "plan_789",
            "project_id": "project_101",
            "request": "Test",
            "affected_files": ["test.py"],
            "changes": [
                {
                    "file_path": "test.py",
                    "change_type": "add",
                    "description": "Add test",
                    "before_snippet": None,
                    "after_snippet": "code",
                    "line_start": None,
                    "line_end": None
                }
            ],
            "risk_level": "low",
            "risk_score": 0.3,
            "estimated_hours": 2.0,
            "complexity": "simple",
            "summary": "Summary",
            "detailed_explanation": "Details",
            "impact_description": "Impact",
            "created_at": datetime.utcnow().isoformat()
        }
        
        plan = ModificationPlan.from_dict(data)
        
        assert plan.id == "plan_789"
        assert plan.project_id == "project_101"
        assert len(plan.changes) == 1
        assert plan.changes[0].file_path == "test.py"
    
    def test_get_summary_text(self):
        """Test getting formatted summary text."""
        from models.modification_plan import CodeChange
        
        plan = ModificationPlan(
            id="plan_123",
            project_id="project_456",
            request="Test",
            affected_files=["file1.py", "file2.py"],
            changes=[CodeChange("file1.py", "modify", "Change", None, None)],
            risk_level="medium",
            risk_score=0.5,
            estimated_hours=3.0,
            complexity="medium",
            summary="Test summary",
            detailed_explanation="Details",
            impact_description="Impact",
            recommendations=["Test recommendation"]
        )
        
        summary_text = plan.get_summary_text()
        
        assert isinstance(summary_text, str)
        assert "plan_123" in summary_text
        assert "medium" in summary_text.lower()
        assert "3.0 hours" in summary_text
        assert "file1.py" in summary_text
        assert "Test recommendation" in summary_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
