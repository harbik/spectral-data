#!/usr/bin/env python3
"""
Convert the UEF lumber spectral dataset to spectral-io batch JSON files.

Source: https://sites.uef.fi/spectral/lumber-spectra/
Measured by Jouni Hiltunen, University of Joensuu, Finland, ca. October 1994.
Equipment: Perkin-Elmer Lambda 9 UV/VIS/NIR spectrophotometer (four-mirror system).
380–2700 nm at 1 nm (2321 points). Reflectance relative to a mirror (filter cutting
87.25% in reference beam).

8 MATLAB files, 4 wood species × 2 types:
  Wb — sawn timber with branches/knots
  Wp — pure sawn timber without branches

Counts per species:
  pine:   51 (Wb) + 44 (Wp) = 95
  spruce: 40 (Wb) + 35 (Wp) = 75
  aspen:  40 (Wb) + 38 (Wp) = 78
  birch:  12 (Wb) + 12 (Wp) = 24

A small number of values fall outside [0, 1] due to instrument noise at the far
NIR end (>2690 nm); these are clipped.

Usage:
    python3 tools/convert/lumber_uef.py <mat_dir> <output_dir>

Example:
    python3 tools/convert/lumber_uef.py \\
        /tmp/lumber_uef/ \\
        spectra/wood/
"""

import json
import sys
from pathlib import Path

import numpy as np
import scipy.io

N_WAVELENGTHS = 2321
WAVELENGTH_START = 380
WAVELENGTH_END = 2700
WAVELENGTH_INTERVAL = 1

MEASUREMENT_DATE = "1994-10-10"

COPYRIGHT = (
    "© University of Eastern Finland (UEF) / Jouni Hiltunen. "
    "Non-commercial use only. "
    "Source: https://sites.uef.fi/spectral/lumber-spectra/"
)

INSTRUMENT = {
    "manufacturer": "Perkin-Elmer",
    "model": "Lambda 9 UV/VIS/NIR",
}

MEASUREMENT_CONDITIONS = {
    "spectral_resolution_nm": 1.0,
    "geometry": "specular (four-mirror system)",
}

# (mat_key, species_label, type_code, type_label, tags)
GROUPS = [
    ("pineWb",   "Scots pine",    "wb", "with branches",    ["pine", "Pinus sylvestris",  "knotty"]),
    ("pineWp",   "Scots pine",    "wp", "pure, no branches",["pine", "Pinus sylvestris",  "clear"]),
    ("spruceWb", "Norway spruce", "wb", "with branches",    ["spruce", "Picea abies",     "knotty"]),
    ("spruceWp", "Norway spruce", "wp", "pure, no branches",["spruce", "Picea abies",     "clear"]),
    ("aspenWb",  "Aspen",         "wb", "with branches",    ["aspen", "Populus tremula",  "knotty"]),
    ("aspenWp",  "Aspen",         "wp", "pure, no branches",["aspen", "Populus tremula",  "clear"]),
    ("birchWb",  "Birch",         "wb", "with branches",    ["birch", "Betula",           "knotty"]),
    ("birchWp",  "Birch",         "wp", "pure, no branches",["birch", "Betula",           "clear"]),
]

# Group output by species
SPECIES = [
    ("pine",   "Scots pine",    ["pineWb",   "pineWp"]),
    ("spruce", "Norway spruce", ["spruceWb", "spruceWp"]),
    ("aspen",  "Aspen",         ["aspenWb",  "aspenWp"]),
    ("birch",  "Birch",         ["birchWb",  "birchWp"]),
]


def main(mat_dir, output_dir):
    base = Path(mat_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Load all MATLAB files
    group_info = {g[0]: g for g in GROUPS}
    mats = {}
    for mat_key, _, _, _, _ in GROUPS:
        mat = scipy.io.loadmat(str(base / f"{mat_key}.mat"))
        data = mat[mat_key]  # (2321, N)
        assert data.shape[0] == N_WAVELENGTHS, f"{mat_key}: expected {N_WAVELENGTHS} rows, got {data.shape[0]}"
        mats[mat_key] = data

    total = 0
    for species_id, species_label, mat_keys in SPECIES:
        records = []
        n_clipped_species = 0

        for mat_key in mat_keys:
            _, _, type_code, type_label, extra_tags = group_info[mat_key]
            data = mats[mat_key]
            n = data.shape[1]
            n_clipped = int(((data > 1.0) | (data < 0.0)).sum())
            n_clipped_species += n_clipped

            for i in range(n):
                vals = np.clip(data[:, i], 0.0, 1.0).tolist()
                record = {
                    "id": f"{species_id}-{type_code}-{i+1:03d}",
                    "metadata": {
                        "measurement_type": "reflectance",
                        "date": MEASUREMENT_DATE,
                        "title": f"{species_label} — {type_label} #{i+1}",
                        "operator": "Jouni Hiltunen",
                        "instrument": INSTRUMENT,
                        "measurement_conditions": MEASUREMENT_CONDITIONS,
                        "tags": ["wood", "lumber", "timber", "sawn"] + extra_tags,
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
                        "values": [round(v, 7) for v in vals],
                        "scale": "fractional",
                    },
                    "provenance": {
                        "source_file": f"{mat_key}.mat",
                        "source_format": "MATLAB (UEF lumber dataset)",
                        "notes": (
                            "Reflectance measured relative to a first-surface mirror "
                            "(87.25% filter in reference beam, four-mirror geometry). "
                            f"{n_clipped} value(s) in this group fell outside [0, 1] "
                            "due to instrument noise at the far NIR end (>2690 nm) "
                            "and were clipped."
                        ),
                    },
                }
                records.append(record)

        n_total = len(records)
        batch = {
            "schema_version": "1.0.0",
            "file_type": "batch",
            "batch_metadata": {
                "title": f"UEF Lumber Reflectance — {species_label}",
                "date": MEASUREMENT_DATE,
                "operator": "Jouni Hiltunen",
                "instrument": INSTRUMENT,
                "measurement_conditions": MEASUREMENT_CONDITIONS,
            },
            "spectra": records,
        }

        out_path = out / f"uef_lumber_{species_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(batch, f, indent=2, ensure_ascii=False)

        print(f"  wrote {out_path}  ({n_total} spectra, {n_clipped_species} values clipped)")
        total += n_total

    print(f"\nTotal: {total} spectra")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
