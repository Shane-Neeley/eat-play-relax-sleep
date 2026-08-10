import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from eprs.cli import parser
from eprs.dispatch import dispatch_next_work, write_dispatch_packet
from eprs.runner import (
    _macos_policy,
    _sandbox_command,
    load_runner_profile,
    run_agent_profile,
    verify_runner_receipt,
)
from eprs.system import new_song
from eprs.work import create_work_item, load_work_item


AGENT_FIXTURE = r'''import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--packet", required=True)
parser.add_argument("--response", required=True)
parser.add_argument("--workspace", required=True)
args = parser.parse_args()
response_path = Path(args.response)
response = json.loads(response_path.read_text())
note = Path(args.workspace) / "continuity.md"
note.write_text("Let the family answer arrive after one full breath.\n")
response.update({
    "summary": "Prepared one bounded local continuity note.",
    "decision": "complete",
    "actions": {
        "network_accessed": False,
        "raw_recordings_modified": False,
        "remote_state_changed": False,
        "uploaded_published_or_sent": False,
        "local_audio_processed": False,
        "listening_performed": False,
        "commands_run": ["wrote one workspace-local note"],
    },
    "results": [{"role": "continuity-note", "path": "continuity.md"}],
})
response_path.write_text(json.dumps(response, indent=2) + "\n")
print("x" * 4096)
'''


TIMEOUT_FIXTURE = r'''import argparse
import subprocess
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--packet", required=True)
parser.add_argument("--response", required=True)
parser.add_argument("--workspace", required=True)
args = parser.parse_args()
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
Path(args.workspace, "child.pid").write_text(str(child.pid))
time.sleep(60)
'''


