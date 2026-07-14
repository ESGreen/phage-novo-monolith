(() => {
  const dataElement = document.getElementById("survey-list-data");
  const table = document.querySelector("[data-surveys-table]");
  const activeOnlyInput = document.querySelector("[data-surveys-active-only]");
  const count = document.querySelector("[data-surveys-count]");
  const empty = document.querySelector("[data-surveys-empty]");
  if (!dataElement || !table || !activeOnlyInput) {
    return;
  }

  const surveys = JSON.parse(dataElement.textContent || "[]");
  const tbody = table.tBodies[0];

  const renderRows = () => {
    const activeOnly = activeOnlyInput.checked;
    const visibleSurveys = surveys.filter((survey) => !activeOnly || survey.is_active);
    tbody.replaceChildren();

    visibleSurveys.forEach((survey) => {
      const row = document.createElement("tr");
      const nameCell = document.createElement("td");
      const slugCell = document.createElement("td");
      const activeCell = document.createElement("td");
      const responseCountCell = document.createElement("td");
      const actionsCell = document.createElement("td");
      const editLink = document.createElement("a");
      const responsesLink = document.createElement("a");

      editLink.className = "secondary-button";
      editLink.href = survey.edit_url;
      editLink.textContent = `Edit: ${survey.name}`;
      responsesLink.className = "secondary-button";
      responsesLink.href = survey.responses_url;
      responsesLink.textContent = "View Responses";
      nameCell.append(editLink);
      slugCell.textContent = survey.slug;
      activeCell.textContent = survey.is_active ? "True" : "False";
      responseCountCell.textContent = survey.response_count;
      actionsCell.append(responsesLink);
      row.append(nameCell, slugCell, activeCell, responseCountCell, actionsCell);
      tbody.append(row);
    });

    if (empty) {
      empty.hidden = visibleSurveys.length > 0;
    }
    if (count) {
      count.textContent = `Showing ${visibleSurveys.length} of ${surveys.length} surveys`;
    }
  };

  activeOnlyInput.addEventListener("change", renderRows);
  renderRows();
})();

(() => {
  const cards = Array.from(document.querySelectorAll("[data-survey-question-card]"));
  if (cards.length === 0) {
    return;
  }

  const openArrow = "▾";
  const closedArrow = "▸";
  const hashTarget = window.location.hash
    ? document.getElementById(window.location.hash.slice(1))
    : null;

  const setExpanded = (card, expanded) => {
    const toggle = card.querySelector("[data-survey-question-toggle]");
    const bodyId = toggle?.getAttribute("aria-controls");
    const body = bodyId ? document.getElementById(bodyId) : null;
    const arrow = card.querySelector("[data-collapsible-arrow]");
    if (!toggle || !body) {
      return;
    }

    toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
    body.hidden = !expanded;
    card.classList.toggle("collapsible-card--collapsed", !expanded);
    if (arrow) {
      arrow.textContent = expanded ? openArrow : closedArrow;
    }
  };

  const shouldStartOpen = (card) => {
    if (hashTarget && (card === hashTarget || card.contains(hashTarget))) {
      return true;
    }
    return Boolean(card.querySelector(".errorlist"));
  };

  cards.forEach((card) => {
    const toggle = card.querySelector("[data-survey-question-toggle]");
    if (!toggle) {
      return;
    }

    setExpanded(card, shouldStartOpen(card));
    toggle.addEventListener("click", () => {
      setExpanded(card, toggle.getAttribute("aria-expanded") !== "true");
    });
  });
})();

(() => {
  const dataElement = document.getElementById("condition-choice-cache");
  const parentInput = document.querySelector("[data-condition-parent]");
  const list = document.querySelector("[data-condition-choice-list]");
  if (!dataElement || !parentInput || !list) {
    return;
  }

  const choicesByQuestion = JSON.parse(dataElement.textContent || "{}");
  const choiceName = list.dataset.choiceName || "visible_if_choices";
  const emptyText = list.dataset.emptyText || "Select a controlling question to choose choices.";
  const noChoicesText = list.dataset.noChoicesText || "No choices are configured for this controlling question.";

  const selectedValues = () => new Set(
    Array.from(list.querySelectorAll('input[type="checkbox"]:checked')).map((input) => input.value),
  );

  const renderEmpty = (text) => {
    const message = document.createElement("p");
    message.className = "help-text";
    message.textContent = text;
    list.replaceChildren(message);
  };

  const renderChoices = () => {
    const selected = selectedValues();
    const parentId = parentInput.value;
    const choices = choicesByQuestion[parentId] || [];

    if (!parentId) {
      renderEmpty(emptyText);
      return;
    }
    if (choices.length === 0) {
      renderEmpty(noChoicesText);
      return;
    }

    list.replaceChildren();
    choices.forEach((choice) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      const text = document.createElement("span");
      const choiceId = String(choice.id);

      input.type = "checkbox";
      input.name = choiceName;
      input.value = choiceId;
      input.id = `id_${choiceName}_${choiceId}`;
      input.checked = selected.has(choiceId);
      label.className = "condition-choice-option";
      label.htmlFor = input.id;
      text.textContent = choice.label;
      label.append(input, text);
      list.append(label);
    });
  };

  parentInput.addEventListener("change", renderChoices);
  renderChoices();
})();
