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
