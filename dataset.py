import random
import numpy as np

class SignalGraphDataset:
    def __init__(
        self,
        node_size=5,
        std=0.01,
        max_distance=10.0,
        connectivity_prob=0.4,
        label_type="node",
        seed=None,
    ):
        self.node_size = node_size
        self.std = std
        self.max_distance = max_distance
        self.connectivity_prob = connectivity_prob
        self.label_type = label_type

        # optional reproducibility
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def getGraph(self):
        num_nodes = random.randint(self.node_size, self.node_size)
        positions = np.random.rand(num_nodes, 2) * self.max_distance

        # adjacency matrix (0/1)
        A = np.zeros((num_nodes, num_nodes), dtype=np.float32)
        for i in range(num_nodes):
            for j in range(i + 1, num_nodes):
                if random.random() < self.connectivity_prob:
                    A[i, j] = 1.0
                    A[j, i] = 1.0

        source = np.random.rand(2) * self.max_distance

        # pairwise distances (with tiny eps on diagonal)
        eps = 1e-6
        distances = np.zeros((num_nodes, num_nodes), dtype=np.float32)
        for i in range(num_nodes):
            for j in range(num_nodes):
                if i == j:
                    distances[i, j] = eps
                    continue
                dx = positions[i, 0] - positions[j, 0]
                dy = positions[i, 1] - positions[j, 1]
                distances[i, j] = np.sqrt(dx * dx + dy * dy) + eps

        # distances from source to each node
        source_distances = np.zeros(num_nodes, dtype=np.float32)
        for i in range(num_nodes):
            dx = positions[i, 0] - source[0]
            dy = positions[i, 1] - source[1]
            source_distances[i] = np.sqrt(dx * dx + dy * dy) + eps

        # signal + noise
        signal = 1.0 / source_distances
        signal = signal + np.random.randn(*signal.shape).astype(np.float32) * self.std

        # normalize to [0, 1]
        signal_min = float(signal.min())
        signal_max = float(signal.max())
        signal = (signal - signal_min) / (signal_max - signal_min + eps)

        x = signal[:, None].astype(np.float32)  # shape (num_nodes, 1)

        if self.label_type == "node":
            # relative vector from node to source: (source - position)
            relative_positions = np.zeros((num_nodes, 2), dtype=np.float32)
            for i in range(num_nodes):
                relative_positions[i] = (source - positions[i]).astype(np.float32)
            y = relative_positions

        elif self.label_type == "graph":
            y = source.astype(np.float32)
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

            nodes_letters[labels[i]] = {
                "neighbours": n_letters,
                "value": float(x[i, 0]),
            }
            nodes[str(i)] = {
                "neighbours": neighbors,
                "value": float(x[i, 0]),
            }

        return {
            "x": x,                      # signal per node (num_nodes, 1)
            "A": A,                      # connectivity matrix (num_nodes, num_nodes)
            "adj": distances,            # distances matrix (num_nodes, num_nodes)
            "y": y,                      # label (relative positions) or source position
            "source": source.astype(np.float32),
            "num_nodes": num_nodes,
            "positions": positions.astype(np.float32),
            "nodes": nodes,
            "nodes_letters": nodes_letters,
        }


if __name__ == "__main__":
    dataset = SignalGraphDataset(label_type="graph")
    G = dataset.getGraph()
    print(G["nodes_letters"])
    # visualize_graph(G)
