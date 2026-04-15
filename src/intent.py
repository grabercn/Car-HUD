"""Smart intent matcher for voice commands.
No LLM needed — uses weighted keyword scoring with synonyms.
Handles natural phrasing like a mini NLU engine.
"""

# Each intent has weighted keywords and phrases
# Higher weight = stronger signal for that intent
INTENTS = {
    "show_camera": {
        "action": "show", "target": "camera",
        "keywords": {
            "camera": 3, "cam": 3, "rear": 2, "back": 1, "behind": 2,
            "reverse": 2, "parking": 2, "park": 1, "view": 1, "see": 1,
            "look": 1, "dash": 1, "dashcam": 3, "record": 1, "video": 1,
        },
        "phrases": ["show camera", "pull up camera", "rear view", "what's behind",
                     "show me behind", "parking camera", "back camera", "dash cam",
                     "start recording", "show video"],
    },
    "show_music": {
        "action": "show", "target": "music",
        "keywords": {
            "music": 3, "song": 2, "track": 2, "spotify": 3, "playing": 2,
            "artist": 2, "album": 1, "audio": 1, "listen": 1, "play": 1,
            "pause": 2, "skip": 2, "next": 1, "previous": 1,
        },
        "phrases": ["show music", "what's playing", "now playing", "current song",
                     "show spotify", "music player", "play music", "next song",
                     "skip song", "pause music"],
    },
    "show_map": {
        "action": "show", "target": "map",
        "keywords": {
            "map": 3, "navigation": 3, "navigate": 3, "directions": 2,
            "gps": 3, "route": 2, "where": 1, "location": 1, "drive": 1,
            "go": 1, "destination": 2, "compass": 2,
        },
        "phrases": ["show map", "open navigation", "where am i", "show gps",
                     "get directions", "navigate to", "show route"],
    },
    "show_system": {
        "action": "show", "target": "system",
        "keywords": {
            "system": 3, "status": 2, "info": 2, "diagnostics": 2,
            "temperature": 2, "temp": 2, "cpu": 2, "memory": 2, "ram": 2,
            "storage": 1, "health": 1, "performance": 1,
        },
        "phrases": ["show system", "system status", "system info",
                     "how's the system", "show diagnostics", "cpu temperature"],
    },
    "show_home": {
        "action": "show", "target": "home",
        "keywords": {
            "home": 3, "main": 3, "dashboard": 3, "default": 2,
            "back": 1, "return": 1, "close": 1, "exit": 1, "go back": 2,
        },
        "phrases": ["go home", "show home", "main screen", "go back",
                     "show dashboard", "default screen", "close this"],
    },
    "show_vehicle": {
        "action": "show", "target": "vehicle",
        "keywords": {
            "vehicle": 3, "car": 2, "engine": 2, "obd": 3, "speed": 2,
            "rpm": 3, "fuel": 2, "gas": 2, "coolant": 2, "throttle": 2,
            "diagnostic": 2, "check engine": 3, "oil": 1,
        },
        "phrases": ["show vehicle", "car info", "engine status", "check engine",
                     "how much gas", "fuel level", "show speed", "show rpm"],
    },
    "theme_blue": {
        "action": "theme", "target": "blue",
        "keywords": {"blue": 3, "cyan": 2, "default": 1, "color blue": 3},
        "phrases": ["color blue", "change to blue", "blue theme", "make it blue"],
    },
    "theme_red": {
        "action": "theme", "target": "red",
        "keywords": {"red": 3, "sport": 2, "color red": 3},
        "phrases": ["color red", "change to red", "red theme", "sport mode",
                     "make it red"],
    },
    "theme_green": {
        "action": "theme", "target": "green",
        "keywords": {"green": 3, "eco": 2, "color green": 3},
        "phrases": ["color green", "change to green", "green theme", "eco mode",
                     "make it green"],
    },
    "theme_amber": {
        "action": "theme", "target": "amber",
        "keywords": {"amber": 3, "orange": 3, "warm": 1, "color amber": 3,
                     "color orange": 3},
        "phrases": ["color amber", "color orange", "change to amber",
                     "amber theme", "make it orange"],
    },
    "theme_day": {
        "action": "theme", "target": "day",
        "keywords": {"day": 2, "light": 2, "bright": 2, "white": 2, "daytime": 3},
        "phrases": ["day mode", "light mode", "bright mode", "daytime mode",
                     "make it bright", "make it light"],
    },
    "theme_night": {
        "action": "theme", "target": "night",
        "keywords": {"night": 3, "dark": 3, "dim": 2, "nighttime": 3},
        "phrases": ["night mode", "dark mode", "dim mode", "nighttime mode",
                     "make it dark", "make it dim"],
    },
    "theme_auto": {
        "action": "theme", "target": "auto",
        "keywords": {"auto": 2, "automatic": 3, "color auto": 3},
        "phrases": ["auto mode", "automatic mode", "auto color", "auto theme"],
    },
    "brightness_up": {
        "action": "brightness", "target": "up",
        "keywords": {"brighter": 3, "brightness up": 3, "lighter": 2, "increase": 1},
        "phrases": ["brightness up", "make it brighter", "turn up brightness",
                     "more bright", "increase brightness"],
    },
    "brightness_down": {
        "action": "brightness", "target": "down",
        "keywords": {"dimmer": 3, "brightness down": 3, "darker": 2, "decrease": 1},
        "phrases": ["brightness down", "make it dimmer", "turn down brightness",
                     "less bright", "decrease brightness"],
    },
    "wifi_scan": {
        "action": "wifi", "target": "scan",
        "keywords": {"wifi": 2, "network": 2, "networks": 2, "scan": 2,
                     "internet": 1, "wireless": 1},
        "phrases": ["scan networks", "show networks", "list networks",
                     "find wifi", "show wifi", "available networks"],
    },
    "wifi_connect": {
        "action": "wifi", "target": "connect",
        "keywords": {"connect": 3, "join": 2, "wifi": 1, "network": 1},
        "phrases": ["connect to", "join network", "connect wifi",
                     "connect network"],
    },
    "wifi_disconnect": {
        "action": "wifi", "target": "disconnect",
        "keywords": {"disconnect": 3, "drop": 1, "leave": 1},
        "phrases": ["disconnect wifi", "drop wifi", "leave network",
                     "disconnect network"],
    },
    "pair_phone": {
        "action": "pair", "target": "phone",
        "keywords": {"pair": 3, "pairing": 3, "phone": 2, "bluetooth": 2,
                     "setup": 2, "add": 1, "new": 1, "connect phone": 3},
        "phrases": ["pair phone", "setup phone", "add phone", "new phone",
                     "connect phone", "pair bluetooth", "setup bluetooth"],
    },
    "unpair_phone": {
        "action": "unpair", "target": "phone",
        "keywords": {"remove": 3, "forget": 3, "unpair": 3, "delete": 2,
                     "phone": 1, "bluetooth": 1},
        "phrases": ["remove phone", "forget phone", "unpair phone",
                     "delete phone", "forget bluetooth"],
    },
    "start_recording": {
        "action": "dashcam", "target": "start",
        "keywords": {"start": 2, "record": 3, "recording": 3, "dashcam": 3,
                     "camera": 1, "begin": 2, "capture": 2},
        "phrases": ["start recording", "start dashcam", "start camera",
                     "begin recording", "record video", "start capture"],
    },
    "stop_recording": {
        "action": "dashcam", "target": "stop",
        "keywords": {"stop": 2, "record": 2, "recording": 2, "dashcam": 2,
                     "end": 2, "pause": 2},
        "phrases": ["stop recording", "stop dashcam", "stop camera",
                     "end recording", "pause recording"],
    },
    "preview_camera": {
        "action": "show", "target": "camera",
        "keywords": {"preview": 3, "camera": 2, "view": 2, "see": 1,
                     "look": 1, "show": 1, "live": 2, "feed": 2},
        "phrases": ["preview camera", "show camera", "camera view",
                     "live camera", "live feed", "show me camera",
                     "pull up camera", "what do you see"],
    },
    "switch_camera": {
        "action": "show", "target": "camera",
        "keywords": {"switch": 3, "next": 2, "other": 2, "second": 2,
                     "alternate": 2, "swap": 3, "change": 1, "camera": 1},
        "phrases": ["switch camera", "next camera", "other camera",
                     "show other camera", "change camera", "swap camera",
                     "second camera", "show me other camera"],
    },
    "save_clip": {
        "action": "save", "target": "dashcam",
        "keywords": {"save": 4, "keep": 3, "clip": 2, "record": 1, "dashcam": 1,
                     "footage": 2, "video": 1, "that": 2},
        "phrases": ["save clip", "keep that", "save dashcam", "save that video",
                     "save footage", "keep this clip", "remember that"],
    },
    "calibrate": {
        "action": "system", "target": "calibrate",
        "keywords": {"calibrate": 3, "calibration": 3, "tune": 2, "tuning": 2,
                     "train": 2, "training": 2, "setup": 1, "voice": 1, "mic": 2},
        "phrases": ["calibrate", "voice calibration", "tune voice", "train voice",
                     "calibrate microphone", "setup voice", "mic calibration"],
    },
    "music_play": {
        "action": "music", "target": "play",
        "keywords": {"play": 3, "resume": 3, "start": 2, "music": 1},
        "phrases": ["play music", "resume music", "start music", "play song", "resume playback"],
    },
    "music_pause": {
        "action": "music", "target": "pause",
        "keywords": {"pause": 3, "stop": 2, "wait": 1, "music": 1},
        "phrases": ["pause music", "stop music", "pause playback", "stop playback"],
    },
    "music_next": {
        "action": "music", "target": "next",
        "keywords": {"next": 3, "skip": 3, "forward": 2, "song": 1, "track": 1},
        "phrases": ["next song", "skip song", "next track", "skip track", "go forward"],
    },
    "music_previous": {
        "action": "music", "target": "previous",
        "keywords": {"previous": 3, "back": 3, "last": 2, "song": 1, "track": 1},
        "phrases": ["previous song", "go back", "last song", "previous track", "last track"],
    },
    "help": {
        "action": "show", "target": "help",
        "keywords": {"help": 3, "commands": 2, "options": 2, "what": 1,
                     "can": 1, "do": 1, "ask": 2, "abilities": 2, "features": 2},
        "phrases": ["help", "what can you do", "what can i ask", "show help",
                     "show commands", "list commands", "what are my options",
                     "what do you do", "what can i say"],
    },
    "widget_show": {
        "action": "widget", "target": "show",
        "keywords": {"show": 2, "enable": 3, "widget": 3, "turn": 1, "on": 1,
                     "display": 2, "add": 2},
        "phrases": ["show widget", "enable widget", "turn on widget",
                     "show music widget", "show phone widget", "show network widget",
                     "show clock widget", "show dashcam widget",
                     "enable music", "enable phone", "enable network",
                     "add widget"],
    },
    "widget_hide": {
        "action": "widget", "target": "hide",
        "keywords": {"hide": 3, "disable": 3, "widget": 3, "turn": 1, "off": 1,
                     "remove": 2},
        "phrases": ["hide widget", "disable widget", "turn off widget",
                     "hide music widget", "hide phone widget", "hide network widget",
                     "hide clock widget", "hide dashcam widget",
                     "disable music", "disable phone", "disable network",
                     "remove widget"],
    },
}


def match_intent(text):
    """Match spoken text to the best intent.
    Returns (action, target, confidence) or None.
    """
    text_lower = text.lower().strip()
    words = text_lower.split()

    best_intent = None
    best_score = 0

    for intent_name, intent in INTENTS.items():
        score = 0

        # Check exact phrase matches (highest confidence)
        for phrase in intent["phrases"]:
            if phrase in text_lower:
                score += 5 * len(phrase.split())

        # Check keyword matches
        for keyword, weight in intent["keywords"].items():
            if " " in keyword:
                # Multi-word keyword
                if keyword in text_lower:
                    score += weight * 2
            else:
                if keyword in words:
                    score += weight

        if score > best_score:
            best_score = score
            best_intent = intent

    # Need minimum confidence to trigger
    if best_score >= 3 and best_intent:
        confidence = min(1.0, best_score / 10.0)
        return best_intent["action"], best_intent["target"], confidence

    return None
