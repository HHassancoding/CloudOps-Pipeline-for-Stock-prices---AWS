"""Pytest configuration and fixtures."""
import pytest
from sqlmodel import SQLModel, create_engine, Session
from fastapi.testclient import TestClient
from app.main import app
from app import db


@pytest.fixture(name="test_engine")
def test_engine_fixture():
    """Create a test database engine using in-memory SQLite."""
    engine = create_engine("sqlite:///:memory:")
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
    SQLModel.metadata.create_all(test_engine)
    
    # Create test client
    client = TestClient(app)
    
    yield client
    
    # Restore original engine
    db.engine = original_engine
