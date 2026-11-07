#!/usr/bin/env python3

"""Retro BIOS Setup - terminal settings interface."""

import curses

import json

import os

import re

import shutil

import subprocess

import time
import textwrap

from pathlib import Path

APP_NAME = "RETRO BIOS SETUP"

CONFIG_DIR = Path.home() / ".config" / "retro-bios"

CONFIG_FILE = CONFIG_DIR / "settings.json"

APP_CONFIG_FILE = CONFIG_DIR / "config.json"

LOG_FILE = Path.home() / ".local" / "state" / "retro-bios.log"

CATEGORIES = ["Main", "Advanced", "Power", "Devices", "System Log", "Exit"]

EXIT_OPTIONS = [

    "Save Changes and Exit",

    "Discard Changes and Exit",

    "Reset to Default Settings",

    "Cancel",

]

TIMEOUT_MINUTES = [0, 1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120]

POWER_PROFILES_FALLBACK = [

    "balanced",

    "balanced-battery",

    "powersave",

    "throughput-performance",

    "performance",

]

COLORS = {

    "black": curses.COLOR_BLACK,

    "red": curses.COLOR_RED,

    "green": curses.COLOR_GREEN,

    "yellow": curses.COLOR_YELLOW,

    "blue": curses.COLOR_BLUE,

    "magenta": curses.COLOR_MAGENTA,

    "cyan": curses.COLOR_CYAN,

    "white": curses.COLOR_WHITE,

}

FASTFETCH_MODULES = [

    ("title", "Title"),

    ("os", "Operating system"),

    ("host", "Host"),

    ("kernel", "Kernel"),

    ("uptime", "Uptime"),

    ("packages", "Packages"),

    ("shell", "Shell"),

    ("terminal", "Terminal"),

    ("cpu", "CPU"),

    ("gpu", "GPU"),

    ("memory", "Memory"),

    ("disk", "Disk"),

]

DEFAULT_SETTINGS = {

    "power_profile": "balanced",

    "volume": 100,

    "bluetooth": True,

    "screen_timeout": 300,

    "sound_output": None,

    "sound_input": None,

    "wifi_ssid": None,

    "brightness": 100,

}

DEFAULT_APP_CONFIG = {

    "theme": {

        "foreground": "blue",

        "background": "white",

        "highlight": "blue",

    },

    "interface": {

        "menu_spacing": 2,

        "footer_height": 1,

        "bold_text": True,

    },

    "show_fastfetch": True,

    "fastfetch_modules": [item[0] for item in FASTFETCH_MODULES],

}

def clone(value):

    return json.loads(json.dumps(value))

def log(message):

    try:

        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        with LOG_FILE.open("a", encoding="utf-8") as file:

            file.write(

                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "

                f"{message}\n"

            )

    except OSError:

        pass

def run_command(args, timeout=8):

    """Run a command without a shell."""

    try:

        result = subprocess.run(

            args,

            capture_output=True,

            text=True,

            timeout=timeout,

            check=False,

        )

        return (

            result.returncode == 0,

            result.stdout.strip(),

            result.stderr.strip(),

        )

    except (OSError, subprocess.SubprocessError) as exc:

        return False, "", str(exc)

def command_exists(name):

    return shutil.which(name) is not None

def load_app_config():

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    try:

        if APP_CONFIG_FILE.exists():

            loaded = json.loads(

                APP_CONFIG_FILE.read_text(encoding="utf-8")

            )

        else:

            loaded = {}

    except (OSError, json.JSONDecodeError):

        loaded = {}

    config = clone(DEFAULT_APP_CONFIG)

    if isinstance(loaded, dict):

        if isinstance(loaded.get("theme"), dict):

            config["theme"].update(loaded["theme"])

        if isinstance(loaded.get("interface"), dict):

            config["interface"].update(loaded["interface"])

        if isinstance(loaded.get("show_fastfetch"), bool):

            config["show_fastfetch"] = loaded["show_fastfetch"]

        modules = loaded.get("fastfetch_modules")

        if isinstance(modules, list):

            config["fastfetch_modules"] = [

                module

                for module in modules

                if module in dict(FASTFETCH_MODULES)

            ]

    for key in ("foreground", "background", "highlight"):

        if config["theme"].get(key) not in COLORS:

            config["theme"][key] = DEFAULT_APP_CONFIG["theme"][key]

    return config

def save_app_config(config):

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    temp = APP_CONFIG_FILE.with_suffix(".tmp")

    with temp.open("w", encoding="utf-8") as file:

        json.dump(config, file, indent=2, ensure_ascii=False)

        file.write("\n")

    temp.replace(APP_CONFIG_FILE)

def apply_theme(config):
    """Initialize the regular theme and fixed monochrome settings colors."""
    theme = config.get("theme", {})
    foreground = COLORS.get(theme.get("foreground"), curses.COLOR_BLUE)
    background = COLORS.get(theme.get("background"), curses.COLOR_WHITE)
    highlight = COLORS.get(theme.get("highlight"), curses.COLOR_BLUE)

    pairs = (
        (1, foreground, background),
        (2, curses.COLOR_WHITE, highlight),
        (3, highlight, background),
        # Configuration and its submenus always use white on black.
        (4, curses.COLOR_WHITE, curses.COLOR_BLACK),
        # Selected option: black on white.
        (5, curses.COLOR_BLACK, curses.COLOR_WHITE),
    )
    for pair_number, fg, bg in pairs:
        try:
            curses.init_pair(pair_number, fg, bg)
        except curses.error:
            # Keep trying the other pairs; pair 4/5 are essential for config.
            continue


def safe_addstr(win, y, x, text, max_width, attr=0):

    if max_width <= 0:

        return

    try:

        height, width = win.getmaxyx()

        if 0 <= y < height and 0 <= x < width:

            win.addnstr(

                y,

                x,

                str(text),

                min(max_width, width - x - 1),

                attr,

            )

    except curses.error:

        pass

