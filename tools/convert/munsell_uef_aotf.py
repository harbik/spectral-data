#!/usr/bin/env python3
"""
Convert the UEF Munsell Matt AOTF dataset to spectral-io JSON batch files.

Source: https://sites.uef.fi/spectral/munsell-colors-matt-aotf-measured/
Measured at the University of Kuopio (now UEF), Finland, ca. 1993.
Equipment: Acousto Optic Tunable Filter (AOTF), 0/0 geometry, halogen illuminant.
400–700 nm at 5 nm intervals (61 points), 12-bit A/D (raw values pre-normalised in MATLAB file).
1250 matte Munsell chips from the Munsell Book of Color – Matte Finish Collection (1976).

Usage:
    python3 tools/convert/munsell_uef_aotf.py <mat_file> <output_dir>

Example:
    python3 tools/convert/munsell_uef_aotf.py \\
        /tmp/munsell_aotf/munsell400_700_5.mat \\
        spectra/colorbooks/munsell/matt/uef_aotf/
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.io

N_CHIPS = 1250
N_WAVELENGTHS = 61
WAVELENGTH_START = 400
WAVELENGTH_END = 700
WAVELENGTH_INTERVAL = 5

# Files in the tar archive are dated June–October 1993.
MEASUREMENT_DATE = "1993-06-01"

COPYRIGHT = (
    "© University of Eastern Finland (UEF) / Markku Hauta-Kasari. "
    "Non-commercial use only. "
    "Source: https://sites.uef.fi/spectral/munsell-colors-matt-aotf-measured/"
)

HUE_ORDER = ["R", "YR", "Y", "GY", "G", "BG", "B", "PB", "P", "RP"]

# Label format: '  10bV90C01.NM5'
# hue_raw (e.g. '10b') + 'V' + value_code + 'C' + chroma + '.NM5'
_LABEL_RE = re.compile(r"^\s*([^V]+)V(\d+)C(\d+)\.NM5\s*$")
_FAMILY_RE = re.compile(r"^[\d.]*([A-Z]+)$")


def _decode_label(raw: str) -> tuple[str, str, str, str]:
    """Return (hue, hue_family, val_str, chroma_str) from raw label."""
    m = _LABEL_RE.match(raw)
    if not m:
        raise ValueError(f"Cannot parse AOTF label: {raw!r}")

    hue_raw = m.group(1).strip()                          # e.g. '10b', '2_5r'
    val_code = int(m.group(2))                            # e.g. 90, 25
    chroma = int(m.group(3))                              # e.g. 1, 12

    hue = hue_raw.replace("_", ".").upper()               # '10B', '2.5R'

    fm = _FAMILY_RE.match(hue)
    family = fm.group(1) if fm else hue                   # 'B', 'R', 'PB', …

    val = val_code / 10
    val_str = str(int(val)) if val == int(val) else f"{val:.1f}"

    return hue, family, val_str, str(chroma)


def _chip_id(hue: str, val_str: str, chroma: str) -> str:
    return f"{hue}-{val_str}-{chroma}"


def main(mat_path: str, output_dir: str) -> None:
    mat_p = Path(mat_path)
    out = Path(output_dir)

    mat = scipy.io.loadmat(str(mat_p))

    # munsell: (61, 1250), values already normalised to [0, 1]
    spectra_wl_major = mat["munsell"]
    assert spectra_wl_major.shape == (N_WAVELENGTHS, N_CHIPS), (
        f"Unexpected munsell shape: {spectra_wl_major.shape}"
    )
    spectra = spectra_wl_major.T  # → (1250, 61)

    assert spectra.max() <= 1.0, f"Values exceed 1.0: max={spectra.max()}"
    assert spectra.min() >= 0.0, f"Negative values: min={spectra.min()}"

    # S: (1250,) array of 15-char label strings
    labels = [str(s) for s in mat["S"]]
    assert len(labels) == N_CHIPS

    # C: (16, 1250) colorimetry under D65 — same row layout as matt spectrophotometer dataset
    C = mat["C"]
    assert C.shape == (16, N_CHIPS)

    # Group chips by hue family
    groups: dict[str, list[int]] = defaultdict(list)
    for i, label in enumerate(labels):
        _, family, _, _ = _decode_label(label)
        groups[family].append(i)

    out.mkdir(parents=True, exist_ok=True)

    total = 0
    for family in HUE_ORDER:
        indices = groups.get(family, [])
        if not indices:
            continue

        records = []
        for i in indices:
            hue, _, val_str, chroma_str = _decode_label(labels[i])
            xyz = C[3:6, i].tolist()
            xy = C[0:2, i].tolist()
            lab = C[9:12, i].tolist()
            uv_prime = C[12:14, i].tolist()

            record = {
                "id": _chip_id(hue, val_str, chroma_str),
                "metadata": {
                    "measurement_type": "reflectance",
                    "date": MEASUREMENT_DATE,
                    "title": f"Munsell {hue} {val_str}/{chroma_str}",
                    "surface": "Matte",
                    "instrument": {
                        "manufacturer": "AOTF",
                        "model": "Acousto Optic Tunable Filter",
                    },
                    "measurement_conditions": {
                        "spectral_resolution_nm": 5.0,
                        "geometry": "0/0",
                    },
                    "tags": ["munsell", "color-chip", "matte", "color-book", "aotf"],
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
                "color_science": {
                    "illuminant": "D65",
                    "cie_observer": "CIE 1931 2 degree",
                    "results": {
                        "XYZ": [round(v, 6) for v in xyz],
                        "xy": [round(v, 6) for v in xy],
                        "uv_prime": [round(v, 6) for v in uv_prime],
                        "Lab": [round(v, 6) for v in lab],
                    },
                },
                "provenance": {
                    "source_file": "munsell400_700_5.mat",
                    "source_format": "MATLAB (UEF Munsell Matt AOTF dataset)",
                    "notes": (
                        "Values are pre-normalised reflectance from 12-bit AOTF measurements "
                        "(raw counts clipped at 4096 and divided by white-reference level). "
                        "Known issue in source data: some raw values exceeded 4096 (saturation); "
                        "those channels appear as 1.0 in this dataset. "
                        "Noise present below 420 nm due to low halogen lamp intensity."
                    ),
                },
            }
            records.append(record)

        batch = {
            "schema_version": "1.0.0",
            "file_type": "batch",
            "batch_metadata": {
                "title": f"Munsell Matte AOTF — Hue Family {family}",
                "date": MEASUREMENT_DATE,
                "instrument": {
                    "manufacturer": "AOTF",
                    "model": "Acousto Optic Tunable Filter",
                },
                "measurement_conditions": {
                    "spectral_resolution_nm": 5.0,
                    "geometry": "0/0",
                },
            },
            "spectra": records,
        }

        out_path = out / f"{family}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(batch, f, indent=2, ensure_ascii=False)

        print(f"  wrote {out_path}  ({len(records)} spectra)")
        total += len(records)

    for family, indices in groups.items():
        if family not in HUE_ORDER:
            print(f"WARNING: unexpected hue family '{family}' ({len(indices)} chips)", file=sys.stderr)

    print(f"\nTotal: {total} spectra in {len([f for f in HUE_ORDER if groups.get(f)])} files")
    assert total == N_CHIPS, f"Chip count mismatch: wrote {total}, expected {N_CHIPS}"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
