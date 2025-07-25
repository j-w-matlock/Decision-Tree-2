import json
import uuid
import streamlit as st
import streamlit.components.v1 as components
from utils import graph_ops

st.set_page_config(page_title="Decision Tree App", layout="wide")
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

# ---------------------------
# Toolbar
# ---------------------------
st.markdown("### Actions")
toolbar_cols = st.columns(3)

with toolbar_cols[0]:
    if st.button("🗑 Clear Canvas", use_container_width=True):
        st.session_state.graph = {"nodes": [], "edges": []}
        st.rerun()

with toolbar_cols[1]:
    if st.button("⚙ Auto-Compute", use_container_width=True):
        graph_ops.auto_compute_probabilities(graph)
        st.success("Probabilities auto-computed.")
        st.rerun()

with toolbar_cols[2]:
    show_debug = st.toggle("🔍 Debug graph", value=False)

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
            graph["nodes"].append({
                "id": new_node_id(),
                "data": {"label": new_label},
                "kind": node_type
            })
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
                    graph["edges"].append({
                        "id": new_edge_id(),
                        "source": source,
                        "target": target,
                        "label": edge_label or None,
                        "data": {"prob": edge_prob} if edge_prob_enabled else {}
                    })
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
    st.markdown("#### Raw Graph")
    st.code(json.dumps(graph, indent=2))

# ---------------------------
# Canvas Visualization
# ---------------------------
st.markdown("### Canvas")

graph_json = json.dumps(graph)  # Safe JSON

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
    .btn:hover { background: #1e40af; }
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

  <!-- Hidden JSON data -->
  <script id="graphData" type="application/json">{graph_json}</script>

  <script>
    const graph = JSON.parse(document.getElementById('graphData').textContent);

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
      physics: { enabled: true, stabilization: { iterations: 100 } },
      edges: { arrows: { to: { enabled: true } }, smooth: false },
      interaction: { dragView: true, zoomView: true }
    };
    const network = new vis.Network(container, data, options);
    network.fit();

    // Zoom controls
    document.getElementById('zoomIn').addEventListener('click', () => {
      network.moveTo({ scale: network.getScale() * 1.2 });
    });
    document.getElementById('zoomOut').addEventListener('click', () => {
      network.moveTo({ scale: network.getScale() / 1.2 });
    });
    document.getElementById('fit').addEventListener('click', () => network.fit());

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

# Force canvas refresh by adding a unique comment
vis_html_with_ts = vis_html + f"<!-- {uuid.uuid4()} -->"
components.html(vis_html_with_ts, height=650, scrolling=False)