def show_message(stdscr, message, title="Retro BIOS"):

    height, width = stdscr.getmaxyx()

    lines = message.splitlines() or [""]

    box_width = min(

        max(len(line) for line in lines) + 6,

        width - 4,

        76,

    )

    box_height = min(len(lines) + 4, height - 4)

    if box_width < 16 or box_height < 5:

        return

    top = (height - box_height) // 2

    left = (width - box_width) // 2

    win = curses.newwin(box_height, box_width, top, left)

    win.keypad(True)

    win.bkgd(" ", curses.color_pair(1))

    win.erase()

    win.attron(curses.color_pair(2))

    win.border()

    win.attroff(curses.color_pair(2))

    safe_addstr(

        win, 1, 2, f" {title} ",

        box_width - 4,

        curses.color_pair(2) | curses.A_BOLD,

    )

    for index, line in enumerate(lines[:box_height - 3], start=2):

        safe_addstr(win, index, 2, line, box_width - 4)

    safe_addstr(

        win,

        box_height - 2,

        2,

        "Press any key",

        box_width - 4,

        curses.A_BOLD,

    )

    win.refresh()

    win.getch()

def popup_select(stdscr, title, items, current_id, selected_index=0):

    """Select an item from (id, name, is_default) tuples."""

    if not items:

        show_message(stdscr, "No options found.", title)

        return current_id, True

    height, width = stdscr.getmaxyx()

    box_width = min(76, width - 4)

    box_height = min(max(8, min(len(items), height - 8) + 6), height - 4)

    if box_width < 24 or box_height < 7:

        return current_id, True

    selected_index = max(0, min(selected_index, len(items) - 1))

    win = curses.newwin(

        box_height,

        box_width,

        (height - box_height) // 2,

        (width - box_width) // 2,

    )

    win.keypad(True)

    win.bkgd(" ", curses.color_pair(1))

    while True:

        win.erase()

        win.attron(curses.color_pair(2))

        win.border()

        win.attroff(curses.color_pair(2))

        safe_addstr(

            win, 1, 2, f" {title} ", box_width - 4,

            curses.color_pair(2) | curses.A_BOLD,

        )

        visible = box_height - 5

        first = max(

            0,

            min(selected_index - visible + 1, len(items) - visible),

        )

        for row, index in enumerate(

            range(first, min(len(items), first + visible)),

            start=2,

        ):

            item_id, name, is_default = items[index]

            marker = "[x]" if str(item_id) == str(current_id) else "[ ]"

            suffix = " (system default)" if is_default else ""

            attr = curses.A_REVERSE if index == selected_index else 0

            safe_addstr(

                win,

                row,

                2,

                f"{marker} {name}{suffix}",

                box_width - 4,

                attr,

            )

        safe_addstr(

            win,

            box_height - 2,

            2,

            "UP/DOWN: Move  ENTER: Select  ESC: Back",

            box_width - 4,

        )

        win.refresh()

        key = win.getch()

        if key == curses.KEY_UP:

            selected_index = (selected_index - 1) % len(items)

        elif key == curses.KEY_DOWN:

            selected_index = (selected_index + 1) % len(items)

        elif key in (10, 13, curses.KEY_ENTER):

            return str(items[selected_index][0]), False

        elif key == 27:

            return current_id, True

def get_wpctl_status():

    if not command_exists("wpctl"):

        return ""

    ok, out, _ = run_command(["wpctl", "status", "-n"])

    if not ok:

        ok, out, _ = run_command(["wpctl", "status"])

    return out if ok else ""

def parse_audio_section(status, section_name):

    results = []

    active = False

    section_names = {

        "Sinks", "Sources", "Filters", "Streams",

        "Devices", "Video", "Settings",

    }

    for raw in status.splitlines():

        line = raw.strip()

        heading = re.sub(r"^[│├└─\s]+", "", line)

        heading_name = heading.rstrip(":").strip()

        if heading_name in section_names:

            if active:

                break

            active = heading_name == section_name

            continue

        if not active:

            continue

        match = re.search(r"(\*)?\s*(\d+)\.\s+(.+?)\s*$", line)

        if not match:

            continue

        results.append((

            match.group(2),

            match.group(3).strip(),

            bool(match.group(1)) or line.startswith("*"),

        ))

    return results

def get_audio_devices(section):

    return parse_audio_section(get_wpctl_status(), section)

def get_volume():

    if not command_exists("wpctl"):

        return 100

    ok, out, _ = run_command([

        "wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@",

    ])

    if ok:

        match = re.search(r"Volume:\s*([0-9.]+)", out)

        if match:

            return max(0, min(150, round(float(match.group(1)) * 100)))

    return 100

def get_brightness():

    """Read brightness using brightnessctl, light, or sysfs."""

    if command_exists("brightnessctl"):

        ok, out, _ = run_command(["brightnessctl", "-m"])

        if ok:

            fields = out.split(",")

            if len(fields) >= 4:

                try:

                    current = int(fields[2])

                    maximum = int(fields[3])

                    if maximum:

                        return max(0, min(100, round(current * 100 / maximum)))

                except ValueError:

                    pass

    if command_exists("light"):

        ok, out, _ = run_command(["light", "-G"])

        if ok:

            try:

                return max(0, min(100, round(float(out))))

            except ValueError:

                pass

    for device in Path("/sys/class/backlight").glob("*"):

        try:

            current = int((device / "brightness").read_text().strip())

            maximum = int((device / "max_brightness").read_text().strip())

            if maximum:

                return max(0, min(100, round(current * 100 / maximum)))

        except (OSError, ValueError, ZeroDivisionError):

            continue

    return 100

