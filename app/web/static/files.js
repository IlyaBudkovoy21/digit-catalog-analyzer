const filesBody = document.querySelector("#filesBody");
const orderSelect = document.querySelector("#orderSelect");
const selectPage = document.querySelector("#selectPage");
const selectAll = document.querySelector("#selectAll");
const selectionInfo = document.querySelector("#selectionInfo");
const prevPage = document.querySelector("#prevPage");
const nextPage = document.querySelector("#nextPage");
const pageInfo = document.querySelector("#pageInfo");
const calculateButton = document.querySelector("#calculateButton");
const resultSection = document.querySelector("#resultSection");
const resultTitle = document.querySelector("#resultTitle");
const totalStats = document.querySelector("#totalStats");
const fileStats = document.querySelector("#fileStats");

const state = {
    page: 1,
    pageSize: 20,
    pages: 1,
    total: 0,
    items: [],
    selectedIds: new Set(),
    allFiles: false,
};

orderSelect.addEventListener("change", () => {
    state.page = 1;
    loadFiles();
});

selectPage.addEventListener("change", () => {
    if (state.allFiles) return;
    for (const item of state.items) {
        if (selectPage.checked) state.selectedIds.add(item.id);
        else state.selectedIds.delete(item.id);
    }
    renderFiles();
});

selectAll.addEventListener("change", () => {
    state.allFiles = selectAll.checked;
    if (state.allFiles) state.selectedIds.clear();
    renderFiles();
});

prevPage.addEventListener("click", () => {
    if (state.page > 1) {
        state.page -= 1;
        loadFiles();
    }
});

nextPage.addEventListener("click", () => {
    if (state.page < state.pages) {
        state.page += 1;
        loadFiles();
    }
});

calculateButton.addEventListener("click", async () => {
    if (!state.allFiles && state.selectedIds.size === 0) {
        alert("Выберите хотя бы один файл");
        return;
    }
    calculateButton.disabled = true;
    calculateButton.textContent = "Считаю...";
    try {
        const response = await fetch("/api/files/calculate", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({all_files: state.allFiles, file_ids: [...state.selectedIds]}),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Ошибка расчета");
        renderResult(data);
    } catch (error) {
        alert(error.message);
    } finally {
        calculateButton.disabled = false;
        calculateButton.textContent = "Произвести расчеты";
    }
});

async function loadFiles() {
    const params = new URLSearchParams({page: state.page, page_size: state.pageSize, order: orderSelect.value});
    const response = await fetch(`/api/files?${params}`);
    const data = await response.json();
    state.items = data.items;
    state.pages = data.pages;
    state.total = data.total;
    renderFiles();
}

function renderFiles() {
    filesBody.innerHTML = "";
    if (state.items.length === 0) {
        filesBody.innerHTML = `<tr><td colspan="5" class="muted">Файлы еще не скачаны</td></tr>`;
    }
    for (const item of state.items) {
        const row = document.createElement("tr");
        const checked = state.allFiles || state.selectedIds.has(item.id);
        row.innerHTML = `
            <td><input data-id="${item.id}" type="checkbox" ${checked ? "checked" : ""} ${state.allFiles ? "disabled" : ""}></td>
            <td>${escapeHtml(item.name)}</td>
            <td>${formatDate(item.downloaded_at)}</td>
            <td>${item.size_bytes} B</td>
            <td class="hash" title="${item.sha256}">${item.sha256}</td>
        `;
        filesBody.appendChild(row);
    }
    filesBody.querySelectorAll("input[type=checkbox]").forEach((checkbox) => {
        checkbox.addEventListener("change", (event) => {
            const id = Number(event.target.dataset.id);
            if (event.target.checked) state.selectedIds.add(id);
            else state.selectedIds.delete(id);
            syncSelectionControls();
        });
    });
    syncSelectionControls();
}

function syncSelectionControls() {
    selectAll.checked = state.allFiles;
    selectPage.checked = state.items.length > 0 && state.items.every((item) => state.allFiles || state.selectedIds.has(item.id));
    selectPage.disabled = state.allFiles;
    selectionInfo.textContent = state.allFiles ? `Выбрано: все ${state.total}` : `Выбрано: ${state.selectedIds.size}`;
    pageInfo.textContent = `${state.page} / ${state.pages}`;
    prevPage.disabled = state.page <= 1;
    nextPage.disabled = state.page >= state.pages;
}

function renderResult(data) {
    resultSection.classList.remove("hidden");
    resultTitle.textContent = `Статистика по ${data.selected_count} файлам`;
    totalStats.innerHTML = renderDigitStats(data.total_stats);
    fileStats.innerHTML = data.files.map((file) => `
        <article class="file-stat">
            <h4>${escapeHtml(file.name)}</h4>
            <div class="digit-grid">${renderDigitStats(file.stats)}</div>
        </article>
    `).join("");
    resultSection.scrollIntoView({behavior: "smooth", block: "start"});
}

function renderDigitStats(stats) {
    return Object.keys(stats).sort().map((digit) => `
        <div class="digit"><span>цифра ${digit}</span><strong>${stats[digit]}</strong></div>
    `).join("");
}

function formatDate(value) {
    return new Intl.DateTimeFormat("ru-RU", {dateStyle: "medium", timeStyle: "medium"}).format(new Date(value));
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

loadFiles();
