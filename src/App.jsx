import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity, ArrowDown, ArrowLeft, ArrowRight, ArrowUpRight, AudioWaveform,
  BookOpen, Cable, Check, ChevronDown, CircleDot, CircuitBoard, Code2,
  Cpu, ExternalLink, FileCode2, Github, Lightbulb, Layers, Menu, Pause, Play,
  Radio, RadioTower, RotateCcw, ShieldCheck, Signal, Sparkles, Waves, X, Zap
} from 'lucide-react';
import './styles.css';

const REPO = 'https://github.com/luckyprinter/OpenVLC-Public';
const PIN = '411f183a8592d8285118f613bb4909c5bbd9d3cc';
const CODE_4B5B = [0b11110,0b01001,0b10100,0b10101,0b01010,0b01011,0b01110,0b01111,0b10010,0b10011,0b10110,0b10111,0b11010,0b11011,0b11100,0b11101];
const toBits = (value, width) => value.toString(2).padStart(width, '0');
const SOURCE = (path) => `${REPO}/blob/${PIN}/${path}`;

const lessons = [
  { id:'prepare', n:'01', title:'Prepare the transfer', group:'TRANSMITTER', tag:'DESKTOP APPLICATION', body:'A file enters the transmitter application. The GUI holds the selected file and transfer settings, then hands the job to its physical or simulated backend.', detail:'Physical mode communicates with the ESP32 over USB serial. Simulation mode exercises a virtual backend instead of the optical hardware.', code:'tx_state.start_transmission(filepath)', file:'application-source/gui_dev_v3/tx_app_state.py', color:'coral' },
  { id:'stream', n:'02', title:'Move bytes to the ESP32', group:'TRANSMITTER', tag:'USB SERIAL', body:'The desktop application sends stream metadata and file data to the transmitter microcontroller over its USB serial connection.', detail:'The firmware receives stream-begin and stream-data records, validates the transfer parameters, and stages the payload for framing.', code:'STREAM_BEGIN  →  STREAM_DATA', file:'firmware/tx/tx.ino', color:'blue' },
  { id:'encode', n:'03', title:'Encode with 4B5B', group:'LINE CODING', tag:'4B5B · TWO NIBBLES', body:'Every source byte is split into two 4-bit nibbles. Each nibble is translated into a 5-bit codeword using the transmitter lookup table.', detail:'Two 5-bit codewords carry one original byte. The added bit provides transition-friendly coding; it is not encryption or error correction.', code:'high = value >> 4   ·   low = value & 0x0F', file:'firmware/tx/tx.ino', color:'lime' },
  { id:'frame', n:'04', title:'Build a framed message', group:'TRANSMISSION', tag:'FRAME + INTEGRITY', body:'Encoded payload bytes are carried in protocol frames with synchronization and metadata so the receiver can find, interpret, and validate them.', detail:'The protocol specification defines the frame structure and CRC coverage. Consult it for exact field widths, byte ordering, and validation rules.', code:'SYNC  →  HEADER  →  PAYLOAD  →  CRC', file:'firmware/specs/protocol_spec.md', color:'blue' },
  { id:'light', n:'05', title:'Turn bits into light', group:'OPTICAL LINK', tag:'NRZ / OOK · GPIO5', body:'The TX ESP32 drives the LED switching stage. The LED output changes with the encoded symbol stream, carrying information through visible light.', detail:'The documented baseline uses 15 ksymbols/s, approximately 66 μs per symbol, with a 1 ms frame gap. The LED remains on during idle.', code:'ESP32 GPIO5  →  2N3904 + IRF540N  →  12 V LED', file:'firmware/tx/tx.ino', color:'coral' },
  { id:'detect', n:'06', title:'Detect the optical signal', group:'RECEIVER', tag:'PHOTODIODE FRONT END', body:'At the other end of the line of sight, the BPW34 converts received light into photocurrent. The analog front end turns that small current into a usable voltage.', detail:'The receiver chain uses a BPW34 photodiode, OPA2604 transimpedance amplifier, and LM393 comparator. The comparator output feeds RX GPIO5.', code:'BPW34  →  OPA2604 TIA  →  LM393', file:'firmware/rx/rx.ino', color:'blue' },
  { id:'decode', n:'07', title:'Find sync and decode', group:'RECEIVER', tag:'ESP32 RX · GPIO5', body:'The receiver detects the preamble and synchronization word, aligns to the frame, samples symbols, and converts valid 5-bit codewords back into nibbles.', detail:'The firmware defines SYNC_WORD 0xD5B7 and a minimum preamble transition count. Invalid 5-bit codewords are rejected by the decode table.', code:'SYNC_WORD 0xD5B7  ·  DECODE_4B5B', file:'firmware/rx/rx.ino', color:'lime' },
  { id:'verify', n:'08', title:'Validate and reconstruct', group:'INTEGRITY', tag:'CRC · CHUNKS · FILE', body:'The receiver checks integrity, accepts valid payload chunks, and reconstructs the original file. The desktop RX application presents the result and reception data.', detail:'Chunk, frame, and whole-file CRC checks serve different scopes. BER is evaluated by comparing reconstructed data with the corresponding original reference file.', code:'CRC checks  +  reference-file BER comparison', file:'firmware/specs/protocol_spec.md', color:'coral' }
];

