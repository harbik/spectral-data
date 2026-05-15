use serde::{Deserialize, Serialize};
use spectral_io::SpectrumFile;
use std::{path::PathBuf, process};
use walkdir::WalkDir;

#[derive(Serialize, Deserialize)]
struct IndexEntry {
    path: String,
    file_type: String,
    id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    title: Option<String>,
    measurement_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    wavelength_range_nm: Option<[f64; 2]>,
    n_points: usize,
    date: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    tags: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    copyright: Option<String>,
}

#[derive(Serialize, Deserialize)]
struct Index {
    schema_version: &'static str,
    generated: String,
    count: usize,
    spectra: Vec<IndexEntry>,
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (spectra_dir, output_path) = match args.as_slice() {
        [d, o] => (PathBuf::from(d), PathBuf::from(o)),
        [d] => (PathBuf::from(d), PathBuf::from("index.json")),
        _ => {
            eprintln!("usage: spectral-index-gen <spectra-dir> [output.json]");
            process::exit(2);
        }
    };

    let mut entries: Vec<IndexEntry> = Vec::new();
    let mut had_error = false;

    for entry in WalkDir::new(&spectra_dir)
        .sort_by_file_name()
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.path().extension().is_some_and(|x| x == "json"))
    {
        let path = entry.path();
        let rel_path = path
            .strip_prefix(spectra_dir.parent().unwrap_or(&spectra_dir))
            .unwrap_or(path)
            .to_string_lossy()
            .replace('\\', "/");

        match SpectrumFile::from_path(path) {
            Ok(file) => {
                let file_type = if file.spectra().len() == 1 {
                    "single"
                } else {
                    "batch"
                };
                for sp in file.spectra() {
                    let range = sp.wavelength_range_nm().map(|(a, b)| [a, b]);
                    entries.push(IndexEntry {
                        path: rel_path.clone(),
                        file_type: file_type.to_string(),
                        id: sp.id.clone(),
                        title: sp.metadata.title.clone(),
                        measurement_type: format!("{:?}", sp.metadata.measurement_type),
                        wavelength_range_nm: range,
                        n_points: sp.n_points(),
                        date: sp.metadata.date.clone(),
                        tags: sp.metadata.tags.clone(),
                        copyright: sp.metadata.copyright.clone(),
                    });
                }
            }
            Err(e) => {
                eprintln!("ERR {rel_path}: {e}");
                had_error = true;
            }
        }
    }

    let index = Index {
        schema_version: "1",
        generated: chrono_today(),
        count: entries.len(),
        spectra: entries,
    };

    match serde_json::to_string_pretty(&index) {
        Ok(json) => {
            if let Err(e) = std::fs::write(&output_path, json + "\n") {
                eprintln!("could not write {}: {e}", output_path.display());
                process::exit(1);
            }
            println!("wrote {} ({} entries)", output_path.display(), index.count);
        }
        Err(e) => {
            eprintln!("serialisation error: {e}");
            process::exit(1);
        }
    }

    if had_error {
        process::exit(1);
    }
}

fn chrono_today() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let days = secs / 86400;
    let mut y = 1970u32;
    let mut remaining = days;
    loop {
        let days_in_year = if is_leap(y) { 366 } else { 365 };
        if remaining < days_in_year {
            break;
        }
        remaining -= days_in_year;
        y += 1;
    }
    let month_days: [u64; 12] = [
        31,
        if is_leap(y) { 29 } else { 28 },
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ];
    let mut m = 0u32;
    for (i, &md) in month_days.iter().enumerate() {
        if remaining < md {
            m = i as u32 + 1;
            break;
        }
        remaining -= md;
    }
    let d = remaining + 1;
    format!("{y:04}-{m:02}-{d:02}")
}

fn is_leap(y: u32) -> bool {
    (y % 4 == 0 && y % 100 != 0) || y % 400 == 0
}
