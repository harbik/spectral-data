#!/usr/bin/env python3
"""
Convert the UEF natural colors dataset to a single spectral-io batch JSON file.

Source: https://sites.uef.fi/spectral/natural-colors/
Measured by Esa Koivisto, Department of Physics, University of Kuopio, Finland.
Equipment: Acousto Optic Tunable Filter (AOTF), 400–700 nm at 5 nm (61 points).
219 reflectance spectra of colored natural samples: flowers, leaves, and plants.

Raw 12-bit A/D values (0–4096); a small number exceed 4096 (clipped before normalising).
Normalised by dividing by 4096.

Reference: Parkkinen, J., Jaaskelainen, T. and Kuittinen, M., "Spectral representation
of color images," IEEE 9th ICPR, Rome, 1988, Vol. 2, pp. 933–935.

Usage:
    python3 tools/convert/natural_uef.py <asc_file> <output_file>

Example:
    python3 tools/convert/natural_uef.py \\
        /tmp/natural_uef/natural400_700_5.asc \\
        spectra/nature/uef_natural.json
"""

import json
import re
import sys
from pathlib import Path

N_WAVELENGTHS = 61
WAVELENGTH_START = 400
WAVELENGTH_END = 700
WAVELENGTH_INTERVAL = 5
ADC_MAX = 4096

# No specific date available; use approximate year from publication.
MEASUREMENT_DATE = "1988-01-01"

COPYRIGHT = (
    "© University of Eastern Finland (UEF) / Esa Koivisto. "
    "Non-commercial use only. "
    "Source: https://sites.uef.fi/spectral/natural-colors/"
)

INSTRUMENT = {
    "manufacturer": "AOTF",
    "model": "Acousto Optic Tunable Filter",
}


def _slugify(text):
    """Convert label text to a URL-safe slug."""
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _parse_asc(path):
    """Parse label+values blocks from the ASCII file. Returns list of (label, [int,...])."""
    blocks = []
    current_label = None
    current_values = []

    with open(path, encoding="ascii", errors="replace") as f:
        for line in f:
            line = line.rstrip()
            if not line.strip():
                continue
            tokens = line.split()
            all_int = True
            for t in tokens:
                try:
                    int(t)
                except ValueError:
                    all_int = False
                    break
            if all_int:
                current_values.extend(int(t) for t in tokens)
            else:
                if current_label is not None:
                    blocks.append((current_label, current_values))
                current_label = line.strip()
                current_values = []

    if current_label is not None:
        blocks.append((current_label, current_values))

    return blocks


def main(asc_path, output_file):
    asc_p = Path(asc_path)
    out = Path(output_file)

    blocks = _parse_asc(asc_p)
    n = len(blocks)

    # Assign unique IDs (add numeric suffix for duplicate labels)
    slug_counts = {}
    slug_seen = {}
    ids = []
    for label, _ in blocks:
        slug = _slugify(label)
        slug_counts[slug] = slug_counts.get(slug, 0) + 1
    for label, _ in blocks:
        slug = _slugify(label)
        if slug_counts[slug] == 1:
            ids.append(slug)
        else:
            slug_seen[slug] = slug_seen.get(slug, 0) + 1
            ids.append(f"{slug}-{slug_seen[slug]:02d}")

    n_clipped = 0
    records = []
    for i, (label, raw_vals) in enumerate(blocks):
        assert len(raw_vals) == N_WAVELENGTHS, (
            f"Spectrum '{label}' has {len(raw_vals)} values, expected {N_WAVELENGTHS}"
        )
        clipped_here = sum(1 for v in raw_vals if v > ADC_MAX)
        n_clipped += clipped_here

        values = [round(min(v, ADC_MAX) / ADC_MAX, 7) for v in raw_vals]

        record = {
            "id": ids[i],
            "metadata": {
                "measurement_type": "reflectance",
                "date": MEASUREMENT_DATE,
                "title": label,
                "operator": "Esa Koivisto",
                "instrument": INSTRUMENT,
                "measurement_conditions": {
                    "spectral_resolution_nm": 5.0,
                },
                "tags": ["natural", "vegetation", "plant", "aotf"],
                "copyright": COPYRIGHT,
            },
            "wavelength_axis": {
                "range_nm": {
                    "start": WAVELENGTH_START,
                    "end": WAVELENGTH_END,
                    "interval": WAVELENGTH_INTERVAL,
                }
            },
            "spectral_data": {
                "values": values,
                "scale": "fractional",
            },
            "provenance": {
                "source_file": asc_p.name,
                "source_format": "ASCII (UEF natural colors dataset)",
                "notes": (
                    "Raw 12-bit AOTF A/D values (0–4096) normalised by dividing by 4096. "
                    f"{n_clipped} source value(s) across all {n} spectra exceeded 4096 "
                    "(instrument saturation) and were clipped before normalising."
                ),
            },
        }
        records.append(record)

    batch = {
        "schema_version": "1.0.0",
        "file_type": "batch",
        "batch_metadata": {
            "title": "UEF Natural Colors — Flowers, Leaves, and Plants",
            "date": MEASUREMENT_DATE,
            "operator": "Esa Koivisto",
            "instrument": INSTRUMENT,
            "measurement_conditions": {
                "spectral_resolution_nm": 5.0,
            },
        },
        "spectra": records,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    print(f"Wrote {out}  ({len(records)} spectra, {n_clipped} values clipped)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
