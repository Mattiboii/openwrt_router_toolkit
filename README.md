# OpenWrt Router Toolkit (`openwrt_router_toolkit`)

An open-source toolkit and comprehensive guide to recovering, unlocking password-protected bootloaders, dumping OEM credentials, and permanently flashing OpenWrt (`ubootmod` layout) on **Zyxel EX5601-T0 / T-56** and MediaTek Filogic routers.

Includes both a **modern graphical interface (GUI)** and a **headless command-line interface (CLI)**.

---

## ⚡ Features

* **GUI & CLI Modes:** Run the interactive GUI wizard or execute automated headless CLI commands.
* **Bootloader Password Bypass:** Implements the `zyeng` Multiboot UDP exploit (`225.0.0.0:5631`) to set `EngDebugFlag=1` without knowing the ISP or supervisor password.
* **Credentials Extractor:** Dumps unique hardware credentials (`supervisor password`, `admin password`, `factory Wi-Fi key`, MAC addresses, serial number) directly from the `ZHAL>` bootbase.
* **Zero-Config Embedded TFTP Server:** Built-in single-socket RFC 1350 TFTP server that avoids standard Windows Firewall blocks.
* **Automated RAM & Permanent Flashing:** Boots OpenWrt recovery in RAM, unlocks write-protected MTD blocks via `kmod-mtd-rw`, attaches UBI, flashes OpenWrt BL2 preloader and BL31 FIP bootloader, and runs `sysupgrade`.

---

## 🖥️ Graphical Interface (GUI)

To launch the graphical wizard:
```bash
python main.py
# or explicitly:
python main.py --gui
```

### GUI Workflow:
1. **Connection Bar:** Select your USB-Serial COM port (auto-refreshed) and PC network interface.
2. **Step 1 — Start `zyeng` (Broadcast):** Power ON the router and let it boot normally for ~50s to inject `EngDebugFlag=1` into NVRAM.
3. **Step 2 — Intercept U-Boot (ZHAL):** Power-cycle the router; the tool automatically hammers the space bar, catches `ZHAL>`, and runs `ATGU` to unlock the MediaTek U-Boot prompt (`MT7986>`).
4. **Step 3 — Dump Hardware Keys:** Reads and displays your unique supervisor, admin, and Wi-Fi passwords with a one-click copy button.
5. **Step 4 — Boot OpenWrt in RAM:** Launches the embedded TFTP server and loads `openwrt.itb` into RAM (`bootm 0x46000000`).
6. **Step 5 — Flash OpenWrt (Permanent):** Repartitions flash and executes the permanent `ubootmod` sysupgrade.

---

## 💻 Command-Line Interface (CLI)

For headless systems, servers, or automated scripting:

```bash
# Show all available options
python main.py --help

# List available serial COM ports and network interfaces
python main.py --list-ports
python main.py --list-interfaces

# Step 1: Run zyeng broadcaster on specific interface
python main.py --zyeng --iface 192.168.137.1

# Step 2: Intercept bootloader on COM port
python main.py --intercept --port COM3

# Step 3: Dump hardware credentials
python main.py --dump-passwords --port COM3
```

---

## 🛠️ Hardware Specifications

| Component | Specification |
| :--- | :--- |
| **SoC** | MediaTek MT7986A (Filogic 830), Quad-Core ARM Cortex-A53 @ 2.0 GHz |
| **RAM** | 1024 MB (1 GB) DDR4 |
| **Flash** | 512 MB SPI-NAND (Macronix MX35LF4GE4AD) |
| **Ethernet** | 1x 2.5 GbE (Maxlinear GPY211C), 4x 1 GbE (MediaTek MT7531 switch), 1x 2.5 GbE SFP slot |
| **Wireless** | Wi-Fi 6 (802.11ax) 4x4 2.4 GHz + 4x4 5 GHz (MediaTek MT7975 / MT7976) |
| **UART Pinout** | 3.3V TTL, 115200 8N1 (TX, RX, GND on J1 header) |

---

## 🔌 Physical Connection Setup

1. **Serial Connection:** Connect a 3.3V USB-to-UART adapter to the router's internal serial header (`TX` to `RX`, `RX` to `TX`, `GND` to `GND`). Set baud rate to **115200 8N1**.
2. **Ethernet Connection:** Connect an Ethernet cable from your PC to **LAN 2** (the second yellow 1G port). *Note: The bootloader only enables LAN 2 during initial boot stages.*

---

## 📦 Required OpenWrt Assets

Place the following official OpenWrt 23.05.5 `ubootmod` assets in the project directory:
* `openwrt-23.05.5-mediatek-filogic-zyxel_ex5601-t0-ubootmod-initramfs-recovery.itb` (copy as `openwrt.itb`)
* `openwrt-23.05.5-mediatek-filogic-zyxel_ex5601-t0-ubootmod-bl31-uboot.fip`
* `openwrt-23.05.5-mediatek-filogic-zyxel_ex5601-t0-ubootmod-preloader.bin`
* `openwrt-23.05.5-mediatek-filogic-zyxel_ex5601-t0-ubootmod-squashfs-sysupgrade.itb`
* `kmod-mtd-rw_5.15.167+git-20160214-2_aarch64_cortex-a53.ipk`

---

## 🌐 Accessing OpenWrt After Flashing

* **Web UI (LuCI):** [http://192.168.1.1](http://192.168.1.1) (or secondary alias [http://192.168.137.2](http://192.168.137.2))
* **SSH:** `ssh root@192.168.1.1`
* **Default Password:** None (set on first login).
* **Usable Overlay Storage:** ~395 MB free for packages (`opkg install ...`).

---

## 📜 Credits & License
* Multiboot protocol vulnerability discovery and `zyeng.c`: **Bjørn Mork (`bmork`)**
* `ubootmod` layout documentation and recovery procedure: **Nikolay Dandanov (`ndandanov`)** and **`konus`** (OpenWrt forums).
* Toolkit implementation and documentation: Open source community.
* License: GPL-2.0 / MIT.