const navItems = [
  ['journey','The signal journey'], ['architecture','System architecture'],
  ['protocol','Protocol notes'], ['hardware','Hardware map'], ['validation','Integrity checks']
];

function Packet({ step }) {
  const positions = [[90,176],[205,176],[330,176],[455,176],[580,176],[705,176],[830,176],[955,176]];
  const [x,y] = positions[step] || positions[0];
  return <motion.g initial={false} animate={{x:x-90,y:y-176,opacity:1}} transition={{type:'spring',stiffness:90,damping:18}}>
    <circle cx="90" cy="176" r="13" fill="#ef765b" opacity=".16"/>
    <circle cx="90" cy="176" r="5" fill="#e66e54"/>
    <path d="M90 176 L90 145" stroke="#e66e54" strokeWidth="1.5" strokeDasharray="3 3"/>
  </motion.g>;
}

function SignalDiagram({ active, onSelect }) {
  const [zoom,setZoom] = useState(1);
  const names = ['TX GUI','USB','4B5B','FRAME','LED','BPW34','RX MCU','FILE'];
  const activeX = 86 + active * 124;
  return <div className="diagram-frame">
    <div className="diagram-topline"><span><i/> LIVE SYSTEM MODEL</span><div className="diagram-toolbar"><span>INTERACTIVE · 08 STAGES</span><button onClick={()=>setZoom(v=>Math.max(.85,v-.15))} aria-label="Zoom out">−</button><button onClick={()=>setZoom(v=>Math.min(1.6,v+.15))} aria-label="Zoom in">+</button><button onClick={()=>setZoom(1)} aria-label="Fit diagram">FIT</button></div></div>
    <svg className="signal-svg" viewBox="0 0 1020 330" role="img" aria-label="Isometric diagram of the visible light communication signal path">
      <defs>
        <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#d7cbbd" strokeWidth=".7"/></pattern>
        <linearGradient id="beam" x1="0" x2="1"><stop stopColor="#e66e54" stopOpacity=".12"/><stop offset=".5" stopColor="#e6a94f" stopOpacity=".7"/><stop offset="1" stopColor="#e66e54" stopOpacity=".12"/></linearGradient>
        <filter id="soft"><feGaussianBlur stdDeviation="7"/></filter>
      </defs>
      <rect width="1020" height="330" fill="url(#grid)" opacity=".8"/>
      <g transform={`translate(${510*(1-zoom)} ${165*(1-zoom)}) scale(${zoom})`}>
      <path d="M52 225 L965 225" stroke="#b8aa9a" strokeWidth="1.2" strokeDasharray="4 7"/>
      <path d="M540 164 L690 164" stroke="url(#beam)" strokeWidth="28" filter="url(#soft)"/>
      <path d="M540 164 L690 164" stroke="#d9a34b" strokeWidth="2" strokeDasharray="7 6" opacity=".85"/>
      {Array.from({length:5},(_,i)=><motion.circle key={i} r="3.5" fill="#e6a94f" animate={{cx:[548,680],opacity:[0,1,0]}} transition={{duration:1.5,delay:i*.28,repeat:Infinity,ease:'linear'}} cy={164}/>)}
      <g className={active===0?"diagram-node active":"diagram-node"} transform="translate(42 80)" role="button" tabIndex={0} aria-label={`Select ${names[0]} stage`} onClick={()=>onSelect(0)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(0)}}}>
        <path d="M0 75 L40 52 L112 52 L72 75 Z" fill="#e5d7c6" stroke="#2c2a27"/>
        <path d="M0 75 L72 75 L72 142 L0 142 Z" fill="#d5c5b3" stroke="#2c2a27"/>
        <path d="M72 75 L112 52 L112 119 L72 142 Z" fill="#c1b09e" stroke="#2c2a27"/>
        <rect x="18" y="90" width="38" height="35" fill="#f6eee5" stroke="#2c2a27"/>
        <rect x="25" y="98" width="24" height="20" fill="#e9a28b"/>
        <path d="M38 52V24" stroke="#2c2a27" strokeWidth="2"/><circle cx="38" cy="19" r="7" fill="#e66e54"/>
        <text x="55" y="165" textAnchor="middle" className="svg-label">TX DESKTOP</text>
      </g>
      <g className={active===1?"diagram-node active":"diagram-node"} transform="translate(176 104)" role="button" tabIndex={0} aria-label={`Select ${names[1]} stage`} onClick={()=>onSelect(1)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(1)}}}>
        <path d="M0 44 L28 28 L91 28 L63 44 Z" fill="#cbd6d9" stroke="#2c2a27"/>
        <path d="M0 44 L63 44 L63 99 L0 99 Z" fill="#aebdc2" stroke="#2c2a27"/>
        <path d="M63 44 L91 28 L91 83 L63 99 Z" fill="#91a4aa" stroke="#2c2a27"/>
        <rect x="15" y="57" width="31" height="23" fill="#f5eee5" stroke="#2c2a27"/>
        <text x="45" y="122" textAnchor="middle" className="svg-label">USB SERIAL</text>
      </g>
      <g className={active===2?"diagram-node active":"diagram-node"} transform="translate(300 94)" role="button" tabIndex={0} aria-label={`Select ${names[2]} stage`} onClick={()=>onSelect(2)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(2)}}}>
        <path d="M0 52 L30 34 L112 34 L82 52 Z" fill="#d7d1b7" stroke="#2c2a27"/>
        <path d="M0 52 L82 52 L82 119 L0 119 Z" fill="#c3bb9e" stroke="#2c2a27"/>
        <path d="M82 52 L112 34 L112 101 L82 119 Z" fill="#a69e82" stroke="#2c2a27"/>
        {Array.from({length:5},(_,i)=><rect key={i} x={14+i*12} y="68" width="7" height="23" rx="1" fill={i<3?'#e66e54':'#f5eee5'} stroke="#625a4b" strokeWidth=".5"/>)}
        <text x="55" y="142" textAnchor="middle" className="svg-label">ESP32 · 4B5B</text>
      </g>
      <g className={active===3?"diagram-node active":"diagram-node"} transform="translate(430 102)" role="button" tabIndex={0} aria-label={`Select ${names[3]} stage`} onClick={()=>onSelect(3)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(3)}}}>
        <path d="M0 44 L28 27 L105 27 L77 44 Z" fill="#cbd6d9" stroke="#2c2a27"/>
        <path d="M0 44 L77 44 L77 99 L0 99 Z" fill="#aebdc2" stroke="#2c2a27"/>
        <path d="M77 44 L105 27 L105 82 L77 99 Z" fill="#91a4aa" stroke="#2c2a27"/>
        <path d="M14 61H61M14 70H61M14 79H49" stroke="#46565a" strokeWidth="2"/>
        <text x="52" y="122" textAnchor="middle" className="svg-label">FRAME + CRC</text>
      </g>
      <g className={active===4?"diagram-node active":"diagram-node"} transform="translate(580 95)" role="button" tabIndex={0} aria-label={`Select ${names[4]} stage`} onClick={()=>onSelect(4)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(4)}}}>
        <path d="M0 56 L28 39 L104 39 L76 56 Z" fill="#ead6a9" stroke="#2c2a27"/>
        <path d="M0 56 L76 56 L76 112 L0 112 Z" fill="#d7bd83" stroke="#2c2a27"/>
        <path d="M76 56 L104 39 L104 95 L76 112 Z" fill="#b89a5d" stroke="#2c2a27"/>
        <path d="M39 39V11" stroke="#2c2a27" strokeWidth="2"/><circle cx="39" cy="7" r="9" fill="#f0c66e" stroke="#2c2a27"/>
        <circle cx="39" cy="7" r="19" fill="#f0c66e" opacity=".18"/>
        <text x="51" y="135" textAnchor="middle" className="svg-label">12 V LED</text>
      </g>
      <g className={active===5?"diagram-node active":"diagram-node"} transform="translate(704 95)" role="button" tabIndex={0} aria-label={`Select ${names[5]} stage`} onClick={()=>onSelect(5)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(5)}}}>
        <path d="M0 56 L28 39 L104 39 L76 56 Z" fill="#d5e0d9" stroke="#2c2a27"/>
        <path d="M0 56 L76 56 L76 112 L0 112 Z" fill="#b9c9bf" stroke="#2c2a27"/>
        <path d="M76 56 L104 39 L104 95 L76 112 Z" fill="#9daf9f" stroke="#2c2a27"/>
        <circle cx="39" cy="65" r="15" fill="#f7eee4" stroke="#2c2a27" strokeWidth="1.5"/><circle cx="39" cy="65" r="5" fill="#e66e54"/>
        <text x="51" y="135" textAnchor="middle" className="svg-label">BPW34 · TIA</text>
      </g>
      <g className={active===6?"diagram-node active":"diagram-node"} transform="translate(830 102)" role="button" tabIndex={0} aria-label={`Select ${names[6]} stage`} onClick={()=>onSelect(6)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(6)}}}>
        <path d="M0 44 L28 27 L105 27 L77 44 Z" fill="#d7d1b7" stroke="#2c2a27"/>
        <path d="M0 44 L77 44 L77 99 L0 99 Z" fill="#c3bb9e" stroke="#2c2a27"/>
        <path d="M77 44 L105 27 L105 82 L77 99 Z" fill="#a69e82" stroke="#2c2a27"/>
        <rect x="18" y="59" width="42" height="25" fill="#f5eee5" stroke="#2c2a27"/>
        <path d="M24 72h8l5-7 6 14 5-7h7" fill="none" stroke="#e66e54" strokeWidth="1.5"/>
        <text x="52" y="122" textAnchor="middle" className="svg-label">ESP32 RX</text>
      </g>
      <g className={active===7?"diagram-node active":"diagram-node"} transform="translate(950 88)" role="button" tabIndex={0} aria-label={`Select ${names[7]} stage`} onClick={()=>onSelect(7)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(7)}}}>
        <path d="M0 75 L30 57 L80 57 L50 75 Z" fill="#e5d7c6" stroke="#2c2a27"/>
        <path d="M0 75 L50 75 L50 142 L0 142 Z" fill="#d5c5b3" stroke="#2c2a27"/>
        <path d="M50 75 L80 57 L80 124 L50 142 Z" fill="#c1b09e" stroke="#2c2a27"/>
        <path d="M13 91h24M13 101h24M13 111h18" stroke="#64584e" strokeWidth="2"/>
        <text x="38" y="165" textAnchor="middle" className="svg-label">RX GUI</text>
      </g>
      <path d={`M${activeX} 38 v22`} stroke="#e66e54" strokeWidth="1.5"/>
      <circle cx={activeX} cy="30" r="15" fill="#e66e54"/><text x={activeX} y="34" textAnchor="middle" className="svg-number">{String(active+1).padStart(2,'0')}</text>
      <Packet step={active}/>
      </g>
    </svg>
    <div className="diagram-caption"><span>FIG. 01</span><span>One file, eight transformations, one optical channel.</span><span className="diagram-mobile-hint">SWIPE TO VIEW FULL DIAGRAM</span><span>NOT TO SCALE</span></div>
  </div>;
}

