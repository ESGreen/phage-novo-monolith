(function () {
    "use strict";

    document.querySelectorAll("[data-payout-method]").forEach((method) => {
        const form = method.closest("form");
        if (!form) return;

        const groups = form.querySelectorAll("[data-payout-fields]");
        const updateFields = () => {
            groups.forEach((group) => {
                const active = group.dataset.payoutFields === method.value;
                group.hidden = !active;
                group.querySelectorAll("input, select, textarea").forEach((field) => {
                    field.disabled = !active;
                });
            });
        };

        method.addEventListener("change", updateFields);
        updateFields();
    });
})();
