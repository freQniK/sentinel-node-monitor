#!/usr/bin/env python3
"""
Sentinel Node Monitor
Monitors a list of Sentinel dVPN nodes and reports their status.
Sends Telegram alerts when nodes go offline.
Tracks uptime metrics over 1-day, 7-day, and 30-day windows.
Checks blockchain registration status via Sentinel API.
"""

import json
import time
import sys
import os
import signal
import requests
import urllib3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from collections import defaultdict

# Suppress InsecureRequestWarning for -k style requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "TOKEN"
TELEGRAM_CHAT_ID = "CHATID"
INPUT_FILE = "nodes.txt"
STATE_FILE = "node_state.json"
METRICS_FILE = "node_metrics.json"
REQUEST_TIMEOUT = 10          # seconds
POLL_INTERVAL = 60            # seconds between checks
SENTINEL_API = "https://api.sentinel.mathnodes.com"
# ─────────────────────────────────────────────────────────────────────

# Time windows in seconds
WINDOW_1D = 86400
WINDOW_7D = 604800
WINDOW_30D = 2592000

# ANSI color codes
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_RED  = "\033[41m"
    BG_GREEN = "\033[42m"

# ─────────────────────────────────────────────────────────────────────
# METRICS ENGINE
# ─────────────────────────────────────────────────────────────────────

