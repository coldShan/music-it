from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

from .errors import OMRPipelineError


class AudiverisRunner:
    def __init__(self, command: str | None = None):
        self.command = command or os.getenv("AUDIVERIS_CMD", "audiveris")

    def ensure_available(self) -> None:
        if shutil.which(self.command):
            return
        raise OMRPipelineError(
            "Audiveris command not found. Install Audiveris or set AUDIVERIS_CMD."
        )

    def _write_debug_file(self, debug_dir: Path | None, name: str, content: str) -> None:
        if debug_dir is None:
            return
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / name).write_text(content, encoding="utf-8")

    def _dump_file_list(self, roots: Iterable[Path]) -> str:
        lines: list[str] = []
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    lines.append(str(path))
        return "\n".join(lines) if lines else "(no files)"

    def _find_musicxml_candidates(self, output_dir: Path, image_path: Path) -> list[Path]:
        candidates: list[Path] = []
        for root in (output_dir, image_path.parent):
            candidates.extend(sorted(root.rglob("*.musicxml")))
            candidates.extend(sorted(root.rglob("*.xml")))
            candidates.extend(sorted(root.rglob("*.mxl")))
        return candidates

    def run(self, image_path: Path, output_dir: Path, debug_dir: Path | None = None) -> Path:
        self.ensure_available()
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.command,
            "-batch",
            "-transcribe",
            "-export",
            "-output",
            str(output_dir),
            str(image_path),
        ]

        self._write_debug_file(
            debug_dir,
            "audiveris-command.txt",
            " ".join(cmd),
        )

        proc = subprocess.run(cmd, capture_output=True, text=True)
        self._write_debug_file(debug_dir, "audiveris-stdout.log", proc.stdout)
        self._write_debug_file(debug_dir, "audiveris-stderr.log", proc.stderr)

        if debug_dir is not None and output_dir.exists():
            archived_out = debug_dir / "audiveris-out"
            if archived_out.exists():
                shutil.rmtree(archived_out)
            shutil.copytree(output_dir, archived_out, dirs_exist_ok=True)
            self._write_debug_file(
                debug_dir,
                "audiveris-files.txt",
                self._dump_file_list((output_dir, image_path.parent)),
            )

        if proc.returncode != 0:
            raise OMRPipelineError(
                f"Audiveris failed: {proc.stderr.strip() or proc.stdout.strip()}"
            )

        candidates = self._find_musicxml_candidates(output_dir, image_path)
        if not candidates:
            omr_candidates = sorted(output_dir.rglob("*.omr"))
            if omr_candidates:
                retry_cmd = [
                    self.command,
                    "-batch",
                    "-force",
                    "-transcribe",
                    "-export",
                    "-output",
                    str(output_dir),
                    str(omr_candidates[0]),
                ]
                self._write_debug_file(
                    debug_dir,
                    "audiveris-retry-command.txt",
                    " ".join(retry_cmd),
                )
                retry = subprocess.run(retry_cmd, capture_output=True, text=True)
                self._write_debug_file(debug_dir, "audiveris-retry-stdout.log", retry.stdout)
                self._write_debug_file(debug_dir, "audiveris-retry-stderr.log", retry.stderr)
                if retry.returncode != 0:
                    raise OMRPipelineError(
                        f"Audiveris retry failed: {retry.stderr.strip() or retry.stdout.strip()}"
                    )
                candidates = self._find_musicxml_candidates(output_dir, image_path)
                self._write_debug_file(
                    debug_dir,
                    "audiveris-files-after-retry.txt",
                    self._dump_file_list((output_dir, image_path.parent)),
                )

        if not candidates:
            all_files = [str(path.relative_to(image_path.parent)) for path in image_path.parent.rglob("*") if path.is_file()]
            files_hint = ", ".join(all_files[:10]) if all_files else "none"
            raise OMRPipelineError(
                "Audiveris finished but no MusicXML was generated. "
                f"Generated files: {files_hint}"
            )

        # Prefer plain MusicXML when both compressed and plain outputs exist.
        candidates.sort(
            key=lambda p: (
                0 if p.suffix.lower() in {".musicxml", ".xml"} else 1,
                len(str(p)),
            )
        )
        return candidates[0]
