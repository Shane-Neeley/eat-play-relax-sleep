from copy import deepcopy
import unittest
from unittest.mock import patch

from eprs.wildlife_scout import rank_observations, scout


def observation(identifier=10, taxon_id=20):
    return {'id': identifier, 'taxon': {'id': taxon_id, 'ancestor_ids': [1],
            'name': 'Test animal', 'observations_count': 12}, 'quality_grade': 'research',
            'observed_on': '2026-09-05', 'location': 'sensitive',
            'sounds': [{'id': 3, 'file_url': 'https://example.com/a.wav',
                        'license_code': 'cc-by', 'attribution': 'Recorder'}]}


class WildlifeScoutTests(unittest.TestCase):
    def test_licenses_sensitive_locations_tentative_and_dedup(self):
        first = observation()
        other = observation(11, 21)
        other['quality_grade'] = 'needs_id'
        other['sounds'][0]['license_code'] = 'cc-by-nc'
        selected = rank_observations([first, deepcopy(first), other])
        self.assertEqual(len(selected), 2)
        self.assertNotIn('location', selected[0])
        self.assertEqual(selected[1]['identification'], 'tentative')
        self.assertEqual(selected[1]['media'][0]['reuse'], 'reference-only')
        self.assertEqual(selected[0]['media'][0]['attribution'], 'Recorder')

    def test_plants_introduced_cooldown_and_overflow(self):
        plant = observation(12, 22)
        plant['taxon']['ancestor_ids'] = [47126]
        introduced = observation(13, 23)
        introduced.update(introduced=True, threatened=True, endemic=True)
        result = rank_observations([plant, introduced, observation()], limit=1)
        self.assertEqual(result[0]['taxon_id'], 20)
        self.assertEqual(rank_observations([observation()], seen=(20,)), [])
        introduced_only = rank_observations([introduced])[0]
        self.assertFalse(any('threatened' in x or 'global' in x for x in introduced_only['reasons']))

    def test_watchlist_overrides_recency_and_missing_attribution_is_not_cleared(self):
        old = observation(9, 99)
        old['sounds'][0]['attribution'] = None
        result = rank_observations([observation(), old], watchlist=(99,))
        self.assertEqual(result[0]['taxon_id'], 99)
        self.assertEqual(result[0]['media'][0]['reuse'], 'reference-only')

    def test_api_failure_is_not_zero_results(self):
        with patch('eprs.wildlife_scout._sound_request', return_value=b'{"error":"oops"}'):
            with self.assertRaises(ValueError):
                scout(place_id=10)
