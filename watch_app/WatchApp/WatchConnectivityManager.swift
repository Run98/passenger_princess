import WatchConnectivity

/// Sends captured data (timestamps, vitals, dictation) from the watch to the
/// paired iPhone over Watch Connectivity, which uses Bluetooth automatically --
/// no internet needed for this leg (see CLAUDE.md "Sync / transport details").
final class WatchConnectivityManager: NSObject, WCSessionDelegate {
    static let shared = WatchConnectivityManager()

    private let session = WCSession.default

    override init() {
        super.init()
        if WCSession.isSupported() {
            session.delegate = self
            session.activate()
        }
    }

    func sendTimestamp(label: String, recordedAt: String) {
        send(["type": "timestamp", "label": label, "recorded_at": recordedAt])
    }

    func sendVitals(bp: String, hr: Int, spo2: Int, rr: Int, gcs: Int, glucose: Int) {
        send([
            "type": "vitals",
            "bp": bp, "hr": hr, "spo2": spo2, "rr": rr, "gcs": gcs, "glucose": glucose,
        ])
    }

    func sendDictation(text: String) {
        send(["type": "dictation", "text": text])
    }

    private func send(_ payload: [String: Any]) {
        // transferUserInfo queues reliably and delivers even if the phone
        // app isn't foregrounded -- important since EMTs won't be checking
        // their phone mid-call.
        session.transferUserInfo(payload)
    }

    // MARK: - WCSessionDelegate (required, minimal handling for a watch app)

    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {}
}
