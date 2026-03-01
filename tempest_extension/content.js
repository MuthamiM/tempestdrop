// Guard: prevent double-initialization if script is injected multiple times
if (window.__tempestDropLoaded) {
    // Already running - just make sure the message listener is ready
} else {
window.__tempestDropLoaded = true;

// Manchester Encoding (0 -> 01, 1 -> 10)
function manchesterEncode(bits) {
    let encoded = "";
    for (let i = 0; i < bits.length; i++) {
        if (bits[i] === "0") encoded += "01";
        else if (bits[i] === "1") encoded += "10";
    }
    return encoded;
}

// Global control
let isTransmitting = false;
let overlay = null;

function createOverlay() {
    if (overlay) return;
    console.log("[TempestDrop] Initializing Physical Overlay...");
    overlay = document.createElement("div");
    overlay.id = "tempest-drop-modulator";
    overlay.style.position = "fixed";
    overlay.style.top = "0";
    overlay.style.left = "0";
    overlay.style.width = "100vw";
    overlay.style.height = "100vh";
    overlay.style.zIndex = "2147483647";
    overlay.style.pointerEvents = "none";
    overlay.style.backgroundColor = "white"; // White pulses are highest energy for the sensor
    overlay.style.opacity = "0";
    document.documentElement.appendChild(overlay);
}

function modulate(bits) {
    if (!isTransmitting) return;
    createOverlay();

    const encoded = manchesterEncode(bits);
    const BAUD_RATE = 10; // 10 bits per second (Hz)
    const bitTime = 1000 / BAUD_RATE;

    console.log(`[TempestDrop] TRANSMITTING: ${bits.length} bits (${encoded.length} symbols)`);

    let index = 0;

    function step() {
        if (!isTransmitting || index >= encoded.length) {
            console.log("[TempestDrop] Transmission Finished.");
            overlay.style.opacity = "0";
            isTransmitting = false;
            return;
        }

        const bit = encoded[index];
        // Production: 0.01 (1%) — imperceptible to humans, detectable by sensor
        // Demo/debug: use 0.35 for visible flashes
        overlay.style.opacity = bit === "1" ? "0.01" : "0.00";

        index++;
        setTimeout(step, bitTime);
    }

    step();
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log("[TempestDrop] Message Received:", request.action);
    if (request.action === "start") {
        isTransmitting = true;
        modulate(request.payload);
        sendResponse({ status: "ok", bits: request.payload.length });
    } else if (request.action === "stop") {
        isTransmitting = false;
        sendResponse({ status: "stopped" });
    }
    return true; // keep message channel open for async response
});

} // end guard
