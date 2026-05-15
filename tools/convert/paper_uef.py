#!/usr/bin/env python3
"""
Convert the UEF paper reflectance dataset to spectral-io batch JSON files.

Source: https://sites.uef.fi/spectral/paper-spectra/
Measured by Jouni Haanpalo, ca. October 1994.
Equipment: Minolta CM-2002, d/8 geometry, 400–700 nm at 10 nm (31 points).

3 material types × 2 specular modes:
  Newsprint (18 samples): SCI → 3 meas/sample = 54; SCE → 2 meas/sample = 36
  Paper     (72 samples): SCI → 3 meas/sample = 216; SCE → 2 meas/sample = 144
  Cardboard (70 samples): SCI → 3 meas/sample = 210; SCE → 2 meas/sample = 140

SCI measurements: calibrated against a first-surface mirror (3 per sample:
  single sheet on black background, single sheet on white background, opaque pile).
SCE measurements: calibrated against manufacturer white plastic reference (2 per
  sample: single sheet on black background, single sheet on white background).
Mirror calibration: 3 spectra in mirrorsci.mat.

Values are in percent (0–100); divided by 100 for fractional scale. A small
number of SCI values exceed 100% (highly reflective white samples); these are
clipped to 1.0 after dividing.

Usage:
    python3 tools/convert/paper_uef.py <mat_dir> <output_dir>

Example:
    python3 tools/convert/paper_uef.py \\
        /tmp/paper_uef/ \\
        spectra/papers/
"""

import json
import sys
from pathlib import Path

import numpy as np
import scipy.io

N_WAVELENGTHS = 31
WAVELENGTH_START = 400
WAVELENGTH_END = 700
WAVELENGTH_INTERVAL = 10

MEASUREMENT_DATE = "1994-10-10"

COPYRIGHT = (
    "© University of Eastern Finland (UEF) / Jouni Haanpalo. "
    "Non-commercial use only. "
    "Source: https://sites.uef.fi/spectral/paper-spectra/"
)

INSTRUMENT = {
    "manufacturer": "Minolta",
    "model": "CM-2002",
}

# SCI measurements have 3 per sample: black-background, white-background, opaque-pile
SCI_CONDITION_LABELS = ["black-background", "white-background", "opaque-pile"]
# SCE measurements have 2 per sample: black-background, white-background
SCE_CONDITION_LABELS = ["black-background", "white-background"]

# (material_id, material_label, n_samples, sci_key, sce_key)
MATERIALS = [
    ("newsprint", "Newsprint",  18, "newsprintsci", "newsprintsce"),
    ("paper",     "Paper",      72, "papersci",     "papersce"),
    ("cardboard", "Cardboard",  70, "cardboardsci", "cardboardsce"),
]


def _load_pct(mat_dir, key):
    """Load a MATLAB file and return reflectance in percent as (31, N) array."""
    mat = scipy.io.loadmat(str(Path(mat_dir) / f"{key}.mat"))
    data = mat[key]
    assert data.shape[0] == N_WAVELENGTHS
    return data


def _make_records(data, n_samples, meas_per_sample, condition_labels,
                  material_id, material_label, specular_mode, specular_label,
                  mat_key, n_clipped_ref):
    """Build SpectrumRecord dicts from a (31, N) percent-scale array."""
    assert data.shape[1] == n_samples * meas_per_sample, (
        f"{mat_key}: expected {n_samples * meas_per_sample} columns, got {data.shape[1]}"
    )

    n_clipped = int(((data / 100.0) > 1.0).sum())
    n_clipped_ref[0] += n_clipped

    records = []
    for s in range(n_samples):
        for m in range(meas_per_sample):
            col = s * meas_per_sample + m
            vals = np.clip(data[:, col] / 100.0, 0.0, 1.0).tolist()
            cond_label = condition_labels[m]
            sample_num = s + 1
            record = {
                "id": f"{material_id}-{specular_mode}-{sample_num:03d}-{cond_label}",
                "metadata": {
                    "measurement_type": "reflectance",
                    "date": MEASUREMENT_DATE,
                    "title": (
                        f"{material_label} sample {sample_num} "
                        f"({specular_label}, {cond_label.replace('-', ' ')})"
                    ),
                    "operator": "Jouni Haanpalo",
                    "instrument": INSTRUMENT,
                    "measurement_conditions": {
                        "spectral_resolution_nm": 10.0,
                        "geometry": "d/8",
                        "specular_component": specular_label,
                        "background": cond_label,
                    },
                    "tags": [
                        "paper", material_id, specular_mode,
                        cond_label, "color-sample",
                    ],
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
                    "values": [round(v, 6) for v in vals],
                    "scale": "fractional",
                },
                "provenance": {
                    "source_file": f"{mat_key}.mat",
                    "source_format": "MATLAB (UEF paper dataset)",
                    "notes": (
                        "Source values in percent; divided by 100 for fractional scale. "
                        f"{n_clipped} value(s) in this group exceeded 100% "
                        "(highly reflective samples measured SCI against mirror) "
                        "and were clipped to 1.0."
                    ),
                },
            }
            records.append(record)
    return records


