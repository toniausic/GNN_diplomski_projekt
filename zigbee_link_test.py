#!/usr/bin/env python3
"""
zigbee_link_test.py

Quick Zigbee comms test between two XBee Zigbee modules (API mode).

Usage (two terminals / two hosts):

1) On the *responder* side (remote XBee attached to a computer):
   python3 zigbee_link_test.py --mode responder --port /dev/ttyUSB0 --baud 9600

2) On the *sender* side (local XBee attached to a computer):
   python3 zigbee_link_test.py --mode sender --port /dev/ttyUSB0 --baud 9600 \
       --remote64 0013A20041F5B73D --payload 50 --count 10

It prints:
- NP (max RF payload bytes) reported by the firmware
- per-packet payload length (the RF payload you pass to send_data_64_16)
- round-trip success/fail (echo)
"""
import argparse
import time
import struct
from digi.xbee.devices import ZigBeeDevice
from digi.xbee.models.address import XBee64BitAddress, XBee16BitAddress
from digi.xbee.exception import TransmitException


PING_MAGIC = b"PING"
PONG_MAGIC = b"PONG"

def read_np(dev: ZigBeeDevice):
    try:
        b = dev.get_parameter("NP")
        return int.from_bytes(b, "big") if b is not None else None
    except Exception:
        return None

def build_ping(seq: int, payload_len: int) -> bytes:
    # 4 bytes magic + 2 bytes seq + (payload_len - 6) filler
    if payload_len < 6:
        raise ValueError("payload_len must be >= 6")
    filler = bytes([0x55]) * (payload_len - 6)
    return PING_MAGIC + struct.pack(">H", seq) + filler

def build_pong(seq: int, payload_len: int) -> bytes:
    if payload_len < 6:
        raise ValueError("payload_len must be >= 6")
    filler = bytes([0xAA]) * (payload_len - 6)
    return PONG_MAGIC + struct.pack(">H", seq) + filler

def parse(msg: bytes):
    if len(msg) < 6:
        return None, None
    magic = msg[:4]
    seq = struct.unpack(">H", msg[4:6])[0]
    return magic, seq

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["sender", "responder"], required=True)
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--remote64", help="Remote 64-bit address (hex) for sender mode")
    ap.add_argument("--payload", type=int, default=50, help="RF payload bytes to send (<= NP)")
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--timeout", type=float, default=2.0)
    args = ap.parse_args()

    dev = ZigBeeDevice(args.port, args.baud)
    dev.open()
    dev.set_sync_ops_timeout(int(max(1, args.timeout)))

    np_val = read_np(dev)
    print(f"[{args.mode.upper()}] Local addr={dev.get_64bit_addr()}")
    print(f"[{args.mode.upper()}] NP (max RF payload bytes)={np_val}")
    print(f"[{args.mode.upper()}] Using payload_len={args.payload} bytes")

    if args.mode == "responder":
        def on_rx(xbee_message):
            data = xbee_message.data
            magic, seq = parse(data)
            if magic != PING_MAGIC:
                return
            # Reply back to sender with same payload size.
            resp = build_pong(seq, len(data))
            try:
                dev.send_data_64_16(
                    xbee_message.remote_device.get_64bit_addr(),
                    XBee16BitAddress.UNKNOWN_ADDRESS,
                    resp
                )
                print(f"[RESP] RX PING seq={seq} len={len(data)} -> TX PONG len={len(resp)}")
            except TransmitException as e:
                print(f"[RESP] TX FAIL seq={seq}: {e}")

        dev.add_data_received_callback(on_rx)
        print("[RESP] Listening... Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            dev.close()
        return

    # sender mode
    if not args.remote64:
        raise SystemExit("--remote64 is required in sender mode")
    remote64 = XBee64BitAddress.from_hex_string(args.remote64)

    got = {}
    def on_rx(xbee_message):
        data = xbee_message.data
        magic, seq = parse(data)
        if magic == PONG_MAGIC:
            got[seq] = len(data)

    dev.add_data_received_callback(on_rx)

    ok = 0
    for seq in range(1, args.count + 1):
        pkt = build_ping(seq, args.payload)
        t0 = time.time()
        try:
            dev.send_data_64_16(remote64, XBee16BitAddress.UNKNOWN_ADDRESS, pkt)
            print(f"[SEND] TX PING seq={seq} len={len(pkt)}")
        except TransmitException as e:
            print(f"[SEND] TX FAIL seq={seq}: {e}")
            continue

        # wait for pong
        while time.time() - t0 < args.timeout:
            if seq in got:
                ok += 1
                print(f"[SEND] RX PONG seq={seq} len={got[seq]} rtt={(time.time()-t0):.3f}s")
                break
            time.sleep(0.01)
        else:
            print(f"[SEND] TIMEOUT waiting PONG seq={seq}")

    print(f"[SEND] Done. ok={ok}/{args.count}")
    dev.close()

if __name__ == "__main__":
    main()
