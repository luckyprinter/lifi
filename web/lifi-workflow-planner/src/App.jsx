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

function isPublicGuestHost() {
  if (typeof window === "undefined") return false;
  return window.location.hostname.endsWith("github.io");
}

function isCompactViewport() {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(max-width: 900px)").matches;
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

function DetailPanel({ selectedId, notes, onNoteChange, onSubmit, details, readOnly = false }) {
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
          readOnly={readOnly}
          value={notes[selectedId] || ""}
          onChange={(event) => onNoteChange(selectedId, event.target.value)}
          placeholder={readOnly ? "Guest view is read-only. Run the local app to write project notes." : "Write what you noticed, what you suggest, or what you want Codex to change for this node."}
        />
        <h3 className="sub-note-title">System Comment</h3>
        <textarea
          className="node-note system-note"
          readOnly={readOnly}
          value={notes.system_overall || ""}
          onChange={(event) => onNoteChange("system_overall", event.target.value)}
          placeholder={readOnly ? "Guest view is read-only. Run the local app to write system notes." : "Write a project-level note, test result, or recommendation that is not tied to only this node."}
        />
        {readOnly ? <p className="read-only-note">Guests can inspect the workflow, schematic, recommendations, and history. Editing is available only from the local owner app.</p> : (
          <button className="wide-action" onClick={() => onSubmit(true)} type="button">
            <Download size={15} />
            Submit notes to repo
          </button>
        )}
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
  if (type === "capacitor") {
    return (
      <>
        <line x1="8" y1="32" x2="32" y2="32" />
        <line x1="32" y1="16" x2="32" y2="48" />
        <line x1="48" y1="16" x2="48" y2="48" />
        <line x1="48" y1="32" x2="72" y2="32" />
      </>
    );
  }
  if (type === "npn") {
    return (
      <>
        <circle cx="40" cy="32" r="25" />
        <line x1="18" y1="32" x2="36" y2="32" />
        <line x1="36" y1="15" x2="36" y2="49" />
        <line x1="36" y1="22" x2="60" y2="8" />
        <line x1="36" y1="42" x2="60" y2="56" />
        <polyline points="52,50 60,56 50,58" />
      </>
    );
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

const txCircuitOptions = {
  bjtIrf540n: {
    label: "TX: 2N3904 + IRF540N",
    note: "Inverting driver: ESP32 drives a 2N3904 base through a resistor. The 2N3904 collector is the IRF540N gate node; a pull-up turns the MOSFET on when the BJT is off.",
  },
  irlz44n: {
    label: "TX: IRLZ44N Direct",
    note: "Current simpler low-side switch: ESP32 GPIO5 drives a logic-level MOSFET gate through a small resistor.",
  },
};

const rxCircuitOptions = {
  teptDirect: {
    label: "RX: TEPT4400 -> ESP32",
    note: "Simple divider/direct digital or ADC input. Lowest cost, but threshold and speed are fragile.",
  },
  teptLm393: {
    label: "RX: TEPT4400 -> LM393 -> ESP32",
    note: "Current comparator path. TEPT4400 to +IN, 10k pot threshold to -IN, LM393 output pulled up to 3.3 V.",
  },
  bpw34TiaLm393: {
    label: "RX: BPW34 -> OPA2604 TIA -> LM393 -> ESP32",
    note: "Photodiode current becomes voltage through an OPA2604 transimpedance amplifier, then LM393 converts it to ESP32-safe logic.",
  },
};

function PinLabel({ x, y, children }) {
  return <text className="pin-label" x={x} y={y}>{children}</text>;
}

function RefLabel({ x, y, children, anchor = "middle" }) {
  return <text className="ref-label" x={x} y={y} textAnchor={anchor}>{children}</text>;
}

function ValueLabel({ x, y, children, anchor = "middle" }) {
  return <text className="value-label" x={x} y={y} textAnchor={anchor}>{children}</text>;
}

function NetLabel({ x, y, children, anchor = "middle" }) {
  return <text className="net-label" x={x} y={y} textAnchor={anchor}>{children}</text>;
}

function Ground({ x, y }) {
  return (
    <g className="ground-symbol" transform={`translate(${x} ${y})`}>
      <line x1="0" y1="0" x2="0" y2="10" />
      <line x1="-18" y1="10" x2="18" y2="10" />
      <line x1="-12" y1="18" x2="12" y2="18" />
      <line x1="-6" y1="26" x2="6" y2="26" />
    </g>
  );
}

function Supply({ x, y, label }) {
  return (
    <g>
      <line className="wire" x1={x} y1={y} x2={x} y2={y + 18} />
      <path className="supply-symbol" d={`M${x - 12} ${y} L${x} ${y - 16} L${x + 12} ${y} Z`} />
      <NetLabel x={x} y={y - 24}>{label}</NetLabel>
    </g>
  );
}

function DrawTxCircuit({ variant }) {
  if (variant === "bjtIrf540n") {
    return (
      <g className="ece-schematic">
        <text className="sheet-title" x="26" y="34">TX A - Inverting 2N3904 Gate Driver + IRF540N LED Switch</text>

        <g className="ic-symbol" transform="translate(58 122)">
          <rect width="132" height="118" rx="3" />
          <text x="66" y="30" textAnchor="middle">U1</text>
          <text x="66" y="52" textAnchor="middle">ESP32</text>
          <line x1="132" y1="72" x2="166" y2="72" />
          <text x="94" y="78">GPIO5</text>
          <line x1="66" y1="118" x2="66" y2="156" />
        </g>
        <Ground x={124} y={278} />

        <line className="wire" x1="224" y1="194" x2="256" y2="194" />
        <g className="schem-symbol" transform="translate(256 162)"><Symbol type="resistor" /></g>
        <line className="wire" x1="328" y1="194" x2="374" y2="194" />
        <RefLabel x="292" y="148">R1</RefLabel>
        <ValueLabel x="292" y="232">1k-4.7k</ValueLabel>

        <g className="schem-symbol" transform="translate(374 162)"><Symbol type="npn" /></g>
        <RefLabel x="416" y="144">Q1</RefLabel>
        <ValueLabel x="416" y="236">2N3904</ValueLabel>
        <line className="wire" x1="434" y1="218" x2="434" y2="278" />
        <Ground x={434} y={278} />

        <line className="wire" x1="434" y1="170" x2="434" y2="106" />
        <line className="wire" x1="434" y1="106" x2="582" y2="106" />
        <circle className="junction" cx="582" cy="106" r="4" />
        <NetLabel x="512" y="96">GATE_DRV</NetLabel>

        <Supply x={582} y={58} label="+12V" />
        <g className="schem-symbol" transform="translate(542 82) rotate(90 40 32)"><Symbol type="resistor" /></g>
        <line className="wire" x1="582" y1="154" x2="582" y2="106" />
        <RefLabel x="632" y="118" anchor="start">R2</RefLabel>
        <ValueLabel x="632" y="138" anchor="start">10k-47k pull-up</ValueLabel>

        <line className="wire" x1="582" y1="106" x2="656" y2="106" />
        <line className="wire" x1="656" y1="106" x2="656" y2="194" />
        <g className="schem-symbol" transform="translate(656 162) scale(1.15)"><Symbol type="mosfet" /></g>
        <RefLabel x="696" y="146">Q2</RefLabel>
        <ValueLabel x="714" y="250">IRF540N</ValueLabel>
        <line className="wire" x1="738" y1="220" x2="738" y2="278" />
        <Ground x={738} y={278} />

        <line className="wire" x1="738" y1="178" x2="738" y2="132" />
        <line className="wire" x1="738" y1="132" x2="790" y2="132" />
        <g className="schem-symbol" transform="translate(790 100)"><Symbol type="led" /></g>
        <line className="wire" x1="862" y1="132" x2="908" y2="132" />
        <line className="wire" x1="908" y1="132" x2="908" y2="76" />
        <Supply x={908} y={58} label="+12V" />
        <RefLabel x="826" y="88">LED1</RefLabel>
        <ValueLabel x="826" y="176">12 V DC LED bulb</ValueLabel>

        <g className="schem-note" transform="translate(510 304)">
          <rect width="350" height="56" rx="4" />
          <text x="14" y="22">Inverting action: GPIO HIGH turns Q1 on and pulls MOSFET gate LOW.</text>
          <text x="14" y="42">GPIO LOW lets R2 pull the IRF540N gate HIGH.</text>
        </g>
      </g>
    );
  }

  return (
    <g className="ece-schematic">
      <text className="sheet-title" x="26" y="34">TX B - Direct Logic-Level MOSFET LED Switch</text>

      <g className="ic-symbol" transform="translate(64 122)">
        <rect width="132" height="118" rx="3" />
        <text x="66" y="30" textAnchor="middle">U1</text>
        <text x="66" y="52" textAnchor="middle">ESP32</text>
        <line x1="132" y1="72" x2="166" y2="72" />
        <text x="90" y="78">GPIO5</text>
        <line x1="66" y1="118" x2="66" y2="156" />
      </g>
      <Ground x={130} y={278} />

      <line className="wire" x1="230" y1="194" x2="278" y2="194" />
      <g className="schem-symbol" transform="translate(278 162)"><Symbol type="resistor" /></g>
      <line className="wire" x1="350" y1="194" x2="470" y2="194" />
      <circle className="junction" cx="470" cy="194" r="4" />
      <RefLabel x="314" y="148">R1</RefLabel>
      <ValueLabel x="314" y="232">100-220 ohm</ValueLabel>

      <line className="wire" x1="470" y1="194" x2="470" y2="260" />
      <g className="schem-symbol" transform="translate(430 230) rotate(90 40 32)"><Symbol type="resistor" /></g>
      <line className="wire" x1="470" y1="332" x2="470" y2="350" />
      <Ground x={470} y={350} />
      <RefLabel x="514" y="280" anchor="start">R2</RefLabel>
      <ValueLabel x="514" y="300" anchor="start">10k pulldown</ValueLabel>

      <line className="wire" x1="470" y1="194" x2="580" y2="194" />
      <g className="schem-symbol" transform="translate(580 162) scale(1.15)"><Symbol type="mosfet" /></g>
      <RefLabel x="620" y="146">Q1</RefLabel>
      <ValueLabel x="638" y="250">IRLZ44N / logic MOSFET</ValueLabel>
      <line className="wire" x1="662" y1="220" x2="662" y2="278" />
      <Ground x={662} y={278} />

      <line className="wire" x1="662" y1="178" x2="662" y2="132" />
      <line className="wire" x1="662" y1="132" x2="742" y2="132" />
      <g className="schem-symbol" transform="translate(742 100)"><Symbol type="led" /></g>
      <line className="wire" x1="814" y1="132" x2="900" y2="132" />
      <line className="wire" x1="900" y1="132" x2="900" y2="76" />
      <Supply x={900} y={58} label="+12V" />
      <RefLabel x="778" y="88">LED1</RefLabel>
      <ValueLabel x="778" y="176">12 V DC LED bulb</ValueLabel>
    </g>
  );
}

function DrawRxCircuit({ variant }) {
  if (variant === "teptDirect") {
    return (
      <g className="ece-schematic">
        <text className="sheet-title" x="26" y="34">RX A - TEPT4400 Sensor Node Direct To ESP32</text>
        <Supply x={150} y={70} label="+3.3V" />
        <line className="wire" x1="150" y1="88" x2="150" y2="112" />
        <g className="schem-symbol" transform="translate(110 112) rotate(90 40 32)"><Symbol type="resistor" /></g>
        <line className="wire" x1="150" y1="184" x2="150" y2="220" />
        <circle className="junction" cx="150" cy="220" r="4" />
        <RefLabel x="196" y="146" anchor="start">R1</RefLabel>
        <ValueLabel x="196" y="166" anchor="start">10k-47k load</ValueLabel>

        <g className="schem-symbol" transform="translate(110 220)"><Symbol type="phototransistor" /></g>
        <line className="wire" x1="150" y1="282" x2="150" y2="328" />
        <Ground x={150} y={328} />
        <RefLabel x="226" y="252" anchor="start">Q1</RefLabel>
        <ValueLabel x="226" y="272" anchor="start">TEPT4400</ValueLabel>

        <line className="wire" x1="150" y1="220" x2="430" y2="220" />
        <NetLabel x="286" y="208">SENSOR_OUT</NetLabel>
        <g className="ic-symbol" transform="translate(430 148)">
          <rect width="162" height="132" rx="3" />
          <text x="81" y="32" textAnchor="middle">U1</text>
          <text x="81" y="54" textAnchor="middle">ESP32 RX</text>
          <line x1="0" y1="72" x2="-34" y2="72" />
          <text x="18" y="78">GPIO5 / GPIO34</text>
          <line x1="81" y1="132" x2="81" y2="170" />
        </g>
        <Ground x={511} y={318} />

        <g className="schem-note" transform="translate(630 178)">
          <rect width="270" height="76" rx="4" />
          <text x="14" y="22">Measured behavior:</text>
          <text x="14" y="42">light near 0 V, no light about 2.3 V.</text>
          <text x="14" y="62">Needs clean ESP32 logic threshold.</text>
        </g>
      </g>
    );
  }

  if (variant === "teptLm393") {
    return (
      <g className="ece-schematic">
        <text className="sheet-title" x="26" y="34">RX B - TEPT4400 Into LM393 Comparator</text>
        <Supply x={120} y={70} label="+3.3V" />
        <line className="wire" x1="120" y1="88" x2="120" y2="112" />
        <g className="schem-symbol" transform="translate(80 112) rotate(90 40 32)"><Symbol type="resistor" /></g>
        <line className="wire" x1="120" y1="184" x2="120" y2="220" />
        <circle className="junction" cx="120" cy="220" r="4" />
        <RefLabel x="166" y="146" anchor="start">R1</RefLabel>
        <ValueLabel x="166" y="166" anchor="start">10k-47k</ValueLabel>

        <g className="schem-symbol" transform="translate(80 220)"><Symbol type="phototransistor" /></g>
        <line className="wire" x1="120" y1="282" x2="120" y2="328" />
        <Ground x={120} y={328} />
        <RefLabel x="186" y="252" anchor="start">Q1</RefLabel>
        <ValueLabel x="186" y="272" anchor="start">TEPT4400</ValueLabel>

        <line className="wire" x1="120" y1="220" x2="356" y2="220" />
        <NetLabel x="232" y="208">SENSOR_OUT</NetLabel>
        <g className="schem-symbol comparator-symbol" transform="translate(356 162) scale(1.65)"><Symbol type="comparator" /></g>
        <RefLabel x="410" y="142">U2A</RefLabel>
        <ValueLabel x="410" y="278">LM393</ValueLabel>
        <NetLabel x="330" y="214">+IN</NetLabel>

        <Supply x={280} y={70} label="+3.3V" />
        <g className="schem-symbol" transform="translate(240 104) rotate(90 40 32)"><Symbol type="resistor" /></g>
        <line className="wire" x1="280" y1="176" x2="280" y2="328" />
        <Ground x={280} y={328} />
        <circle className="junction" cx="280" cy="236" r="4" />
        <line className="wire" x1="280" y1="236" x2="356" y2="236" />
        <RefLabel x="304" y="132" anchor="start">RV1</RefLabel>
        <ValueLabel x="304" y="152" anchor="start">10k threshold pot</ValueLabel>
        <NetLabel x="330" y="252">-IN</NetLabel>

        <line className="wire" x1="484" y1="215" x2="620" y2="215" />
        <circle className="junction" cx="570" cy="215" r="4" />
        <Supply x={570} y={70} label="+3.3V" />
        <g className="schem-symbol" transform="translate(530 104) rotate(90 40 32)"><Symbol type="resistor" /></g>
        <line className="wire" x1="570" y1="176" x2="570" y2="215" />
        <RefLabel x="594" y="132" anchor="start">R2</RefLabel>
        <ValueLabel x="594" y="152" anchor="start">10k pull-up</ValueLabel>
        <NetLabel x="536" y="204">RX_LOGIC</NetLabel>

        <g className="ic-symbol" transform="translate(620 150)">
          <rect width="168" height="126" rx="3" />
          <text x="84" y="30" textAnchor="middle">U1</text>
          <text x="84" y="52" textAnchor="middle">ESP32 RX</text>
          <line x1="0" y1="65" x2="-34" y2="65" />
          <text x="22" y="72">GPIO5</text>
          <line x1="84" y1="126" x2="84" y2="164" />
        </g>
        <Ground x={704} y={314} />

        <g className="schem-note" transform="translate(800 164)">
          <rect width="140" height="88" rx="4" />
          <text x="12" y="22">Expected polarity:</text>
          <text x="12" y="42">light = LOW</text>
          <text x="12" y="62">dark = HIGH</text>
          <text x="12" y="82">try RX INV=1</text>
        </g>
      </g>
    );
  }

  return (
    <g className="ece-schematic">
      <text className="sheet-title" x="26" y="34">RX C - BPW34 + OPA2604 Transimpedance Amplifier + LM393</text>

      <Supply x={88} y={70} label="+3.3V" />
      <g className="schem-symbol" transform="translate(48 104) rotate(90 40 32)"><Symbol type="resistor" /></g>
      <line className="wire" x1="88" y1="176" x2="88" y2="214" />
      <circle className="junction" cx="88" cy="214" r="4" />
      <g className="schem-symbol" transform="translate(48 214) rotate(90 40 32)"><Symbol type="resistor" /></g>
      <line className="wire" x1="88" y1="286" x2="88" y2="326" />
      <Ground x={88} y={326} />
      <NetLabel x="122" y="208" anchor="start">VREF</NetLabel>
      <ValueLabel x="122" y="228" anchor="start">approx 1.65 V</ValueLabel>

      <g className="schem-symbol" transform="translate(160 128) scale(1.15)"><Symbol type="photodiode" /></g>
      <RefLabel x="200" y="114">D1</RefLabel>
      <ValueLabel x="200" y="200">BPW34</ValueLabel>
      <line className="wire" x1="236" y1="164" x2="292" y2="164" />
      <NetLabel x="264" y="154">PD_IN</NetLabel>
      <line className="wire" x1="200" y1="128" x2="200" y2="76" />
      <Supply x={200} y={58} label="+3.3V" />

      <g className="schem-symbol" transform="translate(292 112) scale(1.7)"><Symbol type="opamp" /></g>
      <RefLabel x="348" y="94">U1A</RefLabel>
      <ValueLabel x="348" y="246">OPA2604 TIA</ValueLabel>
      <line className="wire" x1="88" y1="214" x2="292" y2="214" />
      <line className="wire" x1="292" y1="214" x2="292" y2="183" />
      <NetLabel x="274" y="206">+IN</NetLabel>
      <NetLabel x="274" y="158">-IN</NetLabel>

      <path className="wire" d="M333 153 L333 78 L454 78 L454 166" />
      <g className="schem-symbol" transform="translate(356 46)"><Symbol type="resistor" /></g>
      <g className="schem-symbol" transform="translate(356 84)"><Symbol type="capacitor" /></g>
      <RefLabel x="392" y="36">RF</RefLabel>
      <ValueLabel x="392" y="132">100k-1M with Cf</ValueLabel>
      <line className="wire" x1="422" y1="166" x2="520" y2="166" />
      <NetLabel x="474" y="154">TIA_OUT</NetLabel>

      <g className="schem-symbol comparator-symbol" transform="translate(520 114) scale(1.6)"><Symbol type="comparator" /></g>
      <RefLabel x="572" y="96">U2A</RefLabel>
      <ValueLabel x="572" y="250">LM393</ValueLabel>
      <Supply x={500} y={246} label="+3.3V" />
      <g className="schem-symbol" transform="translate(460 280) rotate(90 40 32)"><Symbol type="resistor" /></g>
      <line className="wire" x1="500" y1="352" x2="500" y2="370" />
      <Ground x={500} y={370} />
      <circle className="junction" cx="500" cy="310" r="4" />
      <line className="wire" x1="500" y1="310" x2="520" y2="183" />
      <NetLabel x="530" y="206">-IN threshold</NetLabel>
      <ValueLabel x="542" y="330" anchor="start">RV1 10k</ValueLabel>

      <line className="wire" x1="648" y1="166" x2="742" y2="166" />
      <circle className="junction" cx="706" cy="166" r="4" />
      <Supply x={706} y={70} label="+3.3V" />
      <g className="schem-symbol" transform="translate(666 104) rotate(90 40 32)"><Symbol type="resistor" /></g>
      <line className="wire" x1="706" y1="176" x2="706" y2="166" />
      <RefLabel x="728" y="132" anchor="start">R3</RefLabel>
      <ValueLabel x="728" y="152" anchor="start">10k pull-up</ValueLabel>
      <NetLabel x="686" y="196">RX_LOGIC</NetLabel>

      <g className="ic-symbol" transform="translate(742 104)">
        <rect width="168" height="126" rx="3" />
        <text x="84" y="30" textAnchor="middle">U3</text>
        <text x="84" y="52" textAnchor="middle">ESP32 RX</text>
        <line x1="0" y1="62" x2="-34" y2="62" />
        <text x="22" y="70">GPIO5</text>
        <line x1="84" y1="126" x2="84" y2="164" />
      </g>
      <Ground x={826} y={268} />

      <g className="schem-note" transform="translate(642 286)">
        <rect width="260" height="58" rx="4" />
        <text x="14" y="22">Check OPA2604 supply headroom and output swing.</text>
        <text x="14" y="42">ESP32 GPIO must stay within 0-3.3 V.</text>
      </g>
    </g>
  );
}

function SchematicWorkbench({ components, setComponents, onSubmit, selectedVersion, readOnly = false }) {
  const [frequency, setFrequency] = useState(9000);
  const [txCircuit, setTxCircuit] = useState("irlz44n");
  const [rxCircuit, setRxCircuit] = useState("teptLm393");
  const isCurrentVersion = selectedVersion.id === "current";
  const shownComponents = isCurrentVersion ? components : selectedVersion.schematicComponents;
  const waveformFrontEnd = rxCircuit === "bpw34TiaLm393" ? "tia" : rxCircuit === "teptLm393" ? "comparator" : "divider";

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
        <ComponentCard type="opamp" title="OPA2604 TIA" note="Photodiode current-to-voltage" />
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
            TX Circuit
            <select value={txCircuit} onChange={(event) => setTxCircuit(event.target.value)}>
              {Object.entries(txCircuitOptions).map(([id, option]) => <option key={id} value={id}>{option.label}</option>)}
            </select>
          </label>
          <label>
            RX Circuit
            <select value={rxCircuit} onChange={(event) => setRxCircuit(event.target.value)}>
              {Object.entries(rxCircuitOptions).map(([id, option]) => <option key={id} value={id}>{option.label}</option>)}
            </select>
          </label>
        </div>

        <div className="circuit-note-grid">
          <article><strong>{txCircuitOptions[txCircuit].label}</strong><span>{txCircuitOptions[txCircuit].note}</span></article>
          <article><strong>{rxCircuitOptions[rxCircuit].label}</strong><span>{rxCircuitOptions[rxCircuit].note}</span></article>
        </div>

        <div className="schematic-sheet">
          <svg viewBox="0 0 980 430" role="img" aria-label="LiFi transmitter schematic">
            <defs>
              <marker id="arrow" markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4">
                <path d="M0,0 L8,4 L0,8 z" />
              </marker>
            </defs>
            <DrawTxCircuit variant={txCircuit} />
          </svg>
        </div>

        <div className="schematic-sheet">
          <svg viewBox="0 0 980 430" role="img" aria-label="LiFi receiver schematic">
            <DrawRxCircuit variant={rxCircuit} />
          </svg>
        </div>

        <Waveform frequency={frequency} frontEnd={waveformFrontEnd} />
        <ComponentEditor components={shownComponents} setComponents={setComponents} onSubmit={onSubmit} readOnly={readOnly || !isCurrentVersion} />
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
  const [panelOpen, setPanelOpen] = useState(() => !isCompactViewport());
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
  const publicReadOnly = useMemo(() => isPublicGuestHost(), []);
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

  const updateNote = (id, value) => {
    if (publicReadOnly) return;
    setNotes((current) => ({ ...current, [id]: value }));
  };
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
    if (publicReadOnly) {
      setSaveStatus("guest read-only");
      return false;
    }

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
    if (publicReadOnly) {
      hydratedRef.current = true;
      setSaveStatus("guest read-only");
      return undefined;
    }

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
    if (publicReadOnly) return;
    if (!hydratedRef.current) return;
    const timer = window.setTimeout(() => {
      submitPlannerState(false);
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [notes, components, publicReadOnly]);

  return (
    <div className={`app ${publicReadOnly ? "guest-readonly" : "owner-editable"}`}>
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
          <span className={publicReadOnly ? "access-pill guest" : "access-pill owner"}>{publicReadOnly ? "Guest read-only" : "Owner edit mode"}</span>
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
            {!publicReadOnly ? (
              <button className="panel-toggle" onClick={() => submitPlannerState(true)} type="button">
                <Download size={15} />
                Submit status
              </button>
            ) : null}
            <button className="panel-toggle" onClick={() => setScrollMode((mode) => (mode === "pan" ? "zoom" : "pan"))} type="button">
              <ZoomIn size={15} />
              {scrollMode === "pan" ? "Scroll pans" : "Scroll zooms"}
            </button>
          </div>

          {activeView === "schematic" ? (
            <SchematicWorkbench components={components} setComponents={setComponents} onSubmit={submitPlannerState} selectedVersion={selectedVersion} readOnly={publicReadOnly} />
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
              <MiniMap className="desktop-only-minimap" pannable zoomable nodeStrokeWidth={3} />
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
            <DetailPanel selectedId={selectedId} notes={notes} onNoteChange={updateNote} onSubmit={submitPlannerState} details={versionDetails} readOnly={publicReadOnly} />
          </>
        ) : null}
      </main>
    </div>
  );
}
