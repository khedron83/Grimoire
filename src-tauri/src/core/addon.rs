use regex::Regex;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

const SIDECAR: &str = ".grimoire.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InstalledAddon {
    pub addon_id: Option<u32>,
    pub name: String,
    pub title: String,
    pub version: String,
    pub author: String,
    pub description: String,
    pub depends_on: Vec<String>,
    pub folder_path: String,
    pub install_date: i64,
}

#[derive(Debug, Deserialize)]
struct Sidecar {
    addon_id: Option<u32>,
    install_date: Option<i64>,
}

fn parse_manifest(path: &Path) -> std::collections::HashMap<String, String> {
    let text = match std::fs::read_to_string(path) {
        Ok(t) => t,
        Err(_) => return Default::default(),
    };
    let re = Regex::new(r"(?m)^##\s*(\w+)\s*:\s*(.+)$").unwrap();
    re.captures_iter(&text)
        .map(|c| (c[1].to_string(), c[2].trim().to_string()))
        .collect()
}

fn parse_deps(raw: &str) -> Vec<String> {
    let ver_re = Regex::new(r"[><=]+.*").unwrap();
    raw.split(|c: char| c.is_whitespace() || c == ',')
        .filter(|s| !s.is_empty())
        .map(|s| ver_re.replace(s, "").to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

fn clean_eso_codes(s: &str) -> String {
    let re = Regex::new(r"\|[cC][0-9a-fA-F]{1,6}|\|r|\|t[^|]*(?:\|t)?").unwrap();
    re.replace_all(s, "").trim().to_string()
}

pub fn addon_from_disk(folder: &Path) -> Option<InstalledAddon> {
    let manifests: Vec<_> = {
        let mut v: Vec<PathBuf> = std::fs::read_dir(folder).ok()?
            .filter_map(|e| e.ok())
            .map(|e| e.path())
            .filter(|p| {
                let ext = p.extension().and_then(|e| e.to_str()).unwrap_or("");
                ext == "addon" || ext == "txt"
            })
            .collect();
        v.sort();
        v
    };
    if manifests.is_empty() {
        return None;
    }

    let folder_name = folder.file_name()?.to_str()?;
    let manifest_path = manifests.iter()
        .find(|p| p.file_stem().and_then(|s| s.to_str()).map(|s| s.eq_ignore_ascii_case(folder_name)).unwrap_or(false))
        .unwrap_or(&manifests[0]);

    let meta = parse_manifest(manifest_path);

    let mut deps: Vec<String> = parse_deps(meta.get("DependsOn").map(|s| s.as_str()).unwrap_or(""));
    deps.extend(parse_deps(meta.get("PCDependsOn").map(|s| s.as_str()).unwrap_or("")));
    deps.dedup();

    let sidecar: Option<Sidecar> = std::fs::read_to_string(folder.join(SIDECAR))
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok());

    let title = clean_eso_codes(meta.get("Title").map(|s| s.as_str()).unwrap_or(folder_name));

    Some(InstalledAddon {
        addon_id: sidecar.as_ref().and_then(|s| s.addon_id),
        name: folder_name.to_string(),
        title: if title.is_empty() { folder_name.to_string() } else { title },
        version: meta.get("Version").or_else(|| meta.get("AddOnVersion")).cloned().unwrap_or_default(),
        author: clean_eso_codes(meta.get("Author").map(|s| s.as_str()).unwrap_or("")),
        description: meta.get("Description").cloned().unwrap_or_default(),
        depends_on: deps,
        folder_path: folder.to_string_lossy().to_string(),
        install_date: sidecar.as_ref().and_then(|s| s.install_date).unwrap_or(0),
    })
}

pub fn write_sidecar(folder: &Path, addon_id: u32, install_date: i64) {
    let _ = std::fs::write(
        folder.join(SIDECAR),
        serde_json::json!({"addon_id": addon_id, "install_date": install_date}).to_string(),
    );
}

pub fn scan_addons_dir(addons_dir: &Path) -> Result<Vec<InstalledAddon>, String> {
    let mut entries: Vec<_> = std::fs::read_dir(addons_dir)
        .map_err(|e| e.to_string())?
        .filter_map(|e| e.ok())
        .filter(|e| e.path().is_dir())
        .collect();
    entries.sort_by_key(|e| e.file_name());

    Ok(entries.iter()
        .filter_map(|e| addon_from_disk(&e.path()))
        .collect())
}
