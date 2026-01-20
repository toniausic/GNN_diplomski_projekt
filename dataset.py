import torch
from torch.utils.data import Dataset
import random
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader

import matplotlib.pyplot as plt

def visualize_graph(sample):
    x = sample["x"].squeeze(-1)
    positions = sample["positions"]
    source = sample["source"]
    num_nodes = sample["num_nodes"]
    A = sample["A"]

    print("sorse:", source)

    plt.figure()

    # bridovi
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if A[i, j] > 0:
                plt.plot(
                    [positions[i, 0], positions[j, 0]],
                    [positions[i, 1], positions[j, 1]],
                    alpha=0.3,
                )

    # čvorovi
    plt.scatter(
        positions[:, 0],
        positions[:, 1],
        s=300 * x + 40,
    )

    # oznake čvorova ako ih je točno 5
    if num_nodes == 5:
        labels = ["A", "B", "C", "D", "E"]
        for i, label in enumerate(labels):
            plt.text(
                positions[i, 0] + 0.02,  # mali pomak udesno
                positions[i, 1] + 0.02,  # mali pomak gore
                label,
                fontsize=12,
                fontweight="bold",
            )

    # izvor signala
    plt.scatter(
        source[0],
        source[1],
        marker="x",
        s=300,
    )

    plt.title("Vizualizacija grafa (velicina = jacina signala)")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.show()

class SignalGraphDataset():
    def __init__(
        self,
        node_size=5,
        std=0.01,
        max_distance=10.0,
        connectivity_prob=0.4,
        label_type="node"
    ):
        self.node_size = node_size
        self.std = std
        self.max_distance = max_distance
        self.connectivity_prob = connectivity_prob
        self.label_type = label_type


    def getGraph(self):
        num_nodes = random.randint(self.node_size, self.node_size)
        positions = torch.rand(num_nodes, 2) * self.max_distance

        A = torch.zeros(num_nodes, num_nodes)
        for i in range(num_nodes):
            for j in range(i + 1, num_nodes):
                if random.random() < self.connectivity_prob:
                    A[i, j] = 1
                    A[j, i] = 1

        source = torch.rand(2) * self.max_distance

        num_nodes = positions.shape[0]
        distances = torch.zeros(num_nodes, num_nodes)

        for i in range(num_nodes):
            for j in range(num_nodes):
                if i == j:
                    distances[i, j] = 1e-6
                    continue

                dx = positions[i, 0] - positions[j, 0]
                dy = positions[i, 1] - positions[j, 1]
                distances[i, j] = torch.sqrt(dx * dx + dy * dy) + 1e-6

        source_distances = torch.zeros(num_nodes)

        for i in range(num_nodes):
            dx = positions[i, 0] - source[0]
            dy = positions[i, 1] - source[1]
            source_distances[i] = torch.sqrt(dx * dx + dy * dy) + 1e-6


        signal = 1.0 / source_distances
        signal += torch.randn_like(signal) * self.std

        signal = (signal - signal.min()) / (signal.max() - signal.min() + 1e-6)

        # for i in range(num_nodes):
        #     print(f"Čvor {i}: Signal = {signal[i]:.4f}, Pozicija = ({positions[i,0]:.2f}, {positions[i,1]:.2f})")

        x = signal.unsqueeze(-1)

        if self.label_type == "node":
            relative_positions = torch.zeros(num_nodes, 2)
            for i in range(num_nodes):
                relative_positions[i] = source - positions[i]
            y = relative_positions

        elif self.label_type == "graph":
            y = torch.tensor(source)
        else:
            raise ValueError("Nepoznat tip oznake")
        
        nodes = {}
        nodes_letters = {}

        labels = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

        for i in range(num_nodes):
            neighbors = []
            n_letters = []
            for j in range(num_nodes):
                if A[i, j] > 0:
                    neighbors.append(str(j))
                    n_letters.append(labels[j])
            nodes_letters[labels[i]] = {"neighbours": n_letters, "value": float(x[i].item())}
            nodes[str(i)] = {"neighbours": neighbors, "value": float(x[i].item())}

        return {
            "x": x,                    # signal po čvoru
            "A": A,                    # matrica povezanosti
            "adj": distances,          # udaljenosti / povezanost
            "y": y,                    # label (izvor signala) / pozicija, relativna ili apsolutna
            "source": source,          # pozicija izvora signala
            "num_nodes": num_nodes,
            "positions": positions,    # pozicije čvorova
            "nodes": nodes,            # čvorovi u formatu za config.json
            "nodes_letters": nodes_letters # čvorovi s oznakama A, B, C... za lakše praćenje
        }
    
if __name__ == "__main__":
    dataset = SignalGraphDataset(label_type="graph")
    G = dataset.getGraph()
    print(G["nodes_letters"])

    # batch = next(iter(loader))
    # print(G["x"].shape)
    # print(G["adj"].shape)
    # print(G["y"])

    # print("Susjedi čvora 0:", dataset.get_neighbors(0, 0))

    # print(G["nodes"])
    # print(G["positions"])

    visualize_graph(G)