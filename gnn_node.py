import argparse
import json
import time
import threading
import uuid
from typing import Dict, Any, Optional

from digi.xbee.devices import DigiMeshDevice
from digi.xbee.models.address import XBee64BitAddress
from digi.xbee.exception import TransmitException


class MeshNodeTiny:
    """
    Tiny mesh node:
    - Unicast send via 64-bit addr (from config)
    - RX callback (message accept)
    - App-level ACK + REPLY
    - Optional forwarding via routes (DestID -> NextHopID)
    - Message format is MINIMAL to avoid PAYLOAD_TOO_LARGE
    """

    def __init__(
        self,
        port: str,
        baud: int,
        node_id: str,
        id_to_addr: Dict[str, str],   # NodeID -> 64-bit hex string (16 hex chars)
        routes: Dict[str, str],       # DestID -> NextHopID
        ack_enabled: bool = True,
    ):
        self.port = port
        self.baud = baud
        self.node_id = node_id
        self.id_to_addr = id_to_addr
        self.routes = routes
        self.ack_enabled = ack_enabled

        self.device = DigiMeshDevice(self.port, self.baud)

        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)

        # Dedup for DATA forwarding
        self.seen = set()  # msg_id set

        # For send mode waiting
        self.pending_ack: Dict[str, bool] = {}
        self.pending_reply: Dict[str, Any] = {}

    # ---------------- lifecycle ----------------
    def start(self):
        self.device.open()
        self.device.add_data_received_callback(self._on_rx)
        print(f"[{self.node_id}] Open on {self.port} @ {self.baud}")
        print(f"[{self.node_id}] Local64={self.device.get_64bit_addr()} NI={self.device.get_node_id()}")

    def stop(self):
        if self.device and self.device.is_open():
            self.device.close()

    # ---------------- routing ----------------
    def _next_hop_for(self, dst_id: str) -> Optional[str]:
        # Explicit route wins
        if dst_id in self.routes:
            return self.routes[dst_id]
        # If we know dst address, try direct
        if dst_id in self.id_to_addr:
            return dst_id
        return None

    # ---------------- send helpers ----------------
    def _send_unicast_addr64(self, addr64_hex: str, msg_obj: Dict[str, Any]) -> bool:
        data = json.dumps(msg_obj, separators=(",", ":")).encode("utf-8")  # compact JSON
        addr = XBee64BitAddress.from_hex_string(addr64_hex)
        try:
            self.device.send_data_64(addr, data)
            return True
        except TransmitException as e:
            status = getattr(e, "transmit_status", None) or getattr(e, "status", None)
            print(f"[{self.node_id}] TX FAIL to={addr64_hex} msg_id={msg_obj.get('msg_id')} status={status}")
            return False

    def _send_to_nodeid(self, nodeid: str, msg_obj: Dict[str, Any]) -> bool:
        if nodeid not in self.id_to_addr:
            print(f"[{self.node_id}] DROP msg_id={msg_obj.get('msg_id')} (unknown next hop '{nodeid}')")
            return False
        return self._send_unicast_addr64(self.id_to_addr[nodeid], msg_obj)

    def _route_and_send(self, msg_obj: Dict[str, Any]) -> bool:
        dst = msg_obj.get("dst")
        msg_id = msg_obj.get("msg_id")
        nh = self._next_hop_for(dst)
        if nh is None:
            print(f"[{self.node_id}] DROP msg_id={msg_id} (no route) dst={dst}")
            return False
        if nh == self.node_id:
            print(f"[{self.node_id}] DROP msg_id={msg_id} (next hop is self) dst={dst}")
            return False

        ok = self._send_to_nodeid(nh, msg_obj)
        if ok:
            print(f"[{self.node_id}] TX {msg_obj.get('type')} msg_id={msg_id} dst={dst} via={nh}")
        return ok

    # ---------------- RX callback ----------------
    def _on_rx(self, xbee_message):
        raw = xbee_message.data
        try:
            msg = json.loads(raw.decode("utf-8"))
        except Exception:
            return
        if not isinstance(msg, dict):
            return
        if msg.get("v") != 1:
            return

        mtype = msg.get("type")
        msg_id = msg.get("msg_id")
        src = msg.get("src")
        dst = msg.get("dst")

        if not mtype or not msg_id or not src or not dst:
            return

        # ACK handling
        if mtype == "ACK":
            with self._cv:
                self.pending_ack[msg_id] = True
                self._cv.notify_all()
            print(f"[{self.node_id}] RX ACK msg_id={msg_id} from {src}")
            return

        # REPLY handling
        if mtype == "REPLY":
            with self._cv:
                self.pending_reply[msg_id] = msg.get("payload")
                self._cv.notify_all()
            print(f"[{self.node_id}] RX REPLY msg_id={msg_id} from {src} payload={msg.get('payload')}")
            return

        # Only DATA below
        if mtype != "DATA":
            return

        # Dedup (prevents forwarding loops)
        with self._lock:
            if msg_id in self.seen:
                return
            self.seen.add(msg_id)

        # Optional ACK back to src (end-to-end)
        if self.ack_enabled:
            ack = {"v": 1, "type": "ACK", "msg_id": msg_id, "src": self.node_id, "dst": src}
            self._route_and_send(ack)

        # If this DATA is for me -> handle and reply
        if dst == self.node_id:
            payload = msg.get("payload")
            print(f"[{self.node_id}] RX DATA msg_id={msg_id} from {src} payload={payload}")

            reply = {"v": 1, "type": "REPLY", "msg_id": msg_id, "src": self.node_id, "dst": src, "payload": "OK"}
            self._route_and_send(reply)
            return

        # Otherwise forward
        self._route_and_send(msg)

    # ---------------- user API ----------------
    def send_data(self, dst_id: str, text: str, timeout_s: float = 4.0) -> Dict[str, Any]:
        msg_id = uuid.uuid4().hex

        # TINY message: keep it small
        msg = {"v": 1, "type": "DATA", "msg_id": msg_id, "src": self.node_id, "dst": dst_id, "payload": text}

        with self._cv:
            self.pending_ack.pop(msg_id, None)
            self.pending_reply.pop(msg_id, None)

        ok = self._route_and_send(msg)
        if not ok:
            return {"msg_id": msg_id, "sent": False, "ack": None, "reply": None}

        deadline = time.time() + float(timeout_s)
        got_ack = False
        got_reply = None

        with self._cv:
            while time.time() < deadline:
                if self.ack_enabled and self.pending_ack.get(msg_id):
                    got_ack = True
                if msg_id in self.pending_reply:
                    got_reply = self.pending_reply[msg_id]
                    break
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self._cv.wait(timeout=min(0.2, remaining))

        return {"msg_id": msg_id, "sent": True, "ack": got_ack if self.ack_enabled else None, "reply": got_reply}


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="npr. /dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--id", required=True, help="Node ID, npr. A")
    ap.add_argument("--config", required=True, help="JSON config file")
    ap.add_argument("--mode", choices=["listen", "send"], required=True)
    ap.add_argument("--dst", help="Destination Node ID (send mode)")
    ap.add_argument("--message", help="Message text (send mode)")
    ap.add_argument("--timeout", type=float, default=4.0)
    ap.add_argument("--no-ack", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    id_to_addr = cfg["id_to_addr"]
    routes_all = cfg.get("routes", {})
    my_routes = routes_all.get(args.id, {})

    node = MeshNodeTiny(
        port=args.port,
        baud=args.baud,
        node_id=args.id,
        id_to_addr=id_to_addr,
        routes=my_routes,
        ack_enabled=(not args.no_ack),
    )

    node.start()
    try:
        if args.mode == "listen":
            print(f"[{args.id}] Listening... Ctrl+C za izlaz")
            while True:
                time.sleep(1)

        if not args.dst or args.message is None:
            raise SystemExit("send mode requires --dst and --message")

        result = node.send_data(dst_id=args.dst, text=args.message, timeout_s=args.timeout)
        print(f"[{args.id}] RESULT {result}")

    finally:
        node.stop()


if __name__ == "__main__":
    main()
