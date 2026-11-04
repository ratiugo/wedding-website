// Opt-out page: stops update emails for the invite code in the link, once the guest
// presses the button.

const inviteCode = new URLSearchParams(location.search).get("invite_code");
const button = document.getElementById("opt-out-button");
const error = document.getElementById("error");

function showError(message) {
  error.textContent = message;
  error.hidden = false;
}

if (!inviteCode) {
  button.hidden = true;
  showError("This link is missing its invitation code. Please use the link from your email.");
}

button.addEventListener("click", async () => {
  button.disabled = true;
  error.hidden = true;
  try {
    const res = await fetch(`/api/rsvp/${encodeURIComponent(inviteCode)}/opt-out`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Something went wrong. Please try again.");
    document.getElementById("ask").hidden = true;
    document.getElementById("done").hidden = false;
  } catch (err) {
    showError(err.message);
  } finally {
    button.disabled = false;
  }
});
