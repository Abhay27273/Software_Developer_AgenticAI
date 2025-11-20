"""Create modifications table

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create modifications table for tracking project changes.
    
    This table stores modification requests, impact analysis, and results.
    """
    
    # Create modifications table
    op.create_table(
        'modifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        
        # Foreign key to project
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Request details
        sa.Column('request', sa.Text, nullable=False),
        sa.Column('requested_by', sa.String(255), nullable=False),
        sa.Column('requested_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        
        # Analysis (JSONB for flexible schema)
        sa.Column('impact_analysis', postgresql.JSONB, server_default='{}'),
        sa.Column('affected_files', postgresql.ARRAY(sa.Text), server_default='{}'),
        
        # Execution status
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('applied_at', sa.TIMESTAMP(timezone=True), nullable=True),
        
        # Results (JSONB for flexible schema)
        sa.Column('modified_files', postgresql.JSONB, server_default='{}'),
        sa.Column('test_results', postgresql.JSONB, server_default='{}'),
        
        # Constraints
        sa.ForeignKeyConstraint(['project_id'], ['project_contexts.id'], 
                               ondelete='CASCADE', name='fk_modifications_project_id'),
        sa.CheckConstraint("status IN ('pending', 'approved', 'applied', 'failed', 'rejected')",
                          name='check_modification_status'),
    )
    
    # Create indexes for performance
    op.create_index('idx_modifications_project_id', 'modifications', ['project_id'])
    op.create_index('idx_modifications_requested_by', 'modifications', ['requested_by'])
    op.create_index('idx_modifications_status', 'modifications', ['status'])
    op.create_index('idx_modifications_requested_at', 'modifications',
                    [sa.text('requested_at DESC')])
    
    # GIN indexes for JSONB columns
    op.create_index('idx_modifications_impact_analysis', 'modifications',
                    ['impact_analysis'], postgresql_using='gin')
    op.create_index('idx_modifications_test_results', 'modifications',
                    ['test_results'], postgresql_using='gin')
    
    # Composite index for common queries
    op.create_index('idx_modifications_project_status', 'modifications',
                    ['project_id', 'status'])


def downgrade() -> None:
    """
    Drop modifications table and related objects.
    """
    # Drop indexes
    op.drop_index('idx_modifications_project_status', table_name='modifications')
    op.drop_index('idx_modifications_test_results', table_name='modifications')
    op.drop_index('idx_modifications_impact_analysis', table_name='modifications')
    op.drop_index('idx_modifications_requested_at', table_name='modifications')
    op.drop_index('idx_modifications_status', table_name='modifications')
    op.drop_index('idx_modifications_requested_by', table_name='modifications')
    op.drop_index('idx_modifications_project_id', table_name='modifications')
    
    # Drop table
    op.drop_table('modifications')
