#!/usr/bin/env python3
"""
Convert the UEF Munsell Glossy 32-chip subset to spectral-io JSON batch files.

Source: https://sites.uef.fi/spectral/munsell-colors-glossy-spectrofotometer-measured/
Contact: Markku Hauta-Kasari, University of Eastern Finland.
Equipment: Minolta CM-2002 spectrofotometer, 400–700 nm at 10 nm, specular excluded.
32 glossy Munsell chips: hues 5R, 7.5R, 5G, 7.5G; values 5–6; chromas 6–8.

Note: reflectance values in the source files are in percent (0–100).
      Divided by 100 to produce fractional [0, 1] values for spectral-io.

Usage:
    python3 tools/convert/munsell_uef_glossy_32.py <mat_file> <output_dir>

Example:
    python3 tools/convert/munsell_uef_glossy_32.py \\
        /tmp/munsell_glossy32/munsell400_700_10.mat \\
        spectra/colorbooks/munsell/glossy/uef_subset/
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.io

N_CHIPS = 32
N_WAVELENGTHS = 31
WAVELENGTH_START = 400
WAVELENGTH_END = 700
WAVELENGTH_INTERVAL = 10

# No exact date published; approximate based on dataset provenance.
MEASUREMENT_DATE = "1999-01-01"

COPYRIGHT = (
    "© University of Eastern Finland (UEF) / Markku Hauta-Kasari. "
    "Non-commercial use only. "
    "Source: https://sites.uef.fi/spectral/munsell-colors-glossy-spectrofotometer-measured/"
)

_HUE_RE = re.compile(r"^[\d_.]*([A-Z]+)")

# Normalize '7_5R' → '7.5R' style labels
def _normalize_label(raw: str) -> str:
    return raw.strip().replace("_", ".")


def _hue_family(label: str) -> str:
    m = _HUE_RE.match(label)
    return m.group(1) if m else "UNKNOWN"


def _chip_id(label: str) -> str:
    return label.replace(" ", "-").replace("/", "-").rstrip("-")


def main(mat_path: str, output_dir: str) -> None:
    mat_p = Path(mat_path)
    out = Path(output_dir)

    mat = scipy.io.loadmat(str(mat_p))

    # munsell: (31, 32), values in percent → divide by 100 for fractional
    spectra_pct = mat["munsell"]  # (31, 32): [wavelength, chip]
    assert spectra_pct.shape == (N_WAVELENGTHS, N_CHIPS), (
        f"Unexpected munsell shape: {spectra_pct.shape}"
    )
    spectra = (spectra_pct / 100.0).T  # → (32, 31): [chip, wavelength]

    assert spectra.max() <= 1.0, f"Values exceed 1.0 after /100: max={spectra.max()}"
    assert spectra.min() >= 0.0, f"Negative values after /100: min={spectra.min()}"

    # S: (32,) array of Munsell notation strings like '5R 6/6  ' or '7_5G 5/8'
    labels = [_normalize_label(str(s)) for s in mat["S"]]
    assert len(labels) == N_CHIPS

    # Group by hue family
    groups: dict[str, list[int]] = defaultdict(list)
    for i, label in enumerate(labels):
        groups[_hue_family(label)].append(i)

    out.mkdir(parents=True, exist_ok=True)

    total = 0
    for family in sorted(groups.keys()):
        indices = groups[family]
        records = []
        for i in indices:
            label = labels[i]
            record = {
                "id": _chip_id(label),
                "metadata": {
                    "measurement_type": "reflectance",
                    "date": MEASUREMENT_DATE,
                    "title": f"Munsell {label}",
                    "surface": "Glossy",
                    "instrument": {
                        "manufacturer": "Minolta",
                        "model": "CM-2002",
                    },
                    "measurement_conditions": {
                        "spectral_resolution_nm": 10.0,
                        "specular_component": "excluded",
                    },
                    "tags": ["munsell", "color-chip", "glossy", "color-book"],
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
                    "values": [round(v, 6) for v in spectra[i].tolist()],
                    "scale": "fractional",
                },
                "provenance": {
                    "source_file": "munsell400_700_10.mat",
                    "source_format": "MATLAB (UEF Munsell Glossy 32-chip dataset)",
                    "notes": (
                        "Measurement date is approximate (ca. 1999); exact date not published. "
                        "Source values were in percent (0–100); divided by 100 for fractional scale. "
                        "Specular component excluded. "
                        "Each Munsell chip appears to have been measured twice; "
                        "duplicate measurements are preserved as separate records."
                    ),
                },
            }
            records.append(record)

        batch = {
            "schema_version": "1.0.0",
            "file_type": "batch",
            "batch_metadata": {
                "title": f"Munsell Glossy 32-chip subset — Hue Family {family}",
                "date": MEASUREMENT_DATE,
                "instrument": {
                    "manufacturer": "Minolta",
                    "model": "CM-2002",
                },
                "measurement_conditions": {
                    "spectral_resolution_nm": 10.0,
                    "specular_component": "excluded",
                },
            },
            "spectra": records,
        }

        out_path = out / f"{family}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(batch, f, indent=2, ensure_ascii=False)

        print(f"  wrote {out_path}  ({len(records)} spectra)")
        total += len(records)

    print(f"\nTotal: {total} spectra in {len(groups)} files")
    assert total == N_CHIPS, f"Chip count mismatch: wrote {total}, expected {N_CHIPS}"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
