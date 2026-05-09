import errno
import os
import platform

import serial
import serial.tools.list_ports

try:
    import grp
except ImportError:
    grp = None


ESP32_KEYWORDS = (
    "cp210",
    "cp210x",
    "silicon labs",
    "ch340",
    "ch341",
    "wch",
    "ft232",
    "ftdi",
    "usb serial",
    "uart",
    "esp32",
    "jtag",
)


def is_linux():
    return platform.system().lower() == "linux"


def is_windows():
    return platform.system().lower() == "windows"


def port_identity(port):
    text = " ".join(
        str(x or "")
        for x in (
            port.device,
            port.name,
            port.description,
            port.hwid,
            getattr(port, "manufacturer", ""),
            getattr(port, "product", ""),
        )
    ).lower()
    return text


def is_likely_physical_port(port):
    device = (port.device or "").lower()
    if is_linux():
        if device.startswith("/dev/ttyusb") or device.startswith("/dev/ttyacm"):
            return True
        if device.startswith("/dev/serial/by-id"):
            return True
        return any(keyword in port_identity(port) for keyword in ESP32_KEYWORDS)

    if is_windows():
        return device.startswith("com")

    return "usb" in port_identity(port) or any(keyword in port_identity(port) for keyword in ESP32_KEYWORDS)


def port_score(port):
    text = port_identity(port)
    score = 0

    if is_likely_physical_port(port):
        score += 50

    for keyword in ESP32_KEYWORDS:
        if keyword in text:
            score += 20

    device = (port.device or "").lower()
    if device.startswith("/dev/ttyusb") or device.startswith("/dev/ttyacm"):
        score += 20
    if device.startswith("com"):
        score += 15

    return score


def scan_physical_ports():
    ports = [p for p in serial.tools.list_ports.comports() if is_likely_physical_port(p)]
    return sorted(ports, key=port_score, reverse=True)


def port_label(port):
    description = port.description or "Serial device"
    hwid = port.hwid or ""
    if hwid:
        return f"{port.device} - {description} [{hwid}]"
    return f"{port.device} - {description}"


def build_port_choices():
    ports = scan_physical_ports()
    labels = [port_label(p) for p in ports]
    mapping = {label: p.device for label, p in zip(labels, ports)}
    return labels, mapping


def extract_device(selection, mapping):
    selection = (selection or "").strip()
    if selection in mapping:
        return mapping[selection]
    if " - " in selection:
        return selection.split(" - ", 1)[0].strip()
    return selection


def permission_fix_text(port):
    if is_linux():
        user = os.environ.get("USER", "your_user")
        group = "dialout"

        try:
            if grp is not None and os.path.exists(port):
                group = grp.getgrgid(os.stat(port).st_gid).gr_name
        except Exception:
            group = "dialout"

        return (
            f"Linux blocked access to {port}.\n\n"
            "Recommended permanent fix:\n"
            f"  sudo usermod -aG {group} {user}\n"
            "Then log out and back in, or reboot.\n"
            "On some distros the serial group is dialout; on others it is uucp or lock.\n\n"
            "Temporary one-session fix if you need to test immediately:\n"
            f"  sudo chmod a+rw {port}\n\n"
            "Avoid running the whole GUI with sudo unless you are only doing a quick emergency test."
        )

    if is_windows():
        return (
            f"Windows blocked access to {port}.\n\n"
            "Close Arduino IDE Serial Monitor, PuTTY, VS Code serial tools, or any other app using this COM port. "
            "If the port still fails, unplug/replug the ESP32 and check Device Manager."
        )

    return f"Permission denied while opening {port}. Close other serial tools or adjust OS serial permissions."


def friendly_serial_error(port, exc):
    original = getattr(exc, "original_exception", exc)
    err_no = getattr(original, "errno", None)
    text = str(exc)

    if isinstance(original, PermissionError) or err_no in (errno.EACCES, errno.EPERM) or "permission denied" in text.lower():
        return permission_fix_text(port)

    if "busy" in text.lower() or "access is denied" in text.lower():
        return (
            f"{port} is busy or already open.\n\n"
            "Close Arduino Serial Monitor, another LiFi GUI window, VS Code serial monitor, or any terminal program using the same port."
        )

    return f"Could not open {port}:\n{text}"


def open_serial(port, baudrate, timeout=0.05, write_timeout=5):
    return serial.Serial(port, baudrate, timeout=timeout, write_timeout=write_timeout)
