# Sentinel Node Monitor

A powerful, real-time monitoring tool for Sentinel dVPN nodes with a beautiful console interface, uptime tracking, blockchain status verification, and Telegram alerting.

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey.svg)

---

## 📋 Table of Contents

- [Features](#-features)
- [Screenshots](#-screenshots)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Understanding the Output](#-understanding-the-output)
- [Telegram Alerts](#-telegram-alerts)
- [Data Files](#-data-files)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Real-time Monitoring** | Continuously polls your Sentinel nodes and displays live status |
| **Blockchain Verification** | Cross-references node availability with on-chain registration status |
| **Uptime Tracking** | Calculates and displays 1-day, 7-day, and 30-day uptime percentages |
| **Visual Dashboard** | Clean, color-coded console interface with progress bars and tables |
| **Telegram Alerts** | Instant notifications when nodes go offline, come back online, or become inactive on-chain |
| **Persistent Metrics** | Stores historical data for accurate uptime calculations across restarts |
| **Fleet Overview** | Aggregated statistics for your entire node fleet |
| **Graceful Handling** | Properly handles network timeouts, API failures, and shutdowns |

---

## 📸 Screenshots

![NodeMonitor](assets/screenshot.pngx)
---

## 📦 Requirements

- **Python 3.9** or higher
- **pip** (Python package manager)
- Network access to your Sentinel nodes
- Network access to`api.sentinel.mathnodes.com`
- *(Optional)* Telegram Bot for alerts

---

## 🚀 Installation

### Option 1: Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/sentinel-node-monitor.git
cd sentinel-node-monitor

# Install dependencies
pip install -r requirements.txt

# Create your nodes file
cp nodes.txt.example nodes.txt

# Edit with your node endpoints
nano nodes.txt
```

### Option 2: Manual Install

```bash
# Create a directory for the monitor
mkdir sentinel-monitor
cd sentinel-monitor

# Download the script
curl -O https://raw.githubusercontent.com/yourusername/sentinel-node-monitor/main/sentinel_monitor.py

# Install the required package
pip install requests

# Create your nodes file
touch nodes.txt
```

### Dependencies

Create a`requirements.txt` file:

```
requests>=2.28.0
urllib3>=1.26.0
```

Or install directly:

```bash
pip install requests
```

---

## ⚙️ Configuration

### Step 1: Create the Nodes File

Create a file named`nodes.txt` in the same directory as the script. Add one node endpoint per line in`IP:PORT` format:

```text
# Sentinel Node List
# Lines starting with # are comments

# US Nodes
45.76.88.12:8585
149.28.45.67:8585

# EU Nodes
185.123.45.67:8585
92.45.100.23:8585

# Asia Nodes
103.200.50.10:8585
```

### Step 2: Configure the Script

Open`sentinel_monitor.py` and modify the configuration section at the top:

```python
# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Your Telegram bot token
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"      # Your Telegram chat ID
INPUT_FILE = "nodes.txt"                     # Path to your nodes file
STATE_FILE = "node_state.json"               # State persistence file
METRICS_FILE = "node_metrics.json"           # Metrics history file
REQUEST_TIMEOUT = 10                         # Seconds to wait for node response
POLL_INTERVAL = 60                           # Seconds between monitoring cycles
SENTINEL_API = "https://api.sentinel.mathnodes.com"  # Blockchain API
# ─────────────────────────────────────────────────────────────────────
```

#### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
|`TELEGRAM_BOT_TOKEN` |`YOUR_BOT_TOKEN_HERE`| Your Telegram bot API token (see [Telegram Setup](#setting-up-telegram-alerts)) |
|`TELEGRAM_CHAT_ID` |`YOUR_CHAT_ID_HERE`| Your Telegram user or group chat ID |
|`INPUT_FILE` |`nodes.txt`| Path to the file containing node endpoints |
|`STATE_FILE` |`node_state.json`| File for storing node state between restarts |
|`METRICS_FILE` |`node_metrics.json`| File for storing historical uptime data |
|`REQUEST_TIMEOUT` |`10`| Maximum seconds to wait for a node to respond |
|`POLL_INTERVAL` |`60`| Seconds to wait between monitoring cycles |
|`SENTINEL_API` |`https://api.sentinel.mathnodes.com`| Sentinel blockchain API endpoint |

### Step 3: Set Up Telegram Alerts (Optional but Recommended)

#### Creating a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Start a chat and send`/newbot`
3. Follow the prompts to name your bot
4. Copy the **API token** provided (looks like`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

#### Finding Your Chat ID

1. Search for **@userinfobot** on Telegram
2. Start a chat with it
3. It will reply with your **numeric user ID** (e.g.,`987654321`)

#### For Group Notifications

1. Add your bot to the group
2. Send a message in the group
3. Visit:`https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find the`"chat":{"id":` value (negative number for groups)

#### Update the Script

```python
TELEGRAM_BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
TELEGRAM_CHAT_ID = "987654321"
```

---

## 🖥️ Usage

### Basic Usage

```bash
python sentinel_monitor.py
```

### Running in the Background

#### Using`screen`
```bash
# Start a new screen session
screen -S sentinel-monitor

# Run the monitor
python sentinel_monitor.py

# Detach with Ctrl+A, then D
# Reattach later with: screen -r sentinel-monitor
```

#### Using`tmux`
```bash
# Start a new tmux session
tmux new -s sentinel-monitor

# Run the monitor
python sentinel_monitor.py

# Detach with Ctrl+B, then D
# Reattach later with: tmux attach -t sentinel-monitor
```

### Stopping the Monitor

Press`Ctrl+C` for a graceful shutdown. The current state will be saved automatically.

---

## 📊 Understanding the Output

### Status Column

| Status | Meaning |
|--------|---------|
| 🟢`● ONLINE`| Node responded successfully within the timeout period |
| 🔴`● OFFLINE`| Node did not respond or returned an error |

### Info Column

| Info | Meaning |
|------|---------|
|`MX \| v2ray \| P:3`| Country code, service type, and peer count |
|`Just went offline`| Node just became unreachable this cycle |
|`Offline → TG sent`| Node went offline and Telegram alert was sent |
|`Down 2h 14m 32s`| Node has been offline for the displayed duration |
|`Back! ↓1h 30m`| Node just came back online after being down |

### Blockchain Column

| Status | Meaning |
|--------|---------|
| 🟢`Active`| Node is registered and active on the Sentinel blockchain |
| 🔴`Inactive`| Node is reachable but NOT active on the blockchain (requires attention!) |
| 🟡`Unknown`| Could not determine blockchain status (API unreachable or node address unknown) |

### Uptime Columns

| Color | Uptime Percentage |
|-------|-------------------|
| 🟢 Green | 99% or higher |
| 🟡 Yellow | 95% - 99% |
| 🔴 Red | Below 95% |
| ⚫ Gray | No data available |

---

## 📱 Telegram Alerts

The monitor sends four types of alerts:

### 🔴 Node Offline Alert
Sent when a node becomes unreachable.

```
🔴 Node Offline Alert

Moniker: Francisco Madero
Endpoint: 147.78.1.167:52618
Time: 2024-03-20 15:30:45

The node has just gone offline.
```

### 🟢 Node Recovery Alert
Sent when an offline node comes back online.

```
🟢 Node Recovery

Moniker: Francisco Madero
Endpoint: 147.78.1.167:52618
Downtime: 1h 23m 45s
Time: 2024-03-20 16:54:30

The node is back online.
```

### 🟡 Blockchain Inactive Alert
Sent when a node is reachable but not active on the blockchain.

```
🟡 Node Blockchain Inactive Alert

Moniker: Francisco Madero
Endpoint: 147.78.1.167:52618
Time: 2024-03-20 15:30:45

The node is reachable but NOT active on the blockchain.
```

### 🟢 Blockchain Recovery Alert
Sent when a node becomes active on the blockchain again.

```
🟢 Node Blockchain Recovery

Moniker: Francisco Madero
Endpoint: 147.78.1.167:52618
Time: 2024-03-20 16:00:00

The node is now active on the blockchain again.
```

**Note:** Alerts are sent only once per event to prevent spam. You won't receive repeated alerts for the same offline/inactive event.

---

## 📁 Data Files

The monitor creates and maintains the following files:

###`node_state.json`

Stores the current state of each node:

```json
{
  "147.78.1.167:52618": {
    "moniker": "Francisco Madero",
    "offline_since": null,
    "alerted": false,
    "node_addr": "sentnode1zfxp8grjtx06xq920rmu7agsmc3jyxa9lq3kms",
    "chain_status": "active",
    "chain_alerted": false
  }
}
```

| Field | Purpose |
|-------|---------|
|`moniker`| Last known node name |
|`offline_since`| Unix timestamp when node went offline (null if online) |
|`alerted`| Whether an offline alert has been sent |
|`node_addr`| Cached blockchain address for the node |
|`chain_status`| Last known blockchain status |
|`chain_alerted`| Whether a blockchain inactive alert has been sent |

###`node_metrics.json`

Stores historical check results for uptime calculations:

```json
{
  "147.78.1.167:52618": [
    {"t": 1710950400.0, "up": true},
    {"t": 1710950460.0, "up": true},
    {"t": 1710950520.0, "up": false}
  ]
}
```

- Data older than 30 days is automatically pruned
- Each entry records a timestamp (`t`) and online status (`up`)

---

## 🔧 Troubleshooting

### Common Issues

#### "File not found: nodes.txt"

```bash
# Create the nodes file
touch nodes.txt

# Add at least one endpoint
echo "147.78.1.167:52618" >> nodes.txt
```

#### "No endpoints found in nodes.txt"

Make sure your`nodes.txt` file:
- Contains at least one IP:PORT entry
- Doesn't have all lines commented out with`#`
- Uses the correct format:`IP:PORT` (e.g.,`147.78.1.167:52618`)

#### Nodes showing as offline but they're running

1. **Check the port**: Ensure you're using the correct port number
2. **Check firewall**: The node's port must be accessible from your monitoring machine
3. **Increase timeout**: Try increasing`REQUEST_TIMEOUT` to 15 or 20 seconds
4. **Test manually**:
```bash
   curl -k https://147.78.1.167:52618
   ```

#### Telegram alerts not working

1. **Verify bot token**: Make sure there are no extra spaces
2. **Verify chat ID**: Ensure it's the numeric ID, not username
3. **Test the bot**: Send a test message:
```bash
   curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
        -d "chat_id=<CHAT_ID>&text=Test"
   ```
4. **Start the bot**: Make sure you've sent`/start` to your bot

#### "Unknown" blockchain status for all nodes

1. **Check API access**:
```bash
   curl https://api.sentinel.mathnodes.com/sentinel/node/v3/nodes/sentnode1...
   ```
2. **Check network**: Ensure outbound HTTPS is allowed
3. **API may be down**: The Sentinel API might be temporarily unavailable

#### High CPU usage

Increase`POLL_INTERVAL` to reduce check frequency:

```python
POLL_INTERVAL = 120  # Check every 2 minutes instead of 1
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Ideas for Contributions

- [ ] Web dashboard interface
- [ ] Email alerts in addition to Telegram
- [ ] Discord webhook support
- [ ] Export metrics to Prometheus/Grafana
- [ ] Historical uptime charts
- [ ] Multi-threaded node checking for large fleets
- [ ] Configuration file support (YAML/TOML)
- [ ] Docker container

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 🙏 Acknowledgments

- [Sentinel Network](https://sentinel.co/) - Decentralized VPN network
- [MathNodes](https://mathnodes.com/) - Sentinel developer

---



<p align="center">
  Made with ❤️ by freQniK
</p>
