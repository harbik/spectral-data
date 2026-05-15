#!/usr/bin/env python3
"""
Convert the UEF Munsell Matte spectrophotometer dataset to spectral-io JSON batch files.

Source: https://sites.uef.fi/spectral/databases-software/munsell-colors-matt-spectrofotometer-measured/
Measured by Jouni Hiltunen, University of Eastern Finland (formerly University of Joensuu).
Equipment: Perkin-Elmer Lambda 9 UV/VIS/NIR, 380–800 nm at 1 nm intervals.
1269 matte Munsell color chips from the Munsell Book of Color – Matte Finish Collection (1976).

Usage:
    python3 tools/convert/munsell_uef.py <asc_file> <mat_file> <output_dir>

Example:
    python3 tools/convert/munsell_uef.py \\
        /tmp/munsell_uef/munsell380_800_1.asc \\
        /tmp/munsell_uef/munsell380_800_1.mat \\
        spectra/colorbooks/munsell/matt/uef/
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.io

N_CHIPS = 1269
N_WAVELENGTHS = 421
WAVELENGTH_START = 380
WAVELENGTH_END = 800
WAVELENGTH_INTERVAL = 1

# Earliest publication using this dataset: Lenz et al., JOSA A, July 1996.
# Exact measurement date unknown; using approximate year of data collection.
MEASUREMENT_DATE = "1995-01-01"

COPYRIGHT = (
    "© University of Eastern Finland (UEF) / Jouni Hiltunen. "
    "Non-commercial use only. "
    "Source: https://sites.uef.fi/spectral/databases-software/"
    "munsell-colors-matt-spectrofotometer-measured/"
)

# Munsell hue family order for sorted output
HUE_ORDER = ["R", "YR", "Y", "GY", "G", "BG", "B", "PB", "P", "RP", "N"]

_HUE_RE = re.compile(r"^[\d.]*([A-Z]+)")


def _hue_family(label: str) -> str:
    m = _HUE_RE.match(label.strip())
    return m.group(1) if m else "UNKNOWN"


def _chip_id(label: str) -> str:
    """Convert 'H V/C' or 'N V/' to a safe identifier like 'H-V-C' or 'N-V'."""
    s = label.strip().replace(" ", "-").replace("/", "-").rstrip("-")
    return s


def _build_record(
    label: str,
    reflectances: list,
    xyz: list,
    xy: list,
    uv_prime: list,
    lab: list,
) -> dict:
    return {
        "id": _chip_id(label),
        "metadata": {
            "measurement_type": "reflectance",
            "date": MEASUREMENT_DATE,
            "title": f"Munsell {label.strip()}",
            "surface": "Matte",
            "operator": "Jouni Hiltunen",
            "instrument": {
                "manufacturer": "Perkin-Elmer",
                "model": "Lambda 9 UV/VIS/NIR",
            },
            "measurement_conditions": {
                "spectral_resolution_nm": 1.0,
            },
            "tags": ["munsell", "color-chip", "matte", "color-book"],
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
            "values": [round(v, 6) for v in reflectances],
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
            "source_file": "munsell380_800_1.asc",
            "source_format": "ASCII (UEF Munsell Matte dataset)",
            "notes": (
                "Measurement date is approximate (ca. 1995); exact date not published. "
                "Colorimetric values (XYZ, Lab, u'v') are pre-computed under D65 / "
                "CIE 1931 2° and provided as-is from the original dataset."
            ),
        },
    }


def main(asc_path: str, mat_path: str, output_dir: str) -> None:
    asc = Path(asc_path)
    mat = Path(mat_path)
    out = Path(output_dir)

    # --- Load spectral data from ASCII file ---
    # Layout: N_CHIPS × N_WAVELENGTHS values, one per line (column-major from MATLAB).
    raw = np.loadtxt(asc)
    assert raw.shape == (N_CHIPS * N_WAVELENGTHS,), f"Unexpected shape: {raw.shape}"
    spectra = raw.reshape(N_CHIPS, N_WAVELENGTHS)  # [chip_index, wavelength_index]

    # --- Load MATLAB file for labels and colorimetry ---
    m = scipy.io.loadmat(str(mat))

    # S: (1269,) array of U12 strings, e.g. "2.5R 9/2    "
    labels = [str(s).strip() for s in m["S"]]
    assert len(labels) == N_CHIPS

    # C: (16, 1269) colorimetry matrix under D65 / CIE 1931 2°
    # Row layout (from dataset README):
    #   0-2  : CIE xyz chromaticity coordinates
    #   3-5  : CIE XYZ tristimulus values
    #   6-8  : linear RGB
    #   9-11 : CIELAB L*, a*, b*
    #  12-13 : CIE 1976 UCS u', v'
    #  14-15 : CIE 1976 Luv u*, v*
    C = m["C"]
    assert C.shape == (16, N_CHIPS), f"Unexpected C shape: {C.shape}"

    # --- Cross-check first chip against MATLAB munsell matrix ---
    munsell_mat = m["munsell"]  # (421, 1269)
    assert np.allclose(spectra[0], munsell_mat[:, 0], atol=1e-9), (
        "ASCII and MATLAB spectral data disagree for chip 0"
    )

    # --- Group chips by hue family ---
    groups: dict[str, list[int]] = defaultdict(list)
    for i, label in enumerate(labels):
        groups[_hue_family(label)].append(i)

    unknown = groups.pop("UNKNOWN", [])
    if unknown:
        print(f"WARNING: {len(unknown)} chips with unrecognized hue notation", file=sys.stderr)

    out.mkdir(parents=True, exist_ok=True)

    total = 0
    for family in HUE_ORDER:
        indices = groups.get(family, [])
        if not indices:
            continue

        records = []
        for i in indices:
            label = labels[i]
            records.append(
                _build_record(
                    label=label,
                    reflectances=spectra[i].tolist(),
                    xyz=C[3:6, i].tolist(),
                    xy=C[0:2, i].tolist(),
                    uv_prime=C[12:14, i].tolist(),
                    lab=C[9:12, i].tolist(),
                )
            )

        batch = {
            "schema_version": "1.0.0",
            "file_type": "batch",
            "batch_metadata": {
                "title": f"Munsell Matte — Hue Family {family}",
                "date": MEASUREMENT_DATE,
                "operator": "Jouni Hiltunen",
                "instrument": {
                    "manufacturer": "Perkin-Elmer",
                    "model": "Lambda 9 UV/VIS/NIR",
                },
                "measurement_conditions": {
                    "spectral_resolution_nm": 1.0,
                },
            },
            "spectra": records,
        }

        out_path = out / f"{family}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(batch, f, indent=2, ensure_ascii=False)

        print(f"  wrote {out_path}  ({len(records)} spectra)")
        total += len(records)

    # Warn about any families not in HUE_ORDER
    for family, indices in groups.items():
        if family not in HUE_ORDER:
            print(f"WARNING: unexpected hue family '{family}' ({len(indices)} chips) — skipped", file=sys.stderr)

    print(f"\nTotal: {total} spectra in {len([f for f in HUE_ORDER if groups.get(f)])} files")
    assert total == N_CHIPS - len(unknown), f"Chip count mismatch: wrote {total}, expected {N_CHIPS}"


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
