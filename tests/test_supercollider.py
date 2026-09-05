from pathlib import Path
import shutil
import tempfile
import unittest

from eprs.supercollider import render


SCLANG = shutil.which("sclang") or "/Applications/SuperCollider.app/Contents/MacOS/sclang"


class SuperColliderTests(unittest.TestCase):
    def test_preserves_existing_output_and_rejects_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/"score.scd"
            source.write_text("0.exit;")
            out=root/"old.wav"
            out.write_bytes(b"do not replace")
            with self.assertRaises(FileExistsError):
                render(source,out)
            self.assertEqual(out.read_bytes(),b"do not replace")
            with self.assertRaises(ValueError):
                render(root/"missing.scd",root/"new.wav")

    @unittest.skipUnless(Path(SCLANG).is_file() and shutil.which("ffprobe"), "native SuperCollider lane unavailable")
    def test_native_engine_renders_lossless_audio_and_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/"one-note.scd"
            source.write_text(r'''(
var score;
score=Score([
 [0,[\d_recv,SynthDef(\fixture,{Out.ar(0,SinOsc.ar(440,0,0.05).dup)}).asBytes]],
 [0.01,[\s_new,\fixture,1000,0,0]],
 [0.25,[\n_free,1000]],
 [0.3,[\c_set,0,0]]
]);
score.recordNRT(outputFilePath:thisProcess.argv[0],headerFormat:"WAV",sampleFormat:"float",
 options:ServerOptions.new.numOutputBusChannels_(2),duration:0.3,action:{0.exit});
)''')
            output=render(source,root/"note.wav",executable=SCLANG,timeout=30)
            self.assertGreater(output.stat().st_size,10000)
            self.assertTrue(output.with_suffix(".wav.json").is_file())
