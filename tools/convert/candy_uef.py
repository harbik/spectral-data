#!/usr/bin/env python3
"""
Convert the UEF candy dye absorbance dataset to a single spectral-io batch JSON file.

Source: https://sites.uef.fi/spectral/candy-colors/
Measured by Jouni Haanpalo, University of Eastern Finland, ca. 1994-10-11.
Equipment: Hewlett Packard 8452A Diode Array Spectrophotometer.
190–820 nm at 2 nm (316 points). Absorbance units.
21 spectra: 9 individual EU food dyes + 1 mixture (E100+E141), each at 5 µl/10 ml and
20 µl/10 ml H₂O, plus one blank (pure water).

The MATLAB file contains absorbance spectra normalised against the pure-water blank.

Usage:
    python3 tools/convert/candy_uef.py <mat_file> <output_file>

Example:
    python3 tools/convert/candy_uef.py \\
        /tmp/candy_uef/candy_matlab.mat \\
        spectra/candies/uef_dyes.json
"""

import json
import sys
from pathlib import Path

import numpy as np
import scipy.io

N_SPECTRA = 21
N_WAVELENGTHS = 316
WAVELENGTH_START = 190
WAVELENGTH_END = 820
WAVELENGTH_INTERVAL = 2

MEASUREMENT_DATE = "1994-10-11"

COPYRIGHT = (
    "© University of Eastern Finland (UEF) / Jouni Haanpalo. "
    "Non-commercial use only. "
    "Source: https://sites.uef.fi/spectral/candy-colors/"
)

# EU food dye E-number → common name
DYE_NAMES = {
    "E100": "Curcumin",
    "E120": "Carmine (Cochineal)",
    "E131": "Patent Blue V",
    "E132": "Indigotine",
    "E141": "Copper chlorophyllin",
    "E160a": "Beta-carotene",
    "E160e": "Beta-apo-8'-carotenic acid ethyl ester",
    "E162": "Betanin (Beetroot Red)",
    "E163": "Anthocyanins",
    "E100E141": "E100 + E141 mixture (Curcumin + Copper chlorophyllin)",
}


def _parse_label(raw: str):
    """Return (id, title, concentration_ul) from label like 'E163_5' or 'blank'."""
    if raw == "blank":
        return "blank", "Pure water (blank reference)", None

    if "_" in raw:
        dye_code, conc_str = raw.rsplit("_", 1)
        conc = int(conc_str)
    else:
        dye_code, conc = raw, None

    name = DYE_NAMES.get(dye_code, dye_code)
    conc_label = f"{conc} µl / 10 ml H₂O" if conc else ""
    title = f"{dye_code} – {name}" + (f" ({conc_label})" if conc_label else "")
    chip_id = raw.replace("_", "-")
    return chip_id, title, conc


def main(mat_path: str, output_file: str) -> None:
    mat_p = Path(mat_path)
    out = Path(output_file)

    mat = scipy.io.loadmat(str(mat_p))

    # candy: (316, 21), absorbance values normalised against pure-water blank
    spectra = mat["candy"]  # keep as (316, 21); col per spectrum
    assert spectra.shape == (N_WAVELENGTHS, N_SPECTRA), f"Unexpected shape: {spectra.shape}"

    labels = [str(s).strip() for s in mat["S"]]
    assert len(labels) == N_SPECTRA

    records = []
    for i, raw_label in enumerate(labels):
        chip_id, title, conc = _parse_label(raw_label)
        values = spectra[:, i].tolist()

        metadata: dict = {
            "measurement_type": "absorbance",
            "date": MEASUREMENT_DATE,
            "title": title,
            "operator": "Jouni Haanpalo",
            "instrument": {
                "manufacturer": "Hewlett-Packard",
                "model": "8452A Diode Array",
            },
            "measurement_conditions": {
                "spectral_resolution_nm": 2.0,
            },
            "tags": ["candy", "food-dye", "eu-e-number", "absorbance", "solution"],
            "copyright": COPYRIGHT,
        }
        if conc is not None:
            metadata["custom"] = {
                "concentration_ul_per_10ml_H2O": conc,
                "solvent": "H2O",
            }

        record = {
            "id": chip_id,
            "metadata": metadata,
            "wavelength_axis": {
                "range_nm": {
                    "start": WAVELENGTH_START,
                    "end": WAVELENGTH_END,
                    "interval": WAVELENGTH_INTERVAL,
                }
            },
            "spectral_data": {
                "values": [round(v, 7) for v in values],
            },
            "provenance": {
                "source_file": mat_p.name,
                "source_format": "MATLAB (UEF candy dye dataset)",
                "notes": (
                    "Absorbance spectra normalised against pure-water blank (blank.wav). "
                    "Small negative values are instrument noise. "
                    "Source .wav files contain raw transmittance from HP 8452A; "
                    "MATLAB file contains pre-computed normalised absorbance."
                ),
            },
        }
        records.append(record)

    batch = {
        "schema_version": "1.0.0",
        "file_type": "batch",
        "batch_metadata": {
            "title": "UEF Candy Dye Absorbance Spectra",
            "date": MEASUREMENT_DATE,
            "operator": "Jouni Haanpalo",
            "instrument": {
                "manufacturer": "Hewlett-Packard",
                "model": "8452A Diode Array",
            },
            "measurement_conditions": {
                "spectral_resolution_nm": 2.0,
            },
        },
        "spectra": records,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    print(f"Wrote {out}  ({len(records)} spectra)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
