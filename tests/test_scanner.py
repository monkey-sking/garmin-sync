from pathlib import Path

from garmin_sync.scanner import scan_activity_files


def test_scan_activity_files_hashes_recursive_supported_activity_files(tmp_path: Path):
    (tmp_path / "a.fit").write_bytes(b"abc")
    (tmp_path / "b.gpx").write_text("<gpx><trkpt/></gpx>")
    (tmp_path / "b.txt").write_text("x")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "c.fit").write_bytes(b"nested")
    (nested / "d.GPX").write_text("<gpx><time>2026-01-01T00:00:00Z</time></gpx>")

    items = scan_activity_files(tmp_path)

    assert [item.file_name for item in items] == ["a.fit", "b.gpx", "c.fit", "d.GPX"]
    assert items[0].sha256 == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert items[0].file_path == str((tmp_path / "a.fit").resolve())
    assert items[2].sha256 == "233562de1a0288b139c4fa40b7d189f806e906eeb048517aeb67f34ac0e2faf1"
    assert items[2].file_path == str((nested / "c.fit").resolve())
