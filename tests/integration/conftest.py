import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from core.db import Base


@pytest.fixture
def postgres_sessions():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    if make_url(url).get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must point to PostgreSQL")

    schema = f"test_transactions_{uuid4().hex}"
    admin = create_engine(url)
    engine = None
    try:
        with admin.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        engine = create_engine(
            url,
            connect_args={
                "options": (
                    f"-csearch_path={schema} -clock_timeout=10000 "
                    "-cstatement_timeout=15000"
                )
            },
        )
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine, autoflush=False)
    finally:
        if engine is not None:
            engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        admin.dispose()