function LessonExplorer() {
  const [active,setActive] = useState(0);
  const [playing,setPlaying] = useState(false);
  const lesson = lessons[active];
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => setActive(v => v === lessons.length-1 ? 0 : v+1), 2600);
    return () => clearInterval(timer);
  }, [playing]);
  const select = (n) => { setActive(Math.max(0,Math.min(lessons.length-1,n))); setPlaying(false); };
  return <section className="lesson-section" id="journey">
    <div className="section-heading"><div><span className="eyebrow">THE INTERACTIVE FIELD GUIDE · 01</span><h2>Follow the signal.</h2></div><p>Not a static block diagram. Step through what happens to the data as it crosses the optical link.</p></div>
    <div className="lesson-layout">
      <aside className="lesson-index">
        <div className="index-head"><span>THE JOURNEY</span><span>0{lessons.length} STEPS</span></div>
        {lessons.map((l,i)=><button key={l.id} onClick={()=>select(i)} className={active===i?'current':''} aria-current={active===i?'step':undefined}><span className="lesson-num">{l.n}</span><span className="lesson-title">{l.title}<small>{l.group}</small></span>{active===i&&<span className="active-mark"/>}</button>)}
        <div className="index-foot"><span className="live-dot"/> {playing?'PLAYING SEQUENCE':'SELECT A STAGE TO EXPLORE'}</div>
      </aside>
      <div className="lesson-main">
        <SignalDiagram active={active} onSelect={select}/>
        <div className="lesson-copy">
          <div className="lesson-copy-main">
            <div className="lesson-meta"><span className={`tag ${lesson.color}`}>{lesson.tag}</span><span>STAGE {lesson.n} / 08</span></div>
            <AnimatePresence mode="wait"><motion.div key={lesson.id} aria-live="polite" initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-8}} transition={{duration:.2}}><h3>{lesson.title}</h3><p>{lesson.body}</p><p className="detail">{lesson.detail}</p><code className="inline-code">{lesson.code}</code><a className="lesson-source-link" href={SOURCE(lesson.file)} target="_blank" rel="noreferrer"><span>VIEW SOURCE FILE</span><code>{lesson.file}</code><ExternalLink size={14}/></a></motion.div></AnimatePresence>
          </div>
          <div className="lesson-controls">
            <button className="icon-btn" onClick={()=>select(active-1)} disabled={active===0} aria-label="Previous stage"><ArrowLeft size={17}/></button>
            <button className="play-btn" onClick={()=>setPlaying(v=>!v)}>{playing?<Pause size={15}/>:<Play size={15}/>} {playing?'Pause':'Auto play'}</button>
            <button className="icon-btn" onClick={()=>select(0)} aria-label="Restart"><RotateCcw size={16}/></button>
            <button className="next-btn" onClick={()=>select(active===lessons.length-1?0:active+1)}>{active===lessons.length-1?'Restart':'Next stage'} <ArrowRight size={16}/></button>
          </div>
        </div>
        <div className="lesson-progress"><span style={{width:`${(active+1)/lessons.length*100}%`}}/></div>
      </div>
    </div>
  </section>;
}

