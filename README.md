# Seal Vision 1.7.3 — Moonlight

Windows foreground image helper for Seal through Moonlight. Existing users can update the original stable SealVision.exe through Check for updates, or load SealVision-update-1.7.3.zip manually. The SHA-256 manifest and launcher_min 1 remain compatible.

## Setup

1. Open a connected Moonlight game stream; use English keyboard layout on both PCs.
2. Drag a rectangle around the actual game image, excluding black borders, title bars and taskbars. Include the bottom chat input.
3. For combat, drag a rectangle around only the AP numbers.
4. For selling, select each pink category in Seal Vision, hover a matching inventory item in Moonlight, then press F6: รองเท้า, ส่วนหัว, ท่อนบน, อาวุธ, ท่อนล่าง. The nearest tooltip is used, excluding the equipped-item comparison. Relearn after stream resolution or game UI scale changes.

5. If the sample nameplate does not match the stream, stop with F9, point at the middle of the visible Street Merchant name and press F7 once. This saves only the cropped nameplate locally. Relearn after changing resolution/UI scale.

## Controls

- F8 starts the selected mode. Combat retains Tab targeting, 1/2 skills, 3 below 50% AP, Space for red bags, and the optional three-cycle test.
- ขายไอเทม starts the complete sale sequence: close an open NPC menu using its white Power/Exit button, wait for the menu to disappear, focus bottom chat, clear retained text, type and verify /elim, Enter, locate the green Street Merchant name, open Trade, scan inventory, match a learned pink category, right-click, verify the sale phrase and O/X layout, then click O. Item names may vary. X is never clicked automatically.
- Merchant search inspects camera angles before making small upper-left ground clicks. It uses the green nameplate image, with OCR on isolated green text rows as a fallback. It stops after 60 moves or 10 minutes. This is bounded visual search, not general map learning or obstacle-aware navigation.
- F9 stops. Focus loss stops selling. Unknown tooltips are skipped. Missing shop/confirmation evidence stops the sequence.
- Only the first unlocked inventory page is scanned: 8 columns by 5 rows. Tabs 2/3 and scrolling are not scanned. The program stops after selling; it does not return to a hunting location.

## Validation and updates

Visual anchors and controller behavior were tested locally against supplied screenshots, including unknown-category and missing-confirmation rejection. Live Moonlight navigation and selling have not been verified. Inspect live recognition before using valuable inventory.

Run python build_update.py for the three-file runtime ZIP. A change to release-version.txt on main triggers the release workflow. User labels, calibration, addresses, accounts, logs and full screenshots are excluded from releases.
