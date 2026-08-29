import SwiftUI
import WatchKit

/// Single tap to start/stop voice dictation. Transcription happens
/// on-device (SpeechRecognizer); the resulting text is sent to the
/// iPhone once recording stops. No editing here -- capture only.
struct DictationView: View {
    @StateObject private var recognizer = SpeechRecognizer()
    @State private var lastSentText: String = ""

    var body: some View {
        VStack(spacing: 12) {
            Text("Dictation").font(.headline)

            Button(action: toggleRecording) {
                Image(systemName: recognizer.isRecording ? "mic.fill" : "mic")
                    .font(.system(size: 36))
                    .foregroundColor(recognizer.isRecording ? .red : .blue)
            }
            .buttonStyle(.plain)

            Text(recognizer.isRecording ? "Listening..." : "Tap to dictate")
                .font(.caption)
                .foregroundColor(.gray)

            if !lastSentText.isEmpty {
                Text("Sent: \"\(lastSentText)\"")
                    .font(.caption2)
                    .foregroundColor(.green)
                    .lineLimit(2)
            }
        }
        .onAppear {
            recognizer.requestAuthorization { _ in }
        }
    }

    private func toggleRecording() {
        if recognizer.isRecording {
            recognizer.stopRecording()
            let text = recognizer.transcript.trimmingCharacters(in: .whitespacesAndNewlines)
            if !text.isEmpty {
                WatchConnectivityManager.shared.sendDictation(text: text)
                lastSentText = text
            }
            WKInterfaceDevice.current().play(.stop)
        } else {
            recognizer.startRecording()
            WKInterfaceDevice.current().play(.start)
        }
    }
}
