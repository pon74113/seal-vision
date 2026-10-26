Seal Vision 1.7.1 — live-test input fixes

- Send real absolute mouse movement for Moonlight/SDL hover handling and include keyboard scan codes.
- Correct chat click position; use Enter on the retry path and require visible /elim before submission.
- Make calibration window selectable and account for its frame offset, including fullscreen game-area selection.
- Bound text OCR detector size and retain results until consumed; add inference diagnostics.
- Five category labels were successfully taught from the live Moonlight inventory in the local test. They remain private local settings.
- Live selling has NOT completed: the test stopped before selling because chat command entry/recognition was not confirmed. No items were sold during that test. Continue with chat focus setup before relying on automated navigation or selling.

Seal Vision 1.7 supports Moonlight instead of requiring AnyDesk.

- Existing users: click Check for updates, then Update now. The original EXE and SHA-256 manifest validation remain compatible.
- Set the game image rectangle (exclude black borders, title bars and taskbars), then set the AP-number rectangle for combat mode.
- Teach all five allowed pink category labels once: select the category in Seal Vision, hover an inventory item in Moonlight, press F6. Relearn after changing stream resolution or game UI scale. This uses the category text, not item names or icon colors.
- The Sell Items button runs `/elim`, verifies it in the bottom chat input, locates the green Street Merchant name, opens Trade, scans the first unlocked inventory tab (8 columns × 5 rows), and sells only learned categories. It checks the sale phrase and O/X layout and clicks O only. Unknown items are skipped.
- If the merchant is not visible, search alternates bounded upper-left ground clicks with right-drag camera turns. F9 stops. Focus loss, unknown dialogs, timeouts or missing visual evidence stop the sequence. The app does not resume combat or walk back to the hunting area after selling.
- Use English keyboard layout on both computers. A failed command is retried by clicking chat; unverified text is never submitted.
- Faster scanning: approximately 250 ms initial tooltip wait and 120 ms verification, plus capture/matching/network latency. No fixed long wait for each confirmed sale.

Validation: visual anchors, tooltip selection, negative/blank-image rejection, manifest integrity and controller simulation checked locally against supplied screenshots. Live Moonlight selling/navigation has not been verified. First use requires game-area calibration and five category samples. The program does not learn arbitrary maps or guarantee a route around obstacles. Do not use on valuable inventory until live recognition has been checked.

Only runtime modules and version.json are included. No addresses, user settings, full screenshots, accounts, inventory records or logs are published.
