use std::path::Path;
use crate::core::addon::{InstalledAddon, addon_from_disk, write_sidecar};
use crate::core::esoui::{RemoteAddon, AddonDetails, download_zip, fetch_addon_details};

pub async fn install_addon(
    info: &mut RemoteAddon,
    addons_dir: &Path,
    on_progress: impl Fn(String),
) -> Result<Vec<InstalledAddon>, String> {
    if info.download_url.is_empty() {
        let details: AddonDetails = fetch_addon_details(info.addon_id).await?;
        info.download_url = details.download_url;
        info.filename = details.filename;
        info.md5 = details.md5;
        if info.description.is_empty() {
            info.description = details.description;
        }
    }
    if info.download_url.is_empty() {
        return Err(format!("No download URL for {}", info.name));
    }

    let tmp_dir = std::env::temp_dir().join(format!("grimoire-{}", info.addon_id));
    tokio::fs::create_dir_all(&tmp_dir).await.map_err(|e| e.to_string())?;
    let zip_name = if info.filename.is_empty() {
        format!("{}.zip", info.addon_id)
    } else {
        info.filename.clone()
    };
    let zip_path = tmp_dir.join(&zip_name);

    let name = info.name.clone();
    download_zip(&info.download_url, &zip_path, |done, total| {
        on_progress(format!(
            "Downloading {}: {}KB{}",
            name,
            done / 1024,
            if total > 0 { format!(" / {}KB", total / 1024) } else { String::new() }
        ));
    }).await?;

    let folders = extract_zip(&zip_path, addons_dir)?;
    let _ = tokio::fs::remove_dir_all(&tmp_dir).await;

    let mut installed = Vec::new();
    for folder_name in folders {
        let folder = addons_dir.join(&folder_name);
        if folder.is_dir() {
            write_sidecar(&folder, info.addon_id, info.date, &info.version);
            if let Some(mut addon) = addon_from_disk(&folder) {
                addon.addon_id = Some(info.addon_id);
                addon.install_date = info.date;
                addon.grimoire_version = Some(info.version.clone());
                installed.push(addon);
            }
        }
    }
    Ok(installed)
}

fn extract_zip(zip_path: &Path, dest: &Path) -> Result<Vec<String>, String> {
    let file = std::fs::File::open(zip_path).map_err(|e| e.to_string())?;
    let mut archive = zip::ZipArchive::new(file)
        .map_err(|e| format!("Invalid zip ({}): {}", zip_path.display(), e))?;
    let mut tops = std::collections::HashSet::new();

    for i in 0..archive.len() {
        let mut entry = archive.by_index(i).map_err(|e| e.to_string())?;
        let name = entry.name().to_string();
        if let Some(top) = std::path::Path::new(&name).components().next() {
            tops.insert(top.as_os_str().to_string_lossy().to_string());
        }
        let out = dest.join(&name);
        if entry.is_dir() {
            std::fs::create_dir_all(&out).map_err(|e| e.to_string())?;
        } else {
            if let Some(p) = out.parent() {
                std::fs::create_dir_all(p).map_err(|e| e.to_string())?;
            }
            let mut f = std::fs::File::create(&out).map_err(|e| e.to_string())?;
            std::io::copy(&mut entry, &mut f).map_err(|e| e.to_string())?;
        }
    }
    Ok(tops.into_iter().collect())
}

pub fn remove_addon(folder_path: &Path) -> Result<(), String> {
    if folder_path.exists() {
        std::fs::remove_dir_all(folder_path).map_err(|e| e.to_string())?;
    }
    Ok(())
}
