import SwiftUI
import WatchKit

/// Quick vitals entry via Digital Crown-driven steppers -- fast tap entry,
/// no typing. Sends a full vitals snapshot to the iPhone on "Log Vitals".
struct VitalsView: View {
    @State private var systolic: Int = 120
    @State private var diastolic: Int = 80
    @State private var hr: Int = 80
    @State private var spo2: Int = 98
    @State private var rr: Int = 16
    @State private var gcs: Int = 15
    @State private var glucose: Int = 100

    var body: some View {
        ScrollView {
            VStack(spacing: 10) {
                Text("Vitals").font(.headline)

                vitalStepper("BP Sys", value: $systolic, range: 60...220)
                vitalStepper("BP Dia", value: $diastolic, range: 30...140)
                vitalStepper("HR", value: $hr, range: 30...220)
                vitalStepper("SpO2", value: $spo2, range: 50...100)
                vitalStepper("RR", value: $rr, range: 4...50)
                vitalStepper("GCS", value: $gcs, range: 3...15)
                vitalStepper("Glucose", value: $glucose, range: 20...500)

                Button("Log Vitals") {
                    logVitals()
                }
                .buttonStyle(.borderedProminent)
                .tint(.blue)
            }
            .padding(.horizontal, 4)
        }
    }

    private func vitalStepper(_ label: String, value: Binding<Int>, range: ClosedRange<Int>) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("\(label): \(value.wrappedValue)")
                .font(.caption)
            Stepper("", value: value, in: range)
                .labelsHidden()
        }
    }

    private func logVitals() {
        WatchConnectivityManager.shared.sendVitals(
            bp: "\(systolic)/\(diastolic)",
            hr: hr, spo2: spo2, rr: rr, gcs: gcs, glucose: glucose
        )
        WKInterfaceDevice.current().play(.success)
    }
}