function Architecture() {
  const columns = [
    {label:'TRANSMIT',tone:'coral',items:[['Desktop TX app','File selection · transfer controls'],['USB serial','Application-to-device transport'],['ESP32 TX','4B5B · framing · symbol timing'],['LED driver','2N3904 · IRF540N · 12 V bulb']]},
    {label:'OPTICAL CHANNEL',tone:'gold',items:[['Visible light','NRZ / OOK intensity modulation'],['Line of sight','Short-range indoor optical path']]},
    {label:'RECEIVE',tone:'green',items:[['Optical front end','BPW34 · OPA2604 · LM393'],['ESP32 RX','Sampling · sync · decode · CRC'],['USB serial','Device-to-application transport'],['Desktop RX app','Waveform · reconstruction · BER']]}
  ];
  return <section className="content-section" id="architecture"><div className="section-heading"><div><span className="eyebrow">02 · SYSTEM ARCHITECTURE</span><h2>Two endpoints.<br/>One line of sight.</h2></div><p>The software, firmware, and optical hardware form one continuous communication system.</p></div><div className="architecture-grid">{columns.map((c,i)=><div className={`architecture-column ${c.tone}`} key={c.label}><div className="column-label">{c.label}</div>{c.items.map(([a,b],j)=><React.Fragment key={a}><div className="arch-node"><span className="node-index">{String(j+1).padStart(2,'0')}</span><div><b>{a}</b><small>{b}</small></div></div>{j<c.items.length-1&&<div className="connector"><ArrowDown size={14}/></div>}</React.Fragment>)}</div>)}</div><div className="architecture-note"><CircleDot size={16}/><span>Research prototype, not a commercial LiFi product or a Wi-Fi replacement. Experimental conditions and measured results belong to the thesis.</span></div></section>;
}

