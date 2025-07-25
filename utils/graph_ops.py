import json
from collections import defaultdict, deque

# ---------------------------
# Validation Functions
# ---------------------------

def validate_graph(graph: dict) -> list[str]:
    """
    Validate the graph structure and return warnings as a list of strings.
    Checks:
    - Decision node probabilities sum to 1.0.
    - Self-loops.
    - (Optional) Cycles or disconnected nodes (currently not blocking).
    """
    warnings = []

    if not graph or "nodes" not in graph or "edges" not in graph:
        return ["Graph data is missing or malformed."]

    node_map = {n["id"]: n for n in graph["nodes"]}
    outgoing_probs = defaultdict(float)

    for e in graph.get("edges", []):
        prob = e.get("data", {}).get("prob")
        if prob is not None:
            outgoing_probs[e["source"]] += prob

        # Self-loop
        if e["source"] == e["target"]:
            label = node_map[e["source"]]["data"]["label"]
            warnings.append(f"Self-loop detected on node '{label}'.")

    # Check probabilities for decision nodes
    for n in graph.get("nodes", []):
        if n.get("kind") == "decision":
            out_edges = [e for e in graph["edges"] if e["source"] == n["id"]]
            if out_edges:
                total_prob = outgoing_probs.get(n["id"], 0.0)
                if not (0.99 <= total_prob <= 1.01) and any(
                    e.get("data", {}).get("prob") is not None for e in out_edges
                ):
                    warnings.append(
                        f"Decision node '{n['data']['label']}' probabilities sum to {total_prob:.2f}, expected 1.0."
                    )

    # Optional: Detect cycles
    if has_cycle(graph):
        warnings.append("The graph contains cycles (loops), which may cause logical errors.")

    return warnings


# ---------------------------
# Probability Utilities
# ---------------------------

def auto_compute_probabilities(graph: dict):
    """
    Automatically distribute probabilities evenly for decision nodes
    if probabilities are missing or zero for all outgoing edges.
    """
    if not graph or "nodes" not in graph or "edges" not in graph:
        return

    for node in graph["nodes"]:
        if node.get("kind") == "decision":
            outgoing_edges = [e for e in graph["edges"] if e["source"] == node["id"]]
            if outgoing_edges and all(
                e.get("data", {}).get("prob") in [None, 0] for e in outgoing_edges
            ):
                equal_prob = round(1.0 / len(outgoing_edges), 3)
                for e in outgoing_edges:
                    e.setdefault("data", {})
                    e["data"]["prob"] = equal_prob


# ---------------------------
# Graph Analysis
# ---------------------------

def has_cycle(graph: dict) -> bool:
    """
    Check if the graph contains any cycles using Kahn's algorithm (topological sort).
    """
    if not graph or "nodes" not in graph or "edges" not in graph:
        return False

    in_degree = {n["id"]: 0 for n in graph["nodes"]}
    for e in graph["edges"]:
        in_degree[e["target"]] = in_degree.get(e["target"], 0) + 1

    queue = deque([n for n, deg in in_degree.items() if deg == 0])
    visited = 0

    while queue:
        current = queue.popleft()
        visited += 1
        for e in graph["edges"]:
            if e["source"] == current:
                in_degree[e["target"]] -= 1
                if in_degree[e["target"]] == 0:
                    queue.append(e["target"])

    return visited != len(graph["nodes"])


def graph_summary(graph: dict) -> dict:
    """
    Return a quick summary of the graph:
    - total nodes
    - total edges
    - counts of node types
    """
    summary = {
        "total_nodes": len(graph.get("nodes", [])),
        "total_edges": len(graph.get("edges", [])),
        "node_types": defaultdict(int)
    }
    for n in graph.get("nodes", []):
        summary["node_types"][n.get("kind", "event")] += 1
    summary["node_types"] = dict(summary["node_types"])
    return summary


# ---------------------------
# Save/Load Utilities
# ---------------------------

def save_graph_to_json(graph: dict, filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)


def load_graph_from_json(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
