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

function DrawTxCircuit({ variant }) {
  if (variant === "bjtIrf540n") {
    return (
      <g>
        <text className="sheet-title" x="26" y="34">TX Driver A: ESP32 GPIO5 -&gt; 2N3904 -&gt; IRF540N -&gt; 12 V DC LED</text>
        <line className="ground-bus" x1="45" y1="366" x2="930" y2="366" />
        <PinLabel x="50" y="388">common ground</PinLabel>

        <g className="schem-block" transform="translate(45 92)">
          <rect width="155" height="190" rx="8" />
          <text x="20" y="32">ESP32 TX</text>
          <g className="schem-symbol" transform="translate(38 55) scale(.95)"><Symbol type="esp32" /></g>
          <PinLabel x="20" y="166">GPIO5</PinLabel>
          <PinLabel x="20" y="184">3.3 V logic</PinLabel>
        </g>

        <line className="wire" x1="200" y1="196" x2="248" y2="196" />
        <g className="schem-symbol" transform="translate(248 164)"><Symbol type="resistor" /></g>
        <PinLabel x="258" y="154">1k-4.7k base resistor</PinLabel>
        <line className="wire" x1="320" y1="196" x2="382" y2="196" />

        <g className="schem-block transistor-block" transform="translate(382 126)">
          <rect width="132" height="164" rx="8" />
          <text x="20" y="28">2N3904 NPN</text>
          <circle cx="66" cy="86" r="30" />
          <line x1="38" y1="86" x2="66" y2="86" />
          <line x1="66" y1="60" x2="92" y2="40" />
          <line x1="66" y1="112" x2="92" y2="132" />
          <polyline points="82,124 92,132 79,135" />
          <PinLabel x="18" y="154">E to GND</PinLabel>
        </g>
        <line className="wire" x1="474" y1="258" x2="474" y2="366" />

        <line className="wire" x1="474" y1="166" x2="610" y2="166" />
        <circle className="junction" cx="610" cy="166" r="4" />
        <PinLabel x="522" y="156">collector / gate node</PinLabel>
        <line className="wire" x1="610" y1="166" x2="610" y2="112" />
        <g className="schem-symbol" transform="translate(570 72) rotate(90 40 32)"><Symbol type="resistor" /></g>
        <PinLabel x="625" y="92">10k-47k gate pull-up</PinLabel>
        <line className="wire" x1="610" y1="72" x2="610" y2="56" />
        <PinLabel x="626" y="60">+12 V gate bias</PinLabel>

        <line className="wire" x1="610" y1="166" x2="668" y2="205" />
        <g className="schem-symbol" transform="translate(650 178) scale(1.08)"><Symbol type="mosfet" /></g>
        <PinLabel x="648" y="168">IRF540N</PinLabel>
        <PinLabel x="650" y="288">source to GND</PinLabel>

        <line className="wire" x1="726" y1="186" x2="762" y2="186" />
        <g className="schem-symbol" transform="translate(762 154)"><Symbol type="led" /></g>
        <PinLabel x="754" y="144">12 V DC LED bulb</PinLabel>
        <line className="wire" x1="852" y1="186" x2="900" y2="186" />
        <line className="wire" x1="900" y1="186" x2="900" y2="82" />
        <PinLabel x="856" y="74">+12 V LED supply</PinLabel>
        <line className="wire" x1="704" y1="244" x2="704" y2="366" />
        <polyline className="ground-symbol" points="684,314 724,314 716,324 692,324 700,334 708,334" />
        <PinLabel x="530" y="326">GPIO HIGH pulls gate LOW: LED OFF</PinLabel>
        <PinLabel x="530" y="346">GPIO LOW lets pull-up turn LED ON</PinLabel>
      </g>
    );
  }

  return (
    <g>
      <text className="sheet-title" x="26" y="34">TX Driver B: ESP32 GPIO5 -&gt; IRLZ44N Logic-Level MOSFET -&gt; 12 V DC LED</text>
      <line className="ground-bus" x1="45" y1="366" x2="930" y2="366" />
      <PinLabel x="50" y="388">common ground</PinLabel>

      <g className="schem-block" transform="translate(45 88)">
        <rect width="170" height="210" rx="8" />
        <text x="20" y="32">ESP32 TX</text>
        <g className="schem-symbol" transform="translate(45 55)"><Symbol type="esp32" /></g>
        <PinLabel x="22" y="168">GPIO5 Manchester</PinLabel>
      </g>

      <line className="wire" x1="215" y1="198" x2="300" y2="198" />
      <g className="schem-symbol" transform="translate(300 166)"><Symbol type="resistor" /></g>
      <PinLabel x="316" y="156">100-220 ohm gate resistor</PinLabel>
      <line className="wire" x1="372" y1="198" x2="465" y2="198" />

      <line className="wire" x1="430" y1="198" x2="430" y2="292" />
      <g className="schem-symbol" transform="translate(390 250) rotate(90 40 32)"><Symbol type="resistor" /></g>
      <PinLabel x="374" y="338">10k pulldown</PinLabel>
      <line className="wire" x1="430" y1="326" x2="430" y2="366" />

      <g className="schem-symbol" transform="translate(455 168) scale(1.15)"><Symbol type="mosfet" /></g>
      <PinLabel x="456" y="156">IRLZ44N / logic MOSFET</PinLabel>
      <PinLabel x="510" y="286">source to GND</PinLabel>
      <line className="wire" x1="532" y1="186" x2="610" y2="186" />
      <g className="schem-symbol" transform="translate(610 154)"><Symbol type="led" /></g>
      <PinLabel x="610" y="144">12 V DC LED bulb</PinLabel>
      <line className="wire" x1="700" y1="186" x2="790" y2="186" />
      <line className="wire" x1="790" y1="186" x2="790" y2="92" />
      <line className="wire" x1="790" y1="92" x2="875" y2="92" />
      <PinLabel x="802" y="82">+12 V supply</PinLabel>
      <line className="wire" x1="525" y1="246" x2="525" y2="366" />
      <polyline className="ground-symbol" points="505,312 545,312 537,322 513,322 521,332 529,332" />
    </g>
  );
}

