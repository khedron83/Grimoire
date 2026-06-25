mod core;

use std::collections::HashSet;
use std::path::{Path, PathBuf};
use tauri::ipc::Channel;

use core::addon::{scan_addons_dir, InstalledAddon};
use core::backup::{BackupEntry, create_backup, list_backups, restore_backup};
use core::config::{Config, load as load_config, save as save_config};
use core::esoui::{AddonDetails, RemoteAddon, fetch_all_addons, fetch_addon_details};
use core::installer::{install_addon, remove_addon};
use core::paths::{detect_addons_dir, detect_saved_vars_dir};

// ── Config ────────────────────────────────────────────────────────────────────

#[tauri::command]
fn get_config() -> Config {
    load_config()
}

#[tauri::command]
fn cmd_save_config(config: Config) -> Result<(), String> {
    save_config(&config)
}

#[tauri::command]
fn cmd_detect_addons_dir() -> Option<String> {
    detect_addons_dir()
}

#[tauri::command]
fn cmd_detect_saved_vars_dir(addons_dir: String) -> Option<String> {
    detect_saved_vars_dir(if addons_dir.is_empty() { None } else { Some(&addons_dir) })
}

// ── Remote addon list ─────────────────────────────────────────────────────────

#[tauri::command]
async fn cmd_fetch_all_addons() -> Result<Vec<RemoteAddon>, String> {
    fetch_all_addons().await
}

#[tauri::command]
async fn cmd_fetch_addon_details(addon_id: u32) -> Result<AddonDetails, String> {
    fetch_addon_details(addon_id).await
}

// ── Installed addons ──────────────────────────────────────────────────────────

#[tauri::command]
fn cmd_scan_installed(addons_dir: String) -> Result<Vec<InstalledAddon>, String> {
    scan_addons_dir(Path::new(&addons_dir))
}

#[tauri::command]
async fn cmd_install_addon(
    addon: RemoteAddon,
    addons_dir: String,
    installed_dirs: Vec<String>,
    on_progress: Channel<String>,
) -> Result<Vec<InstalledAddon>, String> {
    let installed_set: HashSet<String> = installed_dirs.into_iter().collect();
    let mut all_installed = Vec::new();
    let mut queue = vec![addon.clone()];
    let mut seen: HashSet<u32> = HashSet::new();
    let mut live_installed = installed_set.clone();

    while let Some(mut remote) = queue.pop() {
        if seen.contains(&remote.addon_id) {
            continue;
        }
        if !remote.dirs.is_empty() && remote.dirs.iter().all(|d| live_installed.contains(d)) {
            seen.insert(remote.addon_id);
            continue;
        }
        seen.insert(remote.addon_id);

        let _ = on_progress.send(format!("Installing {}…", remote.name));
        let batch = install_addon(&mut remote, Path::new(&addons_dir), |msg| {
            let _ = on_progress.send(msg);
        }).await?;

        for a in &batch {
            live_installed.insert(a.name.clone());
        }
        all_installed.extend(batch);
    }
    Ok(all_installed)
}

#[tauri::command]
fn cmd_remove_addon(folder_path: String) -> Result<(), String> {
    remove_addon(Path::new(&folder_path))
}

// ── Backup ────────────────────────────────────────────────────────────────────

#[tauri::command]
fn cmd_list_backups(backup_dir: String) -> Vec<BackupEntry> {
    list_backups(Path::new(&backup_dir))
}

#[tauri::command]
fn cmd_create_backup(
    addons_dir: String,
    backup_dir: String,
    label: String,
    saved_vars_dir: Option<String>,
    on_progress: Channel<String>,
) -> Result<String, String> {
    create_backup(
        Path::new(&addons_dir),
        Path::new(&backup_dir),
        &label,
        saved_vars_dir.as_deref().filter(|s| !s.is_empty()).map(Path::new),
        |msg| { let _ = on_progress.send(msg); },
    )
}

