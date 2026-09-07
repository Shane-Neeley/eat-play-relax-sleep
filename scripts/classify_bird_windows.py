#!/usr/bin/env python3
"""Optional Perch v2 window corroboration; never source clearance or listening.

Use an existing NumPy/ONNX Runtime environment and explicitly supplied model
and label files. No downloads, installations or source transformations on disk.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess


def window(value: str) -> tuple[float, float]:
    import math
    try:
        start, end = map(float, value.split(':'))
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Use START:END in seconds') from exc
    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= start + 5):
        raise argparse.ArgumentTypeError('Use a finite, positive window of at most five seconds')
    return start, end


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_output(path: Path, inputs: list[Path]) -> None:
    resolved = path.resolve()
    if resolved in {item.resolve() for item in inputs}:
        raise ValueError('Output cannot replace an input')
    if path.exists():
        raise FileExistsError(path)
    if 'FINAL' in resolved.parts or any(a == 'recordings' and b == 'raw'
                                      for a, b in zip(resolved.parts, resolved.parts[1:])):
        raise ValueError('Analysis cannot be written into immutable source/release lanes')


def analyze(source: Path, model: Path, labels: Path, windows: list[tuple[float, float]]) -> dict:
    import numpy as np
    import onnxruntime as ort

    if not 1 <= len(windows) <= 24:
        raise ValueError('Provide between one and 24 bounded windows')
    windows = [window(f'{start}:{end}') for start, end in windows]
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_format', '-of', 'json', str(source)
    ], timeout=20))
    duration = float(probe['format']['duration'])
    if any(end > duration + .001 for _, end in windows):
        raise ValueError('Requested window extends beyond the source')
    with labels.open(newline='') as handle:
        rows = list(csv.reader(handle))
    if not rows or rows[0] != ['inat2024_fsd50k']:
        raise ValueError('Expected Perch v2 assets/labels.csv with its taxonomy header')
    taxa = [row[0] for row in rows[1:] if row]
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(model), sess_options=options, providers=['CPUExecutionProvider'])
    inputs = session.get_inputs()
    if len(inputs) != 1 or inputs[0].name != 'inputs' or inputs[0].shape[-1] != 160000:
        raise ValueError('Expected Perch v2 five-second 32 kHz input')
    records = []
    for start, end in windows:
        data = subprocess.check_output([
            'ffmpeg', '-v', 'error', '-ss', str(start), '-i', str(source),
            '-t', str(end-start), '-vn', '-ac', '1', '-ar', '32000', '-f', 'f32le', '-'
        ], timeout=30)
        samples = np.frombuffer(data, dtype='<f4')
        if not len(samples) or not np.all(np.isfinite(samples)):
            raise ValueError('Window has no finite audio')
        padded = np.pad(samples[:160000], (0, max(0, 160000-len(samples)))).astype('float32')
        logits = session.run(['label'], {'inputs': padded[None]})[0][0]
        if len(logits) != len(taxa) or not np.all(np.isfinite(logits)):
            raise ValueError('Model output does not match the label table')
        records.append({
            'start_seconds': start, 'end_seconds': end,
            'zero_padding_seconds': max(0, 160000-len(samples))/32000,
            'ranked_labels': [{'taxon': taxa[i], 'logit': float(logits[i])}
                              for i in np.argsort(logits)[-5:][::-1]],
        })
    return {
        'schema': 'eprs.perch-window-review/v1',
        'source': {'name': source.name, 'sha256': checksum(source)},
        'model': {'name': model.name, 'sha256': checksum(model)},
        'labels_sha256': checksum(labels), 'runtime': ort.__version__,
        'method': 'Perch v2 ONNX CPU; 32 kHz mono decode; short windows zero-padded to five seconds',
        'windows': records, 'source_use_eligible': False,
        'limitations': 'Uncalibrated logits are not probabilities. Short padded cuts can change rankings. Compare complete phrases with surrounding context and independent source evidence. This is model classification, not a human audition, species certification, animal-intent claim, or release approval.',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--window', action='append', type=window, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    validate_output(args.out, [args.source, args.model, args.labels])
    record = analyze(args.source, args.model, args.labels, args.window)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as handle:
        json.dump(record, handle, indent=2)
        handle.write('\n')
    print(args.out)


if __name__ == '__main__':
    main()
