import argparse
import json
import time
import threading
from typing import Dict, Any, List

from digi.xbee.devices import DigiMeshDevice
from digi.xbee.models.address import XBee64BitAddress
from digi.xbee.exception import TransmitException


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class ConsensusNode:
    def __init__(
        self,
        node_id: str,
        port: str,
        baud: int,
        id_to_addr: Dict[str, str],
        neighbors: List[str],
        value0: float,
        sigma: float, 
        num_iterations: int,
        wait_timeout_s: float,
    ):
        self.node_id = node_id
        self.port = port
        self.baud = baud

        self.id_to_addr = id_to_addr
        self.neighbors = neighbors[:]
        self.value = float(value0)

        self.sigma = float(sigma)
        self.num_iterations = int(num_iterations)
        self.wait_timeout_s = float(wait_timeout_s)

        self.device = DigiMeshDevice(self.port, self.baud)

        self.received_values: Dict[int, Dict[str, float]] = {}
        self._lock = threading.Lock()

    def start(self):
        self.device.open()
        self.device.add_data_received_callback(self._on_rx)

        print(f"[{self.node_id}] Port: {self.port} @ {self.baud}")
        print(f"[{self.node_id}] Adresa: {self.device.get_64bit_addr()}")
        print(f"[{self.node_id}] Susjedi ={self.neighbors} value ={self.value}")

    def stop(self):
        if self.device and self.device.is_open():
            self.device.close()

    def send_value(self, k: int, neighbor_id: str, value: float) -> bool:
        if neighbor_id not in self.id_to_addr:
            print(f"[{self.node_id}] Nepoznat susjed '{neighbor_id}'")
            return False

        msg = {
            "type": "VAL",
            "k": k,
            "src": self.node_id,
            "value": value,
        }

        data = json.dumps(msg).encode("utf-8")
        addr = XBee64BitAddress.from_hex_string(self.id_to_addr[neighbor_id])

        try:
            self.device.send_data_64(addr, data)
            return True
        except TransmitException as e:
            status = getattr(e, "transmit_status", None) or getattr(e, "status", None)
            print(f"[{self.node_id}] TX FAIL to={neighbor_id} k={k} status={status}")
            return False

    def _on_rx(self, xbee_message):  # receive_value
        try:
            msg = json.loads(xbee_message.data.decode("utf-8"))
        except Exception:
            return

        # provjera je li dict i je li tip VAL, mozemo izbaciti ako imamo dataset kojem mozemo vjerovati
        if not isinstance(msg, dict):
            return
        if msg.get("type") != "VAL":
            return

        k = msg.get("k")
        value = msg.get("value")

        # Tražimo node_id pošiljatelja
        src64 = str(xbee_message.remote_device.get_64bit_addr()).upper()
        src_id = None
        for nid, addr in self.id_to_addr.items():
            if addr.upper() == src64:
                src_id = nid
                break
        if src_id is None:
            return

        # Upis u buffer: received_values[k][src_id] = value
        with self._lock:
            self.received_values.setdefault(int(k), {})[src_id] = float(value)

    def run(self):
        for k in range(self.num_iterations):

            # Pošalji svoju vrijednost susjedima.
            for n in self.neighbors:
                self.send_value(k, n, self.value)

            # Čekaj vrijednosti od svojih susjeda (sleep(0.1) kao u pseudokodu).
            t0 = time.time()
            while True:
                with self._lock:
                    got = self.received_values.get(k, {})
                    got_count = len(got)

                if got_count >= len(self.neighbors):
                    break

                if time.time() - t0 >= self.wait_timeout_s:
                    break

                time.sleep(0.1)

            #konsenzus algoritam iz pseudokoda
          # TODO: Ako je broj manji od broja susjeda nista samo print, inace radi
            if len(got) < len(self.neighbors):
                print(f"[{self.node_id}] k={k} recv={len(got)}/{len(self.neighbors)} value={self.value:.6f}")
            else:
                suma = 0.0
                for n in self.neighbors:
                # svi susjedi su tu, ali ostavljamo sigurnosnu provjeru
                    if n in got:
                        suma += (got[n] - self.value)

                self.value = self.value + self.sigma * suma
                print(f"[{self.node_id}] k={k} recv={len(got)}/{len(self.neighbors)} value={self.value:.6f}")



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default = "/dev/ttyUSB0"  )
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--id", required=True)
    ap.add_argument("--config", default = "config.json")
    ap.add_argument("--iters", type=int, default=30)
    ap.add_argument("--sigma", type=float, default=0.1)
    ap.add_argument("--timeout", type=float, default=2.0)
    args = ap.parse_args()

    cfg = load_config(args.config)

    id_to_addr = cfg["id_to_addr"]
    nodes = cfg["nodes"]

    if args.id not in nodes:
        raise SystemExit(f"Node '{args.id}' not found in config")

    node_config = nodes[args.id]

    node = ConsensusNode(
        node_id=args.id,
        port=args.port,
        baud=args.baud,
        id_to_addr=id_to_addr,
        neighbors=node_config["neighbours"],
        value0=node_config["value"], # treba promijeniti
        sigma=args.sigma,
        num_iterations=args.iters,
        wait_timeout_s=args.timeout,
    )

    node.start()
    try:
        node.run()
    finally:
        node.stop()


if __name__ == "__main__":
    main()
