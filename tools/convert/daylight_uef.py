#!/usr/bin/env python3
"""
Convert the UEF daylight spectral dataset to a single spectral-io batch JSON file.

Source: https://sites.uef.fi/spectral/daylight-spectra/
Measured by Jussi Parkkinen and Pertti Silfsten (LUT), March 30 – May 16, 1995.
Equipment: Photo Research PR-713/702 AM spectroradiometer.
390–1070 nm at 4 nm (171 points). Spectral radiance.
52 spectra in three groups:
  - BaSO4 white reference panel (15 spectra)
  - Sky via mirror reflection (22 spectra)
  - Spruce tree at ~100 m distance (15 spectra)

Usage:
    python3 tools/convert/daylight_uef.py <baso4_mat> <sky_mat> <tree_mat> <output_file>

Example:
    python3 tools/convert/daylight_uef.py \\
        /tmp/daylight_uef/BaSO4.mat \\
        /tmp/daylight_uef/sky.mat \\
        /tmp/daylight_uef/tree.mat \\
        spectra/nature/uef_daylight.json
"""

import json
import sys
from pathlib import Path

import numpy as np
import scipy.io

N_WAVELENGTHS = 171
WAVELENGTH_START = 390
WAVELENGTH_END = 1070
WAVELENGTH_INTERVAL = 4

# Measurements span 1995-03-30 to 1995-05-16; use start date for records.
MEASUREMENT_DATE = "1995-03-30"

COPYRIGHT = (
    "© University of Eastern Finland (UEF) / Jussi Parkkinen, Pertti Silfsten. "
    "Non-commercial use only. "
    "Source: https://sites.uef.fi/spectral/daylight-spectra/"
)

INSTRUMENT = {
    "manufacturer": "Photo Research",
    "model": "PR-713/702 AM",
}

MEASUREMENT_CONDITIONS = {
    "spectral_resolution_nm": 4.0,
}

GROUPS = [
    ("baso4", "BaSO4 white reference panel",   "baso4", ["barium-sulfate", "white-reference", "daylight"]),
    ("sky",   "Sky (mirror reflection)",        "sky",   ["sky", "daylight", "natural-illuminant"]),
    ("tree",  "Spruce tree (~100 m distance)",  "tree",  ["tree", "spruce", "vegetation", "daylight"]),
]


def main(baso4_path: str, sky_path: str, tree_path: str, output_file: str) -> None:
    paths = {"baso4": Path(baso4_path), "sky": Path(sky_path), "tree": Path(tree_path)}
    out = Path(output_file)

    records = []
    for mat_key, description, group_id, tags in GROUPS:
        mat = scipy.io.loadmat(str(paths[mat_key]))
        # Matrix key matches the file content key name
        data_key = [k for k in mat.keys() if not k.startswith("_")][0]
        spectra = mat[data_key]  # (171, N): rows=wavelengths, cols=spectra
        assert spectra.shape[0] == N_WAVELENGTHS, f"Unexpected rows: {spectra.shape}"
        n = spectra.shape[1]

        for i in range(n):
            record = {
                "id": f"{group_id}-{i+1:02d}",
                "metadata": {
                    "measurement_type": "radiance",
                    "date": MEASUREMENT_DATE,
                    "title": f"{description} #{i+1}",
                    "operator": "Jussi Parkkinen, Pertti Silfsten",
                    "instrument": INSTRUMENT,
                    "measurement_conditions": MEASUREMENT_CONDITIONS,
                    "tags": tags,
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
                    "values": [round(v, 9) for v in spectra[:, i].tolist()],
                },
                "provenance": {
                    "source_file": paths[mat_key].name,
                    "source_format": f"MATLAB (UEF daylight dataset — {description})",
                    "notes": (
                        "Measurement period: 1995-03-30 to 1995-05-16, Finland (LTKK). "
                        "Various conditions: cloudless, overcast, snowing, and sunset. "
                        "Individual measurement dates/times not available per spectrum. "
                        "Values are spectral radiance from PR-713/702 AM spectroradiometer; "
                        "exact physical units (W/sr/m²/nm) assumed but not confirmed in README."
                    ),
                },
            }
            records.append(record)

    batch = {
        "schema_version": "1.0.0",
        "file_type": "batch",
        "batch_metadata": {
            "title": "UEF Daylight Spectral Measurements",
            "date": MEASUREMENT_DATE,
            "operator": "Jussi Parkkinen, Pertti Silfsten",
            "instrument": INSTRUMENT,
            "measurement_conditions": MEASUREMENT_CONDITIONS,
        },
        "spectra": records,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    print(f"Wrote {out}  ({len(records)} spectra)")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
