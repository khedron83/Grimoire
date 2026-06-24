use std::path::{Path, PathBuf};

const ESO_STEAM_APP_ID: &str = "306130";
const PROTON_ADDONS_REL: &str = "pfx/drive_c/users/steamuser/Documents/Elder Scrolls Online/live/AddOns";

fn home() -> PathBuf {
    std::env::var("HOME").or_else(|_| std::env::var("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/"))
}

fn steam_library_paths() -> Vec<PathBuf> {
    let base = home().join(".local/share/Steam");
    let mut libs = vec![base.clone()];
    let vdf = base.join("steamapps/libraryfolders.vdf");
    if let Ok(text) = std::fs::read_to_string(&vdf) {
        let re = regex::Regex::new(r#""path"\s+"([^"]+)""#).unwrap();
        for cap in re.captures_iter(&text) {
            libs.push(PathBuf::from(&cap[1]));
        }
    }
    libs
}

fn find_proton_addons() -> Option<PathBuf> {
    for lib in steam_library_paths() {
        let compat = lib.join("steamapps/compatdata").join(ESO_STEAM_APP_ID);
        if compat.exists() {
            return Some(compat.join(PROTON_ADDONS_REL));
        }
    }
    None
}

pub fn detect_addons_dir() -> Option<String> {
    #[cfg(target_os = "windows")]
    {
        let docs = home().join("Documents");
        return Some(docs.join("Elder Scrolls Online/live/AddOns").to_string_lossy().to_string());
    }
    #[cfg(not(target_os = "windows"))]
    {
        if let Some(p) = find_proton_addons() {
            return Some(p.to_string_lossy().to_string());
        }
        let native = home().join("Documents/Elder Scrolls Online/live/AddOns");
        if native.exists() {
            return Some(native.to_string_lossy().to_string());
        }
        None
    }
}

pub fn detect_saved_vars_dir(addons_dir: Option<&str>) -> Option<String> {
    let base = if let Some(d) = addons_dir.filter(|s| !s.is_empty()) {
        Path::new(d).parent()?.to_path_buf()
    } else {
        let detected = detect_addons_dir()?;
        Path::new(&detected).parent()?.to_path_buf()
    };
    Some(base.join("SavedVariables").to_string_lossy().to_string())
}
