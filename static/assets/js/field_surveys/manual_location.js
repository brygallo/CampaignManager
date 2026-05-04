(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".leaflet-map-widget [data-leaflet-current-location]").forEach(function (button) {
      button.classList.remove("btn-sm");
      button.classList.add("btn-lg");
    });
  });
})();
