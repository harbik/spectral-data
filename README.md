# spectral-data

A community repository of optical spectral measurements in the
[spectral-io](https://crates.io/crates/spectral-io) JSON format.

Every file in `spectra/` is a valid `spectral_io::SpectrumFile` — a compact,
self-describing JSON record that includes the measured spectrum, instrument
metadata, and optional colorimetric context. The format is documented at
[docs.rs/spectral-io](https://docs.rs/spectral-io).

## Browsing the data

`index.json` at the root of this repository is a machine-readable catalog of
every individual spectrum. It is regenerated automatically whenever a file is
merged to `main`.

```json
{
  "schema_version": "1",
  "generated": "2026-05-12",
  "count": 5,
  "spectra": [
    {
      "path": "spectra/ceramics/wallace_china.json",
      "file_type": "batch",
      "id": "Pearl Grey",
      "title": "Pearl Grey",
      "measurement_type": "Reflectance",
      "wavelength_range_nm": [380.0, 730.0],
      "n_points": 36,
      "date": "2002-01-06",
      "copyright": "© Robin D. Myers, all rights reserved worldwide. chromaxion.com"
    }
  ]
}
```

## Reading data in Rust

```toml
[dependencies]
spectral-io = "0.1"
```

```rust
use spectral_io::SpectrumFile;

let file = SpectrumFile::from_path("spectra/ceramics/wallace_china.json")?;
for sp in file.spectra() {
    let (lo, hi) = sp.wavelength_range_nm().unwrap();
    println!("{}: {:.0}–{:.0} nm, {} points", sp.id, lo, hi, sp.n_points());
}
```

## Directory layout

```
spectra/
  candies/
  ceramics/
  charts/
  fabrics/
  filters/
  inks/
  monitors/
  nature/
  paints/
  papers/
tools/
  validate/      ← CI validator binary (Rust)
  index-gen/     ← index.json generator (Rust)
index.json       ← auto-generated catalog
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide. The short version:

1. Fork, add your JSON file under `spectra/<category>/`, open a PR.
2. CI validates the file with the `spectral-validate` tool.
3. After merge, `index.json` is regenerated automatically.

## Licence

Code in `tools/` is MIT OR Apache-2.0.

Individual spectra carry their own copyright notice in `metadata.copyright`.
Files without a copyright notice are donated under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
