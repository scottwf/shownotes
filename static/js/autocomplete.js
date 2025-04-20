document.addEventListener("DOMContentLoaded", () => {
  setupAutocomplete("title1", "suggestions1", "shows");
  setupAutocomplete("title2", "suggestions2", "shows");
  setupAutocomplete("show", "suggestions-show", "shows");
  setupAutocomplete("character", "suggestions-character", "characters", () => {
    const contextInput = document.getElementById("show");
    return contextInput ? contextInput.value.trim() : "";
  });
});

function setupAutocomplete(inputId, suggestionId, endpoint, getContext = null) {
  const input = document.getElementById(inputId);
  const suggestionBox = document.getElementById(suggestionId);
  let currentFocus = -1;

  if (!input || !suggestionBox) return;

  input.addEventListener("input", async function () {
    const query = this.value.trim();
    if (query.length < 2) {
      suggestionBox.innerHTML = "";
      suggestionBox.style.display = "none";
      return;
    }

    let url = `/autocomplete/${endpoint}?q=${encodeURIComponent(query)}`;
    if (getContext) {
      const context = getContext();
      if (context) {
        url += `&context=${encodeURIComponent(context)}`;
      }
    }

    try {
      const response = await fetch(url);
      const suggestions = await response.json();

      renderSuggestions(suggestions);
    } catch (err) {
      console.error("Autocomplete fetch error:", err);
    }
  });

  input.addEventListener("keydown", function (e) {
    const items = suggestionBox.querySelectorAll(".suggestion-item");
    if (!items.length) return;

    if (e.key === "ArrowDown") {
      currentFocus = (currentFocus + 1) % items.length;
      updateActive(items);
      e.preventDefault();
    } else if (e.key === "ArrowUp") {
      currentFocus = (currentFocus - 1 + items.length) % items.length;
      updateActive(items);
      e.preventDefault();
    } else if (e.key === "Enter") {
      if (currentFocus >= 0 && currentFocus < items.length) {
        input.value = items[currentFocus].textContent;
        clearSuggestions();
        e.preventDefault();
      }
    }
  });

  document.addEventListener("click", function (e) {
    if (e.target !== input) {
      clearSuggestions();
    }
  });

  function renderSuggestions(suggestions) {
    suggestionBox.innerHTML = "";
    currentFocus = -1;

    suggestions.forEach(suggestion => {
      const div = document.createElement("div");
      div.textContent = suggestion;
      div.classList.add("suggestion-item");
      div.addEventListener("mousedown", function () {
        input.value = suggestion;
        clearSuggestions();
      });
      suggestionBox.appendChild(div);
    });

    suggestionBox.style.display = suggestions.length ? "block" : "none";
  }

  function clearSuggestions() {
    suggestionBox.innerHTML = "";
    suggestionBox.style.display = "none";
    currentFocus = -1;
  }

  function updateActive(items) {
    items.forEach(item => item.classList.remove("active"));
    if (currentFocus >= 0) {
      items[currentFocus].classList.add("active");
    }
  }
}