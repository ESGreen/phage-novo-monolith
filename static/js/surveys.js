(function () {
  const parseChoiceIds = (value) => {
    if (!value) {
      return [];
    }
    return value
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  };

  const selectedChoiceIds = (form, questionId) => {
    const card = form.querySelector(`[data-survey-question-card][data-question-id="${questionId}"]`);
    if (!card || card.hidden) {
      return [];
    }
    const select = card.querySelector("[data-choice-select]");
    if (select && select.value) {
      return [select.value];
    }
    return Array.from(card.querySelectorAll("[data-choice-input]:checked")).map(
      (input) => input.dataset.choiceId,
    );
  };

  const setCardEnabled = (card, enabled) => {
    card.querySelectorAll("input, select, textarea, button").forEach((field) => {
      field.disabled = !enabled;
    });
  };

  const updateOtherText = (card) => {
    const otherText = card.querySelector("[data-other-text]");
    if (!otherText) {
      return;
    }
    const otherCheckbox = card.querySelector("[data-other-checkbox]");
    const select = card.querySelector("[data-choice-select]");
    if (otherCheckbox) {
      otherText.disabled = !otherCheckbox.checked || card.hidden;
    } else if (select) {
      otherText.disabled = select.value !== "__other__" || card.hidden;
    }
  };

  const cardIsVisible = (form, card, cardsById, visiting) => {
    const parentId = card.dataset.visibleIfQuestionId;
    if (!parentId) {
      return true;
    }
    if (visiting.has(card.dataset.questionId)) {
      return false;
    }
    visiting.add(card.dataset.questionId);
    const parentCard = cardsById.get(parentId);
    if (!parentCard || !cardIsVisible(form, parentCard, cardsById, visiting)) {
      return false;
    }
    const requiredChoiceIds = parseChoiceIds(card.dataset.visibleIfChoiceIds || "");
    const selectedIds = selectedChoiceIds(form, parentId);
    return requiredChoiceIds.some((choiceId) => selectedIds.includes(choiceId));
  };

  const updateSurveyForm = (form) => {
    const cards = Array.from(form.querySelectorAll("[data-survey-question-card]"));
    const cardsById = new Map(cards.map((card) => [card.dataset.questionId, card]));
    cards.forEach((card) => {
      const visible = cardIsVisible(form, card, cardsById, new Set());
      card.hidden = !visible;
      setCardEnabled(card, visible);
      updateOtherText(card);
    });
  };

  document.querySelectorAll("[data-survey-form]").forEach((form) => {
    form.addEventListener("change", () => updateSurveyForm(form));
    updateSurveyForm(form);
  });
})();
