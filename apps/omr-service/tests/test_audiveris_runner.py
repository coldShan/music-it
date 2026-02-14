from pathlib import Path

from src.services.audiveris import AudiverisRunner


def test_runner_invokes_transcribe_export(monkeypatch, tmp_path: Path) -> None:
    called = {}

    def fake_which(command):
        return "/usr/local/bin/audiveris" if command == "audiveris" else None

    def fake_run(cmd, capture_output, text):
        called["cmd"] = cmd
        out_dir = Path(cmd[cmd.index("-output") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "score.musicxml").write_text("<score-partwise/>", encoding="utf-8")

        class Result:
            returncode = 0
            stderr = ""
            stdout = "ok"

        return Result()

    monkeypatch.setattr("src.services.audiveris.shutil.which", fake_which)
    monkeypatch.setattr("src.services.audiveris.subprocess.run", fake_run)

    image = tmp_path / "input.png"
    image.write_bytes(b"x")

    runner = AudiverisRunner("audiveris")
    debug_dir = tmp_path / "debug"
    musicxml = runner.run(image, tmp_path / "out", debug_dir=debug_dir)

    assert musicxml.name == "score.musicxml"
    assert "-transcribe" in called["cmd"]
    assert "-export" in called["cmd"]
    assert (debug_dir / "audiveris-command.txt").exists()
    assert (debug_dir / "audiveris-stdout.log").exists()
    assert (debug_dir / "audiveris-files.txt").exists()


def test_runner_retries_when_only_omr_generated(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}

    def fake_which(command):
        return "/usr/local/bin/audiveris" if command == "audiveris" else None

    def fake_run(cmd, capture_output, text):
        calls["count"] += 1
        out_dir = Path(cmd[cmd.index("-output") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)

        class Result:
            returncode = 0
            stderr = ""
            stdout = "ok"

        if calls["count"] == 1:
            (out_dir / "score.omr").write_text("omr", encoding="utf-8")
        else:
            (out_dir / "score.musicxml").write_text("<score-partwise/>", encoding="utf-8")
        return Result()

    monkeypatch.setattr("src.services.audiveris.shutil.which", fake_which)
    monkeypatch.setattr("src.services.audiveris.subprocess.run", fake_run)

    image = tmp_path / "input.png"
    image.write_bytes(b"x")
    runner = AudiverisRunner("audiveris")
    musicxml = runner.run(image, tmp_path / "out", debug_dir=tmp_path / "debug")

    assert calls["count"] == 2
    assert musicxml.suffix == ".musicxml"
