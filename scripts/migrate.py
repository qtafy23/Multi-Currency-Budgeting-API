#!/usr/bin/env python3
"""
Database migration script for auto-generating and applying Alembic migrations.
Usage:
    python scripts/migrate.py          # Auto-generate and apply migrations
    python scripts/migrate.py --dry-run # Show what would be migrated
    python scripts/migrate.py --generate-only # Only generate, don't apply
"""

import subprocess
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config.settings import settings

def run_command(cmd, cwd=None):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd or project_root,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(f"Error output: {e.stderr}")
        return None

def generate_migration(message="Auto-generated migration"):
    """Generate a new migration using Alembic auto-generation."""
    print("🔍 Detecting model changes...")
    result = run_command(f"alembic revision --autogenerate -m \"{message}\"")
    if result:
        print("✅ Migration generated successfully")
        return True
    else:
        print("❌ Failed to generate migration")
        return False

def apply_migrations():
    """Apply all pending migrations."""
    print("🚀 Applying migrations...")
    result = run_command("alembic upgrade head")
    if result:
        print("✅ Migrations applied successfully")
        return True
    else:
        print("❌ Failed to apply migrations")
        return False

def show_status():
    """Show current migration status."""
    print("📊 Current migration status:")
    result = run_command("alembic current")
    if result:
        print(f"Current revision: {result}")
    else:
        print("Could not determine current revision")

    print("\n📋 Pending migrations:")
    result = run_command("alembic history --verbose")
    if result:
        print(result)

def main():
    """Main migration workflow."""
    import argparse
    parser = argparse.ArgumentParser(description="Database migration helper")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without applying")
    parser.add_argument("--generate-only", action="store_true", help="Only generate migration, don't apply")
    parser.add_argument("-m", "--message", default="Auto-generated migration", help="Migration message")

    args = parser.parse_args()

    print(f"🔧 Database Migration Tool")
    print(f"📍 Database: {settings.database_url.replace(settings.database_url.split('@')[0], '***:***@')}")
    print()

    # Show current status
    show_status()
    print()

    if args.dry_run:
        print("🔍 Dry run mode - showing what would be migrated...")
        # Generate migration but don't apply
        if generate_migration(args.message):
            print("📄 Generated migration file (not applied)")
            print("Run without --dry-run to apply the migration")
        return

    # Generate migration
    if not generate_migration(args.message):
        sys.exit(1)

    if args.generate_only:
        print("📄 Migration generated (not applied)")
        print("Run 'alembic upgrade head' to apply it")
        return

    # Apply migrations
    if not apply_migrations():
        sys.exit(1)

    print("\n🎉 Migration process completed successfully!")

if __name__ == "__main__":
    main()