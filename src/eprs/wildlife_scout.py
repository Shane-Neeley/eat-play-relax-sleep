"""Bounded regional discovery; observation rarity is not biological rarity."""
from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
from urllib.parse import urlencode, urlparse

from .inaturalist_audio import _sound_request, INATURALIST_API
from .system import utc_now


def rank_observations(records: list[dict], *, limit: int = 12,
                      watchlist: tuple[int, ...] = (), seen: tuple[int, ...] = ()) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError('limit must be between 1 and 100')
    ranked = []
    for obs in records:
        taxon = obs.get('taxon') or {}
        taxon_id = taxon.get('id')
        if not isinstance(taxon_id, int) or taxon_id in seen:
            continue
        if taxon_id != 1 and 1 not in (taxon.get('ancestor_ids') or []):
            continue
        if obs.get('captive') or obs.get('quality_grade') not in {'research', 'needs_id'}:
            continue
        identifier = obs.get('id')
        if not isinstance(identifier, int) or identifier <= 0:
            continue
        reasons = []
        score = 0
        if taxon_id in watchlist:
            score += 100
            reasons.append('regional watchlist')
        introduced = bool(obs.get('introduced') or taxon.get('introduced'))
        if not introduced:
            for flag, weight in [('threatened', 40), ('endemic', 25)]:
                if obs.get(flag) or taxon.get(flag):
                    score += weight
                    reasons.append(flag + ' flag in community record')
            count = taxon.get('observations_count')
            if isinstance(count, int) and 0 < count < 1000:
                score += 15
                reasons.append('few global iNaturalist records; not proof of rarity')
        media = []
        for kind, entries, url_key in [('audio', obs.get('sounds') or [], 'file_url'),
                                       ('image', obs.get('photos') or [], 'url')]:
            for item in entries:
                url = item.get(url_key)
                if item.get('hidden') or not isinstance(url, str) or urlparse(url).scheme != 'https':
                    continue
                license_code = (item.get('license_code') or '').lower()
                attribution = item.get('attribution')
                reusable = license_code == 'cc0' or (license_code == 'cc-by' and bool(attribution))
                media.append({'kind': kind, 'id': item.get('id'), 'url': url,
                              'license_code': license_code or None, 'attribution': attribution,
                              'reuse': 'candidate-subject-to-review' if reusable else 'reference-only'})
        if any(m['kind'] == 'audio' and m['reuse'].startswith('candidate') for m in media):
            score += 30
            reasons.append('compatible audio candidate; audible window unverified')
        if any(m['kind'] == 'image' and m['reuse'].startswith('candidate') for m in media):
            score += 10
            reasons.append('compatible image candidate')
        if obs['quality_grade'] == 'research':
            score += 10
        ranked.append({'observation_id': identifier, 'taxon_id': taxon_id,
                       'name': taxon.get('name'), 'common_name': taxon.get('preferred_common_name'),
                       'observed_on': obs.get('observed_on'),
                       'url': f'https://www.inaturalist.org/observations/{identifier}',
                       'identification': 'community-reviewed' if obs['quality_grade'] == 'research' else 'tentative',
                       'introduced': introduced, 'score': score, 'reasons': reasons,
                       'media': media})
    ranked.sort(key=lambda item: (item['score'], str(item['observed_on']), item['observation_id']), reverse=True)
    selected, taxa = [], set()
    for item in ranked:
        if item['taxon_id'] not in taxa:
            selected.append(item)
            taxa.add(item['taxon_id'])
        if len(selected) == limit:
            break
    return selected


def scout(*, place_id: int, days: int = 7, limit: int = 12, sounds: bool = False,
          watchlist: tuple[int, ...] = (), seen: tuple[int, ...] = ()) -> dict:
    if place_id <= 0 or not 1 <= days <= 90:
        raise ValueError('positive place id and 1–90 days required')
    parameters = {'place_id': place_id, 'taxon_id': 1, 'captive': 'false',
                  'd1': (date.today() - timedelta(days=days)).isoformat(),
                  'order_by': 'observed_on', 'order': 'desc', 'per_page': 100}
    if sounds:
        parameters.update(sounds='true', sound_license='cc0,cc-by')
    url = f'{INATURALIST_API}/observations?{urlencode(parameters)}'
    payload = json.loads(_sound_request(url, 'EPRS-wildlife-scout/1.0 (regional creative discovery)', 30))
    if not isinstance(payload, dict) or not isinstance(payload.get('results'), list):
        raise ValueError('invalid observation response; previous cache preserved')
    return {'schema': 'eprs.wildlife-scout/v1', 'retrieved_at': utc_now(),
            'query': parameters, 'total_results': payload.get('total_results'),
            'sample_size': len(payload['results']),
            'boundary': 'Ranked within one recent page, not an exhaustive rarity survey. No precise locations. Audio identity requires review. No video assets supplied by this endpoint.',
            'candidates': rank_observations(payload['results'], limit=limit,
                                            watchlist=watchlist, seen=seen)}


def save_report(report: dict, output: Path) -> None:
    """Refuse to overwrite any prior evidence or cache."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(report, indent=2) + '\n')
