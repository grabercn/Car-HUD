# Voice Commands

Say **"Hey Honda"** to activate, then speak a command.

## Available Commands

### Music
| Command | Action |
|---------|--------|
| "play music" / "resume" | Resume playback |
| "pause" / "stop music" | Pause playback |
| "next song" / "skip" | Next track |
| "previous" / "go back" | Previous track |

### Theme
| Command | Action |
|---------|--------|
| "change to blue/red/green/amber" | Set specific theme |
| "day mode" / "night mode" | Set day or night theme |
| "auto mode" | Auto day/night based on time |

### Display
| Command | Action |
|---------|--------|
| "brightness up" | Increase by 20% |
| "brightness down" | Decrease by 20% |
| "brightness max" | Set to 100% |
| "brightness min" | Set to 10% |

### Widgets
| Command | Action |
|---------|--------|
| "show/enable [name] widget" | Enable a widget |
| "hide/disable [name] widget" | Disable a widget |
| "pin [name] widget" | Pin widget to top |
| "unpin [name] widget" | Unpin widget |

### Camera
| Command | Action |
|---------|--------|
| "show camera" | Open camera view |
| "save clip" | Save dashcam clip |

### System
| Command | Action |
|---------|--------|
| "show help" | Show command list |

## How It Works

1. **Vosk** (offline speech-to-text) listens continuously
2. **Wake word** "Hey Honda" activates command mode
3. Text is processed by `brain.py`:
   - Check learned word corrections (`wordlearn.py`)
   - Try cache (fastest)
   - Try Gemini AI (if online)
   - Fall back to local intent matching (`intent.py`)
4. Command is written to `/tmp/car-hud-voice-signal`
5. HUD reads the signal and executes the action

## Adding Custom Commands

Edit `src/intent.py` — add to the `INTENTS` dict:

```python
"your_command": {
    "action": "your_action",
    "target": "your_target",
    "keywords": {"keyword": 3, "another": 2},  # weight 1-5
    "phrases": ["exact phrase one", "exact phrase two"],
},
```
