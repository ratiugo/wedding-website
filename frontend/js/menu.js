// The site bar's menu button, and (on the home page) the bar turning solid once the
// hero photo is scrolled past.

const bar = document.querySelector(".site-bar");
const button = bar.querySelector(".menu-button");
const menu = document.getElementById("menu");

function setMenuOpen(open) {
  menu.hidden = !open;
  button.setAttribute("aria-expanded", open);
  bar.classList.toggle("menu-open", open);
  document.body.classList.toggle("no-scroll", open);
}

button.addEventListener("click", () => setMenuOpen(menu.hidden));
menu.addEventListener("click", (event) => {
  if (event.target.closest("a")) setMenuOpen(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setMenuOpen(false);
});

const hero = document.querySelector(".hero");
if (hero) {
  new IntersectionObserver(([entry]) => {
    bar.classList.toggle("over-hero", entry.isIntersecting);
  }, { rootMargin: "-60px 0px 0px 0px" }).observe(hero);
}
