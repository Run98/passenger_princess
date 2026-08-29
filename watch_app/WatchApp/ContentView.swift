import SwiftUI

/// Root view for the watch app. Capture-only: three tabs, no editing/review.
/// Kept intentionally minimal per CLAUDE.md ("as few buttons/screens as possible").
struct ContentView: View {
    var body: some View {
        TabView {
            TimestampView()
                .tag(0)
            VitalsView()
                .tag(1)
            DictationView()
                .tag(2)
        }
        .tabViewStyle(.page)
    }
}

#Preview {
    ContentView()
}
