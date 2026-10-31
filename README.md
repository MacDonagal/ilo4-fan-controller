# iLO4 Fan Controller for HP Gen8 Servers

<p align="center">
  <img width="400" src="readme/screenshot.png" alt="iLO4 Fan Controller web UI">
  <br>
  <i>Freely manage your HP's fan speeds; anywhere, any time!</i>
</p>

A small web UI and REST API to control the fans of HP ProLiant Gen8 servers through a
modded iLO4 firmware, with a hardened Docker image and a ready-to-use Home Assistant package.

> [!WARNING]
> **Silencing an enterprise server can overheat it.** In `lock` mode the iLO can no longer
> speed the fans up, whatever the temperatures. A DL360p Gen8 with fans locked at 25 % had its
> Smart Array P420i controller (sensor `31-HD Controller`) reach 110 °C and power off, in a
> 24 °C room. Prefer the **`min` mode** (see [Fan modes](#fan-modes)) and keep an eye on your
> temperatures.

---

## Table of contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick start (Docker Compose)](#quick-start-docker-compose)
- [Configuration](#configuration)
- [Fan modes](#fan-modes)
- [REST API](#rest-api)
- [Home Assistant](#home-assistant)
- [Other installation methods](#other-installation-methods)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [How it works](#how-it-works)
- [The idea](#the-idea)

## Features

- 🌀 Web UI: per-fan or all-at-once speeds, presets (Quiet / Normal / Turbo), unlock button
- 🛡️ Two fan modes: **`min`** (speed floor, iLO keeps regulating) and **`lock`** (fixed speed)
- 🔌 REST API for scripts and home automation
- 🐳 Hardened Docker image: standalone Next.js build, non-root user, `tini`, healthcheck,
  read-only filesystem, Docker secrets support (`*_FILE` variables)
- 🏠 Home Assistant package: fan and temperature sensors, speed slider, A/C automations,
  overheat safety net on **every** iLO sensor

## Requirements

- An HP ProLiant **Gen8** server with **iLO4**
- iLO4 firmware flashed with
  _["The Fan Hack"](https://www.reddit.com/r/homelab/comments/hix44v/silence_of_the_fans_pt_2_hp_ilo_4_273_now_with/)_
  (it provides the `fan` SSH commands)
- An iLO user allowed to use SSH and the Redfish API
- Docker + Docker Compose (or Node.js 24 for a bare-metal install)

Tested on a **DL360p Gen8** (8 fan blocks).

## Quick start (Docker Compose)

1. Clone the repository:

   ```bash
   git clone https://github.com/DavidIlie/ilo4-fan-controller
   cd ilo4-fan-controller
   ```

2. Store the iLO password in a secret file. The app runs as **UID 1001** and Compose mounts
   the file with its host permissions, so it must be readable by that user:

   ```bash
   echo -n 'your-ilo-password' > ilo_password.txt
   sudo chown 1001:1001 ilo_password.txt && sudo chmod 400 ilo_password.txt
   ```

3. Edit [`docker-compose.yaml`](docker-compose.yaml): set `ILO_HOST`, `ILO_USERNAME` and,
   if needed, the host port (`"3000:3000"`, left side only).

4. Build and start:

   ```bash
   docker compose up -d --build
   ```

5. Check it is running and can talk to the iLO:

   ```bash
   docker compose ps                         # should become "healthy"
   curl -s http://localhost:3000/api/health  # {"status":"ok"}
   curl -s http://localhost:3000/api/fans    # your fans and their speeds
   ```

Then open `http://<docker-host>:3000`.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `ILO_HOST` | ✅ | iLO IP address or hostname (ex. `192.168.1.69`) |
| `ILO_USERNAME` | ✅ | iLO user |
| `ILO_PASSWORD` | ✅ | iLO password |
| `ILO_HOST_FILE`, `ILO_USERNAME_FILE`, `ILO_PASSWORD_FILE` | | Read the value from a file instead (Docker secrets) |
| `PORT` | | Port the app listens on inside the container (default `3000`) |

## Fan modes

| Mode | iLO commands | Behavior |
|---|---|---|
| **`min`** (recommended) | `unlock`, `max 255`, `min <speed>` | The speed is a **floor**: fans never go below it, but the iLO can still spin them up when a component gets hot |
| `lock` | `lock <speed>` | The speed is **fixed**: iLO thermal regulation is **disabled** until you unlock |

- In the web UI, pick the mode with the **Mode** selector (`Minimum` is the default and is
  remembered by your browser).
- In the API, `mode` defaults to `lock` for backward compatibility: pass `"mode": "min"`
  explicitly.
- **Unlock** gives the fans back to the iLO automatic regulation.

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/fans` | Current fans as reported by the iLO (`{"fans": [...]}`) |
| `POST` | `/api/fans` | Set speeds: `{"fans": [30, 30, ...], "mode": "min"}` (one value per fan, 10-100 %) |
| `POST` | `/api/fans/unlock` | Give fan control back to the iLO |
| `GET` | `/api/health` | Liveness check, does **not** contact the iLO |

Setting speeds runs one SSH command per fan (three in `min` mode), so it can take 10-20 seconds.

```bash
BASE_URL="http://ilo-fan-controller.local:3000"

# Read the fans (name + speed)
curl -s "$BASE_URL/api/fans" | jq '.fans[] | {FanName, CurrentReading}'

# 30 % floor on 8 fans, iLO keeps regulating
curl -s -X POST "$BASE_URL/api/fans" \
  -H 'Content-Type: application/json' \
  -d '{"fans":[30,30,30,30,30,30,30,30],"mode":"min"}'

# Back to full iLO automatic control
curl -s -X POST "$BASE_URL/api/fans/unlock"
```

## Home Assistant

[`examples/home-assistant/ilo4_fans.yaml`](examples/home-assistant/ilo4_fans.yaml) is a
ready-to-use [package](https://www.home-assistant.io/docs/configuration/packages/):

- **Sensors**: average / max fan speed, inlet temperature, hottest CPU, RAID controller
  temperature, **thermal margin** (smallest gap between any sensor and its own critical
  threshold) and the name of the hottest sensor
- **Slider** to set the fan floor (`min` mode)
- **Script** to give control back to the iLO
- **Automations**:
  - room too hot → A/C on (cool, 24 °C) + 50 % fan floor
  - room back to normal → A/C off + iLO automatic mode
  - **safety net**: any sensor less than 15 °C from its critical threshold, or temperatures
    unavailable → fans at 100 %, with a notification

Setup:

1. Copy the file to `/config/packages/` and enable packages in `configuration.yaml`:

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

2. Add the secrets listed at the top of the file to `/config/secrets.yaml`.
3. Adapt the entity ids (A/C, sensors) and thresholds to your setup.
4. Check the configuration, then restart Home Assistant.

### A/C control with an IR blaster

[`examples/home-assistant/smartir/climate.yaml`](examples/home-assistant/smartir/climate.yaml)
creates a `climate` entity with [SmartIR](https://github.com/smartHomeHub/SmartIR) and a
Broadlink RM Mini. SmartIR profile **1390** (Midea RG52C1/BGE remote) is tested with a
**Domo DO263A** mobile A/C. Many Midea-made units should work with it too.

## Other installation methods

### docker run

```bash
docker build -t local/ilo4-fan-controller:latest-local .

docker run -d \
  --name=ilo4-fan-controller \
  -p 3000:3000 \
  -e ILO_HOST='192.168.1.69' \
  -e ILO_USERNAME='your-username' \
  -e ILO_PASSWORD='your-password' \
  --restart unless-stopped \
  local/ilo4-fan-controller:latest-local
```

This works the same with Portainer, Rancher, Kubernetes, etc.

### Directly with Node.js

```bash
cp .env.template .env   # then fill in ILO_HOST, ILO_USERNAME, ILO_PASSWORD
yarn                    # install dependencies
yarn build              # build the Next.js app
yarn start              # or run it with systemd / pm2
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ILO_PASSWORD_FILE points to an unreadable file` | The secret file must be readable by UID 1001: `chown 1001:1001 ilo_password.txt && chmod 400 ilo_password.txt`, then `docker compose up -d --force-recreate` |
| `curl` returns nothing | Check the host port in `docker-compose.yaml` (`"<host>:3000"`) and `docker compose ps` / `docker compose logs` |
| "Oops! Couldn't talk to iLO" | Wrong `ILO_HOST` or credentials, or the container cannot reach the iLO network |
| Manual Redfish requests return an empty body | The iLO redirects: use `curl -L` and the `/redfish/v1/chassis/1/Thermal` path |
| SSH to the iLO refused by a recent OpenSSH client | `ssh -o KexAlgorithms=+diffie-hellman-group14-sha1 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa user@ilo` |
| Fans stuck at a low speed | Unlock them: `POST /api/fans/unlock`, `fan p global unlock` over SSH, or reset the iLO |

To list every temperature sensor with its thresholds:

```bash
curl -skL -u 'user:password' https://<ilo>/redfish/v1/chassis/1/Thermal \
  | jq -c '.Temperatures[] | {Name, ReadingCelsius, UpperThresholdCritical}'
```

## Security

- There is **no authentication**: keep it on your LAN, or put it behind an authentication
  proxy such as [Authelia](https://github.com/authelia/authelia)
  ([Kubernetes guide](https://github.com/DavidIlie/kubernetes-setup/tree/master/8%20-%20authelia)).
  It wouldn't be fun for someone to put your server fans at 100 %, or 10 %, whilst you're not home.
- Prefer the `ILO_PASSWORD_FILE` secret over a plain-text password, and never commit
  `ilo_password.txt` (it is git-ignored).
- The iLO uses a self-signed certificate, so TLS verification is disabled for Redfish calls.

## How it works

- On page load, Next.js `getServerSideProps` reads the fans from the iLO Redfish API
  (`/redfish/v1/chassis/1/Thermal`). Fans are parsed dynamically, so any number of fans works.
- Applying settings or a preset opens an SSH session to the iLO and runs the `fan p …`
  commands provided by the fan hack.

## The idea

HP offers enterprise servers which are normally supposed to be in some sort of datacenter
environment, where things such as fan speed are not really a concern. When old HPE servers are
decommissioned and put on the used market, people like myself buy these servers to have them
part of our _Home Datacenter_.

These servers can easily start sounding like an airplane taking off in your house, so modified
firmwares of the server's IPMI system (iLO4) have been created to manage the fan speeds via SSH.
But when your power goes off and you need to change the fan speed from your phone, that's a
whole different story. The main inspiration for this project was
[this post on r/homelab](https://www.reddit.com/r/homelab/comments/rcel73/i_created_a_web_page_to_manage_the_fans_of_my/),
but I decided to create my own so that I can make it as customizable as possible and not have
it restricted to some models.
