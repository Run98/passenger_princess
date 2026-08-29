import WatchConnectivity
import Foundation

/// Receives captures relayed from the watch (over Bluetooth via Watch
/// Connectivity) and forwards them to the FastAPI backend over HTTP.
/// If the backend isn't reachable, captures are queued to disk
/// (OfflineQueue) and retried -- see CLAUDE.md's offline-first + Bluetooth
/// fallback sync design.
final class PhoneConnectivityManager: NSObject, WCSessionDelegate {
    static let shared = PhoneConnectivityManager()

    /// Set this to your backend's address. For a demo without venue wifi,
    /// this can point to a Bluetooth PAN / personal-hotspot address on the
    /// laptop running the FastAPI server (see CLAUDE.md "Sync / transport details").
    var backendBaseURL = URL(string: "http://192.168.1.100:8000")!

    /// The active call ID this session's captures should be attached to.
    /// In the demo flow, this is set once when a new call starts.
    var activeCallId: String = ""

    private let session = WCSession.default

    override init() {
        super.init()
        if WCSession.isSupported() {
            session.delegate = self
            session.activate()
        }
        retryQueueIfPossible()
    }

    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {}
    func sessionDidBecomeInactive(_ session: WCSession) {}
    func sessionDidDeactivate(_ session: WCSession) { session.activate() }

    // MARK: - Receiving from watch

    func session(_ session: WCSession, didReceiveUserInfo userInfo: [String: Any] = [:]) {
        guard let type = userInfo["type"] as? String, !activeCallId.isEmpty else { return }

        switch type {
        case "timestamp":
            forward(path: "/api/calls/\(activeCallId)/timestamps", body: [
                "label": userInfo["label"] as? String ?? "",
                "recorded_at": userInfo["recorded_at"] as? String ?? "",
            ])
        case "vitals":
            forward(path: "/api/calls/\(activeCallId)/vitals", body: [
                "bp": userInfo["bp"] as? String ?? "",
                "hr": userInfo["hr"] as? Int ?? 0,
                "spo2": userInfo["spo2"] as? Int ?? 0,
                "rr": userInfo["rr"] as? Int ?? 0,
                "gcs": userInfo["gcs"] as? Int ?? 0,
                "glucose": userInfo["glucose"] as? Int ?? 0,
            ])
        case "dictation":
            forward(path: "/api/calls/\(activeCallId)/dictations", body: [
                "text": userInfo["text"] as? String ?? "",
            ])
        default:
            break
        }
    }

    // MARK: - Forwarding to backend (with offline fallback)

    private func forward(path: String, body: [String: Any]) {
        guard let url = URL(string: path, relativeTo: backendBaseURL),
              let jsonData = try? JSONSerialization.data(withJSONObject: body) else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = jsonData
        request.timeoutInterval = 5

        URLSession.shared.dataTask(with: request) { _, response, error in
            let ok = (response as? HTTPURLResponse)?.statusCode == 200
            if error != nil || !ok {
                // No connectivity to backend right now -- queue for later.
                let encoded = body.mapValues { AnyCodable($0) }
                OfflineQueue.shared.enqueue(callId: self.activeCallId, endpointPath: path, payload: encoded)
            }
        }.resume()
    }

    /// Call periodically (e.g. on app foreground, or on a timer) to flush
    /// anything queued while offline.
    func retryQueueIfPossible() {
        let items = OfflineQueue.shared.pending()
        guard !items.isEmpty else { return }
        for item in items {
            let body = item.payload.mapValues { $0.value }
            forward(path: item.endpointPath, body: body)
        }
        OfflineQueue.shared.removeFirst(items.count)
    }
}
