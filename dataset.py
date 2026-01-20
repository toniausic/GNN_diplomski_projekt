import torch
from torch.utils.data import Dataset
import random
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader

def visualize_graph(sample):
    x = sample["x"].squeeze(-1)
    positions = sample["positions"][0]
    source = sample["source"][0]
    num_nodes = sample["num_nodes"]
    A = sample["A"][0]

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
        s= 300 * x + 40,
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


class SignalGraphDataset(Dataset):
    def __init__(
        self,
        num_samples=1000,
        min_nodes=4,
        max_nodes=8,
        std=0.01,
        max_distance=10.0,
        connectivity_prob=0.4,
        label_type="node"
    ):
        self.num_samples = num_samples
        self.min_nodes = min_nodes
        self.max_nodes = max_nodes
        self.std = std
        self.max_distance = max_distance
        self.connectivity_prob = connectivity_prob
        self.label_type = label_type

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        num_nodes = random.randint(self.min_nodes, self.max_nodes)
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

        return {
            "x": x,                    # signal po čvoru
            "A": A,                    # matrica povezanosti
            "adj": distances,          # udaljenosti / povezanost
            "y": y,                    # label (izvor signala) / pozicija, relativna ili apsolutna
            "source": source,          # pozicija izvora signala
            "num_nodes": num_nodes,
            "positions": positions,    # pozicije čvorova
        }
    
    def get_neighbors(self, idx, vtx):
        sample = self[idx]
        A = sample["A"]
        neighbors = torch.where(A[vtx] > 0)[0]
        return neighbors.tolist()

dataset = SignalGraphDataset(num_samples=1, label_type="graph")
loader = DataLoader(dataset, batch_size=1, shuffle=True)

batch = next(iter(loader))
print(batch["x"].shape)
print(batch["adj"].shape)
print(batch["y"])

# print("Susjedi čvora 0:", dataset.get_neighbors(0, 0))


sample = dataset[0]
visualize_graph(batch)