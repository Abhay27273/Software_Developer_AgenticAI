"""
Demo script showing how to use the CodeModifier with LangGraph.

This script demonstrates:
1. Basic code modification
2. Adding new functions
3. Modifying existing functions
4. Handling errors and rollback
5. Viewing diffs
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.code_modifier import CodeModifier, modify_code_file


# Sample code to modify
SAMPLE_CALCULATOR = '''
class Calculator:
    """A simple calculator class."""
    
    def add(self, a, b):
        """Add two numbers."""
        return a + b
    
    def subtract(self, a, b):
        """Subtract b from a."""
        return a - b
    
    def multiply(self, a, b):
        """Multiply two numbers."""
        return a * b
'''


async def demo_basic_modification():
    """Demo 1: Basic code modification - add input validation."""
    print("=" * 80)
    print("DEMO 1: Adding Input Validation")
    print("=" * 80)
    
    modification_request = """
    Add input validation to all methods in the Calculator class.
    Each method should check that both a and b are numbers (int or float).
    If not, raise a TypeError with a descriptive message.
    """
    
    result = await modify_code_file(
        file_path="calculator.py",
        original_content=SAMPLE_CALCULATOR,
        modification_request=modification_request
    )
    
    if result.success:
        print("✅ Modification successful!")
        print("\n📝 Modified Code:")
        print("-" * 80)
        print(result.modified_files["calculator.py"])
        print("-" * 80)
        
        print("\n📊 Diff:")
        print("-" * 80)
        print(result.diff)
        print("-" * 80)
    else:
        print("❌ Modification failed!")
        print(f"Errors: {result.validation_errors}")
    
    print("\n")


async def demo_add_new_method():
    """Demo 2: Add a new method to the class."""
    print("=" * 80)
    print("DEMO 2: Adding New Method")
    print("=" * 80)
    
    modification_request = """
    Add a new method called 'divide' to the Calculator class.
    The method should:
    1. Take two parameters: a and b
    2. Check if b is zero and raise a ZeroDivisionError if it is
    3. Return the result of a divided by b
    4. Include a docstring
    """
    
    result = await modify_code_file(
        file_path="calculator.py",
        original_content=SAMPLE_CALCULATOR,
        modification_request=modification_request
    )
    
    if result.success:
        print("✅ Modification successful!")
        print("\n📝 Modified Code:")
        print("-" * 80)
        print(result.modified_files["calculator.py"])
        print("-" * 80)
        
        print("\n📊 Diff:")
        print("-" * 80)
        print(result.diff)
        print("-" * 80)
    else:
        print("❌ Modification failed!")
        print(f"Errors: {result.validation_errors}")
    
    print("\n")


async def demo_refactor_code():
    """Demo 3: Refactor code to use a helper method."""
    print("=" * 80)
    print("DEMO 3: Refactoring with Helper Method")
    print("=" * 80)
    
    modification_request = """
    Refactor the Calculator class to use a private helper method for validation.
    Create a method called '_validate_numbers' that checks if both inputs are numbers.
    Update all existing methods to use this helper method.
    """
    
    result = await modify_code_file(
        file_path="calculator.py",
        original_content=SAMPLE_CALCULATOR,
        modification_request=modification_request
    )
    
    if result.success:
        print("✅ Modification successful!")
        print("\n📝 Modified Code:")
        print("-" * 80)
        print(result.modified_files["calculator.py"])
        print("-" * 80)
        
        print("\n📊 Diff:")
        print("-" * 80)
        print(result.diff)
        print("-" * 80)
    else:
        print("❌ Modification failed!")
        print(f"Errors: {result.validation_errors}")
    
    print("\n")


async def demo_add_logging():
    """Demo 4: Add logging to methods."""
    print("=" * 80)
    print("DEMO 4: Adding Logging")
    print("=" * 80)
    
    modification_request = """
    Add logging to the Calculator class:
    1. Import the logging module at the top
    2. Create a logger instance in the __init__ method
    3. Add debug logging to each method showing the operation and result
    """
    
    result = await modify_code_file(
        file_path="calculator.py",
        original_content=SAMPLE_CALCULATOR,
        modification_request=modification_request
    )
    
    if result.success:
        print("✅ Modification successful!")
        print("\n📝 Modified Code:")
        print("-" * 80)
        print(result.modified_files["calculator.py"])
        print("-" * 80)
        
        print("\n📊 Diff:")
        print("-" * 80)
        print(result.diff)
        print("-" * 80)
    else:
        print("❌ Modification failed!")
        print(f"Errors: {result.validation_errors}")
    
    print("\n")


async def demo_error_handling():
    """Demo 5: Demonstrate error handling and rollback."""
    print("=" * 80)
    print("DEMO 5: Error Handling and Rollback")
    print("=" * 80)
    
    # This should fail because we're asking for something that would break the code
    modification_request = """
    Remove all methods from the Calculator class and replace them with a single
    method that doesn't make sense.
    """
    
    result = await modify_code_file(
        file_path="calculator.py",
        original_content=SAMPLE_CALCULATOR,
        modification_request=modification_request
    )
    
    if result.success:
        print("⚠️ Modification succeeded (unexpected)")
    else:
        print("✅ Modification correctly failed!")
        print(f"\n❌ Validation Errors:")
        for error in result.validation_errors:
            print(f"  - {error}")
        
        print(f"\n🔄 Rollback Available: {result.rollback_available}")
        print("Original code would be preserved.")
    
    print("\n")


async def demo_using_code_modifier_class():
    """Demo 6: Using CodeModifier class directly for more control."""
    print("=" * 80)
    print("DEMO 6: Using CodeModifier Class Directly")
    print("=" * 80)
    
    # Create a CodeModifier instance
    modifier = CodeModifier(model="gemini-2.5-pro")
    
    modification_request = """
    Add a method called 'power' that raises a to the power of b.
    Include proper error handling for negative exponents with floats.
    """
    
    print("🔧 Initializing CodeModifier...")
    print(f"   Model: {modifier.model}")
    print(f"   Workflow: {type(modifier.workflow).__name__}")
    
    print("\n🚀 Starting modification workflow...")
    result = await modifier.modify_code(
        file_path="calculator.py",
        original_content=SAMPLE_CALCULATOR,
        modification_request=modification_request
    )
    
    if result.success:
        print("✅ Modification successful!")
        print("\n📝 Modified Code:")
        print("-" * 80)
        print(result.modified_files["calculator.py"])
        print("-" * 80)
        
        print("\n📊 Metadata:")
        print(f"  - Timestamp: {result.metadata.get('timestamp', 'N/A')}")
        print(f"  - Rollback Available: {result.rollback_available}")
    else:
        print("❌ Modification failed!")
        print(f"Errors: {result.validation_errors}")
    
    print("\n")


async def demo_complex_modification():
    """Demo 7: Complex modification with multiple changes."""
    print("=" * 80)
    print("DEMO 7: Complex Multi-Step Modification")
    print("=" * 80)
    
    modification_request = """
    Make the following changes to the Calculator class:
    1. Add an __init__ method that initializes a history list
    2. Modify all methods to record operations in the history
    3. Add a 'get_history' method that returns the history
    4. Add a 'clear_history' method that clears the history
    5. Add type hints to all methods
    """
    
    result = await modify_code_file(
        file_path="calculator.py",
        original_content=SAMPLE_CALCULATOR,
        modification_request=modification_request
    )
    
    if result.success:
        print("✅ Modification successful!")
        print("\n📝 Modified Code:")
        print("-" * 80)
        print(result.modified_files["calculator.py"])
        print("-" * 80)
        
        print("\n📊 Diff:")
        print("-" * 80)
        print(result.diff)
        print("-" * 80)
        
        print("\n📈 Modification Statistics:")
        diff_lines = result.diff.split('\n')
        additions = len([l for l in diff_lines if l.startswith('+')])
        deletions = len([l for l in diff_lines if l.startswith('-')])
        print(f"  - Lines added: {additions}")
        print(f"  - Lines removed: {deletions}")
        print(f"  - Net change: {additions - deletions}")
    else:
        print("❌ Modification failed!")
        print(f"Errors: {result.validation_errors}")
    
    print("\n")


async def main():
    """Run all demos."""
    print("\n")
    print("🎯 CodeModifier with LangGraph - Demo Suite")
    print("=" * 80)
    print("This demo shows various code modification scenarios using LangGraph")
    print("=" * 80)
    print("\n")
    
    demos = [
        ("Basic Modification", demo_basic_modification),
        ("Add New Method", demo_add_new_method),
        ("Refactor Code", demo_refactor_code),
        ("Add Logging", demo_add_logging),
        ("Error Handling", demo_error_handling),
        ("Direct Class Usage", demo_using_code_modifier_class),
        ("Complex Modification", demo_complex_modification),
    ]
    
    for i, (name, demo_func) in enumerate(demos, 1):
        print(f"\n{'='*80}")
        print(f"Running Demo {i}/{len(demos)}: {name}")
        print(f"{'='*80}\n")
        
        try:
            await demo_func()
        except Exception as e:
            print(f"❌ Demo failed with error: {e}")
            import traceback
            traceback.print_exc()
        
        if i < len(demos):
            print("\n⏸️  Press Enter to continue to next demo...")
            input()
    
    print("\n")
    print("=" * 80)
    print("✅ All demos completed!")
    print("=" * 80)
    print("\n")
    print("💡 Key Takeaways:")
    print("  1. CodeModifier uses LangGraph for stateful workflow")
    print("  2. Automatic syntax validation and error handling")
    print("  3. Diff generation for reviewing changes")
    print("  4. Rollback capability for failed modifications")
    print("  5. Preserves existing functionality by default")
    print("\n")


if __name__ == "__main__":
    # Note: This demo requires API keys to be set in environment
    print("⚠️  Note: This demo requires LLM API keys to be configured")
    print("   Set GOOGLE_API_KEY or other provider keys in your .env file")
    print("\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
