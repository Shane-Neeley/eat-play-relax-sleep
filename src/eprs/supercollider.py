"""Bounded execution of an authored SuperCollider NRT score, with a receipt.

The score receives the new WAV output path as its first argument. It must
recordNRT and exit. This executes trusted local code; it is not a sandbox.
"""
from pathlib import Path
import json
import shutil
import subprocess
import time

from .system import sha256


def render(source: str | Path, output: str | Path, *, executable: str | None = None,
           timeout: float = 180) -> Path:
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file() or source.suffix != ".scd":
        raise ValueError("Expected an authored .scd score")
    if output.exists() or output.with_suffix(output.suffix + ".json").exists():
        raise FileExistsError(output)
    if output.suffix.lower() != ".wav" or timeout <= 0:
        raise ValueError("Use a new WAV output and a positive deadline")
    executable = executable or shutil.which("sclang")
    if not executable:
        mac = Path("/Applications/SuperCollider.app/Contents/MacOS/sclang")
        executable = str(mac) if mac.is_file() else None
    if not executable:
        raise RuntimeError("SuperCollider sclang is unavailable; choose another real engine")
    output.parent.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(source)
    log = output.with_suffix(".render.log")
    started = time.monotonic()
    # Native code may start scsynth. A process group bounds all descendants.
    import os
    import signal
    with log.open("x") as handle:
        process = subprocess.Popen([executable, "-D", str(source), str(output)],
                                   cwd=source.parent, stdout=handle, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    if code or not output.is_file() or output.stat().st_size < 128:
        raise RuntimeError(f"SuperCollider did not return audio; inspect {log}")
    if sha256(source) != source_hash:
        raise RuntimeError("SuperCollider score changed during rendering; preserve this output as unverified")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                            "-of", "json", str(output)], capture_output=True, text=True,
                           check=True, timeout=20)
    record = {"schema": "eprs.supercollider-nrt/v1", "engine": "SuperCollider NRT",
              "source": {"name": source.name, "sha256": source_hash},
              "output": {"name": output.name, "sha256": sha256(output)},
              "elapsed_seconds": round(time.monotonic() - started, 3),
              "probe": json.loads(probe.stdout), "creative_approval": False}
    output.with_suffix(output.suffix + ".json").write_text(json.dumps(record, indent=2) + "\n")
    return output
