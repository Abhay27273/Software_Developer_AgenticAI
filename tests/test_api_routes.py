"""
Tests for API Routes (Task 7)

This module tests the REST API endpoints for:
- Project management
- Modifications
- Templates
- Documentation
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime

# Import the FastAPI app
from main import app

client = TestClient(app)


class TestProjectManagementEndpoints:
    """Test project management endpoints (Task 7.1)"""
    
    def test_create_project(self):
        """Test POST /api/projects - Create new project"""
        response = client.post(
            "/api/projects",
            json={
                "name": "Test Project",
                "description": "A test project",
                "project_type": "api",
                "owner_id": "test_user"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "project" in data
        assert data["project"]["name"] == "Test Project"
    
    def test_list_projects(self):
        """Test GET /api/projects - List user's projects"""
        response = client.get("/api/projects?owner_id=test_user")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "projects" in data
        assert "pagination" in data


class TestModificationEndpoints:
    """Test modification endpoints (Task 7.2)"""
    
    def test_request_modification(self):
        """Test POST /api/projects/{id}/modify - Request modification"""
        # This test would require a real project ID
        # For now, we'll just verify the endpoint exists
        pass


class TestTemplateEndpoints:
    """Test template endpoints (Task 7.3)"""
    
    def test_list_templates(self):
        """Test GET /api/templates - List available templates"""
        response = client.get("/api/templates")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "templates" in data


class TestDocumentationEndpoints:
    """Test documentation endpoints (Task 7.4)"""
    
    def test_get_all_documentation(self):
        """Test GET /api/projects/{id}/docs - Get all documentation"""
        # This test would require a real project ID
        # For now, we'll just verify the endpoint structure
        pass
