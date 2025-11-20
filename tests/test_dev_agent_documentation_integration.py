"""
Integration test for Dev Agent documentation generation.

This test verifies that the Dev Agent correctly integrates with the
DocumentationGenerator to produce documentation alongside code.
"""

import pytest
import asyncio
from pathlib import Path
from agents.dev_agent import DevAgent
from models.task import Task
from models.enums import TaskStatus


class TestDevAgentDocumentationIntegration:
    """Test Dev Agent integration with documentation generation."""
    
    @pytest.fixture
    def dev_agent(self):
        """Create a DevAgent instance for testing."""
        return DevAgent()
    
    def test_dev_agent_has_doc_generator(self, dev_agent):
        """Test that DevAgent has a DocumentationGenerator instance."""
        assert hasattr(dev_agent, 'doc_generator')
        assert dev_agent.doc_generator is not None
    
    def test_detect_tech_stack(self, dev_agent):
        """Test tech stack detection from code files."""
        code_files = {
            "main.py": """
from fastapi import FastAPI
import psycopg2

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello"}
""",
            "models.py": """
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
"""
        }
        
        tech_stack = dev_agent._detect_tech_stack(code_files)
        
        assert "Python" in tech_stack
        assert "FastAPI" in tech_stack
        assert "PostgreSQL" in tech_stack
    
    def test_extract_env_vars(self, dev_agent):
        """Test environment variable extraction."""
        code_files = {
            ".env.example": """
DATABASE_URL=postgresql://localhost/mydb
API_KEY=your-api-key
SECRET_KEY=your-secret-key
DEBUG=true
PORT=8000
"""
        }
        
        env_vars = dev_agent._extract_env_vars(code_files)
        
        assert "DATABASE_URL" in env_vars
        assert "API_KEY" in env_vars
        assert "SECRET_KEY" in env_vars
        assert "DEBUG" in env_vars
        assert "PORT" in env_vars
    
    def test_extract_env_vars_from_config(self, dev_agent):
        """Test environment variable extraction from config files."""
        code_files = {
            "config.py": """
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
API_KEY = os.getenv("API_KEY")
DEBUG = os.getenv("DEBUG", "false")
"""
        }
        
        # This should not extract from Python code, only from .env files
        env_vars = dev_agent._extract_env_vars(code_files)
        
        # Should be empty or minimal since it's Python code, not .env format
        assert isinstance(env_vars, dict)
    
    def test_detect_multiple_frameworks(self, dev_agent):
        """Test detection of multiple frameworks in the same project."""
        code_files = {
            "backend/main.py": "from fastapi import FastAPI",
            "frontend/App.jsx": "import React from 'react'",
            "database/models.py": "import psycopg2",
            "cache/redis_client.py": "import redis"
        }
        
        tech_stack = dev_agent._detect_tech_stack(code_files)
        
        assert "Python" in tech_stack
        assert "FastAPI" in tech_stack
        assert "React" in tech_stack
        assert "PostgreSQL" in tech_stack
        assert "Redis" in tech_stack
    
    def test_detect_flask_framework(self, dev_agent):
        """Test detection of Flask framework."""
        code_files = {
            "app.py": """
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/users')
def get_users():
    return jsonify([])
"""
        }
        
        tech_stack = dev_agent._detect_tech_stack(code_files)
        
        assert "Flask" in tech_stack
        assert "Python" in tech_stack
    
    def test_detect_django_framework(self, dev_agent):
        """Test detection of Django framework."""
        code_files = {
            "views.py": """
from django.http import JsonResponse
from django.views import View

class UserView(View):
    def get(self, request):
        return JsonResponse({'users': []})
"""
        }
        
        tech_stack = dev_agent._detect_tech_stack(code_files)
        
        assert "Django" in tech_stack
        assert "Python" in tech_stack
    
    def test_detect_javascript_frameworks(self, dev_agent):
        """Test detection of JavaScript frameworks."""
        code_files = {
            "server.js": """
const express = require('express');
const app = express();

app.get('/', (req, res) => {
    res.json({message: 'Hello'});
});
""",
            "App.vue": """
<template>
    <div>Hello Vue</div>
</template>
"""
        }
        
        tech_stack = dev_agent._detect_tech_stack(code_files)
        
        assert "Express.js" in tech_stack
        assert "Vue.js" in tech_stack
    
    def test_detect_databases(self, dev_agent):
        """Test detection of various databases."""
        code_files = {
            "db_postgres.py": "import psycopg2",
            "db_mysql.py": "import mysql.connector",
            "db_mongo.py": "from pymongo import MongoClient",
            "db_redis.py": "import redis"
        }
        
        tech_stack = dev_agent._detect_tech_stack(code_files)
        
        assert "PostgreSQL" in tech_stack
        assert "MySQL" in tech_stack
        assert "MongoDB" in tech_stack
        assert "Redis" in tech_stack
    
    def test_detect_typescript(self, dev_agent):
        """Test detection of TypeScript."""
        code_files = {
            "main.ts": """
interface User {
    id: number;
    name: string;
}

const getUser = (id: number): User => {
    return {id, name: 'John'};
};
"""
        }
        
        tech_stack = dev_agent._detect_tech_stack(code_files)
        
        assert "TypeScript" in tech_stack
    
    def test_empty_code_files(self, dev_agent):
        """Test handling of empty code files."""
        code_files = {}
        
        tech_stack = dev_agent._detect_tech_stack(code_files)
        env_vars = dev_agent._extract_env_vars(code_files)
        
        assert isinstance(tech_stack, list)
        assert isinstance(env_vars, dict)
        assert len(tech_stack) == 0
        assert len(env_vars) == 0
    
    def test_code_files_with_no_frameworks(self, dev_agent):
        """Test code files with no recognizable frameworks."""
        code_files = {
            "utils.py": """
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
"""
        }
        
        tech_stack = dev_agent._detect_tech_stack(code_files)
        
        # Should at least detect Python from .py extension
        assert "Python" in tech_stack


class TestDocumentationGeneratorMethods:
    """Test the documentation generator helper methods."""
    
    @pytest.fixture
    def dev_agent(self):
        """Create a DevAgent instance for testing."""
        return DevAgent()
    
    def test_format_env_vars_with_sensitive_data(self, dev_agent):
        """Test that sensitive environment variables are masked."""
        env_vars = {
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "API_KEY": "sk-1234567890abcdef",
            "SECRET_KEY": "super-secret-key",
            "PASSWORD": "my-password",
            "TOKEN": "auth-token-123",
            "DEBUG": "true",
            "PORT": "8000"
        }
        
        formatted = dev_agent.doc_generator._format_env_vars(env_vars)
        
        # Sensitive values should be redacted
        assert "***REDACTED***" in formatted
        
        # Non-sensitive values might be shown
        assert "DEBUG" in formatted or "PORT" in formatted
    
    def test_summarize_codebase(self, dev_agent):
        """Test codebase summarization."""
        code_files = {
            "main.py": """
class UserService:
    def get_user(self, user_id):
        pass
    
    def create_user(self, data):
        pass

def main():
    pass
""",
            "models.py": """
class User:
    pass

class Product:
    pass
""",
            "utils.py": """
def format_date(date):
    pass

def validate_email(email):
    pass
"""
        }
        
        summary = dev_agent.doc_generator._summarize_codebase(code_files)
        
        assert "main.py" in summary
        assert "models.py" in summary
        assert "utils.py" in summary
        
        # Should mention classes or functions
        assert any(keyword in summary for keyword in ["Classes", "Functions", "class", "def"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
