import matplotlib.pyplot as plt

def visualize_graph(sample):
    x = sample["x"].squeeze(-1)          # shape: (num_nodes,)
    positions = sample["positions"]      # shape: (num_nodes, 2)
    source = sample["source"]            # shape: (2,)
    num_nodes = sample["num_nodes"]
    A = sample["A"]                      # shape: (num_nodes, num_nodes)

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

    # izvor signala
    plt.scatter(
        source[0],
        source[1],
        marker="x",
        s=300,
    )

        # oznake čvorova (A–E) ako graf ima 5 čvorova
    if num_nodes == 5:
        labels = ["A", "B", "C", "D", "E"]
        for i, label in enumerate(labels):
            plt.text(
                positions[i, 0],
                positions[i, 1],
                label,
                fontsize=12,
                fontweight="bold",
                ha="center",
                va="center",
            )


    plt.title("Vizualizacija grafa (velicina = jacina signala)")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.draw()


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)