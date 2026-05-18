import { useMemo, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  ReactFlow,
  Position,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircuitBoard,
  Cpu,
  FileText,
  Gauge,
  GitBranch,
  Layers3,
  Lightbulb,
  Radio,
  Search,
  SlidersHorizontal,
  Workflow,
  Zap,
} from "lucide-react";
import { flows, nodeDetails, views } from "./flowData.js";

const iconByLayer = {
  software: FileText,
  firmware: Cpu,
  circuit: CircuitBoard,
  physical: Lightbulb,
  transport: Radio,
};

const statusIcon = {
  working: CheckCircle2,
  ready: CheckCircle2,
  suspect: AlertTriangle,
  bottleneck: Gauge,
  blocked: AlertTriangle,
  experimental: SlidersHorizontal,
};

function makeFlow(viewId, query) {
  const flow = flows[viewId] || flows.system;
  const q = query.trim().toLowerCase();
  const nodeRows = flow.nodes || [];
  const visibleIds = new Set(
    nodeRows
      .filter(([id]) => {
        if (!q) return true;
        const item = nodeDetails[id];
        return [item.title, item.summary, item.layer, item.system, item.status, ...(item.parameters || [])]
          .join(" ")
          .toLowerCase()
          .includes(q);
      })
      .map(([id]) => id),
  );

  const nodes = nodeRows
    .filter(([id]) => visibleIds.has(id))
    .map(([id, x, y]) => ({
      id,
      type: "lifiNode",
      position: { x, y },
      data: nodeDetails[id],
    }));

  const edges = (flow.edges || [])
    .filter(([source, target]) => visibleIds.has(source) && visibleIds.has(target))
    .map(([source, target]) => ({
      id: `${source}-${target}`,
      source,
      target,
      animated: ["adcThreshold", "manchesterRx"].includes(source) || ["adcThreshold", "manchesterRx"].includes(target),
      type: "smoothstep",
      className: nodeDetails[target]?.status === "bottleneck" ? "edge-warn" : "",
    }));

  return { nodes, edges };
}

function LifiNode({ data, selected }) {
  const LayerIcon = iconByLayer[data.layer] || Layers3;
  const StatusIcon = statusIcon[data.status] || Activity;

  return (
    <button className={`lifi-node status-${data.status} ${selected ? "selected" : ""}`} type="button">
      <Handle type="target" position={Position.Left} />
      <div className="node-top">
        <span className="node-icon">
          <LayerIcon size={18} />
        </span>
        <span className="node-status">
          <StatusIcon size={15} />
          {data.status}
        </span>
      </div>
      <strong>{data.title}</strong>
      <span>{data.summary}</span>
      <Handle type="source" position={Position.Right} />
    </button>
  );
}

const nodeTypes = { lifiNode: LifiNode };

function DetailPanel({ selectedId }) {
  const item = nodeDetails[selectedId] || nodeDetails.adcThreshold;
  const StatusIcon = statusIcon[item.status] || Activity;

  return (
    <aside className="details">
      <div className="details-head">
        <span className={`detail-status status-${item.status}`}>
          <StatusIcon size={16} />
          {item.status}
        </span>
        <span>{item.system.toUpperCase()}</span>
      </div>
      <h2>{item.title}</h2>
      <p>{item.summary}</p>

      <section>
        <h3>Parameters</h3>
        <ul>
          {item.parameters.map((param) => (
            <li key={param}>{param}</li>
          ))}
        </ul>
      </section>

      <section>
        <h3>Evidence</h3>
        <ul>
          {item.evidence.map((source) => (
            <li key={source}>{source}</li>
          ))}
        </ul>
      </section>
    </aside>
  );
}

function EvolutionView() {
  return (
    <div className="timeline">
      <div className="timeline-title">
        <GitBranch size={20} />
        Repo Evolution
      </div>
      {flows.evolution.timeline.map(([hash, label], index) => (
        <div className="timeline-row" key={`${hash}-${label}`}>
          <span>{String(index + 1).padStart(2, "0")}</span>
          <strong>{hash}</strong>
          <p>{label}</p>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [activeView, setActiveView] = useState("system");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState("adcThreshold");
  const initial = useMemo(() => makeFlow(activeView, query), [activeView, query]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);

  useMemo(() => {
    setNodes(initial.nodes);
    setEdges(initial.edges);
  }, [initial, setEdges, setNodes]);

  const counts = Object.values(nodeDetails).reduce(
    (acc, item) => {
      acc[item.status] = (acc[item.status] || 0) + 1;
      return acc;
    },
    {},
  );

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span>
            <Workflow size={24} />
          </span>
          <div>
            <h1>LiFi Workflow Planner</h1>
            <p>System flow, physical circuit, theory, and live bottleneck map</p>
          </div>
        </div>
        <div className="health">
          <span><CheckCircle2 size={16} /> {counts.working + counts.ready} stable</span>
          <span><AlertTriangle size={16} /> {counts.suspect} suspect</span>
          <span><Zap size={16} /> {counts.bottleneck} bottleneck</span>
        </div>
      </header>

      <main className="workspace">
        <nav className="sidebar">
          {views.map((view) => (
            <button
              className={activeView === view.id ? "active" : ""}
              key={view.id}
              onClick={() => setActiveView(view.id)}
              type="button"
            >
              {view.label}
            </button>
          ))}
        </nav>

        <section className="canvas-wrap">
          <div className="toolbar">
            <div className="search">
              <Search size={17} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search nodes, parameters, evidence"
              />
            </div>
            <div className="mode-label">{views.find((view) => view.id === activeView)?.label}</div>
          </div>

          {activeView === "evolution" ? (
            <EvolutionView />
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={(_, node) => setSelectedId(node.id)}
              fitView
              minZoom={0.25}
              maxZoom={1.5}
            >
              <Background gap={22} color="#d6e3ea" />
              <Controls showInteractive={false} />
              <MiniMap pannable zoomable nodeStrokeWidth={3} />
            </ReactFlow>
          )}
        </section>

        <DetailPanel selectedId={selectedId} />
      </main>
    </div>
  );
}
