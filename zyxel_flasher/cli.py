import argparse
import time
import sys
import serial
from .core import (
    MultibootBroadcaster,
    SingleSocketTFTPServer,
    list_serial_ports,
    list_network_interfaces
)

def run_cli():
    parser = argparse.ArgumentParser(
        description="Zyxel EX5601-T0 / MT7986 OpenWrt Bootloader Unlocker & Flasher CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--gui", action="store_true", help="Launch the graphical user interface")
    parser.add_argument("--list-ports", action="store_true", help="List available serial COM ports")
    parser.add_argument("--list-interfaces", action="store_true", help="List available network interfaces")
    parser.add_argument("--port", type=str, default="COM3", help="Serial port to use (default: COM3)")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate (default: 115200)")
    parser.add_argument("--iface", type=str, default="192.168.137.1", help="PC network interface IP")

    # Specific actions
    parser.add_argument("--zyeng", action="store_true", help="Broadcast zyeng Multiboot packets for 50 seconds")
    parser.add_argument("--intercept", action="store_true", help="Monitor serial and intercept bootloader into ZHAL/U-Boot")
    parser.add_argument("--dump-passwords", action="store_true", help="Dump hardware supervisor/admin/WiFi keys via ZHAL")
    parser.add_argument("--tftp-boot", action="store_true", help="Start TFTP server and boot openwrt.itb into RAM")
    parser.add_argument("--full-auto", action="store_true", help="Interactive step-by-step unlock and flashing guide")

    args = parser.parse_args()

    if args.list_ports:
        ports = list_serial_ports()
        print("Available serial ports:")
        for p in ports:
            print(f" - {p}")
        return

    if args.list_interfaces:
        ips = list_network_interfaces()
        print("Available network interfaces:")
        for ip in ips:
            print(f" - {ip}")
        return

    if args.zyeng:
        print(f"[+] Starting zyeng broadcast on {args.iface} for 50 seconds...")
        b = MultibootBroadcaster([args.iface], interval=0.05)
        b.start()
        print("[!] Please POWER ON the router now. Letting it boot for 50s...")
        try:
            for i in range(50, 0, -1):
                sys.stdout.write(f"\rRemaining: {i:02d}s | Packets sent: {b.packets_sent}")
                sys.stdout.flush()
                time.sleep(1)
        finally:
            b.stop()
        print("\n[+] Stage 1 complete! Debug flag set in NVRAM.")
        return

    if args.intercept:
        print(f"[+] Listening on {args.port} at {args.baud} baud. Waiting for reboot...")
        ser = serial.Serial(args.port, args.baud, timeout=0.02)
        start = time.time()
        buffer = ""
        last_space = 0
        try:
            while time.time() - start < 120:
                chunk = ser.read(512)
                if chunk:
                    text = chunk.decode("utf-8", errors="replace")
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    buffer += text
                    if "Hit any key" in buffer or any(f" {i} " in buffer[-20:] for i in range(0, 6)):
                        if time.time() - last_space > 0.08:
                            ser.write(b" ")
                            last_space = time.time()
                    if "ZHAL>" in buffer:
                        print("\n[+] Caught ZHAL prompt! Sending 'ATGU'...")
                        ser.write(b"ATGU\r\n")
                        buffer = ""
                        time.sleep(0.5)
                    if "MT7986>" in buffer:
                        print("\n\n" + "="*50)
                        print("[SUCCESS] REACHED MT7986 U-BOOT SHELL!")
                        print("="*50)
                        break
                time.sleep(0.005)
        finally:
            ser.close()
        return

    if args.dump_passwords:
        print(f"[+] Reading passwords from {args.port}...")
        ser = serial.Serial(args.port, args.baud, timeout=1.0)
        ser.write(b"\r\nATCK\r\n")
        time.sleep(0.5)
        out = ser.read(4096).decode("utf-8", errors="replace")
        ser.write(b"ATSH\r\n")
        time.sleep(0.5)
        out += ser.read(4096).decode("utf-8", errors="replace")
        ser.close()
        print("\n" + "="*50)
        print("DUMPED HARDWARE CREDENTIALS:")
        print("="*50)
        for line in out.splitlines():
            if any(k in line.lower() for k in ["supervisor password", "admin password", "wifi psk", "serial number", "first mac"]):
                print(line.strip())
        return

    # If no flags specified, launch GUI
    from .gui import ZyxelFlasherGUI
    app = ZyxelFlasherGUI()
    app.mainloop()
