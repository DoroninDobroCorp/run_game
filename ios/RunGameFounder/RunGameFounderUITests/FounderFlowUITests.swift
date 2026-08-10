import XCTest

@MainActor
final class FounderFlowUITests: XCTestCase {
    private func launchedApp() -> XCUIApplication {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments.append("--ui-testing-reset")
        app.launch()
        return app
    }

    func testDashboardAndRouteWalkthroughOpen() {
        let app = launchedApp()
        XCTAssertTrue(app.staticTexts["Линия, которой нет"].waitForExistence(timeout: 4))
        XCTAssertTrue(app.staticTexts["Готовность устройства"].exists)
        XCTAssertTrue(app.staticTexts["Отдельный Mac gate: field review в binding"].exists)
        XCTAssertFalse(app.buttons["missionRunLink"].isEnabled)

        app.buttons["routeWalkthroughLink"].tap()
        XCTAssertTrue(app.navigationBars["Дневной обход"].waitForExistence(timeout: 4))
        XCTAssertTrue(app.staticTexts["Контрольные точки"].exists)
        XCTAssertTrue(app.staticTexts["Локальная запись GPX"].exists)
        XCTAssertFalse(app.buttons["routeApprovalButton"].isEnabled)
    }

    func testBundledMasterStartsPlayback() {
        let app = launchedApp()
        app.buttons["homeAudioLink"].tap()
        XCTAssertTrue(app.navigationBars["Проверка аудио"].waitForExistence(timeout: 4))
        let playPause = app.buttons["homeAudioPlayPause"]
        XCTAssertTrue(playPause.exists)
        XCTAssertFalse(app.buttons["homeAudioApprovalButton"].isEnabled)
        playPause.tap()
        XCTAssertTrue(app.buttons["Пауза"].waitForExistence(timeout: 4))
    }
}
