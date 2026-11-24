import React, { useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity, ArrowDown, ArrowLeft, ArrowRight, ArrowUpRight, BookOpen,
  Cable, Check, ChevronDown, ChevronRight, CircuitBoard, Code2, Cpu,
  FileCode2, Github, Lightbulb, Menu, Radio, RotateCcw, Search,
  ShieldCheck, Sparkles, Waves, X, Zap
} from 'lucide-react';
import './academy.css';

const FW = '411f183a8592d8285118f613bb4909c5bbd9d3cc';
const APP = '80ef4afa63a3fe571ffd5026560bf7d7d90fbecc';
const REPO = 'https://github.com/luckyprinter/OpenVLC-Public';
const link = (path, ref = FW, lines = '') => REPO + '/blob/' + ref + '/' + path + (lines ? '#L' + lines.replace('-', '-L') : '');

const stages = [
  {id:'file',label:'Choose a file',kind:'file',eyebrow:'01 · APPLICATION',title:'A file becomes a transfer job',copy:'The transmitter application reads the selected file, records its size and name, and prepares the transfer settings. It does not send light itself: it coordinates the physical transmitter over USB serial.',signal:'FILE BYTES',detail:'Desktop TX application → serial controller',code:'tx_app_state.py'},
  {id:'usb',label:'USB serial',kind:'usb',eyebrow:'02 · HOST ↔ ESP32',title:'The host and board agree on a transfer',copy:'The desktop sends a STREAM_BEGIN command and waits for the firmware acknowledgement. File data is delivered in acknowledged blocks before the optical transmission starts.',signal:'STREAM_BEGIN → ACK → STREAM_DATA',detail:'Application serial controller → TX firmware command handler',code:'serial/controllers.py'},
  {id:'coding',label:'4B5B coding',kind:'coding',eyebrow:'03 · LINE CODING',title:'Eight bits become ten',copy:'Each byte is split into a high and low nibble. The firmware maps each 4-bit value to a 5-bit codeword, producing a transition-friendly stream for clock recovery.',signal:'BYTE → TWO 5-BIT CODEWORDS',detail:'TX firmware → send4b5bEncodedByte()',code:'firmware/tx/tx.ino'},
  {id:'frame',label:'Frame building',kind:'frame',eyebrow:'04 · PROTOCOL',title:'Payload gets structure and checks',copy:'A frame carries identifiers, lengths, chunk information, filename metadata, payload bytes, and integrity fields. The receiver uses these fields to find boundaries and reject damaged data.',signal:'SYNC → SOF → HEADER → PAYLOAD → CRC',detail:'TX buildFrame() ↔ RX processCompleteFrame()',code:'firmware/specs/protocol_spec.md'},
  {id:'light',label:'Light transmission',kind:'light',eyebrow:'05 · OPTICAL TX',title:'GPIO timing drives the LED',copy:'The ESP32 switches the LED driver according to the encoded symbol stream. The LED is the physical transmitter: the information travels across the room as changes in visible light.',signal:'GPIO5 → DRIVER → 12 V LED',detail:'TX sendOpticalFrame() → send4b5bBit()',code:'firmware/tx/tx.ino'},
  {id:'detect',label:'Photodetection',kind:'detect',eyebrow:'06 · ANALOG RX',title:'Photons become an electrical signal',copy:'The BPW34 photodiode converts received light into photocurrent. The OPA2604 transimpedance amplifier produces a voltage, and the LM393 comparator converts the threshold crossing into a digital signal.',signal:'BPW34 → OPA2604 → LM393 → GPIO5',detail:'Physical receiver front end → RX ESP32',code:'firmware/rx/rx.ino'},
  {id:'decode',label:'Sampling & decode',kind:'decode',eyebrow:'07 · RX FIRMWARE',title:'The receiver recovers symbols and bytes',copy:'The receiver samples around the expected symbol centre, uses majority voting when enabled, acquires synchronization, aligns to the encoded start marker, and decodes valid 5-bit codewords.',signal:'SAMPLES → SYNC → 5B → NIBBLES → BYTE',detail:'RX sampleRawAt() → read4b5bByte()',code:'firmware/rx/rx.ino'},
  {id:'file',label:'Verify & rebuild',kind:'verify',eyebrow:'08 · INTEGRITY',title:'Verified chunks become the original file',copy:'The receiver checks frame and chunk CRCs before accepting payload data. After all chunks arrive, whole-file CRC validation protects the reconstructed file. The desktop application can then save and compare it with the original reference.',signal:'FRAME CRC → CHUNK CRC → FILE CRC',detail:'RX firmware → RX desktop application',code:'firmware/rx/rx.ino'}
];

