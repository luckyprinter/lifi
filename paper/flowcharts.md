# LiFi System Flowcharts

These flowcharts are written in Mermaid so they can be rendered by GitHub,
Markdown preview extensions, and many documentation tools.

## Whole System: TX To RX

```mermaid
flowchart LR
    A[User selects text/image/audio/video] --> B[TX GUI converts data to bytes]
    B --> C[Frame builder adds metadata and CRC]
    C --> D[USB serial sends frame to TX ESP32]
    D --> E[TX firmware Manchester-encodes bytes]
    E --> F[GPIO5 drives 2N3904 + IRF540N]
    F --> G[12 V DC LED emits modulated visible light]
    G --> H[Free-space optical path]
    H --> I[BPW34 converts light to photocurrent]
    I --> J[OPA2604 TIA converts current to voltage]
    J --> K[LM393 comparator produces logic waveform]
    K --> L[RX ESP32 samples Manchester half-bits]
    L --> M[RX firmware validates frame and CRC]
    M --> N[RX GUI reconstructs and displays/saves data]
```

## TX System Flow

```mermaid
flowchart TD
    A[Start TX GUI] --> B[Select serial port and connect]
    B --> C[Set optical frequency]
    C --> D[Choose payload type]
    D --> E[Read payload bytes]
    E --> F[Split into chunks]
    F --> G[Compute CRC per frame]
    G --> H[Send frame bytes over USB serial]
    H --> I[TX ESP32 receives frame]
    I --> J[Send preamble/start pattern]
    J --> K[For each byte, send Manchester symbols]
    K --> L[GPIO5 switches driver circuit]
    L --> M[LED turns optical symbols into light]
    M --> N[Report TX done marker to GUI]
```

## RX System Flow

```mermaid
flowchart TD
    A[Light reaches BPW34] --> B[Photocurrent changes with optical intensity]
    B --> C[OPA2604 TIA converts current to voltage]
    C --> D[LM393 compares signal against threshold]
    D --> E[ESP32 receives digital waveform]
    E --> F[Detect expected start transition]
    F --> G[Wait halfBitUs / 2]
    G --> H[Sample each Manchester half-bit]
    H --> I{Halves different?}
    I -- No --> J[Count unstable bit and resync]
    I -- Yes --> K[Decode bit from second half]
    K --> L[Build byte]
    L --> M[Search preamble and start byte]
    M --> N[Read frame type, size, CRC, payload]
    N --> O{CRC pass?}
    O -- No --> P[Report bad CRC]
    O -- Yes --> Q[Send received chunk to RX GUI]
    Q --> R[Display text or save reconstructed file]
```

## Physical Layer Timing Flow

```mermaid
flowchart LR
    A[frequencyHz] --> B["halfBitUs = 1000000 / (2 * frequencyHz)"]
    B --> C[TX changes LED state every halfBitUs]
    B --> D[RX waits and samples every halfBitUs]
    C --> E[Manchester waveform]
    D --> E
    E --> F[Valid bit requires two opposite half-bit samples]
```

## Debug Flow

```mermaid
flowchart TD
    A[Transmission fails] --> B{LED visibly switches?}
    B -- No --> C[Debug TX GPIO, 2N3904, IRF540N, LED power]
    B -- Yes --> D{LM393 output toggles cleanly?}
    D -- No --> E[Adjust BPW34 bias, TIA, comparator threshold, shielding]
    D -- Yes --> F{RX frequency matches TX?}
    F -- No --> G[Set same frequency in both firmware/GUI]
    F -- Yes --> H{Unstable Manchester bits?}
    H -- Yes --> I[Check polarity, sample point, frequency, optical contrast]
    H -- No --> J{CRC fails?}
    J -- Yes --> K[Reduce chunk size/frequency and log BER]
    J -- No --> L[Proceed to larger payload tests]
```
