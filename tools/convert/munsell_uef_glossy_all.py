#!/usr/bin/env python3
"""
Convert the UEF Munsell Glossy All (1600-chip) dataset to spectral-io JSON batch files.

Source: https://sites.uef.fi/spectral/munsell-colors-glossy-all-spectrofotometer-measured/
Measured by Joni Orava, University of Eastern Finland.
Equipment: Perkin-Elmer Lambda 18 UV/VIS, 380–780 nm at 1 nm, specular excluded.
1600 glossy Munsell chips from the Munsell Book of Color – Glossy Finish Collection (1976).

Usage:
    python3 tools/convert/munsell_uef_glossy_all.py <asc_file> <mat_file> <names_xls> <output_dir>

Example:
    python3 tools/convert/munsell_uef_glossy_all.py \\
        /tmp/munsell_glossy_all/munsell380_780_1_glossy.asc \\
        /tmp/munsell_glossy_all/munsell380_780_1_glossy.mat \\
        /tmp/munsell_glossy_all/names.xls \\
        spectra/colorbooks/munsell/glossy/uef/
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.io
import xlrd

N_CHIPS = 1600
N_WAVELENGTHS = 401
WAVELENGTH_START = 380
WAVELENGTH_END = 780
WAVELENGTH_INTERVAL = 1

# No exact date published; approximate based on known dataset provenance.
MEASUREMENT_DATE = "2003-01-01"

COPYRIGHT = (
    "© University of Eastern Finland (UEF) / Joni Orava. "
    "Non-commercial use only. "
    "Source: https://sites.uef.fi/spectral/munsell-colors-glossy-all-spectrofotometer-measured/"
)

HUE_ORDER = ["R", "YR", "Y", "GY", "G", "BG", "B", "PB", "P", "RP", "N"]

# First character of 3-char prefix → Munsell hue step
_STEP_MAP = {"A": "2.5", "B": "5", "C": "7.5", "D": "10"}

# Last 2 chars of 3-char prefix → Munsell hue family
_FAMILY_FROM_SUFFIX = {
    "RR": "R", "YR": "YR", "YY": "Y", "GY": "GY",
    "GG": "G", "BG": "BG", "BB": "B", "PB": "PB",
    "PP": "P", "RP": "RP",
}


def _decode_label(stem: str) -> tuple[str, str]:
    """Return (hue_family, title) for a chip file stem like 'ABB2002' or 'NEUT050'."""
    if stem.startswith("NEUT"):
        val_hundredths = int(stem[4:])
        val = val_hundredths / 100
        val_str = f"{val:.2f}".rstrip("0").rstrip(".")
        return "N", f"N {val_str}/"

    prefix = stem[:3]
    num = stem[3:]
    step_char = prefix[0]
    suffix = prefix[1:]

    family = _FAMILY_FROM_SUFFIX.get(suffix, suffix)
    step = _STEP_MAP.get(step_char)

    val_code = int(num[:2])
    chroma = int(num[2:])
    val = val_code / 10
    val_str = str(int(val)) if val == int(val) else f"{val:.1f}"

    if step is not None:
        hue = f"{step}{family}"
        title = f"Munsell {hue} {val_str}/{chroma}"
    else:
        # Supplemental hue (E–H prefix) — keep raw code in title
        title = f"Munsell {prefix} {val_str}/{chroma}"

    return family, title


def main(asc_path: str, mat_path: str, names_path: str, output_dir: str) -> None:
    asc = Path(asc_path)
    mat_p = Path(mat_path)
    out = Path(output_dir)

    # --- Spectral data: ASC is (401 rows × 1600 cols), wavelength-major ---
    spectra_wl_major = np.loadtxt(asc)
    assert spectra_wl_major.shape == (N_WAVELENGTHS, N_CHIPS), (
        f"Unexpected ASC shape: {spectra_wl_major.shape}"
    )
    spectra = spectra_wl_major.T  # → (1600, 401): [chip_index, wavelength_index]

    # --- MATLAB: XYZ (1600×3) and xyY (1600×3) ---
    mat = scipy.io.loadmat(str(mat_p))
    XYZ_mat = mat["XYZ"]    # (1600, 3): CIE XYZ under D65
    xyY_mat = mat["xyY"]    # (1600, 3): x, y, Y

    # Cross-check spectral data against MATLAB X matrix (401×1600)
    assert np.allclose(spectra[0], mat["X"][:, 0], atol=1e-9), (
        "ASC and MATLAB spectral data disagree for chip 0"
    )

    # --- Labels from names.xls column 1 ---
    wb = xlrd.open_workbook(str(Path(names_path)))
    ws = wb.sheet_by_index(0)
    assert ws.nrows == N_CHIPS, f"Expected {N_CHIPS} label rows, got {ws.nrows}"
    filenames = [str(ws.cell_value(r, 1)).strip() for r in range(ws.nrows)]
    stems = [f.replace(".DX", "") for f in filenames]

    # --- Group chips by hue family ---
    groups: dict[str, list[int]] = defaultdict(list)
    for i, stem in enumerate(stems):
        family, _ = _decode_label(stem)
        groups[family].append(i)

    out.mkdir(parents=True, exist_ok=True)

    total = 0
    for family in HUE_ORDER:
        indices = groups.get(family, [])
        if not indices:
            continue

        records = []
        for i in indices:
            stem = stems[i]
            family_key, title = _decode_label(stem)
            xyz = XYZ_mat[i].tolist()
            xy = xyY_mat[i, :2].tolist()

            record = {
                "id": stem,
                "metadata": {
                    "measurement_type": "reflectance",
                    "date": MEASUREMENT_DATE,
                    "title": title,
                    "surface": "Glossy",
                    "operator": "Joni Orava",
                    "instrument": {
                        "manufacturer": "Perkin-Elmer",
                        "model": "Lambda 18 UV/VIS",
                    },
                    "measurement_conditions": {
                        "spectral_resolution_nm": 1.0,
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
                "color_science": {
                    "illuminant": "D65",
                    "cie_observer": "CIE 1931 2 degree",
                    "results": {
                        "XYZ": [round(v, 6) for v in xyz],
                        "xy": [round(v, 6) for v in xy],
                    },
                },
                "provenance": {
                    "source_file": f"{stem}.DX",
                    "source_format": "ASCII (UEF Munsell Glossy All dataset)",
                    "notes": (
                        "Measurement date is approximate (ca. 2003); exact date not published. "
                        "Specular component excluded. "
                        "Colorimetric values (XYZ, xy) are pre-computed under D65 / "
                        "CIE 1931 2° and provided as-is from the original dataset."
                    ),
                },
            }
            records.append(record)

        batch = {
            "schema_version": "1.0.0",
            "file_type": "batch",
            "batch_metadata": {
                "title": f"Munsell Glossy — Hue Family {family}",
                "date": MEASUREMENT_DATE,
                "operator": "Joni Orava",
                "instrument": {
                    "manufacturer": "Perkin-Elmer",
                    "model": "Lambda 18 UV/VIS",
                },
                "measurement_conditions": {
                    "spectral_resolution_nm": 1.0,
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

    for family, indices in groups.items():
        if family not in HUE_ORDER:
            print(f"WARNING: unexpected hue family '{family}' ({len(indices)} chips)", file=sys.stderr)

    print(f"\nTotal: {total} spectra in {len([f for f in HUE_ORDER if groups.get(f)])} files")
    assert total == N_CHIPS, f"Chip count mismatch: wrote {total}, expected {N_CHIPS}"


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
