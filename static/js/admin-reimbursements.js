(function () {
    "use strict";

    const yearForm = document.querySelector("[data-year-form]");
    if (yearForm) {
        yearForm.querySelector("select").addEventListener("change", () => yearForm.submit());
    }

    const button = document.querySelector("[data-copy-paid-expenses]");
    const table = document.querySelector("[data-paid-expenses-table]");
    const status = document.querySelector("[data-copy-status]");
    if (!button || !table || !navigator.clipboard) return;

    function safeCell(value) {
        const trimmed = value.trimStart();
        return /^[=+\-@]/.test(trimmed) ? `'${value}` : value;
    }

    button.addEventListener("click", async () => {
        const text = Array.from(table.rows)
            .map((row) =>
                Array.from(row.cells)
                    .map((cell) => safeCell(cell.textContent.trim()))
                    .join("\t"),
            )
            .join("\n");
        const htmlTable = table.cloneNode(true);
        Array.from(htmlTable.rows).forEach((row) => {
            Array.from(row.cells).forEach((cell) => {
                cell.textContent = safeCell(cell.textContent.trim());
            });
        });
        try {
            if (window.ClipboardItem && navigator.clipboard.write) {
                await navigator.clipboard.write([
                    new ClipboardItem({
                        "text/html": new Blob([htmlTable.outerHTML], { type: "text/html" }),
                        "text/plain": new Blob([text], { type: "text/plain" }),
                    }),
                ]);
            } else {
                await navigator.clipboard.writeText(text);
            }
            status.textContent = "Paid expenses copied to clipboard.";
        } catch (_error) {
            status.textContent = "Could not copy. Use Download CSV instead.";
        }
    });
})();
