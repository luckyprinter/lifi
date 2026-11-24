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
const APP = FW; // Application and firmware lessons both use the audited OpenVLC-Public main snapshot.
const REPO = 'https://github.com/luckyprinter/OpenVLC-Public';
const link = (path, ref = FW, lines = '') => REPO + '/blob/' + ref + '/' + path + (lines ? '#L' + lines.replace('-', '-L') : '');

const stages = [
  {id:'file',label:'Choose a file',kind:'file',eyebrow:'01 · TX APPLICATION',title:'A person selects a file, then presses Start',copy:'Open the TX console, choose a file from the Dashboard, inspect its metadata, and press Start. File Manager queueing is a separate action and does not automatically start the Dashboard transfer.',signal:'SELECT FILE → METADATA → START',detail:'TX Dashboard → TXAppState → physical backend',code:'application-source/gui_dev_v3/app.py',codeLesson:'app-launch'},
  {id:'usb',label:'Prepare over USB',kind:'usb',eyebrow:'02 · HOST ↔ ESP32',title:'Python prepares the physical transmitter',copy:'The application state delegates to the physical backend, which starts a background serial-controller worker. The controller reads the file, calculates its CRC, chooses a supported transfer path, and performs the USB serial handshake.',signal:'STREAM_BEGIN → ACK → STREAM_DATA → ACK',detail:'TXAppState → TXPhysicalBackend → TXSerialController',code:'application-source/gui_dev_v3/serial/controllers.py',codeLesson:'tx-start'},
  {id:'frame',label:'Build protocol frames',kind:'frame',eyebrow:'03 · TX FIRMWARE',title:'The ESP32 builds frames and chunks',copy:'After STREAM_START, the TX firmware verifies the preloaded file CRC, creates a transfer-notice frame, divides the payload into chunks, and builds each frame with its metadata and integrity fields.',signal:'SOF → HEADER → NAME → PAYLOAD → CRC',detail:'handleStreamStart() → buildFrame()',code:'firmware/tx/tx.ino',codeLesson:'tx-frame'},
  {id:'coding',label:'Encode with 4B5B',kind:'coding',eyebrow:'04 · LINE CODING',title:'Eight data bits become ten encoded bits',copy:'Each frame byte is split into a high and low nibble. The TX firmware maps each nibble to a five-bit codeword, then sends the preamble and synchronization word before the encoded frame bytes.',signal:'BYTE → TWO 5-BIT CODEWORDS',detail:'send4b5bEncodedByte() → send4b5bCode()',code:'firmware/tx/tx.ino',codeLesson:'tx-encode'},
  {id:'light',label:'Transmit visible light',kind:'light',eyebrow:'05 · OPTICAL TX',title:'GPIO timing drives the LED',copy:'The ESP32 writes logical symbol levels to GPIO5 using the configured driver polarity. The external driver switches the 12 V LED load, and the LED carries the encoded data across the line-of-sight optical path.',signal:'GPIO5 → LED DRIVER → 12 V LED → LIGHT',detail:'send4b5bBit() → physical LED driver',code:'firmware/tx/tx.ino',codeLesson:'tx-bit'},
  {id:'detect',label:'Photodetect the signal',kind:'detect',eyebrow:'06 · ANALOG RX',title:'Photons become an electrical signal',copy:'The BPW34 photodiode converts received light into photocurrent. The OPA2604 transimpedance amplifier produces a voltage, and the LM393 comparator converts the threshold crossing into a digital signal for RX GPIO5.',signal:'BPW34 → OPA2604 → LM393 → GPIO5',detail:'Physical receiver front end → RX ESP32',code:'firmware/rx/rx.ino',codeLesson:'rx-majority'},
  {id:'decode',label:'Sample and decode',kind:'decode',eyebrow:'07 · RX FIRMWARE',title:'The receiver recovers symbols, bytes, and chunks',copy:'The RX ESP32 detects idle and the start edge, samples around the symbol centre, acquires the preamble and sync word, decodes 4B5B, parses frames, and validates frame and chunk CRCs before storing data.',signal:'SAMPLES → SYNC → 4B5B → FRAME → CHUNK',detail:'sampleRawAt() → read4b5bByte() → processCompleteFrame()',code:'firmware/rx/rx.ino',codeLesson:'rx-decode'},
  {id:'verify',label:'Inspect and verify',kind:'verify',eyebrow:'08 · RX APPLICATION',title:'RX saves the file; the user inspects it',copy:'The receiver listens automatically. Once the firmware reconstructs the file and passes whole-file CRC, the RX desktop backend receives RX_FILE_HEX and saves it. The user can then open Inspect, select chunks, load the original reference file, and run BER analysis.',signal:'RX_FILE_HEX → SAVE → INSPECT → REFERENCE BER',detail:'RX firmware → RX physical backend → RX Dashboard / Inspect / BER',code:'application-source/gui_dev_v3/rx/backends/physical.py',codeLesson:'rx-app'}
];

