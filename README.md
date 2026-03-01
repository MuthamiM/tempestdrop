# TempestDrop // Optical Air-Gap Exfiltration Suite

TempestDrop is a high-complexity, polyglot cybersecurity tool designed for the **Advanced System Hackathon 2026**. It demonstrates the power of optical side-channels, allowing data to be exfiltrated from air-gapped systems by modulating monitor brightness.

## Architecture

| Component | Language | Description |
|---|---|---|
| **Native Modulator** | C++ | DDC/CI hardware brightness control via Win32 API |
| **Infection Orchestrator** | C# (.NET 9) | File scanning, Manchester encoding, IPC to modulator |
| **Chrome Extension** | JavaScript (MV3) | Zero-privilege DOM overlay modulation at 10 Hz |
| **DSP Engine** | Python | OpenCV capture + 4th-order Butterworth bandpass filter |
| **C2 Dashboard** | Java 21 | JavaFX 21.0.2 real-time waveform analysis + decoding |
| **Landing Page** | HTML/CSS | Product showcase page |

## Quick Start

### One-Click Demo
```
run_demo.bat
```
This launches the Python DSP backend, Java C2 Dashboard, and C# Orchestrator in separate windows.

### Manual Launch
```bash
# 1. Start the DSP backend (Attacker Machine)
python py_dsp/dsp_engine.py

# 2. Start the Java C2 Dashboard (Attacker Machine)
cd java_ui
.\mvnw.cmd javafx:run

# 3. Deploy the Chrome Extension to Target Machine
#    chrome://extensions > Load Unpacked > select tempest_extension/

# 4. Or deploy the C# + C++ pipeline on Target Machine
cs_infector\bin\Debug\net9.0\cs_infector_new.exe
```

## Requirements

| Dependency | Version | Notes |
|---|---|---|
| JDK | 21 LTS | Microsoft OpenJDK recommended |
| Python | 3.10+ | With opencv-python, numpy, scipy, flask, flask-socketio |
| .NET | 9.0 | For C# Infector |
| Chrome | 88+ | Manifest V3 extension support |
| Maven | 3.9+ | Included via Maven Wrapper (no install needed) |

## How It Works

```
[TARGET]  secret.txt → C# Encoder → Manchester Bits → Screen Modulation (10 Hz)
                                                            │
                                                      ── AIR GAP ──
                                                            │
[ATTACKER]  Webcam/Sensor → Python DSP → Bandpass Filter → Java C2 Dashboard
```

1. The **Chrome Extension** (or C++/C# pipeline) reads secret data and Manchester-encodes it
2. Screen brightness is modulated at 10 baud (white overlay pulses)
3. An optical sensor or webcam on the attacker machine captures the light changes
4. The **Python DSP Engine** applies a Butterworth bandpass filter to isolate the 10 Hz carrier
5. Filtered signal streams via WebSocket to the **Java C2 Dashboard** for real-time visualization and decoding

## Project Structure

```
tempestdrop/
├── cpp_modulator/      # C++ native DDC/CI brightness modulator
├── cs_infector/        # C# infection orchestrator (.NET 9)
├── java_ui/            # Java 21 + JavaFX 21.0.2 C2 Dashboard
│   ├── pom.xml         # Maven build config
│   └── mvnw.cmd        # Maven Wrapper (no install needed)
├── py_dsp/             # Python DSP engine (Flask + OpenCV)
├── tempest_extension/  # Chrome Manifest V3 extension
├── landing_page/       # Product landing page
├── run_demo.bat        # One-click demo launcher
└── secret.txt          # Sample target payload
```

## Legal

This software is provided for **educational and research purposes only**. Developed for the Advanced System Hackathon 2026. Use it only on systems you have explicit permission to test.
