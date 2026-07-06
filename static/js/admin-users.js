(() => {
  const form = document.querySelector("[data-user-create-form]");
  if (!form) {
    return;
  }

  const passwordInput = form.querySelector("[name='initial_secret']");
  const generateButton = form.querySelector("[data-generate-password]");
  const copyButton = form.querySelector("[data-copy-intro-email]");
  const status = form.querySelector("[data-intro-email-status]");
  const csrfInput = form.querySelector("[name='csrfmiddlewaretoken']");
  const passwordGroups = [
    "ABCDEFGHJKLMNPQRSTUVWXYZ",
    "abcdefghijkmnopqrstuvwxyz",
    "23456789",
    "!#$%&*+-=?",
  ];
  const allPasswordChars = passwordGroups.join("");

  const setStatus = (message, type = "") => {
    if (status) {
      status.textContent = message;
      if (type) {
        status.dataset.statusType = type;
      } else {
        delete status.dataset.statusType;
      }
    }
  };

  const randomIndex = (max) => {
    const value = new Uint32Array(1);
    window.crypto.getRandomValues(value);
    return value[0] % max;
  };

  const randomChar = (chars) => chars[randomIndex(chars.length)];

  const shuffle = (chars) => {
    for (let index = chars.length - 1; index > 0; index -= 1) {
      const swapIndex = randomIndex(index + 1);
      [chars[index], chars[swapIndex]] = [chars[swapIndex], chars[index]];
    }
    return chars;
  };

  const generatePassword = () => {
    const chars = passwordGroups.map(randomChar);
    while (chars.length < 24) {
      chars.push(randomChar(allPasswordChars));
    }
    return shuffle(chars).join("");
  };

  const copyText = async (text) => {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.top = "-1000px";
    document.body.append(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  };

  if (generateButton && passwordInput) {
    generateButton.addEventListener("click", () => {
      passwordInput.value = generatePassword();
      passwordInput.focus();
    });
  }

  if (copyButton) {
    copyButton.addEventListener("click", async () => {
      copyButton.disabled = true;
      setStatus("Preparing intro email...");
      try {
        const response = await fetch(form.dataset.introEmailUrl, {
          body: new FormData(form),
          headers: {
            "X-CSRFToken": csrfInput.value,
            "X-Requested-With": "XMLHttpRequest",
          },
          method: "POST",
        });
        const data = await response.json();
        if (!response.ok) {
          setStatus(data.message || "Fix the create user fields before copying.", "error");
          return;
        }
        await copyText(data.body);
        setStatus("Intro email copied.", "success");
      } catch {
        setStatus("Could not copy intro email.", "error");
      } finally {
        copyButton.disabled = false;
      }
    });
  }
})();

(() => {
  const table = document.querySelector("[data-user-table]");
  if (!table) {
    return;
  }

  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const searchInput = document.querySelector("[data-user-table-search]");
  const clearButton = document.querySelector("[data-user-table-clear]");
  const count = document.querySelector("[data-user-table-count]");
  const sortButtons = Array.from(table.querySelectorAll("[data-sort-column]"));
  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
  let activeSortColumn = 0;
  let activeSortDirection = "asc";

  const sortValue = (row, columnIndex) => row.cells[columnIndex].dataset.sort || "";

  const compareRows = (left, right) => {
    const leftValue = sortValue(left, activeSortColumn);
    const rightValue = sortValue(right, activeSortColumn);
    const result = collator.compare(leftValue, rightValue);
    return activeSortDirection === "asc" ? result : -result;
  };

  const updateSortIndicators = () => {
    for (const button of sortButtons) {
      const column = Number(button.dataset.sortColumn);
      button.removeAttribute("aria-sort");
      button.dataset.sortDirection = "";
      const label = button.textContent.replace(/\s+[\^v]$/, "");
      if (column === activeSortColumn) {
        button.dataset.sortDirection = activeSortDirection;
        button.setAttribute("aria-sort", activeSortDirection === "asc" ? "ascending" : "descending");
        button.textContent = `${label} ${activeSortDirection === "asc" ? "^" : "v"}`;
      } else {
        button.textContent = label;
      }
    }
  };

  const applySearch = () => {
    const query = searchInput.value.trim().toLowerCase();
    let visibleRows = 0;
    for (const row of rows) {
      const matches = !query || row.dataset.search.includes(query);
      row.hidden = !matches;
      if (matches) {
        visibleRows += 1;
      }
    }
    if (count) {
      count.textContent = `Showing ${visibleRows} of ${rows.length} users`;
    }
  };

  const applySort = () => {
    const sortedRows = rows.slice().sort(compareRows);
    tbody.append(...sortedRows);
    updateSortIndicators();
    applySearch();
  };

  for (const button of sortButtons) {
    button.addEventListener("click", () => {
      const column = Number(button.dataset.sortColumn);
      if (column === activeSortColumn) {
        activeSortDirection = activeSortDirection === "asc" ? "desc" : "asc";
      } else {
        activeSortColumn = column;
        activeSortDirection = "asc";
      }
      applySort();
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", applySearch);
  }

  if (clearButton) {
    clearButton.addEventListener("click", () => {
      searchInput.value = "";
      searchInput.focus();
      applySearch();
    });
  }

  applySort();
})();
