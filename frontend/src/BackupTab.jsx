import React, { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Channel } from "@tauri-apps/api/core";

function backupDir(config) {
  return config.backup_dir || (
    (typeof window !== "undefined" && window.__TAURI__)
      ? null  // will be resolved by Rust default
      : null
  );
}

export default function BackupTab({ config, setStatus }) {
  const [backups, setBackups] = useState([]);
  const [label, setLabel] = useState("");
  const [includeSv, setIncludeSv] = useState(config.backup_include_saved_vars);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");

  const dir = config.backup_dir || (
    // fallback: sibling of addons_dir parent / "grimoire-backups"
    config.addons_dir
      ? config.addons_dir.replace(/[/\\]AddOns$/, "/grimoire-backups")
      : null
  );

  async function refresh() {
    if (!dir) return;
    try {
      const list = await invoke("cmd_list_backups", { backupDir: dir });
      setBackups(list);
    } catch (e) {
      setStatus(`Error listing backups: ${e}`);
    }
  }

  useEffect(() => { refresh(); }, [dir]);

  async function createBackup() {
    if (!config.addons_dir || !dir) { setStatus("AddOns directory not set."); return; }
    setBusy(true);
    const ch = new Channel();
    ch.onmessage = msg => setProgress(msg);
    try {
      const zip = await invoke("cmd_create_backup", {
        addonsDir: config.addons_dir,
        backupDir: dir,
        label: label.trim(),
        savedVarsDir: includeSv && config.saved_vars_dir ? config.saved_vars_dir : null,
        onProgress: ch,
      });
      setLabel("");
      setStatus(`Backup saved: ${zip.split(/[/\\]/).pop()}`);
      refresh();
    } catch (e) {
      setStatus(`Backup error: ${e}`);
    } finally {
      setBusy(false);
      setProgress("");
    }
  }

  async function restore() {
    if (!selected || !config.addons_dir) return;
    if (!confirm(`Restore from ${selected.name}?\nExisting addons will be overwritten.`)) return;
    setBusy(true);
    const ch = new Channel();
    ch.onmessage = msg => setProgress(msg);
    try {
      await invoke("cmd_restore_backup", {
        zipPath: selected.path,
        addonsDir: config.addons_dir,
        savedVarsDir: config.saved_vars_dir || null,
        onProgress: ch,
      });
      setStatus("Restore complete.");
    } catch (e) {
      setStatus(`Restore error: ${e}`);
    } finally {
      setBusy(false);
      setProgress("");
    }
  }

  async function deleteBackup() {
    if (!selected || !confirm(`Delete ${selected.name}?`)) return;
    try {
      await invoke("cmd_delete_backup", { path: selected.path });
      setSelected(null);
      refresh();
    } catch (e) {
      setStatus(`Delete error: ${e}`);
    }
  }

  return (
    <div className="backup-layout">
      <div className="backup-actions">
        <input type="text" placeholder="Optional label (e.g. 'before patch')…"
          value={label} onChange={e => setLabel(e.target.value)} disabled={busy} />
        <label style={{ display: "flex", alignItems: "center", gap: 4, whiteSpace: "nowrap" }}>
          <input type="checkbox" checked={includeSv}
            onChange={e => setIncludeSv(e.target.checked)} />
          Include SavedVariables
        </label>
        <button className="primary" onClick={createBackup} disabled={busy || !config.addons_dir}>
          {busy ? "Working…" : "Create Backup"}
        </button>
      </div>
      {busy && (
        <>
          <div className="progress-bar indeterminate"><div className="fill" /></div>
          <div style={{ padding: "2px 8px", fontSize: 11, color: "var(--text-dim)" }}>{progress}</div>
        </>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th style={{ width: "99%" }}>Filename</th>
              <th>Size</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            {backups.map(b => (
              <tr key={b.path} className={selected?.path === b.path ? "selected" : ""}
                onClick={() => setSelected(s => s?.path === b.path ? null : b)}>
                <td>{b.name}</td>
                <td>{b.size_mb.toFixed(1)} MB</td>
                <td>{b.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="toolbar">
        <button onClick={restore} disabled={!selected || busy}>Restore Selected</button>
        <button className="danger" onClick={deleteBackup} disabled={!selected || busy}>Delete Selected</button>
        <div style={{ flex: 1 }} />
        <button onClick={() => dir && invoke("cmd_open_folder", { path: dir })}>
          Open Backup Folder
        </button>
      </div>
    </div>
  );
}
