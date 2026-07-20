const menuButton = document.querySelector(".nav-toggle");
const scrim = document.querySelector(".nav-scrim");
const sidebar = document.querySelector(".sidebar");

function setMenu(open) {
  document.body.classList.toggle("nav-open", open);
  menuButton?.setAttribute("aria-expanded", String(open));
  scrim?.setAttribute("tabindex", open ? "0" : "-1");
}

menuButton?.addEventListener("click", () => {
  setMenu(!document.body.classList.contains("nav-open"));
});

scrim?.addEventListener("click", () => setMenu(false));

sidebar?.addEventListener("click", (event) => {
  if (event.target.closest("a") && window.innerWidth < 900) {
    setMenu(false);
  }
});

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setMenu(false);
});

