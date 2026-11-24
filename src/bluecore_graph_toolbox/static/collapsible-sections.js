/*
 * Remembers which collapsible sections (<details data-remember id="...">) are
 * open or closed, in this browser, so a reload keeps them as they were.
 *
 * Loaded at the end of the page, so saved states are put back before the
 * page is first drawn. Only a UI preference: if storage is blocked, sections
 * simply start as the page sets them.
 */
(function () {
  "use strict";

  var KEY = "bluecore:graph-toolbox:ui:sections";

  function load() {
    try {
      var saved = JSON.parse(window.localStorage.getItem(KEY) || "{}");
      return saved && typeof saved === "object" ? saved : {};
    } catch (error) {
      return {};
    }
  }

  function save(states) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(states));
    } catch (error) {
      // Storage blocked or full: the section still works, it just won't be remembered.
    }
  }

  var states = load();
  document.querySelectorAll("details[data-remember][id]").forEach(function (section) {
    if (typeof states[section.id] === "boolean") {
      section.open = states[section.id];
    }
    section.addEventListener("toggle", function () {
      states = load();
      states[section.id] = section.open;
      save(states);
    });
  });
})();
