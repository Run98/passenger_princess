import Foundation

/// A tiny disk-backed queue for captures that couldn't be synced to the
/// backend yet (no wifi/cellular/Bluetooth-to-backend connectivity).
/// Captures persist across app relaunches and are retried once connectivity
/// returns -- see CLAUDE.md's "offline-first" design principle.
final class OfflineQueue {
    static let shared = OfflineQueue()

    private let fileURL: URL
    private var queue: [QueuedItem] = []

    struct QueuedItem: Codable {
        let callId: String
        let endpointPath: String   // e.g. "/api/calls/<id>/timestamps"
        let payload: [String: AnyCodable]
    }

    private init() {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        fileURL = dir.appendingPathComponent("offline_queue.json")
        load()
    }

    func enqueue(callId: String, endpointPath: String, payload: [String: AnyCodable]) {
        queue.append(QueuedItem(callId: callId, endpointPath: endpointPath, payload: payload))
        persist()
    }

    func pending() -> [QueuedItem] { queue }

    func removeFirst(_ n: Int) {
        queue.removeFirst(min(n, queue.count))
        persist()
    }

    private func persist() {
        if let data = try? JSONEncoder().encode(queue) {
            try? data.write(to: fileURL)
        }
    }

    private func load() {
        guard let data = try? Data(contentsOf: fileURL),
              let items = try? JSONDecoder().decode([QueuedItem].self, from: data) else { return }
        queue = items
    }
}

/// Minimal type-erased Codable wrapper so the queue can store mixed JSON payloads.
struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) { self.value = value }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let v = try? container.decode(String.self) { value = v }
        else if let v = try? container.decode(Int.self) { value = v }
        else if let v = try? container.decode(Double.self) { value = v }
        else if let v = try? container.decode(Bool.self) { value = v }
        else { value = "" }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case let v as String: try container.encode(v)
        case let v as Int: try container.encode(v)
        case let v as Double: try container.encode(v)
        case let v as Bool: try container.encode(v)
        default: try container.encode("")
        }
    }
}
