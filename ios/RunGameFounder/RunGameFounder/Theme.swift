import SwiftUI

enum RunGameTheme {
    static let ink = Color(red: 0.035, green: 0.045, blue: 0.075)
    static let panel = Color(red: 0.075, green: 0.09, blue: 0.14)
    static let electric = Color(red: 0.37, green: 0.92, blue: 0.72)
    static let violet = Color(red: 0.58, green: 0.49, blue: 1.0)
    static let warning = Color(red: 1.0, green: 0.66, blue: 0.28)
    static let danger = Color(red: 1.0, green: 0.31, blue: 0.38)
}

struct PanelModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(18)
            .background(RunGameTheme.panel.opacity(0.95), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .stroke(Color.white.opacity(0.07), lineWidth: 1)
            }
    }
}

extension View {
    func runGamePanel() -> some View { modifier(PanelModifier()) }
}
