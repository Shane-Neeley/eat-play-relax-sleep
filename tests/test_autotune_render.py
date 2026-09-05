"""Exercise the real optional vocoder with adversarial input signals."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from eprs.autotune import render_autotune, settings_for

AVAILABLE = all(importlib.util.find_spec(name) for name in ('numpy', 'soundfile', 'pyworld'))


@unittest.skipUnless(AVAILABLE, 'optional WORLD environment unavailable')
class AutotuneRenderTests(unittest.TestCase):
    def test_inverted_stereo_remains_voiced_and_source_is_immutable(self):
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / 'raw.wav', Path(folder) / 'tuned.wav'
            t = np.arange(24000) / 24000
            voice = .15 * np.sin(2 * np.pi * 225 * t)
            sf.write(source, np.stack([voice, -voice], axis=1), 24000, subtype='FLOAT')
            original = source.read_bytes()
            _, _, metadata = render_autotune(source, output, settings_for(
                'hard-step', key='A', scale='chromatic'), intent='Regression pitch correction')
            self.assertGreater(metadata['analysis']['voiced_ratio'], .8)
            audio, rate = sf.read(output)
            self.assertEqual(audio.shape, (24000, 2))
            self.assertEqual(rate, 24000)
            self.assertEqual(source.read_bytes(), original)

    def test_unvoiced_noise_preserves_source_instead_of_vocoder_texture(self):
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / 'raw.wav', Path(folder) / 'tuned.wav'
            noise = np.random.default_rng(42).normal(0, .02, 24000)
            sf.write(source, noise, 24000, subtype='FLOAT')
            _, _, metadata = render_autotune(source, output, settings_for(
                'tight', key='C', scale='major', overrides={'output_gain_db': 0}),
                intent='Preserve unvoiced consonants')
            result, _ = sf.read(output)
            self.assertLess(metadata['analysis']['voiced_ratio'], .05)
            self.assertLess(np.mean((result-noise)**2), 1e-9)

    def test_unsupported_rate_and_nan_fail_without_output(self):
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as folder:
            for rate, samples in [(8000, np.zeros(8000)), (24000, np.full(24000, np.nan))]:
                source, output = Path(folder) / 'raw.wav', Path(folder) / 'tuned.wav'
                sf.write(source, samples, rate, subtype='FLOAT')
                with self.assertRaises(ValueError):
                    render_autotune(source, output, settings_for('tight', key='C', scale='major'),
                                    intent='Reject invalid source')
                self.assertFalse(output.exists())
