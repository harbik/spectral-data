use spectral_io::SpectrumFile;
use std::{path::PathBuf, process};

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.is_empty() {
        eprintln!("usage: spectral-validate <file.json> [file.json ...]");
        process::exit(2);
    }

    let mut had_error = false;

    for arg in &args {
        let path = PathBuf::from(arg);
        match SpectrumFile::from_path(&path) {
            Ok(file) => {
                let n = file.spectra().len();
                println!("ok  {} ({} {})", arg, n, if n == 1 { "spectrum" } else { "spectra" });
            }
            Err(e) => {
                eprintln!("ERR {arg}");
                eprintln!("    {e}");
                had_error = true;
            }
        }
    }

    if had_error {
        process::exit(1);
    }
}