const codeLessons = [
 {id:'tx-state',level:'APPLICATION',name:'TX application state',path:'application-source/gui_dev_v3/tx_app_state.py',ref:APP,range:'23-36',lang:'python',summary:'The state object holds the transmitter workspace values. Notice that the mode is initialized to physical: this is an application setting, not a live connection.',lines:[
  ['settings: AppSettings = field(default_factory=load_settings)','Create settings from the persisted configuration when a state object is made.'],
  ['mode: str = "physical"','Default the application to its real serial-hardware backend.'],
  ['filename: str = "No file"','Keep a clear empty state before the user chooses a file.'],
  ['file_size_bytes: int = 0','Store the selected file size in bytes.'],
  ['total_chunks: int = 0','Track how many protocol chunks are needed.'],
  ['chunk_size: int = 256','Set the current default chunk payload size.'],
  ['encoding: str = "4B5B"','Expose the line-coding choice used by this application state.'],
  ['modulation: str = "NRZ / OOK"','Describe the optical modulation configuration.'],
  ['symbol_rate: str = "15,000 sym/s"','Represent the configured symbol rate.'],
  ['led_pin: int = 5','Record the transmitter GPIO assignment.'],
  ['tx_power: str = "100 %"','Store the configured TX power label.'],
  ['pre_emphasis: str = "Disabled"','Store whether pre-emphasis is enabled.'],
  ['status_text: str = "Offline — no hardware"','Start honestly: a default state does not mean a board is connected.']
 ],concept:'A dataclass field declaration gives the state object a named piece of data and, often, an initial value. These fields are not the transmission itself; UI actions and controller methods consume them.'},
 {id:'serial-start',level:'APPLICATION',name:'Begin a serial transfer',path:'application-source/gui_dev_v3/serial/controllers.py',ref:APP,range:'460-478',lang:'python',summary:'This excerpt constructs the STREAM_BEGIN command, updates the UI status, clears stale firmware stream state, sends the command, and waits for an acknowledgement.',lines:[
  ['begin = (','Start constructing a multi-line command string.'],
  ['f"STREAM_BEGIN:{tid}:1:{len(data)}:{chunk_size}"','Include transfer ID, mode/flags, byte length, and chunk size.'],
  ['f":{file_crc:04X}:1:{name_bytes.hex().upper()}"','Append the file CRC and encoded filename metadata.'],
  ['tot_c = max(1, (len(data) + chunk_size - 1) // chunk_size)','Calculate the number of chunks using integer ceiling division.'],
  ['self.status("Preparing", path.name, ... )','Tell the UI that this transfer is being prepared.'],
  ['self.send_line("STREAM_CLEAR")','Ask the TX firmware to clear previous stream state.'],
  ['si = self.line_counter','Remember the current serial-line index before sending.'],
  ['if not self.send_line(begin):','Stop if the command cannot be written to serial.'],
  ['return False','Report that the start operation failed.'],
  ['if not self.wait_for_line_containing(...):','Wait up to five seconds for the firmware acknowledgement.'],
  ['self.status("Send failed", ... )','Publish an explicit failure state if no acknowledgement arrives.'],
  ['return False','Do not proceed as if the firmware accepted the transfer.']
 ],concept:'The host and firmware use a small command protocol over USB serial. Sending a command is not the same as the LED transmitting: this is the control-plane handshake that prepares the hardware.'},
 {id:'tx-encode',level:'FIRMWARE · TX',name:'Encode one byte as 4B5B',path:'firmware/tx/tx.ino',ref:FW,range:'160-163',lang:'cpp',summary:'This tiny function is a good first example of bit manipulation. It separates a byte into two nibbles and looks up the 5-bit representation of each.',lines:[
  ['void send4b5bEncodedByte(uint8_t value) {','Define a function that receives one unsigned 8-bit value and returns no value.'],
  ['send4b5bCode(CODE_4B5B[(value >> 4) & 0x0F]);','Shift the high nibble down, mask to four bits, look up its codeword, then send five bits.'],
  ['send4b5bCode(CODE_4B5B[value & 0x0F]);','Mask the low nibble, look up its codeword, then send five bits.'],
  ['}','End the function.']
 ],concept:'For 0xA5, the high nibble is 0xA and the low nibble is 0x5. In this firmware table they map to 10110 and 01011. The result is ten transmitted bits for one original byte.'},
 {id:'tx-bit',level:'FIRMWARE · TX',name:'Put one bit on the LED driver',path:'firmware/tx/tx.ino',ref:FW,range:'147-150',lang:'cpp',summary:'This is the boundary between a logical bit and a physical GPIO level. The helper applies the configured line polarity, then waits for the symbol boundary.',lines:[
  ['void send4b5bBit(bool bitValue) {','Accept one logical bit as true or false.'],
  ['digitalWrite(TX_PIN, bitValue ? lineOneLevel() : lineZeroLevel());','Choose the electrical output level for logical one or zero, including active-low configuration.'],
  ['waitSymbolBoundary();','Hold the symbol for its configured timing interval.'],
  ['}','End the helper.']
 ],concept:'Logical 1 does not universally mean GPIO HIGH. The driver can be active-low. Keeping logical bit meaning separate from electrical pin polarity prevents the encoder from needing to know the transistor circuit details.'},
 {id:'tx-frame',level:'FIRMWARE · TX',name:'Build a protocol frame',path:'firmware/tx/tx.ino',ref:FW,range:'182-201',lang:'cpp',summary:'The frame builder writes fields into a byte buffer in a defined order, appends the payload, calculates a CRC, and returns the final frame length.',lines:[
  ['size_t buildFrame(...) {','Return the number of bytes written into the shared frame buffer.'],
  ['uint16_t chunkCrc = crc16_ccitt(payload, payloadLen);','Calculate integrity for this chunk payload.'],
  ['size_t pos = 0;','Use pos as the next free position in the frame buffer.'],
  ['frameBuf[pos++] = SOF_BYTE;','Write the start-of-frame marker and advance pos.'],
  ['frameBuf[pos++] = VERSION_BYTE;','Write the protocol version.'],
  ['frameBuf[pos++] = frameType;','Write the frame type.'],
  ['putU16 / putU32(...)','Serialize multi-byte metadata fields into the buffer.'],
  ['for (...) frameBuf[pos++] = ...;','Append filename bytes and payload bytes.'],
  ['uint16_t frameCrc = crc16_ccitt(frameBuf, pos);','Calculate CRC over all frame bytes written so far.'],
  ['putU16(frameBuf, pos, frameCrc);','Append the frame CRC.'],
  ['return pos;','Return the total frame length.']
 ],concept:'The exact byte order and field widths are part of the protocol contract. The receiver must parse the same order. This is why the protocol specification and both firmware implementations must be studied together.'},
 {id:'rx-majority',level:'FIRMWARE · RX',name:'Read a symbol with majority voting',path:'firmware/rx/rx.ino',ref:FW,range:'761-771',lang:'cpp',summary:'Instead of trusting one digital read, this helper can take three readings around the expected symbol centre and choose the majority value.',lines:[
  ['bool sampleRawAt(uint32_t sampleTimeUs) {','Return one recovered raw bit for a target time in microseconds.'],
  ['if (!useMajoritySampling || symbolUs < 30) ...','Use a single read if majority mode is off or the symbol is too short for this sampling pattern.'],
  ['uint32_t delta = symbolUs / 6;','Place the outer samples one-sixth of a symbol period before and after the centre.'],
  ['waitUntil(sampleTimeUs - delta);','Wait until the first sample instant.'],
  ['bool a = digitalRead(RX_PIN);','Read the comparator output.'],
  ['waitUntil(sampleTimeUs);','Wait for the centre sample.'],
  ['bool b = digitalRead(RX_PIN);','Read the second sample.'],
  ['waitUntil(sampleTimeUs + delta);','Wait for the third sample instant.'],
  ['bool c = digitalRead(RX_PIN);','Read the third sample.'],
  ['return (a + b + c) >= 2;','Return true when at least two of the three readings are HIGH.'],
  ['}','End the function.']
 ],concept:'At 15 ksymbols/s, one symbol lasts about 66.7 microseconds. The three samples are close together around the centre, where the receiver expects the symbol to be stable.'},
 {id:'rx-decode',level:'FIRMWARE · RX',name:'Decode two codewords into one byte',path:'firmware/rx/rx.ino',ref:FW,range:'840-854',lang:'cpp',summary:'The receiver reads two 5-bit groups, looks each one up in the reverse table, rejects invalid entries, and combines two nibbles into one byte.',lines:[
  ['bool read4b5bByte(uint8_t &value) {','Return success/failure and write the decoded byte through a reference parameter.'],
  ['if (!lineSynced && !acquire4b5bSync()) return false;','Acquire line synchronization before decoding data.'],
  ['if (!frameAligned) return alignToEncodedSof(value);','Find the encoded start-of-frame boundary before normal payload decoding.'],
  ['uint8_t highCode = 0, lowCode = 0;','Reserve variables for the two 5-bit codewords.'],
  ['if (!read5b(highCode) || !read5b(lowCode)) return false;','Read both groups; stop if either read fails.'],
  ['int8_t highNibble = DECODE_4B5B[highCode & 0x1F];','Look up the first codeword in the reverse table.'],
  ['int8_t lowNibble = DECODE_4B5B[lowCode & 0x1F];','Look up the second codeword.'],
  ['if (highNibble < 0 || lowNibble < 0) {','Negative lookup values mean an invalid codeword.'],
  ['invalidCodeCount++; resetLineDecoder();','Count the error and reset decoder alignment.'],
  ['value = (uint8_t)((highNibble << 4) | lowNibble);','Shift the high nibble into place and combine it with the low nibble.'],
  ['return true;','Report that one byte was decoded successfully.']
 ],concept:'The ampersand in highCode & 0x1F is a bitwise AND mask. The double ampersand in the validity check is logical AND. These operators look similar but do different jobs.'},
 {id:'rx-crc',level:'FIRMWARE · RX',name:'Validate a complete frame',path:'firmware/rx/rx.ino',ref:FW,range:'907-942',lang:'cpp',summary:'This function validates the frame CRC first, checks metadata and lengths, validates the chunk CRC, and only then hands verified data to the chunk buffer.',lines:[
  ['void processCompleteFrame() {','Process a frame after the byte decoder has assembled it.'],
  ['if (framePos < 1 + 19 + 2) ...','Reject a frame too short to contain required fields and CRC.'],
  ['uint16_t rxFrameCrc = getU16(...);','Read the CRC sent at the end of the frame.'],
  ['uint16_t calcFrameCrc = crc16_ccitt(...);','Recalculate the CRC from received bytes.'],
  ['if (rxFrameCrc != calcFrameCrc) ...','Reject the frame if the CRC does not match.'],
  ['uint8_t / uint16_t / uint32_t fields...','Decode version, frame type, transfer ID, sizes, indexes, CRC, and filename length.'],
  ['if (version != VERSION_BYTE || ...) ...','Reject unsupported or out-of-range metadata.'],
  ['size_t payloadStart = nameStart + nameLen;','Locate the payload after the variable-length filename.'],
  ['if (payloadStart + chunkLen + 2 != framePos) ...','Check that the declared payload and trailing CRC fit the actual frame.'],
  ['uint16_t calcChunkCrc = crc16_ccitt(...);','Calculate integrity for the payload only.'],
  ['if (rxChunkCrc != calcChunkCrc) ...','Reject a damaged chunk.'],
  ['bufferVerifiedChunk(...);','Pass only verified metadata and payload to the reassembly buffer.'],
  ['resetLineDecoder();','Reset per-frame decoding state after processing.']
 ],concept:'A frame CRC protects the frame structure and metadata. A chunk CRC checks the payload chunk. Later, a whole-file CRC checks the reconstructed file. They protect different scopes.'}
];

