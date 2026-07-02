# Game Rules

`tglarn` follows the original ReLarn/Larn rules through the upstream C engine. Python does not reimplement combat, inventory, economy, dungeon generation, or win/loss logic. It acts as an adapter around the terminal interface.

High-level rules exposed by the wrapper:

- The player controls one adventurer in a turn-based roguelike dungeon.
- Movement commands include cardinal and diagonal directions.
- The world contains monsters, traps, items, gold, stairs, stores, banks, schools, tax prompts, and modal events from the C game.
- Inventory interaction uses terminal picklists and item action submenus.
- Stores include buy flows, sell flows, indexed item lists, sale multi-selection, invoice confirmation, and explicit exit states.
- Banks and tax systems require numeric prompts for deposits, withdrawals, and payments.
- The player can lose through death, failed survival conditions, or other game-over states controlled by ReLarn.
- The player wins by recovering the cure objective and satisfying the original game completion conditions.

# Scope Definition

The MVP scope is a Telegram direct-chat wrapper for isolated single-player ReLarn sessions. The bot supports many players in parallel, but each player has an independent session document and game state.

The public playable Telegram bot is available at [@tglarnbot](https://t.me/tglarnbot).

In scope:

- Isolated per-user sessions keyed primarily by Telegram user ID, with active Telegram chat and message IDs tracked for UI validation.
- Non-interactive background adapter execution slots for blocking C-engine calls. The implementation does not keep one permanent C process per player; each ReLarn cycle is run through a controlled subprocess and PTY lifecycle.
- State serialization through MongoDB session documents, including native ReLarn save blobs encoded as base64.
- Separation between local integration code and the upstream `vendor/relarn/` tree.
- Contextual inline keyboards for movement, menus, inventory, stores, prompts, confirmations, and modal screens.
- Text fallback for direct command entry and numeric prompt entry.
- Crash-safe service boundaries that prevent adapter failures from corrupting persisted state.

Out of scope:

- Multiplayer shared worlds.
- Group-chat gameplay.
- Rewriting ReLarn mechanics in Python.
- Modifying upstream C gameplay rules for Telegram convenience.
- Browser-only gameplay.

# Functional Requirements

- Route Telegram interactions by direct-chat context and Telegram user identity.
- Store active `chat_id` and `message_id` values so stale inline callbacks can be rejected before a game command is executed.
- Maintain one MongoDB session document per player with `engine_state`, `last_screen`, `last_log`, `last_status`, `map_view`, active message metadata, and `state_version`.
- Generate dynamic, contextual inline keyboards from `GameResponse.actions` and pending prompt metadata.
- Expose the production game entry point through the public Telegram handle `@tglarnbot`.
- Keep inline button labels emoji-free, using labels such as `Cancel`, `Main Menu`, `Confirm sale`, `Decline`, `Finish sale`, and `Exit Store`.
- Support lettered picklists, indexed picklists, direction prompts, object prompts, inventory action menus, multi-pick sale lists, store invoices, and number prompts.
- Provide a `numPrompt` path for numeric C prompts such as tax payments, gold drops, bank deposits, and bank withdrawals.
- Offer numeric prompt presets such as `Zero`, `One Hundred`, `Five Hundred`, `One Thousand`, `Max`, plus `Cancel` and `Main Menu` where applicable.
- Accept plain text numeric messages as fallback input when the C engine is waiting for a number.
- Send ESC-equivalent cancellation commands to the C process for prompt cleanup when a user chooses `Cancel` or leaves a prompt through `Main Menu`.
- Persist only valid post-command game states. Prompt screens, crashes, and stale writes must not overwrite the last valid save state.
- Use optimistic concurrency control for game-state advancement so rapid button presses cannot overwrite a newer state.

# Acceptance Criteria

- All 140 unit and integration tests pass with `pytest`.
- `ruff check .` passes without lint errors.
- No blocking synchronous adapter call runs on the main asyncio event loop.
- Blocking C-engine work is offloaded through bounded worker execution.
- Stale button callbacks are rejected when the callback message is not the current active game message.
- MongoDB game-state writes use `state_version` and atomic `$inc` updates to prevent race-condition overwrites.
- C-engine crashes, unexpected early exits, invalid base64 save blobs, and adapter exceptions are isolated to the current player response.
- Failure responses do not advance or corrupt the stored `engine_state`.
- Store buy/sell transactions expose selection, confirmation, cancellation, sale completion, and store exit controls.
- Numeric prompts support both inline presets and typed numeric fallback.
- Telegram rendering remains stable across clients by using Pillow-generated images for terminal grid output instead of relying only on Markdown or HTML text layout.
- Combat and death logs preserve duplicate same-turn messages so hidden multi-hit damage remains visible to the player.
