#!/usr/bin/env python3
"""
Convert the UEF forest reflectance dataset to spectral-io JSON batch files.

Source: https://sites.uef.fi/spectral/forest-colors/
Measured by Raimo Silvennoinen (Vaisala Lab, University of Joensuu), June 1992.
Equipment: Photo Research PR-713/702 AM spectroradiometer.
390–850 nm at 5 nm (93 points). Reflectance spectra.
1056 spectra: Scots pine (370), Norway spruce (349), birch (337).

A small number of values exceed 1.0 due to measurement noise and calibration
artefacts (~0.08% of all values); these are clipped to 1.0.

Reference: Jaaskelainen et al., Applied Optics, Vol. 33(12), 1994.

Usage:
    python3 tools/convert/forest_uef.py <spruce_mat> <birch_mat> <pine_mat> <output_dir>

Example:
    python3 tools/convert/forest_uef.py \\
        /tmp/forest_uef/spruce.mat \\
        /tmp/forest_uef/birch.mat \\
        /tmp/forest_uef/pine.mat \\
        spectra/nature/
"""

import json
import sys
from pathlib import Path

import numpy as np
import scipy.io

N_WAVELENGTHS = 93
WAVELENGTH_START = 390
WAVELENGTH_END = 850
WAVELENGTH_INTERVAL = 5

MEASUREMENT_DATE = "1992-06-01"

COPYRIGHT = (
    "© University of Eastern Finland (UEF) / Raimo Silvennoinen. "
    "Non-commercial use only. "
    "Source: https://sites.uef.fi/spectral/forest-colors/"
)

INSTRUMENT = {
    "manufacturer": "Photo Research",
    "model": "PR-713/702 AM",
}

GROUPS = [
    ("spruce", "Norway spruce needle",  ["norway-spruce", "Picea abies",   "needle", "vegetation", "forest"]),
    ("birch",  "Birch leaf",            ["birch", "Betula",                 "leaf",   "vegetation", "forest"]),
    ("pine",   "Scots pine needle",     ["scots-pine", "Pinus sylvestris",  "needle", "vegetation", "forest"]),
]


def main(spruce_path: str, birch_path: str, pine_path: str, output_dir: str) -> None:
    paths = {
        "spruce": Path(spruce_path),
        "birch":  Path(birch_path),
        "pine":   Path(pine_path),
    }
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    total = 0
    for species, description, tags in GROUPS:
        mat = scipy.io.loadmat(str(paths[species]))
        data = mat[species]   # (93, N)
        assert data.shape[0] == N_WAVELENGTHS

        n = data.shape[1]
        clipped = int((data > 1.0).sum())

        records = []
        for i in range(n):
            vals = np.clip(data[:, i], 0.0, 1.0).tolist()
            record = {
                "id": f"{species}-{i+1:03d}",
                "metadata": {
                    "measurement_type": "reflectance",
                    "date": MEASUREMENT_DATE,
                    "title": f"{description} #{i+1}",
                    "operator": "Raimo Silvennoinen",
                    "instrument": INSTRUMENT,
                    "measurement_conditions": {
                        "spectral_resolution_nm": 5.0,
                    },
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
                    "values": [round(v, 7) for v in vals],
                    "scale": "fractional",
                },
                "provenance": {
                    "source_file": paths[species].name,
                    "source_format": f"MATLAB (UEF forest dataset — {species})",
                    "notes": (
                        "Each spectrum is the average reflectance of thousands of needles/leaves "
                        "from a single growing tree, measured in Finland and Sweden, June 1992 "
                        "(clear weather, growing season). "
                        f"{clipped} source value(s) across all {n} {species} spectra exceeded 1.0 "
                        "(instrument noise/calibration artefacts) and were clipped to 1.0."
                    ),
                },
            }
            records.append(record)

        batch = {
            "schema_version": "1.0.0",
            "file_type": "batch",
            "batch_metadata": {
                "title": f"UEF Forest Reflectance — {description}s",
                "date": MEASUREMENT_DATE,
                "operator": "Raimo Silvennoinen",
                "instrument": INSTRUMENT,
                "measurement_conditions": {
                    "spectral_resolution_nm": 5.0,
                },
            },
            "spectra": records,
        }

        out_file = out / f"uef_forest_{species}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(batch, f, indent=2, ensure_ascii=False)

        print(f"  wrote {out_file}  ({n} spectra, {clipped} values clipped)")
        total += n

    print(f"\nTotal: {total} spectra")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