const stageTrace = {
 file: {
  user:{title:'What the person does',body:'Open the system launcher, choose Transmitter Console, go to Dashboard, press Select File, and choose a local file. After checking the displayed details, press Start. The File Manager is a different workflow: Browse / Add File and Add to Transmit Queue place a file in a queue; that action is not the dashboard Start button.',note:'Selecting a file prepares the job. It does not transmit the file over the optical link yet.',sources:[{label:'Dashboard file selection',path:'application-source/gui_dev_v3/tx/dashboard.py',lines:'719-752',lesson:'tx-select'},{label:'Dashboard Start action',path:'application-source/gui_dev_v3/tx/dashboard.py',lines:'754-766',lesson:'tx-start'}]},
  application:{title:'What the TX application does',body:'The dashboard opens a QFileDialog, checks that the chosen path exists, stores the filename, extension, byte size, estimated chunk count, and estimated duration, then saves the full path as _pending_filepath. When Start is clicked, the handler passes that path to TXAppState.start_transmission().',note:'The selected-file metadata is application state. The actual file bytes are read later by the serial controller.',sources:[{label:'Selected-file state and metadata',path:'application-source/gui_dev_v3/tx/dashboard.py',lines:'719-752',lesson:'tx-select'},{label:'TX state fields',path:'application-source/gui_dev_v3/tx_app_state.py',lines:'29-41',lesson:'tx-state'}]},
  serial:{title:'What crosses USB serial',body:'Nothing containing the selected file is sent merely because the user selected it. The physical TX connection already exists or is being auto-detected. The file-preload and command handshake begin only after Start delegates the job to the physical backend and serial controller.',note:'This is an important boundary: file selection is a GUI action; serial transfer is a later operation.',sources:[{label:'Physical TX backend entry point',path:'application-source/gui_dev_v3/tx/backends/physical.py',lines:'194-207'},{label:'Serial controller STREAM path',path:'application-source/gui_dev_v3/serial/controllers.py',lines:'326-356',lesson:'serial-start'}]},
  hardware:{title:'What the device is doing',body:'The TX ESP32 is connected to the desktop by USB. At the file-selection stage it has not started emitting the file as light. It is waiting for the host to send the transfer setup and payload, followed by STREAM_START.',note:'The lamp can remain illuminated in its configured idle state; idle illumination is not proof that a file is being transmitted.',sources:[{label:'TX firmware stream command handlers',path:'firmware/tx/tx.ino',lines:'219-256'}]},
  observe:{title:'What the reader should see',body:'The dashboard File Details panel shows filename, size, chunk count, estimated duration, and status. After selection, the status becomes “Selected …”. The Start button is enabled only when the serial connection is available.',note:'The dashboard bitstream widget is a deterministic illustrative pattern generated from file size, not a hardware capture of the exact outgoing bitstream. Treat it as an animation, not measurement evidence.',sources:[{label:'File Details display and button state',path:'application-source/gui_dev_v3/tx/dashboard.py',lines:'332-414'}]}
 },
 usb: {
  user:{title:'The user starts the transfer',body:'The user presses Start on the TX Dashboard. If a file is already pending, the handler passes its path to the application state. If not, it asks the user to select a file first.',note:'The Start action is the handoff from the GUI workflow into the transmission pipeline.',sources:[{label:'Start button handler',path:'application-source/gui_dev_v3/tx/dashboard.py',lines:'754-766',lesson:'tx-start'}]},
  application:{title:'State → physical backend → controller',body:'TXAppState.start_transmission() delegates to TXPhysicalBackend in physical mode. The physical backend starts a background thread whose target is TXSerialController.send_file(). Running the work in a background thread keeps the Qt interface responsive while the file is read and sent.',note:'The website teaches this physical path as the prototype path. Simulation classes remain alternate/test infrastructure in the repository, not the device’s real optical path.',sources:[{label:'TXAppState delegation',path:'application-source/gui_dev_v3/tx_app_state.py',lines:'225-238'},{label:'Background serial worker',path:'application-source/gui_dev_v3/tx/backends/physical.py',lines:'194-207'}]},
  serial:{title:'The controller prepares the file',body:'The controller reads the file bytes, calculates the file CRC, chooses a transfer ID, and decides between DMA and STREAM. DMA is used only when the user setting requests it and the connected firmware reports DMA capability; otherwise the controller uses the STREAM path. The walkthrough follows STREAM, which is the non-DMA path supported by the pinned TX firmware.',note:'DMA is a capability-gated alternate path. Do not assume every TX firmware build supports it.',sources:[{label:'Transfer path selection and STREAM fallback',path:'application-source/gui_dev_v3/serial/controllers.py',lines:'145-190'},{label:'STREAM command and acknowledgement',path:'application-source/gui_dev_v3/serial/controllers.py',lines:'326-356',lesson:'serial-start'}]},
  hardware:{title:'The TX ESP32 prepares its buffer',body:'The board receives the stream setup metadata, validates the file size and chunk size, records the transfer ID and expected file CRC, decodes the filename, and calculates the number of chunks. It acknowledges with TX_STREAM_BEGIN_OK.',note:'The host-to-board USB transfer is a preload/control stage. The optical data frames are emitted only after the later STREAM_START command.',sources:[{label:'Firmware STREAM_BEGIN handler',path:'firmware/tx/tx.ino',lines:'219-242'}]},
  observe:{title:'Progress and acknowledgements',body:'The host waits for TX_STREAM_BEGIN_OK after STREAM_BEGIN, then sends STREAM_DATA blocks with byte offsets and uppercase hexadecimal payloads. Each block must be acknowledged by TX_STREAM_DATA_OK before the controller advances its progress status.',note:'A missing acknowledgement causes the controller to stop and report a transfer failure rather than silently pretending the data was loaded.',sources:[{label:'Host-side block transfer and status',path:'application-source/gui_dev_v3/serial/controllers.py',lines:'358-380'},{label:'Firmware block parser and ACK',path:'firmware/tx/tx.ino',lines:'244-256'}]}
 },
 frame: {
  user:{title:'No extra click is needed',body:'After the file has been preloaded, the controller sends STREAM_START. The user does not manually create protocol frames; the firmware constructs them from the received file buffer and transfer metadata.',note:'This is where the operation changes from host-to-board file loading to optical transmission.',sources:[{label:'Host sends STREAM_START and waits for completion',path:'application-source/gui_dev_v3/serial/controllers.py',lines:'377-430'}]},
  application:{title:'The application tracks the send phase',body:'The serial controller publishes statuses such as Preparing, Preloading, Sending, and Send complete. These status callbacks update the TX application state and dashboard; they are progress indicators, not a byte-for-byte optical capture.',note:'The desktop application coordinates and reports the transfer. Frame assembly and symbol output happen in the ESP32 firmware.',sources:[{label:'TX controller status updates',path:'application-source/gui_dev_v3/serial/controllers.py',lines:'326-430'},{label:'TX dashboard panels',path:'application-source/gui_dev_v3/tx/dashboard.py',lines:'640-715'}]},
  serial:{title:'STREAM_START is the trigger',body:'The host sends the line STREAM_START after the data blocks have been acknowledged. The TX firmware command loop dispatches that command to handleStreamStart(). The host then waits for TX_STREAM_DONE to confirm the optical round completed.',note:'The file bytes have already been loaded into the TX ESP32 buffer; STREAM_START tells the board to begin emitting frames.',sources:[{label:'STREAM_START host sequence',path:'application-source/gui_dev_v3/serial/controllers.py',lines:'377-430'},{label:'Firmware command dispatch',path:'firmware/tx/tx.ino',lines:'291-324'}]},
  hardware:{title:'The firmware creates protocol frames',body:'handleStreamStart() checks that the entire file is loaded and that its file CRC matches. It sends a transfer-notice frame, then loops through chunk indexes, calculates each payload length, builds the frame, and calls sendOpticalFrame(). buildFrame() writes SOF, version, frame type, transfer ID, file size, chunk counts, chunk index, payload length, file CRC, chunk CRC, filename and payload, then appends frame CRC.',note:'Frame construction happens before line coding: the complete frame bytes are then serialized into the optical bitstream.',sources:[{label:'TX frame builder',path:'firmware/tx/tx.ino',lines:'182-200',lesson:'tx-frame'},{label:'TX stream-to-frame loop',path:'firmware/tx/tx.ino',lines:'259-278'}]},
  observe:{title:'What the reader should see',body:'The TX dashboard changes to a sending state and reports progress, elapsed time, and data rate. The protocol frame itself is an internal firmware structure; the application does not display every field as a live packet capture.',note:'Use the frame-field lesson to inspect the actual byte layout. Do not confuse a dashboard animation with a captured frame.',sources:[{label:'Frame format specification',path:'firmware/specs/protocol_spec.md'}]}
 },
 coding: {
  user:{title:'The user does not encode bytes manually',body:'The user only chooses a file and starts transmission. The firmware performs line coding automatically for every frame byte.',note:'4B5B is a protocol implementation detail hidden behind the normal application workflow.',sources:[{label:'TX byte encoder',path:'firmware/tx/tx.ino',lines:'160-163',lesson:'tx-encode'}]},
  application:{title:'The Python app does not run the 4B5B lookup',body:'The Python controller sends the file and transfer commands to the board. The 4B5B lookup and symbol timing are implemented in the TX firmware, keeping the time-critical optical output close to the GPIO.',note:'This boundary is useful when reading the repository: Python prepares and supervises; embedded C++ produces the timed signal.',sources:[{label:'Serial controller STREAM path',path:'application-source/gui_dev_v3/serial/controllers.py',lines:'326-380'},{label:'Firmware 4B5B encoder',path:'firmware/tx/tx.ino',lines:'147-168',lesson:'tx-encode'}]},
  serial:{title:'USB is no longer carrying each optical symbol',body:'After STREAM_START, the ESP32 emits the frame over the LED output. USB serial remains the control/status channel for commands and completion notices; the encoded optical payload travels through the light path.',note:'The USB cable and the optical path have different jobs.',sources:[{label:'Firmware command parser',path:'firmware/tx/tx.ino',lines:'291-324'}]},
  hardware:{title:'One byte becomes ten encoded bits',body:'send4b5bEncodedByte() extracts the high nibble with a right shift and the low nibble with a mask. Each nibble indexes CODE_4B5B and produces one five-bit codeword. For 0xA5, the firmware table yields 10110 01011.',note:'4B5B adds one coded bit per nibble. It is not encryption and it does not repair corrupted bits.',sources:[{label:'4B5B byte encoder',path:'firmware/tx/tx.ino',lines:'160-163',lesson:'tx-encode'},{label:'Bit and codeword output',path:'firmware/tx/tx.ino',lines:'147-158',lesson:'tx-bit'}]},
  observe:{title:'How to read the model',body:'The animation shows the relationship between an eight-bit byte and its two five-bit codewords. It is a source-derived teaching example, not a recorded transmission trace.',note:'Pause on the two nibbles, then open the code lesson and follow the shift, mask, lookup, and send calls.',sources:[{label:'TX 4B5B lookup and encoder',path:'firmware/tx/tx.ino',lines:'160-163',lesson:'tx-encode'}]}
 },
 light: {
  user:{title:'The person sees the LED as the transmitter',body:'No extra GUI action is needed once STREAM_START has begun. The commercial LED bulb remains the optical source; the receiver must have a usable line of sight to it.',note:'The room light can look steady to a person while its intensity is being modulated rapidly.',sources:[{label:'TX firmware pin and idle configuration',path:'firmware/tx/tx.ino',lines:'1-15'}]},
  application:{title:'The TX app reports progress, not photons',body:'The dashboard receives progress/status updates from the serial controller. It can show a logical waveform-style animation, but that display is not a photodiode measurement or a physical logic-analyzer capture.',note:'The current DigitalBitstreamWidget generates a deterministic teaching pattern from file size. Label it illustrative in the application atlas.',sources:[{label:'TX dashboard and bitstream widget',path:'application-source/gui_dev_v3/tx/dashboard.py',lines:'418-560'}]},
  serial:{title:'The serial cable is not the optical channel',body:'USB serial is used to configure and preload the TX ESP32. During the optical round, the information-bearing symbols are output on TX GPIO5 and carried by the LED light. The host receives completion status separately.',note:'Keep the control path and data path visually distinct.',sources:[{label:'TX serial controller',path:'application-source/gui_dev_v3/serial/controllers.py',lines:'326-430'}]},
  hardware:{title:'GPIO5 controls the LED driver',body:'The TX firmware defines TX_PIN as GPIO5. send4b5bBit() chooses the electrical level for a logical bit using the configured active-low/active-high mapping, writes the pin, and waits for the symbol boundary. The external transistor/MOSFET driver switches the 12 V LED load.',note:'The logical bit is not identical to a GPIO HIGH level: active-low driver configuration can invert the electrical polarity.',sources:[{label:'TX pin and modulation settings',path:'firmware/tx/tx.ino',lines:'1-15'},{label:'Bit output and symbol timing',path:'firmware/tx/tx.ino',lines:'147-179',lesson:'tx-bit'}]},
  observe:{title:'What is physically observable',body:'The LED is the visible transmitter. A photodiode at the receiver converts its intensity changes into current. The Academy beam animation is conceptual and should not be interpreted as a measured beam profile or received optical power.',note:'The experiment’s actual distances, alignment, and results belong in the hardware and validation lessons.',sources:[{label:'Hardware and protocol reference',path:'firmware/README.md'}]}
 },
 detect: {
  user:{title:'The RX unit must be aligned with the LED',body:'The user positions the receiver so its photodiode can see the transmitter. The RX application does not need the user to choose an incoming filename before it can listen for optical data.',note:'Alignment and the analog signal level are physical conditions, not GUI file-selection settings.',sources:[{label:'RX pin definitions',path:'firmware/rx/rx.ino',lines:'1-20'}]},
  application:{title:'RX opens a physical serial reader',body:'The RX physical backend identifies the receiver firmware, opens the serial port at its configured RX baud rate, and starts a background reader thread. The app polls the backend for current transfer and signal state.',note:'This serial connection is between the RX ESP32 and the RX desktop app; it is separate from the optical path between the two boards.',sources:[{label:'RX physical serial reader',path:'application-source/gui_dev_v3/rx/backends/physical.py',lines:'190-297'}]},
  serial:{title:'RX serial carries telemetry and completed data',body:'The RX firmware sends link-quality telemetry, transfer notices, chunk-store progress, and eventually a completed-file HEX record. The RX desktop reads these lines from USB serial; the optical payload itself arrives at the photodiode first.',note:'The receiver serial line is an output/telemetry path from RX ESP32 to its desktop application.',sources:[{label:'RX line dispatch',path:'application-source/gui_dev_v3/rx/backends/physical.py',lines:'255-297'}]},
  hardware:{title:'The analog front end turns light into logic',body:'The BPW34 converts light into photocurrent. The OPA2604 transimpedance amplifier converts that current into a voltage. The LM393 compares the conditioned signal against Vref and produces the digital edge sampled by RX GPIO5. GPIO34 monitors PVo, GPIO35 monitors Vref, and GPIO25 adjusts the comparator reference through PWM.',note:'The circuit drawing and voltage traces are explanatory unless the page explicitly identifies a saved hardware measurement.',sources:[{label:'RX GPIO and monitor pins',path:'firmware/rx/rx.ino',lines:'10-17'},{label:'RX signal and Vref state',path:'application-source/gui_dev_v3/rx/backends/physical.py',lines:'909-920'}]},
  observe:{title:'What the RX app can show',body:'The RX dashboard combines reception status, CRC status, PVo/Vref/margin monitor values, an OOK waveform panel, decode information, received-file details, and activity logs. The Signal page expands the live monitoring and historical trend views.',note:'Only label PVo/Vref/margin as live telemetry when they came from a connected device; a conceptual waveform is not a measured trace.',sources:[{label:'RX dashboard panels and refresh',path:'application-source/gui_dev_v3/rx/dashboard.py',lines:'309-405'},{label:'RX signal monitor',path:'application-source/gui_dev_v3/rx/signal_page.py',lines:'1-70'}]}
 },
 decode: {
  user:{title:'The receiver works without a receive-file dialog',body:'Once powered and connected, the RX ESP32 continuously watches its comparator input for the optical start transition. The user waits for the incoming transfer; selecting a destination or a filename is not how the firmware starts decoding.',note:'The user-facing action is to monitor the RX dashboard, not to manually initiate each optical frame.',sources:[{label:'RX start-edge and symbol sampling',path:'firmware/rx/rx.ino',lines:'744-804'}]},
  application:{title:'The app receives firmware events',body:'The RX physical backend dispatches RX_TRANSFER_NOTICE and RX_RAM_STORE events into transfer progress/log state. RX_FILE_HEX is handled immediately by the file-receive path after the firmware has reconstructed the whole file.',note:'The application is not doing the real-time 4B5B symbol decoding; that work happens on the RX ESP32.',sources:[{label:'RX physical line dispatch',path:'application-source/gui_dev_v3/rx/backends/physical.py',lines:'270-297'},{label:'RX notice and chunk progress',path:'application-source/gui_dev_v3/rx/backends/physical.py',lines:'299-354'}]},
  serial:{title:'Firmware output messages',body:'During reception, the firmware can emit RX_TRANSFER_NOTICE when it sees a transfer-notice frame and RX_RAM_STORE after a verified chunk is stored. When all chunks are present and the whole-file CRC passes, it emits RX_FILE_HEX with transfer metadata and the reconstructed bytes.',note:'RX_FILE_HEX is emitted only after the firmware’s whole-file CRC succeeds.',sources:[{label:'RX frame validation and chunk storage',path:'firmware/rx/rx.ino',lines:'907-942'},{label:'Whole-file CRC and file output',path:'firmware/rx/rx.ino',lines:'874-882'}]},
  hardware:{title:'Sampling, synchronization, decoding',body:'The firmware waits for stable idle, detects the start edge, samples around each symbol centre, and can take three readings for majority voting. It searches for the preamble and 0xD5B7 sync word, aligns to the encoded SOF, decodes two 5-bit words into one byte, and rejects invalid codewords.',note:'At 15 ksymbols/s a symbol is about 66.7 μs. The three-sample majority rule is a timing/noise robustness technique, not forward error correction.',sources:[{label:'RX majority sampling',path:'firmware/rx/rx.ino',lines:'761-771',lesson:'rx-majority'},{label:'RX sync acquisition',path:'firmware/rx/rx.ino',lines:'773-804'},{label:'RX 4B5B decoder',path:'firmware/rx/rx.ino',lines:'840-854',lesson:'rx-decode'}]},
  observe:{title:'What to look for',body:'The RX dashboard shows transfer progress and signal diagnostics. Firmware sync events, received chunk counts, and CRC outcomes can be surfaced in the activity log. A missing sync, invalid codeword, or CRC mismatch indicates a different failure stage.',note:'Use the failure stage to narrow troubleshooting: no signal, no sync, invalid coding, bad frame/chunk CRC, or incomplete whole-file reconstruction.',sources:[{label:'RX dashboard refresh',path:'application-source/gui_dev_v3/rx/dashboard.py',lines:'309-405'},{label:'RX firmware decoder and CRC',path:'firmware/rx/rx.ino',lines:'840-942'}]}
 },
 verify: {
  user:{title:'After reception, the user inspects the result',body:'The RX application listens automatically; it does not ask the user to select the incoming file. After a completed transfer appears, open Inspect, examine the chunk health map and byte explorer, and optionally press Load Reference to choose the original source file. Then open BER Analyzer to compare the reconstructed bytes against that reference.',note:'The “file selection” on RX is usually selecting the original reference file for BER analysis—not selecting the incoming optical transfer.',sources:[{label:'Inspect page and Load Reference control',path:'application-source/gui_dev_v3/rx/inspect_page.py',lines:'329-370'},{label:'Load original reference into app state',path:'application-source/gui_dev_v3/rx/inspect_page.py',lines:'435-445'}]},
  application:{title:'RX backend decodes and saves the completed file',body:'The physical RX backend parses the RX_FILE_HEX record, decodes the filename and file bytes from hexadecimal, recalculates CRC-16, and writes the reconstructed bytes to the configured capture directory. It then creates a completed transfer record for the RX UI.',note:'The firmware has already reconstructed the file and checked whole-file CRC. The desktop backend performs its own parse/CRC check before saving.',sources:[{label:'RX_FILE_HEX parser and CRC',path:'application-source/gui_dev_v3/rx/backends/physical.py',lines:'356-383',lesson:'rx-app'},{label:'RX transfer record creation',path:'application-source/gui_dev_v3/rx/backends/physical.py',lines:'430-455'}]},
  serial:{title:'The completed file crosses RX USB serial',body:'The RX ESP32 prints RX_FILE_HEX with transfer ID, frame type, total size, chunk count, file CRC, filename hex, and file-data hex. The desktop receiver reads that line from its serial reader thread and dispatches it to the save handler.',note:'This is the final ESP32-to-PC handoff. It is not another optical transmission.',sources:[{label:'Firmware RX_FILE_HEX output',path:'firmware/rx/rx.ino',lines:'874-882'},{label:'RX backend dispatch',path:'application-source/gui_dev_v3/rx/backends/physical.py',lines:'270-297'}]},
  hardware:{title:'Integrity checks have different scopes',body:'The firmware validates frame CRC and chunk CRC before storing each payload. Once every chunk is present, it calculates the whole-file CRC before emitting RX_FILE_HEX. BER is a separate application-side comparison that requires the original expected file (or a recognized BERTEST pattern).',note:'CRC PASS alone does not establish a measured BER of 0.00%. The BER Analyzer must compare received bytes with the intended reference bytes.',sources:[{label:'Frame and chunk CRC validation',path:'firmware/rx/rx.ino',lines:'907-942',lesson:'rx-crc'},{label:'Whole-file CRC before output',path:'firmware/rx/rx.ino',lines:'874-882'}]},
  observe:{title:'Inspect, compare, then export',body:'Inspect shows the transfer snapshot, reference-file status, chunk health map, chunk details, and byte explorer. BER Analyzer compares the expected bytes with the reconstructed received bytes and reports overlap BER, strict BER, bit errors, bit accuracy, and size difference. Export/history is a later step and should be taught with its own data-provenance notes.',note:'A valid CRC proves the checked bytes match the CRC value carried by the transfer; BER comparison tests the received payload against the separately loaded original file.',sources:[{label:'Inspect chunk and byte explorer',path:'application-source/gui_dev_v3/rx/inspect_page.py',lines:'329-490'},{label:'BER reference comparison',path:'application-source/gui_dev_v3/rx/ber_analyzer_page.py',lines:'97-150',lesson:'rx-ber'}]}
 }
};

