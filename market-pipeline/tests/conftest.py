"""Pytest configuration and fixtures."""
import pytest
import logging
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.main import app
from app import db
from app import models


# Suppress verbose logging during tests (only show warnings and errors)
logging.getLogger("app.models").setLevel(logging.WARNING)
logging.getLogger("app.services").setLevel(logging.WARNING)
logging.getLogger("app.db").setLevel(logging.WARNING)
logging.getLogger("app.main").setLevel(logging.WARNING)


@pytest.fixture(name="test_engine")
def test_engine_fixture():
    """Create a test database engine using in-memory SQLite."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="test_session")
def test_session_fixture(test_engine):
    """Create a test database session."""
    with Session(test_engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(test_engine):
    """Create a test client with in-memory database."""
    # Override the database engine for testing
    original_engine = db.engine
    db.engine = test_engine
    
    # Create tables
    db.init_db()
    
    # Create test client
    client = TestClient(app)
    
    yield client
    
    # Restore original engine
    db.engine = original_engine
