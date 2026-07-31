# Regression test plan

1. Adapter command sequences
   - Assert direct `wield`, `wear`, `drop`, `read`, `quaff`, and `eat` commands
     expand to the native command plus `?`.
   - Assert new top-level and run commands map to exact C bytes.

2. Indexed stores
   - Detect a store screen containing a blank separator.
   - Assert each option records its physical row and selection emits the
     correct number of `j` keys.

3. Inventory equipment actions
   - Assert wielded items expose `Unwield`, worn items expose `Take Off`, and
     ordinary items expose only valid actions.
   - Assert action callbacks produce exact C replay bytes.

4. Numeric keypad
   - Assert the keyboard renders digits, backspace, maximum, submit, and
     cancellation.
   - Assert callback parsing limits drafts to C `long` size and submit produces
     the existing `number:` adapter command.

5. Command UI and callback safety
   - Assert every meaningful mapped C command is reachable from a keyboard.
   - Assert callback construction rejects payloads over 64 UTF-8 bytes.

6. Validation
   - Run focused pytest files after each phase.
   - Run full pytest and Ruff once after all changes.
   - Review new assertions and record the final result in
     `.testagent/status.md`.

## Development support extension

1. Assert `⭐ Support Development ⭐` is strictly between `Legend` and
   `Main Menu`.
2. Assert the submenu exposes the exact Ko-fi URL and the 50/100/250 Telegram
   Stars choices.
3. Exercise invoice construction, pre-checkout validation, payment persistence,
   thanks, `/paysupport`, and `/terms`.
4. Run focused tests, the full suite, Ruff, and diff checks.

## Menu regression extension

1. Assert the ordinary main menu keeps Resume, renames the story action to
   Plot, adds About immediately below it, and removes Repository.
2. Assert Main Menu opened from the in-game menu has a final Back button that
   returns to the game menu while Resume remains available.
3. Exercise Resume through the registered callback handler and assert that it
   edits the current game response directly without sending splash photos.
4. Exercise Plot and About callbacks. Plot must retain the story; About must
   show the deployed runtime version, Simon Borin as author, and the canonical
   GitHub URL without a Repository menu action or work-account attribution.
5. Exercise Stars selection and assert it reuses the existing message, exposes
   a Back path, and does not call `answer_invoice`, `answer`, or another
   new-message API.
6. Run the focused regressions and record exact results below.

## Beta feedback and canonical-link extension

1. Parse README content and require a visible Beta heading, beta wording, an
   issue-report invitation, and the canonical GitHub Issues link.
2. Parse the Pages HTML as visible text and anchors; require beta/issue wording,
   the canonical Issues link, and the canonical repository link.
3. Format the bot About template and require the canonical Pages URL.
4. Run the new static tests together with the existing About callback
   regression, then run Ruff and `git diff --check`.

## Contextual Main Menu navigation extension

1. Build each regression as a callback sequence beginning with Game Menu,
   selecting the Main Menu button rendered by that handler, and invoking the
   generic Main Menu callback on the same active message.
2. Parameterize About, Plot, Legend, Rules, and Display Size; follow each
   section's rendered Main Menu control and assert the restored Main Menu ends
   in `Back -> GAME_MENU`.
3. Traverse both Rules details through Rules and then Main Menu, asserting that
   context survives every edit.
4. Traverse invalid and all valid Display Size selections. Invalid selection
   must keep the contextual Back; valid selections must return to game controls
   without introducing a context-free Main Menu callback.
5. Traverse Restart Game -> Cancel and assert the restored Main Menu retains
   its bottom game-menu Back.
6. Invoke `/start` and `/menu` handlers with inactive context and assert they
   remain context-free.
7. Force the active photo-message replacement path and assert the newly sent
   chat/message identity is persisted before the next click.
8. Run focused pytest and Ruff, then perform mutation-oriented gap and
   assertion-quality review.

## Game-over screenshot and public credits identity extension

1. Update the existing credits test to require `@SimonBorin` and explicitly
   reject `Simon.A.Borin` and `@ringcentral.com`.
2. Require a credits cache namespace newer than the historical `credits-v5`
   value so existing rendered frames cannot preserve the removed identity.
3. Add README and Pages regressions rejecting both `End of a run` and
   `tglarn-game-over.png`.
4. Assert the screenshot files are absent from both `docs/screenshots/` and
   `site/assets/`, not merely unreferenced.
5. Run the focused animation/static-page tests and Ruff, then record
   requirement mapping and mutation-oriented assertion review.
