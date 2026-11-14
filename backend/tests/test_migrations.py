"""
Test Alembic migrations run cleanly from an empty database.

Tests:
1. Upgrade to head from scratch.
2. Downgrade to base.
3. Re-upgrade to head.
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest
from alembic.config import Config
from alembic import command

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_alembic_migrations_clean_upgrade_and_downgrade(tmp_path: Path):
    db_file = tmp_path / "migration_test.db"
    ini_path = PROJECT_ROOT / "alembic.ini"

    cfg = Config(str(ini_path))
    # Point alembic to the temporary SQLite database
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_file}")

    # Upgrade to head from empty DB
    command.upgrade(cfg, "head")
    assert db_file.exists()

    # Downgrade back to base
    command.downgrade(cfg, "base")

    # Re-upgrade to head cleanly
    command.upgrade(cfg, "head")