#[tauri::command]
fn cmd_restore_backup(
    zip_path: String,
    addons_dir: String,
    saved_vars_dir: Option<String>,
    on_progress: Channel<String>,
) -> Result<(), String> {
    restore_backup(
        Path::new(&zip_path),
        Path::new(&addons_dir),
        saved_vars_dir.as_deref().filter(|s| !s.is_empty()).map(Path::new),
        |msg| { let _ = on_progress.send(msg); },
    )
}

#[tauri::command]
fn cmd_delete_backup(path: String) -> Result<(), String> {
    std::fs::remove_file(Path::new(&path)).map_err(|e| e.to_string())
}

#[tauri::command]
fn cmd_open_folder(path: String) -> Result<(), String> {
    let p = PathBuf::from(&path);
    std::fs::create_dir_all(&p).map_err(|e| e.to_string())?;
    #[cfg(target_os = "windows")]
    std::process::Command::new("explorer").arg(&p).spawn().map_err(|e| e.to_string())?;
    #[cfg(target_os = "linux")]
    std::process::Command::new("xdg-open").arg(&p).spawn().map_err(|e| e.to_string())?;
    #[cfg(target_os = "macos")]
    std::process::Command::new("open").arg(&p).spawn().map_err(|e| e.to_string())?;
    Ok(())
}

// ── Update check ─────────────────────────────────────────────────────────────

#[tauri::command]
async fn cmd_check_update(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let client = reqwest::Client::new();
    let Ok(resp) = client
        .get("https://api.github.com/repos/khedron83/Grimoire/releases/latest")
        .header("User-Agent", "Grimoire")
        .send().await else { return Ok(None) };
    let Ok(json) = resp.json::<serde_json::Value>().await else { return Ok(None) };
    let tag = json["tag_name"].as_str().unwrap_or("");
    let latest = tag.trim_start_matches('v');
    let current = app.package_info().version.to_string();
    if !latest.is_empty() && semver_gt(latest, &current) {
        Ok(Some(tag.to_string()))
    } else {
        Ok(None)
    }
}

fn semver_gt(a: &str, b: &str) -> bool {
    let parse = |s: &str| s.splitn(3, '.').map(|p| p.parse::<u32>().unwrap_or(0)).collect::<Vec<_>>();
    parse(a) > parse(b)
}

#[tauri::command]
fn cmd_open_url(url: String) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    std::process::Command::new("cmd").args(["/C", "start", "", &url]).spawn().map_err(|e| e.to_string())?;
    #[cfg(target_os = "linux")]
    std::process::Command::new("xdg-open").arg(&url).spawn().map_err(|e| e.to_string())?;
    #[cfg(target_os = "macos")]
    std::process::Command::new("open").arg(&url).spawn().map_err(|e| e.to_string())?;
    Ok(())
}

// ── Dialog helper ─────────────────────────────────────────────────────────────

#[tauri::command]
async fn cmd_pick_folder(app: tauri::AppHandle) -> Option<String> {
    use tauri_plugin_dialog::DialogExt;
    app.dialog()
        .file()
        .blocking_pick_folder()
        .map(|p| p.to_string())
}

// ── App setup ─────────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // WebKit2GTK DMA buffer renderer causes white screens / GPU failures on many
    // Linux systems (AppImage, bare binary). Must be set before WebKit init.
    #[cfg(target_os = "linux")]
    std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            get_config,
            cmd_save_config,
            cmd_detect_addons_dir,
            cmd_detect_saved_vars_dir,
            cmd_fetch_all_addons,
            cmd_fetch_addon_details,
            cmd_scan_installed,
            cmd_install_addon,
            cmd_remove_addon,
            cmd_list_backups,
            cmd_create_backup,
            cmd_restore_backup,
            cmd_delete_backup,
            cmd_open_folder,
            cmd_pick_folder,
            cmd_check_update,
            cmd_open_url,
        ])
        .run(tauri::generate_context!())
        .expect("error running grimoire");
}