function DrawRxCircuit({ variant }) {
  if (variant === "teptDirect") {
    return (
      <g>
        <text className="sheet-title" x="26" y="34">RX Front-End A: TEPT4400 -&gt; ESP32 GPIO/ADC</text>
        <line className="ground-bus" x1="45" y1="360" x2="930" y2="360" />
        <PinLabel x="50" y="388">common ground</PinLabel>
        <PinLabel x="68" y="82">+3.3 V</PinLabel>
        <line className="wire" x1="100" y1="92" x2="100" y2="138" />
        <g className="schem-symbol" transform="translate(60 138) rotate(90 40 32)"><Symbol type="resistor" /></g>
        <PinLabel x="122" y="172">10k-47k load resistor</PinLabel>
        <line className="wire" x1="100" y1="212" x2="100" y2="230" />
        <circle className="junction" cx="100" cy="230" r="4" />
        <line className="wire" x1="100" y1="230" x2="235" y2="230" />
        <PinLabel x="122" y="222">sensor node</PinLabel>
        <g className="schem-symbol" transform="translate(60 235)"><Symbol type="phototransistor" /></g>
        <PinLabel x="142" y="270">TEPT4400</PinLabel>
        <line className="wire" x1="100" y1="300" x2="100" y2="360" />
        <g className="schem-block" transform="translate(235 132)">
          <rect width="210" height="170" rx="8" />
          <text x="20" y="32">ESP32 RX</text>
          <g className="schem-symbol" transform="translate(64 52) scale(.9)"><Symbol type="esp32" /></g>
          <PinLabel x="20" y="142">GPIO5 digital or GPIO34 ADC</PinLabel>
        </g>
        <PinLabel x="510" y="205">Measured: light near 0 V, no light around 2.3 V</PinLabel>
        <PinLabel x="510" y="232">Works only if threshold and edge speed are clean.</PinLabel>
      </g>
    );
  }

  if (variant === "teptLm393") {
    return (
      <g>
        <text className="sheet-title" x="26" y="34">RX Front-End B: TEPT4400 -&gt; LM393 Comparator -&gt; ESP32</text>
        <line className="ground-bus" x1="45" y1="360" x2="930" y2="360" />
        <PinLabel x="50" y="388">common ground</PinLabel>

        <PinLabel x="58" y="82">+3.3 V</PinLabel>
        <line className="wire" x1="90" y1="92" x2="90" y2="140" />
        <g className="schem-symbol" transform="translate(50 140) rotate(90 40 32)"><Symbol type="resistor" /></g>
        <PinLabel x="114" y="176">10k-47k load</PinLabel>
        <line className="wire" x1="90" y1="214" x2="90" y2="232" />
        <circle className="junction" cx="90" cy="232" r="4" />
        <g className="schem-symbol" transform="translate(50 238)"><Symbol type="phototransistor" /></g>
        <PinLabel x="132" y="273">TEPT4400</PinLabel>
        <line className="wire" x1="90" y1="304" x2="90" y2="360" />

        <line className="wire" x1="90" y1="232" x2="268" y2="232" />
        <g className="schem-symbol comparator-symbol" transform="translate(270 170) scale(1.6)"><Symbol type="comparator" /></g>
        <PinLabel x="286" y="156">LM393</PinLabel>
        <PinLabel x="244" y="210">+IN sensor</PinLabel>

        <g className="schem-symbol" transform="translate(190 72) rotate(90 40 32)"><Symbol type="resistor" /></g>
        <PinLabel x="235" y="70">10k pot</PinLabel>
        <PinLabel x="230" y="92">top +3.3 V</PinLabel>
        <line className="wire" x1="230" y1="144" x2="230" y2="360" />
        <line className="wire" x1="230" y1="160" x2="270" y2="238" />
        <PinLabel x="236" y="250">-IN threshold</PinLabel>

        <line className="wire" x1="392" y1="222" x2="548" y2="222" />
        <circle className="junction" cx="468" cy="222" r="4" />
        <g className="schem-symbol" transform="translate(428 86) rotate(90 40 32)"><Symbol type="resistor" /></g>
        <line className="wire" x1="468" y1="86" x2="468" y2="222" />
        <PinLabel x="482" y="112">10k output pull-up to 3.3 V</PinLabel>

        <g className="schem-block" transform="translate(548 142)">
          <rect width="210" height="156" rx="8" />
          <text x="20" y="32">ESP32 RX</text>
          <g className="schem-symbol" transform="translate(64 48) scale(.9)"><Symbol type="esp32" /></g>
          <PinLabel x="20" y="130">GPIO5 digital input</PinLabel>
        </g>
        <PinLabel x="780" y="205">Output polarity: light LOW, dark HIGH</PinLabel>
        <PinLabel x="780" y="232">Try RX INV=1 for current active-high TX.</PinLabel>
      </g>
    );
  }

  return (
    <g>
      <text className="sheet-title" x="26" y="34">RX Front-End C: BPW34 -&gt; OPA2604 TIA -&gt; LM393 -&gt; ESP32</text>
      <line className="ground-bus" x1="45" y1="360" x2="930" y2="360" />
      <PinLabel x="50" y="388">common ground</PinLabel>

      <PinLabel x="48" y="76">Vref approx 1.65 V</PinLabel>
      <g className="schem-symbol" transform="translate(55 90) rotate(90 40 32)"><Symbol type="resistor" /></g>
      <g className="schem-symbol" transform="translate(55 245) rotate(90 40 32)"><Symbol type="resistor" /></g>
      <PinLabel x="105" y="116">10k</PinLabel>
      <PinLabel x="105" y="274">10k</PinLabel>
      <line className="wire" x1="95" y1="76" x2="95" y2="92" />
      <line className="wire" x1="95" y1="164" x2="95" y2="246" />
      <line className="wire" x1="95" y1="318" x2="95" y2="360" />
      <circle className="junction" cx="95" cy="204" r="4" />
      <line className="wire" x1="95" y1="204" x2="245" y2="204" />
      <PinLabel x="102" y="198">OPA2604 +IN bias</PinLabel>

      <g className="schem-symbol" transform="translate(145 122) scale(1.1)"><Symbol type="photodiode" /></g>
      <PinLabel x="138" y="112">BPW34 photodiode</PinLabel>
      <line className="wire" x1="185" y1="122" x2="185" y2="76" />
      <PinLabel x="190" y="78">reverse bias / sensor node</PinLabel>
      <line className="wire" x1="228" y1="160" x2="245" y2="160" />

      <g className="schem-symbol" transform="translate(245 110) scale(1.7)"><Symbol type="opamp" /></g>
      <PinLabel x="258" y="96">OPA2604 TIA</PinLabel>
      <PinLabel x="232" y="152">-IN</PinLabel>
      <PinLabel x="232" y="206">+IN</PinLabel>
      <path className="wire" d="M270 136 C270 74 392 74 392 160" />
      <g className="schem-symbol" transform="translate(300 52)"><Symbol type="resistor" /></g>
      <PinLabel x="318" y="42">Rf 100k-1M</PinLabel>
      <PinLabel x="356" y="92">Cf parallel optional</PinLabel>
      <line className="wire" x1="378" y1="160" x2="500" y2="160" />

      <g className="schem-symbol comparator-symbol" transform="translate(500 108) scale(1.55)"><Symbol type="comparator" /></g>
      <PinLabel x="510" y="94">LM393 comparator</PinLabel>
      <PinLabel x="480" y="148">+IN TIA output</PinLabel>
      <g className="schem-symbol" transform="translate(430 236) rotate(90 40 32)"><Symbol type="resistor" /></g>
      <PinLabel x="466" y="230">10k pot threshold</PinLabel>
      <line className="wire" x1="470" y1="276" x2="500" y2="178" />
      <line className="wire" x1="470" y1="304" x2="470" y2="360" />
      <PinLabel x="492" y="214">-IN threshold</PinLabel>

      <line className="wire" x1="620" y1="160" x2="720" y2="160" />
      <circle className="junction" cx="675" cy="160" r="4" />
      <g className="schem-symbol" transform="translate(635 52) rotate(90 40 32)"><Symbol type="resistor" /></g>
      <line className="wire" x1="675" y1="54" x2="675" y2="160" />
      <PinLabel x="690" y="80">10k pull-up to 3.3 V</PinLabel>

      <g className="schem-block" transform="translate(720 90)">
        <rect width="205" height="156" rx="8" />
        <text x="20" y="32">ESP32 RX</text>
        <g className="schem-symbol" transform="translate(62 48) scale(.9)"><Symbol type="esp32" /></g>
        <PinLabel x="20" y="130">GPIO5 clean logic</PinLabel>
      </g>
      <PinLabel x="692" y="274">OPA2604 may need supply headroom;</PinLabel>
      <PinLabel x="692" y="296">verify output swing before ESP32 logic tests.</PinLabel>
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
