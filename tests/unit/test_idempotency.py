from __future__ import annotations

from pathlib import Path

from edvmp.shared.store import LocalSqliteStore


def test_idempotency_claim_is_conditional(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    store = LocalSqliteStore(str(db))

    assert store.try_claim_idempotency(idempotency_key="k1", job_id="j1") is True
    assert store.try_claim_idempotency(idempotency_key="k1", job_id="j1") is False