def set_brightness(value):

    value = max(0, min(100, int(value)))

    if command_exists("brightnessctl"):

        ok, _, err = run_command([

            "brightnessctl", "set", f"{value}%",

        ], timeout=10)

        if ok:

            return True, ""

        last_error = err

    else:

        last_error = ""

    if command_exists("light"):

        ok, _, err = run_command([

            "light", "-S", str(value),

        ], timeout=10)

        if ok:

            return True, ""

        last_error = err

    devices = list(Path("/sys/class/backlight").glob("*"))

    for device in devices:

        try:

            maximum = int((device / "max_brightness").read_text().strip())

            target = round(maximum * value / 100)

            (device / "brightness").write_text(str(target))

            return True, ""

        except (OSError, ValueError) as exc:

            last_error = str(exc)

    return False, last_error or "No usable backlight controller found."

def get_bluetooth_state():

    if not command_exists("bluetoothctl"):

        return True

    ok, out, _ = run_command(["bluetoothctl", "show"])

    if ok:

        match = re.search(r"Powered:\s*(yes|no)", out, re.I)

        if match:

            return match.group(1).lower() == "yes"

    return True

def get_screen_timeout():

    if command_exists("gsettings"):

        ok, out, _ = run_command([

            "gsettings", "get",

            "org.gnome.desktop.session", "idle-delay",

        ])

        if ok:

            match = re.search(r"\b(\d+)\b", out)

            if match:

                return int(match.group(1))

    return DEFAULT_SETTINGS["screen_timeout"]

def get_current_power_profile():

    if command_exists("powerprofilesctl"):

        ok, out, _ = run_command(["powerprofilesctl", "get"])

        if ok and out:

            return out

    if command_exists("tuned-adm"):

        ok, out, _ = run_command(["tuned-adm", "active"])

        if ok:

            match = re.search(r"active profile:\s*(.+)", out, re.I)

            if match:

                return match.group(1).strip()

    return DEFAULT_SETTINGS["power_profile"]

def get_power_profiles():

    if command_exists("powerprofilesctl"):

        ok, out, _ = run_command(["powerprofilesctl", "list"])

        if ok:

            profiles = []

            for line in out.splitlines():

                match = re.search(

                    r"\b(performance|balanced|power-saver)\b",

                    line,

                )

                if match:

                    profiles.append(match.group(1))

            if profiles:

                return list(dict.fromkeys(profiles))

    if command_exists("tuned-adm"):

        ok, out, _ = run_command(["tuned-adm", "list"])

        if ok:

            profiles = re.findall(r"-\s*([a-zA-Z0-9_-]+)\s*$", out, re.M)

            if profiles:

                return list(dict.fromkeys(profiles))

    return POWER_PROFILES_FALLBACK

def get_wifi_networks():

    if not command_exists("nmcli"):

        return []

    ok, out, _ = run_command([

        "nmcli", "-t", "-f", "IN-USE,SSID,SECURITY,SIGNAL",

        "device", "wifi", "list",

    ], timeout=12)

    if not ok:

        return []

    strongest = {}

    for line in out.splitlines():

        fields = re.split(r"(?<!\\):", line)

        fields = [

            field.replace("\\:", ":").replace("\\\\", "\\")

            for field in fields

        ]

        if len(fields) < 4:

            continue

        in_use, ssid, security, signal = fields[:4]

        ssid = ssid.strip()

        if not ssid:

            continue

        try:

            signal = int(signal)

        except ValueError:

            signal = 0

        item = (ssid, security or "Open", signal, in_use.strip() == "*")

        if (

            ssid not in strongest

            or signal > strongest[ssid][2]

            or item[3]

        ):

            strongest[ssid] = item

    return sorted(

        strongest.values(),

        key=lambda item: (not item[3], -item[2], item[0].lower()),

    )

def get_current_wifi_ssid():

    return next(

        (network[0] for network in get_wifi_networks() if network[3]),

        None,

    )

def popup_wifi_select(stdscr, current_ssid):

    networks = get_wifi_networks()

    if not networks:

        show_message(

            stdscr,

            "No Wi-Fi networks found.\nCheck NetworkManager and nmcli.",

            "Wi-Fi",

        )

        return current_ssid, True

    items = [

        (

            ssid,

            f"{ssid}  {security}  {signal}%",

            connected,

        )

        for ssid, security, signal, connected in networks

    ]

    selected = next(

        (i for i, item in enumerate(items) if item[0] == current_ssid),

        0,

    )

    return popup_select(stdscr, "WI-FI NETWORKS", items, current_ssid, selected)

def find_saved_wifi_profile(ssid):

    if not command_exists("nmcli"):

        return None

    ok, out, _ = run_command([

        "nmcli", "-t", "-f", "NAME,TYPE",

        "connection", "show",

    ])

    if not ok:

        return None

    for line in out.splitlines():

        fields = re.split(r"(?<!\\):", line)

        if len(fields) < 2:

            continue

        name = fields[0].replace("\\:", ":")

        connection_type = fields[1]

        if connection_type not in ("802-11-wireless", "wifi"):

            continue

        ok, profile_ssid, _ = run_command([

            "nmcli", "-g", "802-11-wireless.ssid",

            "connection", "show", "id", name,

        ])

        if ok and profile_ssid == ssid:

            return name

        if name == ssid:

            return name

    return None

def detect_system_settings():

    sinks = get_audio_devices("Sinks")

    sources = get_audio_devices("Sources")

    return {

        "power_profile": get_current_power_profile(),

        "volume": get_volume(),

        "bluetooth": get_bluetooth_state(),

        "screen_timeout": get_screen_timeout(),

        "sound_output": next((x[0] for x in sinks if x[2]), None),

        "sound_input": next((x[0] for x in sources if x[2]), None),

        "wifi_ssid": get_current_wifi_ssid(),

        "brightness": get_brightness(),

    }

