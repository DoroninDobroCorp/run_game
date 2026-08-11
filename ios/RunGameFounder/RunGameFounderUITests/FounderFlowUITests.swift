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

        let walkthroughLink = app.buttons["routeWalkthroughLink"]
        XCTAssertTrue(walkthroughLink.exists)
        app.swipeUp()
        walkthroughLink.tap()

        XCTAssertTrue(app.navigationBars["Дневной обход"].waitForExistence(timeout: 4))
        XCTAssertTrue(app.staticTexts["Контрольные точки"].exists)
        XCTAssertTrue(app.staticTexts["Локальная запись GPX"].exists)

        let startWalkthrough = app.buttons["startWalkthroughButton"]
        XCTAssertTrue(startWalkthrough.exists)

        let routeApproval = app.buttons["routeApprovalButton"]
        XCTAssertTrue(routeApproval.exists)
        XCTAssertFalse(routeApproval.isEnabled)
    }

    func testBundledMasterStartsPlayback() {
        let app = launchedApp()
        let homeAudioLink = app.buttons["homeAudioLink"]
        XCTAssertTrue(homeAudioLink.exists)
        app.swipeUp()
        homeAudioLink.tap()

        XCTAssertTrue(app.navigationBars["Проверка аудио"].waitForExistence(timeout: 4))
        let playPause = app.buttons["homeAudioPlayPause"]
        XCTAssertTrue(playPause.exists)
        XCTAssertTrue(playPause.isHittable)

        let approvalButton = app.buttons["homeAudioApprovalButton"]
        XCTAssertTrue(approvalButton.exists)
        XCTAssertFalse(approvalButton.isEnabled)

        playPause.tap()
        XCTAssertTrue(app.buttons["Пауза"].waitForExistence(timeout: 4))
    }

    func testCompactScreenLayoutAndAccessibilityIdentifiers() {
        let app = launchedApp()

        // 1. Dashboard controls and identifiers
        let walkthroughLink = app.buttons["routeWalkthroughLink"]
        let homeAudioLink = app.buttons["homeAudioLink"]
        let missionRunLink = app.buttons["missionRunLink"]

        XCTAssertTrue(walkthroughLink.waitForExistence(timeout: 4))
        XCTAssertTrue(homeAudioLink.exists)
        XCTAssertTrue(missionRunLink.exists)

        XCTAssertEqual(missionRunLink.identifier, "missionRunLink")

        // 2. Route Walkthrough controls & labels
        app.swipeUp()
        walkthroughLink.tap()
        XCTAssertTrue(app.navigationBars["Дневной обход"].waitForExistence(timeout: 4))

        let startWalkthrough = app.buttons["startWalkthroughButton"]
        let routeApproval = app.buttons["routeApprovalButton"]

        XCTAssertTrue(startWalkthrough.exists)
        XCTAssertTrue(routeApproval.exists)
        XCTAssertEqual(startWalkthrough.identifier, "startWalkthroughButton")
        XCTAssertEqual(routeApproval.identifier, "routeApprovalButton")

        // Navigate back
        app.navigationBars["Дневной обход"].buttons.element(boundBy: 0).tap()
        XCTAssertTrue(app.staticTexts["Линия, которой нет"].waitForExistence(timeout: 4))

        // 3. Home Audio Check controls & labels
        app.swipeUp()
        app.buttons["homeAudioLink"].tap()
        XCTAssertTrue(app.navigationBars["Проверка аудио"].waitForExistence(timeout: 4))

        let homeAudioPlayPause = app.buttons["homeAudioPlayPause"]
        let homeAudioApproval = app.buttons["homeAudioApprovalButton"]

        XCTAssertTrue(homeAudioPlayPause.exists)
        XCTAssertTrue(homeAudioApproval.exists)
        XCTAssertEqual(homeAudioPlayPause.identifier, "homeAudioPlayPause")
        XCTAssertEqual(homeAudioApproval.identifier, "homeAudioApprovalButton")

        // Navigate back
        app.navigationBars["Проверка аудио"].buttons.element(boundBy: 0).tap()
        XCTAssertTrue(app.staticTexts["Линия, которой нет"].waitForExistence(timeout: 4))
    }

    func testEvidenceLockNavigationalDestinationsDisabled_WhenPendingDebrief() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments.append("--ui-testing-reset")
        app.launchArguments.append("--ui-testing-pending-debrief")
        app.launch()

        XCTAssertTrue(app.staticTexts["Линия, которой нет"].waitForExistence(timeout: 4))
        XCTAssertTrue(app.staticTexts["Незавершённый immediate-дебриф"].exists)

        let walkthroughLink = app.buttons["routeWalkthroughLink"]
        let homeAudioLink = app.buttons["homeAudioLink"]
        let missionRunLink = app.buttons["missionRunLink"]

        XCTAssertTrue(walkthroughLink.exists)
        XCTAssertTrue(homeAudioLink.exists)
        XCTAssertTrue(missionRunLink.exists)

        XCTAssertFalse(walkthroughLink.isEnabled)
        XCTAssertFalse(homeAudioLink.isEnabled)
        XCTAssertFalse(missionRunLink.isEnabled)
    }

    func testPendingRecallNavigationalDestinationsDisabled_WhenPendingRecall() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments.append("--ui-testing-reset")
        app.launchArguments.append("--ui-testing-pending-recall")
        app.launch()

        XCTAssertTrue(app.staticTexts["Линия, которой нет"].waitForExistence(timeout: 4))
        XCTAssertTrue(app.staticTexts["24-часовой recall"].exists)

        let walkthroughLink = app.buttons["routeWalkthroughLink"]
        let homeAudioLink = app.buttons["homeAudioLink"]
        let missionRunLink = app.buttons["missionRunLink"]

        XCTAssertTrue(walkthroughLink.exists)
        XCTAssertTrue(homeAudioLink.exists)
        XCTAssertTrue(missionRunLink.exists)

        XCTAssertFalse(walkthroughLink.isEnabled)
        XCTAssertFalse(homeAudioLink.isEnabled)
        XCTAssertFalse(missionRunLink.isEnabled)
    }
}