function StageTraceDetails({stage,onOpenCode}) {
 const [layer,setLayer] = useState('user');
 React.useEffect(()=>setLayer('user'),[stage.id]);
 const detail = stageTrace[stage.id]?.[layer];
 const labels = [{id:'user',label:'USER ACTION'},{id:'application',label:'APPLICATION'},{id:'serial',label:'USB SERIAL'},{id:'hardware',label:'FIRMWARE / HARDWARE'},{id:'observe',label:'WHAT YOU SEE'}];
 if (!detail) return null;
 return <section className="stage-trace" aria-label="Cross-layer implementation trace">
  <div className="trace-heading"><div><span className="eyebrow">FOLLOW THE SAME EVENT THROUGH THE SYSTEM</span><h4>Five connected layers</h4></div><span className="trace-revision">SOURCE · {FW.slice(0,8)}</span></div>
  <div className="trace-tabs" role="tablist" aria-label="Implementation layers">
   {labels.map(item=><button key={item.id} role="tab" aria-selected={layer===item.id} className={layer===item.id?'active':''} onClick={()=>setLayer(item.id)}>{item.label}</button>)}
  </div>
  <AnimatePresence mode="wait">
   <motion.div key={stage.id+'-'+layer} className="trace-detail" initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-5}} transition={{duration:.16}}>
    <div className="trace-copy"><span className="trace-layer-index">{String(labels.findIndex(x=>x.id===layer)+1).padStart(2,'0')} / 05</span><h5>{detail.title}</h5><p>{detail.body}</p><div className="trace-note"><Lightbulb size={15}/><span>{detail.note}</span></div></div>
    <div className="trace-sources"><span className="eyebrow">SOURCE LOCATIONS</span>
     {detail.sources.map((source,i)=><div className="trace-source" key={source.path+'-'+i}><div><b>{source.label}</b><code>{source.path.split('/').slice(-1)[0]}{source.lines?' · L'+source.lines.replace('-','–L'):''}</code></div><div className="trace-source-actions"><a href={link(source.path,FW,source.lines||'')} target="_blank" rel="noreferrer">OPEN SOURCE <ArrowUpRight size={12}/></a>{source.lesson&&<button onClick={()=>onOpenCode(source.lesson)}><Code2 size={12}/> LINE LESSON</button>}</div></div>)}
    </div>
   </motion.div>
  </AnimatePresence>
 </section>
}

