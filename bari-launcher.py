#!/usr/bin/env python3
"""
Minecraft Turtle Launcher
A simple, all-in-one Minecraft Java launcher using Python's turtle graphics.
Requires: pip install minecraft-launcher-lib requests
"""

import turtle
import threading
import subprocess
import sys
import os
import json
import time
import tkinter as tk
from tkinter import simpledialog, messagebox

# ── Auto-install dependencies ──────────────────────────────────────────────────
def ensure_deps():
    pkgs = ["minecraft-launcher-lib", "requests"]
    for pkg in pkgs:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--break-system-packages", "-q"])

ensure_deps()

import requests
import minecraft_launcher_lib as mclib

# ── Config ─────────────────────────────────────────────────────────────────────
MC_DIR       = os.path.expanduser("~/.minecraft")
CONFIG_FILE  = os.path.join(MC_DIR, "turtle_launcher.json")
os.makedirs(MC_DIR, exist_ok=True)

# ── Palette ────────────────────────────────────────────────────────────────────
BG          = "#1a1a2e"
PANEL       = "#16213e"
GREEN       = "#4ade80"
GREEN_DK    = "#16a34a"
GRASS       = "#5a9e3a"
DIRT        = "#8B5E3C"
STONE       = "#6b7280"
STONE_LT    = "#9ca3af"
SKY         = "#87CEEB"
WHITE       = "#f0fdf4"
GRAY        = "#374151"
GRAY_LT     = "#6b7280"
YELLOW      = "#facc15"
RED         = "#ef4444"
ORANGE      = "#f97316"

