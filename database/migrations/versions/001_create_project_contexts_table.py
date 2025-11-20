"""Create project_contexts table

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create project_contexts table with all required columns and indexes.
    
    This table stores project state across iterations including codebase,
    configuration, and metrics.
    """
    
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Create project_contexts table
    op.create_table(
        'project_contexts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, 
                  server_default=sa.text('uuid_generate_v4()')),
        
        # Basic information
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('owner_id', sa.String(255), nullable=False),
        
        # Code and structure (JSONB for flexible schema)
        sa.Column('codebase', postgresql.JSONB, server_default='{}'),
        sa.Column('dependencies', postgresql.ARRAY(sa.Text), server_default='{}'),
        
        # Configuration (JSONB for flexible schema)
        sa.Column('environment_vars', postgresql.JSONB, server_default='{}'),
        sa.Column('deployment_config', postgresql.JSONB, server_default='{}'),
        
        # Metrics
        sa.Column('test_coverage', sa.Numeric(5, 4), server_default='0.0'),
        sa.Column('security_score', sa.Numeric(5, 4), server_default='0.0'),
        sa.Column('performance_score', sa.Numeric(5, 4), server_default='0.0'),
        
        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), 
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), 
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_deployed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        
        # Constraints
        sa.CheckConstraint("type IN ('api', 'web_app', 'mobile_backend', 'data_pipeline', 'microservice')", 
                          name='check_project_type'),
        sa.CheckConstraint("status IN ('active', 'archived', 'deleted')", 
                          name='check_project_status'),
        sa.CheckConstraint('test_coverage >= 0.0 AND test_coverage <= 1.0', 
                          name='check_test_coverage_range'),
        sa.CheckConstraint('security_score >= 0.0 AND security_score <= 1.0', 
                          name='check_security_score_range'),
        sa.CheckConstraint('performance_score >= 0.0 AND performance_score <= 1.0', 
                          name='check_performance_score_range'),
    )
    
    # Create indexes for performance
    op.create_index('idx_project_contexts_owner_id', 'project_contexts', ['owner_id'])
    op.create_index('idx_project_contexts_status', 'project_contexts', ['status'])
    op.create_index('idx_project_contexts_type', 'project_contexts', ['type'])
    op.create_index('idx_project_contexts_created_at', 'project_contexts', 
                    [sa.text('created_at DESC')])
    op.create_index('idx_project_contexts_updated_at', 'project_contexts', 
                    [sa.text('updated_at DESC')])
    
    # GIN indexes for JSONB columns for efficient querying
    op.create_index('idx_project_contexts_codebase', 'project_contexts', ['codebase'],
                    postgresql_using='gin')
    op.create_index('idx_project_contexts_environment_vars', 'project_contexts', 
                    ['environment_vars'], postgresql_using='gin')
    
    # Composite index for common queries
    op.create_index('idx_project_contexts_owner_status', 'project_contexts', 
                    ['owner_id', 'status'])
    
    # Create trigger function for updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_project_contexts_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger
    op.execute("""
        CREATE TRIGGER trigger_update_project_contexts_updated_at
            BEFORE UPDATE ON project_contexts
            FOR EACH ROW
            EXECUTE FUNCTION update_project_contexts_updated_at();
    """)


def downgrade() -> None:
    """
    Drop project_contexts table and related objects.
    """
    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS trigger_update_project_contexts_updated_at ON project_contexts')
    
    # Drop trigger function
    op.execute('DROP FUNCTION IF EXISTS update_project_contexts_updated_at()')
    
    # Drop indexes (will be dropped automatically with table, but explicit for clarity)
    op.drop_index('idx_project_contexts_owner_status', table_name='project_contexts')
    op.drop_index('idx_project_contexts_environment_vars', table_name='project_contexts')
    op.drop_index('idx_project_contexts_codebase', table_name='project_contexts')
    op.drop_index('idx_project_contexts_updated_at', table_name='project_contexts')
    op.drop_index('idx_project_contexts_created_at', table_name='project_contexts')
    op.drop_index('idx_project_contexts_type', table_name='project_contexts')
    op.drop_index('idx_project_contexts_status', table_name='project_contexts')
    op.drop_index('idx_project_contexts_owner_id', table_name='project_contexts')
    
    # Drop table
    op.drop_table('project_contexts')