function Protocol() {
  const [mode,setMode]=useState('encoding');
  const [byteValue,setByteValue]=useState(0xA6);
  const high=(byteValue>>4)&0x0F, low=byteValue&0x0F;
  const highCode=toBits(CODE_4B5B[high],5), lowCode=toBits(CODE_4B5B[low],5);
  const encodedBits = highCode + lowCode;
  const transitions = encodedBits.slice(1).split('').filter((bit,i)=>bit!==encodedBits[i]).length;
  const [decodeCodeword,setDecodeCodeword]=useState(0b11110);
  const decodedNibble=CODE_4B5B.indexOf(decodeCodeword);
  return <section className="content-section dark-section" id="protocol"><div className="section-heading"><div><span className="eyebrow">03 · PROTOCOL NOTES</span><h2>Bits need a<br/>shared language.</h2></div><p>Explore the actual 4B5B lookup table and the fields carried by each protocol frame.</p></div>
    <div className="protocol-switch"><button className={mode==='encoding'?'selected':''} aria-pressed={mode==='encoding'} onClick={()=>setMode('encoding')}>4B5B encoding</button><button className={mode==='frame'?'selected':''} aria-pressed={mode==='frame'} onClick={()=>setMode('frame')}>Frame structure</button></div>
    {mode==='encoding'?<div className="encoding-demo"><div className="encoding-input"><span>INPUT BYTE · DECIMAL / HEX</span><strong>{toBits(byteValue,8).slice(0,4)} {toBits(byteValue,8).slice(4)}</strong><small>0x{byteValue.toString(16).toUpperCase().padStart(2,'0')} · {byteValue} decimal</small><input className="byte-slider" aria-label="Choose input byte" type="range" min="0" max="255" value={byteValue} onChange={e=>setByteValue(Number(e.target.value))}/><div className="byte-control"><label htmlFor="byte-value">BYTE VALUE</label><input id="byte-value" type="number" min="0" max="255" value={byteValue} onChange={e=>setByteValue(Math.max(0,Math.min(255,Number(e.target.value)||0)))}/></div></div><div className="encoding-arrow"><ArrowRight/></div><div className="encoding-output"><span>LOOKUP TABLE OUTPUT · 5 BITS EACH</span><div className="nibble-label">HIGH NIBBLE · 0x{high.toString(16).toUpperCase()}</div><div className="bit-row">{highCode.split('').map((b,i)=><i key={i} className={b==='1'?'one':''}>{b}</i>)}</div><div className="nibble-label">LOW NIBBLE · 0x{low.toString(16).toUpperCase()}</div><div className="bit-row">{lowCode.split('').map((b,i)=><i key={i} className={b==='1'?'one':''}>{b}</i>)}</div><small>{toBits(byteValue,8)} → {highCode} {lowCode}</small></div><div className="encoding-foot">The firmware maps each 4-bit nibble through its CODE_4B5B[16] lookup table. This adds one encoded bit per nibble; it is line coding, not encryption or error correction.</div><div className="signal-inspector"><div className="inspector-head"><span>ENCODED SYMBOL STREAM</span><b>{encodedBits.length} symbols · {transitions} transitions</b></div><div className="symbol-strip">{encodedBits.split('').map((bit,i)=><div key={i} className={bit==='1'?'symbol-high':'symbol-low'}><b>{bit}</b><small>{i+1}</small></div>)}</div><div className="wave-caption"><span>1 = LED ON</span><span>0 = LED OFF</span><span>1 symbol ≈ 66.7 μs at 15 ksymbols/s</span></div><div className="waveform"><svg viewBox="0 0 640 94" role="img" aria-label="NRZ OOK waveform for the encoded 10-bit stream" preserveAspectRatio="none"><path d={encodedBits.split('').map((bit,i)=>`M${i*64} ${bit==='1'?18:70} h64`).join(' ')} fill="none" stroke="#e9a45b" strokeWidth="3" strokeLinejoin="round"/><path d={Array.from({length:11},(_,i)=>`M${i*64} 10 v72`).join(' ')} stroke="#ffffff" opacity=".14" strokeDasharray="2 4"/></svg></div><p>OOK illustration: a logical 1 commands the LED-on line level; a logical 0 commands LED-off. The firmware's active-low setting determines the electrical pin polarity, not the logical meaning.</p></div><div className="decoder-check"><div><span>TRY THE RECEIVER LOOKUP</span><b>5-bit codeword decoder</b><p>Only the 16 assigned codewords map to data nibbles. Other 5-bit values are invalid and rejected.</p></div><div className="decoder-control"><strong>{toBits(decodeCodeword,5)}</strong><input type="range" min="0" max="31" value={decodeCodeword} onChange={e=>setDecodeCodeword(Number(e.target.value))} aria-label="Choose a 5-bit codeword"/><span className={decodedNibble>=0?'decode-valid':'decode-invalid'}>{decodedNibble>=0?`VALID · nibble 0x${decodedNibble.toString(16).toUpperCase()}`:'INVALID · rejected'}</span></div></div></div>:<div className="frame-demo"><div className="frame-band sync">SOF<br/>0xA5</div><div className="frame-band header">VERSION · TRANSFER ID · FRAME TYPE · TOTAL SIZE · TOTAL CHUNKS · CHUNK INDEX · PAYLOAD LENGTH · FILE CRC · CHUNK CRC</div><div className="frame-band payload">FILE NAME</div><div className="frame-band payload">PAYLOAD DATA</div><div className="frame-band crc">FRAME<br/>CRC</div><p>Field order follows the pinned protocol specification. Exact field widths, byte serialization, and CRC coverage are defined by the firmware source.</p><div className="batch-note"><b>Large-file path</b><span>Files above the 80 KiB firmware buffer are split by the desktop application into VLCB1~filename parts; the receiver reassembles them after each part passes CRC validation.</span></div></div>}
    <div className="protocol-foot"><span>PINNED SOURCE · {PIN.slice(0,12)}</span><a href={SOURCE('firmware/specs/protocol_spec.md')} target="_blank" rel="noreferrer">Open protocol specification <ArrowUpRight size={14}/></a></div>
  </section>;
}

function Hardware() {
  const [selected,setSelected]=useState(0);
  const parts=[
    ['TX GPIO5','Optical drive','Digital symbol output from the transmitter ESP32.'],
    ['2N3904 + IRF540N','Switching stage','Translates the logic-level control into switching for the 12 V LED load.'],
    ['12 V DC LED bulb','Optical source','Converts the electrical OOK pattern into changing light intensity.'],
    ['BPW34','Photodetector','Converts received light into photocurrent.'],
    ['OPA2604','Transimpedance amplifier','Converts photodiode current into a voltage signal.'],
    ['LM393','Comparator','Produces the digital signal supplied to the RX ESP32.'],
    ['RX GPIO5','Comparator digital output','Carries the recovered digital data from the LM393 comparator into the receiver ESP32.'],
    ['RX GPIO25','Adaptive Vref PWM output','Drives the PWM control used to adjust the LM393 comparator reference threshold.'],
    ['RX GPIO34','Scaled PVo ADC input','Monitors the divided photodetector-amplifier signal level at the receiver.'],
    ['RX GPIO35','Scaled Vref ADC input','Monitors the divided comparator-reference voltage for threshold feedback.']
  ];
  return <section className="content-section" id="hardware"><div className="section-heading"><div><span className="eyebrow">04 · HARDWARE MAP</span><h2>From photons<br/>to logic levels.</h2></div><p>Choose a component to trace its job in the transmitter or receiver signal chain.</p></div><div className="hardware-layout"><div className="hardware-list">{parts.map(([a,b],i)=><button key={a} onClick={()=>setSelected(i)} className={selected===i?'selected':''} aria-pressed={selected===i}><span>{String(i+1).padStart(2,'0')}</span><b>{a}</b><small>{b}</small><ArrowRight size={15}/></button>)}</div><div className="hardware-detail"><div className="detail-index">COMPONENT / {String(selected+1).padStart(2,'0')}</div><div className="component-symbol">{selected<3?<Lightbulb size={42}/>:<CircuitBoard size={42}/>}</div><h3>{parts[selected][0]}</h3><span>{parts[selected][1]}</span><p>{parts[selected][2]}</p><div className="detail-rule"/>
      {selected===7&&<div className="vref-calibration"><div className="calibration-metrics"><div><span>TARGET MARGIN</span><b>365 mV</b></div><div><span>ACCEPTED RANGE</span><b>280–450 mV</b></div><div><span>CALIBRATION WINDOWS</span><b>3 × 20 ms</b><small>10 ms gaps</small></div><div><span>MINIMUM HEADROOM</span><b>50 mV</b></div></div><p>The firmware averages the three measured signal peaks, subtracts the target margin to calculate the Vref target, then tunes the PWM output toward that target.</p><code>Vref target ≈ average signal peak − 365 mV</code></div>}
      {(selected===8||selected===9)&&<div className="vref-calibration"><div className="calibration-metrics"><div><span>TOP RESISTOR</span><b>22 kΩ</b></div><div><span>BOTTOM RESISTOR</span><b>8.2 kΩ</b></div><div><span>ADC REFERENCE</span><b>3.30 V</b></div><div><span>SOFTWARE SCALE</span><b>3.683×</b></div></div><p>The firmware reads the divided voltage at the ESP32 ADC, then multiplies it by the divider scale to estimate the corresponding receiver front-end voltage.</p><code>Vfront-end ≈ VADC × (22k + 8.2k) / 8.2k</code></div>}
      <small>PINOUTS AND ELECTRICAL LIMITS SHOULD BE VERIFIED AGAINST THE CIRCUIT AND DATASHEETS.</small></div></div></section>;
}

function Validation() {
  return <section className="content-section validation-section" id="validation"><div className="section-heading"><div><span className="eyebrow">05 · INTEGRITY & VALIDATION</span><h2>Trust, but<br/>verify the bits.</h2></div><p>A completed transfer is not a single pass/fail light. Integrity is checked at multiple scopes.</p></div><div className="validation-cards"><article><span>01</span><ShieldCheck/><h3>Chunk CRC</h3><p>Checks a payload chunk before it is accepted and stored.</p></article><article><span>02</span><Layers/><h3>Frame CRC</h3><p>Checks the assembled frame structure and contents.</p></article><article><span>03</span><FileCode2/><h3>File CRC</h3><p>Checks integrity across the reconstructed file.</p></article><article><span>04</span><Activity/><h3>BER comparison</h3><p>Compares reconstructed data with the corresponding original reference file.</p></article></div><div className="distinction"><b>CRC PASS ≠ BER = 0%</b><span>CRC validates defined data units. BER compares corresponding bits in the reference and received data. They answer different questions. <code>BER = differing bits ÷ compared bits × 100%</code></span></div></section>;
}

function SourceFooter() {
  return <footer className="site-footer"><div className="footer-top"><div><span className="eyebrow">THE RESEARCH ARTIFACT</span><h2>Open implementation.<br/><i>Inspectable by design.</i></h2><p>This guide explains the system. The repository contains the implementation. The thesis remains the authority for methodology and measured results.</p></div><a className="repo-button" href={REPO} target="_blank" rel="noreferrer"><Github size={18}/> Explore source repository <ArrowUpRight size={16}/></a></div><div className="footer-meta"><span>OPENVLC FIELD GUIDE</span><span>REFERENCE COMMIT · {PIN.slice(0,12)}</span><a href={SOURCE('README.md')}>REPOSITORY README <ExternalLink size={12}/></a></div></footer>;
}

export default function App() {
  const [menu,setMenu]=useState(false);
  const [scrolled,setScrolled]=useState(false);
  useEffect(()=>{const fn=()=>setScrolled(window.scrollY>24);window.addEventListener('scroll',fn,{passive:true});return()=>window.removeEventListener('scroll',fn)},[]);
  return <div className="site-shell">
    <header className={scrolled?'site-header compact':'site-header'}><a className="wordmark" href="#top"><span className="mark"><RadioTower size={19}/></span><span>OPEN<span className="wordmark-accent">VLC</span><small>FIELD GUIDE</small></span></a><nav id="site-navigation" aria-label="Site navigation" className={menu?'nav-open':''}>{navItems.map(([id,label])=><a key={id} href={`#${id}`} onClick={()=>setMenu(false)}>{label}</a>)}</nav><div className="header-actions"><a href={REPO} target="_blank" rel="noreferrer" className="header-source">SOURCE <ArrowUpRight size={13}/></a><button className="menu-toggle" onClick={()=>setMenu(v=>!v)} aria-label="Toggle navigation" aria-controls="site-navigation" aria-expanded={menu}>{menu?<X/>:<Menu/>}</button></div></header>
    <main id="top">
      <section className="hero"><div className="hero-copy"><div className="hero-kicker"><span className="pulse-dot"/> AN INTERACTIVE ENGINEERING GUIDE <span>·</span> ESP32 VISIBLE LIGHT COMMUNICATION</div><h1>Data, carried<br/>by <em>light.</em></h1><p className="hero-intro">A guided exploration of a short-range VLC prototype — from a file on the transmitter desktop to a reconstructed file at the receiver.</p><div className="hero-ctas"><a className="primary-cta" href="#journey">Explore the signal <ArrowDown size={16}/></a><a className="secondary-cta" href={REPO} target="_blank" rel="noreferrer"><Github size={16}/> View the implementation</a></div><div className="hero-facts"><div><b>4B5B</b><span>LINE CODING</span></div><div><b>NRZ / OOK</b><span>OPTICAL SIGNAL</span></div><div><b>CRC</b><span>INTEGRITY CHECKS</span></div></div></div><div className="hero-art" role="img" aria-label="Abstract visible light signal illustration"><div className="art-grid"/><div className="art-orbit orbit-one"/><div className="art-orbit orbit-two"/><div className="art-beam"/><div className="art-bulb"><Lightbulb size={52}/></div><div className="art-label label-a">15,000 SYMBOLS / SEC</div><div className="art-label label-b">VISIBLE LIGHT CHANNEL</div><div className="art-packet packet-a"/><div className="art-packet packet-b"/><div className="art-packet packet-c"/><span className="art-coord">TX / RX — LOS</span></div><div className="hero-bottom"><span>01 — SYSTEM OVERVIEW</span><span>SCROLL TO EXPLORE <ArrowDown size={13}/></span></div></section>
      <div className="ticker"><span>ESP32</span><i/> <span>4B5B LINE CODING</span><i/> <span>NRZ / OOK</span><i/> <span>BPW34 PHOTODIODE</span><i/> <span>CRC VALIDATION</span><i/> <span>SHORT-RANGE INDOOR VLC</span></div>
      <LessonExplorer/><Architecture/><Protocol/><Hardware/><Validation/><SourceFooter/>
    </main>
  </div>;
}
