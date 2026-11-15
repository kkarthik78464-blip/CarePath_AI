const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
const hospitalList = document.getElementById("hospitalList");
const appointmentForm = document.getElementById("appointmentForm");
const appointmentMessage = document.getElementById("appointmentMessage");

const roleSelect = document.getElementById("roleSelect");
if (roleSelect) {
  const doctorFields = document.getElementById("doctorFields");
  const hospitalId = document.getElementById("hospitalId");
  const professionalId = document.getElementById("professionalId");
  const updateDoctorFields = () => {
    const isDoctor = roleSelect.value === "doctor";
    doctorFields.hidden = !isDoctor;
    hospitalId.required = isDoctor;
    professionalId.required = isDoctor;
  };
  roleSelect.addEventListener("change", updateDoctorFields);
  updateDoctorFields();
}

async function loadHospitals() {
  if (!hospitalList) return;
  try {
    const response = await fetch("/api/hospitals", {credentials: "same-origin"});
    const data = await response.json();
    hospitalList.innerHTML = "";
    data.hospitals.forEach(h => {
      const card = document.createElement("article");
      card.className = "hospital-card";
      card.innerHTML = `
        <span class="demo-tag">SAMPLE HOSPITAL</span>
        <h3>${escapeHtml(h.name)}</h3>
        <p>${escapeHtml(h.area)} · ${escapeHtml(h.specialty)}</p>
        <div class="hospital-meta"><span>People waiting</span><strong>${Number(h.queue)} (sample)</strong></div>
        <div class="hospital-actions">
          <button class="btn btn-outline" type="button" data-queue="${Number(h.id)}">Sample queue</button>
          <a class="btn" target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(h.name + " " + h.area)}">Map ↗</a>
        </div>
        <p class="queue-result" id="queue-${Number(h.id)}" aria-live="polite"></p>`;
      hospitalList.appendChild(card);
    });
    hospitalList.querySelectorAll("[data-queue]").forEach(btn => {
      btn.addEventListener("click", () => loadQueue(btn.dataset.queue));
    });
  } catch {
    hospitalList.textContent = "Could not load sample hospitals. Check that the Python server is running.";
  }
}

async function loadQueue(id) {
  const target = document.getElementById(`queue-${id}`);
  if (!target) return;
  target.textContent = "Loading illustrative estimate…";
  try {
    const response = await fetch(`/api/queue/${encodeURIComponent(id)}`, {credentials: "same-origin"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load estimate.");
    target.textContent = `Sample estimate: ${data.estimated_wait_minutes} minutes. ${data.message}`;
  } catch (error) {
    target.textContent = error.message;
  }
}

if (appointmentForm) {
  appointmentForm.addEventListener("submit", async event => {
    event.preventDefault();
    appointmentMessage.className = "form-message";
    appointmentMessage.textContent = "Saving your demo request…";
    const values = Object.fromEntries(new FormData(appointmentForm).entries());
    try {
      const response = await fetch("/api/appointments", {
        method: "POST",
        credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken},
        body: JSON.stringify(values)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Request failed.");
      appointmentMessage.textContent = `${data.message} Request ID: ${data.appointment_id}. Refresh this page to see it in your list.`;
      appointmentForm.reset();
    } catch (error) {
      appointmentMessage.classList.add("error");
      appointmentMessage.textContent = error.message;
    }
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[char]));
}

let installPrompt;
window.addEventListener("beforeinstallprompt", event => {
  event.preventDefault();
  installPrompt = event;
  document.getElementById("installBtn")?.classList.remove("hidden");
});
document.getElementById("installBtn")?.addEventListener("click", async () => {
  if (!installPrompt) return;
  installPrompt.prompt();
  await installPrompt.userChoice;
  installPrompt = null;
  document.getElementById("installBtn")?.classList.add("hidden");
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/static/sw.js").catch(() => {}));
}
loadHospitals();
