# Grimoire

An addon manager for **The Elder Scrolls Online**, built with [Tauri](https://tauri.app) (Rust + React). Browse, install, and back up your addons directly from [ESOUI.com](https://www.esoui.com) — no browser required.

Works on **Windows**, **Linux**, and **Steam Deck**.

---

## Features

- **Browse** the full ESOUI addon catalogue (~3,000 addons) with live search, category filter, and sortable columns
- **Install** addons in one click with live progress
- **Remove** addons cleanly from the AddOns directory
- **Backup & restore** your AddOns folder and optionally your SavedVariables (character data, settings)
- **Auto-detect** your AddOns directory on first launch (Windows, Linux, Steam Deck/Proton paths all covered)
- **Update notifications** — checks GitHub on launch and shows a banner if a new version is available
- Dark theme designed to match ESO's aesthetic

---

## Install

Download the latest release from the [Releases page](https://github.com/khedron83/Grimoire/releases/latest):

| Platform | File |
|---|---|
| Linux (deb) | `grimoire_*.deb` |
| Linux (AppImage) | `grimoire_*.AppImage` |
| Linux (Flatpak) | `grimoire.flatpak` |
| Windows | `Grimoire_*_x64-setup.exe` |

### First run

Grimoire will attempt to auto-detect your AddOns directory. If it can't find it, Settings opens automatically. Set the path to:

| Platform | Default path |
|---|---|
| Windows | `C:\Users\<you>\Documents\Elder Scrolls Online\live\AddOns` |
| Linux (native) | `~/Documents/Elder Scrolls Online/live/AddOns` |
| Steam Deck / Proton | `~/.steam/steam/steamapps/compatdata/306130/pfx/drive_c/users/steamuser/Documents/Elder Scrolls Online/live/AddOns` |

---

## Usage

### Installed tab

Lists every addon currently in your AddOns directory.

- Click to select (Ctrl+A selects all)
- Right-click or press Delete to remove
- Right-click → Open folder to inspect files

### Browse tab

Fetches the full addon list from ESOUI on launch.

- **Search** — filter by name, author, or category in real time
- **Sort** — click any column header
- **Detail panel** — select an addon to see its description and install status
- **Install** — downloads and installs in one step with a live progress log

### Backup tab

- **Create backup** — zips your AddOns folder (and optionally SavedVariables) with a label and timestamp
- **Restore** — extracts a previous backup, replacing current files
- **Delete** — removes old backup archives

---

## Building from source

```bash
# Prerequisites: Rust, Node 22, and system WebKit deps (Linux)
# Linux: sudo apt install libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf libgtk-3-dev

git clone https://github.com/khedron83/Grimoire.git
cd Grimoire
npm install
npm run tauri build
```

---

## License

This project is licensed under the **GNU General Public License v3.0**. See [LICENSE](LICENSE) for details.

Addon metadata is sourced from [ESOUI.com](https://www.esoui.com) via the MMOUI JSON API.