def main(mat_dir, output_dir):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    total = 0
    for material_id, material_label, n_samples, sci_key, sce_key in MATERIALS:
        sci_data = _load_pct(mat_dir, sci_key)
        sce_data = _load_pct(mat_dir, sce_key)

        n_clipped = [0]
        sci_records = _make_records(
            sci_data, n_samples, 3, SCI_CONDITION_LABELS,
            material_id, material_label,
            "sci", "included", sci_key, n_clipped,
        )
        sce_records = _make_records(
            sce_data, n_samples, 2, SCE_CONDITION_LABELS,
            material_id, material_label,
            "sce", "excluded", sce_key, n_clipped,
        )

        records = sci_records + sce_records
        batch = {
            "schema_version": "1.0.0",
            "file_type": "batch",
            "batch_metadata": {
                "title": f"UEF Paper Reflectance — {material_label}",
                "date": MEASUREMENT_DATE,
                "operator": "Jouni Haanpalo",
                "instrument": INSTRUMENT,
                "measurement_conditions": {
                    "spectral_resolution_nm": 10.0,
                    "geometry": "d/8",
                },
            },
            "spectra": records,
        }

        out_path = out / f"uef_paper_{material_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(batch, f, indent=2, ensure_ascii=False)
        print(
            f"  wrote {out_path}  "
            f"({len(records)} spectra [{len(sci_records)} SCI + {len(sce_records)} SCE], "
            f"{n_clipped[0]} values clipped)"
        )
        total += len(records)

    # Mirror calibration
    mirror_data = _load_pct(mat_dir, "mirrorsci")
    n_mirror = mirror_data.shape[1]
    mirror_n_clipped = [0]
    mirror_records = []
    for i in range(n_mirror):
        vals = np.clip(mirror_data[:, i] / 100.0, 0.0, 1.0).tolist()
        mirror_records.append({
            "id": f"mirror-sci-{i+1:02d}",
            "metadata": {
                "measurement_type": "reflectance",
                "date": MEASUREMENT_DATE,
                "title": f"First-surface mirror calibration reference #{i+1}",
                "operator": "Jouni Haanpalo",
                "instrument": INSTRUMENT,
                "measurement_conditions": {
                    "spectral_resolution_nm": 10.0,
                    "geometry": "d/8",
                    "specular_component": "included",
                },
                "tags": ["paper", "mirror", "calibration", "sci"],
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
                "values": [round(v, 6) for v in vals],
                "scale": "fractional",
            },
            "provenance": {
                "source_file": "mirrorsci.mat",
                "source_format": "MATLAB (UEF paper dataset)",
                "notes": (
                    "Calibration spectra measured from a first-surface mirror "
                    "used as SCI reference. Source values in percent; divided by 100."
                ),
            },
        })

    mirror_batch = {
        "schema_version": "1.0.0",
        "file_type": "batch",
        "batch_metadata": {
            "title": "UEF Paper Dataset — Mirror Calibration Reference",
            "date": MEASUREMENT_DATE,
            "operator": "Jouni Haanpalo",
            "instrument": INSTRUMENT,
            "measurement_conditions": {
                "spectral_resolution_nm": 10.0,
                "geometry": "d/8",
                "specular_component": "included",
            },
        },
        "spectra": mirror_records,
    }
    mirror_path = out / "uef_paper_mirror.json"
    with open(mirror_path, "w", encoding="utf-8") as f:
        json.dump(mirror_batch, f, indent=2, ensure_ascii=False)
    print(f"  wrote {mirror_path}  ({n_mirror} spectra)")
    total += n_mirror

    print(f"\nTotal: {total} spectra")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
