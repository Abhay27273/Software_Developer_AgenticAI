# Implementation Plan

- [x] 1. Enhance ProjectTemplate model with dict-like access








  - Add `__getitem__`, `__contains__`, `__iter__` magic methods to ProjectTemplate class
  - Add `keys()` and `get()` methods for comple
te dict compatibility
  - Verify existing object notation still works
  - _Requirements: 1.1, 1.2, 1.3, 1.4_
- [x] 2. Update TemplateLibrary to accept multiple input types










- [-] 2. Update TemplateLibrary to accept multiple input types

  - [x] 2.1 Enhance save_template method to accept dict or ProjectTemplate

    - Add type checking with isinstance()
    - Convert dict to ProjectTemplate using from_dict()
    - Generate template ID if missing from dict
    - Return template ID string instead of boolean
    - _Requirements: 1.5, 4.1_
  

  - [x] 2.2 Enhance apply_template method to accept template_id or ProjectTemplate

    - Add type checking for string vs object
    - Load template internally if template_id string provided
    - Keep existing logic for ProjectTemplate objects
    - Return dict with 'files' key for backward compatibility
    - _Requirements: 4.2_
  

  - [x] 2.3 Add get_template method for dict representation

    - Load template by ID
    - Return to_dict() representation
    - Handle template not found case
    - _Requirements: 4.3_

  
  - [x] 2.4 Add _generate_template_id helper method





    - Convert name to kebab-case
    - Add timestamp for uniqueness
    - Handle special characters
    - _Requirements: 1.5_

- [x] 3. Fix mock LLM client prompt detection





  - [x] 3.1 Improve prompt parsing in mock_llm_client fixture

    - Extract project_name from prompt using regex
    - Use extracted project_name in README title
    - Add specific detection for "user guide" prompts
    - Add specific detection for "deployment" + "guide" prompts
    - Ensure API documentation is only returned for API-specific prompts
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 5.2, 5.3, 5.4, 5.5_

- [x] 4. Add fallback mechanism to TestGenerator



  - [x] 4.1 Define fallback test templates as class constants


    - Create FALLBACK_UNIT_TEST_TEMPLATE with valid test structure
    - Create FALLBACK_INTEGRATION_TEST_TEMPLATE
    - Include pytest imports and basic test functions
    - _Requirements: 3.2, 3.4_
  
  - [x] 4.2 Add test content validation method


    - Create _is_valid_test_content() method
    - Check for error message indicators
    - Verify presence of "def test_" or "test(" patterns
    - Verify presence of assertions
    - _Requirements: 3.3_
  
  - [x] 4.3 Add fallback test generation method


    - Create _get_fallback_test() method
    - Generate basic test structure for given filename
    - Support different languages (Python, JavaScript)
    - Include TODO comments for manual implementation
    - _Requirements: 3.2, 3.4_
  
  - [x] 4.4 Update generate_unit_tests with fallback logic


    - Wrap LLM calls in try-except blocks
    - Validate generated content before returning
    - Use fallback if validation fails
    - Use fallback if LLM call raises exception
    - _Requirements: 3.1, 3.2, 3.5_
  
  - [x] 4.5 Update generate_integration_tests with fallback logic


    - Apply same fallback pattern as unit tests
    - Use integration-specific fallback template
    - _Requirements: 3.1, 3.2_

- [x] 5. Run integration tests and verify fixes





  - Execute pytest on test_integration_pm_dev_enhancements.py
  - Verify all 5 template system tests pass
  - Verify all 3 documentation generation tests pass
  - Verify test generation test passes
  - Check for any new failures or regressions
  - _Requirements: All_
