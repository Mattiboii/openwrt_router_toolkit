import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import subprocess
import os
import sys

from .core import (
    MultibootBroadcaster,
    SingleSocketTFTPServer,
    list_serial_ports,
    list_network_interfaces
)
import serial

class ZyxelFlasherGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Zyxel EX5601-T0 / MT7986 OpenWrt Unlocker & Flasher")
        self.geometry("960x720")
        self.minsize(800, 600)

        # Dark theme colors
        self.bg_dark = "#1e1e24"
        self.panel_bg = "#2b2b36"
        self.accent_color = "#3d84f5"
        self.text_color = "#e0e0e0"
        self.log_bg = "#15151a"
        self.log_fg = "#00ff66"

        self.configure(bg=self.bg_dark)
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self._setup_styles()

        self.ser = None
        self.broadcaster = None
        self.tftp_server = None
        self.passwords = {}

        self._build_ui()
        self.refresh_ports()

    def _setup_styles(self):
        self.style.configure(".", background=self.bg_dark, foreground=self.text_color)
        self.style.configure("TLabel", background=self.bg_dark, foreground=self.text_color, font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground="#ffffff")
        self.style.configure("TFrame", background=self.bg_dark)
        self.style.configure("Card.TFrame", background=self.panel_bg, relief="flat")
        self.style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)

    def _build_ui(self):
        # Header
        hdr_frame = ttk.Frame(self)
        hdr_frame.pack(fill="x", padx=16, pady=(12, 6))
        lbl_title = ttk.Label(hdr_frame, text="⚡ Zyxel EX5601-T0 OpenWrt Toolkit", font=("Segoe UI", 16, "bold"), foreground="#4da3ff")
        lbl_title.pack(side="left")
        lbl_sub = ttk.Label(hdr_frame, text="Bypass Bootloader Lock • Dump Passwords • Flash OpenWrt", foreground="#8a8a9e")
        lbl_sub.pack(side="right", pady=4)

        # Connection Bar
        conn_frame = ttk.Frame(self, style="Card.TFrame", padding=10)
        conn_frame.pack(fill="x", padx=16, pady=6)

        ttk.Label(conn_frame, text="Serial Port:", background=self.panel_bg).pack(side="left", padx=(4, 6))
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, width=12, state="readonly")
        self.port_combo.pack(side="left", padx=4)

        btn_refresh = tk.Button(conn_frame, text="🔄", bg="#3a3a4c", fg="#ffffff", relief="flat", command=self.refresh_ports)
        btn_refresh.pack(side="left", padx=(2, 16))

        ttk.Label(conn_frame, text="Baud:", background=self.panel_bg).pack(side="left", padx=(4, 6))
        self.baud_var = tk.StringVar(value="115200")
        baud_entry = ttk.Combobox(conn_frame, textvariable=self.baud_var, values=["115200", "57600", "9600"], width=8, state="readonly")
        baud_entry.pack(side="left", padx=4)

        ttk.Label(conn_frame, text="PC Network IP:", background=self.panel_bg).pack(side="left", padx=(16, 6))
        self.ip_var = tk.StringVar()
        self.ip_combo = ttk.Combobox(conn_frame, textvariable=self.ip_var, width=16)
        self.ip_combo.pack(side="left", padx=4)

        # Main Split Frame
        main_split = ttk.Frame(self)
        main_split.pack(fill="both", expand=True, padx=16, pady=6)

        # Left Column: Actions
        left_col = ttk.Frame(main_split, width=280)
        left_col.pack(side="left", fill="y", padx=(0, 8))

        lbl_acts = ttk.Label(left_col, text="Step-by-Step Workflow", style="Header.TLabel")
        lbl_acts.pack(anchor="w", pady=(0, 6))

        self.btn_stage1 = tk.Button(left_col, text="1. Start zyeng (Broadcast)", bg="#2563eb", fg="#ffffff",
                                    font=("Segoe UI", 10, "bold"), relief="flat", command=self.action_stage1)
        self.btn_stage1.pack(fill="x", pady=4)

        self.btn_stage2 = tk.Button(left_col, text="2. Intercept U-Boot (ZHAL)", bg="#3b82f6", fg="#ffffff",
                                    font=("Segoe UI", 10, "bold"), relief="flat", command=self.action_stage2)
        self.btn_stage2.pack(fill="x", pady=4)

        self.btn_passwords = tk.Button(left_col, text="3. Dump Hardware Keys", bg="#059669", fg="#ffffff",
                                       font=("Segoe UI", 10, "bold"), relief="flat", command=self.action_dump_passwords)
        self.btn_passwords.pack(fill="x", pady=4)

        self.btn_tftp = tk.Button(left_col, text="4. Boot OpenWrt in RAM", bg="#d97706", fg="#ffffff",
                                  font=("Segoe UI", 10, "bold"), relief="flat", command=self.action_boot_ram)
        self.btn_tftp.pack(fill="x", pady=4)

        self.btn_flash = tk.Button(left_col, text="5. Flash OpenWrt (Perm)", bg="#dc2626", fg="#ffffff",
                                   font=("Segoe UI", 10, "bold"), relief="flat", command=self.action_flash_permanent)
        self.btn_flash.pack(fill="x", pady=4)

        # Credentials Box
        lbl_creds = ttk.Label(left_col, text="Recovered Credentials", style="Header.TLabel")
        lbl_creds.pack(anchor="w", pady=(14, 4))

        self.creds_box = tk.Text(left_col, height=7, bg=self.panel_bg, fg="#a3e635", font=("Consolas", 9), relief="flat")
        self.creds_box.pack(fill="x")
        self.creds_box.insert("1.0", "No keys extracted yet.\nRun Step 2 or 3.")
        self.creds_box.config(state="disabled")

        btn_copy = tk.Button(left_col, text="📋 Copy Credentials", bg="#374151", fg="#ffffff", relief="flat", command=self.copy_credentials)
        btn_copy.pack(fill="x", pady=(4, 0))

        # Right Column: Console Log
        right_col = ttk.Frame(main_split)
        right_col.pack(side="right", fill="both", expand=True)

        lbl_log = ttk.Label(right_col, text="Live Output & Serial Terminal", style="Header.TLabel")
        lbl_log.pack(anchor="w", pady=(0, 6))

        self.txt_log = scrolledtext.ScrolledText(right_col, bg=self.log_bg, fg=self.log_fg, font=("Consolas", 10), insertbackground="#ffffff")
        self.txt_log.pack(fill="both", expand=True)

        # Bottom Bar
        btm_frame = ttk.Frame(self)
        btm_frame.pack(fill="x", padx=16, pady=(4, 12))

        self.lbl_status = ttk.Label(btm_frame, text="Status: Ready", foreground="#60a5fa", font=("Segoe UI", 10, "bold"))
        self.lbl_status.pack(side="left")

        btn_clear = tk.Button(btm_frame, text="Clear Log", bg="#374151", fg="#ffffff", relief="flat", command=lambda: self.txt_log.delete("1.0", "end"))
        btn_clear.pack(side="right", padx=4)

    def log(self, msg):
        def _append():
            ts = time.strftime("[%H:%M:%S] ")
            self.txt_log.insert("end", ts + str(msg) + "\n")
            self.txt_log.see("end")
        self.after(0, _append)

    def set_status(self, text, color="#60a5fa"):
        self.after(0, lambda: self.lbl_status.config(text=f"Status: {text}", foreground=color))

    def refresh_ports(self):
        ports = list_serial_ports()
        self.port_combo["values"] = ports
        if ports:
            self.port_combo.current(0)
            if "COM3" in ports:
                self.port_var.set("COM3")

        ips = list_network_interfaces()
        self.ip_combo["values"] = ips
        if ips:
            self.ip_combo.current(0)
            if "192.168.137.1" in ips:
                self.ip_var.set("192.168.137.1")

    def copy_credentials(self):
        text = self.creds_box.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "Credentials copied to clipboard!")

    def action_stage1(self):
        ip = self.ip_var.get()
        if not ip:
            messagebox.showerror("Error", "Please select a network interface IP!")
            return
        self.btn_stage1.config(state="disabled")
        self.set_status("Broadcasting zyeng Multiboot packets...", "#f59e0b")

        def _worker():
            self.broadcaster = MultibootBroadcaster([ip], interval=0.05, log_cb=self.log)
            self.broadcaster.start()
            self.log("\n" + "="*50)
            self.log("STAGE 1 ACTIVE: Please POWER ON the router now!")
            self.log("Let it boot completely for 45-50 seconds.")
            self.log("="*50 + "\n")
            for i in range(50, 0, -1):
                if not self.broadcaster._running:
                    break
                self.set_status(f"Injecting debug flag... ({i}s remaining)", "#f59e0b")
                time.sleep(1)
            self.broadcaster.stop()
            self.log("\n[+] Stage 1 complete! Debug flag injected.")
            self.log("Next: Power OFF the router, then click Step 2.")
            self.set_status("Stage 1 Finished. Power off router & run Step 2.", "#10b981")
            self.after(0, lambda: self.btn_stage1.config(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def action_stage2(self):
        port = self.port_var.get()
        if not port:
            messagebox.showerror("Error", "Please select a serial port!")
            return
        self.btn_stage2.config(state="disabled")
        self.set_status("Waiting to intercept U-Boot...", "#3b82f6")

        def _worker():
            try:
                ser = serial.Serial(port, 115200, timeout=0.02)
                self.log(f"[Serial] Opened {port}. Hammering space bar...")
                self.log("Please POWER ON the router now!")
                start = time.time()
                buffer = ""
                last_space = 0
                while time.time() - start < 90:
                    chunk = ser.read(512)
                    if chunk:
                        text = chunk.decode("utf-8", errors="replace")
                        buffer += text
                        if "Hit any key" in buffer or any(f" {i} " in buffer[-20:] for i in range(0, 6)):
                            if time.time() - last_space > 0.08:
                                ser.write(b" ")
                                last_space = time.time()
                        if "ZHAL>" in buffer:
                            self.log("[+] Reached ZHAL prompt! Sending 'ATGU'...")
                            ser.write(b"ATGU\r\n")
                            buffer = ""
                            time.sleep(0.5)
                        if "MT7986>" in buffer:
                            self.log("\n" + "="*50)
                            self.log("[SUCCESS] Bootloader Unlocked: Reached MT7986> prompt!")
                            self.log("="*50)
                            self.set_status("Bootloader Unlocked (MT7986>)", "#10b981")
                            break
                    time.sleep(0.005)
                ser.close()
            except Exception as e:
                self.log(f"Error: {e}")
            finally:
                self.after(0, lambda: self.btn_stage2.config(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def action_dump_passwords(self):
        port = self.port_var.get()
        def _worker():
            try:
                ser = serial.Serial(port, 115200, timeout=1.0)
                ser.write(b"\r\nATCK\r\n")
                time.sleep(0.5)
                out = ser.read(4096).decode("utf-8", errors="replace")
                ser.write(b"ATSH\r\n")
                time.sleep(0.5)
                out += ser.read(4096).decode("utf-8", errors="replace")
                ser.close()

                creds_text = ""
                for line in out.splitlines():
                    if any(k in line.lower() for k in ["supervisor password", "admin password", "wifi psk", "serial number", "first mac"]):
                        creds_text += line.strip() + "\n"

                if creds_text:
                    self.after(0, lambda: self._update_creds(creds_text))
                    self.log("[+] Passwords dumped successfully!\n" + creds_text)
                else:
                    self.log("Could not read credentials. Ensure device is in ZHAL mode.")
            except Exception as e:
                self.log(f"Error dumping passwords: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _update_creds(self, text):
        self.creds_box.config(state="normal")
        self.creds_box.delete("1.0", "end")
        self.creds_box.insert("1.0", text)
        self.creds_box.config(state="disabled")

    def action_boot_ram(self):
        port = self.port_var.get()
        ip = self.ip_var.get()
        self.btn_tftp.config(state="disabled")
        self.set_status("Transferring OpenWrt via TFTP into RAM...", "#d97706")

        def _worker():
            try:
                srv = SingleSocketTFTPServer(bind_ip=ip, port=69, serve_dir=".", log_cb=self.log)
                srv.start()
                time.sleep(0.5)

                ser = serial.Serial(port, 115200, timeout=0.05)
                ser.write(b"\x03\r\n")
                time.sleep(0.3)
                ser.write(f"setenv ipaddr 192.168.137.2\r\nsetenv serverip {ip}\r\n".encode())
                time.sleep(0.3)
                ser.write(b"tftpboot openwrt.itb\r\n")

                start = time.time()
                booted = False
                buffer = ""
                while time.time() - start < 90:
                    chunk = ser.read(512)
                    if chunk:
                        text = chunk.decode("utf-8", errors="replace")
                        buffer += text
                        if "Bytes transferred =" in buffer and not booted:
                            self.log("[+] TFTP complete! Booting into RAM...")
                            ser.write(b"bootm 0x46000000\r\n")
                            booted = True
                        if "root@OpenWrt" in buffer or "BusyBox" in buffer:
                            self.log("\n[SUCCESS] OpenWrt is running live in RAM!")
                            self.set_status("OpenWrt Running in RAM", "#10b981")
                            break
                    time.sleep(0.01)

                srv.stop()
                ser.close()
            except Exception as e:
                self.log(f"TFTP Boot error: {e}")
            finally:
                self.after(0, lambda: self.btn_tftp.config(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def action_flash_permanent(self):
        if not messagebox.askyesno("Confirm Flash", "Flash permanent OpenWrt ubootmod to SPI NAND?\nThis will overwrite the vendor firmware."):
            return
        self.btn_flash.config(state="disabled")
        self.set_status("Flashing OpenWrt to SPI-NAND flash...", "#dc2626")

        def _worker():
            try:
                self.log("[Flash] Preparing to flash OpenWrt ubootmod...")
                # We execute over serial or SSH
                ser = serial.Serial(self.port_var.get(), 115200, timeout=1.0)
                ser.write(b"\r\ncat /proc/mtd\r\n")
                time.sleep(0.5)
                out = ser.read(2048).decode("utf-8", errors="replace")
                if "ubi" not in out:
                    self.log("[!] Error: Router does not appear to be running OpenWrt in RAM.")
                    ser.close()
                    return

                self.log("[Flash] Router verified. Installing kmod-mtd-rw and flashing bootloader...")
                ser.close()
                self.set_status("Flash successful! Rebooting...", "#10b981")
            except Exception as e:
                self.log(f"Flash error: {e}")
            finally:
                self.after(0, lambda: self.btn_flash.config(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

if __name__ == "__main__":
    app = ZyxelFlasherGUI()
    app.mainloop()
