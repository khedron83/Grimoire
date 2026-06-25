import React, { useState, useEffect, useRef, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Channel } from "@tauri-apps/api/core";

const COLS = [
  { key: "title", label: "Name", flex: true },
  { key: "version", label: "Installed" },
  { key: "_remote_version", label: "Latest" },
  { key: "author", label: "Author" },
  { key: "_status", label: "Status" },
];

// Strip trailing version strings: "LibAddonMenu-2.0" → "LibAddonMenu", "Foo v1.38" → "Foo"
function stripVersion(name) {
  return name.replace(/\s*[-_]?\s*v?\d+[\d.]*\w*\s*$/i, "").trim() || name;
}

function hasUpdate(addon, remote) {
  if (!remote) return false;
  // Compare ESOUI-to-ESOUI version (stored at install time) — no manifest format mismatch
  if (addon.grimoire_version) return remote.version !== addon.grimoire_version;
  // Fallback: date comparison when we have a sidecar but no version stored
  if (addon.install_date && remote.date) return remote.date > addon.install_date;
  return false;
}

function buildRemoteMap(allAddons) {
  const m = {};
  for (const a of allAddons) {
    for (const dir of a.dirs ?? []) m[dir] = a;
    m[a.name] = a;
  }
  return m;
}

export default function InstalledTab({ config, allAddons, installedMap, setInstalledMap, setStatus }) {
  const [addons, setAddons] = useState([]);
  const [sort, setSort] = useState({ key: "_status", dir: "asc" });
  const [selected, setSelected] = useState(new Set());
  const [focusedIdx, setFocusedIdx] = useState(-1);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [ctxMenu, setCtxMenu] = useState(null); // { x, y, names: Set }
  const tableRef = useRef(null);
  const lastClickIdx = useRef(-1);

  const remoteMap = React.useMemo(() => buildRemoteMap(allAddons), [allAddons]);

  async function refresh() {
    if (!config.addons_dir) { setStatus("AddOns directory not set — check Settings."); return; }
    try {
      const list = await invoke("cmd_scan_installed", { addonsDir: config.addons_dir });
      setAddons(list);
      const m = {};
      for (const a of list) m[a.name] = a;
      setInstalledMap(m);
    } catch (e) {
      setStatus(`Scan error: ${e}`);
    }
  }

  useEffect(() => { if (config.addons_dir) refresh(); }, [config.addons_dir]);

  const displayed = React.useMemo(() => {
    const q = filter.toLowerCase();
    return [...addons].filter(a => !q ||
      (a.title || a.name).toLowerCase().includes(q) ||
      a.author.toLowerCase().includes(q)
    ).sort((a, b) => {
      const ra = remoteMap[a.name], rb = remoteMap[b.name];
      const sa = hasUpdate(a, ra) ? 0 : ra ? 1 : 2;
      const sb = hasUpdate(b, rb) ? 0 : rb ? 1 : 2;
      if (sort.key === "_status") return sort.dir === "asc" ? sa - sb : sb - sa;
      const av = a[sort.key] ?? "", bv = b[sort.key] ?? "";
      return sort.dir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
    });
  }, [addons, remoteMap, sort]);

  function toggleSort(key) {
    setSort(s => s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" });
  }

  function handleRowClick(idx, e) {
    const name = displayed[idx].name;
    setFocusedIdx(idx);
    lastClickIdx.current = idx;
    setSelected(prev => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }

  function handleRowContext(idx, e) {
    e.preventDefault();
    e.stopPropagation();
    const name = displayed[idx].name;
    // If right-clicking an unselected row, select only that row
    const names = selected.has(name) && selected.size > 0 ? new Set(selected) : new Set([name]);
    if (!selected.has(name)) {
      setSelected(names);
      setFocusedIdx(idx);
      lastClickIdx.current = idx;
    }
    setCtxMenu({ x: e.clientX, y: e.clientY, names });
  }

  function handleKeyDown(e) {
    if (!displayed.length) return;
    const idx = focusedIdx < 0 ? 0 : focusedIdx;

    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const next = e.key === "ArrowDown"
        ? Math.min(idx + 1, displayed.length - 1)
        : Math.max(idx - 1, 0);
      setFocusedIdx(next);
      if (e.shiftKey) {
        setSelected(prev => {
          const n = new Set(prev);
          n.add(displayed[next].name);
          return n;
        });
      } else if (!e.ctrlKey) {
        setSelected(new Set([displayed[next].name]));
        lastClickIdx.current = next;
      }
    } else if (e.key === " ") {
      e.preventDefault();
      const name = displayed[idx].name;
      setSelected(prev => {
        const n = new Set(prev);
        n.has(name) ? n.delete(name) : n.add(name);
        return n;
      });
    } else if (e.key === "Escape") {
      setSelected(new Set());
      setCtxMenu(null);
    } else if (e.key === "Delete") {
      if (selected.size) removeAddons(addons.filter(a => selected.has(a.name)));
    } else if (e.key === "a" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      setSelected(new Set(displayed.map(a => a.name)));
    }
  }

  async function removeAddons(toRemove) {
    if (!toRemove.length || !confirm(`Remove ${toRemove.length} addon(s)?`)) return;
    for (const addon of toRemove) {
      try {
        await invoke("cmd_remove_addon", { folderPath: addon.folder_path });
      } catch (e) {
        setStatus(`Remove error: ${e}`);
      }
    }
    setSelected(new Set());
    await refresh();
  }

  const removeSelected = () => removeAddons(addons.filter(a => selected.has(a.name)));

  async function updateAll() {
    const updates = addons.filter(a => hasUpdate(a, remoteMap[a.name]));
    if (!updates.length) { setStatus("All addons are up to date."); return; }
    setBusy(true);
    let count = 0;
    for (const addon of updates) {
      const remote = remoteMap[addon.name];
      if (!remote) continue;
      setStatus(`Updating ${addon.title || addon.name} (${count + 1}/${updates.length})…`);
      const ch = new Channel();
      ch.onmessage = msg => setProgress(msg);
      try {
        await invoke("cmd_install_addon", {
          addon: remote,
          addonsDir: config.addons_dir,
          installedDirs: [],
          onProgress: ch,
        });
        count++;
      } catch (e) {
        setStatus(`Update error for ${addon.name}: ${e}`);
      }
    }
    setBusy(false);
    setProgress("");
    await refresh();
    setStatus(`Updated ${count} of ${updates.length} addon${updates.length !== 1 ? "s" : ""}.`);
  }

  const ctxToRemove = ctxMenu
    ? addons.filter(a => ctxMenu.names.has(a.name))
    : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}
      onContextMenu={e => e.preventDefault()}
      onClick={() => setCtxMenu(null)}>

      {ctxMenu && (
        <div onContextMenu={e => e.preventDefault()}
          style={{
            position: "fixed", left: ctxMenu.x, top: ctxMenu.y,
            background: "var(--bg2)", border: "1px solid var(--border)", color: "var(--text)",
            borderRadius: 4, zIndex: 200, minWidth: 180, boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
            padding: "4px 0",
          }}>
          {ctxToRemove.map(a => (
            <div key={a.name} style={{ padding: "3px 14px", fontSize: 11, color: "var(--text-dim)" }}>
              {stripVersion(a.title || a.name)}
            </div>
          ))}
          <div style={{ borderTop: "1px solid var(--border)", margin: "4px 0" }} />
          <div
            style={{ padding: "6px 14px", cursor: "pointer", fontSize: 12 }}
            onMouseEnter={e => e.currentTarget.style.background = "var(--row-hover)"}
            onMouseLeave={e => e.currentTarget.style.background = ""}
            onClick={e => { e.stopPropagation(); setCtxMenu(null); removeAddons(ctxToRemove); }}>
            Remove{ctxToRemove.length > 1 ? ` (${ctxToRemove.length})` : ""}
          </div>
        </div>
      )}

      <div className="toolbar">
        <button onClick={refresh} disabled={busy}>Refresh</button>
        <button onClick={updateAll} disabled={busy || !allAddons.length}>Update All</button>
        <input type="text" placeholder="Filter…" value={filter}
          onChange={e => setFilter(e.target.value)} style={{ marginLeft: 4 }} />
        <button className="danger" onClick={removeSelected} disabled={!selected.size || busy}>
          Remove{selected.size > 1 ? ` (${selected.size})` : ""}
        </button>
      </div>
      {busy && (
        <>
          <div className="progress-bar indeterminate"><div className="fill" /></div>
          <div style={{ padding: "2px 8px", fontSize: 11, color: "var(--text-dim)" }}>{progress}</div>
        </>
      )}
      <div className="table-wrap" ref={tableRef}
        tabIndex={0} onKeyDown={handleKeyDown}
        style={{ outline: "none" }}>
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
            {displayed.map((addon, idx) => {
              const remote = remoteMap[addon.name];
              const upd = hasUpdate(addon, remote);
              const isSel = selected.has(addon.name);
              const isFocused = focusedIdx === idx;
              return (
                <tr key={addon.name}
                  className={isSel ? "selected" : ""}
                  style={isFocused && !isSel ? { outline: "1px solid var(--accent)", outlineOffset: -1 } : {}}
                  onClick={e => handleRowClick(idx, e)}
                  onContextMenu={e => handleRowContext(idx, e)}>
                  <td className={upd ? "update" : ""}>{addon.title || addon.name}</td>
                  <td>{addon.version || "—"}</td>
                  <td>{remote?.version ?? "—"}</td>
                  <td>{addon.author}</td>
                  <td className={upd ? "update" : ""}>
                    {upd ? "Update available" : remote ? "Up to date" : ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