# ── State ──────────────────────────────────────────────────────────────────────
state = {
    "versions":      [],
    "selected_idx":  0,
    "username":      "",
    "status":        "Loading versions…",
    "progress":      0.0,
    "progress_msg":  "",
    "log_lines":     [],
    "installing":    False,
    "launching":     False,
    "scroll_offset": 0,
    "loader_filter": "all",   # all | release | snapshot | forge | fabric | quilt | neoforge
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            d = json.load(f)
            state["username"] = d.get("username", "")

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump({"username": state["username"]}, f)

# ── Version fetching ───────────────────────────────────────────────────────────
MODDED_VERSIONS = {
    "fabric": [],
    "forge":  [],
    "quilt":  [],
    "neoforge": [],
}

def fetch_versions():
    try:
        vanilla = mclib.utils.get_version_list()
        state["versions"] = vanilla

        # Fabric
        try:
            r = requests.get("https://meta.fabricmc.net/v2/versions/loader", timeout=8)
            fabric_loaders = r.json()
            r2 = requests.get("https://meta.fabricmc.net/v2/versions/game", timeout=8)
            fabric_games = [g["version"] for g in r2.json() if g.get("stable")]
            MODDED_VERSIONS["fabric"] = [
                {"id": f"fabric-loader-{fabric_loaders[0]['version']}-{gv}",
                 "type": "fabric", "mc": gv}
                for gv in fabric_games[:20]
            ]
        except Exception:
            pass

        # Forge (just list supported MC versions from API)
        try:
            r = requests.get("https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json", timeout=8)
            promos = r.json().get("promos", {})
            forge_entries = []
            seen = set()
            for key, version in promos.items():
                mc_ver = key.replace("-latest", "").replace("-recommended", "")
                label = f"forge-{mc_ver}-{version}"
                if label not in seen:
                    seen.add(label)
                    forge_entries.append({"id": label, "type": "forge", "mc": mc_ver})
            MODDED_VERSIONS["forge"] = forge_entries[:20]
        except Exception:
            pass

        # Quilt
        try:
            r = requests.get("https://meta.quiltmc.org/v3/versions/game", timeout=8)
            quilt_games = [g["version"] for g in r.json() if g.get("stable", True)]
            r2 = requests.get("https://meta.quiltmc.org/v3/versions/loader", timeout=8)
            ql = r2.json()[0]["version"] if r2.json() else "0.26.0"
            MODDED_VERSIONS["quilt"] = [
                {"id": f"quilt-loader-{ql}-{gv}", "type": "quilt", "mc": gv}
                for gv in quilt_games[:20]
            ]
        except Exception:
            pass

        # NeoForge
        try:
            r = requests.get("https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml", timeout=8)
            import re
            versions = re.findall(r"<version>([^<]+)</version>", r.text)
            neo_entries = []
            seen = set()
            for v in reversed(versions[-40:]):
                parts = v.split(".")
                mc_ver = f"1.{parts[0]}.{parts[1]}" if len(parts) >= 2 else v
                label = f"neoforge-{v}"
                if mc_ver not in seen:
                    seen.add(mc_ver)
                    neo_entries.append({"id": label, "type": "neoforge", "mc": mc_ver})
            MODDED_VERSIONS["neoforge"] = neo_entries[:20]
        except Exception:
            pass

        state["status"] = f"Ready — {len(state['versions'])} versions available"
    except Exception as e:
        state["status"] = f"Error loading versions: {e}"

# ── Drawing helpers ────────────────────────────────────────────────────────────
def rect(t, x, y, w, h, fill, outline=None):
    t.penup()
    t.goto(x, y)
    t.pendown()
    t.fillcolor(fill)
    if outline:
        t.pencolor(outline)
        t.pensize(2)
    else:
        t.pencolor(fill)
        t.pensize(1)
    t.begin_fill()
    for _ in range(2):
        t.forward(w)
        t.right(90)
        t.forward(h)
        t.right(90)
    t.end_fill()
    t.penup()

def text(t, x, y, s, color=WHITE, size=12, bold=False, align="left"):
    t.penup()
    t.goto(x, y)
    style = ("Arial", size, "bold" if bold else "normal")
    t.pencolor(color)
    t.write(s, align=align, font=style)

def mc_block(t, x, y, size, top_color, side_color):
    """Draw a simple isometric-ish block icon."""
    rect(t, x, y, size, size, top_color)
    rect(t, x, y - size, size, size // 3, side_color)

# ── UI Regions ─────────────────────────────────────────────────────────────────
W, H = 860, 580
HALF = W // 2

# ── Main draw ──────────────────────────────────────────────────────────────────
def draw_all(t):
    t.clear()
    t.speed(0)
    t.hideturtle()

    # Background
    rect(t, -W//2, H//2, W, H, BG)

    # ── Left Panel: Version List ───────────────────────────────────────────────
    rect(t, -W//2, H//2, HALF - 10, H, PANEL)

    # Title bar
    rect(t, -W//2, H//2, HALF - 10, 50, GRASS)
    text(t, -W//2 + 14, H//2 - 36, "⛏  Minecraft Launcher", WHITE, 15, bold=True)

    # Filter buttons
    filters = ["all", "release", "snapshot", "fabric", "forge", "quilt", "neoforge"]
    btn_w = 72
    bx = -W//2 + 8
    by = H//2 - 62
    for f in filters:
        active = state["loader_filter"] == f
        rect(t, bx, by, btn_w - 4, 20, GREEN_DK if active else GRAY, GREEN if active else STONE)
        text(t, bx + (btn_w - 4)//2, by - 16, f.capitalize(), WHITE if active else STONE_LT, 9, align="center")
        bx += btn_w

    # Version list
    visible_versions = get_filtered_versions()
    list_y_start = H//2 - 90
    row_h = 32
    visible_rows = 12
    offset = state["scroll_offset"]

    for i in range(visible_rows):
        idx = i + offset
        if idx >= len(visible_versions):
            break
        v = visible_versions[idx]
        vy = list_y_start - i * row_h
        selected = (idx == state["selected_idx"])

        row_color = GREEN_DK if selected else (PANEL if i % 2 == 0 else "#1e2a3a")
        rect(t, -W//2 + 4, vy, HALF - 22, row_h - 2, row_color)

        # type badge
        vtype = v.get("type", "release")
        badge_color = {
            "release":  GREEN_DK,
            "snapshot": ORANGE,
            "old_beta": STONE,
            "old_alpha": STONE,
            "fabric":   "#7c3aed",
            "forge":    "#b45309",
            "quilt":    "#0e7490",
            "neoforge": "#be185d",
        }.get(vtype, STONE)

        rect(t, -W//2 + 6, vy - 4, 70, 22, badge_color)
        text(t, -W//2 + 8, vy - 20, vtype[:8], WHITE, 8)
        text(t, -W//2 + 82, vy - 22, v["id"][:30], WHITE if selected else STONE_LT, 11, bold=selected)

    # Scrollbar hint
    if len(visible_versions) > visible_rows:
        text(t, -W//2 + 8, list_y_start - visible_rows * row_h - 10,
             f"↑↓ scroll  ({offset+1}–{min(offset+visible_rows, len(visible_versions))} of {len(visible_versions)})",
             GRAY_LT, 9)

    # ── Right Panel ────────────────────────────────────────────────────────────
    rx = -W//2 + HALF + 10
    rect(t, rx, H//2, HALF - 10, H, PANEL)

    # Grass / dirt decoration
    rect(t, rx, H//2, HALF - 10, 8, GRASS)
    rect(t, rx, H//2 - 8, HALF - 10, 14, DIRT)

    # Minecraft logo text
    text(t, rx + (HALF - 10)//2, H//2 - 55, "MINECRAFT", YELLOW, 26, bold=True, align="center")
    text(t, rx + (HALF - 10)//2, H//2 - 80, "Java Edition Launcher", STONE_LT, 10, align="center")

    # Block decorations
    for bx_, col1, col2 in [
        (rx + 20,        GRASS,  DIRT),
        (rx + HALF - 60, GRASS,  DIRT),
    ]:
        rect(t, bx_,      H//2 - 100, 28, 28, col1)
        rect(t, bx_,      H//2 - 128, 28, 28, col2)

    # Selected version info
    sel = get_selected_version()
    iy = H//2 - 120
    if sel:
        rect(t, rx + 10, iy, HALF - 30, 90, GRAY)
        text(t, rx + 20, iy - 18, "Selected Version", STONE_LT, 9)
        text(t, rx + 20, iy - 38, sel["id"][:30], WHITE, 12, bold=True)
        vtype = sel.get("type", "release")
        installed = check_installed(sel["id"])
        text(t, rx + 20, iy - 58, f"Type: {vtype}", STONE_LT, 10)
        text(t, rx + 20, iy - 76, "✓ Installed" if installed else "✗ Not installed",
             GREEN if installed else RED, 10)

    # Username display
    uy = H//2 - 225
    rect(t, rx + 10, uy, HALF - 30, 38, GRAY)
    text(t, rx + 20, uy - 14, "Username:", STONE_LT, 9)
    text(t, rx + 20, uy - 30, state["username"] or "(click Set Username)", WHITE, 11, bold=True)

    # Progress bar
    py = H//2 - 278
    rect(t, rx + 10, py, HALF - 30, 22, GRAY)
    if state["progress"] > 0:
        bar_w = int((HALF - 34) * state["progress"])
        rect(t, rx + 12, py - 2, bar_w, 18, GREEN)
    text(t, rx + (HALF - 10)//2, py - 18, state["progress_msg"][:38], STONE_LT, 8, align="center")

    # Buttons
    buttons = [
        ("Set Username",    rx + 10,      H//2 - 315, HALF//2 - 20, 34, STONE,    WHITE),
        ("Install Version", rx + HALF//2, H//2 - 315, HALF//2 - 20, 34, GREEN_DK, WHITE),
        ("▶  LAUNCH",      rx + 10,      H//2 - 360, HALF - 30,    40, GREEN,    BG),
    ]
    for label, bx2, b_y, bw, bh, bg2, fg in buttons:
        rect(t, bx2, b_y, bw, bh, bg2, WHITE)
        text(t, bx2 + bw//2, b_y - bh + 8, label, fg, 12, bold=True, align="center")

    # Log area
    log_y = H//2 - 410
    rect(t, rx + 10, log_y, HALF - 30, 90, "#0d1117")
    text(t, rx + 20, log_y - 14, "Log", STONE_LT, 9)
    for li, line in enumerate(state["log_lines"][-5:]):
        text(t, rx + 14, log_y - 26 - li * 13, line[:44], STONE_LT, 8)

    # Status bar
    rect(t, -W//2, -H//2 + 24, W, 24, GRAY)
    text(t, 0, -H//2 + 6, state["status"], WHITE, 10, align="center")

    # Keybinds hint
    text(t, -W//2 + 8, -H//2 + 6, "↑↓: scroll  Enter: launch  I: install  U: username", STONE_LT, 8)

# ── Helpers ────────────────────────────────────────────────────────────────────
def get_filtered_versions():
    f = state["loader_filter"]
    if f == "all":
        vanilla = list(state["versions"])
        modded = []
        for lst in MODDED_VERSIONS.values():
            modded.extend(lst)
        return vanilla + modded
    elif f in ("release", "snapshot", "old_beta", "old_alpha"):
        return [v for v in state["versions"] if v.get("type") == f]
    else:
        return MODDED_VERSIONS.get(f, [])

def get_selected_version():
    versions = get_filtered_versions()
    idx = state["selected_idx"]
    if 0 <= idx < len(versions):
        return versions[idx]
    return None

def check_installed(version_id):
    path = os.path.join(MC_DIR, "versions", version_id, f"{version_id}.json")
    return os.path.exists(path)

def add_log(msg):
    state["log_lines"].append(msg)
    if len(state["log_lines"]) > 50:
        state["log_lines"].pop(0)

# ── Actions ────────────────────────────────────────────────────────────────────
def do_set_username(screen):
    root = screen.getcanvas().winfo_toplevel()
    name = simpledialog.askstring("Username", "Enter your Minecraft username:", parent=root)
    if name and name.strip():
        state["username"] = name.strip()
        save_config()
        add_log(f"Username set to: {state['username']}")

def do_install(screen):
    sel = get_selected_version()
    if not sel:
        state["status"] = "No version selected."
        return
    vtype = sel.get("type", "release")
    vid = sel["id"]

    if vtype in ("fabric", "forge", "quilt", "neoforge"):
        root = screen.getcanvas().winfo_toplevel()
        messagebox.showinfo("Modded Install",
            f"To install {vtype} ({vid}), use the official installer:\n\n"
            f"• Fabric: https://fabricmc.net/use/installer/\n"
            f"• Forge:  https://files.minecraftforge.net/\n"
            f"• Quilt:  https://quiltmc.org/install/\n"
            f"• NeoForge: https://neoforged.net/\n\n"
            f"Then relaunch this launcher and select the installed version.",
            parent=root)
        return

    if state["installing"]:
        state["status"] = "Already installing…"
        return

    state["installing"] = True
    state["status"] = f"Installing {vid}…"
    add_log(f"Starting install: {vid}")

    def _install():
        try:
            def on_progress(current, total, status):
                state["progress_msg"] = status[:40] if status else ""
                state["progress"] = current / total if total else 0
                state["status"] = f"Installing {vid}: {status}"

            callback = {
                "setStatus":   lambda s: on_progress(state["progress"], 1, s),
                "setProgress": lambda c: None,
                "setMax":      lambda m: None,
            }
            mclib.install.install_minecraft_version(vid, MC_DIR, callback=callback)
            state["status"]   = f"✓ Installed {vid}"
            state["progress"] = 1.0
            state["progress_msg"] = "Done!"
            add_log(f"Installed: {vid}")
        except Exception as e:
            state["status"] = f"Install failed: {e}"
            add_log(f"Error: {e}")
        finally:
            state["installing"] = False

    threading.Thread(target=_install, daemon=True).start()

def do_launch():
    sel = get_selected_version()
    if not sel:
        state["status"] = "No version selected."
        return
    vid = sel["id"]
    if not state["username"]:
        state["status"] = "Set a username first!"
        return
    if not check_installed(vid):
        state["status"] = f"{vid} is not installed. Install it first."
        return
    if state["launching"]:
        return

    state["launching"] = True
    state["status"] = f"Launching {vid}…"
    add_log(f"Launching: {vid} as {state['username']}")

    def _launch():
        try:
            opts = mclib.utils.generate_test_options()
            opts["username"]   = state["username"]
            opts["uuid"]       = "00000000000000000000000000000000"
            opts["token"]      = ""
            opts["gameDir"]    = MC_DIR
            opts["version"]    = vid

            cmd = mclib.command.get_minecraft_command(vid, MC_DIR, opts)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            state["status"] = f"▶ Running {vid}"
            for line in proc.stdout:
                add_log(line.strip()[:60])
            proc.wait()
            state["status"] = f"Game exited (code {proc.returncode})"
            add_log(f"Exited with code {proc.returncode}")
        except Exception as e:
            state["status"] = f"Launch failed: {e}"
            add_log(f"Error: {e}")
        finally:
            state["launching"] = False

    threading.Thread(target=_launch, daemon=True).start()

# ── Input handling ─────────────────────────────────────────────────────────────
def make_click_handler(screen, t):
    def on_click(x, y):
        rx = -W//2 + HALF + 10
        # Filter buttons
        filters = ["all", "release", "snapshot", "fabric", "forge", "quilt", "neoforge"]
        btn_w = 72
        bx = -W//2 + 8
        by = H//2 - 62
        for f in filters:
            if bx <= x <= bx + btn_w - 4 and by - 20 <= y <= by:
                state["loader_filter"] = f
                state["selected_idx"]  = 0
                state["scroll_offset"] = 0
            bx += btn_w

        # Version list click
        list_y_start = H//2 - 90
        row_h = 32
        visible_rows = 12
        if -W//2 + 4 <= x <= -W//2 + HALF - 18:
            for i in range(visible_rows):
                vy = list_y_start - i * row_h
                if vy - row_h + 2 <= y <= vy:
                    idx = i + state["scroll_offset"]
                    versions = get_filtered_versions()
                    if 0 <= idx < len(versions):
                        state["selected_idx"] = idx

        # Right panel buttons
        uy = H//2 - 315
        # Set Username
        if rx + 10 <= x <= rx + 10 + HALF//2 - 20 and uy - 34 <= y <= uy:
            do_set_username(screen)
        # Install Version
        if rx + HALF//2 <= x <= rx + HALF - 20 and uy - 34 <= y <= uy:
            do_install(screen)
        # Launch
        if rx + 10 <= x <= rx + HALF - 20 and H//2 - 400 <= y <= H//2 - 360:
            do_launch()

        draw_all(t)
    return on_click

def setup_keys(screen, t):
    def scroll_up():
        if state["scroll_offset"] > 0:
            state["scroll_offset"] -= 1
            if state["selected_idx"] > state["scroll_offset"] + 11:
                state["selected_idx"] = state["scroll_offset"] + 11
        draw_all(t)

    def scroll_down():
        versions = get_filtered_versions()
        if state["scroll_offset"] < len(versions) - 12:
            state["scroll_offset"] += 1
            if state["selected_idx"] < state["scroll_offset"]:
                state["selected_idx"] = state["scroll_offset"]
        draw_all(t)

    def sel_up():
        if state["selected_idx"] > 0:
            state["selected_idx"] -= 1
            if state["selected_idx"] < state["scroll_offset"]:
                state["scroll_offset"] = state["selected_idx"]
        draw_all(t)

    def sel_down():
        versions = get_filtered_versions()
        if state["selected_idx"] < len(versions) - 1:
            state["selected_idx"] += 1
            if state["selected_idx"] >= state["scroll_offset"] + 12:
                state["scroll_offset"] = state["selected_idx"] - 11
        draw_all(t)

    def launch_key():
        do_launch()
        draw_all(t)

    def install_key():
        do_install(screen)
        draw_all(t)

    def username_key():
        do_set_username(screen)
        draw_all(t)

    screen.onkey(sel_up,      "Up")
    screen.onkey(sel_down,    "Down")
    screen.onkey(scroll_up,   "Prior")   # Page Up
    screen.onkey(scroll_down, "Next")    # Page Down
    screen.onkey(launch_key,  "Return")
    screen.onkey(install_key, "i")
    screen.onkey(install_key, "I")
    screen.onkey(username_key,"u")
    screen.onkey(username_key,"U")
    screen.listen()

# ── Refresh loop ───────────────────────────────────────────────────────────────
def refresh_loop(screen, t):
    draw_all(t)
    screen.ontimer(lambda: refresh_loop(screen, t), 800)

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    load_config()

    screen = turtle.Screen()
    screen.title("⛏  Minecraft bari`s Turtle Launcher")
    screen.bgcolor(BG)
    screen.setup(width=W, height=H)
    screen.tracer(0)

    t = turtle.Turtle()
    t.hideturtle()
    t.speed(0)

    # Initial draw
    state["status"] = "Fetching version list…"
    draw_all(t)
    screen.update()

    # Fetch versions in background
    threading.Thread(target=lambda: (fetch_versions(), draw_all(t), screen.update()), daemon=True).start()

    # Bind input
    screen.onclick(make_click_handler(screen, t))
    setup_keys(screen, t)

    # Start refresh loop
    screen.ontimer(lambda: refresh_loop(screen, t), 800)

    screen.mainloop()

if __name__ == "__main__":
    main()
