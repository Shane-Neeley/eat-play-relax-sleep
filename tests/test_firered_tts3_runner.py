import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import wave


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "firered_tts3_voice.py"


def wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\x00\x00" * 2400)
    return buffer.getvalue()


class FireRedHandler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, format, *args):
        return

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(size))
        type(self).requests.append(payload)
        body = json.dumps({"event_id": "event-1"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.endswith("/event-1"):
            host = f"http://127.0.0.1:{self.server.server_port}"
            result = [{"url": host + "/generated.wav"}, "bright adult chant"]
            body = ("event: complete\ndata: " + json.dumps(result) + "\n\n").encode()
            content_type = "text/event-stream"
        elif self.path == "/generated.wav":
            body = wav_bytes()
            content_type = "audio/wav"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FireRedTTS3RunnerTests(unittest.TestCase):
    def test_help_and_version_do_not_require_network_or_model_imports(self):
        help_run = subprocess.run(
            [sys.executable, str(RUNNER), "--help"],
            capture_output=True, text=True, check=True,
        )
        version_run = subprocess.run(
            [sys.executable, str(RUNNER), "--version"],
            capture_output=True, text=True, check=True,
        )
        self.assertIn("FireRedTTS3", help_run.stdout)
        self.assertIn("--autotune-preset", help_run.stdout)
        self.assertIn("firered-tts3-voice 0.1", version_run.stdout)

    def test_reference_free_space_render_records_request_and_audio(self):
        FireRedHandler.requests = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), FireRedHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                out = Path(folder) / "voice"
                base = f"http://127.0.0.1:{server.server_port}"
                run = subprocess.run(
                    [
                        sys.executable, str(RUNNER),
                        "--base-url", base,
                        "--space-id", "fixture/firered",
                        "--space-revision", "fixture-sha",
                        "--instruct", "Original bright adult chant",
                        "--text", "Wild signal, light it up.",
                        "--out-dir", str(out),
                        "--prefix", "wild",
                        "--seed", "77",
                    ],
                    capture_output=True, text=True, check=True,
                )
                self.assertIn("manifest.json", run.stdout)
                manifest = json.loads((out / "manifest.json").read_text())
                self.assertEqual(manifest["schema"], "eprs.firered-tts3-render/v1")
                self.assertEqual(manifest["mode"], "voice-design")
                self.assertEqual(manifest["outputs"][0]["sample_rate"], 24000)
                self.assertEqual(manifest["outputs"][0]["voice_plan"], "bright adult chant")
                self.assertTrue((out / "wild-01.wav").is_file())
                self.assertEqual(FireRedHandler.requests[0]["seed"], 77)
                self.assertEqual(FireRedHandler.requests[0]["n_timesteps"], 10)
        finally:
            server.shutdown()
            server.server_close()

    def test_profile_and_registry_are_provider_bound(self):
        profile = json.loads((ROOT / "config/adapters/firered-tts3.json").read_text())
        registry = json.loads((ROOT / "config/toolchain.json").read_text())
        provider = next(
            item for item in registry["tools"] if item["id"] == "firered_tts3_space"
        )
        self.assertEqual(profile["provider"], provider["id"])
        self.assertTrue(set(profile["capabilities"]).issubset(provider["capabilities"]))
        self.assertIn(
            "remote-voice-collaboration",
            {item["id"] for item in registry["workflows"]},
        )


if __name__ == "__main__":
    unittest.main()
