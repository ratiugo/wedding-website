// RSVP page: look up an invitation by invite code, show a row per guest, save answers.

// Same origin as the site: the local dev server and (later) CloudFront both
// forward /api/* to the Lambda.
const API_BASE = "/api";

const lookupForm = document.getElementById("lookup-form");
const rsvpForm = document.getElementById("rsvp-form");
const thanks = document.getElementById("thanks");

let invitation = null;

async function api(method, inviteCode, body) {
  const res = await fetch(`${API_BASE}/rsvp/${encodeURIComponent(inviteCode)}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Something went wrong. Please try again.");
  return data;
}

function showStep(step) {
  for (const el of [lookupForm, rsvpForm, thanks]) el.hidden = el !== step;
}

function showError(id, message) {
  const el = document.getElementById(id);
  el.textContent = message || "";
  el.hidden = !message;
}

// Disable a form's button while a request is in flight. The first request can
// take a while if the database is waking up, so say so.
async function busy(form, label, work) {
  const button = form.querySelector("button[type=submit]");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = label;
  try {
    return await work();
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

// --- Step 1: lookup ---

async function loadInvitation(inviteCode) {
  showError("lookup-error", "");
  try {
    invitation = await busy(lookupForm, "Finding your invitation…", () => api("GET", inviteCode));
  } catch (err) {
    showStep(lookupForm);
    showError("lookup-error", err.message);
    return;
  }

  // Put the invite code in the URL so a refresh (or bookmark) comes straight back here.
  history.replaceState(null, "", `?invite_code=${invitation.invite_code}`);
  if (invitation.responded_at) showThanks();
  else showForm();
}

lookupForm.addEventListener("submit", (e) => {
  e.preventDefault();
  loadInvitation(document.getElementById("invite-code").value.trim());
});

// --- Step 2: the form ---

function showForm() {
  document.getElementById("invite-label").textContent = invitation.label;
  document.getElementById("notes").value = invitation.notes;

  const list = document.getElementById("guest-list");
  list.replaceChildren(...invitation.guests.map(guestRow));

  showError("rsvp-error", "");
  showStep(rsvpForm);
}

function guestRow(guest) {
  const row = document.getElementById("guest-template").content.firstElementChild.cloneNode(true);
  row.dataset.id = guest.id;

  const nameLabel = row.querySelector(".plus-one-name");
  const nameInput = nameLabel.querySelector("input");
  const dietary = row.querySelector(".dietary");
  const radios = row.querySelectorAll("input[type=radio]");

  if (guest.plus_one) {
    row.querySelector(".guest-name").textContent = "Your guest";
    nameLabel.hidden = false;
    // "Plus-one" is the placeholder from the guest list, not a real name.
    nameInput.value = guest.name === "Plus-one" ? "" : guest.name;
  } else {
    row.querySelector(".guest-name").textContent = guest.name;
  }

  for (const radio of radios) {
    radio.name = `attending-${guest.id}`;
    radio.checked = guest.attending === (radio.value === "yes");
    radio.addEventListener("change", () => updateRow(row));
  }
  dietary.querySelector("input").value = guest.dietary;

  updateRow(row);
  return row;
}

// Only ask for dietary info (and the plus-one's name) when the guest is coming.
function updateRow(row) {
  const attending = row.querySelector("input[type=radio][value=yes]").checked;
  row.querySelector(".dietary").hidden = !attending;
  row.querySelector(".plus-one-name input").required = attending && !row.querySelector(".plus-one-name").hidden;
}

rsvpForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("rsvp-error", "");

  const guests = [...document.querySelectorAll("#guest-list .guest")].map((row) => {
    const answer = {
      id: Number(row.dataset.id),
      attending: row.querySelector("input[type=radio][value=yes]").checked,
      dietary: row.querySelector(".dietary input").value,
    };
    if (!row.querySelector(".plus-one-name").hidden) {
      answer.name = row.querySelector(".plus-one-name input").value;
    }
    return answer;
  });
  const notes = document.getElementById("notes").value;

  try {
    invitation = await busy(rsvpForm, "Sending…", () =>
      api("PUT", invitation.invite_code, { guests, notes })
    );
    showThanks();
  } catch (err) {
    showError("rsvp-error", err.message);
  }
});

// --- Step 3: confirmation ---

function showThanks() {
  const coming = invitation.guests.filter((g) => g.attending).length;
  document.getElementById("thanks-message").textContent =
    coming > 0
      ? `Thank you! We can't wait to celebrate with you. (${coming} attending)`
      : "Thank you for letting us know. You'll be missed!";
  showStep(thanks);
}

document.getElementById("edit-button").addEventListener("click", showForm);

// --- Start ---

const inviteCodeFromLink = new URLSearchParams(location.search).get("invite_code");
if (inviteCodeFromLink) {
  document.getElementById("invite-code").value = inviteCodeFromLink;
  loadInvitation(inviteCodeFromLink);
}
