import argparse
import json
import time
import sys
import threading
from typing import Dict, Any
from dataset import SignalGraphDataset
from util import visualize_graph, load_config
import matplotlib.pyplot as plt
import socket

from digi.xbee.devices import DigiMeshDevice
from digi.xbee.models.address import XBee64BitAddress
from digi.xbee.exception import TransmitException

class CentralNode:
    def __init__(
        self,
        port: str,
        baud: int,
        id_to_addr: Dict[str, str],
    ):
        self.port = port
        self.baud = baud

        self.id_to_addr = id_to_addr

        self.device = DigiMeshDevice(self.port, self.baud)

        self.received_addresses: Dict[str, str] = {}

        self.received_values: Dict[int, Dict[str, float]] = {}
        self._init_event = threading.Event()

    def _on_rx(self, xbee_message):
        try:
            msg = json.loads(xbee_message.data.decode("utf-8"))
        except Exception:
            return
        
        if msg.get("t") == "i":
            


    def start(self, xbee_message):
        self.device.open()
        self.device.add_data_received_callback(self._on_rx)
        
        print(f"[CENTRAL] Port: {self.port} @ {self.baud}")
        print(f"[CENTRAL] Adresa: {self.device.get_64bit_addr()}")

        print(f"Waiting for addresses")
        if self._init_event.wait():
            print(self.received_values)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--n_from_config", default=False)
    ap.add_argument("--retries", type=int, default=10)
    ap.add_argument("--retry_delay", type=float, default=0.4)
    args = ap.parse_args()

    cfg = load_config(args.config)
    id_to_addr = cfg["id_to_addr"]

    dataset = SignalGraphDataset()
    G = dataset.getGraph()
    nodes = G["nodes_letters"]
    if args.n_from_config:
        nodes = cfg["nodes"]

    centralNode = CentralNode(

    )
    


if __name__ == "__main__":
    main()