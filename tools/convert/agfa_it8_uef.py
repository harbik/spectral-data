#!/usr/bin/env python3
"""
Convert the UEF Agfa IT8.7/2 spectral dataset to a single spectral-io batch JSON file.

Source: https://sites.uef.fi/spectral/agfa-it8-7-2-set/
Measured by Elzbieta Marszalec, University of Oulu, 1994-03-29.
Equipment: Minolta CM-2002 (d/8 geometry, SCE), 400–700 nm at 10 nm (31 points).
289 patches: 264 color (12 rows A-L × 22 cols) + 22 neutral scale + black + white + cal-white.

Values in the source DAT file are in percent (0–100); divided by 100 for fractional [0, 1].

Usage:
    python3 tools/convert/agfa_it8_uef.py <dat_file> <output_file>

Example:
    python3 tools/convert/agfa_it8_uef.py \\
        /tmp/agfa_it8/agfait872.dat \\
        spectra/charts/agfa_it8_7_2.json
"""

import json
import re
import sys
from pathlib import Path

N_PATCHES = 289
N_WAVELENGTHS = 31
WAVELENGTH_START = 400
WAVELENGTH_END = 700
WAVELENGTH_INTERVAL = 10

MEASUREMENT_DATE = "1994-03-29"

COPYRIGHT = (
    "© Elzbieta Marszalec / University of Oulu. "
    "Source: https://sites.uef.fi/spectral/agfa-it8-7-2-set/ "
    "(contact: Markku Hauta-Kasari, University of Eastern Finland)"
)

_HVC_RE = re.compile(r"([\d.]+\s*[A-Z]+)\s+([\d.]+)/([\d.]+)")


def _patch_id(sample_num: int) -> str:
    """Map 1-based sample number to patch label."""
    if 1 <= sample_num <= 264:
        row = chr(ord("A") + (sample_num - 1) // 22)  # A–L
        col = (sample_num - 1) % 22 + 1
        return f"{row}{col:02d}"
    if 265 <= sample_num <= 286:
        return f"N{sample_num - 264:02d}"
    return {287: "BLACK", 288: "WHITE", 289: "CAL-WHITE"}[sample_num]


def _parse_dat(path: Path) -> list[dict]:
    """Parse all 289 sample blocks from the Minolta DAT file."""
    with open(path, encoding="ascii", errors="replace") as f:
        lines = [l.rstrip() for l in f.readlines()]

    # Find header positions
    headers = [i for i, l in enumerate(lines) if l.startswith("No.")]
    assert len(headers) == N_PATCHES, f"Expected {N_PATCHES} headers, got {len(headers)}"

    samples = []
    for h_idx in headers:
        sample_num = int(lines[h_idx][3:])
        block = lines[h_idx + 1 : h_idx + 119]

        # Spectral values: first 31 lines
        reflectances = [float(block[j]) / 100.0 for j in range(N_WAVELENGTHS)]

        # Colorimetry embedded in the block
        xyz = uv = lab = hvc_title = None
        i = N_WAVELENGTHS + 1  # skip the code line + blank
        while i < len(block):
            tag = block[i].strip()
            if tag == "XYZ" and i + 3 < len(block):
                xyz = [float(block[i + 1]), float(block[i + 2]), float(block[i + 3])]
                i += 4
            elif tag == "Yxy" and i + 3 < len(block):
                # Y, x, y
                xy = [float(block[i + 2]), float(block[i + 3])]
                i += 4
            elif tag == "L*a*b*" and i + 3 < len(block):
                lab = [float(block[i + 1]), float(block[i + 2]), float(block[i + 3])]
                i += 4
            elif tag == "HVC" and i + 1 < len(block):
                hvc_raw = block[i + 1].strip()
                m = _HVC_RE.match(hvc_raw)
                if m:
                    hvc_title = f"Munsell {m.group(1).strip()} {m.group(2)}/{m.group(3)}"
                i += 2
            else:
                i += 1

        samples.append({
            "num": sample_num,
            "reflectances": reflectances,
            "xyz": xyz,
            "xy": xy if "xy" in dir() else None,
            "lab": lab,
            "hvc_title": hvc_title,
        })
        # reset xy for next iteration
        xy = None  # noqa: F841

    return samples


def main(dat_path: str, output_file: str) -> None:
    dat = Path(dat_path)
    out = Path(output_file)

    samples = _parse_dat(dat)
    assert len(samples) == N_PATCHES

    records = []
    for s in samples:
        pid = _patch_id(s["num"])
        title = s["hvc_title"] or f"IT8.7/2 patch {pid}"

        record = {
            "id": pid,
            "metadata": {
                "measurement_type": "reflectance",
                "date": MEASUREMENT_DATE,
                "title": title,
                "operator": "Elzbieta Marszalec",
                "instrument": {
                    "manufacturer": "Minolta",
                    "model": "CM-2002",
                },
                "measurement_conditions": {
                    "spectral_resolution_nm": 10.0,
                    "geometry": "d/8",
                    "specular_component": "excluded",
                },
                "tags": ["it8.7/2", "color-target", "calibration", "agfa"],
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
                "values": [round(v, 6) for v in s["reflectances"]],
                "scale": "fractional",
            },
            "provenance": {
                "source_file": dat.name,
                "source_format": "Minolta CM-2002 DAT (UEF Agfa IT8.7/2 dataset)",
                "notes": (
                    "Source values in percent; divided by 100 for fractional scale. "
                    "Patch order: samples 1–264 are color patches A01–L22 "
                    "(12 rows × 22 cols, row-major); 265–286 are neutral scale N01–N22; "
                    "287 = black reference; 288 = white reference; "
                    "289 = Minolta white calibration standard."
                ),
            },
        }

        cs = {}
        if s["xyz"]:
            cs["XYZ"] = [round(v, 6) for v in s["xyz"]]
        if s["xy"]:
            cs["xy"] = [round(v, 6) for v in s["xy"]]
        if s["lab"]:
            cs["Lab"] = [round(v, 6) for v in s["lab"]]
        if cs:
            record["color_science"] = {
                "illuminant": "D65",
                "cie_observer": "CIE 1931 2 degree",
                "results": cs,
            }

        records.append(record)

    batch = {
        "schema_version": "1.0.0",
        "file_type": "batch",
        "batch_metadata": {
            "title": "Agfa IT8.7/2 Color Reference Set",
            "date": MEASUREMENT_DATE,
            "operator": "Elzbieta Marszalec",
            "instrument": {
                "manufacturer": "Minolta",
                "model": "CM-2002",
            },
            "measurement_conditions": {
                "spectral_resolution_nm": 10.0,
                "geometry": "d/8",
                "specular_component": "excluded",
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
