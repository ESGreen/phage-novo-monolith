(function () {
  const formatDollars = (cents) => {
    const amount = cents / 100;
    return `$${amount.toFixed(2)}`;
  };

  const inputValueFromCents = (cents) => (cents / 100).toFixed(2);

  const parseAmountCents = (input) => {
    const value = Number.parseFloat(input.value || "0");
    if (Number.isNaN(value)) {
      return 0;
    }
    return Math.round(value * 100);
  };

  const updateTierCards = (form, selectedInput) => {
    form.querySelectorAll("[data-tax-tier-card]").forEach((card) => {
      const input = card.querySelector("[data-tax-tier-input]");
      const choice = card.querySelector("[data-tax-tier-choice]");
      const selected = input === selectedInput;
      card.classList.toggle("tax-tier-card--selected", selected);
      if (choice) {
        choice.textContent = selected ? "◉ Selected" : "○ Select";
      }
    });
  };

  const updateAddOnCards = (form) => {
    form.querySelectorAll("[data-tax-add-on-card]").forEach((card) => {
      const input = card.querySelector("[data-tax-add-on-input]");
      card.classList.toggle("tax-add-on-card--selected", input.checked);
    });
  };

  const selectedAddOnCents = (form) => {
    return Array.from(form.querySelectorAll("[data-tax-add-on-input]:checked")).reduce(
      (total, input) => total + Number.parseInt(input.dataset.taxAddOnCents || "0", 10),
      0,
    );
  };

  const updateSummary = (form) => {
    const selectedTier = form.querySelector("[data-tax-tier-input]:checked");
    const amountInput = form.querySelector("[data-tax-amount-input]");
    const minimumDisplay = form.querySelector("[data-tax-minimum-display]");
    const amountDisplay = form.querySelector("[data-tax-amount-display]");
    const addOnDisplay = form.querySelector("[data-tax-add-on-display]");
    const totalDisplay = form.querySelector("[data-tax-total-display]");
    const zeroMessage = form.querySelector("[data-tax-zero-message]");
    if (!selectedTier || !amountInput) {
      return;
    }

    const minimumCents = Number.parseInt(selectedTier.dataset.taxMinimumCents || "0", 10);
    const addOnCents = selectedAddOnCents(form);
    const taxAmountCents = parseAmountCents(amountInput);
    const totalCents = taxAmountCents + addOnCents;

    if (minimumDisplay) {
      minimumDisplay.textContent = formatDollars(minimumCents);
    }
    if (amountDisplay) {
      amountDisplay.textContent = formatDollars(taxAmountCents);
    }
    if (addOnDisplay) {
      addOnDisplay.textContent = formatDollars(addOnCents);
    }
    if (totalDisplay) {
      totalDisplay.textContent = formatDollars(totalCents);
    }
    if (zeroMessage) {
      zeroMessage.hidden = totalCents > 0;
    }
  };

  const setTierMinimum = (form, selectedTier, resetAmount) => {
    const amountInput = form.querySelector("[data-tax-amount-input]");
    const minimumCents = Number.parseInt(selectedTier.dataset.taxMinimumCents || "0", 10);
    amountInput.min = inputValueFromCents(minimumCents);
    amountInput.step = "5.00";
    if (resetAmount) {
      amountInput.value = inputValueFromCents(minimumCents);
    }
  };

  document.querySelectorAll("[data-tax-form]").forEach((form) => {
    form.querySelectorAll("[data-tax-tier-input]").forEach((input) => {
      input.addEventListener("change", () => {
        setTierMinimum(form, input, true);
        updateTierCards(form, input);
        updateSummary(form);
      });
    });

    form.querySelectorAll("[data-tax-add-on-input]").forEach((input) => {
      input.addEventListener("change", () => {
        updateAddOnCards(form);
        updateSummary(form);
      });
    });

    const amountInput = form.querySelector("[data-tax-amount-input]");
    if (amountInput) {
      amountInput.addEventListener("input", () => updateSummary(form));
    }

    const selectedTier = form.querySelector("[data-tax-tier-input]:checked");
    if (selectedTier) {
      setTierMinimum(form, selectedTier, false);
      updateTierCards(form, selectedTier);
    }
    updateAddOnCards(form);
    updateSummary(form);
  });
})();
