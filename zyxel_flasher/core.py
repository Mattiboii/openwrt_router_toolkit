import socket
import struct
import time
import threading
import serial
import serial.tools.list_ports
import os
import sys

# Multiboot packet definition
DEST_MULTICAST = "225.0.0.0"
DEST_BROADCAST = "255.255.255.255"
DEST_PORT = 5631

ZYENG_PACKET = struct.pack(
    ">4sHIIIHBB2sB7s1024s",
    b"zyx\x00",
    0,
    0,
    0x400,
    0x400,
    0,
    0x08,       # BIT(3) - type
    0x08,       # BIT(3) - images
    b"\x00\x00",# cc
    0x01,       # BIT(0) - FLAG_SET_DEBUG
    b"\x00" * 7,
    b"\x00" * 1024
)

def list_serial_ports():
    """Return a list of available serial COM port names."""
    return [p.device for p in serial.tools.list_ports.comports()]

def list_network_interfaces():
    """Return a list of local IPv4 addresses."""
    ips = []
    try:
        host = socket.gethostname()
        for ip in socket.gethostbyname_ex(host)[2]:
            if not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    if "192.168.137.1" not in ips:
        ips.append("192.168.137.1")
    return list(dict.fromkeys(ips))

class MultibootBroadcaster:
    def __init__(self, interface_ips, interval=0.05, log_cb=print):
        self.interface_ips = interface_ips if isinstance(interface_ips, list) else [interface_ips]
        self.interval = interval
        self.log_cb = log_cb
        self._running = False
        self._thread = None
        self.packets_sent = 0

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log_cb(f"[zyeng] Broadcaster started on interfaces: {self.interface_ips}")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.log_cb(f"[zyeng] Broadcaster stopped. Sent {self.packets_sent} packets.")

    def _run(self):
        while self._running:
            for ip in self.interface_ips:
                s = None
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind((ip, 0))
                    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ip))
                    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

                    s.sendto(ZYENG_PACKET, (DEST_MULTICAST, DEST_PORT))
                    s.sendto(ZYENG_PACKET, (DEST_BROADCAST, DEST_PORT))
                    self.packets_sent += 2
                except Exception:
                    pass
                finally:
                    if s:
                        try:
                            s.close()
                        except Exception:
                            pass
            time.sleep(self.interval)

class SingleSocketTFTPServer:
    """RFC 1350 compliant single-socket TFTP server that avoids firewall blocking."""
    def __init__(self, bind_ip="192.168.137.1", port=69, serve_dir=".", log_cb=print):
        self.bind_ip = bind_ip
        self.port = port
        self.serve_dir = os.path.abspath(serve_dir)
        self.log_cb = log_cb
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log_cb(f"[TFTP] Server listening on {self.bind_ip}:{self.port} serving {self.serve_dir}")

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.log_cb("[TFTP] Server stopped.")

    def _run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self.bind_ip, self.port))
            sock.settimeout(0.5)
        except Exception as e:
            self.log_cb(f"[TFTP] Failed to bind {self.bind_ip}:{self.port}: {e}")
            return

        try:
            while not self._stop_event.is_set():
                try:
                    data, client_addr = sock.recvfrom(1024)
                except socket.timeout:
                    continue
                except Exception:
                    break

                if len(data) < 4:
                    continue

                opcode = struct.unpack(">H", data[:2])[0]
                if opcode != 1:  # Only RRQ handled
                    continue

                parts = data[2:].split(b"\x00")
                filename = parts[0].decode("latin1")
                filepath = os.path.join(self.serve_dir, os.path.basename(filename))
                self.log_cb(f"[TFTP] Request for '{filename}' from {client_addr}")

                # Parse options
                opts = {}
                i = 2
                while i + 1 < len(parts):
                    k = parts[i].decode("latin1").lower()
                    v = parts[i+1].decode("latin1")
                    opts[k] = v
                    i += 2

                if not os.path.exists(filepath):
                    self.log_cb(f"[TFTP] File '{filepath}' not found!")
                    sock.sendto(b"\x00\x05\x00\x01File not found\x00", client_addr)
                    continue

                with open(filepath, "rb") as f:
                    file_bytes = f.read()

                blksize = 512
                if "blksize" in opts:
                    blksize = int(opts["blksize"])
                    oack = (
                        b"\x00\x06blksize\x00" + str(blksize).encode() +
                        b"\x00tsize\x00" + str(len(file_bytes)).encode() + b"\x00"
                    )
                    sock.sendto(oack, client_addr)
                    sock.settimeout(2.0)
                    try:
                        sock.recvfrom(512)
                    except socket.timeout:
                        continue

                total_len = len(file_bytes)
                offset = 0
                block_num = 1
                start_t = time.time()

                while offset < total_len or (offset == total_len and block_num == 1):
                    chunk = file_bytes[offset:offset+blksize]
                    pkt = struct.pack(">HH", 3, block_num & 0xFFFF) + chunk

                    acked = False
                    for _ in range(5):
                        sock.sendto(pkt, client_addr)
                        sock.settimeout(1.5)
                        try:
                            ack, addr = sock.recvfrom(512)
                            if addr == client_addr and len(ack) >= 4:
                                op, b = struct.unpack(">HH", ack[:4])
                                if op == 4 and b == (block_num & 0xFFFF):
                                    acked = True
                                    break
                        except socket.timeout:
                            pass

                    if not acked:
                        self.log_cb(f"[TFTP] Block {block_num} transfer timed out.")
                        break

                    offset += len(chunk)
                    block_num += 1
                    if len(chunk) < blksize:
                        break

                elapsed = max(0.01, time.time() - start_t)
                mb_s = (total_len / 1024 / 1024) / elapsed
                self.log_cb(f"[TFTP] Sent {total_len} bytes in {elapsed:.2f}s ({mb_s:.2f} MB/s)!")
        finally:
            sock.close()
