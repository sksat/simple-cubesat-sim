#!/usr/bin/env python3
"""DRV8833 Motor Controller - Host Script (HID)

Usage:
  motor_control.py [speed]
  motor_control.py 50       # Forward 50%
  motor_control.py r50      # Reverse 50%
  motor_control.py 0        # Stop
  motor_control.py          # Interactive mode
"""

import hid
import struct
import sys
import time

# USB VID/PID
VID = 0x2E8A
PID = 0x0B33

# Direction constants
DIR_STOP = 0
DIR_FORWARD = 1
DIR_REVERSE = 2


def find_device():
    """Find the motor controller HID device"""
    devices = hid.enumerate(VID, PID)
    if not devices:
        return None
    try:
        device = hid.Device(path=devices[0]["path"])
        return device
    except hid.HIDException:
        return None


def send_command(device, direction: int, duty: int):
    """Send motor command via HID output report"""
    # Output report: [report_id, direction, duty]
    # report_id = 0 for default
    report = bytes([0, direction, duty])
    device.write(report)


def read_state(device) -> tuple[int, int] | None:
    """Read current motor state from HID input report"""
    device.nonblocking = True
    data = device.read(64, timeout=100)
    if data and len(data) >= 2:
        return (data[0], data[1])  # state, duty
    return None


def parse_speed(s: str) -> tuple[int, int]:
    """Parse speed string, return (direction, duty)"""
    s = s.strip().lower()
    if s == "0" or s == "stop":
        return (DIR_STOP, 0)
    if s.startswith("r"):
        duty = int(s[1:])
        return (DIR_REVERSE, min(100, max(0, duty)))
    duty = int(s)
    if duty < 0:
        return (DIR_REVERSE, min(100, abs(duty)))
    return (DIR_FORWARD, min(100, duty))


def state_str(state: int) -> str:
    """Convert state to string"""
    return {0: "STOP", 1: "FWD", 2: "REV"}.get(state, "???")


def main():
    args = sys.argv[1:]

    device = find_device()
    if device is None:
        print(f"Motor controller not found (VID={VID:04x} PID={PID:04x})")
        sys.exit(1)

    info = device.product
    print(f"Found: {info}")

    try:
        if args:
            # Command mode
            cmd = "".join(args)
            direction, duty = parse_speed(cmd)
            send_command(device, direction, duty)
            # Wait for command to be processed
            time.sleep(0.15)
            state = read_state(device)
            if state:
                print(f"OK: {state_str(state[0])} {state[1]}%")
            else:
                print(f"Sent: dir={direction} duty={duty}")
        else:
            # Interactive mode
            interactive_mode(device)
    finally:
        device.close()


def interactive_mode(device):
    """Interactive command mode"""
    print("DRV8833 Motor Controller (HID)")
    print("Commands: 0-100 (forward), r1-r100 (reverse), 0 (stop)")
    print("Ctrl+C to exit")
    print()

    try:
        while True:
            cmd = input("> ").strip()
            if not cmd:
                continue
            if cmd.lower() in ("q", "quit", "exit"):
                break
            if cmd.lower() == "status":
                state = read_state(device)
                if state:
                    print(f"State: {state_str(state[0])} {state[1]}%")
                continue

            try:
                direction, duty = parse_speed(cmd)
                send_command(device, direction, duty)
                time.sleep(0.05)
                state = read_state(device)
                if state:
                    print(f"OK: {state_str(state[0])} {state[1]}%")
            except ValueError:
                print("Invalid command")
    except KeyboardInterrupt:
        print("\nStopping motor...")
        send_command(device, DIR_STOP, 0)


if __name__ == "__main__":
    main()
