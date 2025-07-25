import json
import uuid
import streamlit as st
import streamlit.components.v1 as components
from utils import graph_ops

st.set_page_config(page_title="Decision Tree – Freeform Builder", layout="wide")
st.title("🌳 Decision Tree – Freeform Builder")

# ---------------------------
# Helpers
# ---------------------------
def new_node_id() -> str:
    return f"n_{uuid.uuid4().hex[:6]}"

def new_edge_id() -> str:
    return f"e_{uuid.uuid4().hex[:6]}"

# ---------------------------
# Session state
# ---------------------------
if "graph" not in st.session_state:
    st.session_state.graph = {"nodes": [], "edges": []}

graph = st.session_state.graph

# Provide a visible starting point the first time
if not graph["nodes"]:
    graph["nodes"] = [
        {"id": "1", "data": {"label": "Start"}, "kind": "event"},
        {"id": "2", "data": {"label": "Decision"}, "kind": "decision"},
        {"id": "3", "data": {"label": "Result"}, "kind": "result"},
    ]
    graph["edges"] = [
        {"id": "e1", "source": "1", "target": "2", "label": "Next"},
        {"id": "e2", "source": "2", "target": "3", "label": "Outcome"},
    ]

# ---------------------------
# Toolbar (no JSON import/export)
# ---------------------------
st.markdown("### Actions")
c1, c2, c3 = st.columns(3)

with c1:
    if st.button(
        "🗑 Clear Canvas",
        use_container_width=True,
        help="Remove all nodes and edges from the canvas.",
    ):
        st.session_state.graph = {"nodes": [], "edges": []}
        st.rerun()

with c2:
    if st.button(
        "⚙ Auto-Compute Probabilities",
        use_container_width=True,
        help="Evenly distribute probabilities on decision nodes if none are set.",
    ):
        graph_ops.auto_compute_probabilities(graph)
        st.success("Probabilities auto-computed.")
        st.rerun()

with c3:
    show_debug = st.toggle(
        "🔍 Debug graph",
        value=False,
        help="Show the raw graph dict stored in session state.",
    )

# ---------------------------
# Sidebar – Node & Edge Management
# ---------------------------
st.sidebar.header("🛠 Node Management")

with st.sidebar.expander("➕ Add Node", expanded=True):
    with st.form("add_node_form", clear_on_submit=True):
        new_label = st.text_input("Label", placeholder="e.g. New Event")
        node_type = st.selectbox("Type", ["event", "decision", "result"])
        submitted = st.form_submit_button("Add Node")
        if submitted and new_label.strip():
            graph["nodes"].append(
                {"id": new_node_id(), "data": {"label": new_label}, "kind": node_type}
            )
            st.rerun()

st.sidebar.header("🔗 Edge Management")
if len(graph["nodes"]) >= 2:
    with st.sidebar.expander("➕ Add Edge", expanded=True):
        node_labels = {n["id"]: n["data"]["label"] for n in graph["nodes"]}
        with st.form("add_edge_form", clear_on_submit=True):
            source = st.selectbox(
                "Source", list(node_labels.keys()), format_func=lambda x: node_labels[x]
            )
            target = st.selectbox(
                "Target",
                [n["id"] for n in graph["nodes"] if n["id"] != source],
                format_func=lambda x: node_labels[x],
            )
            edge_label = st.text_input("Edge label (optional)")
            edge_prob_enabled = st.checkbox("Add probability")
            edge_prob = (
                st.number_input("Probability", 0.0, 1.0, 0.5, 0.01)
                if edge_prob_enabled
                else None
            )
            if st.form_submit_button("Add Edge"):
                if source == target:
                    st.warning("Cannot connect a node to itself.")
                else:
                    graph["edges"].append(
                        {
                            "id": new_edge_id(),
                            "source": source,
                            "target": target,
                            "label": edge_label or None,
                            "data": {"prob": edge_prob} if edge_prob_enabled else {},
                        }
                    )
                    st.rerun()

# ---------------------------
# Validation Warnings
# ---------------------------
warnings = graph_ops.validate_graph(graph)
if warnings:
    st.markdown("#### ⚠️ Warnings")
    for w in warnings:
        st.warning(w)

