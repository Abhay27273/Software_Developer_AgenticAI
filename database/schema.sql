-- Database schema for Software Developer Agentic AI
-- Production Enhancement Features

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- PROJECT CONTEXTS TABLE
-- ============================================================================
-- Stores project state across iterations including codebase, configuration,
-- and metrics.

CREATE TABLE IF NOT EXISTS project_contexts (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Basic information
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('api', 'web_app', 'mobile_backend', 'data_pipeline', 'microservice')),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    owner_id VARCHAR(255) NOT NULL,
    
    -- Code and structure (JSONB for flexible schema)
    codebase JSONB DEFAULT '{}'::jsonb,
    dependencies TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Configuration (JSONB for flexible schema)
    environment_vars JSONB DEFAULT '{}'::jsonb,
    deployment_config JSONB DEFAULT '{}'::jsonb,
    
    -- Metrics
    test_coverage DECIMAL(5,4) DEFAULT 0.0 CHECK (test_coverage >= 0.0 AND test_coverage <= 1.0),
    security_score DECIMAL(5,4) DEFAULT 0.0 CHECK (security_score >= 0.0 AND security_score <= 1.0),
    performance_score DECIMAL(5,4) DEFAULT 0.0 CHECK (performance_score >= 0.0 AND performance_score <= 1.0),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_deployed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for project_contexts table
CREATE INDEX IF NOT EXISTS idx_project_contexts_owner_id ON project_contexts(owner_id);
CREATE INDEX IF NOT EXISTS idx_project_contexts_status ON project_contexts(status);
CREATE INDEX IF NOT EXISTS idx_project_contexts_type ON project_contexts(type);
CREATE INDEX IF NOT EXISTS idx_project_contexts_created_at ON project_contexts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_project_contexts_updated_at ON project_contexts(updated_at DESC);

-- GIN index for JSONB columns for efficient querying
CREATE INDEX IF NOT EXISTS idx_project_contexts_codebase ON project_contexts USING GIN (codebase);
CREATE INDEX IF NOT EXISTS idx_project_contexts_environment_vars ON project_contexts USING GIN (environment_vars);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_project_contexts_owner_status ON project_contexts(owner_id, status);

-- ============================================================================
-- MODIFICATIONS TABLE
-- ============================================================================
-- Tracks project modification requests, analysis, and results.

CREATE TABLE IF NOT EXISTS modifications (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Foreign key to project
    project_id UUID NOT NULL REFERENCES project_contexts(id) ON DELETE CASCADE,
    
    -- Request details
    request TEXT NOT NULL,
    requested_by VARCHAR(255) NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Analysis (JSONB for flexible schema)
    impact_analysis JSONB DEFAULT '{}'::jsonb,
    affected_files TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Execution status
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'applied', 'failed', 'rejected')),
    applied_at TIMESTAMP WITH TIME ZONE,
    
    -- Results (JSONB for flexible schema)
    modified_files JSONB DEFAULT '{}'::jsonb,
    test_results JSONB DEFAULT '{}'::jsonb
);

-- Indexes for modifications table
CREATE INDEX IF NOT EXISTS idx_modifications_project_id ON modifications(project_id);
CREATE INDEX IF NOT EXISTS idx_modifications_requested_by ON modifications(requested_by);
CREATE INDEX IF NOT EXISTS idx_modifications_status ON modifications(status);
CREATE INDEX IF NOT EXISTS idx_modifications_requested_at ON modifications(requested_at DESC);

-- GIN indexes for JSONB columns
CREATE INDEX IF NOT EXISTS idx_modifications_impact_analysis ON modifications USING GIN (impact_analysis);
CREATE INDEX IF NOT EXISTS idx_modifications_test_results ON modifications USING GIN (test_results);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_modifications_project_status ON modifications(project_id, status);

-- ============================================================================
-- TEMPLATES TABLE
-- ============================================================================
-- Stores reusable project templates with customization variables.

CREATE TABLE IF NOT EXISTS templates (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Basic information
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL CHECK (category IN ('api', 'web', 'mobile', 'data', 'microservice')),
    
    -- Template content (JSONB for flexible schema)
    files JSONB DEFAULT '{}'::jsonb,
    
    -- Configuration
    required_vars TEXT[] DEFAULT ARRAY[]::TEXT[],
    optional_vars TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Metadata
    tech_stack TEXT[] DEFAULT ARRAY[]::TEXT[],
    estimated_setup_time INTEGER DEFAULT 15,
    complexity VARCHAR(20) DEFAULT 'medium' CHECK (complexity IN ('simple', 'medium', 'complex')),
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for templates table
CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category);
CREATE INDEX IF NOT EXISTS idx_templates_complexity ON templates(complexity);
CREATE INDEX IF NOT EXISTS idx_templates_created_at ON templates(created_at DESC);

-- GIN index for JSONB files column
CREATE INDEX IF NOT EXISTS idx_templates_files ON templates USING GIN (files);

-- GIN index for array columns
CREATE INDEX IF NOT EXISTS idx_templates_tech_stack ON templates USING GIN (tech_stack);
CREATE INDEX IF NOT EXISTS idx_templates_tags ON templates USING GIN (tags);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Trigger to automatically update updated_at timestamp for project_contexts
CREATE OR REPLACE FUNCTION update_project_contexts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_project_contexts_updated_at
    BEFORE UPDATE ON project_contexts
    FOR EACH ROW
    EXECUTE FUNCTION update_project_contexts_updated_at();

-- Trigger to automatically update updated_at timestamp for templates
CREATE OR REPLACE FUNCTION update_templates_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_templates_updated_at
    BEFORE UPDATE ON templates
    FOR EACH ROW
    EXECUTE FUNCTION update_templates_updated_at();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE project_contexts IS 'Stores project state across iterations including codebase, configuration, and metrics';
COMMENT ON COLUMN project_contexts.codebase IS 'JSONB storage for project files (filename -> content)';
COMMENT ON COLUMN project_contexts.environment_vars IS 'JSONB storage for environment variables';
COMMENT ON COLUMN project_contexts.deployment_config IS 'JSONB storage for deployment configuration';

COMMENT ON TABLE modifications IS 'Tracks project modification requests, analysis, and results';
COMMENT ON COLUMN modifications.impact_analysis IS 'JSONB storage for modification impact analysis';
COMMENT ON COLUMN modifications.affected_files IS 'Array of file paths affected by modification';
COMMENT ON COLUMN modifications.modified_files IS 'JSONB storage for modified file contents';
COMMENT ON COLUMN modifications.test_results IS 'JSONB storage for test execution results';

COMMENT ON TABLE templates IS 'Stores reusable project templates with customization variables';
COMMENT ON COLUMN templates.files IS 'JSONB storage for template files (filename -> template content)';
COMMENT ON COLUMN templates.tech_stack IS 'Array of technologies used in template';
COMMENT ON COLUMN templates.tags IS 'Array of tags for template categorization';