const paths = [
 {id:'start',number:'01',title:'Understand the prototype',desc:'Start with the real device, its purpose, and the experiment.',duration:'20 min',items:['What visible-light communication means','The physical TX and RX assemblies','The room-scale optical link','What the experiment measured']},
 {id:'hardware',number:'02',title:'Explore the hardware',desc:'Follow the electrical and optical signal through every component.',duration:'35 min',items:['ESP32 transmitter and LED driver','12 V LED and optical path','BPW34 photodiode and OPA2604 TIA','LM393 comparator and receiver GPIO']},
 {id:'protocol',number:'03',title:'Understand the protocol',desc:'Learn how bytes become symbols, frames, and verified chunks.',duration:'45 min',items:['Binary, bits, bytes, and nibbles','4B5B line coding','NRZ/OOK modulation','Synchronization, frame fields, and CRC']},
 {id:'software',number:'04',title:'Explore the software',desc:'Understand the desktop applications and firmware responsibilities.',duration:'45 min',items:['TX application state and serial controller','TX firmware command and stream path','RX sampling and decoder pipeline','RX application and file reconstruction']},
 {id:'code',number:'05',title:'Learn to read the code',desc:'Build programming confidence by tracing real functions line by line.',duration:'60 min',items:['Variables, types, arrays, and pointers','Conditions, loops, and bitwise operators','Function calls and data flow','Debugging and safe code changes']},
 {id:'practice',number:'06',title:'Practice and check understanding',desc:'Use small challenges to test whether the concepts really make sense.',duration:'25 min',items:['Predict the encoded bits','Trace a received byte','Find a CRC validation bug','Complete the final knowledge check']}
];

