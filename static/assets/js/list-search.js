"use strict";

(function () {
  function initListSearch() {
    const input = document.getElementById("id_table_search");
    const form = document.getElementById("list-search-form");

    if (!input || !form) return;

    const url = new URL(window.location.href);
    const initialTags = (url.searchParams.get("search") || "")
      .split(/[,;]+/)
      .map((value) => value.trim())
      .filter(Boolean);

    let tagify = null;
    if (typeof Tagify !== "undefined") {
      tagify = new Tagify(input, {
        delimiters: ",",
        dropdown: { enabled: 0 },
        editTags: 1,
        placeholder: input.getAttribute("placeholder") || "Buscar...",
        transformTag: (tagData) => {
          tagData.class = "tagify__tag tagify__tag-light--primary";
        },
      });

      if (initialTags.length) {
        tagify.removeAllTags();
        tagify.addTags(initialTags);
      }
    }

    const getSearchValue = () => {
      if (!tagify) {
        return (input.value || "")
          .split(/[,;]+/)
          .map((value) => value.trim())
          .filter(Boolean)
          .join(",");
      }

      const values = tagify.value.map((tag) => tag.value.trim()).filter(Boolean);
      const pending = (tagify.DOM.input.textContent || "").trim();
      if (pending) values.push(pending);
      return values.join(",");
    };

    const submitSearch = (event) => {
      if (event) event.preventDefault();

      const searchValue = getSearchValue();
      if (searchValue) {
        url.searchParams.set("search", searchValue);
      } else {
        url.searchParams.delete("search");
      }
      url.searchParams.delete("page");

      window.location.search = url.search;
    };

    form.addEventListener("submit", submitSearch);

    if (tagify) {
      tagify.DOM.input.addEventListener(
        "keydown",
        (event) => {
          if (event.key === "Enter") {
            submitSearch(event);
          }
        },
        true
      );
    } else {
      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") submitSearch(event);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initListSearch);
  } else {
    initListSearch();
  }
})();