class MetricsStore:
    """
    Stores per-node check results as timestamped entries.
    Each entry: {"t": <unix_timestamp>, "up": <bool>}
    Prunes data older than 30 days automatically.
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data: dict[str, list[dict]] = {}
        self._load()

    def _load(self):
        path = Path(self.filepath)
        if path.exists():
            try:
                with open(path, "r") as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.data = {}

    def save(self):
        with open(self.filepath, "w") as f:
            json.dump(self.data, f)

    def record(self, endpoint: str, timestamp: float, is_online: bool):
        """Record a single check result for a node."""
        if endpoint not in self.data:
            self.data[endpoint] = []
        self.data[endpoint].append({
            "t": timestamp,
            "up": is_online,
        })
        # Prune entries older than 30 days
        cutoff = timestamp - WINDOW_30D
        self.data[endpoint] = [
            e for e in self.data[endpoint] if e["t"] >= cutoff
        ]

    def get_uptime_percent(self, endpoint: str, now: float,
                           window_seconds: int) -> Optional[float]:
        """
        Calculate uptime percentage for a node within a time window.
        Returns None if no data exists in the window.
        """
        entries = self.data.get(endpoint, [])
        cutoff = now - window_seconds
        window_entries = [e for e in entries if e["t"] >= cutoff]
        if not window_entries:
            return None
        up_count = sum(1 for e in window_entries if e["up"])
        return (up_count / len(window_entries)) * 100.0

    def get_fleet_uptime(self, endpoints: list[str], now: float,
                         window_seconds: int) -> Optional[float]:
        """
        Calculate fleet-wide average uptime percentage.
        """
        percents = []
        for ep in endpoints:
            pct = self.get_uptime_percent(ep, now, window_seconds)
            if pct is not None:
                percents.append(pct)
        if not percents:
            return None
        return sum(percents) / len(percents)

    def get_total_checks_in_window(self, endpoint: str, now: float,
                                   window_seconds: int) -> int:
        entries = self.data.get(endpoint, [])
        cutoff = now - window_seconds
        return len([e for e in entries if e["t"] >= cutoff])

# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def load_endpoints(filepath: str) -> list[str]:
    """Load IP:PORT entries from a file, one per line."""
    path = Path(filepath)
    if not path.exists():
        print(f"{Color.RED}✗ File not found: {filepath}{Color.RESET}")
        print(f"  Create a file called '{filepath}' with one "
              f"IP:PORT per line.")
        sys.exit(1)

    endpoints = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                endpoints.append(line)

    if not endpoints:
        print(f"{Color.RED}✗ No endpoints found in {filepath}"
              f"{Color.RESET}")
        sys.exit(1)

    return endpoints

def load_state() -> dict:
    """Load persisted state from disk."""
    path = Path(STATE_FILE)
    if path.exists():
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def send_telegram_alert(moniker: str, endpoint: str,
                        alert_type: str = "offline"):
    """Send a Telegram message when a node goes offline or inactive."""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return None

    if alert_type == "inactive":
        message = (
            f"🟡 *Node Blockchain Inactive Alert*\n\n"
            f"**Moniker:** `{moniker}`\n"
            f"**Endpoint:** `{endpoint}`\n"
            f"**Time:** "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"The node is reachable but NOT active on the "
            f"blockchain."
        )
    else:
        message = (
            f"🔴 *Node Offline Alert*\n\n"
            f"**Moniker:** `{moniker}`\n"
            f"**Endpoint:** `{endpoint}`\n"
            f"**Time:** "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"The node has just gone offline."
        )

    url = (f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
           f"/sendMessage")
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except requests.RequestException:
        return False

def send_telegram_recovery(moniker: str, endpoint: str, downtime: str):
    """Send a Telegram message when a node comes back online."""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return

    message = (
        f"🟢 *Node Recovery*\n\n"
        f"**Moniker:** `{moniker}`\n"
        f"**Endpoint:** `{endpoint}`\n"
        f"**Downtime:** {downtime}\n"
        f"**Time:** "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"The node is back online."
    )

    url = (f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
           f"/sendMessage")
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        requests.post(url, json=payload, timeout=10)
    except requests.RequestException:
        pass

def send_telegram_chain_recovery(moniker: str, endpoint: str):
    """Send a Telegram message when a node becomes active on chain."""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return

    message = (
        f"🟢 *Node Blockchain Recovery*\n\n"
        f"**Moniker:** `{moniker}`\n"
        f"**Endpoint:** `{endpoint}`\n"
        f"**Time:** "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"The node is now active on the blockchain again."
    )

    url = (f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
           f"/sendMessage")
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        requests.post(url, json=payload, timeout=10)
    except requests.RequestException:
        pass

def query_node(endpoint: str) -> Optional[dict]:
    """
    Query a node's status endpoint (like curl -k).
    Returns parsed result dict on success, None on failure.
    """
    url = f"https://{endpoint}"
    try:
        resp = requests.get(
            url, timeout=REQUEST_TIMEOUT, verify=False
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") is True:
                return data.get("result", {})
    except (requests.RequestException, json.JSONDecodeError,
            ValueError):
        pass
    return None

def query_blockchain_status(node_address: str) -> Optional[str]:
    """
    Query the Sentinel blockchain API for a node's on-chain status.
    Returns the status string (e.g. 'active', 'inactive') or None.
    """
    url = (f"{SENTINEL_API}/sentinel/node/v3/nodes/{node_address}")
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            node_data = data.get("node", {})
            return node_data.get("status", None)
    except (requests.RequestException, json.JSONDecodeError,
            ValueError):
        pass
    return None

def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    td = timedelta(seconds=int(seconds))
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)

def uptime_color(pct: Optional[float]) -> str:
    """Return an ANSI color code based on uptime percentage."""
    if pct is None:
        return Color.DIM
    if pct >= 99.0:
        return Color.GREEN
    if pct >= 95.0:
        return Color.YELLOW
    return Color.RED

def format_uptime(pct: Optional[float]) -> str:
    """Format an uptime percentage with appropriate color."""
    if pct is None:
        return f"{Color.DIM}  N/A  {Color.RESET}"
    color = uptime_color(pct)
    return f"{color}{pct:6.2f}%{Color.RESET}"

def format_chain_status(status: Optional[str]) -> str:
    """Format the blockchain status with color coding."""
    if status is None:
        return f"{Color.DIM} Unknown   {Color.RESET}"
    if status == "active":
        return f"{Color.GREEN} Active    {Color.RESET}"
    if status == "inactive":
        return f"{Color.RED} Inactive  {Color.RESET}"
    # Other statuses
    display = status.capitalize()[:9].ljust(9)
    return f"{Color.YELLOW} {display}{Color.RESET}"

def uptime_bar(pct: Optional[float], width: int = 10) -> str:
    """Create a visual bar for uptime percentage."""
    if pct is None:
        return f"{Color.DIM}{'░' * width}{Color.RESET}"
    filled = int((pct / 100.0) * width)
    empty = width - filled
    color = uptime_color(pct)
    return (f"{color}{'█' * filled}"
            f"{Color.DIM}{'░' * empty}{Color.RESET}")

# ─────────────────────────────────────────────────────────────────────
# DISPLAY
# ─────────────────────────────────────────────────────────────────────

TABLE_WIDTH = 130

def print_header():
    w = TABLE_WIDTH
    inner = w - 2
    print(f"{Color.CYAN}{Color.BOLD}")
    print(f"╔{'═' * inner}╗")
    title = "🛰  SENTINEL NODE MONITOR  🛰"
    pad = inner - len(title)
    lpad = pad // 2
    rpad = pad - lpad
    print(f"║{' ' * lpad}{title}{' ' * rpad}║")
    print(f"╚{'═' * inner}╝")
    print(f"{Color.RESET}")

def print_node_table_header():
    print(f"{Color.BOLD}{Color.WHITE}")
    print("┌─────┬────────────────────────┬"
          "──────────────────────────┬───────────┬"
          "────────────────────────┬───────────┬"
          "─────────┬─────────┬─────────┐")
    print("│  #  │ IP Address             │"
          " Moniker                  │ Status    │"
          " Info                   │Blockchain │"
          "  1 Day  │  7 Day  │ 30 Day  │")
    print("├─────┼────────────────────────┼"
          "──────────────────────────┼───────────┼"
          "────────────────────────┼───────────┼"
          "─────────┼─────────┼─────────┤")
    print(f"{Color.RESET}", end="")

def print_node_table_footer():
    print(f"{Color.DIM}"
          "└─────┴────────────────────────┴"
          "──────────────────────────┴───────────┴"
          "────────────────────────┴───────────┴"
          "─────────┴─────────┴─────────┘"
          f"{Color.RESET}")

def print_node_row(index: int, endpoint: str, moniker: str,
                   is_online: bool, info: str,
                   chain_status: Optional[str],
                   up_1d: Optional[float],
                   up_7d: Optional[float],
                   up_30d: Optional[float]):
    idx_str = str(index).rjust(3)
    ep_str = endpoint.ljust(22)[:22]
    mon_str = moniker.ljust(24)[:24]

    if is_online:
        status = f"{Color.GREEN}● ONLINE {Color.RESET}"
    else:
        status = f"{Color.RED}● OFFLINE{Color.RESET}"

    info_str = info.ljust(22)[:22]
    chain_str = format_chain_status(chain_status)

    u1 = format_uptime(up_1d)
    u7 = format_uptime(up_7d)
    u30 = format_uptime(up_30d)

    print(f"│ {idx_str} │ {ep_str} │ {mon_str} │ "
          f"{status} │ {info_str} │{chain_str}│ "
          f"{u1} │ {u7} │ {u30} │")

def print_fleet_dashboard(endpoints: list[str],
                          metrics: MetricsStore,
                          now: float, online_count: int,
                          offline_count: int,
                          chain_active: int,
                          chain_inactive: int,
                          chain_unknown: int):
    """Print the fleet-wide metrics dashboard."""
    total = len(endpoints)

    fleet_1d = metrics.get_fleet_uptime(endpoints, now, WINDOW_1D)
    fleet_7d = metrics.get_fleet_uptime(endpoints, now, WINDOW_7D)
    fleet_30d = metrics.get_fleet_uptime(endpoints, now, WINDOW_30D)

    if total > 0:
        online_pct = (online_count / total) * 100
    else:
        online_pct = 0.0

    w = TABLE_WIDTH
    inner = w - 2

    print(f"{Color.BOLD}{Color.CYAN}")
    print(f"┌{'─' * inner}┐")
    title = "📊  FLEET DASHBOARD  📊"
    pad = inner - len(title)
    lpad = pad // 2
    rpad = pad - lpad - 2
    print(f"│{' ' * lpad}{title}{' ' * rpad}│")
    print(f"├{'─' * inner}┤")
    print(f"{Color.RESET}", end="")

    # Row 1: Current Status
    on_color = Color.GREEN if online_count > 0 else Color.DIM
    off_color = Color.RED if offline_count > 0 else Color.DIM
    ratio_color = Color.GREEN if online_pct >= 95 else (
        Color.YELLOW if online_pct >= 75 else Color.RED
    )

    status_line = (
        f"  {Color.BOLD}Current Status:{Color.RESET}"
        f"   {on_color}{Color.BOLD}{online_count}{Color.RESET}"
        f" online   "
        f"{off_color}{Color.BOLD}{offline_count}{Color.RESET}"
        f" offline   "
        f"{Color.DIM}of{Color.RESET} "
        f"{Color.BOLD}{total}{Color.RESET} total"
        f"     {ratio_color}{Color.BOLD}{online_pct:.1f}% "
        f"available now{Color.RESET}"
    )
    # We need to calculate visible length (without ANSI codes)
    # For simplicity, pad generously
    print(f"│{status_line}"
          + " " * 49 + f"│")

    # Row 2: Blockchain Status
    chain_act_color = Color.GREEN if chain_active > 0 else Color.DIM
    chain_inact_color = (Color.RED if chain_inactive > 0
                         else Color.DIM)
    chain_unk_color = (Color.YELLOW if chain_unknown > 0
                       else Color.DIM)

    chain_line = (
        f"  {Color.BOLD}Blockchain:{Color.RESET}"
        f"      {chain_act_color}{Color.BOLD}{chain_active}"
        f"{Color.RESET} active   "
        f"{chain_inact_color}{Color.BOLD}{chain_inactive}"
        f"{Color.RESET} inactive  "
        f"{chain_unk_color}{Color.BOLD}{chain_unknown}"
        f"{Color.RESET} unknown"
    )
    print(f"│{chain_line}"
          + " " * 76 + f"│")

    print(f"{Color.DIM}│{'─' * inner}│{Color.RESET}")

    # Row 3: Uptime Windows
    print(f"│  {Color.BOLD}Fleet Uptime:{Color.RESET}"
          + " " * (inner - 15) + "│")

    bar_1d = uptime_bar(fleet_1d, 20)
    val_1d = format_uptime(fleet_1d)
    print(f"│    {Color.WHITE}  1 Day:{Color.RESET}  "
          f"{bar_1d}  {val_1d}"
          + " " * 85 + "│")

    bar_7d = uptime_bar(fleet_7d, 20)
    val_7d = format_uptime(fleet_7d)
    print(f"│    {Color.WHITE}  7 Day:{Color.RESET}  "
          f"{bar_7d}  {val_7d}"
          + " " * 85 + "│")

    bar_30d = uptime_bar(fleet_30d, 20)
    val_30d = format_uptime(fleet_30d)
    print(f"│    {Color.WHITE} 30 Day:{Color.RESET}  "
          f"{bar_30d}  {val_30d}"
          + " " * 85 + "│")

    print(f"{Color.DIM}│{'─' * inner}│{Color.RESET}")

    # Row 4: Worst performers
    worst = []
    for ep in endpoints:
        pct = metrics.get_uptime_percent(ep, now, WINDOW_1D)
        if pct is not None:
            worst.append((ep, pct))
    worst.sort(key=lambda x: x[1])

    if worst and worst[0][1] < 100.0:
        print(f"│  {Color.BOLD}Lowest Uptime (24h):{Color.RESET}"
              + " " * (inner - 22) + "│")
        for ep, pct in worst[:3]:
            color = uptime_color(pct)
            ep_display = ep.ljust(22)[:22]
            print(f"│    {Color.RED}▼{Color.RESET} "
                  f"{ep_display}  {color}{pct:6.2f}%"
                  f"{Color.RESET}"
                  f"  {uptime_bar(pct, 15)}"
                  + " " * 74 + "│")
    else:
        print(f"│  {Color.GREEN}✓ All nodes at 100% "
              f"uptime in the last 24 hours{Color.RESET}"
              + " " * (inner - 49) + "│")

    print(f"{Color.DIM}└{'─' * inner}┘{Color.RESET}")

# ─────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────────────

def run_monitor():
    """Main monitoring loop."""
    endpoints = load_endpoints(INPUT_FILE)
    state = load_state()
    metrics = MetricsStore(METRICS_FILE)

    telegram_configured = (
        TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN_HERE"
    )
    cycle = 0

    print_header()
    print(f"  {Color.DIM}Loaded {Color.CYAN}{len(endpoints)}"
          f"{Color.DIM} endpoints from "
          f"{Color.CYAN}{INPUT_FILE}{Color.RESET}")
    print(f"  {Color.DIM}Telegram alerts: "
          f"{Color.GREEN + 'ENABLED' if telegram_configured else Color.YELLOW + 'DISABLED'}"
          f"{Color.RESET}")
    print(f"  {Color.DIM}Polling every "
          f"{Color.CYAN}{POLL_INTERVAL}s{Color.DIM} │ "
          f"Timeout {Color.CYAN}{REQUEST_TIMEOUT}s{Color.RESET}")
    print(f"  {Color.DIM}Metrics stored in "
          f"{Color.CYAN}{METRICS_FILE}{Color.RESET}")
    print(f"  {Color.DIM}Blockchain API: "
          f"{Color.CYAN}{SENTINEL_API}{Color.RESET}")
    print(f"  {Color.DIM}Press {Color.YELLOW}Ctrl+C"
          f"{Color.DIM} to stop{Color.RESET}")
    print()

    while True:
        cycle += 1
        now = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"  {Color.BLUE}━━━ Scan #{cycle} "
              f"at {now_str} ━━━{Color.RESET}")
        print()

        print_node_table_header()

        online_count = 0
        offline_count = 0
        chain_active_count = 0
        chain_inactive_count = 0
        chain_unknown_count = 0

        for i, endpoint in enumerate(endpoints, 1):
            ep_key = endpoint

            if ep_key not in state:
                state[ep_key] = {
                    "moniker": "Unknown",
                    "offline_since": None,
                    "alerted": False,
                    "node_addr": None,
                    "chain_status": None,
                    "chain_alerted": False,
                }

            # Ensure new state fields exist for older state files
            if "node_addr" not in state[ep_key]:
                state[ep_key]["node_addr"] = None
            if "chain_status" not in state[ep_key]:
                state[ep_key]["chain_status"] = None
            if "chain_alerted" not in state[ep_key]:
                state[ep_key]["chain_alerted"] = False

            result = query_node(endpoint)

            if result is not None:
                # ── NODE IS ONLINE ──
                online_count += 1
                moniker = result.get("moniker", "Unknown")
                node_addr = result.get("addr", None)
                state[ep_key]["moniker"] = moniker
                state[ep_key]["node_addr"] = node_addr

                metrics.record(ep_key, now, True)

                if state[ep_key]["offline_since"] is not None:
                    down_dur = (
                        now - state[ep_key]["offline_since"]
                    )
                    down_str = format_duration(down_dur)
                    send_telegram_recovery(
                        moniker, endpoint, down_str
                    )
                    info = f"Back! \u2193{down_str}"
                else:
                    location = result.get("location", {})
                    country = location.get("country_code", "??")
                    svc = result.get("service_type", "?")
                    peers = result.get("peers", 0)
                    info = f"{country} | {svc} | P:{peers}"

                state[ep_key]["offline_since"] = None
                state[ep_key]["alerted"] = False

                # ── BLOCKCHAIN STATUS CHECK ──
                chain_status = None
                if node_addr:
                    chain_status = query_blockchain_status(
                        node_addr
                    )

                # Track chain status transitions
                prev_chain = state[ep_key].get("chain_status")
                state[ep_key]["chain_status"] = chain_status

                if chain_status == "active":
                    chain_active_count += 1
                    # Recovery: was inactive, now active
                    if (prev_chain == "inactive"
                            and state[ep_key]["chain_alerted"]):
                        send_telegram_chain_recovery(
                            moniker, endpoint
                        )
                    state[ep_key]["chain_alerted"] = False
                elif chain_status == "inactive":
                    chain_inactive_count += 1
                    # Alert: first time going inactive
                    if not state[ep_key]["chain_alerted"]:
                        send_telegram_alert(
                            moniker, endpoint, "inactive"
                        )
                        state[ep_key]["chain_alerted"] = True
                else:
                    chain_unknown_count += 1

                up_1d = metrics.get_uptime_percent(
                    ep_key, now, WINDOW_1D)
                up_7d = metrics.get_uptime_percent(
                    ep_key, now, WINDOW_7D)
                up_30d = metrics.get_uptime_percent(
                    ep_key, now, WINDOW_30D)

                print_node_row(
                    i, endpoint, moniker, True, info,
                    chain_status,
                    up_1d, up_7d, up_30d
                )

            else:
                # ── NODE IS OFFLINE ──
                offline_count += 1
                moniker = state[ep_key].get("moniker", "Unknown")

                metrics.record(ep_key, now, False)

                if state[ep_key]["offline_since"] is None:
                    state[ep_key]["offline_since"] = now
                    info = "Just went offline"

                    if not state[ep_key]["alerted"]:
                        sent = send_telegram_alert(
                            moniker, endpoint, "offline"
                        )
                        state[ep_key]["alerted"] = True
                        if sent:
                            info = "Offline \u2192 TG sent"
                        elif telegram_configured:
                            info = "Offline \u2192 TG fail"
                else:
                    down_dur = (
                        now - state[ep_key]["offline_since"]
                    )
                    info = f"Down {format_duration(down_dur)}"

                # Still try blockchain check using cached addr
                chain_status = None
                cached_addr = state[ep_key].get("node_addr")
                if cached_addr:
                    chain_status = query_blockchain_status(
                        cached_addr
                    )

                state[ep_key]["chain_status"] = chain_status
                if chain_status == "active":
                    chain_active_count += 1
                elif chain_status == "inactive":
                    chain_inactive_count += 1
                else:
                    chain_unknown_count += 1

                up_1d = metrics.get_uptime_percent(
                    ep_key, now, WINDOW_1D)
                up_7d = metrics.get_uptime_percent(
                    ep_key, now, WINDOW_7D)
                up_30d = metrics.get_uptime_percent(
                    ep_key, now, WINDOW_30D)

                print_node_row(
                    i, endpoint, moniker, False, info,
                    chain_status,
                    up_1d, up_7d, up_30d
                )

        print_node_table_footer()
        print()

        # Fleet Dashboard
        print_fleet_dashboard(
            endpoints, metrics, now,
            online_count, offline_count,
            chain_active_count, chain_inactive_count,
            chain_unknown_count
        )
        print()

        # Persist
        save_state(state)
        metrics.save()

        # Countdown
        try:
            for remaining in range(POLL_INTERVAL, 0, -1):
                print(
                    f"\r  {Color.DIM}Next scan in "
                    f"{Color.CYAN}{remaining}s{Color.DIM}...  "
                    f"{Color.RESET}",
                    end="", flush=True,
                )
                time.sleep(1)
            print("\r" + " " * 40 + "\r", end="")
        except KeyboardInterrupt:
            raise

def main():
    """Entry point with graceful shutdown."""
    def signal_handler(sig, frame):
        print(f"\n\n  {Color.YELLOW}⚡ Shutting down "
              f"gracefully...{Color.RESET}\n")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    clear_screen()

    try:
        run_monitor()
    except KeyboardInterrupt:
        print(f"\n\n  {Color.YELLOW}⚡ Monitoring stopped."
              f"{Color.RESET}\n")
        sys.exit(0)

if __name__ == "__main__":
    main()