function Brand(){return <a className="academy-brand" href="#home" aria-label="OpenVLC Academy home"><span className="brand-mark"><Waves size={19}/></span><span>OPENVLC <b>ACADEMY</b></span></a>}

function HeroModel(){
 return <div className="hero-model" aria-label="Animated illustration of a visible light communication link">
  <div className="model-grid"/><div className="model-orbit orbit-a"/><div className="model-orbit orbit-b"/>
  <div className="model-device tx-device"><Cpu size={25}/><b>TX</b><small>ESP32</small></div>
  <div className="model-device rx-device"><CircuitBoard size={25}/><b>RX</b><small>ESP32</small></div>
  <div className="model-lamp"><Lightbulb size={31}/></div>
  <div className="light-beam"/>{Array.from({length:7},(_,i)=><i className="hero-photon" style={{'--i':i}} key={i}/>)}
  <span className="model-label label-tx">TRANSMITTER</span><span className="model-label label-link">VISIBLE LIGHT · LOS</span><span className="model-label label-rx">RECEIVER</span>
  <div className="model-readout"><span><i/> OPTICAL LINK MODEL</span><b>DATA → LIGHT → DATA</b></div>
 </div>
}

function StageVisual({stage}){
 const base = <div className="stage-visual-top"><span>INTERACTIVE SIGNAL MODEL</span><span>STAGE {String(stages.findIndex(s=>s.id===stage.id)+1).padStart(2,'0')} / 08</span></div>;
 return <div className={'stage-visual visual-'+stage.kind}>{base}
  <AnimatePresence mode="wait">
   <motion.div key={stage.id} className="stage-scene" initial={{opacity:0,y:12,scale:.98}} animate={{opacity:1,y:0,scale:1}} exit={{opacity:0,y:-8}} transition={{duration:.28}}>
    {stage.kind==='file'&&<><div className="file-sheet"><FileCode2 size={34}/><b>sample.bin</b><small>FILE · 4,096 BYTES</small><div className="file-lines"><i/><i/><i/><i/></div></div><motion.div className="scene-arrow" animate={{x:[0,16,0]}} transition={{repeat:Infinity,duration:2}}><ArrowRight/></motion.div><div className="scene-chip"><Cpu/><b>TX APP</b><small>TRANSFER JOB</small></div></>}
    {stage.kind==='usb'&&<><div className="scene-chip"><LaptopGlyph/><b>DESKTOP</b><small>TX APPLICATION</small></div><motion.div className="usb-cable" animate={{opacity:[.55,1,.55]}} transition={{repeat:Infinity,duration:1.8}}/><div className="scene-chip"><Cpu/><b>ESP32</b><small>TX FIRMWARE</small></div><div className="serial-packets">{['BEGIN','ACK','DATA'].map((x,i)=><motion.i key={x} animate={{x:[-18,18,-18],opacity:[.25,1,.25]}} transition={{repeat:Infinity,duration:2.2,delay:i*.35}}>{x}</motion.i>)}</div></>}
    {stage.kind==='coding'&&<><div className="bit-group"><small>INPUT BYTE</small><b>1010 0101</b></div><motion.div className="encode-arrow" animate={{scale:[1,1.12,1]}} transition={{repeat:Infinity,duration:2}}><Zap/></motion.div><div className="codeword-groups"><small>ENCODED · 4B5B</small><b>10110 <em>01011</em></b><span>5 bits + 5 bits</span></div><div className="moving-bits">{'1011001011'.split('').map((b,i)=><motion.i key={i} animate={{y:[0,-5,0],opacity:[.5,1,.5]}} transition={{repeat:Infinity,duration:1.4,delay:i*.08}}>{b}</motion.i>)}</div></>}
    {stage.kind==='frame'&&<><div className="frame-stack"><span>SOF</span><span>HEADER</span><span>NAME</span><span>PAYLOAD</span><span>CRC</span></div><motion.div className="frame-scan" animate={{x:['-5%','105%']}} transition={{repeat:Infinity,duration:3,ease:'linear'}}/><div className="frame-check"><ShieldCheck/><b>INTEGRITY FIELDS</b><small>FRAME + CHUNK</small></div></>}
    {stage.kind==='light'&&<><div className="mini-board"><Cpu/><b>ESP32</b><small>GPIO 5</small></div><div className="driver-block"><CircuitBoard/><b>LED DRIVER</b><small>SWITCHING STAGE</small></div><div className="mini-led"><Lightbulb/><span/></div><div className="beam-particles">{Array.from({length:8},(_,i)=><motion.i key={i} animate={{x:[0,230],opacity:[0,1,0],scale:[.6,1,.6]}} transition={{repeat:Infinity,duration:2.3,delay:i*.25,ease:'linear'}}/>)}</div><span className="scene-caption">SYMBOL TIMING CONTROLS LIGHT OUTPUT</span></>}
    {stage.kind==='detect'&&<><div className="detector-chain"><div><Radio/><b>BPW34</b><small>PHOTOCURRENT</small></div><ArrowRight/><div><Activity/><b>OPA2604</b><small>VOLTAGE</small></div><ArrowRight/><div><Zap/><b>LM393</b><small>DIGITAL EDGE</small></div></div><div className="analog-trace"><svg viewBox="0 0 520 100" role="img" aria-label="Conceptual analog signal"><path d="M0 68 C35 68 35 20 75 20 S110 75 150 75 S190 30 230 30 S270 65 310 65 S350 18 390 18 S430 72 470 72 S495 42 520 42" fill="none" stroke="#ffbd70" strokeWidth="3"/><path d="M0 78H520" stroke="#526c76" strokeDasharray="5 7"/></svg></div><small className="scene-caption">CONCEPTUAL SIGNAL SHAPE · NOT A MEASURED TRACE</small></>}
    {stage.kind==='decode'&&<><div className="sample-wave"><div className="wave-label">COMPARATOR OUTPUT</div><svg viewBox="0 0 520 130" role="img" aria-label="Conceptual digital waveform with three sample markers"><path d="M0 94H55V28H130V94H205V28H280V94H355V28H430V94H520" fill="none" stroke="#7dd7c7" strokeWidth="3"/>{[72,91,110,222,241,260,372,391,410].map((x,i)=><circle key={i} cx={x} cy={i%3===0?28:94} r="5" fill="#ffbd70"/>)}</svg><div className="sample-legend"><span><i/> SAMPLE POINTS</span><span>3-READ MAJORITY</span></div></div><div className="decode-result"><b>10110</b><ArrowRight/><b>1010</b><small>VALID NIBBLE</small></div></>}
    {stage.kind==='verify'&&<><div className="verify-stack"><div><Check/><span>FRAME CRC</span><b>PASS</b></div><div><Check/><span>CHUNK CRC</span><b>PASS</b></div><div><Check/><span>FILE CRC</span><b>PASS</b></div></div><motion.div className="rebuild-file" animate={{y:[0,-5,0]}} transition={{repeat:Infinity,duration:2}}><FileCode2 size={30}/><b>original-file.bin</b><small>REASSEMBLED</small></motion.div></>}
   </motion.div>
  </AnimatePresence>
  <div className="stage-visual-bottom"><span>{stage.signal}</span><span>MODEL · NOT LIVE TELEMETRY</span></div>
 </div>
}
function LaptopGlyph(){return <Cable size={24}/>}

