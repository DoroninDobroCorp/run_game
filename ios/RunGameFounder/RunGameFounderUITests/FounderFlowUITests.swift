import XCTest

@MainActor
final class FounderFlowUITests: XCTestCase {
    private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<8 {
            if element.isHittable { return }
            app.swipeUp()
        }
        XCTAssertTrue(element.isHittable, "Control should be reachable by scrolling: \(element.identifier)")
    }
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
        XCTAssertTrue(app.staticTexts["Полевой маршрут подтверждён"].exists)
        XCTAssertFalse(app.buttons["missionRunLink"].isEnabled)

        let walkthroughLink = app.buttons["routeWalkthroughLink"]
        XCTAssertTrue(walkthroughLink.exists)
        reveal(walkthroughLink, in: app)
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
        reveal(homeAudioLink, in: app)
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
        reveal(walkthroughLink, in: app)
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
        reveal(app.buttons["homeAudioLink"], in: app)
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

    func testRehearsalCompletesAndDoesNotUnlockPhysicalMission() {
        let app = launchedApp()
        let link = app.buttons["rehearsalLink"]
        XCTAssertTrue(link.waitForExistence(timeout: 5))
        reveal(link, in: app)
        link.tap()
        XCTAssertTrue(app.navigationBars["Тестовый забег"].waitForExistence(timeout: 5))
        let speed = app.segmentedControls["rehearsalSpeed"]
        reveal(speed, in: app)
        speed.buttons["120× · 15 с"].tap()
        let play = app.buttons["rehearsalPlayPause"]
        reveal(play, in: app)
        play.tap()
        XCTAssertTrue(app.staticTexts["rehearsalResult"].waitForExistence(timeout: 30))
        XCTAssertTrue(app.staticTexts["Тестовый круг пройден"].exists)
        app.navigationBars["Тестовый забег"].buttons.element(boundBy: 0).tap()
        reveal(link, in: app)
        link.tap()
        XCTAssertTrue(app.staticTexts["rehearsalResult"].waitForExistence(timeout: 5), "Returning to the test must preserve its result")
        let reset = app.buttons["rehearsalReset"]
        reveal(reset, in: app)
        reset.tap()
        XCTAssertFalse(app.staticTexts["rehearsalResult"].exists)
        app.navigationBars["Тестовый забег"].buttons.element(boundBy: 0).tap()
        XCTAssertFalse(app.buttons["missionRunLink"].isEnabled)
        XCTAssertFalse(app.staticTexts["Незавершённый immediate-дебриф"].exists)
        XCTAssertFalse(app.staticTexts["24-часовой recall"].exists)
    }

    func testRehearsalPausesAndPreservesProgressAcrossNavigationAndBackground() {
        let app = launchedApp()
        let link = app.buttons["rehearsalLink"]
        XCTAssertTrue(link.waitForExistence(timeout: 5))
        reveal(link, in: app)
        link.tap()
        let play = app.buttons["rehearsalPlayPause"]
        let clock = app.staticTexts["rehearsalClock"]
        reveal(play, in: app)
        play.tap()
        let progressed = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            clock.label != "00:00"
        }, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [progressed], timeout: 5), .completed)
        play.tap()
        let pausedTime = clock.label
        XCTAssertTrue(play.label.contains("Продолжить"))

        app.navigationBars["Тестовый забег"].buttons.element(boundBy: 0).tap()
        reveal(link, in: app)
        link.tap()
        XCTAssertEqual(clock.label, pausedTime)
        reveal(play, in: app)
        XCTAssertTrue(play.label.contains("Продолжить"))
        play.tap()

        XCUIDevice.shared.press(.home)
        app.activate()
        XCTAssertTrue(play.waitForExistence(timeout: 5))
        XCTAssertTrue(play.label.contains("Продолжить"), "Backgrounding must pause the rehearsal")
        let returnedTime = clock.label
        let advancedWhilePaused = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            clock.label != returnedTime
        }, object: nil)
        advancedWhilePaused.isInverted = true
        XCTAssertEqual(XCTWaiter.wait(for: [advancedWhilePaused], timeout: 1), .completed)
    }
}
