# Contributing

## Quick Start

1. Clone the repo
2. Make changes in `src/`
3. Push to `main` — docs auto-deploy, OTA updater pulls changes

## Code Style

- **Docstrings:** Google style on all public functions
- **Constants:** Use `config.py` for paths, colors, vehicle specs
- **Error handling:** `except Exception:` (never bare `except:`)
- **Logging:** Use `from config import log` instead of `print()`
- **File I/O:** Use `from config import write_signal, read_signal`

## Testing on Pi

```bash
# Deploy a single file
scp src/yourfile.py pi@Car-HUD.local:~/car-hud/

# Check syntax
python3 -c "compile(open('yourfile.py').read(), 'f', 'exec')"

# Restart the service
sudo systemctl restart car-hud

# Check for errors
journalctl -u car-hud --no-pager -n 20
```

## Documentation

Docs are auto-generated from code docstrings on every push to `main`.

- **Manual pages:** `docs/*.md` — edit directly
- **API reference:** Auto-generated from `src/*.py` docstrings by `docs/gen_ref_pages.py`
- **Widget docs:** Auto-generated from `src/widgets/w_*.py` module docstrings
- **Hosted at:** `https://grabercn.github.io/Car-HUD/`

To preview locally:
```bash
pip install mkdocs-material mkdocstrings[python]
mkdocs serve
```

## Architecture Rules

1. **One service per feature** — don't merge unrelated functionality
2. **JSON files for IPC** — write to `/tmp/car-hud-*`, never use sockets
3. **Auto-discovery** — widgets, cameras, BLE devices should be found automatically
4. **Offline first** — core features must work without internet
5. **Crash resilient** — services restart independently, never take down the HUD
