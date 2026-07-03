const states = [
  {
    title: "Welcome to tglarn",
    body: "A Telegram wrapper around the classic Larn/ReLarn roguelike engine.",
    image: "assets/replay-welcome.png",
    alt: "Pillow-rendered welcome screen for the tglarn Telegram bot",
    caption: "Text prompt rendered by Pillow from a terminal-style screen.",
    log: ["Choose who will enter the dungeon."],
    keyboard: [["Play Game"], ["Main Menu"]],
  },
  {
    title: "Create Character",
    body: "Each class starts with different stats, gear, and spell access.",
    image: "assets/replay-class-guide.png",
    alt: "Pillow-rendered class guide screen for tglarn",
    caption: "Class guidance rendered as a bot text screen.",
    log: ["Class Guide is available before committing to a run."],
    keyboard: [
      ["Ogre", "Wizard"],
      ["Klingon", "Elf"],
      ["Rogue", "Geek"],
      ["Dwarf", "Rambo"],
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
      ["NW", "N", "NE"],
      ["W", "Inspect", "E"],
      ["SW", "S", "SE"],
      ["Spell", "Menu"],
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
    keyboard: [["Buy spear"], ["Sell item"], ["Exit Store"], ["Main Menu"]],
  },
];

let currentState = 0;

const titleNode = document.querySelector("#mock-state-title");
const bodyNode = document.querySelector("#mock-state-body");
const imageNode = document.querySelector("#mock-state-image");
const captionNode = document.querySelector("#mock-state-caption");
const logNode = document.querySelector("#mock-log-list");
const keyboardNode = document.querySelector("#mock-inline-keyboard");
const controlButtons = document.querySelectorAll(".control-pad button");

function renderState(index) {
  currentState = (index + states.length) % states.length;
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

      for (const label of row) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label;
        button.addEventListener("click", () => renderState(currentState + 1));
        rowNode.append(button);
      }

      return rowNode;
    }),
  );
}

for (const button of controlButtons) {
  button.addEventListener("click", () => {
    const explicitState = button.dataset.state;
    if (explicitState !== undefined) {
      renderState(Number.parseInt(explicitState, 10));
      return;
    }

    renderState(currentState + 1);
  });
}

renderState(0);
