import React, { useState } from "react";
import { invoke } from "@tauri-apps/api/core";

async function pickDir() {
  try {
    return await invoke("cmd_pick_folder");
  } catch {
    return null;
  }
}

export default function Settings({ config, onSave, onClose }) {
  const [form, setForm] = useState({ ...config });

  function set(key, val) { setForm(f => ({ ...f, [key]: val })); }

  async function autoDetect() {
    const dir = await invoke("cmd_detect_addons_dir");
    if (dir) set("addons_dir", dir);
  }

  async function autoDetectSv() {
    const dir = await invoke("cmd_detect_saved_vars_dir", { addonsDir: form.addons_dir });
    if (dir) set("saved_vars_dir", dir);
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h2>Settings</h2>

        <div className="form-row">
          <label>AddOns directory</label>
          <div className="row-input">
            <input type="text" value={form.addons_dir}
              onChange={e => set("addons_dir", e.target.value)}
              placeholder="Path to ESO AddOns folder…" />
            <button onClick={async () => { const d = await pickDir(); if (d) set("addons_dir", d); }}>Browse…</button>
            <button onClick={autoDetect}>Auto-detect</button>
          </div>
        </div>

        <div className="form-row">
          <label>SavedVariables directory</label>
          <div className="row-input">
            <input type="text" value={form.saved_vars_dir}
              onChange={e => set("saved_vars_dir", e.target.value)}
              placeholder="Path to ESO SavedVariables folder (optional)…" />
            <button onClick={async () => { const d = await pickDir(); if (d) set("saved_vars_dir", d); }}>Browse…</button>
            <button onClick={autoDetectSv}>Auto-detect</button>
          </div>
        </div>

        <div className="form-row">
          <label>Backup directory</label>
          <div className="row-input">
            <input type="text" value={form.backup_dir}
              onChange={e => set("backup_dir", e.target.value)}
              placeholder="Where to save backups…" />
            <button onClick={async () => { const d = await pickDir(); if (d) set("backup_dir", d); }}>Browse…</button>
          </div>
        </div>

        <div className="form-row">
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={form.backup_include_saved_vars}
              onChange={e => set("backup_include_saved_vars", e.target.checked)} />
            Include SavedVariables in backups by default
          </label>
        </div>

        <div className="form-row">
          <label>Browse default sort</label>
          <div className="row-input">
            <select value={form.browse_sort_column}
              onChange={e => set("browse_sort_column", e.target.value)}>
              {[["name","Title"],["version","Version"],["author","Author"],
                ["category","Category"],["downloads_total","Downloads"],["date","Updated"]]
                .map(([v,l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <select value={form.browse_sort_order}
              onChange={e => set("browse_sort_order", e.target.value)}>
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </div>
        </div>

        <div className="form-row">
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={form.auto_update_on_launch}
              onChange={e => set("auto_update_on_launch", e.target.checked)} />
            Check for updates on launch
          </label>
        </div>

        <div className="modal-footer">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" onClick={() => onSave(form)}>Save</button>
        </div>
      </div>
    </div>
  );
}
