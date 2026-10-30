"""
ESP32 Hardware Detection and Communication Driver for QuSec.
Supports auto-detection of ESP32 USB-UART bridges (CP210x, CH340, FTDI, Espressif native),
serial communication, hardware True Random Number Generation (TRNG), and Wi-Fi relay.
"""

import os
import glob
import time
import json
import logging
from typing import Optional, Dict, Any, List

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    serial = None
    HAS_SERIAL = False

logger = logging.getLogger("qusec.hardware.esp32")

# Known USB Vendor/Product IDs for common ESP32 development boards
ESP32_KNOWN_VID_PID = {
    (0x10C4, 0xEA60): "Silicon Labs CP210x (ESP32)",
    (0x1A86, 0x7523): "QinHeng CH340 (ESP32)",
    (0x1A86, 0x55D4): "QinHeng CH343 / CH9102 (ESP32)",
    (0x303A, 0x1001): "Espressif USB JTAG/serial (ESP32-S3/C3)",
    (0x303A, 0x0002): "Espressif ESP32-S2 USB",
    (0x0403, 0x6001): "FTDI FT232R (ESP32 DevKit)",
    (0x0403, 0x6010): "FTDI Dual Serial",
}


class ESP32Device:
    """Represents a detected or connected ESP32 microcontroller."""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        description: str = "ESP32 Device",
        timeout: float = 1.0,
    ):
        self.port = port
        self.baudrate = baudrate
        self.description = description
        self.timeout = timeout
        self._serial: Optional[Any] = None
        self.is_connected = False
        self.firmware_version: Optional[str] = None
        self.device_role: Optional[str] = None

    def connect(self) -> bool:
        """Open serial connection to the ESP32."""
        if not HAS_SERIAL:
            logger.warning("pyserial is not installed.")
            return False
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout,
            )
            # Toggle DTR/RTS to avoid stuck bootloader if applicable
            self._serial.dtr = False
            self._serial.rts = False
            time.sleep(0.1)
            self.is_connected = True
            logger.info("Connected to ESP32 on port %s @ %d baud", self.port, self.baudrate)
            return True
        except Exception as e:
            logger.debug("Failed to connect to %s: %s", self.port, e)
            self.is_connected = False
            return False

    def disconnect(self):
        """Close serial connection."""
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass
        self.is_connected = False

    def send_command(self, cmd: str, expect_json: bool = True) -> Optional[Any]:
        """Send a newline-terminated command and return response."""
        if not self.is_connected or not self._serial:
            return None
        try:
            line_to_send = (cmd.strip() + "\n").encode("utf-8")
            self._serial.write(line_to_send)
            self._serial.flush()
            response = self._serial.readline().decode("utf-8", errors="replace").strip()
            if not response:
                return None
            if expect_json:
                try:
                    return json.loads(response)
                except Exception:
                    return {"raw": response}
            return response
        except Exception as e:
            logger.warning("Error communicating with ESP32 on %s: %s", self.port, e)
            return None

    def ping(self) -> bool:
        """Ping the ESP32 to check liveness."""
        if not self.is_connected:
            return False
        res = self.send_command("PING")
        if res:
            if isinstance(res, dict) and (res.get("status") == "PONG" or "PONG" in str(res)):
                return True
            if "PONG" in str(res):
                return True
        return False

    def get_hardware_random_bytes(self, num_bytes: int = 32) -> Optional[bytes]:
        """Request true hardware random bytes from ESP32 internal RNG."""
        if not self.is_connected:
            return None
        res = self.send_command(f"RNG {num_bytes}")
        if isinstance(res, dict) and "hex" in res:
            try:
                return bytes.fromhex(res["hex"])
            except ValueError:
                return None
        return None

    def send_classical_packet(self, packet_bytes: bytes) -> bool:
        """Forward a classical packet via ESP32 Wi-Fi transmitter."""
        if not self.is_connected:
            return False
        hex_data = packet_bytes.hex()
        res = self.send_command(f"TX {hex_data}")
        return bool(res and isinstance(res, dict) and res.get("status") == "OK")

    def set_alarm(self, enable: bool = True, blink_ms: int = 150) -> bool:
        """Trigger or clear security alarm LED (second LED, GPIO 4) on ESP32."""
        if not self.is_connected:
            return False
        cmd = f"ALARM {'1' if enable else '0'} {blink_ms}"
        res = self.send_command(cmd)
        return bool(res and isinstance(res, dict) and res.get("status") == "OK")

    def set_role(self, role: str) -> bool:
        """Configure device role on the ESP32 (SENDER or RECEIVER)."""
        if not self.is_connected:
            return False
        res = self.send_command(f"SET_ROLE {role.upper()}")
        return bool(res and isinstance(res, dict) and res.get("status") == "OK")

    def read_incoming_packet(self) -> Optional[bytes]:
        """Check serial buffer for classical packets forwarded from ESP32 Wi-Fi ('RX <data>')."""
        if not self.is_connected or not self._serial:
            return None
        try:
            if getattr(self._serial, "in_waiting", 0) > 0:
                line = self._serial.readline().decode("utf-8", errors="replace").strip()
                if line.startswith("RX "):
                    raw_data = line[3:].strip()
                    try:
                        return bytes.fromhex(raw_data)
                    except ValueError:
                        return raw_data.encode("utf-8")
        except Exception as e:
            logger.debug("ESP32 read packet exception: %s", e)
        return None


