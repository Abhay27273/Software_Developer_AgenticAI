"""
Documentation Generator Module

This module provides comprehensive documentation generation capabilities for the Dev Agent.
It generates README files, API documentation, user guides, and deployment guides.
"""

import logging
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

from utils.llm_setup import ask_llm, LLMError

logger = logging.getLogger(__name__)


class ReadmeTemplate:
    """Template for generating consistent README files."""
    
    @staticmethod
    def get_structure() -> str:
        """Get the standard README structure template."""
        return """# {project_name}

{project_description}

## Features

{features}

## Installation

{installation}

## Configuration

{configuration}

## Usage

{usage}

## Troubleshooting

{troubleshooting}

## Contributing

{contributing}

## License

{license}
"""
    
    @staticmethod
    def get_default_sections() -> Dict[str, str]:
        """Get default content for standard sections."""
        return {
            "contributing": """Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request""",
            
            "license": "This project is licensed under the MIT License - see the LICENSE file for details.",
            
            "troubleshooting": """### Common Issues

**Issue**: Application fails to start
- **Solution**: Check that all environment variables are set correctly

**Issue**: Database connection errors
- **Solution**: Verify database credentials and ensure the database server is running

**Issue**: Port already in use
- **Solution**: Change the port in configuration or stop the conflicting service"""
        }


