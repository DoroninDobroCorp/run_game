import XCTest

final class FounderFlowUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launch()
    }

    func testDashboardAndRouteWalkthroughOpen() {
        XCTAssertTrue(app.staticTexts["Линия, которой нет"].waitForExistence(timeout: 4))
        XCTAssertTrue(app.staticTexts["Готовность к миссии"].exists)
        XCTAssertFalse(app.buttons["missionRunLink"].isEnabled)

        app.buttons["routeWalkthroughLink"].tap()
        XCTAssertTrue(app.navigationBars["Дневной обход"].waitForExistence(timeout: 4))
        XCTAssertTrue(app.staticTexts["Контрольные точки"].exists)
        XCTAssertTrue(app.staticTexts["Локальная запись GPX"].exists)
    }

    func testBundledMasterStartsPlayback() {
        app.buttons["homeAudioLink"].tap()
        XCTAssertTrue(app.navigationBars["Проверка аудио"].waitForExistence(timeout: 4))
        let playPause = app.buttons["homeAudioPlayPause"]
        XCTAssertTrue(playPause.exists)
        playPause.tap()
        XCTAssertTrue(app.buttons["Пауза"].waitForExistence(timeout: 4))
    }
}