class ESP32Detector:
    """Scans system serial interfaces to auto-detect attached ESP32 boards."""

    @staticmethod
    def scan_ports() -> List[Dict[str, Any]]:
        """Enumerate all serial ports and detect potential ESP32 microcontrollers."""
        found = []
        if not HAS_SERIAL:
            return found

        try:
            ports = list(serial.tools.list_ports.comports())
        except Exception as e:
            logger.debug("serial.tools.list_ports error: %s", e)
            ports = []

        # System fallback for macOS /dev/cu.* devices
        if not ports:
            raw_ports = glob.glob("/dev/cu.usb*") + glob.glob("/dev/cu.wch*") + glob.glob("/dev/cu.SLAB*") + glob.glob("/dev/ttyUSB*")
            for p in raw_ports:
                found.append({
                    "port": p,
                    "description": "USB-Serial Device",
                    "hwid": "Unknown",
                    "is_esp32": True,
                    "model": "Generic ESP32 / USB-UART",
                })
            return found

        for p in ports:
            is_esp = False
            model = "Serial Device"
            vid = p.vid
            pid = p.pid

            if (vid, pid) in ESP32_KNOWN_VID_PID:
                is_esp = True
                model = ESP32_KNOWN_VID_PID[(vid, pid)]
            elif p.description and any(k in p.description.lower() for k in ["cp210", "ch340", "ch341", "ch9102", "esp32", "ft232", "usb to uart"]):
                is_esp = True
                model = f"Detected ESP32 Bridge ({p.description})"
            elif any(k in p.device.lower() for k in ["usbserial", "wchusbserial", "slab_usbtouart", "ttyusb", "usbmodem"]):
                is_esp = True
                model = "USB-Serial Interface"

            found.append({
                "port": p.device,
                "description": p.description or "Serial Port",
                "hwid": p.hwid or "N/A",
                "vid": vid,
                "pid": pid,
                "is_esp32": is_esp,
                "model": model,
            })

        return found

    @staticmethod
    def find_esp32(preferred_port: Optional[str] = None) -> Optional[ESP32Device]:
        """Auto-detect the first active ESP32 device."""
        ports = ESP32Detector.scan_ports()
        if preferred_port:
            for p in ports:
                if p["port"] == preferred_port:
                    dev = ESP32Device(port=preferred_port, description=p.get("model", "ESP32"))
                    if dev.connect():
                        return dev

        esp_ports = [p for p in ports if p["is_esp32"]]
        for p in esp_ports:
            dev = ESP32Device(port=p["port"], description=p["model"])
            if dev.connect():
                return dev

        return None
