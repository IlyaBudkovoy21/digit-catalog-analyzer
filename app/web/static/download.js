const startButton = document.querySelector("#startButton");
const apiBaseUrlInput = document.querySelector("#apiBaseUrl");
const candidateIdInput = document.querySelector("#candidateId");
const statusText = document.querySelector("#statusText");
const statusBadge = document.querySelector("#statusBadge");
const startedAtNsk = document.querySelector("#startedAtNsk");
const namesReceived = document.querySelector("#namesReceived");
const filesDownloaded = document.querySelector("#filesDownloaded");
const progressBar = document.querySelector("#progressBar");
const message = document.querySelector("#message");

let currentRunId = null;
let pollTimer = null;

startButton.addEventListener("click", async () => {
    startButton.disabled = true;
    message.textContent = "Ставлю задачу в очередь...";
    try {
        const response = await fetch("/api/download/start", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                api_base_url: apiBaseUrlInput.value.trim() || null,
                candidate_id: candidateIdInput.value.trim() || null,
            }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Не удалось стартовать скачивание");
        currentRunId = data.id;
        renderRun(data);
        startPolling();
    } catch (error) {
        message.textContent = error.message;
        startButton.disabled = false;
    }
});

async function loadLatestRun() {
    const response = await fetch("/api/download/runs/latest");
    if (!response.ok) return;
    const data = await response.json();
    if (!data) return;
    currentRunId = data.id;
    renderRun(data);
    if (["queued", "running", "waiting"].includes(data.status)) startPolling();
}

function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(pollRun, 1500);
    pollRun();
}

async function pollRun() {
    if (!currentRunId) return;
    const response = await fetch(`/api/download/runs/${currentRunId}`);
    if (!response.ok) return;
    const data = await response.json();
    renderRun(data);
    if (["completed", "failed"].includes(data.status)) {
        clearInterval(pollTimer);
        startButton.disabled = false;
    }
}

function renderRun(run) {
    statusText.textContent = statusTitle(run.status);
    statusBadge.textContent = run.status;
    statusBadge.className = `badge ${run.status}`;
    startedAtNsk.textContent = run.started_at_nsk ? formatDate(run.started_at_nsk) : "-";
    namesReceived.textContent = run.total_names_received ?? 0;
    filesDownloaded.textContent = run.total_files_downloaded ?? 0;
    message.textContent = run.error || run.last_message || "-";

    const total = Number(run.total_names_received || 0);
    const done = Number(run.total_files_downloaded || 0);
    const percent = run.status === "completed" ? 100 : total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
    progressBar.style.width = `${percent}%`;
}

function statusTitle(status) {
    return {
        queued: "Ожидает worker",
        running: "Скачивание идет",
        waiting: "Пауза из-за лимита API",
        completed: "Каталог скачан полностью",
        failed: "Ошибка скачивания",
    }[status] || "Загрузка еще не запускалась";
}

function formatDate(value) {
    return new Intl.DateTimeFormat("ru-RU", {
        dateStyle: "medium",
        timeStyle: "medium",
        timeZone: "Asia/Novosibirsk",
    }).format(new Date(value));
}

loadLatestRun();
