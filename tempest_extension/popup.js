let isLeaking = false;

const btn = document.getElementById('toggleBtn');
const statusText = document.getElementById('status-text');
const statusDot = document.getElementById('status-dot');
const payloadInput = document.getElementById('payload');
const byteCount = document.getElementById('byteCount');
const bitCount = document.getElementById('bitCount');
const txIndicator = document.getElementById('txIndicator');

// Live byte/bit counter
payloadInput.addEventListener('input', () => {
    const len = payloadInput.value.length;
    byteCount.textContent = len;
    bitCount.textContent = len * 8;
});

// Auto-detect restricted pages on popup open
(async () => {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab || !tab.url || tab.url.startsWith("chrome://") || tab.url.startsWith("chrome-extension://") || tab.url.startsWith("edge://") || tab.url.startsWith("about:")) {
            btn.disabled = true;
            btn.style.opacity = '0.3';
            btn.style.cursor = 'not-allowed';
            btn.innerText = "⚠  Restricted Page";
            statusText.innerText = "Navigate to a real website first";
            statusText.style.color = "#ff9500";
            statusDot.style.background = "#ff9500";
            statusDot.style.boxShadow = "0 0 6px #ff9500";
        }
    } catch (e) {
        console.warn("[TempestDrop] Tab check failed:", e);
    }
})();

btn.addEventListener('click', async () => {
    const payload = payloadInput.value;

    if (!isLeaking) {
        if (!payload) {
            statusText.innerText = "Error: Null Payload";
            statusText.style.color = "#ff6b6b";
            return;
        }

        // Convert string to binary
        const binary = payload.split('').map(char => char.charCodeAt(0).toString(2).padStart(8, '0')).join('');

        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!tab) throw new Error("No active tab found");

            console.log(`[TempestDrop] Injecting content script into tab ${tab.id}...`);

            // Programmatically inject content.js — works even on tabs that were
            // open before the extension was loaded (bypasses declarative-only limit)
            try {
                await chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    files: ['content.js']
                });
            } catch (injectErr) {
                // Script may already be injected (guard in content.js handles double-run)
                console.warn("[TempestDrop] Script inject warning (may already exist):", injectErr);
            }

            chrome.tabs.sendMessage(tab.id, { action: "start", payload: binary }, (response) => {
                if (chrome.runtime.lastError) {
                    console.error(chrome.runtime.lastError);
                    statusText.innerText = "Injection Failed";
                    statusText.style.color = "#ff6b6b";
                    alert("Injection Failed! Try refreshing the target page once, then click again.");
                } else {
                    // UI Update: Transition to ACTIVE state
                    btn.innerText = "■  Terminate Link";
                    btn.classList.add('active');

                    statusText.innerText = "TX Active — Signal Live";
                    statusText.style.color = "#ff003c";
                    statusDot.classList.add('active');
                    txIndicator.classList.add('active');
                    isLeaking = true;
                }
            });

        } catch (err) {
            statusText.innerText = "Critical Error";
            statusText.style.color = "#ff6b6b";
            console.error(err);
        }
    } else {
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (tab) {
                chrome.tabs.sendMessage(tab.id, { action: "stop" });
            }

            // UI Update: Revert to STANDBY state
            btn.innerText = "▶  Initiate Leak";
            btn.classList.remove('active');

            statusText.innerText = "System Standby";
            statusText.style.color = "#7a7a8a";
            statusDot.classList.remove('active');
            txIndicator.classList.remove('active');

            isLeaking = false;
        } catch (err) {
            console.error(err);
        }
    }
});
