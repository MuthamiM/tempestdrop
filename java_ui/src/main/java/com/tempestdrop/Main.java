package com.tempestdrop;

import javafx.application.Application;
import javafx.application.Platform;
import javafx.scene.Scene;
import javafx.scene.chart.LineChart;
import javafx.scene.chart.NumberAxis;
import javafx.scene.chart.XYChart;
import javafx.scene.control.TextArea;
import javafx.scene.layout.Priority;
import javafx.scene.layout.VBox;
import javafx.stage.Screen;
import javafx.stage.Stage;

import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;
import org.json.JSONObject;

import java.net.URI;

public class Main extends Application {

    private XYChart.Series<Number, Number> rawSeries;
    private XYChart.Series<Number, Number> filteredSeries;
    private TextArea terminalOut;
    private TextArea decodedOut;
    private javafx.scene.control.ProgressBar audioMeter;
    private javafx.scene.control.Label audioLabel;
    private int xTick = 0;
    
    // Simplistic binary accumulation string for the demo
    private StringBuilder incomingBits = new StringBuilder();
    private StringBuilder decodedText = new StringBuilder();

    @Override
    public void start(Stage primaryStage) {
        primaryStage.setTitle("TempestDrop // C2 Dashboard [Attacker UI]");

        // UI Layout
        VBox vbox = new VBox(10);
        vbox.setStyle("-fx-background-color: #121212; -fx-padding: 10px;");

        // Charts
        NumberAxis xAxisRaw = new NumberAxis();
        NumberAxis yAxisRaw = new NumberAxis();
        LineChart<Number, Number> rawChart = new LineChart<>(xAxisRaw, yAxisRaw);
        rawChart.setTitle("Raw Optical Signal (Ambient + Payload)");
        rawSeries = new XYChart.Series<>();
        rawChart.getData().add(rawSeries);
        rawChart.setCreateSymbols(false);
        rawChart.setStyle("-fx-text-fill: white;");

        NumberAxis xAxisFiltered = new NumberAxis();
        NumberAxis yAxisFiltered = new NumberAxis();
        LineChart<Number, Number> filteredChart = new LineChart<>(xAxisFiltered, yAxisFiltered);
        filteredChart.setTitle("DSP Demodulated Bandpass Output (10Hz Isolator)");
        filteredSeries = new XYChart.Series<>();
        filteredChart.getData().add(filteredSeries);
        filteredChart.setCreateSymbols(false);

        // Make charts grow equally to fill available space
        VBox.setVgrow(rawChart, Priority.ALWAYS);
        VBox.setVgrow(filteredChart, Priority.ALWAYS);
        rawChart.setMinHeight(150);
        filteredChart.setMinHeight(150);

        // Terminal Decoded Data
        terminalOut = new TextArea();
        terminalOut.setEditable(false);
        terminalOut.setStyle("-fx-control-inner-background: #000; -fx-text-fill: #00ff00; -fx-font-family: monospace; -fx-font-size: 16px;");
        terminalOut.setMinHeight(80);
        terminalOut.setPrefHeight(120);
        terminalOut.setMaxHeight(160);

        // Stolen Data Display
        decodedOut = new TextArea();
        decodedOut.setEditable(false);
        decodedOut.setStyle("-fx-control-inner-background: #1a0000; -fx-text-fill: #ff003c; -fx-font-family: monospace; -fx-font-size: 28px; -fx-font-weight: bold;");
        decodedOut.setMinHeight(80);
        decodedOut.setPrefHeight(100);
        decodedOut.setMaxHeight(140);
        decodedOut.setText("[STOLEN DATA] Waiting for signal...");

        // Audio Meter
        javafx.scene.layout.HBox audioBox = new javafx.scene.layout.HBox(10);
        audioBox.setStyle("-fx-padding: 5 10 5 10;");
        audioLabel = new javafx.scene.control.Label("\uD83C\uDFA4 MIC: idle");
        audioLabel.setStyle("-fx-text-fill: #00ccff; -fx-font-family: monospace; -fx-font-size: 13px;");
        audioLabel.setMinWidth(180);
        audioMeter = new javafx.scene.control.ProgressBar(0);
        audioMeter.setPrefWidth(400);
        audioMeter.setMaxWidth(Double.MAX_VALUE);
        audioMeter.setStyle("-fx-accent: #00ccff;");
        javafx.scene.layout.HBox.setHgrow(audioMeter, Priority.ALWAYS);
        audioBox.getChildren().addAll(audioLabel, audioMeter);

        vbox.getChildren().addAll(rawChart, filteredChart, audioBox, terminalOut, decodedOut);

        // Size the window to fit the screen
        var screenBounds = Screen.getPrimary().getVisualBounds();
        double width = Math.min(1000, screenBounds.getWidth() * 0.85);
        double height = Math.min(800, screenBounds.getHeight() * 0.9);
        Scene scene = new Scene(vbox, width, height);
        primaryStage.setScene(scene);
        primaryStage.setMaximized(true);
        primaryStage.show();

        // Start WebSocket Connection to Python Backend
        connectToPythonDSP();
    }