def normalize_settings(value):

    settings = DEFAULT_SETTINGS.copy()

    if isinstance(value, dict):

        for key in settings:

            if key in value:

                settings[key] = value[key]

    for key, low, high in (

        ("volume", 0, 150),

        ("brightness", 0, 100),

    ):

        try:

            settings[key] = max(low, min(high, int(settings[key])))

        except (TypeError, ValueError):

            settings[key] = DEFAULT_SETTINGS[key]

    try:

        settings["screen_timeout"] = max(

            0, int(settings["screen_timeout"])

        )

    except (TypeError, ValueError):

        settings["screen_timeout"] = DEFAULT_SETTINGS["screen_timeout"]

    settings["bluetooth"] = bool(settings["bluetooth"])

    settings["power_profile"] = str(settings["power_profile"])

    for key in ("sound_output", "sound_input", "wifi_ssid"):

        if settings[key] is not None:

            settings[key] = str(settings[key])

    return settings

def load_saved_settings():

    try:

        with CONFIG_FILE.open("r", encoding="utf-8") as file:

            return normalize_settings(json.load(file))

    except (OSError, json.JSONDecodeError):

        return normalize_settings(detect_system_settings())

def persist_settings(settings):

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    temp_file = CONFIG_FILE.with_suffix(".tmp")

    with temp_file.open("w", encoding="utf-8") as file:

        json.dump(settings, file, indent=2, ensure_ascii=False)

        file.write("\n")

    temp_file.replace(CONFIG_FILE)

def apply_settings(settings):

    errors = []

    profile = settings["power_profile"]

    if command_exists("powerprofilesctl"):

        ok, _, err = run_command(["powerprofilesctl", "set", profile])

        if not ok:

            errors.append(f"Power profile: {err or 'command failed'}")

    elif command_exists("tuned-adm"):

        ok, _, err = run_command(["tuned-adm", "profile", profile])

        if not ok:

            errors.append(f"Power profile: {err or 'command failed'}")

    else:

        errors.append("Power profile: no supported power manager found")

    for key, section in (

        ("sound_output", "Sinks"),

        ("sound_input", "Sources"),

    ):

        device_id = settings[key]

        if device_id is None:

            continue

        devices = get_audio_devices(section)

        if not any(str(device[0]) == str(device_id) for device in devices):

            errors.append(f"{key}: selected audio device no longer exists")

            continue

        ok, _, err = run_command(["wpctl", "set-default", str(device_id)])

        if not ok:

            errors.append(f"{key}: {err or 'command failed'}")

    wifi_ssid = settings.get("wifi_ssid")

    if (

        wifi_ssid

        and command_exists("nmcli")

        and get_current_wifi_ssid() != wifi_ssid

    ):

        profile_name = find_saved_wifi_profile(wifi_ssid)

        if not profile_name:

            errors.append(

                f"Wi-Fi: no saved profile for '{wifi_ssid}'. "

                "Connect to it in system settings first."

            )

        else:

            ok, _, err = run_command(

                ["nmcli", "connection", "up", "id", profile_name],

                timeout=20,

            )

            if not ok:

                errors.append(f"Wi-Fi: {err or 'connection failed'}")

    if command_exists("wpctl"):

        volume = settings["volume"]

        # wpctl's --limit restricts the maximum volume.

        # Use it for amplification above 100%.

        args = ["wpctl", "set-volume"]

        if volume > 100:

            args.extend(["--limit", "1.5"])

        args.extend(["@DEFAULT_AUDIO_SINK@", f"{volume}%"])

        ok, _, err = run_command(args)

        if not ok:

            errors.append(f"Volume: {err or 'command failed'}")

    else:

        errors.append("Volume: wpctl is not installed")

    if command_exists("bluetoothctl"):

        power = "on" if settings["bluetooth"] else "off"

        ok, _, err = run_command(["bluetoothctl", "power", power])

        if not ok:

            errors.append(f"Bluetooth: {err or 'command failed'}")

    if command_exists("gsettings"):

        ok, _, err = run_command([

            "gsettings", "set",

            "org.gnome.desktop.session", "idle-delay",

            str(settings["screen_timeout"]),

        ])

        if not ok:

            errors.append(f"Screen timeout: {err or 'command failed'}")

    ok, err = set_brightness(settings["brightness"])

    if not ok:

        errors.append(f"Brightness: {err or 'could not change brightness'}")

    return errors

def get_fastfetch(config):

    if not command_exists("fastfetch"):

        return ["Fastfetch is not installed."]

    modules = config.get("fastfetch_modules", [])

    if not modules:

        return ["All Fastfetch modules are disabled."]

    structure = ":".join(modules)

    ok, out, err = run_command([

        "fastfetch",

        "--logo", "none",

        "--structure", structure,

    ], timeout=8)

    if not ok:

        return [f"Fastfetch error: {err or 'command failed'}"]

    return out.splitlines() or ["Fastfetch returned no information."]

def get_system_log_lines(limit=18):

    try:

        if LOG_FILE.exists():

            lines = LOG_FILE.read_text(

                encoding="utf-8",

                errors="replace",

            ).splitlines()

            return lines[-limit:] or ["Retro BIOS log is empty."]

    except OSError:

        pass

    return ["No Retro BIOS log yet.", f"Log path: {LOG_FILE}"]

def draw_header(stdscr, selected):

    height, width = stdscr.getmaxyx()

    safe_addstr(

        stdscr, 0, 0, APP_NAME.ljust(width), width - 1,

        curses.color_pair(2) | curses.A_BOLD,

    )

    x = 2

    for index, category in enumerate(CATEGORIES):

        label = f" {category} "

        if x >= width - 1:

            break

        attr = (

            curses.color_pair(2) | curses.A_BOLD

            if index == selected

            else curses.A_NORMAL

        )

        safe_addstr(stdscr, 2, x, label, width - x - 1, attr)

        x += len(label) + 1

    footer = "←/→ Category  ↑/↓ Move  ENTER Select  C Configuration  Q Exit"

    safe_addstr(

        stdscr, height - 1, 0, footer.center(width), width - 1,

        curses.color_pair(2) | curses.A_BOLD,

    )

