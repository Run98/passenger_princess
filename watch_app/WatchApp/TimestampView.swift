import SwiftUI
import WatchKit

/// One-tap event timestamps: Dispatch, On Scene, Patient Contact, Transport, Hospital Arrival.
/// Each tap sends {label, recorded_at} to the paired iPhone via WatchConnectivityManager.
struct TimestampView: View {
    static let labels = ["Dispatch", "On Scene", "Patient Contact", "Transport", "Hospital Arrival"]

    @State private var loggedLabels: Set<String> = []

    var body: some View {
        ScrollView {
            VStack(spacing: 8) {
                Text("Timestamps")
                    .font(.headline)
                ForEach(Self.labels, id: \.self) { label in
                    Button(action: { logTimestamp(label) }) {
                        HStack {
                            Text(label)
                            Spacer()
                            if loggedLabels.contains(label) {
                                Image(systemName: "checkmark.circle.fill")
                            }
                        }
                    }
                    .buttonStyle(.bordered)
                    .tint(loggedLabels.contains(label) ? .green : .blue)
                }
            }
            .padding(.horizontal, 4)
        }
    }

    private func logTimestamp(_ label: String) {
        let recordedAt = ISO8601DateFormatter().string(from: Date())
        WatchConnectivityManager.shared.sendTimestamp(label: label, recordedAt: recordedAt)
        loggedLabels.insert(label)
        WKInterfaceDevice.current().play(.click)
    }
}
