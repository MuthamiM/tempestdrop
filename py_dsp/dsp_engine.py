import cv2
import numpy as np
import scipy.signal as signal
from collections import deque
import time
import json
import threading
import asyncio
import websockets
import wave
import struct
import os
try:
    import sounddevice as sd
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False
    print('[!] sounddevice not installed — microphone capture disabled')
from flask import Flask, render_template_string
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>TempestDrop // Live Stream</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<style>
  :root { --neon: #00ff41; --red: #ff003c; --bg: #050508; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:#e0e0e0; font-family:'Courier New',monospace; overflow-x:hidden; }
  .header { text-align:center; padding:18px 10px 12px; border-bottom:1px solid rgba(0,255,65,0.15); }
  .header h1 { color:var(--neon); font-size:1.1rem; letter-spacing:4px; text-transform:uppercase; text-shadow:0 0 10px rgba(0,255,65,0.3); }
  .header .sub { color:#555; font-size:0.65rem; margin-top:4px; letter-spacing:1px; }
  .status { text-align:center; padding:8px; font-size:0.7rem; }
  .status .dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; vertical-align:middle; }
  .dot.on { background:var(--neon); box-shadow:0 0 8px var(--neon); }
  .dot.off { background:#ff3333; box-shadow:0 0 8px #ff3333; }
  .cards { display:flex; flex-direction:column; gap:10px; padding:12px; }
  .card { background:rgba(0,255,65,0.03); border:1px solid rgba(0,255,65,0.1); border-radius:10px; padding:14px; }
  .card h3 { color:var(--neon); font-size:0.7rem; letter-spacing:2px; text-transform:uppercase; margin-bottom:8px; }
  .val { font-size:1.8rem; font-weight:bold; color:#fff; }
  .val.bit-1 { color:var(--neon); text-shadow:0 0 12px var(--neon); }
  .val.bit-0 { color:var(--red); }
  .val small { font-size:0.6rem; color:#555; margin-left:4px; }
  canvas { width:100%; height:120px; display:block; margin-top:8px; border-radius:6px; background:rgba(0,0,0,0.3); }
  .terminal { background:#000; border:1px solid rgba(0,255,65,0.1); border-radius:10px; padding:12px; margin:12px; font-size:0.65rem; color:var(--neon); max-height:150px; overflow-y:auto; word-break:break-all; line-height:1.6; }
  .stolen { background:rgba(255,0,60,0.04); border:2px solid rgba(255,0,60,0.25); border-radius:12px; margin:12px; padding:16px; text-align:center; }
  .stolen h3 { color:var(--red); font-size:0.7rem; letter-spacing:3px; text-transform:uppercase; margin-bottom:10px; }
  .stolen .data { font-size:1.6rem; font-weight:bold; color:#fff; word-break:break-all; min-height:2rem; text-shadow:0 0 15px rgba(255,0,60,0.4); font-family:'Courier New',monospace; }
  .stolen .status { font-size:0.6rem; color:#666; margin-top:8px; }
  .footer { text-align:center; padding:12px; color:#333; font-size:0.55rem; letter-spacing:1px; }
  @media(min-width:600px) { .cards { flex-direction:row; flex-wrap:wrap; } .card { flex:1; min-width:200px; } }
</style>
</head>
<body>
<div class="header">
  <h1>\u26a1 TempestDrop</h1>
  <div class="sub">Optical Side-Channel • Live Monitor</div>
</div>
<div class="status" id="connStatus"><span class="dot off" id="dot"></span> Connecting...</div>
<div class="cards">
  <div class="card">
    <h3>Raw Luma</h3>
    <div class="val" id="rawVal">--<small>cd/m\u00b2</small></div>
    <canvas id="rawChart"></canvas>
  </div>
  <div class="card">
    <h3>Filtered (10Hz BP)</h3>
    <div class="val" id="filtVal">--<small>\u0394</small></div>
    <canvas id="filtChart"></canvas>
  </div>
  <div class="card">
    <h3>Digital Bit</h3>
    <div class="val" id="bitVal" style="font-size:2.5rem;">-</div>
  </div>
</div>
<!-- AUDIO SECTION -->
<div style="padding:0 12px;">
  <div class="card" style="margin-top:0;">
    <h3>\U0001f3a4 Microphone Capture</h3>
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:8px;">
      <div style="flex:1;">
        <div style="display:flex;justify-content:space-between;font-size:0.6rem;color:#666;margin-bottom:3px;">
          <span>Level</span><span id="audioDb">-\u221e dB</span>
        </div>
        <div style="background:rgba(0,0,0,0.4);border-radius:4px;height:18px;overflow:hidden;border:1px solid rgba(0,255,65,0.1);">
          <div id="vuBar" style="height:100%;width:0%;background:linear-gradient(90deg,#00ff41,#ffcc00,#ff003c);border-radius:3px;transition:width 0.08s;"></div>
        </div>
      </div>
      <div style="text-align:center;min-width:60px;">
        <div class="val" style="font-size:1.2rem;" id="audioPeak">0.00</div>
        <div style="font-size:0.5rem;color:#555;">PEAK</div>
      </div>
    </div>
    <canvas id="audioChart" style="width:100%;height:80px;display:block;border-radius:6px;background:rgba(0,0,0,0.3);"></canvas>
    <div style="display:flex;gap:8px;margin-top:10px;">
      <button onclick="toggleRec()" id="recBtn" style="flex:1;padding:8px;background:rgba(255,0,60,0.08);border:1px solid rgba(255,0,60,0.25);color:#ff003c;font-family:inherit;font-size:0.6rem;border-radius:6px;cursor:pointer;letter-spacing:1px;">\u23fa REC</button>
      <span id="recStatus" style="flex:2;font-size:0.55rem;color:#555;display:flex;align-items:center;">Not recording</span>
    </div>
  </div>
</div>
<div class="terminal" id="term">[*] Awaiting stream data...\n</div>
<div class="stolen" id="stolenBox">
  <h3>\U0001f4e1 Stolen Data</h3>
  <div class="data" id="stolenText">Waiting for signal...</div>
  <div class="status" id="stolenStatus">No active transmission</div>
  <button onclick="runTest()" style="margin-top:12px;padding:8px 16px;background:rgba(255,0,60,0.1);border:1px solid rgba(255,0,60,0.3);color:#ff003c;font-family:inherit;font-size:0.65rem;border-radius:6px;cursor:pointer;letter-spacing:1px;">\\u25b6 DEMO TEST</button>
</div>
<div class="footer">Optical + Acoustic Side-Channel \u2022 Manchester Encoded \u2022 2 Baud</div>
<script>
const socket = io();
const rawData = [], filtData = [], audioData = [];
const MAX = 200;
let bitCount = 0, bits = "";
let isRecording = false;

function drawChart(canvasId, data, color) {
  const c = document.getElementById(canvasId);
  const ctx = c.getContext("2d");
  const W = c.width = c.offsetWidth * 2;
  const H = c.height = c.offsetHeight * 2;
  ctx.clearRect(0,0,W,H);
  if(data.length < 2) return;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  for(let i=0;i<data.length;i++) {
    const x = (i/(data.length-1))*W;
    const y = H - ((data[i]-min)/range)*H*0.85 - H*0.05;
    i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
  }
  ctx.stroke();
}

socket.on("connect", () => {
  document.getElementById("dot").className = "dot on";
  document.getElementById("connStatus").innerHTML = `<span class="dot on" id="dot"></span> Live &mdash; Receiving`;
});
socket.on("disconnect", () => {
  document.getElementById("dot").className = "dot off";
  document.getElementById("connStatus").innerHTML = `<span class="dot off" id="dot"></span> Disconnected`;
});

socket.on("dsp_stream", (d) => {
  rawData.push(d.raw_luma); if(rawData.length>MAX) rawData.shift();
  filtData.push(d.filtered_luma); if(filtData.length>MAX) filtData.shift();
  document.getElementById("rawVal").innerHTML = d.raw_luma.toFixed(2) + `<small>cd/m&sup2;</small>`;
  document.getElementById("filtVal").innerHTML = d.filtered_luma.toFixed(4) + `<small>&Delta;</small>`;
  const bv = document.getElementById("bitVal");
  bv.textContent = d.digital_bit;
  bv.className = d.digital_bit === 1 ? "val bit-1" : "val bit-0";
  drawChart("rawChart", rawData, "#00ff41");
  drawChart("filtChart", filtData, "#ff003c");
  bits += d.digital_bit;
  bitCount++;
  if(bitCount % 60 === 0) {
    const term = document.getElementById("term");
    term.innerHTML += `<br>[STREAM]: ${bits.slice(-60)}`;
    term.scrollTop = term.scrollHeight;
  }
});

socket.on("decoded", (d) => {
  const st = document.getElementById("stolenText");
  const ss = document.getElementById("stolenStatus");
  const box = document.getElementById("stolenBox");
  if(d.event === "sync") {
    st.textContent = "\\u2588";
    ss.textContent = "PREAMBLE LOCKED \\u2014 decoding...";
    ss.style.color = "#ff003c";
    box.style.borderColor = "rgba(255,0,60,0.6)";
    box.style.boxShadow = "0 0 20px rgba(255,0,60,0.15)";
  } else if(d.event === "char") {
    st.textContent = d.text;
    ss.textContent = d.text.length + " bytes recovered";
  } else if(d.event === "end") {
    st.textContent = d.text;
    ss.textContent = "\\u2713 TX COMPLETE \\u2014 " + d.text.length + " bytes stolen";
    ss.style.color = "#00ff41";
    box.style.borderColor = "rgba(0,255,65,0.5)";
    box.style.boxShadow = "0 0 25px rgba(0,255,65,0.15)";
  }
});

function runTest() {
  fetch("/api/inject", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({text: "STOLEN-KEY-42"})
  }).then(r => r.json()).then(d => console.log("Test inject:", d)).catch(e => console.error(e));
}

// --- Audio stream handling ---
socket.on("audio_stream", (d) => {
  // VU meter
  const pct = Math.min(100, (d.rms / 0.15) * 100);
  document.getElementById("vuBar").style.width = pct + "%";
  document.getElementById("audioPeak").textContent = d.peak.toFixed(3);
  const db = d.rms > 0 ? (20 * Math.log10(d.rms)).toFixed(1) : "-\\u221e";
  document.getElementById("audioDb").textContent = db + " dB";
  // Waveform chart
  if(d.waveform && d.waveform.length) {
    audioData.length = 0;
    for(let i=0;i<d.waveform.length;i++) audioData.push(d.waveform[i]);
    drawAudioWaveform();
  }
});

function drawAudioWaveform() {
  const c = document.getElementById("audioChart");
  if(!c) return;
  const ctx = c.getContext("2d");
  const W = c.width = c.offsetWidth * 2;
  const H = c.height = c.offsetHeight * 2;
  ctx.clearRect(0,0,W,H);
  if(audioData.length < 2) return;
  // Draw center line
  ctx.beginPath();
  ctx.strokeStyle = "rgba(0,255,65,0.1)";
  ctx.lineWidth = 1;
  ctx.moveTo(0, H/2);
  ctx.lineTo(W, H/2);
  ctx.stroke();
  // Draw waveform
  ctx.beginPath();
  ctx.strokeStyle = "#00ccff";
  ctx.lineWidth = 1.5;
  for(let i=0;i<audioData.length;i++) {
    const x = (i/(audioData.length-1))*W;
    const y = H/2 - audioData[i] * H * 0.9;
    i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
  }
  ctx.stroke();
}

function toggleRec() {
  isRecording = !isRecording;
  const btn = document.getElementById("recBtn");
  const st = document.getElementById("recStatus");
  if(isRecording) {
    fetch("/api/audio/record", {method:"POST"}).then(r=>r.json()).then(d=>{
      st.textContent = "\\u23fa Recording: " + (d.path||"active");
      st.style.color = "#ff003c";
    });
    btn.textContent = "\\u23f9 STOP";
    btn.style.background = "rgba(255,0,60,0.2)";
  } else {
    fetch("/api/audio/stop", {method:"POST"}).then(r=>r.json()).then(d=>{
      st.textContent = "\\u2713 Saved: " + (d.path||"done");
      st.style.color = "#00ff41";
    });
    btn.textContent = "\\u23fa REC";
    btn.style.background = "rgba(255,0,60,0.08)";
  }
}
</script>
</body>
</html>
'''

# --- Plain WebSocket server for Java C2 client ---
ws_clients = set()
ws_loop = None

async def ws_handler(websocket):
    ws_clients.add(websocket)
    print(f"[+] Java C2 client connected ({len(ws_clients)} active)")
    try:
        async for msg in websocket:
            pass  # We only push data to clients
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        ws_clients.discard(websocket)
        print(f"[-] Java C2 client disconnected ({len(ws_clients)} active)")

def broadcast_ws(data):
    """Send DSP data to all connected Java WebSocket clients."""
    if not ws_clients or ws_loop is None:
        return
    message = json.dumps(data)
    for client in list(ws_clients):
        try:
            asyncio.run_coroutine_threadsafe(client.send(message), ws_loop)
        except Exception:
            ws_clients.discard(client)

def broadcast_decoded(event, char=None, text=None):
    """Send decoded Manchester data to all clients."""
    payload = {'type': 'decoded', 'event': event}
    if char is not None:
        payload['char'] = char
    if text is not None:
        payload['text'] = text
    # Socket.IO
    socketio.emit('decoded', payload)
    # Plain WebSocket (Java C2)
    if ws_clients and ws_loop:
        message = json.dumps(payload)
        for client in list(ws_clients):
            try:
                asyncio.run_coroutine_threadsafe(client.send(message), ws_loop)
            except Exception:
                ws_clients.discard(client)

async def start_ws_server():
    global ws_loop
    ws_loop = asyncio.get_event_loop()
    async with websockets.serve(ws_handler, "0.0.0.0", 5001):
        print("[*] Plain WebSocket server running on port 5001 (for Java C2)")
        await asyncio.Future()  # run forever

def run_ws_server():
    asyncio.run(start_ws_server())

# --- DSP Configuration ---
FPS = 30  # Conservative estimate; will measure actual
BAUD_RATE = 2  # 2 Hz half-bit rate — reliable at low webcam FPS (6-10fps)
BUFFER_SIZE = 300  # ~10 seconds at 30fps
NYQUIST = FPS / 2.0
# Bandpass for visualization: Manchester at 5 baud has energy at 1.25-2.5 Hz
# Use a wider passband to catch the signal
LOW_CUT = 1.0 / NYQUIST
HIGH_CUT = 4.0 / NYQUIST

b, a = signal.butter(2, [LOW_CUT, HIGH_CUT], btype='band')

luma_buffer = deque(maxlen=BUFFER_SIZE)
time_buffer = deque(maxlen=BUFFER_SIZE)
raw_luma_history = deque(maxlen=60)  # Short window for threshold calc

# Global variables for the demodulation
decoded_bits = ""
is_recording = False
actual_fps = 30.0  # Will be measured
fps_frame_count = 0
fps_start_time = None

# ---- Manchester Decoder (Edge-Based) ----
class ManchesterDecoder:
    """Edge-based Manchester decoder.
    Detects level transitions, measures inter-edge intervals,
    classifies as T (half-bit) or 2T (full-bit), and extracts data bits.
    Convention: falling mid-bit = data 1, rising mid-bit = data 0
    (matches TX page: '1'->"10"=HIGH,LOW  '0'->"01"=LOW,HIGH)"""
    PREAMBLE_MIN = 8          # 8 alternating bits to declare sync
    SILENCE_TIMEOUT = 80      # ~3s at 26fps of no transitions = end of TX

    def __init__(self):
        self.data_bits = []
        self.synced = False
        self.decoded_text = ""
        self.last_level = None
        self.idle_frames = 0
        self.frame_count = 0
        self.last_edge_frame = 0
        self.edge_started = False
        self.skip_next = False  # True = next T-edge is boundary (skip)
        self.fpb = 13  # frames per half-bit, updated dynamically
        self._pending_event = None

    def set_fps(self, fps, baud):
        """Update frames-per-half-bit based on measured FPS."""
        self.fpb = max(2, round(fps / baud))
        print(f'[DSP] Decoder tuned: {fps:.1f} FPS / {baud} baud = {self.fpb} frames per half-bit')

    def reset(self):
        self.__init__()

    def feed(self, digital_bit):
        """Feed one thresholded frame. Returns (event, data) or None.
        Events: ('SYNC',None), ('CHAR','X'), ('END','full text')"""
        self.frame_count += 1
        result = None

        if self.last_level is not None and digital_bit != self.last_level:
            # ---- EDGE detected ----
            direction = 'rise' if digital_bit == 1 else 'fall'
            self.idle_frames = 0

            if self.edge_started:
                interval = self.frame_count - self.last_edge_frame
                self._process_edge(direction, interval)
                result = self._check_output()
            else:
                self.edge_started = True

            self.last_edge_frame = self.frame_count
        else:
            self.idle_frames += 1

        self.last_level = digital_bit

        # Detect end of transmission
        if self.idle_frames >= self.SILENCE_TIMEOUT and self.decoded_text:
            text = self.decoded_text
            self.reset()
            return ('END', text)

        return result

    def _process_edge(self, direction, interval):
        """Classify an edge as mid-bit (data) or boundary (skip)."""
        half = self.fpb
        tol = half * 0.45  # generous ±45% tolerance

        is_T = abs(interval - half) <= tol
        is_2T = abs(interval - 2 * half) <= tol

        if not (is_T or is_2T):
            # Invalid interval — noise spike or lost sync
            print(f'[DSP] Edge reset: interval={interval} (expected ~{half} or ~{2*half})')
            self._edge_reset()
            return

        if is_2T:
            if self.skip_next:
                # Expected T but got 2T — phase error
                self._edge_reset()
                return
            # Definitely a mid-bit transition (no boundary between different-valued bits)
            bit = 1 if direction == 'fall' else 0
            self.data_bits.append(bit)
            self.skip_next = False
        elif is_T:
            if self.skip_next:
                # This is the mid-bit transition (after a boundary)
                bit = 1 if direction == 'fall' else 0
                self.data_bits.append(bit)
                self.skip_next = False
            else:
                # This is a boundary transition — skip it
                self.skip_next = True

    def _edge_reset(self):
        """Soft reset: keep decoded text but lose bit-level state."""
        self.edge_started = False
        self.skip_next = False
        if not self.synced:
            self.data_bits = []

    def _check_output(self):
        """Check if we have enough bits for preamble sync or a decoded char."""
        if not self.synced:
            if len(self.data_bits) >= self.PREAMBLE_MIN:
                recent = self.data_bits[-self.PREAMBLE_MIN:]
                if all(recent[i] != recent[i+1] for i in range(self.PREAMBLE_MIN - 1)):
                    self.synced = True
                    self.data_bits = []
                    print(f'[+] PREAMBLE LOCKED after {self.frame_count} frames')
                    return ('SYNC', None)
            # Trim if accumulating too many without sync
            if len(self.data_bits) > 60:
                self.data_bits = self.data_bits[-20:]
            return None

        # After preamble: accumulate 8 data bits -> 1 ASCII char
        if len(self.data_bits) >= 8:
            byte_bits = self.data_bits[:8]
            self.data_bits = self.data_bits[8:]
            val = 0
            for bb in byte_bits:
                val = (val << 1) | bb
            if 32 <= val <= 126:
                char = chr(val)
                self.decoded_text += char
                return ('CHAR', char)

        return None

decoder = ManchesterDecoder()

# Signal detection thresholds
MIN_LUMA_RANGE = 20.0  # Min difference between recent max/min luma to consider signal active (noise=10-11, signal=35+)

# ---- Audio Capture ----
AUDIO_RATE = 16000      # 16kHz sample rate
AUDIO_CHANNELS = 1      # Mono
AUDIO_BLOCK = 1024      # Samples per callback block
audio_rms_history = deque(maxlen=100)  # ~6 seconds of RMS levels
audio_waveform = deque(maxlen=4000)    # ~0.25s of raw samples for waveform display
audio_recording = False
audio_wav_writer = None
audio_wav_path = None
audio_peak = 0.0
audio_stream_active = False

def audio_callback(indata, frames, time_info, status):
    """Called by sounddevice for each audio block from the microphone."""
    global audio_peak
    if status:
        print(f'[AUDIO] {status}')
    samples = indata[:, 0]  # mono channel
    rms = float(np.sqrt(np.mean(samples ** 2)))
    peak = float(np.max(np.abs(samples)))
    audio_peak = max(audio_peak * 0.95, peak)  # Slow decay peak meter
    audio_rms_history.append(rms)
    # Keep a small waveform buffer for visualization
    audio_waveform.extend(samples[-256:].tolist())
    # Write to WAV if recording
    if audio_recording and audio_wav_writer:
        try:
            audio_wav_writer.writeframes((samples * 32767).astype(np.int16).tobytes())
        except Exception:
            pass

def start_audio_capture():
    """Start microphone capture in a background stream."""
    global audio_stream_active
    if not HAS_AUDIO:
        print('[!] Cannot start audio — sounddevice not available')
        return
    try:
        stream = sd.InputStream(
            samplerate=AUDIO_RATE,
            channels=AUDIO_CHANNELS,
            blocksize=AUDIO_BLOCK,
            callback=audio_callback
        )
        stream.start()
        audio_stream_active = True
        print(f'[+] Microphone capture active: {AUDIO_RATE}Hz mono')
    except Exception as e:
        print(f'[!] Audio capture failed: {e}')

def start_audio_recording():
    """Start saving captured audio to a WAV file."""
    global audio_recording, audio_wav_writer, audio_wav_path
    if audio_recording:
        return audio_wav_path
    ts = time.strftime('%Y%m%d_%H%M%S')
    audio_wav_path = os.path.join(os.path.dirname(__file__), f'capture_{ts}.wav')
    audio_wav_writer = wave.open(audio_wav_path, 'wb')
    audio_wav_writer.setnchannels(AUDIO_CHANNELS)
    audio_wav_writer.setsampwidth(2)  # 16-bit
    audio_wav_writer.setframerate(AUDIO_RATE)
    audio_recording = True
    print(f'[REC] Recording audio to {audio_wav_path}')
    return audio_wav_path

def stop_audio_recording():
    """Stop recording and close the WAV file."""
    global audio_recording, audio_wav_writer
    if not audio_recording:
        return None
    audio_recording = False
    if audio_wav_writer:
        audio_wav_writer.close()
        audio_wav_writer = None
    print(f'[REC] Audio recording saved: {audio_wav_path}')
    return audio_wav_path

def process_frame(frame):
    # Convert BGR to Grayscale to get Luma (brightness)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Use center half of frame as ROI to reduce noise
    height, width = gray.shape
    roi = gray[height//4 : 3*height//4, width//4 : 3*width//4]
    
    # Calculate the spatial mean intensity
    mean_luma = np.mean(roi)
    return mean_luma

def demodulate_signal():
    global decoded_bits
    if len(luma_buffer) < 30:
        return # Not enough data
    
    y = np.array(luma_buffer)
    
    # === VISUALIZATION: Bandpass filter for chart display only ===
    try:
        filtered_y = signal.filtfilt(b, a, y)
    except Exception:
        filtered_y = y * 0
    
    # === DECODING: Use raw luma with adaptive threshold ===
    # Look at recent ~1 second of raw luma for threshold
    window = max(30, int(actual_fps))
    recent = y[-window:]
    luma_min = float(np.min(recent))
    luma_max = float(np.max(recent))
    luma_range = luma_max - luma_min
    threshold = (luma_max + luma_min) / 2.0
    
    # Digitize using simple midpoint threshold on raw luma
    current_luma = float(y[-1])
    if luma_range > MIN_LUMA_RANGE:
        state = 1 if current_luma > threshold else 0
    else:
        state = 0  # No significant signal
    
    # Emit for visualization
    payload = {
        "raw_luma": float(current_luma),
        "filtered_luma": float(filtered_y[-1]) if len(filtered_y) > 0 else 0.0,
        "digital_bit": int(state),
        "luma_range": round(luma_range, 2),
        "threshold": round(threshold, 2)
    }
    
    socketio.emit('dsp_stream', payload)
    broadcast_ws(payload)

    # Only feed decoder when there's a real signal (luma modulation detected)
    if luma_range < MIN_LUMA_RANGE:
        return  # No signal detected
    
    # Feed decoder with raw-thresholded bit
    result = decoder.feed(state)
    if result:
        event_type, data = result
        if event_type == 'SYNC':
            print(f'[+] PREAMBLE SYNCED (range={luma_range:.1f}) \u2014 decoding payload...')
            broadcast_decoded('sync')
        elif event_type == 'CHAR':
            print(f'[DECODED] \'{data}\' \u2192 {decoder.decoded_text}')
            broadcast_decoded('char', char=data, text=decoder.decoded_text)
        elif event_type == 'END':
            print(f'[\u2713 DECODED] TX COMPLETE: "{data}"')
            broadcast_decoded('end', text=data)

def video_loop():
    global actual_fps, fps_frame_count, fps_start_time
    print("[*] Starting OpenCV Video Loop on Thread.")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    
    # CRITICAL: Lock auto-exposure so the camera doesn't counteract our modulation
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25) # 0.25 is often Manual on DSHOW
    cap.set(cv2.CAP_PROP_EXPOSURE, -6) # Shorter exposure = faster FPS
    # Try to request higher FPS
    cap.set(cv2.CAP_PROP_FPS, 30)
    # Try to set resolution lower for faster FPS
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("[!] Error: Could not open webcam.")
        return
        
    print("[+] Webcam locked and exposure hardened. Awaiting Photons...")

    start_time = time.time()
    fps_start_time = time.time()
    fps_frame_count = 0
    fps_reported = False
    diag_counter = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Measure actual FPS
        fps_frame_count += 1
        elapsed = time.time() - fps_start_time
        if elapsed >= 2.0 and not fps_reported:
            actual_fps = fps_frame_count / elapsed
            decoder.set_fps(actual_fps, BAUD_RATE)
            print(f'[DSP] Measured webcam FPS: {actual_fps:.1f}')
            fps_reported = True
            
        luma = process_frame(frame)
        current_time = time.time() - start_time
        
        luma_buffer.append(luma)
        time_buffer.append(current_time)
        
        demodulate_signal()
        
        # Periodic diagnostics every ~3 seconds
        diag_counter += 1
        if diag_counter % 90 == 0 and len(luma_buffer) > 30:
            y = np.array(luma_buffer)
            recent = y[-30:]
            rng = float(np.max(recent) - np.min(recent))
            mean = float(np.mean(recent))
            if rng > MIN_LUMA_RANGE:
                print(f'[DSP] SIGNAL ACTIVE | luma={mean:.1f} range={rng:.1f} synced={decoder.synced} decoded="{decoder.decoded_text}"')
        
        # Stream audio data every ~5 frames (~5Hz at 26fps)
        if diag_counter % 5 == 0 and audio_stream_active:
            rms = float(audio_rms_history[-1]) if audio_rms_history else 0.0
            wf = list(audio_waveform)[-256:] if audio_waveform else []
            audio_payload = {
                'rms': rms,
                'peak': round(audio_peak, 4),
                'recording': audio_recording,
                'waveform': [round(s, 5) for s in wf]
            }
            socketio.emit('audio_stream', audio_payload)
            # Also send to Java C2 via WebSocket
            broadcast_ws({'type': 'audio', 'rms': rms, 'peak': round(audio_peak, 4)})

        # Display the frame to the attacker
        cv2.imshow("TempestDrop Receiver Pipeline", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/health')
def health():
    return "TempestDrop DSP Backend Running."

TX_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>TempestDrop // Phone TX</title>
<style>
  :root { --neon:#00ff41; --red:#ff003c; --bg:#050508; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:#e0e0e0; font-family:'Courier New',monospace; min-height:100vh; display:flex; flex-direction:column; }
  .header { text-align:center; padding:20px 10px 14px; border-bottom:1px solid rgba(0,255,65,0.15); }
  .header h1 { color:var(--neon); font-size:1rem; letter-spacing:3px; text-transform:uppercase; }
  .header .sub { color:#555; font-size:0.6rem; margin-top:4px; }
  .main { flex:1; padding:16px; display:flex; flex-direction:column; gap:14px; }
  label { color:var(--neon); font-size:0.65rem; letter-spacing:2px; text-transform:uppercase; }
  input { width:100%; background:rgba(0,255,65,0.04); border:1px solid rgba(0,255,65,0.2); border-radius:8px; color:#fff; padding:12px; font-family:inherit; font-size:0.85rem; outline:none; }
  input:focus { border-color:rgba(0,255,65,0.5); box-shadow:0 0 10px rgba(0,255,65,0.1); }
  .info { font-size:0.6rem; color:#555; margin-top:4px; }
  button { width:100%; padding:14px; border:1px solid rgba(0,255,65,0.3); border-radius:8px; background:rgba(0,255,65,0.08); color:var(--neon); font-family:inherit; font-size:0.85rem; font-weight:bold; letter-spacing:2px; text-transform:uppercase; cursor:pointer; }
  button:active { background:rgba(0,255,65,0.2); }
  button:disabled { opacity:0.3; }
  button.stop { border-color:rgba(255,0,60,0.3); background:rgba(255,0,60,0.08); color:var(--red); }
  .status { text-align:center; font-size:0.7rem; padding:8px; }
  .progress { text-align:center; font-size:0.6rem; color:#555; margin-top:4px; }
  #overlay { position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:99999; pointer-events:none; background:white; opacity:0; }
  .instructions { background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); border-radius:8px; padding:12px; font-size:0.6rem; color:#666; line-height:1.6; }
  .instructions strong { color:var(--neon); }
</style>
</head>
<body>
<div class="header">
  <h1>&#9889; TempestDrop TX</h1>
  <div class="sub">Phone Transmitter &bull; Optical Side-Channel</div>
</div>
<div class="main">
  <div class="instructions">
    <strong>How to use:</strong><br>
    1. Type a secret below<br>
    2. Point the PC webcam at this phone screen<br>
    3. Hit TRANSMIT &mdash; the screen will flash<br>
    4. Watch the Java C2 Dashboard decode the bits
  </div>
  <div>
    <label>&#8250; Secret Payload</label>
    <input id="payload" type="text" placeholder="Type secret data here..." value="HI" autocomplete="off">
    <div class="info" id="info">2 bytes &middot; 16 bits &middot; ~16s TX time</div>
  </div>
  <button id="btn" onclick="toggle()">&#9654; Transmit</button>
  <div class="status" id="status" style="color:#555;">Ready &mdash; aim webcam at this screen</div>
  <div class="progress" id="progress"></div>
</div>
<div id="overlay"></div>
<script>
const overlay = document.getElementById("overlay");
const btn = document.getElementById("btn");
const statusEl = document.getElementById("status");
const progressEl = document.getElementById("progress");
const payloadInput = document.getElementById("payload");
const infoEl = document.getElementById("info");
let transmitting = false, timer = null;

payloadInput.addEventListener("input", () => {
  const len = payloadInput.value.length;
  const bits = len * 8;
  const secs = (bits * 2 / 2).toFixed(1);
  infoEl.textContent = len + " bytes \\u00b7 " + bits + " bits \\u00b7 ~" + secs + "s TX time";
});

function manchesterEncode(bits) {
  let out = "";
  for (let i = 0; i < bits.length; i++) {
    out += bits[i] === "0" ? "01" : "10";
  }
  return out;
}

function textToBinary(text) {
  let bin = "";
  for (let i = 0; i < text.length; i++) {
    bin += text.charCodeAt(i).toString(2).padStart(8, "0");
  }
  return bin;
}

function toggle() {
  if (!transmitting) startTX();
  else stopTX();
}

function stopTX() {
  transmitting = false;
  overlay.style.opacity = "0";
  btn.textContent = "\\u25b6 Transmit";
  btn.classList.remove("stop");
  statusEl.style.color = "#555";
  statusEl.textContent = "Stopped";
  progressEl.textContent = "";
}

function startTX() {
  const secret = payloadInput.value;
  if (!secret) { statusEl.textContent = "Enter a payload first!"; statusEl.style.color = "#ff3333"; return; }

  const binary = textToBinary(secret);
  const preamble = "1010101010101010101010101010101010101010"; // 40-bit sync preamble (longer for optical reliability)
  const encoded = manchesterEncode(preamble + binary);

  transmitting = true;
  btn.textContent = "\\u25a0 Stop TX";
  btn.classList.add("stop");
  statusEl.style.color = "#ff003c";
  statusEl.textContent = "TX ACTIVE \\u2014 transmitting " + secret.length + " bytes...";

  // Set phone brightness to max for better contrast
  document.body.style.background = "#000";

  const BAUD = 2;
  const bitTime = 1000 / BAUD;  // 500ms per symbol
  let idx = 0;

  function step() {
    if (!transmitting || idx >= encoded.length) {
      if (transmitting) {
        // Transmission complete
        overlay.style.opacity = "0";
        statusEl.style.color = "#00ff41";
        statusEl.textContent = "\\u2713 TX Complete \\u2014 " + secret.length + " bytes sent";
        btn.textContent = "\\u25b6 Transmit Again";
        btn.classList.remove("stop");
        transmitting = false;
        progressEl.textContent = "";
      }
      return;
    }

    const bit = encoded[idx];
    overlay.style.opacity = bit === "1" ? "1" : "0";
    idx++;
    progressEl.textContent = Math.round((idx / encoded.length) * 100) + "% (" + idx + "/" + encoded.length + " symbols)";
    setTimeout(step, bitTime);
  }

  step();
}
</script>
</body>
</html>
'''

@app.route('/tx')
def tx_page():
    return render_template_string(TX_HTML)

@app.route('/api/inject', methods=['POST'])
def api_inject():
    """Network-based data injection — simulates a decoded optical transmission."""
    from flask import request
    data = request.get_json(force=True)
    text = data.get('text', '')
    if not text:
        return json.dumps({'error': 'no text'}), 400

    print(f'[INJECT] Network injection: "{text}"')
    broadcast_decoded('sync')
    partial = ""
    for ch in text:
        partial += ch
        broadcast_decoded('char', char=ch, text=partial)
        time.sleep(0.15)
    broadcast_decoded('end', text=text)
    print(f'[INJECT] Complete: "{text}"')
    return json.dumps({'ok': True, 'text': text})

@app.route('/api/audio/record', methods=['POST'])
def api_audio_record():
    """Start recording microphone audio to a WAV file."""
    path = start_audio_recording()
    return json.dumps({'ok': True, 'path': path})

@app.route('/api/audio/stop', methods=['POST'])
def api_audio_stop():
    """Stop recording and save the WAV file."""
    path = stop_audio_recording()
    return json.dumps({'ok': True, 'path': path})

@app.route('/api/audio/status')
def api_audio_status():
    """Get audio capture status."""
    return json.dumps({
        'active': audio_stream_active,
        'recording': audio_recording,
        'path': audio_wav_path,
        'rms': float(audio_rms_history[-1]) if audio_rms_history else 0.0,
        'peak': round(audio_peak, 4),
        'has_sounddevice': HAS_AUDIO
    })

if __name__ == '__main__':
    # Start microphone capture
    if HAS_AUDIO:
        audio_thread = threading.Thread(target=start_audio_capture, daemon=True)
        audio_thread.start()
    
    # Start video loop in background
    video_thread = threading.Thread(target=video_loop, daemon=True)
    video_thread.start()
    
    # Start plain WebSocket server for Java C2 Dashboard (port 5001)
    ws_thread = threading.Thread(target=run_ws_server, daemon=True)
    ws_thread.start()
    
    print("[*] Starting Flask WebSocket Server on Port 5000...")
    print(f"[*] Audio capture: {'ENABLED' if HAS_AUDIO else 'DISABLED (install sounddevice)'}")
    socketio.run(app, host='0.0.0.0', port=5000)
