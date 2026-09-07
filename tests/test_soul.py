import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.dispatch import dispatch_next_work
from eprs.producer import start
from eprs.soul import MEMORY_LIMIT, SOUL_LIMIT, producer_context, validate_producer_context
from eprs.system import PROJECT_ROOT, new_song
from eprs.work import create_work_item


class SoulTests(unittest.TestCase):
    def test_fresh_identity_and_bounded_song_memory_without_mutating_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            soul = root / 'SOUL.md'
            soul.write_text('Confidence without a prescribed genre.')
            song = new_song(root / 'songs', 'Memory')
            memory = song / 'notes/musical-memory.md'
            memory.write_text('Try silence. ' * 1000)
            first = producer_context(song, root=root)
            self.assertEqual(first['soul']['sha256'], hashlib.sha256(soul.read_bytes()).hexdigest())
            preview = first['musical_memory'][-1]
            self.assertTrue(preview['truncated'])
            self.assertLessEqual(len(preview['text'].encode()), MEMORY_LIMIT)
            self.assertEqual(preview['sha256'], hashlib.sha256(memory.read_bytes()).hexdigest())
            soul.write_text('Care and curiosity.')
            second = producer_context(song, root=root)
            self.assertNotEqual(first['soul']['sha256'], second['soul']['sha256'])
            self.assertEqual(first['soul']['text'], 'Confidence without a prescribed genre.')

    def test_invalid_identity_fails_instead_of_silently_dropping_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for content in (' ', 'x' * (SOUL_LIMIT + 1)):
                (root / 'SOUL.md').write_text(content)
                with self.assertRaises(ValueError):
                    producer_context(root=root)
            (root / 'SOUL.md').unlink()
            with patch('eprs.soul.PROJECT_ROOT', root), patch('eprs.soul.sysconfig.get_path', return_value=folder):
                with self.assertRaisesRegex(ValueError, 'missing'):
                    producer_context(root=root)

    def test_installed_identity_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            installed = root / 'share/eprs'
            installed.mkdir(parents=True)
            (installed / 'SOUL.md').write_text('Installed producer identity')
            with patch('eprs.soul.PROJECT_ROOT', root), patch('eprs.soul.sysconfig.get_path', return_value=folder):
                self.assertEqual(producer_context(root=root)['soul']['origin'], 'installed')

    def test_memory_cannot_escape_song_by_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / 'songs', 'Private')
            outside = root / 'private.md'
            outside.write_text('Private')
            (song / 'notes/musical-memory.md').symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'escapes'):
                producer_context(song)

    def test_context_and_dispatch_deliver_soul_even_with_small_evidence_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            song = new_song(Path(folder), 'Continuity')
            (song / 'notes/musical-memory.md').write_text('Hypothesis: let the call breathe; no listening yet.')
            packet = build_agent_context(song, max_text_bytes=1024)
            expected = (PROJECT_ROOT / 'SOUL.md').read_text()
            self.assertEqual(packet['producer_context']['soul']['text'], expected)
            self.assertIn('let the call breathe', render_agent_context_markdown(packet))
            self.assertLessEqual(packet['limits']['text_bytes_used'], 1024)
            create_work_item(song, 'Find a premise', 'research', 'Read local song notes.')
            dispatch = dispatch_next_work(song, 'soul-test')
            self.assertEqual(dispatch['status'], 'ready')
            self.assertEqual(dispatch['context']['producer_context']['soul']['text'], expected)

    def test_production_run_freezes_identity_and_song_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / 'songs', 'Claim')
            (root / 'SOUL.md').write_text('Quiet confidence')
            (song / 'notes/musical-memory.md').write_text('Unreviewed hypothesis: bass rest.')
            concept = dict(engine='test', composition='melodic', groove='4/4',
                           sound_world='wood', form='rondo', visual='still')
            record = start(root, 'soul', 'test', str(song.relative_to(root)), concept)
            (root / 'SOUL.md').write_text('Changed later')
            frozen = json.loads((root / '.eprs-local/producer/runs/soul.json').read_text())
            self.assertEqual(frozen['producer_context'], record['producer_context'])
            self.assertEqual(frozen['producer_context']['soul']['text'], 'Quiet confidence')

    def test_runner_identity_validation_rejects_legacy_or_tampered_context(self):
        context = producer_context()
        validate_producer_context(context)
        for absent in (None, {}, {"schema": "eprs.producer-context/v1"}):
            with self.assertRaises(ValueError):
                validate_producer_context(absent)
        context['soul']['text'] += 'tampered'
        with self.assertRaisesRegex(ValueError, 'changed'):
            validate_producer_context(context)
