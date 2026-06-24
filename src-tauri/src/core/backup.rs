use std::cmp::Reverse;
use std::path::Path;
use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct BackupEntry {
    pub name: String,
    pub path: String,
    pub size_mb: f64,
    pub date: String,
}

pub fn create_backup(
    addons_dir: &Path,
    backup_dir: &Path,
    label: &str,
    saved_vars_dir: Option<&Path>,
    on_progress: impl Fn(String),
) -> Result<String, String> {
    std::fs::create_dir_all(backup_dir).map_err(|e| e.to_string())?;
    let ts = chrono::Local::now().format("%Y%m%d_%H%M%S");
    let suffix = if label.is_empty() { String::new() } else { format!("_{}", label) };
    let zip_path = backup_dir.join(format!("grimoire_{}{}.zip", ts, suffix));

    let file = std::fs::File::create(&zip_path).map_err(|e| e.to_string())?;
    let mut zw = zip::ZipWriter::new(file);
    let opts = zip::write::SimpleFileOptions::default()
        .compression_method(zip::CompressionMethod::Deflated)
        .compression_level(Some(6));

    add_dir_to_zip(&mut zw, addons_dir, "AddOns", opts, &on_progress)?;
    if let Some(sv) = saved_vars_dir {
        if sv.exists() {
            add_dir_to_zip(&mut zw, sv, "SavedVariables", opts, &on_progress)?;
        }
    }
    zw.finish().map_err(|e| e.to_string())?;
    Ok(zip_path.to_string_lossy().to_string())
}

fn add_dir_to_zip(
    zw: &mut zip::ZipWriter<std::fs::File>,
    dir: &Path,
    prefix: &str,
    opts: zip::write::SimpleFileOptions,
    on_progress: &impl Fn(String),
) -> Result<(), String> {
    for entry in walkdir::WalkDir::new(dir).sort_by_file_name() {
        let entry = entry.map_err(|e| e.to_string())?;
        let rel = entry.path().strip_prefix(dir).map_err(|e| e.to_string())?;
        let arc_name = format!("{}/{}", prefix, rel.to_string_lossy());
        if entry.path().is_file() {
            on_progress(arc_name.clone());
            zw.start_file(&arc_name, opts).map_err(|e| e.to_string())?;
            let mut f = std::fs::File::open(entry.path()).map_err(|e| e.to_string())?;
            std::io::copy(&mut f, zw).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

pub fn restore_backup(
    zip_path: &Path,
    addons_dir: &Path,
    saved_vars_dir: Option<&Path>,
    on_progress: impl Fn(String),
) -> Result<(), String> {
    let file = std::fs::File::open(zip_path).map_err(|e| e.to_string())?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| e.to_string())?;
    let members: Vec<String> = (0..archive.len())
        .map(|i| archive.by_index(i).map(|e| e.name().to_string()))
        .collect::<Result<_, _>>().map_err(|e| e.to_string())?;

    let structured = members.iter().any(|m| m.starts_with("AddOns/"));

    for i in 0..archive.len() {
        let mut entry = archive.by_index(i).map_err(|e| e.to_string())?;
        let name = entry.name().to_string();
        on_progress(name.clone());

        if structured {
            if let Some(rel) = name.strip_prefix("AddOns/").filter(|r| !r.is_empty()) {
                let dest = addons_dir.join(rel);
                extract_entry(&mut entry, &dest)?;
            } else if let Some(rel) = name.strip_prefix("SavedVariables/").filter(|r| !r.is_empty()) {
                if let Some(sv) = saved_vars_dir {
                    let dest = sv.join(rel);
                    extract_entry(&mut entry, &dest)?;
                }
            }
        } else {
            let dest = addons_dir.join(&name);
            extract_entry(&mut entry, &dest)?;
        }
    }
    Ok(())
}

fn extract_entry(entry: &mut zip::read::ZipFile, dest: &Path) -> Result<(), String> {
    if entry.is_dir() {
        std::fs::create_dir_all(dest).map_err(|e| e.to_string())
    } else {
        if let Some(p) = dest.parent() {
            std::fs::create_dir_all(p).map_err(|e| e.to_string())?;
        }
        let mut f = std::fs::File::create(dest).map_err(|e| e.to_string())?;
        std::io::copy(entry, &mut f).map(|_| ()).map_err(|e| e.to_string())
    }
}

pub fn list_backups(backup_dir: &Path) -> Vec<BackupEntry> {
    if !backup_dir.exists() {
        return vec![];
    }
    let mut entries: Vec<_> = std::fs::read_dir(backup_dir)
        .into_iter()
        .flatten()
        .filter_map(|e| e.ok())
        .filter(|e| {
            e.file_name().to_string_lossy().starts_with("grimoire_")
                && e.path().extension().and_then(|x| x.to_str()) == Some("zip")
        })
        .collect();
    entries.sort_by_key(|e| Reverse(e.metadata().and_then(|m| m.modified()).ok()));

    entries.iter().map(|e| {
        let meta = e.metadata().ok();
        let size_mb = meta.as_ref().map(|m| m.len() as f64 / 1_048_576.0).unwrap_or(0.0);
        let date = meta.as_ref()
            .and_then(|m| m.modified().ok())
            .map(|t| {
                let dt: chrono::DateTime<chrono::Local> = t.into();
                dt.format("%Y-%m-%d %H:%M").to_string()
            })
            .unwrap_or_default();
        BackupEntry {
            name: e.file_name().to_string_lossy().to_string(),
            path: e.path().to_string_lossy().to_string(),
            size_mb,
            date,
        }
    }).collect()
}
