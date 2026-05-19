import { useEffect, useMemo, useRef, useState } from "react";
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
  Download,
  Cpu,
  FileText,
  Gauge,
  GitBranch,
  Layers3,
  Lightbulb,
  Radio,
  Search,
  SlidersHorizontal,
  Trash2,
  ZoomIn,
  Workflow,
  Zap,
} from "lucide-react";
import { evolutionDetails, flows, lifiVersions, nodeDetails, recommendations, views } from "./flowData.js";

const NOTES_KEY = "lifi-planner-notes-v1";
const COMPONENTS_KEY = "lifi-schematic-components-v1";
const NAV_MIN = 76;
const NAV_MAX = 240;
const DETAIL_MIN = 260;
const DETAIL_MAX = 560;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function readStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

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

function makeFlow(viewId, query, details = nodeDetails) {
  const flow = flows[viewId] || flows.system;
  const q = query.trim().toLowerCase();
  const nodeRows = flow.nodes || [];
  const visibleIds = new Set(
    nodeRows
      .filter(([id]) => {
        if (!q) return true;
        const item = details[id];
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
      data: details[id],
    }));

  const edges = (flow.edges || [])
    .filter(([source, target]) => visibleIds.has(source) && visibleIds.has(target))
    .map(([source, target]) => ({
      id: `${source}-${target}`,
      source,
      target,
      animated: ["adcThreshold", "manchesterRx"].includes(source) || ["adcThreshold", "manchesterRx"].includes(target),
      type: "smoothstep",
      className: details[target]?.status === "bottleneck" ? "edge-warn" : "",
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

function DetailPanel({ selectedId, notes, onNoteChange, onSubmit, details }) {
  const item = details[selectedId] || details.adcThreshold;
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

      <section>
        <h3>Node Comment For Codex</h3>
        <textarea
          className="node-note"
          value={notes[selectedId] || ""}
          onChange={(event) => onNoteChange(selectedId, event.target.value)}
          placeholder="Write what you noticed, what you suggest, or what you want Codex to change for this node."
        />
        <h3 className="sub-note-title">System Comment</h3>
        <textarea
          className="node-note system-note"
          value={notes.system_overall || ""}
          onChange={(event) => onNoteChange("system_overall", event.target.value)}
          placeholder="Write a project-level note, test result, or recommendation that is not tied to only this node."
        />
        <button className="wide-action" onClick={() => onSubmit(true)} type="button">
          <Download size={15} />
          Submit notes to repo
        </button>
      </section>
    </aside>
  );
}

function EvolutionView() {
  const [selected, setSelected] = useState("4d78a01");

  return (
    <div className="timeline">
      <div className="timeline-title">
        <GitBranch size={20} />
        Repo Evolution
      </div>
      <div className="timeline-grid">
        <div>
          {flows.evolution.timeline.map(([hash, label], index) => (
            <button className={`timeline-row ${selected === hash ? "active" : ""}`} key={`${hash}-${label}`} onClick={() => setSelected(hash)} type="button">
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{hash}</strong>
              <p>{label}</p>
            </button>
          ))}
        </div>
        <aside className="history-detail">
          <strong>{selected}</strong>
          <p>{evolutionDetails[selected] || "No detailed note yet."}</p>
        </aside>
      </div>
    </div>
  );
}

function RecommendationsView() {
  return (
    <div className="recommendations">
      <div className="timeline-title">
        <Lightbulb size={20} />
        Recommendations And Study Path
      </div>
      <div className="recommendation-grid">
        {recommendations.map((item) => (
          <article className="recommendation-card" key={item.title}>
            <span>{item.priority}</span>
            <h2>{item.title}</h2>
            <p>{item.summary}</p>
            <ul>
              {item.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </div>
  );
}

function Symbol({ type }) {
  if (type === "resistor") {
    return <polyline points="8,32 16,32 20,20 28,44 36,20 44,44 52,20 60,44 64,32 72,32" />;
  }
  if (type === "mosfet") {
    return (
      <>
        <line x1="38" y1="12" x2="38" y2="52" />
        <line x1="48" y1="14" x2="48" y2="26" />
        <line x1="48" y1="38" x2="48" y2="50" />
        <line x1="10" y1="32" x2="34" y2="32" />
        <line x1="48" y1="14" x2="70" y2="14" />
        <line x1="48" y1="50" x2="70" y2="50" />
        <polyline points="54,32 46,28 46,36 54,32" />
      </>
    );
  }
  if (type === "led") {
    return (
      <>
        <polygon points="26,18 26,46 50,32" />
        <line x1="50" y1="18" x2="50" y2="46" />
        <line x1="8" y1="32" x2="26" y2="32" />
        <line x1="50" y1="32" x2="72" y2="32" />
        <line x1="54" y1="14" x2="66" y2="4" />
        <polyline points="62,4 66,4 66,8" />
        <line x1="58" y1="22" x2="74" y2="12" />
        <polyline points="70,12 74,12 74,16" />
      </>
    );
  }
  if (type === "phototransistor") {
    return (
      <>
        <circle cx="40" cy="32" r="22" />
        <line x1="40" y1="12" x2="40" y2="52" />
        <line x1="40" y1="18" x2="58" y2="8" />
        <line x1="40" y1="46" x2="58" y2="56" />
        <polyline points="22,8 34,18 30,20" />
        <polyline points="14,18 28,26 24,29" />
      </>
    );
  }
  if (type === "photodiode") {
    return (
      <>
        <circle cx="40" cy="32" r="22" />
        <polygon points="26,18 26,46 50,32" />
        <line x1="50" y1="18" x2="50" y2="46" />
        <polyline points="18,8 31,18 27,21" />
        <polyline points="10,18 24,27 20,30" />
      </>
    );
  }
  if (type === "opamp") {
    return (
      <>
        <polygon points="18,10 18,54 64,32" />
        <text x="24" y="27">-</text>
        <text x="24" y="44">+</text>
        <line x1="6" y1="24" x2="18" y2="24" />
        <line x1="6" y1="42" x2="18" y2="42" />
        <line x1="64" y1="32" x2="76" y2="32" />
      </>
    );
  }
  if (type === "comparator") {
    return (
      <>
        <polygon points="18,10 18,54 64,32" />
        <text x="24" y="27">+</text>
        <text x="24" y="44">-</text>
        <line x1="6" y1="24" x2="18" y2="24" />
        <line x1="6" y1="42" x2="18" y2="42" />
        <line x1="64" y1="32" x2="76" y2="32" />
        <path d="M68 20 h10 v24 h-10" />
      </>
    );
  }
  return (
    <>
      <rect x="12" y="12" width="56" height="40" rx="4" />
      <text x="40" y="36" textAnchor="middle">ESP32</text>
      {Array.from({ length: 5 }).map((_, i) => (
        <line key={i} x1="8" y1={18 + i * 7} x2="12" y2={18 + i * 7} />
      ))}
      {Array.from({ length: 5 }).map((_, i) => (
        <line key={i} x1="68" y1={18 + i * 7} x2="72" y2={18 + i * 7} />
      ))}
    </>
  );
}

function ComponentCard({ type, title, note }) {
  return (
    <div className="component-card">
      <svg viewBox="0 0 80 64" aria-hidden="true">
        <Symbol type={type} />
      </svg>
      <div>
        <strong>{title}</strong>
        <span>{note}</span>
      </div>
    </div>
  );
}

const defaultComponents = lifiVersions.find((version) => version.id === "current")?.schematicComponents || [];

function ComponentEditor({ components, setComponents, onSubmit, readOnly = false }) {
  const update = (id, field, value) => {
    if (readOnly) return;
    setComponents((items) => items.map((item) => (item.id === id ? { ...item, [field]: value } : item)));
  };

  const add = () => {
    if (readOnly) return;
    setComponents((items) => [
      ...items,
      { id: `custom_${Date.now()}`, type: "resistor", name: "New component", value: "10k ohm", note: "Edit this component" },
    ]);
  };

  const remove = (id) => {
    if (readOnly) return;
    setComponents((items) => items.filter((item) => item.id !== id));
  };

  return (
    <section className="component-editor">
      <div className="editor-head">
        <h2>{readOnly ? "Historical Component Values" : "Editable Component Values"}</h2>
        <div>
          {!readOnly ? <button onClick={add} type="button">Add</button> : null}
          {!readOnly ? <button onClick={() => onSubmit(true)} type="button"><Download size={14} /> Submit</button> : null}
        </div>
      </div>
      {components.map((item) => (
        <div className="component-row" key={item.id}>
          <select disabled={readOnly} value={item.type} onChange={(event) => update(item.id, "type", event.target.value)}>
            <option value="esp32">ESP32</option>
            <option value="resistor">Resistor</option>
            <option value="mosfet">MOSFET</option>
            <option value="led">LED</option>
            <option value="phototransistor">Phototransistor</option>
            <option value="photodiode">Photodiode</option>
            <option value="opamp">Op-Amp/TIA</option>
            <option value="comparator">Comparator</option>
          </select>
          <input readOnly={readOnly} value={item.name} onChange={(event) => update(item.id, "name", event.target.value)} />
          <input readOnly={readOnly} value={item.value} onChange={(event) => update(item.id, "value", event.target.value)} />
          <input readOnly={readOnly} value={item.note} onChange={(event) => update(item.id, "note", event.target.value)} />
          {!readOnly ? <button aria-label={`Remove ${item.name}`} onClick={() => remove(item.id)} type="button"><Trash2 size={15} /></button> : <span className="read-only-mark">past</span>}
        </div>
      ))}
    </section>
  );
}

function Waveform({ frequency, frontEnd }) {
  const periodUs = Math.round(1000000 / frequency);
  const halfUs = Math.round(periodUs / 2);
  const analogDelay = frontEnd === "tia" ? "fast, high gain" : frontEnd === "comparator" ? "squared by threshold" : "slower RC edge";

  return (
    <div className="wave-panel">
      <div>
        <h3>{frequency.toLocaleString()} Hz Behavior Model</h3>
        <p>At {frequency.toLocaleString()} Hz, one bit period is about {periodUs} us, with {halfUs} us per Manchester half-bit.</p>
      </div>
      <svg viewBox="0 0 720 210" role="img" aria-label="Simplified LiFi waveform">
        <text x="18" y="28">TX LED current</text>
        <polyline className="digital-wave" points="150,45 190,45 190,18 230,18 230,45 270,45 270,18 310,18 310,45 350,45 350,18 390,18 390,45 430,45 430,18 470,18 470,45 510,45 510,18 550,18 550,45 590,45" />
        <text x="18" y="98">Sensor voltage</text>
        <path className="analog-wave" d="M150 115 C175 115 178 82 195 82 C220 82 218 115 235 115 C260 115 258 82 275 82 C300 82 298 115 315 115 C340 115 338 82 355 82 C380 82 378 115 395 115 C420 115 418 82 435 82 C460 82 458 115 475 115 C500 115 498 82 515 82 C540 82 538 115 555 115 C575 115 575 115 590 115" />
        <text x="18" y="168">Comparator / ADC logic</text>
        <polyline className="digital-wave rx" points="150,185 195,185 195,154 235,154 235,185 275,185 275,154 315,154 315,185 355,185 355,154 395,154 395,185 435,185 435,154 475,154 475,185 515,185 515,154 555,154 555,185 590,185" />
      </svg>
      <p className="wave-note">Sensor output depends on light intensity, resistor value, capacitance, and front-end. Current issue: ADC threshold sits close to the measured sensor swing, so the logic waveform collapses.</p>
      <p className="wave-note">Selected front-end: {analogDelay}.</p>
    </div>
  );
}

function SchematicWorkbench({ components, setComponents, onSubmit, selectedVersion }) {
  const [frequency, setFrequency] = useState(9000);
  const [sensor, setSensor] = useState("phototransistor");
  const [frontEnd, setFrontEnd] = useState("divider");
  const isCurrentVersion = selectedVersion.id === "current";
  const shownComponents = isCurrentVersion ? components : selectedVersion.schematicComponents;

  return (
    <div className="schematic-workbench">
      <section className="schematic-palette">
        <h2>Schematic Symbols</h2>
        <p className="version-note">{selectedVersion.short}: {selectedVersion.summary}</p>
        <ComponentCard type="esp32" title="ESP32" note="TX GPIO5 / RX ADC GPIO34" />
        <ComponentCard type="resistor" title="Resistor" note="220 ohm gate, 10k load/pulldown" />
        <ComponentCard type="mosfet" title="N-MOSFET" note="IRLZ44N low-side LED switch" />
        <ComponentCard type="led" title="LED Bulb" note="Visible light carrier source" />
        <ComponentCard type="phototransistor" title="Phototransistor" note="TEPT4400 style receiver" />
        <ComponentCard type="photodiode" title="Photodiode" note="Alternative faster sensor" />
        <ComponentCard type="opamp" title="TIA Op-Amp" note="Photodiode current-to-voltage" />
        <ComponentCard type="comparator" title="Comparator" note="Clean digital threshold output" />
      </section>

      <section className="schematic-main">
        <div className="schematic-controls">
          <label>
            Test Frequency
            <input min="1000" max="15000" step="500" type="range" value={frequency} onChange={(event) => setFrequency(Number(event.target.value))} />
            <span>{frequency.toLocaleString()} Hz</span>
          </label>
          <label>
            Sensor
            <select value={sensor} onChange={(event) => setSensor(event.target.value)}>
              <option value="phototransistor">Phototransistor</option>
              <option value="photodiode">Photodiode</option>
            </select>
          </label>
          <label>
            RX Front-End
            <select value={frontEnd} onChange={(event) => setFrontEnd(event.target.value)}>
              <option value="divider">Simple divider</option>
              <option value="tia">TIA amplifier</option>
              <option value="comparator">Comparator output</option>
            </select>
          </label>
        </div>

        <div className="schematic-sheet">
          <svg viewBox="0 0 980 430" role="img" aria-label="LiFi schematic sheet">
            <defs>
              <marker id="arrow" markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4">
                <path d="M0,0 L8,4 L0,8 z" />
              </marker>
            </defs>
            <text className="sheet-title" x="26" y="34">Low-Cost LiFi Communication Circuit</text>
            <line className="ground-bus" x1="40" y1="365" x2="930" y2="365" />
            <text className="ground-label" x="44" y="392">common ground reference</text>

            <g className="schem-block" transform="translate(30 80)">
              <rect width="190" height="250" rx="8" />
              <text x="18" y="30">TX ESP32</text>
              <g className="schem-symbol" transform="translate(58 52) scale(1.05)">
                <Symbol type="esp32" />
              </g>
              <text x="18" y="172">GPIO5 Manchester</text>
              <text x="18" y="196">1-15 kHz test range</text>
            </g>

            <line className="wire" x1="220" y1="205" x2="285" y2="205" />
            <g className="schem-symbol" transform="translate(282 173)">
              <Symbol type="resistor" />
            </g>
            <text x="302" y="168">220 ohm</text>
            <line className="wire" x1="355" y1="205" x2="420" y2="205" />

            <g className="schem-symbol" transform="translate(410 145) scale(1.2)">
              <Symbol type="mosfet" />
            </g>
            <text x="416" y="132">IRLZ44N</text>
            <line className="wire" x1="486" y1="162" x2="548" y2="162" />
            <g className="schem-symbol" transform="translate(548 130)">
              <Symbol type="led" />
            </g>
            <text x="552" y="120">12 V LED bulb</text>
            <line className="wire" x1="486" y1="240" x2="486" y2="300" />
            <line className="wire" x1="486" y1="300" x2="486" y2="365" />
            <polyline className="ground-symbol" points="466,300 506,300 498,310 474,310 482,320 490,320" />

            <line className="light-ray" x1="640" y1="162" x2="735" y2="160" markerEnd="url(#arrow)" />
            <line className="light-ray" x1="640" y1="180" x2="735" y2="204" markerEnd="url(#arrow)" />
            <text x="648" y="136">modulated light</text>

            <g className="schem-block" transform="translate(735 80)">
              <rect width="210" height="250" rx="8" />
              <text x="18" y="30">RX Front-End</text>
              <g className="schem-symbol" transform="translate(24 52)">
                <Symbol type={sensor} />
              </g>
              <text x="112" y="86">{sensor === "phototransistor" ? "TEPT4400" : "Photodiode"}</text>
              <g className="schem-symbol" transform="translate(22 135)">
                <Symbol type={frontEnd === "divider" ? "resistor" : frontEnd === "tia" ? "opamp" : "comparator"} />
              </g>
              <text x="112" y="164">{frontEnd === "divider" ? "load resistor" : frontEnd === "tia" ? "transimpedance" : "threshold logic"}</text>
              <text x="18" y="222">Output to ESP32 GPIO34</text>
              <line className="wire" x1="108" y1="250" x2="108" y2="285" />
            </g>
            <line className="wire" x1="843" y1="330" x2="843" y2="365" />
            <polyline className="ground-symbol" points="823,330 863,330 855,340 831,340 839,350 847,350" />
          </svg>
        </div>

        <Waveform frequency={frequency} frontEnd={frontEnd} />
        <ComponentEditor components={shownComponents} setComponents={setComponents} onSubmit={onSubmit} readOnly={!isCurrentVersion} />
      </section>
    </div>
  );
}

function VersionSelector({ selectedVersion, onSelect }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="version-selector">
      <button className="version-trigger" onClick={() => setOpen((value) => !value)} type="button">
        <GitBranch size={15} />
        <span>{selectedVersion.short}</span>
      </button>
      {open ? (
        <div className="version-menu">
          <div className="version-menu-title">Repo Version Ladder</div>
          {lifiVersions.map((version, index) => (
            <button
              className={`version-row ${selectedVersion.id === version.id ? "active" : ""}`}
              key={version.id}
              onClick={() => {
                onSelect(version.id);
                setOpen(false);
              }}
              type="button"
            >
              <span className="version-step">{String(index + 1).padStart(2, "0")}</span>
              <span>
                <strong>{version.label}</strong>
                <small>{version.hash} · {version.period}</small>
                <em>{version.summary}</em>
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function App() {
  const [activeView, setActiveView] = useState("system");
  const [activeVersionId, setActiveVersionId] = useState("current");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState("adcThreshold");
  const [panelOpen, setPanelOpen] = useState(true);
  const [navOpen, setNavOpen] = useState(true);
  const [navWidth, setNavWidth] = useState(() => clamp(Number(readStorage("lifi-nav-width-v1", 112)) || 112, NAV_MIN, NAV_MAX));
  const [detailWidth, setDetailWidth] = useState(() => clamp(Number(readStorage("lifi-detail-width-v1", 340)) || 340, DETAIL_MIN, DETAIL_MAX));
  const [scrollMode, setScrollMode] = useState("pan");
  const [notes, setNotes] = useState(() => readStorage(NOTES_KEY, {}));
  const [components, setComponents] = useState(() => readStorage(COMPONENTS_KEY, defaultComponents));
  const [saveStatus, setSaveStatus] = useState("local only");
  const [lastServerSavedAt, setLastServerSavedAt] = useState("");
  const hydratedRef = useRef(false);
  const latestServerSavedAtRef = useRef("");
  const payloadRef = useRef(null);
  const resizeRef = useRef(null);
  const selectedVersion = useMemo(
    () => lifiVersions.find((version) => version.id === activeVersionId) || lifiVersions[0],
    [activeVersionId],
  );
  const versionDetails = useMemo(() => {
    const overrides = selectedVersion.nodeOverrides || {};
    return Object.fromEntries(
      Object.entries(nodeDetails).map(([id, item]) => [id, { ...item, ...(overrides[id] || {}) }]),
    );
  }, [selectedVersion]);
  const initial = useMemo(() => makeFlow(activeView, query, versionDetails), [activeView, query, versionDetails]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);

  useEffect(() => {
    setNodes(initial.nodes);
    setEdges(initial.edges);
  }, [initial, setEdges, setNodes]);

  useEffect(() => {
    localStorage.setItem(NOTES_KEY, JSON.stringify(notes));
  }, [notes]);

  useEffect(() => {
    localStorage.setItem(COMPONENTS_KEY, JSON.stringify(components));
  }, [components]);

  useEffect(() => {
    localStorage.setItem("lifi-nav-width-v1", JSON.stringify(navWidth));
  }, [navWidth]);

  useEffect(() => {
    localStorage.setItem("lifi-detail-width-v1", JSON.stringify(detailWidth));
  }, [detailWidth]);

  useEffect(() => {
    const onPointerMove = (event) => {
      if (!resizeRef.current) return;
      const { kind, startX, startWidth } = resizeRef.current;
      const delta = event.clientX - startX;
      if (kind === "nav") {
        setNavWidth(clamp(startWidth + delta, NAV_MIN, NAV_MAX));
      } else {
        setDetailWidth(clamp(startWidth - delta, DETAIL_MIN, DETAIL_MAX));
      }
    };

    const onPointerUp = () => {
      resizeRef.current = null;
      document.body.classList.remove("is-resizing");
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);
    };
  }, []);

  useEffect(() => {
    payloadRef.current = {
      activeView,
      activeVersionId,
      selectedId,
      notes,
      schematicComponents: components,
    };
  }, [activeView, activeVersionId, selectedId, notes, components]);

  const counts = Object.values(versionDetails).reduce(
    (acc, item) => {
      acc[item.status] = (acc[item.status] || 0) + 1;
      return acc;
    },
    {},
  );

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Escape") setPanelOpen(false);
      if (event.key.toLowerCase() === "d" && !event.metaKey && !event.ctrlKey) {
        setPanelOpen((open) => !open);
      }
      if (event.key.toLowerCase() === "n" && !event.metaKey && !event.ctrlKey) {
        setNavOpen((open) => !open);
      }
      if (event.key === "/" && document.activeElement?.tagName !== "INPUT") {
        event.preventDefault();
        document.querySelector(".search input")?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const updateNote = (id, value) => setNotes((current) => ({ ...current, [id]: value }));
  const startResize = (kind, event) => {
    event.preventDefault();
    resizeRef.current = {
      kind,
      startX: event.clientX,
      startWidth: kind === "nav" ? navWidth : detailWidth,
    };
    document.body.classList.add("is-resizing");
  };

  const resizeWithKeyboard = (kind, event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const step = event.shiftKey ? 24 : 8;
    const direction = event.key === "ArrowRight" ? 1 : -1;
    if (kind === "nav") {
      setNavWidth((width) => clamp(width + direction * step, NAV_MIN, NAV_MAX));
    } else {
      setDetailWidth((width) => clamp(width - direction * step, DETAIL_MIN, DETAIL_MAX));
    }
  };

  const submitPlannerState = async (archive = false) => {
    const payload = {
      ...(payloadRef.current || {}),
      archive,
      exportedAt: new Date().toISOString(),
    };

    setSaveStatus("saving...");
    try {
      const response = await fetch("/api/handoff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      latestServerSavedAtRef.current = result.savedAt;
      setLastServerSavedAt(result.savedAt);
      setSaveStatus(`saved to ${result.path}`);
      return true;
    } catch (error) {
      setSaveStatus("server unavailable; saved in this browser only");
      return false;
    }
  };

  useEffect(() => {
    const loadLatest = async () => {
      try {
        const response = await fetch("/api/handoff/latest", { cache: "no-store" });
        if (response.status === 204 || !response.ok) {
          hydratedRef.current = true;
          return;
        }
        const payload = await response.json();
        if (payload.savedAt && payload.savedAt !== latestServerSavedAtRef.current) {
          latestServerSavedAtRef.current = payload.savedAt;
          setLastServerSavedAt(payload.savedAt);
        if (payload.notes) setNotes(payload.notes);
        if (payload.schematicComponents) setComponents(payload.schematicComponents);
        if (payload.activeView) setActiveView(payload.activeView);
        if (payload.activeVersionId) setActiveVersionId(payload.activeVersionId);
        if (payload.selectedId) setSelectedId(payload.selectedId);
          setSaveStatus("synced from repo handoff");
        }
      } catch {
        setSaveStatus("local only");
      } finally {
        hydratedRef.current = true;
      }
    };

    loadLatest();
    const interval = window.setInterval(loadLatest, 4000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!hydratedRef.current) return;
    const timer = window.setTimeout(() => {
      submitPlannerState(false);
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [notes, components]);

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
          <span><Download size={16} /> {saveStatus}</span>
        </div>
      </header>

      <main
        className={`workspace ${panelOpen ? "" : "panel-closed"} ${navOpen ? "" : "nav-closed"}`}
        style={{ "--nav-width": `${navWidth}px`, "--detail-width": `${detailWidth}px` }}
      >
        {navOpen ? (
          <>
            <nav className="sidebar">
              {views.map((view) => (
                <div key={view.id} className="nav-item-wrap">
                  {views.findIndex((item) => item.group === view.group) === views.indexOf(view) ? <span className="nav-group">{view.group}</span> : null}
                  <button
                    className={activeView === view.id ? "active" : ""}
                    onClick={() => setActiveView(view.id)}
                    type="button"
                  >
                    {view.label}
                  </button>
                </div>
              ))}
            </nav>
            <div
              aria-label="Resize menu panel"
              aria-orientation="vertical"
              className="resize-handle nav-resize"
              onKeyDown={(event) => resizeWithKeyboard("nav", event)}
              onPointerDown={(event) => startResize("nav", event)}
              role="separator"
              tabIndex={0}
            />
          </>
        ) : null}

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
            <VersionSelector selectedVersion={selectedVersion} onSelect={setActiveVersionId} />
            <button className="panel-toggle" onClick={() => setPanelOpen((open) => !open)} type="button">
              {panelOpen ? "Close details" : "Open details"}
            </button>
            <button className="panel-toggle" onClick={() => setNavOpen((open) => !open)} type="button">
              {navOpen ? "Hide menu" : "Show menu"}
            </button>
            <button className="panel-toggle" onClick={() => submitPlannerState(true)} type="button">
              <Download size={15} />
              Submit status
            </button>
            <button className="panel-toggle" onClick={() => setScrollMode((mode) => (mode === "pan" ? "zoom" : "pan"))} type="button">
              <ZoomIn size={15} />
              {scrollMode === "pan" ? "Scroll pans" : "Scroll zooms"}
            </button>
          </div>

          {activeView === "schematic" ? (
            <SchematicWorkbench components={components} setComponents={setComponents} onSubmit={submitPlannerState} selectedVersion={selectedVersion} />
          ) : activeView === "recommendations" ? (
            <RecommendationsView />
          ) : activeView === "evolution" ? (
            <EvolutionView />
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={(_, node) => setSelectedId(node.id)}
              panOnScroll={scrollMode === "pan"}
              zoomOnScroll={scrollMode === "zoom"}
              zoomOnPinch
              panOnDrag
              selectionOnDrag
              proOptions={{ hideAttribution: true }}
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

        {panelOpen ? (
          <>
            <div
              aria-label="Resize details panel"
              aria-orientation="vertical"
              className="resize-handle detail-resize"
              onKeyDown={(event) => resizeWithKeyboard("detail", event)}
              onPointerDown={(event) => startResize("detail", event)}
              role="separator"
              tabIndex={0}
            />
            <DetailPanel selectedId={selectedId} notes={notes} onNoteChange={updateNote} onSubmit={submitPlannerState} details={versionDetails} />
          </>
        ) : null}
      </main>
    </div>
  );
}
