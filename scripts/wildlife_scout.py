#!/usr/bin/env python3
"""Discover regional wildlife and rights-labelled audio/image candidates."""
import argparse
from pathlib import Path

from eprs.wildlife_scout import save_report, scout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--place-id', type=int, required=True)
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--limit', type=int, default=12)
    parser.add_argument('--sounds', action='store_true')
    parser.add_argument('--watch-taxon', type=int, action='append', default=[])
    parser.add_argument('--seen-taxon', type=int, action='append', default=[])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = scout(place_id=args.place_id, days=args.days, limit=args.limit,
                   sounds=args.sounds, watchlist=tuple(args.watch_taxon), seen=tuple(args.seen_taxon))
    save_report(report, args.out)
    print(args.out)


if __name__ == '__main__':
    main()