const codeLessons = [
 {id:'tx-state',level:'APPLICATION',name:'TX application state',path:'application-source/gui_dev_v3/tx_app_state.py',ref:APP,range:'29-41',lang:'python',summary:'This dataclass defines the values used by the transmitter workspace: selected-file metadata, chunk configuration, encoding, modulation, and display state. These fields describe the job; they do not transmit the file by themselves.',lines:[
  ['    settings: AppSettings = field(default_factory=load_settings)','Create settings from the persisted configuration when a state object is made.'],
    ['    filename: str = "No file"','Keep a clear empty state before the user chooses a file.'],
  ['    filetype: str = ""','Store the selected file type separately from its filename.'],
  ['    file_size_bytes: int = 0','Store the selected file size in bytes.'],
  ['    total_chunks: int = 0','Track how many protocol chunks are needed.'],
  ['    chunk_size: int = 256','Set the current default chunk payload size.'],
  ['    encoding: str = "4B5B"','Expose the line-coding choice used by this application state.'],
  ['    modulation: str = "NRZ / OOK"','Describe the optical modulation configuration.'],
  ['    symbol_rate: str = "15,000 sym/s"','Represent the configured symbol rate.'],
  ['    led_pin: int = 5','Record the transmitter GPIO assignment.'],
  ['    tx_power: str = "100 %"','Store the configured TX power label.'],
  ['    pre_emphasis: str = "Disabled"','Store whether pre-emphasis is enabled.'],
  ['    status_text: str = "Offline — no hardware"','Start honestly: a default state does not mean a board is connected.']
 ],concept:'A dataclass field declaration gives the state object a named piece of data and, often, an initial value. These fields are not the transmission itself; UI actions and controller methods consume them.'},
 {id:'serial-start',level:'APPLICATION',name:'Begin a serial transfer',path:'application-source/gui_dev_v3/serial/controllers.py',ref:APP,range:'338-356',lang:'python',summary:'This exact excerpt constructs STREAM_BEGIN, updates the transfer status, clears old firmware state, sends the command, and waits for the TX firmware acknowledgement.',lines:[
  ['        begin = (','Start a parenthesized multi-line command string.'],
  ['            f"STREAM_BEGIN:{tid}:1:{len(data)}:{chunk_size}"','Build the first command segment. The f-string inserts the transfer ID, file length, and chunk size.'],
  ['            f":{file_crc:04X}:1:{name_bytes.hex().upper()}"','Append the file CRC as hexadecimal and the filename bytes as uppercase hex.'],
  ['        )','Finish assembling the command.'],
  ['        tot_c = max(1, (len(data) + chunk_size - 1) // chunk_size)','Compute the number of chunks using integer ceiling division, with at least one chunk.'],
  ['        self.status(','Begin a UI/status update.'],
  ['            "Preparing", path.name,','Set the status label and selected filename.'],
  ['            percent=0, state="active",','Report zero percent and an active transfer state.'],
  ['            file_name=path.name, size=len(data), tid=tid,','Attach filename, byte size, and transfer ID to the status event.'],
  ['            chunk=0, total_chunks=tot_c,','Initialize progress at chunk zero and include the total chunk count.'],
  ['        )','Finish the status call.'],
  ['        self.send_line("STREAM_CLEAR")','Ask the transmitter firmware to clear any previous stream state.'],
  ['','Blank line separates preparation from the handshake.'],
  ['        si = self.line_counter','Remember the current received-line counter before waiting for a new acknowledgement.'],
  ['        if not self.send_line(begin):','Write STREAM_BEGIN to the serial connection; test whether the write succeeded.'],
  ['            return False','Stop immediately if the command could not be sent.'],
  ['        if not self.wait_for_line_containing("TX_STREAM_BEGIN_OK", 5.0, si):','Wait up to five seconds for the expected firmware acknowledgement after the saved line index.'],
  ['            self.status("Send failed", "TX did not acknowledge STREAM_BEGIN", state="error")','Publish a clear failure state if the firmware does not acknowledge.'],
  ['            return False','Do not continue into data transmission after a failed handshake.']
 ],concept:'The host and firmware use a small command protocol over USB serial. This is the control-plane handshake that prepares the physical transmitter; it is not the optical data transmission itself.'},
 {id:'tx-encode',level:'FIRMWARE · TX',name:'Encode one byte as 4B5B',path:'firmware/tx/tx.ino',ref:FW,range:'160-163',lang:'cpp',summary:'This tiny function is a good first example of bit manipulation. It separates a byte into two nibbles and looks up the 5-bit representation of each.',lines:[
  ['void send4b5bEncodedByte(uint8_t value) {','Define a function that receives one unsigned 8-bit value and returns no value.'],
  ['  send4b5bCode(CODE_4B5B[(value >> 4) & 0x0F]);','Shift the high nibble down, mask to four bits, look up its codeword, then send five bits.'],
  ['  send4b5bCode(CODE_4B5B[value & 0x0F]);','Mask the low nibble, look up its codeword, then send five bits.'],
  ['}','End the function.']
 ],concept:'For 0xA5, the high nibble is 0xA and the low nibble is 0x5. In this firmware table they map to 10110 and 01011. The result is ten transmitted bits for one original byte.'},
 {id:'tx-bit',level:'FIRMWARE · TX',name:'Put one bit on the LED driver',path:'firmware/tx/tx.ino',ref:FW,range:'147-150',lang:'cpp',summary:'This is the boundary between a logical bit and a physical GPIO level. The helper applies the configured line polarity, then waits for the symbol boundary.',lines:[
  ['void send4b5bBit(bool bitValue) {','Accept one logical bit as true or false.'],
  ['  digitalWrite(TX_PIN, bitValue ? lineOneLevel() : lineZeroLevel());','Choose the electrical output level for logical one or zero, including active-low configuration.'],
  ['  waitSymbolBoundary();','Hold the symbol for its configured timing interval.'],
  ['}','End the helper.']
 ],concept:'Logical 1 does not universally mean GPIO HIGH. The driver can be active-low. Keeping logical bit meaning separate from electrical pin polarity prevents the encoder from needing to know the transistor circuit details.'},
 {id:'tx-frame',level:'FIRMWARE · TX',name:'Build a protocol frame',path:'firmware/tx/tx.ino',ref:FW,range:'182-201',lang:'cpp',summary:'This is the exact 20-line frame builder. Select each line to see how metadata and payload bytes are placed in the buffer and how the CRC is appended.',lines:[
  ['size_t buildFrame(uint8_t frameType, uint16_t chunkIndex, const uint8_t *payload, uint16_t payloadLen) {','Define a function returning the number of bytes written. It receives frame metadata and a pointer to the payload.'],
  ['  uint16_t chunkCrc = crc16_ccitt(payload, payloadLen);','Calculate a CRC for this payload chunk before assembling the frame.'],
  ['  size_t pos = 0;','Start writing at offset zero in the frame buffer.'],
  ['  frameBuf[pos++] = SOF_BYTE;','Write the start-of-frame marker, then increment pos.'],
  ['  frameBuf[pos++] = VERSION_BYTE;','Write the protocol version.'],
  ['  frameBuf[pos++] = frameType;','Write the frame type, such as notice or data.'],
  ['  putU16(frameBuf, pos, streamTid);','Serialize the transfer ID as a 16-bit field.'],
  ['  putU32(frameBuf, pos, streamTotalSize);','Serialize the complete file size as a 32-bit field.'],
  ['  putU16(frameBuf, pos, streamTotalChunks);','Write how many chunks belong to this transfer.'],
  ['  putU16(frameBuf, pos, chunkIndex);','Write this frame’s chunk index.'],
  ['  putU16(frameBuf, pos, payloadLen);','Write the number of payload bytes carried in this frame.'],
  ['  putU16(frameBuf, pos, streamFileCrc);','Include the CRC expected for the complete original file.'],
  ['  putU16(frameBuf, pos, chunkCrc);','Include the CRC calculated for this individual chunk.'],
  ['  frameBuf[pos++] = streamNameLen;','Write the filename length before the filename bytes.'],
  ['  for (size_t i = 0; i < streamNameLen; i++) frameBuf[pos++] = streamNameBuf[i];','Copy the filename into the frame one byte at a time.'],
  ['  for (size_t i = 0; i < payloadLen; i++) frameBuf[pos++] = payload[i];','Copy the payload bytes after the filename.'],
  ['  uint16_t frameCrc = crc16_ccitt(frameBuf, pos);','Calculate a CRC over all frame bytes written so far.'],
  ['  putU16(frameBuf, pos, frameCrc);','Append the frame CRC after the payload.'],
  ['  return pos;','Return the total number of bytes in the completed frame.'],
  ['}','End the function.']
 ],concept:'The sender and receiver must agree on the exact field order and sizes. Frame CRC protects the assembled frame; chunk CRC protects the payload; file CRC later checks the reconstructed file.'},
 {id:'rx-majority',level:'FIRMWARE · RX',name:'Read a symbol with majority voting',path:'firmware/rx/rx.ino',ref:FW,range:'761-771',lang:'cpp',summary:'Instead of trusting one digital read, this helper can take three readings around the expected symbol centre and choose the majority value.',lines:[
  ['bool sampleRawAt(uint32_t sampleTimeUs) {','Return one recovered raw bit for a target time in microseconds.'],
  ['  if (!useMajoritySampling || symbolUs < 30) { waitUntil(sampleTimeUs); return digitalRead(RX_PIN); }','Use a single read if majority mode is off or the symbol is too short for this sampling pattern.'],
  ['  uint32_t delta = symbolUs / 6;','Place the outer samples one-sixth of a symbol period before and after the centre.'],
  ['  waitUntil(sampleTimeUs - delta);','Wait until the first sample instant.'],
  ['  bool a = digitalRead(RX_PIN);','Read the comparator output.'],
  ['  waitUntil(sampleTimeUs);','Wait for the centre sample.'],
  ['  bool b = digitalRead(RX_PIN);','Read the second sample.'],
  ['  waitUntil(sampleTimeUs + delta);','Wait for the third sample instant.'],
  ['  bool c = digitalRead(RX_PIN);','Read the third sample.'],
  ['  return (a + b + c) >= 2;','Return true when at least two of the three readings are HIGH.'],
  ['}','End the function.']
 ],concept:'At 15 ksymbols/s, one symbol lasts about 66.7 microseconds. The three samples are close together around the centre, where the receiver expects the symbol to be stable.'},
 {id:'rx-decode',level:'FIRMWARE · RX',name:'Decode two codewords into one byte',path:'firmware/rx/rx.ino',ref:FW,range:'840-854',lang:'cpp',summary:'This exact excerpt checks synchronization and frame alignment, reads two 5-bit codewords, rejects invalid values, and combines two nibbles into a byte.',lines:[
  ['bool read4b5bByte(uint8_t &value) {','Return true or false, and write the decoded byte through the reference parameter value.'],
  ['  if (!lineSynced && !acquire4b5bSync()) return false;','If the line is not synchronized, try to acquire sync. Stop if acquisition fails.'],
  ['  if (!frameAligned) return alignToEncodedSof(value);','Before payload decoding, align the stream to the encoded start-of-frame marker.'],
  ['  uint8_t highCode = 0, lowCode = 0;','Create storage for the high-nibble and low-nibble 5-bit codewords.'],
  ['  if (!read5b(highCode) || !read5b(lowCode)) return false;','Read both 5-bit groups. The logical OR short-circuits if the first read fails.'],
  ['  int8_t highNibble = DECODE_4B5B[highCode & 0x1F];','Mask to five bits and use the reverse lookup table to decode the high nibble.'],
  ['  int8_t lowNibble = DECODE_4B5B[lowCode & 0x1F];','Decode the low nibble with the same lookup table.'],
  ['  if (highNibble < 0 || lowNibble < 0) {','A negative lookup result means at least one codeword is invalid.'],
  ['    invalidCodeCount++;','Increment the diagnostic counter for invalid codewords.'],
  ['    resetLineDecoder();','Reset line-decoder state because the stream can no longer be trusted as aligned.'],
  ['    return false;','Report that no valid byte was produced.'],
  ['  }','Close the invalid-codeword condition.'],
  ['  value = (uint8_t)((highNibble << 4) | lowNibble);','Shift the high nibble into the upper four bits and combine it with the low nibble using bitwise OR.'],
  ['  return true;','Report successful decoding of one byte.'],
  ['}','End the function.']
 ],concept:'For the input byte 0xA5, the high nibble 0xA maps to 10110 and the low nibble 0x5 maps to 01011. The receiver reverses those two lookups and combines them.'},
 {id:'rx-crc',level:'FIRMWARE · RX',name:'Validate a complete frame',path:'firmware/rx/rx.ino',ref:FW,range:'907-942',lang:'cpp',summary:'A 36-line excerpt of the receiver validation path. It checks minimum size, frame CRC, metadata, payload boundaries, chunk CRC, and only then accepts the verified chunk.',lines:[
  ['void processCompleteFrame() {','Process a frame after the line decoder has assembled its bytes.'],
  ['  if (framePos < 1 + 19 + 2) { resetLineDecoder(); return; }','Reject a frame too short to contain the minimum fields and trailing CRC.'],
  ['  uint16_t rxFrameCrc = getU16(frameBuf, framePos - 2);','Read the received frame CRC from the final two bytes.'],
  ['  uint16_t calcFrameCrc = crc16_ccitt(frameBuf, framePos - 2);','Recalculate the CRC over all preceding frame bytes.'],
  ['  if (rxFrameCrc != calcFrameCrc) { crcFailCount++; resetLineDecoder(); return; }','Reject the frame and count a CRC failure if the received and calculated values differ.'],
  ['',''],
  ['  uint8_t version = frameBuf[1];','Read the protocol version field.'],
  ['  uint8_t frameType = frameBuf[2];','Read the frame type.'],
  ['  uint16_t tid = getU16(frameBuf, 3);','Decode the transfer ID.'],
  ['  uint32_t totalSize = getU32(frameBuf, 5);','Decode the complete file size.'],
  ['  uint16_t totalChunks = getU16(frameBuf, 9);','Decode the expected number of chunks.'],
  ['  uint16_t chunkIndex = getU16(frameBuf, 11);','Decode this chunk’s index.'],
  ['  uint16_t chunkLen = getU16(frameBuf, 13);','Decode the payload length for this frame.'],
  ['  uint16_t fileCrc = getU16(frameBuf, 15);','Read the expected whole-file CRC carried in the header.'],
  ['  uint16_t rxChunkCrc = getU16(frameBuf, 17);','Read the received chunk CRC.'],
  ['  uint8_t nameLen = frameBuf[19];','Read the filename length.'],
  ['  if (version != VERSION_BYTE || nameLen > MAX_NAME_BYTES || chunkLen > MAX_PAYLOAD_BYTES || chunkIndex >= totalChunks) { resetLineDecoder(); return; }','Reject unsupported versions and metadata outside allowed bounds.'],
  ['  size_t nameStart = 20;','The filename starts immediately after the fixed header.'],
  ['  size_t payloadStart = nameStart + nameLen;','The payload begins after the variable-length filename.'],
  ['  if (payloadStart + chunkLen + 2 != framePos) { resetLineDecoder(); return; }','Check that filename, payload, and trailing CRC exactly match the assembled frame length.'],
  ['  uint16_t calcChunkCrc = crc16_ccitt(frameBuf + payloadStart, chunkLen);','Calculate a CRC over the payload bytes only.'],
  ['  if (rxChunkCrc != calcChunkCrc) { crcFailCount++; resetLineDecoder(); return; }','Reject the chunk if its payload CRC does not match.'],
  ['  crcOkCount++;','Count a frame/chunk that passed the preceding integrity checks.'],
  ['  if (isRecentlyCompletedTransfer(tid, frameType, totalSize, totalChunks, fileCrc, nameLen, frameBuf + nameStart)) {','Detect a duplicate frame belonging to a recently completed transfer.'],
  ['    if (reportChunks) { Serial.print("RX_DUPLICATE_FRAME_SKIP:"); Serial.println(tid); }','Optionally report that the duplicate is being skipped.'],
  ['    resetLineDecoder();','Reset per-frame decoder state.'],
  ['    return;','Do not process a duplicate again.'],
  ['  }','Close the duplicate-transfer condition.'],
  ['  if (frameType == FRAME_TYPE_NOTICE) {','Handle a transfer-notice frame separately from payload data.'],
  ['    Serial.print("RX_TRANSFER_NOTICE:"); Serial.print(tid); Serial.print(":"); Serial.print(totalSize); Serial.print(":"); Serial.print(totalChunks); Serial.print(":"); Serial.print(fileCrc, HEX); Serial.print(":"); printHexBytes(frameBuf + nameStart, nameLen); Serial.println();','Send the transfer metadata to the desktop over serial.'],
  ['    resetLineDecoder();','Reset the frame decoder after processing the notice.'],
  ['    return;','A notice contains metadata, not a data chunk to buffer.'],
  ['  }','Close the notice-frame condition.'],
  ['  bufferVerifiedChunk(tid, frameType, totalSize, totalChunks, chunkIndex, chunkLen, fileCrc, nameLen, frameBuf + nameStart, frameBuf + payloadStart);','Pass verified metadata and payload bytes to the chunk reassembly buffer.'],
  ['  resetLineDecoder();','Reset decoder state so the next frame can be acquired.'],
  ['}','End the function.']
 ],concept:'The validation order matters: first trust the frame boundary and frame CRC, then validate metadata and payload length, then check the chunk CRC. Only verified data reaches bufferVerifiedChunk().'},

];


