(() => {
  const suggestions = Array.from(document.querySelectorAll("[data-url-suggestion]"))
    .map((element) => element.dataset.urlSuggestion || "")
    .filter(Boolean);
  if (suggestions.length === 0) {
    return;
  }

  const maxVisibleItems = 10;
  const normalize = (value) => value.trim().toLowerCase();

  const enhanceUrlInput = (input, index) => {
    const wrapper = document.createElement("div");
    const list = document.createElement("ul");
    const listId = `${input.id || `url-combobox-${index}`}-list`;
    let activeIndex = -1;
    let visibleItems = [];

    if (!input.id) {
      input.id = `url-combobox-${index}`;
    }
    wrapper.className = "combobox";
    list.className = "combobox-list";
    list.hidden = true;
    list.id = listId;
    list.setAttribute("role", "listbox");
    input.setAttribute("autocomplete", "off");
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", listId);
    input.setAttribute("aria-expanded", "false");

    input.before(wrapper);
    wrapper.append(input, list);

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

    const chooseItem = (value) => {
      input.value = value;
      closeList();
    };

    const renderItems = () => {
      const query = normalize(input.value);
      visibleItems = suggestions
        .filter((suggestion) => !query || normalize(suggestion).includes(query))
        .slice(0, maxVisibleItems);
      list.replaceChildren();

      if (visibleItems.length === 0) {
        closeList();
        return;
      }

      visibleItems.forEach((suggestion, suggestionIndex) => {
        const option = document.createElement("li");
        option.className = "combobox-option";
        option.id = `${listId}-${suggestionIndex}`;
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", "false");
        option.textContent = suggestion;
        option.addEventListener("mousedown", (event) => {
          event.preventDefault();
          chooseItem(suggestion);
        });
        list.append(option);
      });
      setActive(-1);
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
    };

    input.addEventListener("focus", renderItems);
    input.addEventListener("input", renderItems);
    input.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (list.hidden) {
          renderItems();
        }
        setActive(Math.min(activeIndex + 1, visibleItems.length - 1));
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        if (list.hidden) {
          renderItems();
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
  };

  document.querySelectorAll("[data-url-combobox-input]").forEach(enhanceUrlInput);
})();
