Seal Vision 1.7.3 — Moonlight input and NPC menu exit

- Before /elim, detect the Trade menu and its adjacent white Power/Exit button. Require two matching frames, click Exit, and wait for the NPC menu to disappear before focusing chat. This does not click the sale dialog X.
- Click the bottom chat input, use Enter if the caret is absent, clear retained text, verify an empty input, then type and visually verify one complete /elim before Enter.
- Send Windows keyboard input with virtual keys and scan codes. Allow 100 ms for mouse movement delivery and hold clicks for 180 ms so the streamed game receives them.
- Match the green Street Merchant nameplate, read isolated green text rows as a fallback, and search with bounded camera turns and pavement clicks. F7 learns a cropped nameplate from the current stream when a sample differs. Settings stay on the local PC.
- Keep the Sell Items button, five learned pink categories, first inventory page scan, right-click sale and verified O confirmation. F6 teaches categories. F9 stops. Unknown categories are skipped; missing visual evidence stops the sequence.
- Preserve the stable EXE and three-file SHA-256 validated runtime ZIP. Existing users can use Check for updates / Update now, or install the ZIP.

Validation: supplied NPC menu image matches Trade at 0.94 and Exit at 1.00. Controller tests verify two-frame Exit detection, adjacency, menu disappearance before chat, no click on sale confirmation during menu closing, allowed-category checks, O-only confirmation, command verification, unknown-item skip and scan completion. Runtime ZIP syntax and manifest checks pass.

Live status: mouse movement was verified with a short held click; all five category samples were learned locally. The complete warp-to-sale sequence has not completed successfully, and no items have been sold. The latest NPC-exit fix was tested against the supplied image; live control was stopped with Escape before retesting it.

The scan covers only the first unlocked inventory page (8 columns x 5 rows); it stops after selling and does not return to hunting. Navigation is bounded visual search, not a learned map or obstacle-aware pathfinder.

Only runtime modules and version.json are released. Full screenshots, accounts, addresses, inventory records, local nameplate/category samples and logs are excluded.
