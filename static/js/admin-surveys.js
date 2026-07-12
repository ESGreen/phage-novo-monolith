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
