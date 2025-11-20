"""
Test script to verify template library integration with PM Agent.

This script tests:
1. Listing available templates
2. Getting template details
3. Creating a project from a template
"""

import asyncio
import logging
from agents.pm_agent import PlannerAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_template_integration():
    """Test the template library integration."""
    print("\n" + "="*60)
    print("Testing Template Library Integration")
    print("="*60 + "\n")
    
    # Initialize PM Agent
    pm_agent = PlannerAgent()
    
    # Test 1: List all templates
    print("Test 1: Listing all available templates...")
    templates = await pm_agent.list_available_templates()
    print(f"✅ Found {len(templates)} templates:")
    for template in templates:
        print(f"   - {template['name']} ({template['category']})")
    print()
    
    # Test 2: List templates by category
    print("Test 2: Listing templates in 'api' category...")
    api_templates = await pm_agent.list_available_templates(category="api")
    print(f"✅ Found {len(api_templates)} API template(s):")
    for template in api_templates:
        print(f"   - {template['name']}")
    print()
    
    # Test 3: Get template details
    if templates:
        template_id = templates[0]['id']
        print(f"Test 3: Getting details for template '{template_id}'...")
        details = await pm_agent.get_template_details(template_id)
        if details:
            print(f"✅ Template Details:")
            print(f"   Name: {details['name']}")
            print(f"   Category: {details['category']}")
            print(f"   Tech Stack: {', '.join(details['tech_stack'])}")
            print(f"   Complexity: {details['complexity']}")
            print(f"   Setup Time: {details['estimated_setup_time']} minutes")
            print(f"   Files: {details['file_count']}")
            print(f"   Required Variables: {', '.join(details['required_vars'])}")
        print()
    
    # Test 4: Get template variables
    if templates:
        template_id = templates[0]['id']
        print(f"Test 4: Getting required variables for template '{template_id}'...")
        variables = await pm_agent.prompt_for_template_variables(template_id)
        print(f"✅ Template Variables:")
        print(f"   Required: {', '.join(variables['required'])}")
        print(f"   Optional: {', '.join(variables['optional'])}")
        print()
    
    # Test 5: Create a project from template
    if templates:
        template_id = templates[0]['id']
        print(f"Test 5: Creating a project from template '{template_id}'...")
        
        # Provide required variables
        variables = {
            "project_name": "My Test API",
            "db_name": "testdb",
            "project_description": "A test API project created from template"
        }
        
        project = await pm_agent.create_project_from_template(
            template_id=template_id,
            variables=variables,
            project_name="Test API Project"
        )
        
        if project:
            print(f"✅ Project Created Successfully:")
            print(f"   Project ID: {project.id}")
            print(f"   Project Name: {project.name}")
            print(f"   Project Type: {project.type.value}")
            print(f"   Files Created: {len(project.codebase)}")
            print(f"   Files:")
            for filename in list(project.codebase.keys())[:5]:  # Show first 5 files
                print(f"      - {filename}")
            if len(project.codebase) > 5:
                print(f"      ... and {len(project.codebase) - 5} more files")
        else:
            print("❌ Failed to create project from template")
        print()
    
    print("="*60)
    print("Template Integration Tests Complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_template_integration())
