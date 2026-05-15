#!/usr/bin/env python3
"""
Convert the laserstars.org gas discharge emission line data to a single
spectral-io batch JSON file.

Source: https://laserstars.org/data/elements/
Data from NASA Astronomical Data Center catalog A6016.
Reference: Reader J. and Corliss Ch.H., "Line Spectra of the Elements,"
  CRC Handbook of Chemistry and Physics, NSRDS-NBS 68, 1981.
Applet by John Talbot.

19 elements: H, He, Li, C, N, O, Ne, Na, Mg, Al, Si, S, Fe, Ar, Ca, Kr, Xe, Ba, Sr.
Each file: two columns — wavelength (Å) and relative intensity (integer, 1–500).
Wavelengths converted to nm (÷ 10).

Usage:
    python3 tools/convert/elements_laserstars.py <data_dir> <output_file>

Example:
    python3 tools/convert/elements_laserstars.py \\
        /tmp/elements_laserstars/ \\
        spectra/elements/laserstars_emission_lines.json
"""

import json
import sys
from pathlib import Path

MEASUREMENT_DATE = "1981-01-01"

COPYRIGHT = (
    "Data courtesy of the NASA Astronomical Data Center, the National Space "
    "Science Data Center, and the World Data Center A for Rockets and Satellites. "
    "Source: https://laserstars.org/data/elements/ "
    "(applet by John Talbot; underlying data: Reader & Corliss, NSRDS-NBS 68, 1981)"
)

ELEMENTS = [
    # (filename_stem, symbol, atomic_number, full_name)
    ("hydrogen",   "H",  1,  "Hydrogen"),
    ("helium",     "He", 2,  "Helium"),
    ("lithium",    "Li", 3,  "Lithium"),
    ("carbon",     "C",  6,  "Carbon"),
    ("nitrogen",   "N",  7,  "Nitrogen"),
    ("oxygen",     "O",  8,  "Oxygen"),
    ("neon",       "Ne", 10, "Neon"),
    ("sodium",     "Na", 11, "Sodium"),
    ("magnesium",  "Mg", 12, "Magnesium"),
    ("aluminum",   "Al", 13, "Aluminum"),
    ("silicon",    "Si", 14, "Silicon"),
    ("sulfur",     "S",  16, "Sulfur"),
    ("argon",      "Ar", 18, "Argon"),
    ("calcium",    "Ca", 20, "Calcium"),
    ("iron",       "Fe", 26, "Iron"),
    ("krypton",    "Kr", 36, "Krypton"),
    ("strontium",  "Sr", 38, "Strontium"),
    ("xenon",      "Xe", 54, "Xenon"),
    ("barium",     "Ba", 56, "Barium"),
]


def _parse_txt(path):
    """Return (wavelengths_nm, intensities) from a two-column Å/intensity file."""
    pairs = []
    with open(path, encoding="ascii") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            pairs.append((round(float(parts[0]) / 10.0, 4), int(parts[1])))
    pairs.sort(key=lambda p: p[0])
    wavelengths_nm = [p[0] for p in pairs]
    intensities = [p[1] for p in pairs]
    return wavelengths_nm, intensities


def main(data_dir, output_file):
    base = Path(data_dir)
    out = Path(output_file)

    records = []
    for stem, symbol, atomic_number, full_name in ELEMENTS:
        path = base / f"{stem}.txt"
        wavelengths_nm, intensities = _parse_txt(path)

        record = {
            "id": stem,
            "metadata": {
                "measurement_type": "emission",
                "date": MEASUREMENT_DATE,
                "title": f"{full_name} ({symbol}) — Gas Discharge Emission Lines",
                "measurement_conditions": {
                    "source": "gas discharge tube",
                },
                "tags": ["emission", "gas-discharge", "line-spectrum",
                         "atomic-spectroscopy", stem, symbol.lower()],
                "custom": {
                    "symbol": symbol,
                    "atomic_number": atomic_number,
                    "intensity_scale": "relative (1–500)",
                },
                "copyright": COPYRIGHT,
            },
            "wavelength_axis": {
                "values_nm": wavelengths_nm,
            },
            "spectral_data": {
                "values": intensities,
            },
            "provenance": {
                "source_file": f"{stem}.txt",
                "source_format": (
                    "ASCII two-column (wavelength Å, relative intensity); "
                    "NASA ADC catalog A6016"
                ),
                "notes": (
                    "Wavelengths converted from Ångströms to nm (÷ 10). "
                    "Intensities are relative (not absolute radiance); "
                    "maximum is 500 for the brightest line per source dataset. "
                    "Coverage is approximately 390–720 nm (visible range)."
                ),
            },
        }
        records.append(record)
        print(f"  {full_name:12s} ({symbol:2s}, Z={atomic_number:2d}): "
              f"{len(wavelengths_nm)} lines, "
              f"{min(wavelengths_nm):.1f}–{max(wavelengths_nm):.1f} nm")

    batch = {
        "schema_version": "1.0.0",
        "file_type": "batch",
        "batch_metadata": {
            "title": "Gas Discharge Emission Lines — 19 Elements (laserstars.org)",
            "date": MEASUREMENT_DATE,
            "measurement_conditions": {
                "source": "gas discharge tube",
            },
        },
        "spectra": records,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {out}  ({len(records)} spectra)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