def draw_list(stdscr, title, options, selected, start_y=6, start_x=4, status="", max_width=None):

    height, width = stdscr.getmaxyx()
    content_width = max_width if max_width is not None else width - start_x - 2

    safe_addstr(
        stdscr, 4, start_x, title, content_width,
        curses.A_BOLD,
    )

    for index, option in enumerate(options):
        y = start_y + index * 2
        if y >= height - 3:
            break
        attr = curses.A_REVERSE if index == selected else curses.A_NORMAL
        safe_addstr(stdscr, y, start_x, option, content_width, attr)

    if status:
        safe_addstr(
            stdscr, height - 2, 2, status, width - 4,
            curses.A_BOLD,
        )


def draw_setup_description(stdscr, heading, description, x=None):
    """Draw a description panel on the normal setup screen."""
    height, width = stdscr.getmaxyx()
    if width < 70 or height < 12:
        return
    panel_x = x if x is not None else width // 2
    panel_width = width - panel_x - 2
    panel_height = height - 7
    if panel_width < 18 or panel_height < 5:
        return
    try:
        panel = curses.newwin(panel_height, panel_width, 4, panel_x)
        panel.bkgd(" ", curses.color_pair(1))
        panel.erase()
        panel.attron(curses.color_pair(2))
        panel.border()
        panel.attroff(curses.color_pair(2))
        safe_addstr(panel, 1, 2, heading, panel_width - 4,
                    curses.color_pair(2) | curses.A_BOLD)
        wrapped = textwrap.wrap(description, width=max(10, panel_width - 6)) or [""]
        for i, line in enumerate(wrapped[:max(1, panel_height - 3)], start=3):
            safe_addstr(panel, i, 2, line, panel_width - 4, curses.color_pair(1))
        panel.refresh()
    except curses.error:
        pass

def confirm_system_action(stdscr, title, message):
    """Require explicit Y confirmation before rebooting or powering off."""
    height, width = stdscr.getmaxyx()
    box_width = min(max(len(message) + 6, len(title) + 6, 42), width - 4)
    box_height = 7
    if width < 30 or height < 10 or box_width < 20:
        show_message(stdscr, "Terminal too small to confirm this action.", title)
        return False
    top = (height - box_height) // 2
    left = (width - box_width) // 2
    win = curses.newwin(box_height, box_width, top, left)
    win.keypad(True)
    win.bkgd(" ", curses.color_pair(4))
    win.erase()
    win.attron(curses.color_pair(4))
    win.border()
    safe_addstr(win, 1, 2, title, box_width - 4, curses.color_pair(4) | curses.A_BOLD)
    safe_addstr(win, 3, 2, message, box_width - 4, curses.color_pair(4))
    safe_addstr(win, 5, 2, "Press Y to confirm, any other key to cancel", box_width - 4,
                curses.color_pair(4) | curses.A_BOLD)
    win.refresh()
    return win.getch() in (ord("y"), ord("Y"))


def run_system_action(stdscr, action):
    """Run a requested system power action only after confirmation."""
    commands = {
        "Reboot": ["systemctl", "reboot"],
        "Boot to BIOS/UEFI": ["systemctl", "reboot", "--firmware-setup"],
        "Shutdown": ["systemctl", "poweroff"],
    }
    prompts = {
        "Reboot": "Restart the computer now?",
        "Boot to BIOS/UEFI": "Restart and open BIOS/UEFI setup?",
        "Shutdown": "Power off the computer now?",
    }
    if action not in commands:
        return
    if not confirm_system_action(stdscr, action, prompts[action]):
        return
    try:
        result = subprocess.run(commands[action], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "Command failed.").strip()
            show_message(stdscr, detail[:500], f"{action} failed")
    except (OSError, subprocess.SubprocessError) as exc:
        show_message(stdscr, str(exc), f"{action} failed")


