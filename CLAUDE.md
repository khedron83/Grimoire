# Grimoire — dev notes

## Version bumps

When bumping the version, update **all three** of these:

1. `pyproject.toml` — `version = "x.y.z"`
2. `src/ui/workers.py` — `APP_VERSION = "x.y.z"`
3. The About dialog in `src/ui/main_window.py` reads `APP_VERSION` automatically — no change needed there.

After committing, tag and push:
```bash
git tag vX.Y.Z && git push origin master && git push origin vX.Y.Z
```
CI will build and publish the release automatically.
