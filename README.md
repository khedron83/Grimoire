# Grimoire

An addon manager for **The Elder Scrolls Online**, built with Python and PySide6. Browse, install, update, and back up your addons directly from [ESOUI.com](https://www.esoui.com) — no browser required.

Works on **Windows**, **Linux**, and **Steam Deck**.

---

## Features

- **Browse** the full ESOUI addon catalogue (~3,000 addons) with live search, category filter, and sortable columns
- **Install** addons in one click — dependencies resolved and installed automatically
- **Update** installed addons — detects newer versions by date or version string
- **Remove** addons cleanly from the AddOns directory
- **Backup & restore** your AddOns folder and optionally your SavedVariables (character data, settings)
- **Auto-detect** your AddOns directory on first launch (Windows, Linux, Steam Deck paths all covered)
- Dark theme designed to match ESO's aesthetic

---

## Requirements

- Python 3.11+
- A working ESO installation (the AddOns directory)

---

## Install & run

```bash
git clone https://github.com/khedron83/Grimoire.git
cd Grimoire
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

### First run

Grimoire will attempt to auto-detect your AddOns directory. If it can't find it, the Settings dialog opens automatically. Set the path to:

| Platform | Default path |
|---|---|
| Windows | `C:\Users\<you>\Documents\Elder Scrolls Online\live\AddOns` |
| Linux (native) | `~/Documents/Elder Scrolls Online/live/AddOns` |
| Steam Deck / Proton | `~/.steam/steam/steamapps/compatdata/306130/pfx/drive_c/users/steamuser/Documents/Elder Scrolls Online/live/AddOns` |

---

## Usage

### Installed tab

Lists every addon currently in your AddOns directory. Addons with available updates are highlighted in amber.

| Button | Action |
|---|---|
| **Refresh** | Rescan the AddOns directory |
| **Update Selected** | Download and install updates for selected addons |
| **Update All** | Update every addon that has a newer version available |
| **Remove** | Delete the selected addon folder |

### Browse tab

Fetches the full addon list from ESOUI on launch (runs in the background).

- **Search** — filter by name, author, or category in real time
- **Category** — filter by addon category (e.g. Unit Frames, Maps, Combat)
- **Sort** — click any column header (Title, Version, Author, Downloads, Updated)
- **Detail panel** — select any addon to see its description, changelog, and install status
- **Install** — installs the addon and all missing dependencies in one step

### Backup tab

- **Create backup** — zip your entire AddOns folder (and optionally SavedVariables) to a chosen location
- **Restore** — extract a previous backup, replacing current files

---

## Building a standalone executable

Requires PyInstaller:

```bash
pip install pyinstaller
pyinstaller eso_addon_manager.spec
```

The output binary will be in `dist/`.

---

## License

This project is licensed under the **GNU General Public License v3.0**. See [LICENSE](LICENSE) for details.

Addon metadata is sourced from [ESOUI.com](https://www.esoui.com) via the MMOUI JSON API.