function SignalJourney(){
 const [index,setIndex]=useState(0); const [playing,setPlaying]=useState(false); const stage=stages[index];
 React.useEffect(()=>{if(!playing)return;const id=setInterval(()=>setIndex(v=>(v+1)%stages.length),3800);return()=>clearInterval(id)},[playing]);
 return <section className="journey-section" id="journey"><div className="section-kicker">THE COMPLETE TRANSMISSION <span>08 STAGES</span></div><div className="section-title-row"><div><p className="eyebrow">FROM A FILE TO LIGHT AND BACK</p><h2>Follow one transfer.<br/><i>All the way through.</i></h2></div><p className="section-intro">Move through the physical prototype one stage at a time. Each step changes the model, explains what is happening, and points to the responsible code.</p></div>
  <div className="journey-layout"><aside className="stage-rail">{stages.map((s,i)=><button key={s.id+i} className={index===i?'active':''} onClick={()=>{setIndex(i);setPlaying(false)}}><span>{String(i+1).padStart(2,'0')}</span><b>{s.label}</b><i/></button>)}</aside><div className="journey-content"><StageVisual stage={stage}/><div className="journey-explain"><div className="eyebrow">{stage.eyebrow}</div><h3>{stage.title}</h3><p>{stage.copy}</p><div className="stage-connection"><Cable size={15}/><span>{stage.detail}</span></div><div className="stage-actions"><button onClick={()=>setIndex(v=>Math.max(0,v-1))} disabled={index===0}><ArrowLeft size={15}/> PREVIOUS</button><button className="journey-play" onClick={()=>setPlaying(v=>!v)}>{playing?'PAUSE':'AUTO PLAY'} <Activity size={14}/></button><button className="next-stage" onClick={()=>{setIndex(v=>(v+1)%stages.length);setPlaying(false)}}>NEXT STAGE <ArrowRight size={15}/></button></div></div></div></div>
 </section>
}

