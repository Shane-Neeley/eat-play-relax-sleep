from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BarkSingerPromptTests(unittest.TestCase):
    def test_style_note_is_not_concatenated_into_speech_prompt(self):
        source = (ROOT / "scripts" / "bark_singer_voice.py").read_text(encoding="utf-8")
        self.assertIn("prompt = cue_text", source)
        self.assertNotIn("prompt = args.prompt_prefix + cue_text", source)


if __name__ == "__main__":
    unittest.main()
