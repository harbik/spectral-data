# Claude Code instructions for spectral-data

## Purpose

`spectral-data` is a public community repository of optical spectral measurements
stored in the [spectral-io](https://crates.io/crates/spectral-io) JSON format.
It is maintained at `~/Projects/spectral-data` and published at
`https://github.com/harbik/spectral-data`.

It has **no Rust library code of its own** — it is a data repository with two
supporting Rust tools in `tools/` and two GitHub Actions workflows in
`.github/workflows/`.

## Relationship with spectral-io

`spectral-data` depends on `spectral-io` (the crate) for parsing and validation,
but `spectral-io` has no knowledge of `spectral-data`.

The `[patch.crates-io]` section has been intentionally **removed** from
`tools/Cargo.toml` so contributors always build against the published crate on
crates.io. When developing locally alongside `spectral-io`, add the patch
temporarily:

```toml
[patch.crates-io]
spectral-io = { path = "../../spectral-io" }
```

Remove the patch and update `Cargo.lock` before committing, so that CI and
contributors resolve the published version.

When `spectral-io` releases a new version that changes public types (field
additions, new enum variants, renamed fields), update the `spectral-io` version
pin in both `tools/validate/Cargo.toml` and `tools/index-gen/Cargo.toml`.

## Repository layout

```text
spectra/           ← all data files, one subfolder per category
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
  Cargo.toml       ← workspace (members: validate, index-gen)
  validate/        ← spectral-validate binary
    Cargo.toml
    src/main.rs
  index-gen/       ← spectral-index-gen binary
    Cargo.toml
    src/main.rs
.github/
  workflows/
    validate.yml   ← runs on every PR that touches spectra/**/*.json
    index.yml      ← runs on push to main; regenerates index.json
  PULL_REQUEST_TEMPLATE.md
index.json         ← auto-generated catalog (do not edit by hand)
CONTRIBUTING.md
README.md
```

## Tools

### spectral-validate

Validates one or more spectral JSON files. Exits with code 1 if any file fails.

```sh
cd tools
cargo build --release -p spectral-validate
./target/release/spectral-validate ../spectra/ceramics/my-sample.json
```

Output per file: `ok  <path> (N spectra)` or `ERR <path>` with the error message.

### spectral-index-gen

Walks a `spectra/` directory, parses every `.json` file, and writes a flat
catalog to `index.json`.

```sh
cd tools
cargo build --release -p spectral-index-gen
./target/release/spectral-index-gen ../spectra/ ../index.json
```

Each entry in the output contains: `path`, `file_type`, `id`, `title`,
`measurement_type`, `wavelength_range_nm`, `n_points`, `date`, `tags`,
`copyright`.

## CI checks before marking work complete

Whenever either tool (`validate/` or `index-gen/`) is modified, run:

```sh
cd tools
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo build --release
```

There are no automated tests for the tools beyond the CI build. Smoke-test
manually against a known-good file in `spectra/` or from `spectral-io`'s test
data.

## GitHub Actions

### validate.yml

Triggered by any PR that adds or modifies files matching `spectra/**/*.json`.

Steps:

1. Check out the repo.
2. Build `spectral-validate` (cached via `Swatinem/rust-cache`).
3. Use `tj-actions/changed-files` to find the changed JSON files.
4. Run `spectral-validate <changed files>`.

The check is red if any file fails validation. Contributors must fix their file;
maintainers should **not** merge a red PR.

### index.yml

Triggered on push to `main` for the same path pattern.

Steps:

1. Check out the repo.
2. Build `spectral-index-gen`.
3. Run `spectral-index-gen spectra/ index.json`.
4. Commit and push the updated `index.json` using `stefanzweifel/git-auto-commit-action`.
   The commit message is `chore: regenerate index.json [skip ci]`.

`index.json` is therefore always up to date on `main` without any manual step.

## Adding data

Place new JSON files under `spectra/<category>/`. Use an existing category or
create a new one (short, lowercase, singular noun). File names should be
lowercase with underscores.

Each file must be a valid `spectral_io::SpectrumFile` — see
[CONTRIBUTING.md](CONTRIBUTING.md) and the
[spectral-io docs](https://docs.rs/spectral-io) for the full schema.

Key rules enforced by `spectral-validate`:

- `schema_version` must be `"1.0.0"`.
- `file_type` must be `"single"` or `"batch"`.
- `measurement_type` must be one of: `reflectance`, `transmittance`,
  `absorbance`, `radiance`, `irradiance`, `emission`, `sensitivity`.
- `date` must be ISO 8601 (`YYYY-MM-DD`).
- `wavelength_axis` must have exactly one of `range_nm` or `values_nm`.
- Wavelengths must be strictly increasing.
- For `reflectance` / `transmittance` with `scale: "fractional"` (default),
  values must lie in `[0, 1]`.
- Number of values must equal the number of wavelength points.

## Copyright and licensing

- Contributed files without a `metadata.copyright` field are implicitly donated
  under CC0 1.0.
- Files from third-party sources (e.g. the Chromaxion Spectral Library) must
  carry the source's copyright notice in `metadata.copyright`.
- Do not commit data you do not have the right to redistribute.

## Bumping the spectral-io version pin

When a new `spectral-io` version is published:

1. Update `spectral-io` version in `tools/validate/Cargo.toml` and
   `tools/index-gen/Cargo.toml`.
2. Run `cargo update --manifest-path tools/Cargo.toml`.
3. Verify both tools still compile: `cargo build --release --manifest-path tools/Cargo.toml`.
4. Commit `tools/Cargo.toml`, `tools/validate/Cargo.toml`,
   `tools/index-gen/Cargo.toml`, and `tools/Cargo.lock`.