function PathCards({onOpen}){return <section className="paths-section" id="learn"><div className="section-kicker">YOUR LEARNING ROUTE <span>01—06</span></div><div className="section-title-row"><div><p className="eyebrow">BUILT FOR CURIOUS BEGINNERS</p><h2>Learn it in layers.<br/><i>Build real understanding.</i></h2></div><p className="section-intro">Short lessons, clear prerequisites, interactive models, and practical checks. Take your time—each path prepares you for the next.</p></div><div className="path-grid">{paths.map((p,i)=><motion.button key={p.id} className={'path-card path-'+p.id} onClick={()=>onOpen(p.id)} whileHover={{y:-6}} whileTap={{scale:.99}}><div className="path-card-top"><span>{p.number} / 06</span><span>{p.duration}</span></div><div className="path-icon">{[<Lightbulb/>,<CircuitBoard/>,<Radio/>,<Cpu/>,<Code2/>,<ShieldCheck/>][i]}</div><h3>{p.title}</h3><p>{p.desc}</p><div className="path-card-bottom"><span>{p.items.length} LESSONS</span><ArrowUpRight size={18}/></div></motion.button>)}</div></section>}

function CodeLesson({lesson,selected,onSelect}){
 const [line,setLine]=useState(0); const [showAll,setShowAll]=useState(false);
 React.useEffect(()=>{setLine(0);setShowAll(false)},[lesson.id]);
 const source=link(lesson.path,lesson.ref,lesson.range);
 return <article className="code-lesson">
  <div className="code-lesson-head"><div><span className="eyebrow">{lesson.level}</span><h3>{lesson.name}</h3><p>{lesson.summary}</p></div><a href={source} target="_blank" rel="noreferrer">SOURCE LINES <ArrowUpRight size={14}/></a></div>
  <div className="code-editor"><div className="editor-bar"><span><i/> {lesson.path.split('/').slice(-1)[0]}</span><span>{lesson.lang.toUpperCase()} · L{lesson.range.replace('-', '–')}</span></div><div className="editor-code">{lesson.lines.map(([code,explain],i)=><button key={i} className={'editor-line '+(line===i?'chosen':'')} onClick={()=>setLine(i)}><span className="line-no">{Number(lesson.range.split('-')[0])+i}</span><code>{code}</code></button>)}</div><div className="editor-explain"><span>LINE EXPLAINER · {line+1}/{lesson.lines.length}</span><p>{lesson.lines[line][1]}</p><div><button disabled={line===0} onClick={()=>setLine(v=>v-1)}><ArrowLeft size={13}/> PREVIOUS LINE</button><button disabled={line===lesson.lines.length-1} onClick={()=>setLine(v=>v+1)}>NEXT LINE <ArrowRight size={13}/></button></div></div></div>
  <div className="code-concept"><Sparkles size={17}/><div><b>THE BIG IDEA</b><p>{lesson.concept}</p></div></div>
 </article>
}

