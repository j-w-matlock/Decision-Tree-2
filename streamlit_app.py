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

def kind_rank(k: str) -> int:
    order = {"event": 0, "decision": 1, "result": 2}
    return order.get(k, 99)

# ---------------------------
# Session state
# ---------------------------
if "graph" not in st.session_state:
    st.session_state.graph = {"nodes": [], "edges": []}

if "selected_node" not in st.session_state:
    st.session_state.selected_node = None

graph = st.session_state.graph

# ---------------------------
# Layout toggle
# ---------------------------
st.markdown("### Actions")
layout_col1, layout_col2, layout_col3 = st.columns([1, 1, 2])

with layout_col1:
    mode = st.radio(
        "Layout",
        ["Freeform", "Left→Right"],
        index=0,
        help="Freeform lets you drag anything anywhere. Left→Right lays it out like a classic decision tree."
    )
st.session_state.layout_mode = mode

with layout_col2:
    if st.button("🗑 Clear Canvas", use_container_width=True):
        st.session_state.graph = {"nodes": [], "edges": []}
        st.rerun()

with layout_col3:
    if st.button("⚙ Auto-Compute", use_container_width=True):
        graph_ops.auto_compute_probabilities(graph)
        st.success("Probabilities auto-computed.")
        st.rerun()

show_debug = st.toggle("🔍 Debug graph", value=False)

# ---------------------------
# Sidebar – Node Management
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

# ---------------------------
# Sidebar – Edge Management
# ---------------------------
st.sidebar.header("🔗 Edge Management")
if len(graph["nodes"]) >= 2:
    with st.sidebar.expander("➕ Add Edge", expanded=True):
        node_labels = {n["id"]: n["data"]["label"] for n in graph["nodes"]}
        with st.form("add_edge_form", clear_on_submit=True):
            source = st.selectbox(
                "First node",
                list(node_labels.keys()),
                format_func=lambda x: f"{node_labels[x]}  [{next(n['kind'] for n in graph['nodes'] if n['id']==x)}]"
            )
            target = st.selectbox(
                "Second node",
                [n["id"] for n in graph["nodes"] if n["id"] != source],
                format_func=lambda x: f"{node_labels[x]}  [{next(n['kind'] for n in graph['nodes'] if n['id']==x)}]"
            )

            auto_orient = st.checkbox(
                "Auto-orient (Event → Decision → Result)",
                value=True
            )
            reverse_dir = st.checkbox(
                "Reverse direction",
                value=False
            )

            edge_label = st.text_input("Edge label (optional)")
            edge_prob_enabled = st.checkbox("Add probability")
            edge_prob = (
                st.number_input("Probability", 0.0, 1.0, 0.5, 0.01)
                if edge_prob_enabled
                else None
            )

            submitted = st.form_submit_button("Add Edge")
            if submitted:
                src_kind = next(n["kind"] for n in graph["nodes"] if n["id"] == source)
                tgt_kind = next(n["kind"] for n in graph["nodes"] if n["id"] == target)
                _source, _target = source, target

                # Auto-orient
                if auto_orient and kind_rank(src_kind) > kind_rank(tgt_kind):
                    _source, _target = target, source

                # Reverse direction
                if reverse_dir:
                    _source, _target = _target, _source

                if _source == _target:
                    st.warning("Cannot connect a node to itself.")
                else:
                    already_exists = any(
                        e for e in graph["edges"]
                        if e["source"] == _source and e["target"] == _target
                    )
                    if already_exists:
                        st.warning("That edge already exists.")
                    else:
                        graph["edges"].append({
                            "id": new_edge_id(),
                            "source": _source,
                            "target": _target,
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
# Delete Selected Node
# ---------------------------
col1, col2 = st.columns([1, 3])
with col1:
    if st.button("🗑 Delete Selected Node", use_container_width=True):
        if st.session_state.selected_node:
            node_id = st.session_state.selected_node
            graph["nodes"] = [n for n in graph["nodes"] if n["id"] != node_id]
            graph["edges"] = [
                e for e in graph["edges"]
                if e["source"] != node_id and e["target"] != node_id
            ]
            st.session_state.selected_node = None
            st.rerun()
        else:
            st.warning("No node selected on the canvas.")

# ---------------------------
# Canvas Visualization
# ---------------------------
st.markdown("### Canvas")
graph_json = json.dumps(graph)
layout_mode = st.session_state.layout_mode

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

  <script id="graphData" type="application/json">{graph_json}</script>
  <script>
    const graph = JSON.parse(document.getElementById('graphData').textContent);
    const layoutMode = "{layout_mode}";

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

    const options = layoutMode === "Left→Right"
      ? {
          layout: {
            hierarchical: {
              enabled: true,
              direction: "LR",
              sortMethod: "directed",
              levelSeparation: 200,
              nodeSpacing: 150,
              treeSpacing: 200
            }
          },
          physics: false,
          edges: { arrows: { to: { enabled: true } }, smooth: false },
          interaction: { dragView: true, zoomView: true }
        }
      : {
          layout: { hierarchical: false },
          physics: { enabled: true, stabilization: { iterations: 100 } },
          edges: { arrows: { to: { enabled: true } }, smooth: false },
          interaction: { dragView: true, zoomView: true }
        };

    const network = new vis.Network(container, data, options);
    network.fit();

    // Track selected node and send to Streamlit
    network.on("selectNode", function(params) {
      const selected = params.nodes[0] || null;
      const streamlitEvent = window.parent;
      if (streamlitEvent) {
        window.parent.postMessage({type: "streamlit:setComponentValue", value: selected}, "*");
      }
    });

    network.on("deselectNode", function() {
      window.parent.postMessage({type: "streamlit:setComponentValue", value: null}, "*");
    });

    document.getElementById('zoomIn').addEventListener('click', () => {
      network.moveTo({ scale: network.getScale() * 1.2 });
    });
    document.getElementById('zoomOut').addEventListener('click', () => {
      network.moveTo({ scale: network.getScale() / 1.2 });
    });
    document.getElementById('fit').addEventListener('click', () => network.fit());

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
""".replace("{graph_json}", graph_json).replace("{layout_mode}", layout_mode)

# Cache-buster
vis_html_with_ts = vis_html + f"<!-- {uuid.uuid4()} -->"
components.html(vis_html_with_ts, height=650, scrolling=False)
