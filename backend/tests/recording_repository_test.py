import asyncio
from datetime import date, datetime, timezone

import pytest

from app.infrastructure.recording_repository import (
    FtpRecordingRepository,
    parse_recording_filename,
)
from app.infrastructure.settings import settings


class FakeFTP:
    def __init__(self, entries):
        self.entries = entries
        self.quit_called = False
        self.remote_directory = None

    def mlsd(self, remote_directory, facts):
        self.remote_directory = remote_directory
        assert facts == ["type", "size"]
        return iter(self.entries)

    def quit(self):
        self.quit_called = True


@pytest.mark.parametrize(
    ("filename", "expected_prefix", "expected_start"),
    [
        (
            "NodoRedes_00_20260815100739.mp4",
            "NodoRedes_00",
            datetime(2026, 8, 15, 10, 7, 39, tzinfo=timezone.utc),
        ),
        (
            "RLC-810A_00_20260815060334.mp4",
            "RLC-810A_00",
            datetime(2026, 8, 15, 6, 3, 34, tzinfo=timezone.utc),
        ),
        (
            "RLC-810A_00_20260815060334.MP4",
            "RLC-810A_00",
            datetime(2026, 8, 15, 6, 3, 34, tzinfo=timezone.utc),
        ),
        (
            "Pasillo Redes-00-20260815093551.mp4",
            "Pasillo Redes-00",
            datetime(2026, 8, 15, 9, 35, 51, tzinfo=timezone.utc),
        ),
        (
            "camara_sin_canal_20260815093551.mp4",
            "camara_sin_canal",
            datetime(2026, 8, 15, 9, 35, 51, tzinfo=timezone.utc),
        ),
    ],
)
def test_parse_recording_filename_accepts_camera_name_variations(
    filename, expected_prefix, expected_start
):
    assert parse_recording_filename(filename) == (expected_prefix, expected_start)


@pytest.mark.parametrize(
    "filename",
    [
        "PasilloRedes_00_20260815093551.txt",
        "PasilloRedes_00_20261315093551.mp4",
        "PasilloRedes_00_20260815093551.mp4.tmp",
        "PasilloRedes.mp4",
    ],
)
def test_parse_recording_filename_rejects_non_playable_or_invalid_names(filename):
    assert parse_recording_filename(filename) is None


def test_ftp_repository_maps_full_or_base_camera_name_and_skips_unrelated_files(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "ftp_camera_prefixes",
        "NodoRedes:1, PasilloRedes_00:2, RLC-810A_00:3, invalid:not-a-number",
    )
    monkeypatch.setattr(settings, "ftp_root", "/ftp/upload")
    monkeypatch.setattr(settings, "ftp_recording_duration_seconds", 120)
    repository = FtpRecordingRepository()
    ftp = FakeFTP(
        [
            ("NodoRedes_00_20260815100739.mp4", {"type": "file", "size": "101"}),
            ("Pasillo_Redes-00-20260815093551.MP4", {"type": "file", "size": "102"}),
            ("rlc_810a_00_20260815060334.mp4", {"type": "file", "size": "103"}),
            ("PasilloRedes_00_20260815093720.txt", {"type": "file", "size": "104"}),
            ("NodoRedes_00_20261315100739.mp4", {"type": "file", "size": "105"}),
            ("Unknown_00_20260815100807.mp4", {"type": "file", "size": "106"}),
            ("nested", {"type": "dir", "size": "0"}),
        ]
    )
    monkeypatch.setattr(repository, "_connect", lambda: ftp)

    recordings = asyncio.run(repository.search(day=date(2026, 8, 15)))

    by_filename = {recording.filename: recording for recording in recordings}
    assert set(by_filename) == {
        "NodoRedes_00_20260815100739.mp4",
        "Pasillo_Redes-00-20260815093551.MP4",
        "rlc_810a_00_20260815060334.mp4",
    }
    assert by_filename["NodoRedes_00_20260815100739.mp4"].camera_id == 1
    assert by_filename["Pasillo_Redes-00-20260815093551.MP4"].camera_id == 2
    assert by_filename["rlc_810a_00_20260815060334.mp4"].camera_id == 3
    assert by_filename["NodoRedes_00_20260815100739.mp4"].path == (
        "/2026/08/15/NodoRedes_00_20260815100739.mp4"
    )
    assert by_filename["NodoRedes_00_20260815100739.mp4"].duration_seconds == 120
    assert ftp.remote_directory == "/ftp/upload/2026/08/15"
    assert ftp.quit_called


def test_full_camera_prefix_mapping_takes_precedence_over_name_without_channel(monkeypatch):
    monkeypatch.setattr(settings, "ftp_camera_prefixes", "NodoRedes:1,NodoRedes_00:2")
    repository = FtpRecordingRepository()

    assert repository._camera_id_for_prefix("NodoRedes_00") == 2


@pytest.mark.parametrize(
    "target_day",
    [date(2026, 8, 14), date(2026, 8, 15), date(2026, 8, 16)],
)
def test_ftp_repository_uses_requested_date_for_each_daily_folder(monkeypatch, target_day):
    """A timestamp always has 14 digits; its calendar day is not fixed to 14."""
    monkeypatch.setattr(settings, "ftp_camera_prefixes", "NodoRedes:1")
    monkeypatch.setattr(settings, "ftp_root", "/ftp/upload")
    filename = f"NodoRedes_00_{target_day:%Y%m%d}100739.mp4"
    ftp = FakeFTP([(filename, {"type": "file", "size": "101"})])
    repository = FtpRecordingRepository()
    monkeypatch.setattr(repository, "_connect", lambda: ftp)

    recordings = asyncio.run(repository.search(day=target_day))

    assert ftp.remote_directory == f"/ftp/upload/{target_day:%Y/%m/%d}"
    assert [recording.path for recording in recordings] == [
        f"/{target_day:%Y/%m/%d}/{filename}"
    ]
    assert recordings[0].start_time.date() == target_day
