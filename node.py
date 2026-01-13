import argparse #bez njega nemogu --baudrate i slicne oparametre mijenjati u terminalu
import json
import time
import threading

from digi.xbee.devices import DigiMeshDevice
from digi.xbee.models.address import XBee64BitAddress


class Node:
    def __init__(self, port: str, baud: int):
        self.device = DigiMeshDevice(port, baud)

        self._lock = threading.Lock()
        self.last_messages = []   
        self.last_ack_for = None  # msg_id koji je zadnji ACK-an

    def start(self): #ovdje iniciramo uređaj
        self.device.open()
        # callback za primanje (message accept)
        self.device.add_data_received_callback(self._on_rx)
        print("[INFO] Open:", self.device)
        print("[INFO] Local 64-bit:", self.device.get_64bit_addr())
        print("[INFO] NI:", self.device.get_node_id())

    def stop(self): #naravno, gasenje uređaja
        if self.device and self.device.is_open():
            self.device.close()

    def _on_rx(self, xbee_message): #message accept, obrada primljene poruke
        raw = xbee_message.data
        src64 = str(xbee_message.remote_device.get_64bit_addr())

        try:
            msg = json.loads(raw.decode("utf-8"))
        except Exception:
            print(f"[RX] from {src64}: (non-json) {raw!r}")
            return

        with self._lock:
            self.last_messages.append((src64, msg))

        mtype = msg.get("type")
        if mtype == "ping":
            msg_id = msg.get("msg_id")
            print(f"[RX] PING from {src64}, msg_id={msg_id}")

            # pošalji ACK natrag istom pošiljatelju (unicast reply)
            ack = {"type": "ack", "msg_id": msg_id, "ts": time.time()}
            self.send_unicast_64(src64, ack)

        elif mtype == "ack":
            msg_id = msg.get("msg_id")
            print(f"[RX] ACK from {src64}, msg_id={msg_id}")
            with self._lock:
                self.last_ack_for = msg_id

        else:
            print(f"[RX] from {src64}: {msg}")

    def send_unicast_64(self, dest64_hex: str, obj: dict):
        data = json.dumps(obj).encode("utf-8")
        addr = XBee64BitAddress.from_hex_string(dest64_hex)
        self.device.send_data_64(addr, data)  #DigiMesh unicast

    def ping_and_wait_ack(self, dest64_hex: str, msg_id: str, timeout_s: float = 3.0):
        with self._lock:
            self.last_ack_for = None

        self.send_unicast_64(dest64_hex, {"type": "ping", "msg_id": msg_id, "ts": time.time()})
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            with self._lock:
                if self.last_ack_for == msg_id:
                    return True
            time.sleep(0.05)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--peer64", required=True)
    ap.add_argument("--mode", choices=["listen", "ping"], required=True)
    args = ap.parse_args()

    node = Node(args.port, args.baud)
    node.start()
    try:
        if args.mode == "listen":
            print("[INFO] Listening...")
            while True:
                time.sleep(1)

        if args.mode == "ping":
            msg_id = str(int(time.time() * 1000))
            ok = node.ping_and_wait_ack(args.peer64, msg_id)
            print("[RESULT] ACK received" if ok else "[RESULT] ACK TIMEOUT")

    finally:
        node.stop()


if __name__ == "__main__":
    main()
