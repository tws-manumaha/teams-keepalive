# Contributing to Teams Keep-Alive

Thank you for your interest in contributing! This document covers the basics.

## How to contribute

### Report bugs

1. Check existing [Issues](https://github.com/tws-manumaha/teams-keepalive/issues) to avoid duplicates.
2. Open a new issue using the **Bug Report** template.
3. Include your OS, Python version, and the log file from `~/.teams_keepalive/keepalive.log`.

### Suggest features

1. Open a new issue using the **Feature Request** template.
2. Describe the use case and expected behavior.

### Submit code

1. Fork the repository.
2. Create a feature branch:
   ```bash
   git checkout -b feature/my-feature
   ```
3. Make your changes. Keep them in `teams_keepalive.py` unless adding a new file is justified.
4. Test on your platform:
   ```bash
   python -m py_compile teams_keepalive.py
   python teams_keepalive.py
   ```
5. Commit with a clear message:
   ```bash
   git commit -m "feat: add XYZ feature"
   ```
   Use conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`.
6. Push and open a Pull Request against `main`.

## Code style

- Python 3.8+ compatible.
- ASCII-only in `.py` files (no em-dashes, no emoji in code). Tray menu labels may use unicode.
- Type hints where practical.
- Keep the single-file architecture for `teams_keepalive.py`.
- Comments and docstrings in English.

## Testing

Before submitting a PR:

```bash
# Syntax check
python -m py_compile teams_keepalive.py
python -m py_compile generate_icon.py

# Functional test
python generate_icon.py
python teams_keepalive.py
```

If you add new logic, test it:

```bash
python -c "
from teams_keepalive import Config
c = Config('/tmp/test_config.json')
c.set('interval', 120)
print(c.get('interval'))
"
```

## Architecture notes

- **Single file**: `teams_keepalive.py` is the entire app. Do not split it unless there is a compelling reason.
- **Flat tray menu**: pystray's `Menu()` takes variadic `*args` of `MenuItem`. Do NOT use submenus (they crash on Python 3.14). Use `Menu(*items)` with list unpacking.
- **tkinter in separate thread**: The settings GUI must run in `threading.Thread`, never in the pystray callback thread.
- **Windows ctypes**: On Windows, input simulation uses `ctypes.windll.user32` (keybd_event + SetCursorPos). No pynput needed.
- **Config**: Settings persist to `~/.teams_keepalive/config.json`.

## Release process

1. Update `CHANGELOG.md`.
2. Tag the release: `git tag v2.0.0`.
3. Push tags: `git push --tags`.
4. GitHub Actions builds binaries and creates a Release.

## License

By contributing, you agree that your contributions are licensed under the MIT License.
