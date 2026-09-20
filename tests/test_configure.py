from __future__ import annotations

import json

import pytest

from configure import write_config


def test_write_config_persists_valid_public_client_atomically(tmp_path):
    path = write_config(tmp_path, "zpc_Hermes_test-123")

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "client_id": "zpc_Hermes_test-123"
    }
    assert not list(tmp_path.glob(".zenmux.*.json"))


@pytest.mark.parametrize("client_id", ["", "DSH-client", "zpc_bad value", "zpc_"])
def test_write_config_rejects_non_public_client_ids(tmp_path, client_id):
    with pytest.raises(ValueError, match="client ID must match"):
        write_config(tmp_path, client_id)
    assert not (tmp_path / "zenmux.json").exists()
