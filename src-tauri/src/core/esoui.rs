use once_cell::sync::Lazy;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tokio::sync::OnceCell;

static CLIENT: Lazy<reqwest::Client> = Lazy::new(|| {
    reqwest::Client::builder()
        .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        .gzip(true)
        .build()
        .unwrap()
});

#[derive(Debug, Clone)]
struct ApiUrls {
    file_list: String,
    file_details: String,
    category_list: String,
}

static API_URLS: OnceCell<ApiUrls> = OnceCell::const_new();

async fn get_urls() -> Result<&'static ApiUrls, String> {
    API_URLS
        .get_or_try_init(|| async {
            let gc: serde_json::Value = CLIENT
                .get("https://api.mmoui.com/v3/globalconfig.json")
                .timeout(std::time::Duration::from_secs(15))
                .send()
                .await
                .map_err(|e| e.to_string())?
                .json()
                .await
                .map_err(|e| e.to_string())?;

            let eso = gc["GAMES"]
                .as_array()
                .and_then(|g| g.iter().find(|x| x["GameID"] == "ESO"))
                .ok_or("ESO not found in MMOUI global config")?;

            let game_cfg: serde_json::Value = CLIENT
                .get(eso["GameConfig"].as_str().ok_or("missing GameConfig")?)
                .timeout(std::time::Duration::from_secs(15))
                .send()
                .await
                .map_err(|e| e.to_string())?
                .json()
                .await
                .map_err(|e| e.to_string())?;

            let feeds = &game_cfg["APIFeeds"];
            Ok(ApiUrls {
                file_list: feeds["FileList"].as_str().ok_or("missing FileList")?.to_string(),
                file_details: feeds["FileDetails"].as_str().ok_or("missing FileDetails")?.to_string(),
                category_list: feeds["CategoryList"].as_str().ok_or("missing CategoryList")?.to_string(),
            })
        })
        .await
        .map_err(|e: String| e)
}

fn to_str_vec(v: &serde_json::Value) -> Vec<String> {
    match v {
        serde_json::Value::Array(a) => a.iter().filter_map(|x| x.as_str()).filter(|s| !s.is_empty()).map(String::from).collect(),
        serde_json::Value::String(s) if !s.is_empty() => vec![s.clone()],
        _ => vec![],
    }
}

fn strip_bbcode(s: &str) -> String {
    let re = regex::Regex::new(r"\[/?[A-Za-z][^\]]*\]").unwrap();
    re.replace_all(s, "").trim().to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RemoteAddon {
    pub addon_id: u32,
    pub name: String,
    pub version: String,
    pub date: i64,
    pub author: String,
    pub description: String,
    pub changelog: String,
    pub category_id: u32,
    pub category: String,
    pub downloads_total: u32,
    pub downloads_monthly: u32,
    pub favorites: u32,
    pub info_url: String,
    pub download_url: String,
    pub filename: String,
    pub dirs: Vec<String>,
    pub md5: String,
}

pub async fn fetch_all_addons() -> Result<Vec<RemoteAddon>, String> {
    let urls = get_urls().await?;

    let cats_raw: Vec<serde_json::Value> = CLIENT
        .get(&urls.category_list)
        .timeout(std::time::Duration::from_secs(15))
        .send()
        .await
        .map_err(|e| e.to_string())?
        .json()
        .await
        .map_err(|e| e.to_string())?;

    let cats: HashMap<u64, String> = cats_raw.iter().filter_map(|c| {
        let id = c["UICATID"].as_str()?.parse::<u64>().ok()?;
        let name = c["UICATTitle"].as_str()?.to_string();
        Some((id, name))
    }).collect();

    let list: Vec<serde_json::Value> = CLIENT
        .get(&urls.file_list)
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
        .map_err(|e| e.to_string())?
        .json()
        .await
        .map_err(|e| e.to_string())?;

    Ok(list.iter().map(|raw| {
        let cat_id = raw["UICATID"].as_str().and_then(|s| s.parse::<u32>().ok()).unwrap_or(0);
        RemoteAddon {
            addon_id: raw["UID"].as_str().and_then(|s| s.parse().ok()).unwrap_or(0),
            name: raw["UIName"].as_str().unwrap_or("").to_string(),
            version: raw["UIVersion"].as_str().unwrap_or("").to_string(),
            date: raw["UIDate"].as_str().and_then(|s| s.parse().ok()).unwrap_or(0),
            author: raw["UIAuthorName"].as_str().unwrap_or("").to_string(),
            description: String::new(),
            changelog: String::new(),
            category_id: cat_id,
            category: cats.get(&(cat_id as u64)).cloned().unwrap_or_default(),
            downloads_total: raw["UIDownloadTotal"].as_str().and_then(|s| s.parse().ok()).unwrap_or(0),
            downloads_monthly: raw["UIDownloadMonthly"].as_str().and_then(|s| s.parse().ok()).unwrap_or(0),
            favorites: raw["UIFavoriteTotal"].as_str().and_then(|s| s.parse().ok()).unwrap_or(0),
            info_url: raw["UIFileInfoURL"].as_str().unwrap_or("").to_string(),
            download_url: String::new(),
            filename: String::new(),
            dirs: to_str_vec(&raw["UIDir"]),
            md5: String::new(),
        }
    }).collect())
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AddonDetails {
    pub download_url: String,
    pub filename: String,
    pub md5: String,
    pub description: String,
    pub changelog: String,
}

pub async fn fetch_addon_details(addon_id: u32) -> Result<AddonDetails, String> {
    let urls = get_urls().await?;
    let url = format!("{}{}.json", urls.file_details, addon_id);
    let raw: serde_json::Value = CLIENT
        .get(&url)
        .timeout(std::time::Duration::from_secs(15))
        .send()
        .await
        .map_err(|e| e.to_string())?
        .json()
        .await
        .map_err(|e| e.to_string())?;

    let data = if raw.is_array() { raw[0].clone() } else { raw };
    Ok(AddonDetails {
        download_url: data["UIDownload"].as_str().unwrap_or("").to_string(),
        filename: data["UIFileName"].as_str().unwrap_or("").to_string(),
        md5: data["UIMD5"].as_str().unwrap_or("").to_string(),
        description: strip_bbcode(data["UIDescription"].as_str().unwrap_or("")),
        changelog: strip_bbcode(data["UIChangeLog"].as_str().unwrap_or("")),
    })
}

pub async fn download_zip(
    url: &str,
    dest: &std::path::Path,
    on_progress: impl Fn(u64, u64),
) -> Result<(), String> {
    use tokio::io::AsyncWriteExt;
    let mut resp = CLIENT
        .get(url)
        .timeout(std::time::Duration::from_secs(120))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let total = resp.content_length().unwrap_or(0);
    let mut file = tokio::fs::File::create(dest).await.map_err(|e| e.to_string())?;
    let mut done = 0u64;

    while let Some(chunk) = resp.chunk().await.map_err(|e| e.to_string())? {
        file.write_all(&chunk).await.map_err(|e| e.to_string())?;
        done += chunk.len() as u64;
        on_progress(done, total);
    }
    Ok(())
}