function CodeStudio(){
 const [active,setActive]=useState('tx-encode'); const [query,setQuery]=useState(''); const selected=codeLessons.find(x=>x.id===active)||codeLessons[0];
 const groups=['APPLICATION','FIRMWARE · TX','FIRMWARE · RX'];
 const filtered=useMemo(()=>codeLessons.filter(x=>(x.name+' '+x.path+' '+x.level).toLowerCase().includes(query.toLowerCase())),[query]);
 return <section className="code-studio" id="code"><div className="section-kicker">SOURCE CODE STUDIO <span>REAL FILES · PINNED LINES</span></div><div className="section-title-row"><div><p className="eyebrow">FROM SURFACE KNOWLEDGE TO CODE CONFIDENCE</p><h2>Understand the code.<br/><i>One line at a time.</i></h2></div><p className="section-intro">Select a source lesson, tap any line, and read what it does. Each example is pinned to a commit so the code and line numbers stay traceable.</p></div>
 <div className="studio-layout"><aside className="studio-sidebar"><label className="studio-search"><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Find a function or file"/></label>{groups.map(g=><div className="file-group" key={g}><span>{g}</span>{filtered.filter(x=>x.level===g).map(x=><button key={x.id} className={active===x.id?'active':''} onClick={()=>setActive(x.id)}><FileCode2 size={14}/><span>{x.name}</span><ChevronRight size={13}/></button>)}</div>)}</aside><div className="studio-main"><CodeLesson lesson={selected}/></div></div>
 </section>
}

function PathDetail({id,onBack}){const path=paths.find(x=>x.id===id)||paths[0];const [done,setDone]=useState([]);return <section className="path-detail"><button className="back-link" onClick={onBack}><ArrowLeft size={15}/> ALL LEARNING PATHS</button><div className="path-detail-hero"><span className="eyebrow">LEARNING PATH {path.number} · {path.duration}</span><h2>{path.title}</h2><p>{path.desc}</p></div><div className="path-detail-list">{path.items.map((item,i)=><button key={item} onClick={()=>setDone(v=>v.includes(i)?v.filter(x=>x!==i):[...v,i])} className={done.includes(i)?'completed':''}><span>{done.includes(i)?<Check size={16}/>:String(i+1).padStart(2,'0')}</span><b>{item}</b><small>{done.includes(i)?'COMPLETED':'MARK COMPLETE'}</small><ChevronRight size={16}/></button>)}</div><div className="path-detail-note"><Sparkles size={18}/><p>Lessons will open as focused pages with diagrams, code walkthroughs, and knowledge checks. Your progress here is local to this browser session in this first course release.</p></div></section>}

