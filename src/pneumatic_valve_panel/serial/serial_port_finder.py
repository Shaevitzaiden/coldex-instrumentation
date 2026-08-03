# Serial communication libraries
import serial
from serial.serialutil import SerialException
from serial.tools import list_ports


def get_serial_port_details():
    """Return detailed metadata for all currently available serial ports."""
    ports = []
    for port in list_ports.comports():
        ports.append({
            "device": port.device,
            "name": port.name,
            "description": port.description,
            "hwid": port.hwid,
            "manufacturer": port.manufacturer,
            "product": port.product,
            "serial_number": port.serial_number,
            "location": port.location,
            "interface": port.interface,
            "vid": f"0x{port.vid:04X}" if port.vid is not None else None,
            "pid": f"0x{port.pid:04X}" if port.pid is not None else None,
        })
    return ports

def serial_ports():
    """Return a simple list of active serial port device names (for compatibility)."""
    return [port["device"] for port in get_serial_port_details()]

def select_serial_port():
    """Prompt the user to select a serial port from the available options."""
    ports = get_serial_port_details()
    if not ports:
        print("No active serial ports found.")
        return None

    print("Available serial ports:")
    for idx, port in enumerate(ports, start=1):
        print(f"[{idx}] {port['device']} - {port.get('description') or 'No description'}")

    while True:
        try:
            selection = int(input("Select a port by number (or 0 to cancel): "))
            if selection == 0:
                return None
            elif 1 <= selection <= len(ports):
                return ports[selection - 1]["device"]
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def display_serial_ports_data():
    port_details = get_serial_port_details()
    if not port_details:
        print("No active serial ports found.")
    else:
        for idx, port in enumerate(port_details, start=1):
            print(f"[{idx}] {port['device']} - {port.get('description') or 'No description'}")

            if port.get("manufacturer"):
                print(f"    Manufacturer: {port['manufacturer']}")
            if port.get("product"):
                print(f"    Product: {port['product']}")
            if port.get("serial_number"):
                print(f"    Serial Number: {port['serial_number']}")
            if port.get("vid") and port.get("pid"):
                print(f"    VID:PID: {port['vid']}:{port['pid']}")
            if port.get("location"):
                print(f"    Location: {port['location']}")
            if port.get("hwid"):
                print(f"    HWID: {port['hwid']}")