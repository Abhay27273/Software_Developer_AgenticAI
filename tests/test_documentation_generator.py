"""
Tests for the Documentation Generator module.
"""

import pytest
import asyncio
from utils.documentation_generator import (
    DocumentationGenerator,
    ReadmeTemplate,
    APIDocGenerator,
    UserGuideGenerator
)


class TestReadmeTemplate:
    """Test ReadmeTemplate class."""
    
    def test_get_structure(self):
        """Test that README structure is returned."""
        structure = ReadmeTemplate.get_structure()
        assert "# {project_name}" in structure
        assert "{features}" in structure
        assert "{installation}" in structure
        assert "{configuration}" in structure
    
    def test_get_default_sections(self):
        """Test default sections are provided."""
        sections = ReadmeTemplate.get_default_sections()
        assert "contributing" in sections
        assert "license" in sections
        assert "troubleshooting" in sections
        assert "Fork the repository" in sections["contributing"]


class TestAPIDocGenerator:
    """Test APIDocGenerator class."""
    
    def test_extract_endpoints_fastapi(self):
        """Test extracting FastAPI endpoints."""
        code_files = {
            "main.py": """
from fastapi import FastAPI

app = FastAPI()

@app.get("/users")
def get_users():
    return []

@app.post("/users")
def create_user():
    return {}

@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {}
"""
        }
        
        generator = APIDocGenerator(None)
        endpoints = generator.extract_endpoints_from_code(code_files)
        
        assert len(endpoints) == 3
        assert any(ep['method'] == 'GET' and ep['path'] == '/users' for ep in endpoints)
        assert any(ep['method'] == 'POST' and ep['path'] == '/users' for ep in endpoints)
        assert any(ep['method'] == 'GET' and ep['path'] == '/users/{user_id}' for ep in endpoints)
    
    def test_extract_endpoints_flask(self):
        """Test extracting Flask endpoints."""
        code_files = {
            "app.py": """
from flask import Flask

app = Flask(__name__)

@app.route('/api/items', methods=['GET', 'POST'])
def items():
    return {}

@app.route('/api/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    return {}
"""
        }
        
        generator = APIDocGenerator(None)
        endpoints = generator.extract_endpoints_from_code(code_files)
        
        assert len(endpoints) >= 2
        assert any(ep['path'] == '/api/items' for ep in endpoints)


class TestDocumentationGenerator:
    """Test DocumentationGenerator class."""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client for testing."""
        async def mock_llm(user_prompt, system_prompt, model, temperature):
            # Return a simple mock response
            if "README" in user_prompt:
                return """# Test Project

A test project for documentation generation.

## Features

- Feature 1
- Feature 2

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set the following environment variables:
- `API_KEY`: Your API key

## Usage

```python
python main.py
```
"""
            elif "API" in user_prompt:
                return """# API Documentation

## Overview

This is a REST API.

## Endpoints

### GET /users

Get all users.

**Response:**
```json
[{"id": 1, "name": "John"}]
```
"""
            elif "user guide" in user_prompt.lower():
                return """# User Guide

## Getting Started

Follow these steps to get started.

## Features

### Feature 1

Description of feature 1.
"""
            elif "deployment" in user_prompt.lower():
                return """# Deployment Guide

## Prerequisites

- Docker
- Python 3.9+

## Deployment Steps

1. Build the Docker image
2. Run the container
"""
            return "Mock documentation"
        
        return mock_llm
    
    @pytest.fixture
    def doc_generator(self, mock_llm_client):
        """Create DocumentationGenerator with mock LLM."""
        return DocumentationGenerator(llm_client_func=mock_llm_client)
    
    @pytest.mark.asyncio
    async def test_generate_readme(self, doc_generator):
        """Test README generation."""
        code_files = {
            "main.py": "print('Hello')",
            "requirements.txt": "fastapi==0.100.0"
        }
        
        readme = await doc_generator.generate_readme(
            project_name="Test Project",
            project_description="A test project",
            code_files=code_files,
            tech_stack=["Python", "FastAPI"]
        )
        
        assert "# Test Project" in readme
        assert "Installation" in readme
        assert "Contributing" in readme
        assert "License" in readme
    
    @pytest.mark.asyncio
    async def test_generate_api_docs(self, doc_generator):
        """Test API documentation generation."""
        code_files = {
            "main.py": """