function QuizPreview(){const [answer,setAnswer]=useState('');const [checked,setChecked]=useState(false);return <div className="quiz-card"><div className="eyebrow">QUICK KNOWLEDGE CHECK</div><h3>Why does the receiver take three samples?</h3><div className="quiz-options">{[{v:'a',t:'To triple the data rate'},{v:'b',t:'To reduce the effect of a noisy or unstable single reading'},{v:'c',t:'To calculate the file CRC'}].map(o=><button key={o.v} className={answer===o.v?'selected':''} onClick={()=>{setAnswer(o.v);setChecked(false)}}><i>{o.v.toUpperCase()}</i>{o.t}</button>)}</div><button className="quiz-submit" disabled={!answer} onClick={()=>setChecked(true)}>CHECK ANSWER <ArrowRight size={14}/></button>{checked&&<p className={answer==='b'?'correct':'incorrect'}>{answer==='b'?'Correct. Majority voting accepts the value seen by at least two of the three samples.':'Not quite. Think about what can happen when one sample lands near a noisy edge.'}</p>}</div>}

export default function Academy(){
 const [view,setView]=useState('home');const [path,setPath]=useState('start');const [menu,setMenu]=useState(false);
 const openPath=id=>{setPath(id);setView('path');setMenu(false);window.location.hash='path/'+id};
 const backHome=()=>{setView('home');window.location.hash='home'};
 return <div className="academy-shell">
  <header className="academy-header"><Brand/><nav className={menu?'open':''}><a href="#learn" onClick={()=>{setView('home');setMenu(false)}}>LEARNING PATHS</a><a href="#journey" onClick={()=>{setView('home');setMenu(false)}}>SIGNAL JOURNEY</a><a href="#code" onClick={()=>{setView('home');setMenu(false)}}>CODE STUDIO</a><a href={REPO} target="_blank" rel="noreferrer">SOURCE REPO <ArrowUpRight size={12}/></a></nav><button className="mobile-menu" onClick={()=>setMenu(v=>!v)} aria-label="Toggle navigation">{menu?<X/>:<Menu/>}</button></header>
  {view==='path'?<PathDetail id={path} onBack={backHome}/>:<>
   <main><section className="academy-hero" id="home"><div className="hero-copy"><div className="hero-eyebrow"><i/> AN INTERACTIVE ENGINEERING COURSE</div><h1>Data carried<br/>by <em>light.</em></h1><p>Learn how a real ESP32 visible-light communication prototype works—from the LED driver and photodiode to the firmware and desktop code that make it communicate.</p><div className="hero-buttons"><a href="#learn" className="hero-primary">START LEARNING <ArrowRight size={16}/></a><a href="#journey" className="hero-secondary">EXPLORE THE SIGNAL <Waves size={16}/></a></div><div className="hero-stats"><div><b>06</b><span>LEARNING PATHS</span></div><div><b>08</b><span>TRANSMISSION STAGES</span></div><div><b>REAL</b><span>HARDWARE SOURCE</span></div></div></div><HeroModel/></section>
   <div className="academy-ticker"><span>ESP32 TRANSMITTER</span><i/><span>4B5B + NRZ/OOK</span><i/><span>VISIBLE LIGHT</span><i/><span>BPW34 RECEIVER</span><i/><span>CRC VERIFIED FILE</span></div>
   <SignalJourney/><PathCards onOpen={openPath}/><CodeStudio/>
   <section className="practice-section" id="practice"><div><div className="section-kicker">LEARN BY DOING <span>COMING INTO FOCUS</span></div><p className="eyebrow">A LITTLE PRACTICE GOES A LONG WAY</p><h2>Don't just read it.<br/><i>Trace it yourself.</i></h2><p className="section-intro">The course will grow from guided examples into short challenges: predict a bit pattern, trace a function call, identify a bug, and explain why a hardware setting matters.</p><button className="practice-cta" onClick={()=>openPath('practice')}>EXPLORE PRACTICE PATH <ArrowRight size={15}/></button></div><QuizPreview/></section>
  </main>
  <footer className="academy-footer"><div><Brand/><p>An interactive guide to the physical OpenVLC visible-light communication prototype.</p></div><div className="footer-links"><a href={REPO} target="_blank" rel="noreferrer"><Github size={16}/> SOURCE CODE <ArrowUpRight size={13}/></a><a href="https://github.com/luckyprinter/lifi" target="_blank" rel="noreferrer">ACADEMY WEBSITE REPO <ArrowUpRight size={13}/></a></div><div className="footer-bottom"><span>FIRMWARE BASELINE · {FW.slice(0,8)}</span><span>APPLICATION SNAPSHOT · {APP.slice(0,8)} · DRAFT DEVELOPMENT</span><span>CONCEPTUAL MODELS ARE NOT LIVE HARDWARE TELEMETRY</span></div></footer>
  </>}
 </div>
}
