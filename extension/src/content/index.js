console.log("[content] loaded ");

let count = 0;

// Listener for click events on browser tab.
function registerClickListener(listener) {
  window.addEventListener("click", listener);
}

function countClicks() {
  count++;
  console.log("click(): ", count);
}

export function init() {
  registerClickListener(countClicks);
}

init();