codeLessons.push(
 {id:'app-launch',level:'APPLICATION',name:'Choose the TX console in the launcher',path:'application-source/gui_dev_v3/app.py',ref:APP,range:'256-262',lang:'python',summary:'The launcher builds the Transmitter Console card and connects its click signal to the main window. This is the first UI event in the TX journey.',lines:[
  ['        tx_card = _ConsoleCard(','Create the transmitter console card shown on the launcher.'],
  ['            \"Transmitter Console\",','Set the card title.'],
  ['            \"Configure payloads, set symbol rates, and stream\\\\nvisible light data from your TX hardware.\",','Provide the short description shown to the reader.'],
  ['            \"fa5s.broadcast-tower\",','Choose the icon used by the card.'],
  ['            \"Launch TX\",','Set the action label displayed on the card.'],
  ['        )','Finish creating the card.'],
  ['        tx_card.clicked.connect(lambda: self._main_window.launch_mode(\"tx\"))','Connect the card click to the main window method that creates or opens the TX workspace.']
 ],concept:'A GUI signal connects a user action to a function. The click does not start a transmission; it opens the TX console. File selection and Start happen later on the Dashboard.'},
 {id:'console-launch',level:'APPLICATION',name:'Create the TX application workspace',path:'application-source/gui_dev_v3/app.py',ref:APP,range:'321-338',lang:'python',summary:'The main window receives the launcher request, initializes the TX state and shell when needed, then makes the TX workspace visible.',lines:[
  ['    def launch_mode(self, mode: str) -> None:','Define the method that opens either the transmitter or receiver console.'],
  ['        from gui_dev_v3.logger import reinit_logger','Import the logger initializer for the selected application mode.'],
  ['        if mode == \"tx\":','Choose the transmitter branch when the launcher passes the string tx.'],
  ['            if self._tx_shell is None:','Create the TX workspace only the first time it is opened.'],
  ['                reinit_logger(\"tx\")','Switch the application logger to TX context.'],
  ['                self._tx_state = build_default_tx_state()','Create the TX application state object.'],
  ['                self._tx_shell = TXShell(self._tx_state)','Create the TX navigation shell and pass it the state object.'],
  ['                self._stack.addWidget(self._tx_shell)','Add the new TX shell to the stacked main-window pages.'],
  ['            self._stack.setCurrentWidget(self._tx_shell)','Show the TX workspace.'],
  ['            self.setWindowTitle(\"VLC Transmitter\")','Update the window title to identify the active console.'],
  ['        elif mode == \"rx\":','Choose the receiver branch when the launcher passes rx.'],
  ['            if self._rx_shell is None:','Create the RX workspace only when it has not already been initialized.'],
  ['                reinit_logger(\"rx\")','Switch the logger to RX context.'],
  ['                self._rx_state = build_default_state()','Create the RX application state object.'],
  ['                self._rx_shell = RXShell(self._rx_state)','Create the RX navigation shell with its state object.'],
  ['                self._stack.addWidget(self._rx_shell)','Add the RX shell to the main window stack.'],
  ['            self._stack.setCurrentWidget(self._rx_shell)','Show the RX workspace.'],
  ['            self.setWindowTitle(\"VLC Receiver\")','Update the window title to identify the receiver console.']
 ],concept:'The launcher card emits a click signal, launch_mode() chooses a console, and the main window creates a state object plus a navigation shell. None of these steps has started an optical transfer yet.'},
 {id:'tx-select',level:'APPLICATION',name:'Select a file in TX Dashboard',path:'application-source/gui_dev_v3/tx/dashboard.py',ref:APP,range:'719-730',lang:'python',summary:'This is the start of the real dashboard file-selection handler. It opens the file picker, validates the path, and stores the first pieces of file metadata.',lines:[
  ['    def _on_select_file_clicked(self) -> None:','Define the event handler called when the user presses Select File.'],
  ['        from PySide6.QtWidgets import QFileDialog','Import Qt’s native file-dialog widget.'],
  ['        from gui_dev_v3.logger import file_log','Import the application logger used to record the user action.'],
  ['        filepath, _ = QFileDialog.getOpenFileName(self, \"Select File to Transmit\", \"\", \"All Files (*)\")','Open a file picker and return the chosen path. The second returned value is the selected filter and is ignored.'],
  ['        if filepath:','Continue only if the user selected a path rather than cancelling.'],
  ['            from pathlib import Path','Import pathlib for filesystem path handling.'],
  ['            p = Path(filepath)','Wrap the selected string path in a Path object.'],
  ['            if p.exists():','Do not update the UI for a path that no longer exists.'],
  ['                self._state.filename = p.name','Store only the final filename for display.'],
  ['                self._state.filetype = p.suffix.upper()[1:] + \" File\"','Derive a display label from the file extension.'],
  ['                self._state.file_size_bytes = p.stat().st_size','Read the actual file size from filesystem metadata.'],
  ['                self._state.total_chunks = max(1, (self._state.file_size_bytes + self._state.chunk_size - 1) // self._state.chunk_size)','Estimate the number of chunks using ceiling division by the configured chunk size.']
 ],concept:'This handler prepares the UI state. It does not send the file. The complete method also calculates an estimated duration, stores the pending path, logs the selection, and refreshes the dashboard.'},
 {id:'tx-start',level:'APPLICATION',name:'Start the selected TX file',path:'application-source/gui_dev_v3/tx/dashboard.py',ref:APP,range:'754-766',lang:'python',summary:'The Start button retrieves the pending path and delegates the job to TXAppState. If no path is pending, it asks the user to select a file first.',lines:[
  ['    def _on_start_clicked(self) -> None:','Define the handler connected to the Dashboard Start button.'],
  ['        from gui_dev_v3.logger import file_log','Import the application event logger.'],
  ['        from pathlib import Path','Import Path so the selected filename can be written to the log.'],
  ['        filepath = getattr(self, \"_pending_filepath\", None)','Read the path saved by the file-selection handler; use None if it has not been set.'],
  ['        if filepath:','Continue directly if a file is already selected.'],
  ['            file_log(\"TX\", \"User Action\", f\"Clicked Start Transmission for {Path(filepath).name}\")','Record the user action and selected filename.'],
  ['            self._state.start_transmission(filepath)','Hand the file path to the application state; the state/backend/controller layers take over.'],
  ['        else:','Handle the case where Start was pressed before selecting a file.'],
  ['            self._on_select_file_clicked()','Open the same file-selection workflow instead of attempting to send an empty path.'],
  ['            filepath = getattr(self, \"_pending_filepath\", None)','Read the path again after the file dialog returns.'],
  ['            if filepath:','Only start if the user actually selected a file.'],
  ['                file_log(\"TX\", \"User Action\", f\"Clicked Start Transmission for {Path(filepath).name}\")','Record the confirmed Start action.'],
  ['                self._state.start_transmission(filepath)','Delegate to TXAppState, which selects the physical backend in the physical prototype path.']
 ],concept:'The button handler does not contain the serial protocol. It hands the selected path to TXAppState. This separation keeps the GUI event handler small and moves hardware work into the backend/controller.'},
 {id:'rx-app',level:'APPLICATION',name:'Receive and save the completed RX file',path:'application-source/gui_dev_v3/rx/backends/physical.py',ref:APP,range:'356-383',lang:'python',summary:'The RX physical backend receives a completed RX_FILE_HEX line, extracts the transfer metadata and file bytes, verifies CRC-16, and prepares to save the reconstructed file.',lines:[
  ['    def _handle_file_hex(self, line: str) -> None:','Define the handler for the completed-file serial record from RX firmware.'],
  ['        \"\"\"Decode and save a completed file from RX_FILE_HEX line.','The docstring explains that this method decodes the completed file and saves it.'],
  ['','This blank line separates the summary from the wire-format description.'],
  ['        Format: RX_FILE_HEX:<tid>:<frame_type>:<total_size>:<total_chunks>:<crc_hex>:<name_hex>:<data_hex>','The serial record contains transfer metadata, filename bytes, and the complete file bytes.'],
  ['        \"\"\"','End the docstring.'],
  ['        now = time.strftime(\"%H:%M:%S\")','Capture a timestamp for the RX activity log.'],
  ['        try:','Start guarded parsing so malformed serial data does not crash the reader thread.'],
  ['            parts = line.split(\":\")','Split the record into colon-separated fields.'],
  ['            if len(parts) < 8:','Reject a record that does not contain all eight expected fields.'],
  ['                self._log_queue.append({\"time\": now, \"event\": \"RX File\", \"details\": \"Malformed RX_FILE_HEX (too few fields)\"})','Add a diagnostic event for the malformed record.'],
  ['                return','Stop processing the invalid line.'],
  ['','Separate the malformed-record guard from the field extraction.'],
  ['            tid = int(parts[1])','Parse the transfer ID.'],
  ['            total_size = int(parts[3])','Parse the expected total file size.'],
  ['            crc_expected_hex = parts[5]','Read the expected whole-file CRC from the record.'],
  ['            name_hex = parts[6]','Read the filename encoded as hexadecimal bytes.'],
  ['            data_hex = parts[7]','Read the reconstructed file bytes encoded as hexadecimal.'],
  ['','Separate the raw fields from the decoding step.'],
  ['            filename = bytes.fromhex(name_hex).decode(\"utf-8\", errors=\"replace\") if name_hex else f\"rx_{tid}.bin\"','Decode the filename, with a fallback name if no name was supplied.'],
  ['            file_bytes = bytes.fromhex(data_hex)','Convert the hex payload back into the original byte sequence.'],
  ['','Separate decoding from integrity validation.'],
  ['            # Verify CRC16-CCITT','The desktop backend independently verifies the reconstructed bytes.'],
  ['            calc_crc = crc16_ccitt(file_bytes)','Calculate CRC-16/CCITT over the received file bytes.'],
  ['            expected_crc = int(crc_expected_hex, 16)','Convert the expected CRC text into an integer.'],
  ['            crc_ok = (calc_crc == expected_crc)','Compare the calculated CRC with the expected value.'],
  ['','Separate the integrity result from persistence.'],
  ['            # Save to disk','The backend is ready to persist the completed file.'],
  ['            self._save_dir.mkdir(parents=True, exist_ok=True)','Create the capture directory if it does not already exist.']
 ],concept:'The RX ESP32 has already reconstructed the file and checked its whole-file CRC before emitting RX_FILE_HEX. The desktop backend decodes that line, performs another CRC check, and saves the bytes for the user.'},
 {id:'rx-ber',level:'APPLICATION',name:'Compare the received file with a reference',path:'application-source/gui_dev_v3/rx/ber_analyzer_page.py',ref:APP,range:'129-138',lang:'python',summary:'This is the actual Method 2 comparison point. The application compares received bytes against the expected reference bytes and displays BER and accuracy results.',lines:[
  ['        # Perform bit comparison if expected_bytes exists','Do not calculate reference-file BER until expected bytes are available.'],
  ['        if expected_bytes:','Only enter the comparison when a reference file or supported generated reference exists.'],
  ['            res = compare_payload_bits(expected_bytes, received_bytes, mismatch_limit=50)','Compare expected and received payload bytes and request a limited mismatch preview.'],
  ['            # Update labels','The next values are presented in the BER Analyzer UI.'],
  [`            self.lbl_compared.setText(f\"{res['overlap_bytes']} / {res['expected_bytes']} B\")`,'Show how many bytes overlap, relative to the expected file size.'],
  ['            self.lbl_bit_errors.setText(str(res[\"strict_bit_errors\"]))','Show the strict bit-error count.'],
  [`            self.lbl_ber.setText(f\"{res['overlap_ber'] * 100:.6f} %\")`,'Show BER over the overlapping compared region.'],
  [`            self.lbl_strict_ber.setText(f\"{res['strict_ber'] * 100:.6f} %\")`,'Show strict BER, which also accounts for length differences.'],
  [`            self.lbl_accuracy.setText(f\"{res['bit_accuracy'] * 100:.4f} %\")`,'Show bit accuracy derived from the comparison.'],
  ['            delta = res[\"length_delta\"]','Read the difference in file length so missing or extra bytes can be reported.']
 ],concept:'CRC and BER answer different questions. CRC checks data against a transmitted checksum. Method 2 BER compares the reconstructed bytes with a separately loaded original reference file.'}
);

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