# ---------------------------
# Debug (optional)
# ---------------------------
if show_debug:
    st.markdown("#### Raw graph")
    st.code(json.dumps(graph, indent=2))

# ---------------------------
# Canvas Visualization (with mini-map & zoom controls)
# ---------------------------
st.markdown("### Canvas")

# Safely embed the Python dict into JS
graph_json = json.dumps(graph).replace("\\", "\\\\").replace("'", "\\'")

vis_html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
  <style>
    html, body { margin: 0; height: 100%; background: #f8fafc; }
    #network { height: 620px; background: #f1f5f9; border-radius: 8px; border: 1px solid #cbd5e1; position: relative; }
    #controls {
      position: absolute;
      top: 10px;
      left: 10px;
      z-index: 999;
      display: flex;
      gap: 6px;
    }
    .btn {
      padding: 4px 8px;
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    }
    .btn:hover {
      background: #1e40af;
    }
    #miniMap {
      position: absolute;
      bottom: 10px;
      right: 10px;
      width: 150px;
      height: 100px;
      border: 1px solid #ccc;
      border-radius: 4px;
      background: white;
      overflow: hidden;
      z-index: 998;
    }
    #exportBtn {
      position: absolute;
      top: 10px;
      right: 10px;
      z-index: 999;
      padding: 4px 8px;
      background: #22c55e;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    }
    #exportBtn:hover { background: #15803d; }
  </style>
</head>
<body>
  <div id="network"></div>

  <div id="controls">
    <button class="btn" id="zoomIn">+</button>
    <button class="btn" id="zoomOut">-</button>
    <button class="btn" id="fit">Fit</button>
  </div>

  <button id="exportBtn">Export PNG</button>
  <div id="miniMap"></div>

  <script>
    const graph = JSON.parse('{graph_json}');
    const nodes = new vis.DataSet(graph.nodes.map(n => ({
      id: n.id,
      label: n.data.label,
      shape: "box",
      color: {
        background: n.kind === "decision" ? "#e6f7eb" :
                    n.kind === "result" ? "#fff1e6" : "#e0ecff",
        border: n.kind === "decision" ? "#16a34a" :
                n.kind === "result" ? "#f97316" : "#1d4ed8",
      },
      borderWidth: 2,
      margin: 10,
    })));

    const edges = new vis.DataSet(graph.edges.map(e => ({
      id: e.id,
      from: e.source,
      to: e.target,
      label: (e.label || "") + (e.data.prob !== undefined ? ` (p=${e.data.prob})` : "")
    })));

    const container = document.getElementById('network');
    const data = { nodes, edges };
    const options = {
      layout: { hierarchical: false },
      physics: {
        enabled: true,
        solver: "forceAtlas2Based",
        stabilization: { iterations: 120 }
      },
      edges: { arrows: { to: { enabled: true } }, smooth: false },
      interaction: { dragView: true, zoomView: true }
    };

    const network = new vis.Network(container, data, options);
    network.fit(); // center on first render

    // Mini-map
    const miniMapContainer = document.getElementById('miniMap');
    const miniMap = new vis.Network(miniMapContainer, data, {
      interaction: { dragNodes: false, dragView: false, zoomView: false },
      physics: false
    });

    // Zoom controls
    document.getElementById('zoomIn').addEventListener('click', () => {
      const scale = network.getScale();
      network.moveTo({ scale: scale * 1.2 });
    });

    document.getElementById('zoomOut').addEventListener('click', () => {
      const scale = network.getScale();
      network.moveTo({ scale: scale / 1.2 });
    });

    document.getElementById('fit').addEventListener('click', () => {
      network.fit();
    });

    // Export PNG
    document.getElementById('exportBtn').addEventListener('click', () => {
      html2canvas(container).then(canvas => {
        const link = document.createElement('a');
        link.download = 'decision_tree.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
      });
    });
  </script>
</body>
</html>
""".replace("{graph_json}", graph_json)

components.html(vis_html, height=650, scrolling=False)
