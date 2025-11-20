"""Create templates table

Revision ID: 003
Revises: 002
Create Date: 2024-01-01 00:02:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create templates table for storing reusable project templates.
    
    This table stores project templates with customization variables.
    """
    
    # Create templates table
    op.create_table(
        'templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        
        # Basic information
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        
        # Template content (JSONB for flexible schema)
        sa.Column('files', postgresql.JSONB, server_default='{}'),
        
        # Configuration
        sa.Column('required_vars', postgresql.ARRAY(sa.Text), server_default='{}'),
        sa.Column('optional_vars', postgresql.ARRAY(sa.Text), server_default='{}'),
        
        # Metadata
        sa.Column('tech_stack', postgresql.ARRAY(sa.Text), server_default='{}'),
        sa.Column('estimated_setup_time', sa.Integer, server_default='15'),
        sa.Column('complexity', sa.String(20), server_default='medium'),
        sa.Column('tags', postgresql.ARRAY(sa.Text), server_default='{}'),
        
        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        
        # Constraints
        sa.CheckConstraint("category IN ('api', 'web', 'mobile', 'data', 'microservice')",
                          name='check_template_category'),
        sa.CheckConstraint("complexity IN ('simple', 'medium', 'complex')",
                          name='check_template_complexity'),
    )
    
    # Create indexes for performance
    op.create_index('idx_templates_category', 'templates', ['category'])
    op.create_index('idx_templates_complexity', 'templates', ['complexity'])
    op.create_index('idx_templates_created_at', 'templates',
                    [sa.text('created_at DESC')])
    
    # GIN index for JSONB files column
    op.create_index('idx_templates_files', 'templates', ['files'],
                    postgresql_using='gin')
    
    # GIN indexes for array columns
    op.create_index('idx_templates_tech_stack', 'templates', ['tech_stack'],
                    postgresql_using='gin')
    op.create_index('idx_templates_tags', 'templates', ['tags'],
                    postgresql_using='gin')
    
    # Create trigger function for updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_templates_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger
    op.execute("""
        CREATE TRIGGER trigger_update_templates_updated_at
            BEFORE UPDATE ON templates
            FOR EACH ROW
            EXECUTE FUNCTION update_templates_updated_at();
    """)


def downgrade() -> None:
    """
    Drop templates table and related objects.
    """
    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS trigger_update_templates_updated_at ON templates')
    
    # Drop trigger function
    op.execute('DROP FUNCTION IF EXISTS update_templates_updated_at()')
    
    # Drop indexes
    op.drop_index('idx_templates_tags', table_name='templates')
    op.drop_index('idx_templates_tech_stack', table_name='templates')
    op.drop_index('idx_templates_files', table_name='templates')
    op.drop_index('idx_templates_created_at', table_name='templates')
    op.drop_index('idx_templates_complexity', table_name='templates')
    op.drop_index('idx_templates_category', table_name='templates')
    
    # Drop table
    op.drop_table('templates')