def configuration_menu(stdscr, config):
    """Full-screen GRUB-like monochrome configuration menu."""
    choices = [
        "Appearance",
        "Fastfetch Settings",
        "Reboot",
        "Boot to BIOS/UEFI",
        "Shutdown",
        "Back",
    ]
    selected = 0

    while True:
        height, width = stdscr.getmaxyx()
        stdscr.bkgd(" ", curses.color_pair(4))
        stdscr.erase()

        # Full-screen frame, similar to a bootloader menu.
        try:
            stdscr.attron(curses.color_pair(4))
            stdscr.border()
            stdscr.attroff(curses.color_pair(4))
        except curses.error:
            pass

        title = "GRUB GNU 2026 (Configuration & More)"
        title_x = max(1, (width - len(title)) // 2)
        safe_addstr(
            stdscr, 1, title_x, title, max(1, width - title_x - 2),
            curses.color_pair(4) | curses.A_BOLD,
        )

        if height >= 7 and width >= 24:
            # Separator below the title.
            try:
                stdscr.addch(2, 1, curses.ACS_LTEE, curses.color_pair(4))
                for x in range(2, width - 2):
                    stdscr.addch(2, x, curses.ACS_HLINE, curses.color_pair(4))
                stdscr.addch(2, width - 2, curses.ACS_RTEE, curses.color_pair(4))
            except curses.error:
                pass

            safe_addstr(
                stdscr, 4, 3, "SETUP OPTIONS",
                max(1, width - 6), curses.color_pair(4) | curses.A_BOLD,
            )

            # Keep the list vertical and aligned to the left like a boot menu.
            list_y = 6
            for index, choice in enumerate(choices):
                row = list_y + index
                if row >= height - 3:
                    break
                attr = (
                    curses.color_pair(5) | curses.A_BOLD
                    if index == selected else curses.color_pair(4)
                )
                safe_addstr(
                    stdscr, row, 5, choice,
                    max(1, width - 10), attr,
                )
        else:
            # Compact fallback for very small terminals.
            for index, choice in enumerate(choices):
                row = 3 + index
                if row >= height - 1:
                    break
                attr = (
                    curses.color_pair(5) | curses.A_BOLD
                    if index == selected else curses.color_pair(4)
                )
                safe_addstr(stdscr, row, 1, choice, max(1, width - 3), attr)

        footer = "UP/DOWN: Move   ENTER: Select   ESC: Back"
        if height >= 4:
            safe_addstr(
                stdscr, height - 2, 2, footer,
                max(1, width - 4), curses.color_pair(4) | curses.A_BOLD,
            )

        stdscr.refresh()
        key = stdscr.getch()

        if key in (27, ord("c"), ord("C")):
            return
        if key == curses.KEY_UP:
            selected = (selected - 1) % len(choices)
        elif key == curses.KEY_DOWN:
            selected = (selected + 1) % len(choices)
        elif key in (10, 13, curses.KEY_ENTER):
            if selected == 0:
                appearance_menu(stdscr, config)
            elif selected == 1:
                fastfetch_menu(stdscr, config)
            elif selected in (2, 3, 4):
                run_system_action(stdscr, choices[selected])
            else:
                return
            apply_theme(config)
            try:
                save_app_config(config)
            except OSError as exc:
                show_message(stdscr, str(exc), "Configuration save error")

def appearance_menu(stdscr, config):

    fields = [

        ("foreground", "Text color"),

        ("background", "Background color"),

        ("highlight", "Selection color"),

        ("back", "Back"),

    ]

    selected = 0

    color_names = list(COLORS)

    while True:

        height, width = stdscr.getmaxyx()

        stdscr.erase()

        stdscr.bkgd(" ", curses.color_pair(4))

        safe_addstr(

            stdscr, 1, 2, "APPEARANCE",

            width - 4, curses.color_pair(4) | curses.A_BOLD,

        )

        for index, (key, label) in enumerate(fields):

            if key == "back":

                value = ""

            else:

                value = config["theme"][key]

            attr = (curses.color_pair(5) | curses.A_BOLD) if index == selected else curses.color_pair(4)

            safe_addstr(

                stdscr, 4 + index * 2, 4,

                f"{label}: {value}", width - 8, attr,

            )

        safe_addstr(

            stdscr, height - 2, 2,

            "←/→ Change color   ENTER Change   ESC Back",

            width - 4,

        )

        stdscr.refresh()

        key = stdscr.getch()

        if key == 27:

            return

        field = fields[selected][0]

        if field == "back":

            if key in (10, 13, curses.KEY_ENTER):

                return

            if key == curses.KEY_UP:

                selected = (selected - 1) % len(fields)

            elif key == curses.KEY_DOWN:

                selected = (selected + 1) % len(fields)

            continue

        if key in (curses.KEY_UP, curses.KEY_DOWN):

            selected = (

                (selected - 1) % len(fields)

                if key == curses.KEY_UP

                else (selected + 1) % len(fields)

            )

            continue

        if key in (curses.KEY_LEFT, curses.KEY_RIGHT, 10, 13, curses.KEY_ENTER):

            current = config["theme"][field]

            index = color_names.index(current) if current in color_names else 0

            if key == curses.KEY_LEFT:

                index = (index - 1) % len(color_names)

            else:

                index = (index + 1) % len(color_names)

            config["theme"][field] = color_names[index]

            apply_theme(config)

def fastfetch_menu(stdscr, config):

    choices = [

        ("show_fastfetch", "Show Fastfetch"),

    ] + [

        (module, label)

        for module, label in FASTFETCH_MODULES

    ] + [

        ("back", "Back"),

    ]

    selected = 0

    while True:

        height, width = stdscr.getmaxyx()

        stdscr.erase()

        stdscr.bkgd(" ", curses.color_pair(4))

        safe_addstr(

            stdscr, 1, 2, "FASTFETCH SETTINGS",

            width - 4, curses.color_pair(4) | curses.A_BOLD,

        )

        visible = max(1, height - 8)

        first = max(

            0,

            min(selected - visible + 1, len(choices) - visible),

        )

        enabled_modules = config.get("fastfetch_modules", [])

        for row, index in enumerate(

            range(first, min(len(choices), first + visible)),

            start=4,

        ):

            key, label = choices[index]

            if key == "back":

                text = label

            elif key == "show_fastfetch":

                marker = "[x]" if config["show_fastfetch"] else "[ ]"

                text = f"{marker} {label}"

            else:

                marker = "[x]" if key in enabled_modules else "[ ]"

                text = f"{marker} {label}"

            attr = (curses.color_pair(5) | curses.A_BOLD) if index == selected else curses.color_pair(4)

            safe_addstr(stdscr, row, 4, text, width - 8, attr)

        safe_addstr(

            stdscr, height - 2, 2,

            "↑/↓ Move   SPACE/ENTER Toggle   ESC Back",

            width - 4,

        )

        stdscr.refresh()

        key = stdscr.getch()

        if key == 27:

            return

        if key == curses.KEY_UP:

            selected = (selected - 1) % len(choices)

            continue

        if key == curses.KEY_DOWN:

            selected = (selected + 1) % len(choices)

            continue

        if key not in (10, 13, curses.KEY_ENTER, ord(" ")):

            continue

        field, _ = choices[selected]

        if field == "back":

            return

        if field == "show_fastfetch":

            config["show_fastfetch"] = not config["show_fastfetch"]

        else:

            modules = config.setdefault("fastfetch_modules", [])

            if field in modules:

                modules.remove(field)

            else:

                modules.append(field)

            config["fastfetch_modules"] = [

                module

                for module, _ in FASTFETCH_MODULES

                if module in modules

            ]

def main(stdscr):

    curses.curs_set(0)

    stdscr.keypad(True)

    curses.start_color()

    try:

        curses.use_default_colors()

    except curses.error:

        pass

    app_config = load_app_config()

    apply_theme(app_config)

    saved_settings = load_saved_settings()

    settings = saved_settings.copy()

    selected_category = 0

    devices_selected = 0

    power_selected = 0

    advanced_selected = 0

    exit_selected = 0

    devices_options = [

        "Sound Output",

        "Sound Input",

        "Wi-Fi",

        "Bluetooth",

        "Volume",

        "Back",

    ]

    power_profiles = get_power_profiles()

    timeout_selected = min(

        range(len(TIMEOUT_MINUTES)),

        key=lambda i: abs(

            TIMEOUT_MINUTES[i] - round(settings["screen_timeout"] / 60)

        ),

    )

    status_message = "Changes are drafts until Save Changes and Exit."

    while True:

        height, width = stdscr.getmaxyx()

        stdscr.bkgd(" ", curses.color_pair(1))

        stdscr.erase()

        draw_header(stdscr, selected_category)

        category = CATEGORIES[selected_category]

        if category == "Main":
            if app_config.get("show_fastfetch", True):
                lines = get_fastfetch(app_config)
                start = 4
                for index, line in enumerate(lines):
                    y = start + index
                    if y >= height - 4:
                        break
                    safe_addstr(
                        stdscr, y, 3, line,
                        width - 6, curses.color_pair(1) | curses.A_BOLD,
                    )

            safe_addstr(
                stdscr, max(4, height - 4), 3,
                "Terminal settings frontend - not motherboard firmware.",
                width - 6,
            )
            draw_setup_description(
                stdscr, "MAIN DESCRIPTION",
                "Welcome to GRUB GNU 2026. Use the category bar to configure power, devices, advanced settings, and Fastfetch display options.",
            )

        elif category == "Advanced":

            timeout = TIMEOUT_MINUTES[timeout_selected]

            timeout_label = "Never" if timeout == 0 else f"{timeout} min"

            options = [

                f"Screen Timeout: {timeout_label}",

                "Back",

            ]

            draw_list(

                stdscr, "Advanced Configuration",

                options, advanced_selected, status=status_message,
                max_width=(width // 2 - 6 if width >= 70 else None),

            )
            draw_setup_description(
                stdscr, "ADVANCED DESCRIPTION",
                [
                    "Screen timeout controls how long the display waits before blanking.",
                    "Choose Never or a timeout interval to suit your setup.",
                ][0],
            )

        elif category == "Power":

            options = [

                f"Power profile: {settings['power_profile']}",

                f"Brightness: {settings['brightness']}%",

                "Back",

            ]

            draw_list(

                stdscr, "Power Configuration",

                options, power_selected, status=status_message,
                max_width=(width // 2 - 6 if width >= 70 else None),

            )
            draw_setup_description(
                stdscr, "POWER DESCRIPTION",
                "Adjust the system power profile and brightness. Some controls depend on hardware and desktop support.",
            )

            safe_addstr(

                stdscr, 12, 4,

                "Sometimes it doesn't work.",

                width - 6,

            )

        elif category == "Devices":

            sinks = get_audio_devices("Sinks")

            sources = get_audio_devices("Sources")

            output_name = next(

                (

                    device[1] for device in sinks

                    if str(device[0]) == str(settings["sound_output"])

                ),

                "System default",

            )

            input_name = next(

                (

                    device[1] for device in sources

                    if str(device[0]) == str(settings["sound_input"])

                ),

                "System default",

            )

            options = [

                f"Sound Output: {output_name}",

                f"Sound Input: {input_name}",

                f"Wi-Fi: {settings['wifi_ssid'] or 'Keep current connection'}",

                f"Bluetooth: {'Enabled' if settings['bluetooth'] else 'Disabled'}",

                f"Volume: {settings['volume']}%",

                "Back",

            ]

            draw_list(

                stdscr, "Devices Configuration",

                options, devices_selected, status=status_message,
                max_width=(width // 2 - 6 if width >= 70 else None),

            )
            device_descriptions = [
                "Choose the audio output device used for sound playback.",
                "Choose the microphone or other audio input device.",
                "Select a Wi-Fi network. Network changes may require system permissions.",
                "Toggle Bluetooth support for this setup profile.",
                "Adjust the output volume level.",
                "Return to the Main category.",
            ]
            draw_setup_description(
                stdscr, "DEVICES DESCRIPTION",
                device_descriptions[min(devices_selected, len(device_descriptions) - 1)],
            )

        elif category == "System Log":

            safe_addstr(

                stdscr, 4, 3, "Recent Retro BIOS events",

                width - 5, curses.A_BOLD,

            )

            for index, line in enumerate(

                get_system_log_lines(max(1, height - 8)),

                start=5,

            ):

                if index >= height - 2:

                    break

                safe_addstr(stdscr, index, 3, line, (width // 2 - 5 if width >= 70 else width - 5))
            draw_setup_description(
                stdscr, "SYSTEM LOG DESCRIPTION",
                "Recent application events and errors are shown on the left. The log is stored under ~/.local/state/retro-bios.log.",
            )

        elif category == "Exit":

            draw_list(

                stdscr, "Exit Setup",

                EXIT_OPTIONS, exit_selected,

                status=status_message,
                max_width=(width // 2 - 6 if width >= 70 else None),

            )
            exit_descriptions = [
                "Apply pending changes, save them, and exit the setup program.",
                "Discard unsaved changes and exit without applying them.",
                "Restore default settings in the current draft. Save them to apply.",
                "Return to the Main category without exiting.",
            ]
            draw_setup_description(
                stdscr, "EXIT DESCRIPTION",
                exit_descriptions[min(exit_selected, len(exit_descriptions) - 1)],
            )

        safe_addstr(

            stdscr, height - 2,

            max(0, width - len("By Melbartin0 | With ChatGPT") - 2),

            "By Melbartin0 | With ChatGPT",

            len("By Melbartin0 | With ChatGPT"),

            curses.A_BOLD,

        )

        stdscr.refresh()

        key = stdscr.getch()

        if key in (ord("c"), ord("C")):

            configuration_menu(stdscr, app_config)

            apply_theme(app_config)

            try:

                save_app_config(app_config)

                status_message = "Configuration saved."

            except OSError as exc:

                status_message = f"Could not save configuration: {exc}"

            continue

        if key in (ord("q"), ord("Q")):

            selected_category = CATEGORIES.index("Exit")

            continue

        if key == 27:

            selected_category = CATEGORIES.index("Main")

            status_message = "Returned to Main. Draft changes are still pending."

            continue

        # Adjust sliders with left/right.

        if (

            category == "Devices"

            and devices_selected == 4

            and key in (curses.KEY_LEFT, curses.KEY_RIGHT)

        ):

            delta = -5 if key == curses.KEY_LEFT else 5

            settings["volume"] = max(

                0, min(150, settings["volume"] + delta)

            )

            status_message = f"Volume draft: {settings['volume']}%"

            continue

        if (

            category == "Power"

            and power_selected == 1

            and key in (curses.KEY_LEFT, curses.KEY_RIGHT)

        ):

            delta = -5 if key == curses.KEY_LEFT else 5

            settings["brightness"] = max(

                0, min(100, settings["brightness"] + delta)

            )

            status_message = (

                f"Brightness draft: {settings['brightness']}%"

            )

            continue

        if (

            category == "Advanced"

            and advanced_selected == 0

            and key in (curses.KEY_LEFT, curses.KEY_RIGHT)

        ):

            delta = -1 if key == curses.KEY_LEFT else 1

            timeout_selected = max(

                0,

                min(len(TIMEOUT_MINUTES) - 1, timeout_selected + delta),

            )

            settings["screen_timeout"] = (

                TIMEOUT_MINUTES[timeout_selected] * 60

            )

            continue

        if key == curses.KEY_LEFT:

            selected_category = max(0, selected_category - 1)

            continue

        if key == curses.KEY_RIGHT:

            selected_category = min(

                len(CATEGORIES) - 1, selected_category + 1

            )

            continue

        if category == "Devices":

            if key == curses.KEY_UP:

                devices_selected = (

                    devices_selected - 1

                ) % len(devices_options)

            elif key == curses.KEY_DOWN:

                devices_selected = (

                    devices_selected + 1

                ) % len(devices_options)

            elif key in (10, 13, curses.KEY_ENTER):

                if devices_selected == 0:

                    devices = get_audio_devices("Sinks")

                    current = settings["sound_output"]

                    chosen, cancelled = popup_select(

                        stdscr, "SOUND OUTPUT",

                        devices, current,

                    )

                    if not cancelled:

                        settings["sound_output"] = chosen

                        status_message = "Sound output staged."

                elif devices_selected == 1:

                    devices = get_audio_devices("Sources")

                    current = settings["sound_input"]

                    chosen, cancelled = popup_select(

                        stdscr, "SOUND INPUT",

                        devices, current,

                    )

                    if not cancelled:

                        settings["sound_input"] = chosen

                        status_message = "Sound input staged."

                elif devices_selected == 2:

                    chosen, cancelled = popup_wifi_select(

                        stdscr, settings.get("wifi_ssid")

                    )

                    if not cancelled:

                        settings["wifi_ssid"] = chosen

                        status_message = f"Wi-Fi staged: {chosen}"

                elif devices_selected == 3:

                    settings["bluetooth"] = not settings["bluetooth"]

                elif devices_selected == 4:

                    settings["volume"] = min(

                        150, settings["volume"] + 5

                    )

                else:

                    selected_category = CATEGORIES.index("Main")

        elif category == "Power":

            if key == curses.KEY_UP:

                power_selected = max(0, power_selected - 1)

            elif key == curses.KEY_DOWN:

                power_selected = min(2, power_selected + 1)

            elif key in (10, 13, curses.KEY_ENTER):

                if power_selected == 0:

                    profiles = get_power_profiles()

                    current = settings["power_profile"]

                    chosen, cancelled = popup_select(

                        stdscr,

                        "POWER PROFILE",

                        [

                            (profile, profile, profile == current)

                            for profile in profiles

                        ],

                        current,

                    )

                    if not cancelled:

                        settings["power_profile"] = chosen

                elif power_selected == 1:

                    settings["brightness"] = min(

                        100, settings["brightness"] + 5

                    )

                else:

                    selected_category = CATEGORIES.index("Main")

        elif category == "Advanced":

            if key == curses.KEY_UP:

                advanced_selected = max(0, advanced_selected - 1)

            elif key == curses.KEY_DOWN:

                advanced_selected = min(1, advanced_selected + 1)

            elif key in (10, 13, curses.KEY_ENTER):

                if advanced_selected == 0:

                    timeout_selected = (

                        timeout_selected + 1

                    ) % len(TIMEOUT_MINUTES)

                    settings["screen_timeout"] = (

                        TIMEOUT_MINUTES[timeout_selected] * 60

                    )

                else:

                    selected_category = CATEGORIES.index("Main")

        elif category == "Exit":

            if key == curses.KEY_UP:

                exit_selected = (

                    exit_selected - 1

                ) % len(EXIT_OPTIONS)

            elif key == curses.KEY_DOWN:

                exit_selected = (

                    exit_selected + 1

                ) % len(EXIT_OPTIONS)

            elif key in (10, 13, curses.KEY_ENTER):

                if exit_selected == 0:

                    errors = apply_settings(settings)

                    if errors:

                        log("Apply errors: " + " | ".join(errors))

                        show_message(

                            stdscr,

                            "Some settings could not be applied:\n"

                            + "\n".join(errors[:8]),

                            "Save warning",

                        )

                    try:

                        persist_settings(settings)

                        log("Settings saved.")

                        return

                    except OSError as exc:

                        show_message(

                            stdscr, str(exc), "Save error"

                        )

                elif exit_selected == 1:

                    settings = saved_settings.copy()

                    log("Unsaved changes discarded.")

                    return

                elif exit_selected == 2:

                    settings = normalize_settings(DEFAULT_SETTINGS)

                    status_message = "Defaults restored in draft."

                elif exit_selected == 3:

                    settings = saved_settings.copy()

                    selected_category = CATEGORIES.index("Main")

                    exit_selected = 0

if __name__ == "__main__":

    try:

        curses.wrapper(main)

    except KeyboardInterrupt:

        pass
