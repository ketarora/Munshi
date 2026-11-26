from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from munshi.adapters.fakes import MockLedger
from munshi.clock import FixedClock
from munshi.config import Settings
from munshi.db import Database
from munshi.orchestrator import Orchestrator
from munshi.service import create_app

CHILD_TOKEN = "demo-child-token"
OTHER_CHILD_TOKEN = "sharma-child-token"
PARENT_NUMBER = "9812345678"
UNKNOWN_NUMBER = "9000000000"


@pytest.fixture()
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture()
def db(clock: FixedClock):
    database = Database(clock=clock)
    database.seed_demo()
    yield database
    database.close()


@pytest.fixture()
def payments() -> MockLedger:
    return MockLedger()


@pytest.fixture()
def settings() -> Settings:
    return Settings()


@pytest.fixture()
def orch(db: Database, clock: FixedClock, payments: MockLedger, settings: Settings) -> Orchestrator:
    return Orchestrator(db, clock=clock, settings=settings, payments=payments)


@pytest.fixture()
def client(db: Database, clock: FixedClock):
    app = create_app(db=db, clock=clock)
    with TestClient(app) as test_client:
        yield test_client


def auth(token: str = CHILD_TOKEN) -> dict[str, str]:
    return {"X-Munshi-Token": token}


def start_parent_call(orch: Orchestrator) -> str:
    return orch.start_call(PARENT_NUMBER)["call_id"]
