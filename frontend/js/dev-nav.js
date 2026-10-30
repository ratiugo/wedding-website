// On dev and locally only: a small bar linking the site's versions, so each is a click
// away. Real guests (tessandcolton.com) never see it.

if (location.hostname === "localhost" || location.hostname.startsWith("dev.")) {
  const nav = document.createElement("nav");
  nav.innerHTML = `
    <strong>dev</strong>
    <a href="/">Full site</a>
    <a href="/save-the-date.html">Save the date</a>
  `;
  nav.style.cssText = `
    position: fixed; bottom: 12px; left: 50%; transform: translateX(-50%); z-index: 100;
    display: flex; gap: 14px; align-items: center; padding: 6px 14px;
    font: 13px system-ui, sans-serif; background: rgba(40, 40, 40, 0.85); color: #fff;
    border-radius: 999px;
  `;
  for (const link of nav.querySelectorAll("a")) link.style.color = "#fff";
  document.body.append(nav);
}
