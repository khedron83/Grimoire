use serde::{Deserialize, Serialize};
use std::path::PathBuf;

fn config_path() -> PathBuf {
    #[cfg(target_os = "windows")]
    let base = std::env::var("APPDATA").map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(std::env::var("USERPROFILE").unwrap_or_default()));
    #[cfg(not(target_os = "windows"))]
    let base = std::env::var("HOME").map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/tmp"))
        .join(".config");
    base.join("grimoire").join("config.json")
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    pub addons_dir: String,
    pub backup_dir: String,
    pub saved_vars_dir: String,
    pub backup_include_saved_vars: bool,
    pub auto_update_on_launch: bool,
    pub browse_sort_column: String,
    pub browse_sort_order: String,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            addons_dir: String::new(),
            backup_dir: String::new(),
            saved_vars_dir: String::new(),
            backup_include_saved_vars: false,
            auto_update_on_launch: false,
            browse_sort_column: "date".to_string(),
            browse_sort_order: "desc".to_string(),
        }
    }
}

pub fn load() -> Config {
    let path = config_path();
    std::fs::read_to_string(&path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

pub fn save(cfg: &Config) -> Result<(), String> {
    let path = config_path();
    std::fs::create_dir_all(path.parent().unwrap()).map_err(|e| e.to_string())?;
    std::fs::write(&path, serde_json::to_string_pretty(cfg).unwrap()).map_err(|e| e.to_string())
}
