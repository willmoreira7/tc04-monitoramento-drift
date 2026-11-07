from pathlib import Path

import pytest

from src.data import download
from src.data.download import DatasetIntegrityError, download_dataset, is_valid, sha256_of

CONTENT = b"ID,X1\n1,20000\n"
WRONG_SHA256 = "0d1c9c7d5d0b1b6f7b4f0d3fbb3c7d1d8a6f6f1e7a5c0e2b4d6f8a1c3e5b7d9f"


@pytest.fixture
def fake_stream(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def _fake(url: str, target: Path) -> None:
        calls.append(url)
        target.write_bytes(CONTENT)

    monkeypatch.setattr(download, "_stream_to_file", _fake)
    return calls


def _expected_hash(tmp_path: Path) -> str:
    probe = tmp_path / "probe.csv"
    probe.write_bytes(CONTENT)
    return sha256_of(probe)


def test_download_writes_file_when_hash_matches(tmp_path: Path, fake_stream: list[str]) -> None:
    expected = _expected_hash(tmp_path)
    destination = tmp_path / "raw" / "data.csv"

    download_dataset("https://example.org/data.csv", destination, expected)

    assert destination.read_bytes() == CONTENT
    assert not destination.with_suffix(".csv.part").exists()


def test_download_rejects_wrong_hash_and_leaves_nothing(
    tmp_path: Path, fake_stream: list[str]
) -> None:
    destination = tmp_path / "data.csv"

    with pytest.raises(DatasetIntegrityError):
        download_dataset("https://example.org/data.csv", destination, WRONG_SHA256)

    assert not destination.exists()
    assert not destination.with_suffix(".csv.part").exists()


def test_download_skips_when_valid_file_exists(tmp_path: Path, fake_stream: list[str]) -> None:
    expected = _expected_hash(tmp_path)
    destination = tmp_path / "data.csv"
    destination.write_bytes(CONTENT)

    download_dataset("https://example.org/data.csv", destination, expected)

    assert fake_stream == []


def test_is_valid_false_for_missing_file(tmp_path: Path) -> None:
    assert not is_valid(tmp_path / "missing.csv", WRONG_SHA256)
