# Contributing to spectral-data

Thank you for contributing spectral measurements to this community library!
All files in this repository follow the **spectral-io JSON format** (v 1.0.0),
defined by the [`spectral-io`](https://crates.io/crates/spectral-io) Rust crate.

## Quick start

1. Fork this repository and create a branch.
2. Place your JSON file(s) under `spectra/<category>/`.
3. Open a pull request — the CI validator will check your file automatically.
4. Once the check is green and a maintainer approves, the file is merged and
   `index.json` is regenerated automatically.

## File format

Each file must be valid JSON that deserialises as a `spectral_io::SpectrumFile`.
There are two shapes:

### Single spectrum

```json
{
  "schema_version": "1.0.0",
  "file_type": "single",
  "spectrum": {
    "id": "my-sample-01",
    "metadata": {
      "measurement_type": "reflectance",
      "date": "2026-01-15",
      "title": "My Sample"
    },
    "wavelength_axis": {
      "range_nm": { "start": 380.0, "end": 780.0, "interval": 10.0 }
    },
    "spectral_data": {
      "values": [0.05, 0.06, 0.07, "..."]
    }
  }
}
```

### Batch (multiple spectra in one file)

```json
{
  "schema_version": "1.0.0",
  "file_type": "batch",
  "batch_metadata": {
    "title": "My Sample Set",
    "date": "2026-01-15"
  },
  "spectra": [
    { "id": "sample-a", "metadata": { "..." }, "..." },
    { "id": "sample-b", "metadata": { "..." }, "..." }
  ]
}
```

See the [spectral-io documentation](https://docs.rs/spectral-io) for all
available fields and constraints.

## Category folders

Place files under a descriptive subfolder of `spectra/`:

| Folder | Contents |
|---|---|
| `candies/` | Confectionery, food packaging |
| `ceramics/` | Tiles, tableware, porcelain |
| `charts/` | Colour reference charts (Munsell, Macbeth, etc.) |
| `fabrics/` | Textiles, yarns |
| `filters/` | Optical filters, gels |
| `inks/` | Printing inks, toners |
| `monitors/` | Display / monitor emission spectra |
| `nature/` | Leaves, flowers, minerals, sky |
| `paints/` | Paint swatches, automotive finishes |
| `papers/` | Substrates, unprinted papers |

Do not see a category for your material? Create a new subfolder — choose a
short, lowercase, singular noun.

## Required fields

At minimum each `SpectrumRecord` must have:

- `metadata.measurement_type` — one of `reflectance`, `transmittance`,
  `absorbance`, `radiance`, `irradiance`
- `metadata.date` — ISO 8601 (`YYYY-MM-DD`)
- A unique `id` string within the file
- `wavelength_axis` — either `range_nm` (evenly spaced) or `values_nm`
  (irregular)
- `spectral_data.values` — one value per wavelength point

## Attribution and copyright

If your data comes from a third-party source, include a copyright notice in
`metadata.copyright`. You are responsible for ensuring you have permission to
redistribute the data.

Data contributed without a copyright notice is implicitly donated under the
[Creative Commons CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)
public-domain dedication unless you specify a different licence in
`metadata.copyright`.

## Running the validator locally

```sh
cd tools
cargo build --release -p spectral-validate
./target/release/spectral-validate ../spectra/ceramics/my-sample.json
```