class APIDocGenerator:
    """Generator for OpenAPI/Swagger API documentation."""
    
    def __init__(self, llm_client_func):
        """
        Initialize API documentation generator.
        
        Args:
            llm_client_func: Function to call LLM for content generation
        """
        self.llm_client = llm_client_func
    
    def extract_endpoints_from_code(self, code_files: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Extract API endpoints from code files.
        
        Args:
            code_files: Dictionary of filename -> code content
            
        Returns:
            List of endpoint information dictionaries
        """
        endpoints = []
        
        # Patterns for different frameworks
        patterns = {
            'fastapi': r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',
            'flask': r'@app\.route\(["\']([^"\']+)["\'],\s*methods=\[([^\]]+)\]',
            'express': r'app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',
        }
        
        for filename, content in code_files.items():
            # Check for FastAPI/Flask patterns
            for framework, pattern in patterns.items():
                matches = re.finditer(pattern, content, re.MULTILINE)
                for match in matches:
                    if framework == 'flask':
                        path = match.group(1)
                        methods = match.group(2).replace("'", "").replace('"', '').split(',')
                        for method in methods:
                            endpoints.append({
                                'method': method.strip().upper(),
                                'path': path,
                                'file': filename,
                                'framework': framework
                            })
                    else:
                        method = match.group(1).upper()
                        path = match.group(2)
                        endpoints.append({
                            'method': method,
                            'path': path,
                            'file': filename,
                            'framework': framework
                        })
        
        return endpoints


class UserGuideGenerator:
    """Generator for user-facing documentation and guides."""
    
    def __init__(self, llm_client_func):
        """
        Initialize user guide generator.
        
        Args:
            llm_client_func: Function to call LLM for content generation
        """
        self.llm_client = llm_client_func
    
    def get_guide_structure(self) -> str:
        """Get the standard user guide structure."""
        return """# User Guide

## Getting Started

{getting_started}

## Features

{features_detail}

## Workflows

{workflows}

## FAQ

{faq}

## Support

{support}
"""


class DocumentationGenerator:
    """
    Main documentation generator class that coordinates all documentation generation.
    """
    
    def __init__(self, llm_client_func=None, model: str = "gemini-2.0-flash-exp"):
        """
        Initialize the documentation generator.
        
        Args:
            llm_client_func: Optional custom LLM client function. If None, uses ask_llm
            model: LLM model to use for generation
        """
        self.llm_client = llm_client_func or ask_llm
        self.model = model
        self.readme_template = ReadmeTemplate()
        self.api_doc_generator = APIDocGenerator(self.llm_client)
        self.user_guide_generator = UserGuideGenerator(self.llm_client)
        
        logger.info(f"DocumentationGenerator initialized with model: {model}")
    
    async def generate_readme(
        self,
        project_name: str,
        project_description: str,
        code_files: Dict[str, str],
        tech_stack: Optional[List[str]] = None,
        environment_vars: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate a comprehensive README.md file.
        
        Args:
            project_name: Name of the project
            project_description: Brief description of the project
            code_files: Dictionary of filename -> code content
            tech_stack: List of technologies used
            environment_vars: Dictionary of environment variables
            
        Returns:
            Generated README content as markdown string
        """
        logger.info(f"Generating README for project: {project_name}")
        
        try:
            # Analyze code to extract features and requirements
            code_summary = self._summarize_codebase(code_files)
            
            # Build the prompt for LLM
            prompt = f"""Generate a comprehensive README.md file for a software project.

Project Name: {project_name}
Description: {project_description}

Tech Stack: {', '.join(tech_stack) if tech_stack else 'Not specified'}

Code Summary:
{code_summary}

Environment Variables:
{self._format_env_vars(environment_vars) if environment_vars else 'None'}

Generate a README with these sections:
1. Project Overview - Brief introduction and purpose
2. Features - List of key features (extract from code)
3. Installation - Step-by-step installation instructions
4. Configuration - How to set up environment variables and config
5. Usage - Examples of how to use the application
6. Troubleshooting - Common issues and solutions

Make it professional, clear, and beginner-friendly. Use markdown formatting."""

            readme_content = await self.llm_client(
                user_prompt=prompt,
                system_prompt="You are a technical writer creating clear, comprehensive documentation. Generate well-structured markdown documentation.",
                model=self.model,
                temperature=0.3
            )
            
            # Add contributing and license sections
            default_sections = self.readme_template.get_default_sections()
            readme_content += f"\n\n## Contributing\n\n{default_sections['contributing']}"
            readme_content += f"\n\n## License\n\n{default_sections['license']}"
            
            logger.info("README generation completed successfully")
            return readme_content
            
        except Exception as e:
            logger.error(f"Failed to generate README: {e}", exc_info=True)
            raise
    
    async def generate_api_docs(
        self,
        project_name: str,
        code_files: Dict[str, str],
        base_url: str = "http://localhost:8000"
    ) -> str:
        """
        Generate API documentation in OpenAPI/Swagger format.
        
        Args:
            project_name: Name of the project
            code_files: Dictionary of filename -> code content
            base_url: Base URL for the API
            
        Returns:
            Generated API documentation as markdown string
        """
        logger.info(f"Generating API documentation for: {project_name}")
        
        try:
            # Extract endpoints from code
            endpoints = self.api_doc_generator.extract_endpoints_from_code(code_files)
            
            if not endpoints:
                logger.warning("No API endpoints found in code")
                return "# API Documentation\n\nNo API endpoints detected in the codebase."
            
            # Build endpoint details for LLM
            endpoints_summary = "\n".join([
                f"- {ep['method']} {ep['path']} (in {ep['file']})"
                for ep in endpoints
            ])
            
            # Get relevant code context for each endpoint
            code_context = self._extract_endpoint_context(code_files, endpoints)
            
            prompt = f"""Generate comprehensive API documentation for a REST API.

Project: {project_name}
Base URL: {base_url}

Detected Endpoints:
{endpoints_summary}

Code Context:
{code_context}

Generate API documentation with:
1. Overview - Brief description of the API
2. Authentication - How to authenticate (if applicable)
3. Endpoints - For each endpoint:
   - Method and path
   - Description
   - Request parameters/body
   - Response format with examples
   - Status codes
   - Error responses
4. Common Error Codes - Standard error responses

Use markdown format with clear examples. Include sample requests and responses in JSON format."""

            api_docs = await self.llm_client(
                user_prompt=prompt,
                system_prompt="You are an API documentation specialist. Create clear, detailed API documentation with examples.",
                model=self.model,
                temperature=0.3
            )
            
            logger.info(f"API documentation generated for {len(endpoints)} endpoints")
            return api_docs
            
        except Exception as e:
            logger.error(f"Failed to generate API documentation: {e}", exc_info=True)
            raise
    
    async def generate_user_guide(
        self,
        project_name: str,
        project_description: str,
        code_files: Dict[str, str],
        features: Optional[List[str]] = None
    ) -> str:
        """
        Generate a user guide explaining features and workflows.
        
        Args:
            project_name: Name of the project
            project_description: Brief description
            code_files: Dictionary of filename -> code content
            features: List of features to document
            
        Returns:
            Generated user guide as markdown string
        """
        logger.info(f"Generating user guide for: {project_name}")
        
        try:
            # Analyze code to identify features if not provided
            if not features:
                features = self._extract_features_from_code(code_files)
            
            features_text = "\n".join([f"- {feature}" for feature in features])
            
            prompt = f"""Generate a comprehensive user guide for an application.

Project: {project_name}
Description: {project_description}

Features:
{features_text}

Generate a user guide with:
1. Getting Started - Quick start tutorial for new users
2. Features - Detailed explanation of each feature with examples
3. Workflows - Common use cases and step-by-step workflows
4. FAQ - Frequently asked questions and answers
5. Support - How to get help

Make it user-friendly and include practical examples. Use markdown with screenshots placeholders where helpful."""

            user_guide = await self.llm_client(
                user_prompt=prompt,
                system_prompt="You are a technical writer creating user-friendly documentation. Focus on clarity and practical examples.",
                model=self.model,
                temperature=0.4
            )
            
            logger.info("User guide generation completed")
            return user_guide
            
        except Exception as e:
            logger.error(f"Failed to generate user guide: {e}", exc_info=True)
            raise
    
    async def generate_deployment_guide(
        self,
        project_name: str,
        code_files: Dict[str, str],
        tech_stack: Optional[List[str]] = None,
        environment_vars: Optional[Dict[str, str]] = None,
        deployment_platform: str = "Generic"
    ) -> str:
        """
        Generate deployment documentation.
        
        Args:
            project_name: Name of the project
            code_files: Dictionary of filename -> code content
            tech_stack: List of technologies used
            environment_vars: Dictionary of environment variables
            deployment_platform: Target deployment platform
            
        Returns:
            Generated deployment guide as markdown string
        """
        logger.info(f"Generating deployment guide for: {project_name}")
        
        try:
            # Detect deployment requirements
            has_docker = any('dockerfile' in f.lower() for f in code_files.keys())
            has_requirements = 'requirements.txt' in code_files
            has_package_json = 'package.json' in code_files
            
            deployment_info = {
                'has_docker': has_docker,
                'has_requirements': has_requirements,
                'has_package_json': has_package_json,
                'tech_stack': tech_stack or []
            }
            
            prompt = f"""Generate a comprehensive deployment guide for a software project.

Project: {project_name}
Platform: {deployment_platform}
Tech Stack: {', '.join(tech_stack) if tech_stack else 'Not specified'}

Deployment Configuration:
- Docker: {'Yes' if has_docker else 'No'}
- Python Requirements: {'Yes' if has_requirements else 'No'}
- Node.js Package: {'Yes' if has_package_json else 'No'}

Environment Variables:
{self._format_env_vars(environment_vars) if environment_vars else 'None'}

Generate deployment documentation with:
1. Prerequisites - Required tools and accounts
2. Environment Setup - How to configure environment variables
3. Deployment Steps - Step-by-step deployment instructions
4. Scaling Guidelines - How to scale the application
5. Monitoring Setup - How to set up health checks and monitoring
6. Rollback Procedures - How to rollback if deployment fails
7. Troubleshooting - Common deployment issues and solutions

Include specific commands and configuration examples. Make it production-ready."""

            deployment_guide = await self.llm_client(
                user_prompt=prompt,
                system_prompt="You are a DevOps engineer creating deployment documentation. Focus on production-ready practices and clear instructions.",
                model=self.model,
                temperature=0.3
            )
            
            logger.info("Deployment guide generation completed")
            return deployment_guide
            
        except Exception as e:
            logger.error(f"Failed to generate deployment guide: {e}", exc_info=True)
            raise
    
    async def generate_all_documentation(
        self,
        project_name: str,
        project_description: str,
        code_files: Dict[str, str],
        tech_stack: Optional[List[str]] = None,
        environment_vars: Optional[Dict[str, str]] = None,
        deployment_platform: str = "Generic"
    ) -> Dict[str, str]:
        """
        Generate all documentation files at once.
        
        Args:
            project_name: Name of the project
            project_description: Brief description
            code_files: Dictionary of filename -> code content
            tech_stack: List of technologies used
            environment_vars: Dictionary of environment variables
            deployment_platform: Target deployment platform
            
        Returns:
            Dictionary of documentation filename -> content
        """
        logger.info(f"Generating all documentation for: {project_name}")
        
        docs = {}
        
        try:
            # Generate README
            docs['README.md'] = await self.generate_readme(
                project_name, project_description, code_files, tech_stack, environment_vars
            )
            
            # Generate API documentation
            docs['API_DOCUMENTATION.md'] = await self.generate_api_docs(
                project_name, code_files
            )
            
            # Generate user guide
            docs['USER_GUIDE.md'] = await self.generate_user_guide(
                project_name, project_description, code_files
            )
            
            # Generate deployment guide
            docs['DEPLOYMENT_GUIDE.md'] = await self.generate_deployment_guide(
                project_name, code_files, tech_stack, environment_vars, deployment_platform
            )
            
            logger.info(f"Generated {len(docs)} documentation files")
            return docs
            
        except Exception as e:
            logger.error(f"Failed to generate all documentation: {e}", exc_info=True)
            raise
    
    # Helper methods
    
    def _summarize_codebase(self, code_files: Dict[str, str]) -> str:
        """Create a summary of the codebase for documentation context."""
        summary_parts = []
        
        for filename, content in list(code_files.items())[:10]:  # Limit to first 10 files
            lines = content.split('\n')
            summary_parts.append(f"File: {filename} ({len(lines)} lines)")
            
            # Extract key information
            if filename.endswith('.py'):
                classes = re.findall(r'class\s+(\w+)', content)
                functions = re.findall(r'def\s+(\w+)', content)
                if classes:
                    summary_parts.append(f"  Classes: {', '.join(classes[:5])}")
                if functions:
                    summary_parts.append(f"  Functions: {', '.join(functions[:5])}")
        
        return '\n'.join(summary_parts)
    
    def _format_env_vars(self, env_vars: Dict[str, str]) -> str:
        """Format environment variables for documentation."""
        if not env_vars:
            return "No environment variables required"
        
        formatted = []
        for key, value in env_vars.items():
            # Mask sensitive values
            if any(sensitive in key.lower() for sensitive in ['key', 'secret', 'password', 'token']):
                display_value = "***REDACTED***"
            else:
                display_value = value
            formatted.append(f"- `{key}`: {display_value}")
        
        return '\n'.join(formatted)
    
    def _extract_endpoint_context(self, code_files: Dict[str, str], endpoints: List[Dict]) -> str:
        """Extract relevant code context for API endpoints."""
        context_parts = []
        
        for endpoint in endpoints[:10]:  # Limit to first 10 endpoints
            file_content = code_files.get(endpoint['file'], '')
            
            # Find the function definition for this endpoint
            path_pattern = endpoint['path'].replace('/', '\\/').replace('{', '\\{').replace('}', '\\}')
            pattern = rf"@app\.{endpoint['method'].lower()}\(['\"].*?{path_pattern}.*?['\"].*?\).*?def\s+(\w+)"
            
            match = re.search(pattern, file_content, re.DOTALL)
            if match:
                func_name = match.group(1)
                context_parts.append(f"{endpoint['method']} {endpoint['path']} -> {func_name}()")
        
        return '\n'.join(context_parts) if context_parts else "No detailed context available"
    
    def _extract_features_from_code(self, code_files: Dict[str, str]) -> List[str]:
        """Extract features from code analysis."""
        features = []
        
        # Look for common patterns that indicate features
        for filename, content in code_files.items():
            # API endpoints indicate features
            if 'api' in filename.lower() or 'routes' in filename.lower():
                endpoints = re.findall(r'@app\.\w+\(["\']([^"\']+)["\']', content)
                for endpoint in endpoints:
                    # Convert endpoint to feature description
                    feature = endpoint.strip('/').replace('/', ' ').replace('-', ' ').replace('_', ' ')
                    if feature and feature not in features:
                        features.append(feature.title())
            
            # Class names can indicate features
            classes = re.findall(r'class\s+(\w+)', content)
            for cls in classes:
                if not cls.endswith('Test') and cls not in ['Base', 'Config']:
                    feature = re.sub(r'([A-Z])', r' \1', cls).strip()
                    if feature and feature not in features:
                        features.append(feature)
        
        return features[:10] if features else ["Core functionality"]
