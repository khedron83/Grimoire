import React, { useState, useEffect, useCallback, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Channel } from "@tauri-apps/api/core";

const COLS = [
  { key: "name", label: "Title", flex: true },
  { key: "version", label: "Version" },
  { key: "author", label: "Author" },
  { key: "category", label: "Category" },
  { key: "downloads_total", label: "Downloads", num: true },
  { key: "date", label: "Updated", num: true },
];

function buildRemoteMap(allAddons) {
  const m = {};
  for (const a of allAddons) {
    for (const dir of a.dirs ?? []) m[dir] = a;
    m[a.name] = a;
  }
  return m;
}

function fmtDate(ts) {
  if (!ts) return "";
  return new Date(ts).toISOString().slice(0, 10);
}

function fmtNum(n) {
  return n?.toLocaleString() ?? "0";
}

export default function BrowseTab({ config, allAddons, setAllAddons, installedMap, setInstalledMap, setStatus }) {
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("");
  const [catFilter, setCatFilter] = useState("");
  const [sort, setSort] = useState({ key: "date", dir: "desc" });
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [installing, setInstalling] = useState(false);
  const filterTimer = useRef(null);

  // Load on first mount if not already loaded
  useEffect(() => {
    if (allAddons.length === 0) loadList();
  }, []);

  async function loadList() {
    setLoading(true);
    setStatus("Fetching addon list from MMOUI…");
    try {
      const addons = await invoke("cmd_fetch_all_addons");
      setAllAddons(addons);
      setStatus(`${addons.length} addons loaded`);
    } catch (e) {
      setStatus(`Error: ${e}`);
    } finally {
      setLoading(false);
    }
  }

  // Filtered + sorted list
  const displayed = React.useMemo(() => {
    let list = allAddons;
    if (catFilter) list = list.filter(a => a.category === catFilter);
    if (filter) {
      const q = filter.toLowerCase();
      list = list.filter(a =>
        a.name.toLowerCase().includes(q) ||
        a.author.toLowerCase().includes(q) ||
        a.category.toLowerCase().includes(q)
      );
    }
    const { key, dir } = sort;
    list = [...list].sort((a, b) => {
      const av = a[key] ?? 0, bv = b[key] ?? 0;
      return dir === "asc" ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
    });
    return list;
  }, [allAddons, filter, catFilter, sort]);

  const categories = React.useMemo(() => {
    const s = new Set(allAddons.map(a => a.category).filter(Boolean));
    return Array.from(s).sort();
  }, [allAddons]);

  function toggleSort(key) {
    setSort(s => s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" });
  }

  async function onRowClick(addon) {
    setSelected(addon.addon_id);
    setDetail({ ...addon, _loading: !addon.description });
    if (!addon.description) {
      try {
        const d = await invoke("cmd_fetch_addon_details", { addonId: addon.addon_id });
        addon.description = d.description;
        addon.download_url = d.download_url;
        addon.filename = d.filename;
        addon.md5 = d.md5;
        setDetail({ ...addon, _loading: false });
      } catch (e) {
        setDetail(prev => prev && { ...prev, _loading: false, description: `(Error: ${e})` });
      }
    }
  }

  function installStatus(addon) {
    for (const dir of addon.dirs ?? []) {
      if (installedMap[dir]) return installedMap[dir];
    }
    return installedMap[addon.name] ?? null;
  }

  async function install() {
    if (!detail || !config.addons_dir) return;
    setInstalling(true);
    const ch = new Channel();
    ch.onmessage = msg => setStatus(msg);
    const rMap = buildRemoteMap(allAddons);
    const liveInstalled = { ...installedMap };
    const queue = [detail];
    const seen = new Set([detail.addon_id]);
    const allInstalled = [];
    try {
      while (queue.length) {
        const addon = queue.shift();
        const batch = await invoke("cmd_install_addon", {
          addon,
          addonsDir: config.addons_dir,
          installedDirs: Object.keys(liveInstalled),
          onProgress: ch,
        });
        for (const a of batch) liveInstalled[a.name] = a;
        allInstalled.push(...batch);
        // Resolve deps from manifest and queue any that aren't installed yet
        for (const a of batch) {
          for (const dep of a.depends_on ?? []) {
            const remote = rMap[dep];
            if (remote && !seen.has(remote.addon_id) && !liveInstalled[dep]) {
              seen.add(remote.addon_id);
              queue.push(remote);
            }
          }
        }
      }
      setInstalledMap({ ...installedMap, ...liveInstalled });
      setStatus(`Installed: ${allInstalled.map(a => a.title || a.name).join(", ")}`);
    } catch (e) {
      setStatus(`Install error: ${e}`);
    } finally {
      setInstalling(false);
    }
  }

  const inst = detail ? installStatus(detail) : null;
  const hasUpdate = inst && (inst.grimoire_version
    ? inst.grimoire_version !== detail?.version
    : (inst.install_date && detail?.date && detail.date > inst.install_date));

  return (
    <div className="split">
      <div className="split-left">
        <div className="toolbar">
          <button onClick={loadList} disabled={loading}>
            {loading ? "Loading…" : allAddons.length ? "Refresh" : "Load Addon List"}
          </button>
          <input type="text" placeholder="Filter by name, author, category…"
            disabled={!allAddons.length}
            onChange={e => {
              clearTimeout(filterTimer.current);
              const v = e.target.value;
              filterTimer.current = setTimeout(() => setFilter(v), 250);
            }} />
          <select disabled={!allAddons.length} value={catFilter}
            onChange={e => setCatFilter(e.target.value)}>
            <option value="">All Categories</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        {loading && <div className="progress-bar indeterminate"><div className="fill" /></div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {COLS.map(c => (
                  <th key={c.key} className={sort.key === c.key ? "sorted" : ""}
                    style={c.flex ? { width: "99%" } : {}}
                    onClick={() => toggleSort(c.key)}>
                    {c.label}
                    <span className="sort-arrow">
                      {sort.key === c.key ? (sort.dir === "asc" ? " ▲" : " ▼") : " ↕"}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayed.map(addon => {
                const inst2 = installStatus(addon);
                const upd = inst2 && (inst2.grimoire_version
                  ? inst2.grimoire_version !== addon.version
                  : (inst2.install_date && addon.date && addon.date > inst2.install_date));
                return (
                  <tr key={addon.addon_id}
                    className={selected === addon.addon_id ? "selected" : ""}
                    onClick={() => onRowClick(addon)}>
                    <td className={upd ? "update" : inst2 ? "installed" : ""}>
                      {addon.name}{upd ? "  ↑" : ""}
                    </td>
                    <td>{addon.version}</td>
                    <td>{addon.author}</td>
                    <td>{addon.category}</td>
                    <td>{fmtNum(addon.downloads_total)}</td>
                    <td>{fmtDate(addon.date)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div style={{ padding: "4px 8px", color: "var(--text-dim)", fontSize: 11 }}>
          {allAddons.length > 0 && `${displayed.length}${displayed.length < allAddons.length ? ` / ${allAddons.length}` : ""} addons`}
        </div>
      </div>

      <div className="split-right">
        {detail ? (
          <>
            <div className="detail-title">{detail.name}</div>
            <div className="detail-meta">
              {detail.author && <span>Author: {detail.author}<br /></span>}
              {detail.version && <span>Version: {detail.version}<br /></span>}
              {detail.category && <span>Category: {detail.category}<br /></span>}
              {detail.downloads_total > 0 && <span>{fmtNum(detail.downloads_total)} total / {fmtNum(detail.downloads_monthly)} monthly<br /></span>}
              {detail.date > 0 && <span>Updated: {fmtDate(detail.date)}</span>}
            </div>
            <div className="detail-desc">
              {detail._loading ? "Loading…" : (detail.description || "(No description)")}
            </div>
            <button className="primary" disabled={installing || (!hasUpdate && !!inst)}
              onClick={install}>
              {installing ? "Installing…"
                : hasUpdate ? `Update to ${detail.version}`
                : inst ? "Installed"
                : "Install"}
            </button>
          </>
        ) : (
          <div style={{ color: "var(--text-dim)", marginTop: 20, textAlign: "center" }}>
            Select an addon to see details
          </div>
        )}
      </div>
    </div>
  );
}
