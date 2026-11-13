import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEST_DB = ROOT / "data" / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["SEED_DEMO"] = "true"
# Богатый демо-контент проверяем отдельным сценарием, чтобы не менять базу
# ожиданий тестов про отзывы, CRM и бонусы.
os.environ["DEMO_CONTENT"] = "false"
os.environ["SMS_PROVIDER"] = "console"
os.environ["SMS_EXPOSE_CODE"] = "true"
# В тестах несколько модулей регистрируют магазины с одного IP.
os.environ["SIGNUP_ATTEMPTS_PER_HOUR"] = "1000"
os.environ["DEBUG"] = "true"
os.environ["ADMIN_PHONE"] = "+375291112233"
os.environ["ADMIN_PASSWORD"] = "ChangeMe123!"

if TEST_DB.exists():
    TEST_DB.unlink()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def tomorrow(client):
    from datetime import date, timedelta

    return (date.today() + timedelta(days=1)).isoformat()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
