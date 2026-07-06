(() => {
  const maxVisibleItems = 10;

  const normalize = (value) => value.trim().toLowerCase().replace(/\s+/g, " ");

  const enhanceCombobox = (row, index) => {
    const select = row.querySelector("select[data-user-combobox-select]");
    if (!select) {
      return;
    }

    const items = Array.from(select.options)
      .filter((option) => option.value)
      .map((option) => ({
        label: option.dataset.userLabel || option.textContent.trim(),
        search: option.dataset.nameSearch || "",
        value: option.value,
      }))
      .filter((item) => item.search);

    if (items.length === 0) {
      return;
    }

    const label = row.querySelector(`label[for="${select.id}"]`);
    const wrapper = document.createElement("div");
    const input = document.createElement("input");
    const list = document.createElement("ul");
    const status = document.createElement("p");
    const listId = `${select.id || `user-combobox-${index}`}-list`;
    let activeIndex = -1;
    let visibleItems = [];

    wrapper.className = "combobox";
    input.id = `${select.id || `user-combobox-${index}`}-input`;
    input.type = "text";
    input.autocomplete = "off";
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", listId);
    input.setAttribute("aria-expanded", "false");
    input.placeholder = "Start typing a name";
    list.className = "combobox-list";
    list.hidden = true;
    list.id = listId;
    list.setAttribute("role", "listbox");
    status.className = "help-text combobox-status";
    status.setAttribute("aria-live", "polite");

    const selectedOption = select.selectedOptions[0];
    if (selectedOption && selectedOption.value) {
      input.value = selectedOption.dataset.userLabel || selectedOption.textContent.trim();
    }

    if (label) {
      label.htmlFor = input.id;
    }

    const closeList = () => {
      list.hidden = true;
      input.setAttribute("aria-expanded", "false");
      activeIndex = -1;
      input.removeAttribute("aria-activedescendant");
    };

    const setActive = (nextIndex) => {
      activeIndex = nextIndex;
      const options = Array.from(list.querySelectorAll("[role='option']"));
      options.forEach((option, optionIndex) => {
        const active = optionIndex === activeIndex;
        option.setAttribute("aria-selected", active ? "true" : "false");
        if (active) {
          input.setAttribute("aria-activedescendant", option.id);
          option.scrollIntoView({ block: "nearest" });
        }
      });
    };

    const chooseItem = (item) => {
      select.value = item.value;
      input.value = item.label;
      status.textContent = "";
      closeList();
    };

    const renderItems = () => {
      const query = normalize(input.value);
      const matches = items.filter((item) => !query || item.search.includes(query));
      visibleItems = matches.slice(0, maxVisibleItems);
      list.replaceChildren();

      if (visibleItems.length === 0) {
        const emptyItem = document.createElement("li");
        emptyItem.className = "combobox-option combobox-option-empty";
        emptyItem.textContent = "No matching named users.";
        list.append(emptyItem);
        status.textContent = "No matching named users.";
        activeIndex = -1;
        input.removeAttribute("aria-activedescendant");
        return;
      }

      visibleItems.forEach((item, itemIndex) => {
        const option = document.createElement("li");
        option.className = "combobox-option";
        option.id = `${listId}-${itemIndex}`;
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", "false");
        option.textContent = item.label;
        option.addEventListener("mousedown", (event) => {
          event.preventDefault();
          chooseItem(item);
        });
        list.append(option);
      });

      if (matches.length > maxVisibleItems) {
        status.textContent = `Showing ${maxVisibleItems} of ${matches.length} named users.`;
      } else {
        status.textContent = `Showing ${matches.length} named user${matches.length === 1 ? "" : "s"}.`;
      }
      setActive(-1);
    };

    const openList = () => {
      renderItems();
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
    };

    input.addEventListener("focus", openList);
    input.addEventListener("input", () => {
      select.value = "";
      openList();
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (list.hidden) {
          openList();
        }
        setActive(Math.min(activeIndex + 1, visibleItems.length - 1));
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        if (list.hidden) {
          openList();
        }
        setActive(Math.max(activeIndex - 1, 0));
      } else if (event.key === "Enter" && !list.hidden && activeIndex >= 0) {
        event.preventDefault();
        chooseItem(visibleItems[activeIndex]);
      } else if (event.key === "Escape") {
        closeList();
      }
    });

    document.addEventListener("click", (event) => {
      if (!wrapper.contains(event.target)) {
        closeList();
      }
    });

    select.before(wrapper);
    wrapper.append(input, list, status);
    select.hidden = true;
  };

  document.querySelectorAll("[data-user-combobox]").forEach(enhanceCombobox);
})();
