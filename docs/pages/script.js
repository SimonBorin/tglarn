const states = [
  {
    title: "Welcome to tglarn",
    body: "A Telegram wrapper around the classic Larn/ReLarn roguelike engine.",
    map: [
      "Before the Caverns",
      "",
      "Your child is dying from dianthroritis.",
      "Find the cure in the Caverns of Larn before time runs out.",
    ].join("\n"),
    log: ["Choose who will enter the dungeon."],
    keyboard: [["Play Game"], ["Main Menu"]],
  },
  {
    title: "Create Character",
    body: "Each class starts with different stats, gear, and spell access.",
    map: [
      "Recommended starts: Geek, Dwarf, or Rogue.",
      "Rambo is a challenge class.",
      "",
      "Elf starts with protection and leather, but no weapon.",
    ].join("\n"),
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
    map: [
      "#############",
      "#.....#.....#",
      "#..@..#..G..#",
      "#.....O.....#",
      "###.#####.###",
      "#.....*.....#",
      "#############",
    ].join("\n"),
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
    map: [
      "DND Store",
      "",
      "a. leather armor",
      "b. spear",
      "c. potion of healing",
      "",
      "Select an item or exit the store.",
    ].join("\n"),
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
const mapNode = document.querySelector("#mock-map");
const logNode = document.querySelector("#mock-log-list");
const keyboardNode = document.querySelector("#mock-inline-keyboard");
const controlButtons = document.querySelectorAll(".control-pad button");

function renderState(index) {
  currentState = (index + states.length) % states.length;
  const state = states[currentState];

  titleNode.textContent = state.title;
  bodyNode.textContent = state.body;
  mapNode.textContent = state.map;

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