class AgentRunnerTests(unittest.TestCase):
    @staticmethod
    def _profile(root: Path, script: Path, **overrides) -> Path:
        record = {
            "schema": "eprs.runner-profile/v1",
            "id": "fixture-agent",
            "label": "Fixture file agent",
            "protocol": "eprs.packet-response-files/v1",
            "executable": sys.executable,
            "arguments": [
                str(script),
                "--packet", "{packet}",
                "--response", "{response}",
                "--workspace", "{workspace}",
            ],
            "isolation": "auto",
            "network_mode": "deny",
            "timeout_seconds": 5,
            "terminate_grace_seconds": 0.1,
            "max_log_bytes": 1024,
        }
        record.update(overrides)
        path = root / "runner-profile.json"
        path.write_text(json.dumps(record, indent=2) + "\n")
        return path

    @staticmethod
    def _packet(root: Path, song: Path) -> tuple[Path, Path, str]:
        item_path = create_work_item(
            song,
            "Prepare one local continuity observation",
            "automation",
            "Use only the packet and write one bounded result.",
        )
        item_id = json.loads(item_path.read_text())["id"]
        bundle = dispatch_next_work(song, "fixture-agent")
        return write_dispatch_packet(bundle, root / "dispatch.json"), item_path, item_id

    @staticmethod
    def _without_os_sandbox():
        return (
            patch("eprs.runner._isolation_provider", return_value=("macos-sandbox-exec", "/usr/bin/true")),
            patch(
                "eprs.runner._sandbox_command",
                side_effect=lambda workspace, command: (
                    "macos-sandbox-exec", command, None
                ),
            ),
        )

    def test_success_freezes_response_caps_logs_and_preserves_raw(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Runner Success")
            script = root / "agent.py"
            script.write_text(AGENT_FIXTURE)
            profile = self._profile(root, script)
            packet, _, item_id = self._packet(root, song)
            raw = song / "recordings" / "raw" / "room.wav"
            raw.write_bytes(b"unaltered human performance")
            provider_patch, command_patch = self._without_os_sandbox()

            with provider_patch, command_patch:
                receipt_path, receipt = run_agent_profile(song, profile, packet)

            self.assertEqual(receipt["status"], "completed")
            self.assertTrue(receipt["raw_integrity"]["unchanged"])
            self.assertEqual(raw.read_bytes(), b"unaltered human performance")
            self.assertTrue(receipt["logs"]["stdout"]["truncated"])
            self.assertEqual(receipt["logs"]["stdout"]["bytes_kept"], 1024)
            self.assertTrue(receipt["process"]["termination"]["cleanup_verified"])
            self.assertTrue(receipt["response"]["accepted"])
            self.assertEqual(verify_runner_receipt(song, receipt_path)[0], receipt_path)
            _, item = load_work_item(song, item_id)
            self.assertEqual(item["status"], "completed")
            self.assertEqual(
                set(item["runs"][-1]["results"]),
                {"agent-dispatch-packet", "agent-response", "continuity-note"},
            )

            response = song / receipt["response"]["path"]
            response.write_text(response.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "response checksum"):
                verify_runner_receipt(song, receipt_path)

    def test_timeout_kills_process_group_requeues_work_and_preserves_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Runner Timeout")
            script = root / "timeout-agent.py"
            script.write_text(TIMEOUT_FIXTURE)
            profile = self._profile(root, script, timeout_seconds=1.0)
            packet, _, item_id = self._packet(root, song)
            provider_patch, command_patch = self._without_os_sandbox()

            with provider_patch, command_patch:
                receipt_path, receipt = run_agent_profile(song, profile, packet)

            self.assertEqual(receipt["status"], "failed")
            self.assertTrue(receipt["process"]["timed_out"])
            self.assertTrue(receipt["process"]["termination"]["cleanup_verified"])
            self.assertIn("exceeded", receipt["response"]["error"])
            self.assertIsNotNone(receipt["release"]["path"])
            self.assertEqual(load_work_item(song, item_id)[1]["status"], "queued")
            self.assertEqual(verify_runner_receipt(song, receipt_path)[0], receipt_path)

            child_pid = int((receipt_path.parent / "workspace" / "child.pid").read_text())
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.02)
            else:
                self.fail("runner descendant survived process-group cleanup")

    def test_profile_refuses_network_and_unknown_placeholders(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / "agent.py"
            script.write_text(AGENT_FIXTURE)
            network = self._profile(root, script, network_mode="packet")
            with self.assertRaisesRegex(ValueError, "network_mode must be deny"):
                load_runner_profile(network)
            unknown = self._profile(
                root, script, arguments=["{packet}", "{response}", "{secret}"]
            )
            with self.assertRaisesRegex(ValueError, "unknown placeholders: secret"):
                load_runner_profile(unknown)

    def test_macos_policy_denies_network_and_limits_writes(self):
        workspace = Path("/private/tmp/example workspace")
        policy = _macos_policy(workspace)
        self.assertIn("(deny network*)", policy)
        self.assertIn("(deny file-write*)", policy)
        self.assertIn('(allow file-write* (subpath "/private/tmp/example workspace"))', policy)

    @unittest.skipUnless(
        platform.system() == "Darwin" and shutil.which("sandbox-exec"),
        "requires the macOS sandbox provider",
    )
    def test_real_macos_sandbox_denies_network_and_outside_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            workspace = root / "run" / "workspace"
            workspace.mkdir(parents=True)
            outside = root / "outside.txt"
            probe = (
                "import json, pathlib, socket, sys; "
                "result={}; "
                "\ntry: pathlib.Path(sys.argv[1]).write_text('blocked')\n"
                "except OSError as exc: result['outside_errno']=exc.errno\n"
                "try:\n s=socket.socket(); s.settimeout(.2); s.connect(('127.0.0.1', 9))\n"
                "except OSError as exc: result['network_errno']=exc.errno\n"
                "pathlib.Path(sys.argv[2]).write_text(json.dumps(result))"
            )
            provider, command, _ = _sandbox_command(
                workspace,
                [sys.executable, "-c", probe, str(outside), str(workspace / "result.json")],
                system_name="Darwin",
            )

            completed = subprocess.run(command, capture_output=True, text=True, timeout=5)

            self.assertEqual(provider, "macos-sandbox-exec")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(outside.exists())
            result = json.loads((workspace / "result.json").read_text())
            self.assertIn(result["outside_errno"], {1, 13})
            self.assertIn(result["network_errno"], {1, 13})

    def test_cli_exposes_validate_run_and_show(self):
        validate = parser().parse_args(["runner", "validate", "profile.json"])
        self.assertEqual(validate.runner_command, "validate")
        run = parser().parse_args([
            "runner", "run", "profile.json", "--packet", "packet.json",
            "--song", "songs/example",
        ])
        self.assertEqual(run.packet, "packet.json")
        show = parser().parse_args([
            "runner", "show", "notes/runner-runs/example", "--song", "songs/example",
        ])
        self.assertEqual(show.runner_command, "show")


if __name__ == "__main__":
    unittest.main()
