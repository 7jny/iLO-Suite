# iLO Suite

[![Electron](https://img.shields.io/badge/Electron-33.x-47848F?logo=electron&logoColor=white)](https://www.electronjs.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Java](https://img.shields.io/badge/Java-8%20%2F%2021-ED8B00?logo=openjdk&logoColor=white)](https://adoptium.net/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2011%20%7C%2010-0078D6?logo=windows&logoColor=white)](https://microsoft.com)
[![Target](https://img.shields.io/badge/Hardware-HP%20iLO%203%20(ProLiant%20G7)-01A982?logo=hewlettpackardenterprise&logoColor=white)](https://www.hpe.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A modern, native desktop management suite engineered specifically for **HP Integrated Lights-Out 3 (iLO 3)** on **HP ProLiant G7 servers** (e.g. DL380 G7, DL360 G7, ML350 G7).

Bypasses modern Windows 11 / Windows 10 TLS 1.0 and legacy cipher deprecations (3DES, RC4) without lowering system-wide operating system security or installing legacy browsers.

---

## 🎯 The Problem & The Solution

- **The Problem**: Modern Windows 11/10 and contemporary browsers have completely disabled **TLS 1.0**, **3DES**, and **RC4** ciphers in Windows Schannel. When attempting to connect to an HP iLO 3 management controller, users experience SSL handshake timeouts, cipher mismatch errors, and broken Java applets or console timeouts.
- **The Solution**: **iLO Suite** bundles a transparent, high-performance local **Java TLS 1.0 Bridge** (`util.TlsBridge`) running on `127.0.0.1:8089` (HTTP) and `127.0.0.1:8443` (HTTPS). This bridges modern application requests to ancient iLO 3 controllers while keeping your primary Windows operating system completely secure.

---

## ✨ Features

### 1. 🖥️ Remote KVM Console (HPE Standalone Console Integration)
- **1-Click Launch**: Seamlessly starts the official **HPE Lights-Out Standalone Remote Console** (`HPLOCONS.exe`) tunneled through the local TLS 1.0 bridge.
- **HPE Standalone Console Download**: If you do not already have the official console installed, download it directly from HPE:
  - 👉 **[Download HPE Lights-Out Standalone Remote Console for Windows](https://support.hpe.com/connect/s/softwaredetails?softwareId=MTX_82b9ce35b5674c9ea9bd288e7b)** *(HPE SoftPaq / Standalone Installer)*
- **Self-Contained Java 21 Console**: Includes a secondary standalone Java DVC console client (`ilo3-console.jar`) with accelerated KVM display.

### 2. 📊 Real-Time Server Telemetry & Overview
- **Dual Hostnames Identification**: Prominently displays both:
  - **Server OS Hostname**: Operating system hostname reported by RIBCL (e.g. `WIN-CJPI8643PNM`).
  - **iLO Network Hostname & IP**: Management processor DNS name (e.g. `ILO-VMhost7`) and IP address.
- **Detailed Memory (RAM) Topology**:
  - Total Memory in GB (e.g. `128 GB RAM`).
  - Count of installed RAM modules (e.g. `16 sticks installed`).
  - Count of empty/free DIMM slots (e.g. `2 free slots`).
  - Total slot capacity (e.g. `18 Total Slots`).
  - Memory speed & type summary (e.g. `DDR3 @ 1333 MHz / 1600 MHz`).
  - Real-time DIMM slot map displaying each physical slot across CPU sockets.
- **Processors (CPU)**: Socket count, total physical cores, total execution threads, clock speed, and L1/L2/L3 cache sizes.
- **Chassis Power & Cooling**:
  - Real-time power draw in Watts (e.g. `169 Watts`).
  - Power Supply Units (PSU) status and redundancy mode.
  - Fan health, speed percentages, and redundancy status.
  - Temperature sensors (Ambient, CPU, Memory, System board).
- **Storage & Disks**: Physical drive bay status, detected disk models (e.g. Samsung SSD, Intenso SSD), and drive health.
- **Network Adapters**: 4x Gigabit NIC MAC addresses and dedicated iLO port MAC.

### 3. ⚡ Dedicated Power & Chassis Control
- **Color-Coded Power State**:
  - 🟢 **POWER ON**: Vibrant green with glowing status indicator.
  - 🔴 **POWER OFF**: Clean red indicator.
  - 🟡 **STARTING / RESETTING**: Amber/yellow pulsing indicator.
- **Power Actions**:
  - **Momentary Press**: Power button pulse (graceful ACPI OS shutdown or power-on).
  - **Power On**: Direct hardware power-on signal.
  - **Power Off**: Graceful shutdown signal.
  - **System Reset**: Motherboard warm reboot.
  - **Cold Boot**: Hard DC power cycle.
  - **Press & Hold (5s)**: Immediate forced power off with safety warning confirmation.
- **Unit Identification (UID) LED**:
  - Polled periodically every **5 seconds**.
  - Authentic blue pulsing indicator when active or flashing.
  - 1-click toggle to locate physical servers in datacenter racks.

### 4. 💿 Virtual Media (ISO Mounter & Local Streaming)
- Native Windows file picker to mount `.iso` images directly.
- Embedded local HTTP streaming server with HTTP 206 Partial Content range requests for bootable installations.
- Clean RIBCL sequence with automated stale media eject and boot option selection (`BOOT_ONCE`, `BOOT_ALWAYS`, `NO_BOOT`).

### 5. 🚀 Boot Manager
- **One-Time Boot Target**: Configure upcoming boot device (CD/DVD, USB, Hard Drive, PXE Network, or BIOS Setup F9).
- **Persistent Boot Order**: Reorder permanent boot priority and commit directly to server ROM.

### 6. 🌐 iLO Web Interface (Bridge Access)
- Local HTTP reverse proxy (`http://127.0.0.1:8089`) allowing original iLO 3 web interface access inside modern browsers (Chrome, Edge, Firefox) without SSL errors.

### 7. 📜 Integrated System Logs & Terminal
- Real-time stream of all backend API calls, TLS bridge packets, and launcher events.
- Monospace font (`JetBrains Mono`), level filtering (OK, INFO, WARN, ERROR), and instant search.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│              iLO Suite Native Desktop App               │
│          (Electron + Vanilla HTML5 / CSS / JS)          │
└──────────────┬───────────────────────────┬──────────────┘
               │ HTTP API                  │ Direct Launch
               ▼                           ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│    Python Backend (5050)    │   │  HPE Standalone Remote      │
│  - REST API & Orchestration │   │  Console (HPLOCONS.exe)     │
│  - RIBCL Telemetry Parser   │   └──────────────┬──────────────┘
│  - Virtual Media Streamer   │                  │ TLS 1.0 (8443)
└──────────────┬──────────────┘                  │
               │ HTTP (8089)                     │
               ▼                                 ▼
┌─────────────────────────────────────────────────────────┐
│               Java TLS 1.0 Bridge Engine                │
│  - SunJSSE Engine (Supports 3DES, RC4, Legacy RSA)      │
│  - Local HTTP Proxy :8089 ➔ Remote iLO :443             │
│  - Local HTTPS Bridge :8443 ➔ Remote iLO :443           │
└──────────────────────────────┬──────────────────────────┘
                               │ Legacy TLS 1.0
                               ▼
                ┌──────────────────────────────┐
                │     HP ProLiant G7 Server    │
                │     iLO 3 Controller (:443)  │
                └──────────────────────────────┘
```

---

## 📋 Prerequisites

1. **Operating System**: Windows 10 or Windows 11 (64-bit).
2. **Python**: Python 3.10 or higher installed with `python` available in your system `PATH`.
3. **Java Runtime**: Java JRE or JDK (Java 8+ or Java 21) with `java` or `javaw` in `PATH`.
4. **Node.js**: Node.js 18+ (required to run the Electron desktop app).
5. **HPE Standalone Console** *(Recommended for native KVM)*:
   - [Download HPE Lights-Out Standalone Remote Console (HPLOCONS)](https://support.hpe.com/connect/s/softwaredetails?softwareId=MTX_82b9ce35b5674c9ea9bd288e7b).

---

## 🚀 Installation & Quick Start

### 1. Clone the Repository
```powershell
git clone https://github.com/your-username/ilo3_vnc_win11.git
cd ilo3_vnc_win11
```

### 2. Install Node Dependencies
```powershell
npm install
```

### 3. Launch the Application
Launch iLO Suite as a clean native desktop application with zero console windows:

- **1-Click Native App**: Simply double-click **`iLO-Suite.exe`** in the root folder.
- **Terminal (Optional)**:
  ```powershell
  npm start
  ```

---

## 🔧 Port Allocation Table

| Port | Protocol | Purpose |
|---|---|---|
| `5050` | HTTP | Local Python REST API server |
| `8089` | HTTP | Java TLS 1.0 HTTP Bridge (Web GUI Proxy & RIBCL) |
| `8443` | HTTPS | Java TLS 1.0 HTTPS Bridge (Target for `HPLOCONS.exe`) |
| `8088` | HTTP | Virtual Media ISO HTTP Range Streaming Server |

---

## 🔒 Security Note

The TLS 1.0 Bridge only listens locally on `127.0.0.1`. It connects outward to your dedicated iLO management network without weakening Windows 11 system-wide cipher policies or modifying OS registry keys.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
HP, iLO, ProLiant, and HPLOCONS are registered trademarks of Hewlett Packard Enterprise Development LP. This software is an independent open-source tool and is not officially affiliated with or endorsed by HPE.