function SignalJourney({onOpenCode}){
 const [index,setIndex]=useState(0); const [playing,setPlaying]=useState(false); const stage=stages[index];
 React.useEffect(()=>{if(!playing)return;const id=setInterval(()=>setIndex(v=>(v+1)%stages.length),3800);return()=>clearInterval(id)},[playing]);
 return <section className="journey-section" id="journey"><div className="section-kicker">THE COMPLETE USER-TO-HARDWARE FLOW <span>08 STAGES · 05 LAYERS</span></div><div className="section-title-row"><div><p className="eyebrow">FROM A FILE TO LIGHT AND BACK</p><h2>Follow one transfer.<br/><i>All the way through.</i></h2></div><p className="section-intro">Start with a real user action in the TX or RX application, then follow its consequences through Python state, USB serial, ESP32 firmware, the optical hardware, and the result shown back in the GUI.</p></div>
  <div className="journey-layout"><aside className="stage-rail">{stages.map((s,i)=><button key={s.id+i} className={index===i?'active':''} onClick={()=>{setIndex(i);setPlaying(false)}}><span>{String(i+1).padStart(2,'0')}</span><b>{s.label}</b><i/></button>)}</aside><div className="journey-content"><StageVisual stage={stage}/><div className="journey-explain"><div className="eyebrow">{stage.eyebrow}</div><h3>{stage.title}</h3><p>{stage.copy}</p><div className="stage-connection"><Cable size={15}/><span>{stage.detail}</span></div><div className="stage-actions"><button onClick={()=>setIndex(v=>Math.max(0,v-1))} disabled={index===0}><ArrowLeft size={15}/> PREVIOUS</button><button className="journey-play" onClick={()=>setPlaying(v=>!v)}>{playing?'PAUSE':'AUTO PLAY'} <Activity size={14}/></button><button className="open-code-stage" onClick={()=>onOpenCode(stage.codeLesson)}><Code2 size={14}/> OPEN RELATED CODE</button><button className="next-stage" onClick={()=>{setIndex(v=>(v+1)%stages.length);setPlaying(false)}}>NEXT STAGE <ArrowRight size={15}/></button></div></div><StageTraceDetails stage={stage} onOpenCode={onOpenCode}/></div></div>
 </section>
}

function PathCards({onOpen}){return <section className="paths-section" id="learn"><div className="section-kicker">YOUR LEARNING ROUTE <span>01—06</span></div><div className="section-title-row"><div><p className="eyebrow">BUILT FOR CURIOUS BEGINNERS</p><h2>Learn it in layers.<br/><i>Build real understanding.</i></h2></div><p className="section-intro">Short lessons, clear prerequisites, interactive models, and practical checks. Take your time—each path prepares you for the next.</p></div><div className="path-grid">{paths.map((p,i)=><motion.button key={p.id} className={'path-card path-'+p.id} onClick={()=>onOpen(p.id)} whileHover={{y:-6}} whileTap={{scale:.99}}><div className="path-card-top"><span>{p.number} / 06</span><span>{p.duration}</span></div><div className="path-icon">{[<Lightbulb/>,<CircuitBoard/>,<Radio/>,<Cpu/>,<Code2/>,<ShieldCheck/>][i]}</div><h3>{p.title}</h3><p>{p.desc}</p><div className="path-card-bottom"><span>{p.items.length} LESSONS</span><ArrowUpRight size={18}/></div></motion.button>)}</div></section>}

