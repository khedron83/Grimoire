import React, { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import BrowseTab from "./BrowseTab.jsx";
import InstalledTab from "./InstalledTab.jsx";
import BackupTab from "./BackupTab.jsx";
import Settings from "./Settings.jsx";

export default function App() {
  const [tab, setTab] = useState("installed");
  const [config, setConfig] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [status, setStatus] = useState("");
  // Shared state for cross-tab coordination
  const [allAddons, setAllAddons] = useState([]);          // Vec<RemoteAddon>
  const [installedMap, setInstalledMap] = useState({});    // name -> InstalledAddon
  const [updateTag, setUpdateTag] = useState(null);

  useEffect(() => {
    invoke("cmd_check_update").then(tag => { if (tag) setUpdateTag(tag); }).catch(() => {});
  }, []);

  useEffect(() => {
    invoke("get_config").then(cfg => {
      setConfig(cfg);
      if (!cfg.addons_dir) {
        invoke("cmd_detect_addons_dir").then(dir => {
          if (dir) {
            const updated = { ...cfg, addons_dir: dir };
            invoke("cmd_save_config", { config: updated });
            setConfig(updated);
            setStatus(`Auto-detected AddOns at ${dir}`);
          } else {
            setShowSettings(true);
            setStatus("AddOns directory not found — open Settings.");
          }
        });
      }
    });
  }, []);

  const saveConfig = async (cfg) => {
    await invoke("cmd_save_config", { config: cfg });
    setConfig(cfg);
  };

  if (!config) return <div className="loading">Loading…</div>;

  return (
    <div className="app">
      {updateTag && (
        <div className="update-banner">
          Update available: {updateTag}
          <button onClick={() => invoke("cmd_open_url", { url: "https://github.com/khedron83/Grimoire/releases/latest" })}>Download</button>
          <button onClick={() => setUpdateTag(null)}>✕</button>
        </div>
      )}
      <div className="tabs-bar">
        {["installed", "browse", "backup"].map(t => (
          <button key={t} className={`tab-btn${tab === t ? " active" : ""}`}
            onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button className="tab-btn" onClick={() => setShowSettings(true)}>Settings</button>
      </div>

      <div className="tab-content">
        <div style={{ display: tab === "installed" ? "contents" : "none" }}>
          <InstalledTab config={config} allAddons={allAddons} active={tab === "installed"}
            installedMap={installedMap} setInstalledMap={setInstalledMap}
            setStatus={setStatus} />
        </div>
        <div style={{ display: tab === "browse" ? "contents" : "none" }}>
          <BrowseTab config={config} allAddons={allAddons} setAllAddons={setAllAddons}
            installedMap={installedMap} setInstalledMap={setInstalledMap}
            setStatus={setStatus} />
        </div>
        <div style={{ display: tab === "backup" ? "contents" : "none" }}>
          <BackupTab config={config} setStatus={setStatus} />
        </div>
      </div>

      <div className="status-bar">{status || " "}</div>

      {showSettings && (
        <Settings config={config} onSave={cfg => { saveConfig(cfg); setShowSettings(false); }}
          onClose={() => setShowSettings(false)} />
      )}
    </div>
  );
}
