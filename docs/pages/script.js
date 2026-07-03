const states = [
  {
    title: "Welcome to tglarn",
    body: "A Telegram wrapper around the classic Larn/ReLarn roguelike engine.",
    image: "assets/replay-welcome.png",
    alt: "Pillow-rendered welcome screen for the tglarn Telegram bot",
    caption: "Text prompt rendered by Pillow from a terminal-style screen.",
    log: ["Choose who will enter the dungeon."],
    keyboard: [
      [{ label: "Play Game", target: 1 }],
      [{ label: "Main Menu", target: 0 }],
    ],
  },
  {
    title: "Create Character",
    body: "Each class starts with different stats, gear, and spell access.",
    image: "assets/replay-class-guide.png",
    alt: "Pillow-rendered class guide screen for tglarn",
    caption: "Class guidance rendered as a bot text screen.",
    log: ["Class Guide is available before committing to a run."],
    keyboard: [
      [
        { label: "Ogre", target: 2 },
        { label: "Wizard", target: 2 },
      ],
      [
        { label: "Klingon", target: 2 },
        { label: "Elf", target: 2 },
      ],
      [
        { label: "Rogue", target: 2 },
        { label: "Geek", target: 2 },
      ],
      [
        { label: "Dwarf", target: 2 },
        { label: "Rambo", target: 2 },
      ],
    ],
  },
  {
    title: "Dungeon Level 1",
    body: "The terminal grid is rendered as a stable image in the real bot.",
    image: "assets/replay-map.png",
    alt: "Pillow-rendered dungeon map with player, monsters, items, walls, and doors",
    caption: "Map snapshot rendered with the real tile colors and grid style.",
    log: [
      "You enter the caverns.",
      "A gnome waits in the next chamber.",
      "Context buttons update after every turn.",
    ],
    keyboard: [
      [
        { label: "NW", target: 2 },
        { label: "N", target: 2 },
        { label: "NE", target: 2 },
      ],
      [
        { label: "W", target: 2 },
        { label: "Inspect", target: 2 },
        { label: "E", target: 2 },
      ],
      [
        { label: "SW", target: 2 },
        { label: "S", target: 2 },
        { label: "SE", target: 2 },
      ],
      [
        { label: "Spell", target: 2 },
        { label: "Menu", target: 3 },
      ],
    ],
  },
  {
    title: "Store Prompt",
    body: "Classic terminal prompts become explicit Telegram actions.",
    image: "assets/replay-store.png",
    alt: "Pillow-rendered DND Store prompt for tglarn",
    caption: "Store prompt rendered as a terminal text screen.",
    log: [
      "The C engine is waiting for a store command.",
      "The adapter maps that prompt into inline buttons.",
    ],
    keyboard: [
      [{ label: "Buy spear", target: 3 }],
      [{ label: "Sell item", target: 3 }],
      [{ label: "Exit Store", target: 2 }],
      [{ label: "Main Menu", target: 0 }],
    ],
  },
];

let currentState = null;

const titleNode = document.querySelector("#mock-state-title");
const bodyNode = document.querySelector("#mock-state-body");
const imageNode = document.querySelector("#mock-state-image");
const captionNode = document.querySelector("#mock-state-caption");
const logNode = document.querySelector("#mock-log-list");
const keyboardNode = document.querySelector("#mock-inline-keyboard");
const controlButtons = document.querySelectorAll(".control-pad button");

function renderState(index) {
  if (!Number.isInteger(index) || index < 0 || index >= states.length) {
    return;
  }

  if (currentState === index) {
    return;
  }

  currentState = index;
  const state = states[currentState];

  titleNode.textContent = state.title;
  bodyNode.textContent = state.body;
  imageNode.src = state.image;
  imageNode.alt = state.alt;
  captionNode.textContent = state.caption;

  logNode.replaceChildren(
    ...state.log.map((line) => {
      const item = document.createElement("li");
      item.textContent = line;
      return item;
    }),
  );

  keyboardNode.replaceChildren(
    ...state.keyboard.map((row) => {
      const rowNode = document.createElement("div");
      rowNode.className = "mock-keyboard-row";
      rowNode.style.setProperty("--cols", row.length);

      for (const item of row) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = item.label;
        button.addEventListener("click", () => renderState(item.target));
        rowNode.append(button);
      }

      return rowNode;
    }),
  );
}

for (const button of controlButtons) {
  button.addEventListener("click", () => {
    const explicitState = button.dataset.state;
    renderState(Number.parseInt(explicitState, 10));
  });
}

renderState(0);