    private void connectToPythonDSP() {
        try {
            // Connect to the plain WebSocket server on port 5001
            // (Port 5000 is Flask-SocketIO with Engine.IO protocol, not raw WS compatible)
            WebSocketClient client = new WebSocketClient(new URI("ws://localhost:5001")) {
                @Override
                public void onOpen(ServerHandshake handshakedata) {
                    System.out.println("[+] Connected to Python DSP Engine!");
                    Platform.runLater(() -> terminalOut.appendText("[+] LINK ESTABLISHED: Analyzing Ambient Photons...\n"));
                }

                @Override
                public void onMessage(String message) {
                    try {
                        JSONObject data = new JSONObject(message);

                        // Handle audio level updates
                        if (data.has("type") && data.getString("type").equals("audio")) {
                            double rms = data.optDouble("rms", 0);
                            double peak = data.optDouble("peak", 0);
                            Platform.runLater(() -> {
                                audioMeter.setProgress(Math.min(1.0, rms / 0.15));
                                double db = rms > 0 ? 20 * Math.log10(rms) : -96;
                                audioLabel.setText(String.format("\uD83C\uDFA4 MIC: %.1f dB  pk:%.3f", db, peak));
                            });
                            return;
                        }

                        // Check if this is a decoded Manchester message
                        if (data.has("type") && data.getString("type").equals("decoded")) {
                            String event = data.optString("event", "");
                            Platform.runLater(() -> {
                                if (event.equals("sync")) {
                                    decodedOut.setText("[PREAMBLE LOCKED] Decoding...");
                                    decodedOut.setStyle("-fx-control-inner-background: #1a0000; -fx-text-fill: #ff003c; -fx-font-family: monospace; -fx-font-size: 28px; -fx-font-weight: bold;");
                                    terminalOut.appendText("\n[+] PREAMBLE DETECTED — Manchester sync locked!");
                                } else if (event.equals("char")) {
                                    String text = data.optString("text", "");
                                    String ch = data.optString("char", "");
                                    decodedText.setLength(0);
                                    decodedText.append(text);
                                    decodedOut.setText("[STOLEN] " + text + "\u2588");
                                    terminalOut.appendText(ch);
                                } else if (event.equals("end")) {
                                    String text = data.optString("text", "");
                                    decodedOut.setText("[STOLEN] " + text + "  \u2713");
                                    decodedOut.setStyle("-fx-control-inner-background: #001a00; -fx-text-fill: #00ff41; -fx-font-family: monospace; -fx-font-size: 28px; -fx-font-weight: bold;");
                                    terminalOut.appendText("\n[+] TX COMPLETE: " + text.length() + " bytes recovered \u2714");
                                }
                            });
                            return;
                        }

                        double rawLuma = data.getDouble("raw_luma");
                        double filteredLuma = data.getDouble("filtered_luma");
                        int bit = data.getInt("digital_bit");

                        Platform.runLater(() -> {
                            // Chart Updates
                            rawSeries.getData().add(new XYChart.Data<>(xTick, rawLuma));
                            filteredSeries.getData().add(new XYChart.Data<>(xTick, filteredLuma));
                            
                            // Keep memory safe by removing old data
                            if (rawSeries.getData().size() > 200) {
                                rawSeries.getData().remove(0);
                                filteredSeries.getData().remove(0);
                            }
                            xTick++;

                            // Terminal Text Decoding Updates
                            incomingBits.append(bit);
                            if (xTick % 60 == 0) {
                                terminalOut.appendText("\n[STREAM]: ");
                            }
                            terminalOut.appendText(String.valueOf(bit));
                        });

                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }

                @Override
                public void onClose(int code, String reason, boolean remote) {
                    System.out.println("[-] Connection closed: " + reason);
                }

                @Override
                public void onError(Exception ex) {
                    ex.printStackTrace();
                }
            };
            client.connect();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        launch(args);
    }
}
