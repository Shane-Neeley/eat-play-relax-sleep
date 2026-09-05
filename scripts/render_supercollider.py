#!/usr/bin/env python3
"""Render trusted finite native scores; run with uv run from the checkout."""
import argparse
from eprs.supercollider import render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    print(render(args.source, args.output, timeout=args.timeout))


if __name__ == "__main__":
    main()