from fastapi import FastAPI

app = FastAPI()

@app.get("/users")
def get_users():
    return []
"""
        }
        
        api_docs = await doc_generator.generate_api_docs(
            project_name="Test API",
            code_files=code_files
        )
        
        assert "API Documentation" in api_docs
        assert len(api_docs) > 0
    
    @pytest.mark.asyncio
    async def test_generate_user_guide(self, doc_generator):
        """Test user guide generation."""
        code_files = {"main.py": "print('Hello')"}
        
        user_guide = await doc_generator.generate_user_guide(
            project_name="Test App",
            project_description="A test application",
            code_files=code_files,
            features=["Feature 1", "Feature 2"]
        )
        
        assert "User Guide" in user_guide
        assert len(user_guide) > 0
    
    @pytest.mark.asyncio
    async def test_generate_deployment_guide(self, doc_generator):
        """Test deployment guide generation."""
        code_files = {
            "main.py": "print('Hello')",
            "requirements.txt": "fastapi==0.100.0"
        }
        
        deployment_guide = await doc_generator.generate_deployment_guide(
            project_name="Test App",
            code_files=code_files,
            tech_stack=["Python", "FastAPI"],
            environment_vars={"API_KEY": "your-key-here"}
        )
        
        assert "Deployment Guide" in deployment_guide
        assert len(deployment_guide) > 0
    
    @pytest.mark.asyncio
    async def test_generate_all_documentation(self, doc_generator):
        """Test generating all documentation at once."""
        code_files = {
            "main.py": """
from fastapi import FastAPI

app = FastAPI()

@app.get("/users")
def get_users():
    return []
""",
            "requirements.txt": "fastapi==0.100.0"
        }
        
        docs = await doc_generator.generate_all_documentation(
            project_name="Test Project",
            project_description="A test project",
            code_files=code_files,
            tech_stack=["Python", "FastAPI"]
        )
        
        assert "README.md" in docs
        assert "API_DOCUMENTATION.md" in docs
        assert "USER_GUIDE.md" in docs
        assert "DEPLOYMENT_GUIDE.md" in docs
        assert len(docs) == 4
    
    def test_detect_tech_stack(self, doc_generator):
        """Test technology stack detection."""
        code_files = {
            "main.py": "from fastapi import FastAPI\nimport psycopg2",
            "app.js": "import React from 'react'",
            "config.py": "import redis"
        }
        
        tech_stack = doc_generator._detect_tech_stack(code_files)
        
        assert "FastAPI" in tech_stack
        assert "Python" in tech_stack
        assert "PostgreSQL" in tech_stack
        assert "React" in tech_stack
        assert "Redis" in tech_stack
    
    def test_extract_env_vars(self, doc_generator):
        """Test environment variable extraction."""
        code_files = {
            ".env.example": """
# Database configuration
DATABASE_URL=postgresql://localhost/mydb
API_KEY=your-api-key-here
DEBUG=true
"""
        }
        
        env_vars = doc_generator._extract_env_vars(code_files)
        
        assert "DATABASE_URL" in env_vars
        assert "API_KEY" in env_vars
        assert "DEBUG" in env_vars
    
    def test_format_env_vars(self, doc_generator):
        """Test environment variable formatting."""
        env_vars = {
            "DATABASE_URL": "postgresql://localhost/db",
            "API_KEY": "secret-key",
            "DEBUG": "true"
        }
        
        formatted = doc_generator._format_env_vars(env_vars)
        
        assert "DATABASE_URL" in formatted
        assert "API_KEY" in formatted
        assert "***REDACTED***" in formatted  # Sensitive values should be masked
    
    def test_summarize_codebase(self, doc_generator):
        """Test codebase summarization."""
        code_files = {
            "main.py": """
class User:
    pass

def get_user():
    pass

def create_user():
    pass
""",
            "models.py": """
class Product:
    pass
"""
        }
        
        summary = doc_generator._summarize_codebase(code_files)
        
        assert "main.py" in summary
        assert "models.py" in summary
        assert "User" in summary or "Product" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