function highlightLine(source){
 const pattern=/(\/\/.*|#.*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:const|let|var|return|if|else|for|while|switch|case|break|continue|class|def|async|await|import|from|as|try|except|with|True|False|None|true|false|null|static|void|bool|int|uint8_t|uint16_t|uint32_t|size_t|auto|struct|enum|namespace|using|new|delete|this|self)\b|\b\d+(?:\.\d+)?\b)/g;
 return source.split(pattern).filter(Boolean).map((part,i)=>{
  let type='plain';
  if(/^(\/\/|#)/.test(part))type='comment';
  else if(/^("|')/.test(part))type='string';
  else if(/^\d/.test(part))type='number';
  else if(/^(const|let|var|return|if|else|for|while|switch|case|break|continue|class|def|async|await|import|from|as|try|except|with|True|False|None|true|false|null|static|void|bool|int|uint8_t|uint16_t|uint32_t|size_t|auto|struct|enum|namespace|using|new|delete|this|self)$/.test(part))type='keyword';
  else if(/^[A-Za-z_][A-Za-z0-9_]*(?=\()/.test(part))type='function';
  return <span className={'token-'+type} key={i}>{part}</span>;
 });
}

function CodeLesson({lesson,selected,onSelect}){
 const [line,setLine]=useState(0); const [showAll,setShowAll]=useState(false);
 React.useEffect(()=>{setLine(0);setShowAll(false)},[lesson.id]);
 const source=link(lesson.path,lesson.ref,lesson.range);
 return <article className="code-lesson">
  <div className="code-lesson-head"><div><span className="eyebrow">{lesson.level}</span><h3>{lesson.name}</h3><p>{lesson.summary}</p></div><a href={source} target="_blank" rel="noreferrer">SOURCE LINES <ArrowUpRight size={14}/></a></div>
  <div className="code-editor"><div className="editor-bar"><span><i/> {lesson.path.split('/').slice(-1)[0]}</span><span>{lesson.lang.toUpperCase()} · L{lesson.range.replace('-', '–')}</span></div><div className="editor-code">{lesson.lines.map(([code,explain],i)=><button key={i} className={'editor-line '+(line===i?'chosen':'')} onClick={()=>setLine(i)}><span className="line-no">{Number(lesson.range.split('-')[0])+i}</span><code>{highlightLine(code)}</code></button>)}</div><div className="editor-explain"><span>LINE EXPLAINER · {line+1}/{lesson.lines.length}</span><p>{lesson.lines[line][1]}</p><div><button disabled={line===0} onClick={()=>setLine(v=>v-1)}><ArrowLeft size={13}/> PREVIOUS LINE</button><button disabled={line===lesson.lines.length-1} onClick={()=>setLine(v=>v+1)}>NEXT LINE <ArrowRight size={13}/></button></div></div></div>
  <div className="code-concept"><Sparkles size={17}/><div><b>THE BIG IDEA</b><p>{lesson.concept}</p></div></div>
 </article>
}

const sourceFiles = [
 {group:'FIRMWARE',name:'tx/tx.ino',path:'firmware/tx/tx.ino',ref:FW,role:'Transmitter firmware',desc:'Serial command handling, stream validation, frame construction, 4B5B encoding, symbol timing, and GPIO5 optical output.'},
 {group:'FIRMWARE',name:'rx/rx.ino',path:'firmware/rx/rx.ino',ref:FW,role:'Receiver firmware',desc:'Comparator sampling, symbol timing, preamble/sync acquisition, 4B5B decoding, frame parsing, CRC checks, chunk storage, and file output.'},
 {group:'FIRMWARE',name:'specs/protocol_spec.md',path:'firmware/specs/protocol_spec.md',ref:FW,role:'Shared protocol contract',desc:'Defines the frame fields, transfer identifiers, chunk structure, CRC coverage, and transmission sequence shared by both endpoints.'},
 {group:'TX APPLICATION',name:'tx_app_state.py',path:'application-source/gui_dev_v3/tx_app_state.py',ref:APP,role:'TX application state',desc:'Holds the transmitter console state, selected file information, and physical transfer configuration.'},
 {group:'TX APPLICATION',name:'tx/backends/physical.py',path:'application-source/gui_dev_v3/tx/backends/physical.py',ref:APP,role:'Physical TX backend',desc:'Connects the desktop transmitter workspace to real TX firmware over USB serial and publishes physical-backend snapshots.'},
 {group:'TX APPLICATION',name:'tx/shell.py',path:'application-source/gui_dev_v3/tx/shell.py',ref:APP,role:'TX workspace shell',desc:'Builds the transmitter window navigation and coordinates its pages and refresh cycle.'},
 {group:'TX APPLICATION',name:'tx/dashboard.py',path:'application-source/gui_dev_v3/tx/dashboard.py',ref:APP,role:'TX dashboard',desc:'Presents selected-file information, link settings, start controls, progress, and transmitter status.'},
 {group:'SHARED APPLICATION',name:'app.py',path:'application-source/gui_dev_v3/app.py',ref:APP,role:'Desktop application entry',desc:'Creates the Qt application and launches the transmitter or receiver console.'},
 {group:'SHARED APPLICATION',name:'serial/controllers.py',path:'application-source/gui_dev_v3/serial/controllers.py',ref:APP,role:'Serial transfer controller',desc:'Builds firmware commands, performs the STREAM handshake, preloads data blocks, and interprets serial acknowledgements.'},
 {group:'SHARED APPLICATION',name:'serial/session.py',path:'application-source/gui_dev_v3/serial/session.py',ref:APP,role:'Serial session foundation',desc:'Owns the serial connection lifecycle, reader thread, line handling, command writes, and response waiting.'},
 {group:'SHARED APPLICATION',name:'serial/detection.py',path:'application-source/gui_dev_v3/serial/detection.py',ref:APP,role:'Hardware discovery',desc:'Enumerates serial ports and identifies compatible TX or RX firmware before a physical connection is opened.'},
 {group:'SHARED APPLICATION',name:'models.py',path:'application-source/gui_dev_v3/models.py',ref:APP,role:'Shared data models',desc:'Defines typed records and snapshots exchanged between application state, backends, and UI pages.'},
 {group:'RX APPLICATION',name:'rx/backends/physical.py',path:'application-source/gui_dev_v3/rx/backends/physical.py',ref:APP,role:'Physical RX backend',desc:'Communicates with real RX firmware, reads status and signal telemetry, receives transfer output, and exposes receiver snapshots.'},
 {group:'RX APPLICATION',name:'rx/shell.py',path:'application-source/gui_dev_v3/rx/shell.py',ref:APP,role:'RX workspace shell',desc:'Builds the receiver workspace and routes navigation between receiver pages.'},
 {group:'RX APPLICATION',name:'rx/receive_page.py',path:'application-source/gui_dev_v3/rx/receive_page.py',ref:APP,role:'Receive workspace',desc:'Presents receiver transfer activity and the files emitted by the physical receiver backend.'},
 {group:'TX APPLICATION',name:'tx/file_manager_page.py',path:'application-source/gui_dev_v3/tx/file_manager_page.py',ref:APP,role:'TX file manager',desc:'Browses files, calculates file metadata and CRC, and adds selected files to the transmit queue. This is distinct from Dashboard direct Start.'},
 {group:'TX APPLICATION',name:'tx/settings.py',path:'application-source/gui_dev_v3/tx/settings.py',ref:APP,role:'TX settings',desc:'Builds the transmitter settings categories and connects setting controls to persistence and firmware application.'},
 {group:'RX APPLICATION',name:'rx/dashboard.py',path:'application-source/gui_dev_v3/rx/dashboard.py',ref:APP,role:'RX dashboard',desc:'Combines reception status, CRC metrics, signal monitoring, waveform, bit-decode information, received-file details, and activity log.'},
 {group:'RX APPLICATION',name:'rx/signal_page.py',path:'application-source/gui_dev_v3/rx/signal_page.py',ref:APP,role:'RX signal monitor',desc:'Presents PVo, Vref, margin, waveform, diagnostics, historical trends, transfer statistics, and signal-quality views.'},
 {group:'RX APPLICATION',name:'rx/inspect_page.py',path:'application-source/gui_dev_v3/rx/inspect_page.py',ref:APP,role:'RX transfer inspector',desc:'Displays transfer snapshots, reference-file status, chunk health, chunk details, and byte-level inspection.'},
 {group:'RX APPLICATION',name:'rx/ber_analyzer_page.py',path:'application-source/gui_dev_v3/rx/ber_analyzer_page.py',ref:APP,role:'RX BER analyzer',desc:'Compares reconstructed bytes against a loaded reference file and reports overlap BER, strict BER, bit errors, accuracy, and size difference.'},
 {group:'RX APPLICATION',name:'rx/settings.py',path:'application-source/gui_dev_v3/rx/settings.py',ref:APP,role:'RX settings',desc:'Builds receiver settings for connection, signal monitoring, Vref control, experiments, database, and display behavior.'},
 {group:'RX APPLICATION',name:'rx/export_page.py',path:'application-source/gui_dev_v3/rx/export_page.py',ref:APP,role:'RX history and export',desc:'Provides session/history inspection and export workflows for stored receiver records and captures.'},
 {group:'RX APPLICATION',name:'logic/ber_bridge.py',path:'application-source/gui_dev_v3/logic/ber_bridge.py',ref:APP,role:'BER integration',desc:'Connects transfer data to the application’s BER analysis path. Method 2 compares the reconstructed file with its original reference.'}
];
const sourceGroups=['FIRMWARE','TX APPLICATION','RX APPLICATION','SHARED APPLICATION'];
function SourceMap(){
 const [group,setGroup]=useState('FIRMWARE');
 const visible=sourceFiles.filter(f=>f.group===group);
 return <section className="source-map-section"><div className="source-map-heading"><div><span className="eyebrow">EXPLORE THE REPOSITORY</span><h3>Know where each responsibility lives.</h3><p>These are the core firmware and desktop-application files from the same audited OpenVLC-Public main snapshot. Open any file at its immutable commit.</p></div><a href={REPO} target="_blank" rel="noreferrer">FULL REPOSITORY <ArrowUpRight size={14}/></a></div>
  <div className="source-map-tabs">{sourceGroups.map(g=><button key={g} className={group===g?'active':''} onClick={()=>setGroup(g)}>{g}</button>)}</div>
  <div className="source-file-grid"><AnimatePresence mode="wait"><motion.div key={group} className="source-file-grid-inner" initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-5}} transition={{duration:.18}}>{visible.map(file=><a className="source-file-card" key={file.path} href={link(file.path,file.ref)} target="_blank" rel="noreferrer"><div><FileCode2 size={16}/><span>{file.group}</span><ArrowUpRight size={13}/></div><code>{file.name}</code><b>{file.role}</b><p>{file.desc}</p></a>)}</motion.div></AnimatePresence></div>
  <div className="call-sequence"><div className="eyebrow">HOW THE RESPONSIBILITIES CONNECT</div><div className="call-sequence-row"><span>TX desktop app</span><ChevronRight/><span>Physical TX backend</span><ChevronRight/><span>USB serial controller</span><ChevronRight/><span>TX firmware</span></div><div className="call-sequence-row optical"><span>Frame builder</span><ChevronRight/><span>4B5B encoder</span><ChevronRight/><span>GPIO symbol output</span><ChevronRight/><span>LED driver + light</span></div><div className="call-sequence-row receive"><span>Photodiode + comparator</span><ChevronRight/><span>RX firmware decoder</span><ChevronRight/><span>Physical RX backend</span><ChevronRight/><span>RX desktop app</span></div><p>This is the system responsibility flow. The detailed lessons will progressively document exact direct function-call edges, arguments, return values, and state changes.</p></div>
 </section>
}

function CodeStudio({initialLesson}){
 const [active,setActive]=useState(initialLesson||'tx-encode');
 React.useEffect(()=>{if(initialLesson)setActive(initialLesson)},[initialLesson]); const [query,setQuery]=useState(''); const selected=codeLessons.find(x=>x.id===active)||codeLessons[0];
 const groups=['APPLICATION','FIRMWARE · TX','FIRMWARE · RX'];
 const filtered=useMemo(()=>codeLessons.filter(x=>(x.name+' '+x.path+' '+x.level).toLowerCase().includes(query.toLowerCase())),[query]);
 return <section className="code-studio" id="code"><div className="section-kicker">SOURCE CODE STUDIO <span>REAL FILES · PINNED LINES</span></div><div className="section-title-row"><div><p className="eyebrow">FROM SURFACE KNOWLEDGE TO CODE CONFIDENCE</p><h2>Understand the code.<br/><i>One line at a time.</i></h2></div><p className="section-intro">Select a source lesson, tap any line, and read what it does. Each example is pinned to a commit so the code and line numbers stay traceable.</p></div>
 <div className="studio-layout"><aside className="studio-sidebar"><label className="studio-search"><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Find a function or file"/></label>{groups.map(g=><div className="file-group" key={g}><span>{g}</span>{filtered.filter(x=>x.level===g).map(x=><button key={x.id} className={active===x.id?'active':''} onClick={()=>setActive(x.id)}><FileCode2 size={14}/><span>{x.name}</span><ChevronRight size={13}/></button>)}</div>)}</aside><div className="studio-main"><CodeLesson lesson={selected}/></div></div><SourceMap/>
 </section>
}

const topicNotes = {
 start:[
  {title:'What visible-light communication means',body:'Visible-light communication sends information by changing the intensity of a light source quickly enough for a receiver to detect the changes. The LED is both an illumination source and a communication transmitter; the receiver turns the changing light into an electrical signal.',focus:'Keep the distinction clear: the light carries the encoded data, while the desktop application prepares and interprets the file.',try:'Explain why a normal room light can look steady to a person while still changing quickly enough to carry data.'},
  {title:'The physical TX and RX assemblies',body:'The transmitter side uses an ESP32 to control an LED driver and a 12 V commercial LED bulb. The receiver side uses a BPW34 photodiode, an OPA2604 transimpedance amplifier, an LM393 comparator, and a second ESP32.',focus:'Think in two halves: TX converts digital data into controlled light; RX converts received light back into digital logic.',try:'Trace the chain out loud from TX GPIO5 to the RX ESP32 GPIO5.'},
  {title:'The room-scale optical link',body:'The experiment uses a line-of-sight optical path between the ceiling-mounted LED and the receiver assembly. The received optical level depends on geometry and alignment, so distance and horizontal offset are part of the physical setup—not merely software settings.',focus:'A diagram is a model of the geometry. It is not a substitute for measured experiment results.',try:'If the vertical separation is h and the horizontal offset is x, write the straight-line distance as d = √(h² + x²).'},
  {title:'What the experiment measured',body:'The project evaluates a working physical prototype. Transfer outcomes, integrity checks, transmission time, and test conditions must be read from the thesis results and original logs. The Academy must never turn an illustrative animation into a claimed measurement.',focus:'CRC pass/fail, reference-file BER, and optical-link performance are different observations. Keep each metric tied to its measurement method.',try:'Find one result table in the thesis and identify the original file, received file, and metric used to judge the transfer.'}
 ],
 hardware:[
  {title:'ESP32 transmitter and LED driver',body:'The TX ESP32 generates the timed digital symbol stream. GPIO5 controls the active-low driver stage using a 2N3904 and IRF540N arrangement, which switches the 12 V LED load.',focus:'The firmware expresses logical bits; the transistor stage converts the GPIO control into the electrical switching needed by the LED.',try:'Explain why an active-low driver can make a logical one correspond to a LOW GPIO level.'},
  {title:'12 V LED and optical path',body:'The commercial LED bulb is the optical transmitter. The firmware changes its output using intensity modulation, with the idle state configured so the lamp remains illuminated between transmissions.',focus:'The LED is not connected directly to the ESP32 GPIO. The driver stage handles the lamp load.',try:'Draw the path from ESP32 pin to transistor driver to 12 V LED, then draw the light path to the receiver.'},
  {title:'BPW34 and OPA2604 transimpedance amplifier',body:'The BPW34 photodiode produces photocurrent when light reaches its active area. The OPA2604 transimpedance amplifier converts that small current into a voltage that can be conditioned by the receiver circuit.',focus:'A photodiode front end is analog circuitry. It does not directly output the decoded file or a clean digital bitstream.',try:'Describe the difference between photocurrent and the voltage produced by a transimpedance amplifier.'},
  {title:'LM393 comparator and receiver GPIO',body:'The LM393 compares the conditioned signal against an adjustable reference. Its output provides a digital transition that the RX ESP32 samples on GPIO5. Separate analog monitoring inputs observe PVo and Vref.',focus:'The comparator threshold determines how the analog waveform becomes a digital HIGH/LOW signal. The firmware then performs timing and decoding.',try:'Explain what may happen if the comparator threshold is set too high or too low.'}
 ],
 protocol:[
  {title:'Binary, bits, bytes, and nibbles',body:'A bit is one binary digit. Eight bits form a byte. A nibble is four bits, so every byte can be separated into a high nibble and a low nibble. The encoder and decoder use this split to apply the 4B5B lookup table.',focus:'The high nibble is extracted with a right shift; the low nibble is isolated with a bit mask.',try:'Split 0xA5 into its two nibbles and write each nibble in binary.'},
  {title:'4B5B line coding',body:'4B5B maps each 4-bit nibble to a defined 5-bit codeword. One source byte therefore becomes two codewords, or ten encoded bits. The mapping is a lookup table—not arithmetic encryption.',focus:'The RX table is the inverse of the TX table. Invalid 5-bit patterns are rejected rather than guessed.',try:'For 0xA5, look up nibble A and nibble 5 in the actual firmware table. Confirm the output is 10110 01011.'},
  {title:'NRZ/OOK modulation',body:'The encoded bitstream controls on/off keying of the LED using a non-return-to-zero symbol representation. The physical driver polarity can be active-low even though the protocol still reasons about logical zero and one.',focus:'Do not confuse a logical bit, a GPIO voltage level, and whether the LED is illuminated. The driver configuration connects those layers.',try:'Explain why changing activeLowDriver should not require changing the 4B5B lookup table.'},
  {title:'Synchronization, frame fields, and CRC',body:'A receiver needs a recognizable preamble and synchronization word before it can trust byte boundaries. Frames then carry metadata and payload. Frame CRC checks the frame, chunk CRC checks a payload chunk, and whole-file CRC checks the reconstructed file.',focus:'These checks protect different scopes. A CRC is an integrity check, not a correction mechanism and not the same as BER.',try:'Predict which CRC should fail if one payload byte changes but the frame header stays intact.'}
 ],
 software:[
  {title:'TX application state and serial controller',body:'The desktop TX application stores the selected file, transfer settings, and UI state. Its serial controller performs the host-to-board command handshake and sends data blocks over USB serial.',focus:'The GUI coordinates the transfer; the ESP32 firmware performs the timed optical output.',try:'Find the STREAM_BEGIN command builder in the serial controller and identify the transfer ID, file length, and chunk size fields.'},
  {title:'TX firmware command and stream path',body:'The TX firmware receives serial commands, validates the loaded stream, builds protocol frames, and passes each frame to the optical transmission functions. The stream loop calls buildFrame() and sendOpticalFrame().',focus:'Follow the call chain from the serial command handler into handleStreamStart(), then down to frame construction and bit output.',try:'Open the TX firmware and find where handleStreamStart() calls sendOpticalFrame().' },
  {title:'RX sampling and decoder pipeline',body:'The RX firmware waits for a stable idle state, acquires the preamble and sync word, samples the comparator output, decodes 4B5B bytes, aligns to frames, and validates received data.',focus:'Each function has a narrow responsibility. Sampling recovers raw bits; decoding turns codewords into bytes; frame processing checks structured data.',try:'Compare sampleRawAt() with read4b5bByte(). What does each function return, and what kind of input does it consume?'},
  {title:'RX application and file reconstruction',body:'The desktop RX application reads serial status and received-file output from the receiver ESP32. It handles completed transfers, stores the received file, and supports reference-file comparison for Method 2 BER.',focus:'The firmware validates optical frames and chunks; the desktop application manages the received file and comparison workflow.',try:'Explain why a successful chunk CRC alone does not prove the entire reconstructed file matches the original.'}
 ],
 code:[
  {title:'Variables, types, arrays, and pointers',body:'A variable stores a value with a type. The firmware uses fixed-width integer types such as uint8_t and uint16_t because protocol fields have defined bit widths. Arrays hold bytes; pointers refer to memory locations; references let a function write a result back to its caller.',focus:'In buildFrame(), payload is a pointer to bytes and payloadLen tells the function how many bytes may be read.',try:'In the buildFrame() signature, identify the return type, the pointer parameter, and the payload length parameter.'},
  {title:'Conditions, loops, and bitwise operators',body:'Conditions choose which path runs. Loops repeat operations over bits or bytes. Bitwise operators work on individual bits: >> shifts, & masks, and | combines bit fields. Logical operators such as && and || combine true/false expressions.',focus:'The expression (value >> 4) & 0x0F extracts the high nibble. The expression value & 0x0F extracts the low nibble.',try:'Calculate 0xA5 >> 4, then apply & 0x0F. Repeat using 0xA5 & 0x0F.'},
  {title:'Function calls and data flow',body:'A function receives arguments, performs one job, and may return a value or update an output parameter. To understand a program, trace who calls a function, what values it passes, what the function changes, and who consumes the result.',focus:'read4b5bByte() calls read5b() twice, looks up two nibbles, and writes the combined byte through uint8_t &value.',try:'Trace one byte from send4b5bEncodedByte() on TX to read4b5bByte() on RX. List each conversion.'},
  {title:'Debugging and safe code changes',body:'A useful debugging change begins with a hypothesis, a small controlled edit, and a test that can fail if the behavior is wrong. Preserve protocol compatibility: changing field order, timing, or encoding on only one endpoint can break communication.',focus:'Use logs and counters to distinguish serial setup failures, synchronization failures, invalid codewords, CRC failures, and file reconstruction failures.',try:'Imagine changing the TX codeword for nibble A but leaving the RX decode table unchanged. Predict the result and explain why.'}
 ],
 practice:[
  {title:'Predict the encoded bits',body:'Take a byte, split it into nibbles, look up both 5-bit codewords, and join them in transmission order. The goal is to predict the output before looking at the encoder result.',focus:'Use the actual CODE_4B5B table from the pinned TX firmware, not a generic example table.',try:'Encode 0xA5 and write the ten-bit result.'},
  {title:'Trace a received byte',body:'Start at the comparator output and follow the RX functions: sample the signal, recover raw bits, acquire synchronization, read two 5-bit groups, validate each lookup, and combine the nibbles.',focus:'A raw comparator sample is not yet a byte. The receiver must know symbol timing and alignment first.',try:'Explain what the receiver does when one of the 5-bit values maps to a negative DECODE_4B5B entry.'},
  {title:'Find a CRC validation bug',body:'Read the frame validation order and ask what data is trusted at each point. A safe receiver checks frame boundaries and integrity before accepting metadata and payload bytes.',focus:'Never pass unverified payload into the chunk reassembly buffer.',try:'What would be unsafe about calling bufferVerifiedChunk() before checking rxChunkCrc?'},
  {title:'Complete the knowledge check',body:'Use the small quizzes to test concepts from the earlier paths. A good answer should include not just the correct choice, but the reason the other choices are wrong.',focus:'Explain the behavior in your own words. Memorizing a label is not the same as understanding the implementation.',try:'Try the sampling question below, then revisit the code lesson if the reasoning is unclear.'}
 ]
};

function PathDetail({id,onBack}){
 const path=paths.find(x=>x.id===id)||paths[0];
 const topics=topicNotes[id]||topicNotes.start;
 const [active,setActive]=useState(0);
 const [done,setDone]=useState([]);
 const topic=topics[active];
 return <section className="path-detail">
  <button className="back-link" onClick={onBack}><ArrowLeft size={15}/> ALL LEARNING PATHS</button>
  <div className="path-detail-hero"><span className="eyebrow">LEARNING PATH {path.number} · {path.duration}</span><h2>{path.title}</h2><p>{path.desc}</p><div className="path-progress"><span style={{width:(done.length/topics.length*100)+'%'}}/></div><small>{done.length} OF {topics.length} LESSONS COMPLETED</small></div>
  <div className="path-learning-layout">
   <aside className="path-detail-list">{path.items.map((item,i)=><button key={item} onClick={()=>setActive(i)} className={active===i?'selected':''}><span>{done.includes(i)?<Check size={15}/>:String(i+1).padStart(2,'0')}</span><b>{item}</b><ChevronRight size={15}/></button>)}</aside>
   <article className="focused-lesson"><div className="eyebrow">LESSON {String(active+1).padStart(2,'0')} / {String(topics.length).padStart(2,'0')}</div><h3>{topic.title}</h3><p>{topic.body}</p><div className="lesson-focus"><Lightbulb size={17}/><div><b>WHAT TO REMEMBER</b><p>{topic.focus}</p></div></div><div className="lesson-try"><span>TRY IT YOURSELF</span><p>{topic.try}</p></div><div className="focused-actions"><button onClick={()=>setActive(v=>Math.max(0,v-1))} disabled={active===0}><ArrowLeft size={14}/> PREVIOUS</button><button className="mark-done" onClick={()=>setDone(v=>v.includes(active)?v.filter(x=>x!==active):[...v,active])}>{done.includes(active)?'MARK AS UNFINISHED':'MARK LESSON COMPLETE'} <Check size={14}/></button><button onClick={()=>setActive(v=>Math.min(topics.length-1,v+1))} disabled={active===topics.length-1}>NEXT <ArrowRight size={14}/></button></div></article>
  </div>
 </section>
}

function QuizPreview(){const [answer,setAnswer]=useState('');const [checked,setChecked]=useState(false);return <div className="quiz-card"><div className="eyebrow">QUICK KNOWLEDGE CHECK</div><h3>Why does the receiver take three samples?</h3><div className="quiz-options">{[{v:'a',t:'To triple the data rate'},{v:'b',t:'To reduce the effect of a noisy or unstable single reading'},{v:'c',t:'To calculate the file CRC'}].map(o=><button key={o.v} className={answer===o.v?'selected':''} onClick={()=>{setAnswer(o.v);setChecked(false)}}><i>{o.v.toUpperCase()}</i>{o.t}</button>)}</div><button className="quiz-submit" disabled={!answer} onClick={()=>setChecked(true)}>CHECK ANSWER <ArrowRight size={14}/></button>{checked&&<p className={answer==='b'?'correct':'incorrect'}>{answer==='b'?'Correct. Majority voting accepts the value seen by at least two of the three samples.':'Not quite. Think about what can happen when one sample lands near a noisy edge.'}</p>}</div>}

function HomePage({navigate}){
 return <>
  <section className="academy-hero" id="home"><div className="hero-copy"><div className="hero-eyebrow"><i/> AN INTERACTIVE ENGINEERING COURSE</div><h1>Data carried<br/>by <em>light.</em></h1><p>Learn how a real ESP32 visible-light communication prototype works—from the LED driver and photodiode to the firmware and desktop code that make it communicate.</p><div className="hero-buttons"><button className="hero-primary" onClick={()=>navigate('paths')}>START LEARNING <ArrowRight size={16}/></button><button className="hero-secondary" onClick={()=>navigate('journey')}>EXPLORE THE SIGNAL <Waves size={16}/></button></div><div className="hero-stats"><div><b>06</b><span>LEARNING PATHS</span></div><div><b>08</b><span>TRANSMISSION STAGES</span></div><div><b>REAL</b><span>HARDWARE SOURCE</span></div></div></div><HeroModel/></section>
  <div className="academy-ticker"><span>ESP32 TRANSMITTER</span><i/><span>4B5B + NRZ/OOK</span><i/><span>VISIBLE LIGHT</span><i/><span>BPW34 RECEIVER</span><i/><span>CRC VERIFIED FILE</span></div>
  <section className="home-start"><div><span className="eyebrow">PICK UP THE THREAD THAT INTERESTS YOU</span><h2>A clear route from<br/><i>concept to code.</i></h2><p>Explore the physical device, follow a complete transmission, or open the real source code. Each area is its own focused learning space.</p></div><div className="home-start-grid"><button onClick={()=>navigate('paths')}><Lightbulb/><b>Learning paths</b><span>Build knowledge step by step</span><ArrowUpRight/></button><button onClick={()=>navigate('journey')}><Waves/><b>Signal journey</b><span>Watch data travel through the prototype</span><ArrowUpRight/></button><button onClick={()=>navigate('code')}><Code2/><b>Code studio</b><span>Read real files and understand each line</span><ArrowUpRight/></button></div></section>
 </>
}

function PracticePage({openPath}){
 return <section className="practice-section practice-page"><div><div className="section-kicker">LEARN BY DOING <span>CHECK YOUR UNDERSTANDING</span></div><p className="eyebrow">A LITTLE PRACTICE GOES A LONG WAY</p><h2>Don't just read it.<br/><i>Trace it yourself.</i></h2><p className="section-intro">Move from recognizing a concept to predicting what the program will do. Practice with real encoding rules, receiver logic, CRC validation, and debugging scenarios.</p><button className="practice-cta" onClick={()=>openPath('practice')}>OPEN THE PRACTICE PATH <ArrowRight size={15}/></button></div><QuizPreview/></section>
}

export default function Academy(){
 const initialHash=window.location.hash.replace(/^#/,'');
 const initialPath=initialHash.startsWith('path/')?initialHash.slice(5):'start';
 const [view,setView]=useState(()=>initialHash.startsWith('path/')?'path':['journey','paths','code','practice'].includes(initialHash)?initialHash:'home');
 const [path,setPath]=useState(initialPath);
 const [codeSelection,setCodeSelection]=useState('tx-encode');
 const [menu,setMenu]=useState(false);
 const navigate=page=>{setView(page);setMenu(false);window.location.hash=page==='home'?'home':page};
 const openPath=id=>{setPath(id);setView('path');setMenu(false);window.location.hash='path/'+id};
 const openCode=id=>{setCodeSelection(id||'tx-encode');navigate('code')};
 const backToPaths=()=>navigate('paths');
 React.useEffect(()=>{
  const onHash=()=>{const h=window.location.hash.replace(/^#/,'');if(h.startsWith('path/')){setPath(h.slice(5));setView('path')}else if(['journey','paths','code','practice'].includes(h)){setView(h)}else{setView('home')}};
  window.addEventListener('hashchange',onHash);return()=>window.removeEventListener('hashchange',onHash);
 },[]);
 return <div className="academy-shell">
  <header className="academy-header"><Brand/><nav className={menu?'open':''}><button className={view==='paths'||view==='path'?'active':''} onClick={()=>navigate('paths')}>LEARNING PATHS</button><button className={view==='journey'?'active':''} onClick={()=>navigate('journey')}>SIGNAL JOURNEY</button><button className={view==='code'?'active':''} onClick={()=>navigate('code')}>CODE STUDIO</button><button className={view==='practice'?'active':''} onClick={()=>navigate('practice')}>PRACTICE</button><a href={REPO} target="_blank" rel="noreferrer">SOURCE REPO <ArrowUpRight size={12}/></a></nav><button className="mobile-menu" onClick={()=>setMenu(v=>!v)} aria-label="Toggle navigation">{menu?<X/>:<Menu/>}</button></header>
  <main className="academy-main"><AnimatePresence mode="wait" initial={false}><motion.div key={view+(view==='path'?path:'')} className="academy-page-transition" initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-8}} transition={{duration:.2,ease:'easeOut'}}>
   {view==='home'&&<HomePage navigate={navigate}/>}
   {view==='journey'&&<SignalJourney onOpenCode={openCode}/>}
   {view==='paths'&&<PathCards onOpen={openPath}/>}
   {view==='code'&&<CodeStudio initialLesson={codeSelection}/>}
   {view==='practice'&&<PracticePage openPath={openPath}/>}
   {view==='path'&&<PathDetail key={path} id={path} onBack={backToPaths}/>}
  </motion.div></AnimatePresence></main>
  <footer className="academy-footer"><div><Brand/><p>An interactive guide to the physical OpenVLC visible-light communication prototype.</p></div><div className="footer-links"><a href={REPO} target="_blank" rel="noreferrer"><Github size={16}/> SOURCE CODE <ArrowUpRight size={13}/></a><a href="https://github.com/luckyprinter/lifi" target="_blank" rel="noreferrer">ACADEMY WEBSITE REPO <ArrowUpRight size={13}/></a></div><div className="footer-bottom"><span>FIRMWARE BASELINE · {FW.slice(0,8)}</span><span>APPLICATION SOURCE · MAIN · {APP.slice(0,8)}</span><span>CONCEPTUAL MODELS ARE NOT LIVE HARDWARE TELEMETRY</span></div></footer>
 </div>
}
