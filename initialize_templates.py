"""
Script to initialize starter templates in the template library.

Run this script to populate the template library with default templates.
"""

import asyncio
import logging
from utils.starter_templates import initialize_starter_templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Initialize all starter templates."""
    logger.info("Starting template initialization...")
    
    try:
        count = await initialize_starter_templates()
        logger.info(f"✅ Successfully initialized {count} starter templates")
        print(f"\n✅ Template initialization complete!")
        print(f"   {count} templates are now available in the library")
        print(f"\nAvailable templates:")
        print("  1. REST API with FastAPI")
        print("  2. Web App (React + FastAPI)")
        print("  3. Mobile Backend API")
        print("  4. Data Pipeline (ETL)")
        print("  5. Microservice with Observability")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize templates: {e}", exc_info=True)
        print(f"\n❌ Template initialization failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
