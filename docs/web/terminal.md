# Web Terminal

Access at `http://Car-HUD.local:8080/terminal`

A full interactive bash shell accessible from your browser.

## Features

- Real bash PTY (not just command execution)
- Arrow keys, Tab completion, Ctrl+C/D/L
- Quick action buttons for common tasks
- 8KB scrollback buffer
- ANSI escape code stripping

## Quick Buttons

| Button | Command |
|--------|---------|
| Restart HUD | `sudo systemctl restart car-hud` |
| HUD Status | `sudo systemctl status car-hud --no-pager` |
| Logs | `journalctl -u car-hud --no-pager -n 20` |
| htop | `htop -d 20` |
| Disk | `df -h /` |
| Mem | `free -h` |
| Reboot | `sudo reboot` |
| Ctrl+C | Send interrupt signal |
| Clear | `clear` |

## Security Note

!!! warning
    The terminal has **no authentication**. Anyone on your network can execute commands. Only use on trusted networks.
