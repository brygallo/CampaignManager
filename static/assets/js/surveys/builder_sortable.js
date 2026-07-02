(function () {
  function idsFrom(container, idAttr) {
    return Array.prototype.slice.call(container.children)
      .filter(function (child) { return child.matches("[data-sort-item]"); })
      .map(function (node) { return node.dataset[idAttr]; })
      .filter(Boolean);
  }

  function csrfToken() {
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input) return input.value;
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function SurveyBuilderSortable(root) {
    this.root = root;
    this.reorderUrl = root.dataset.reorderUrl;
    this.drag = null;
  }

  SurveyBuilderSortable.prototype.postOrder = function (type, ids, sectionId) {
    var data = new FormData();
    data.append("type", type);
    ids.forEach(function (id) { data.append("ids[]", id); });
    if (type === "questions") data.append("section_id", sectionId || "");
    fetch(this.reorderUrl, {
      method: "POST",
      body: data,
      headers: {
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest"
      },
      credentials: "same-origin"
    });
  };

  SurveyBuilderSortable.prototype.postAllQuestionOrders = function () {
    var self = this;
    this.root.querySelectorAll('[data-sortable="questions"]').forEach(function (container) {
      self.postOrder("questions", idsFrom(container, "questionId"), container.dataset.sectionTarget);
    });
  };

  SurveyBuilderSortable.prototype.enableJquerySortable = function () {
    if (!window.jQuery || typeof window.jQuery.fn.sortable !== "function") return false;
    var self = this;
    var $ = window.jQuery;
    $(this.root).find('[data-sortable="sections"]').sortable({
      handle: "[data-drag-handle]",
      items: "[data-sort-item]",
      tolerance: "pointer",
      update: function () {
        self.postOrder("sections", idsFrom(this, "sectionId"));
      }
    });
    $(this.root).find('[data-sortable="questions"]').sortable({
      connectWith: '[data-sortable="questions"]',
      handle: "[data-drag-handle]",
      items: "[data-sort-item]",
      tolerance: "pointer",
      placeholder: "survey-builder-placeholder",
      start: function (event, ui) {
        ui.placeholder.height(ui.item.outerHeight());
      },
      update: function () {
        self.postAllQuestionOrders();
      }
    });
    return true;
  };

  SurveyBuilderSortable.prototype.init = function () {
    if (this.enableJquerySortable()) return;
    var self = this;
    this.root.querySelectorAll("[data-drag-handle]").forEach(function (handle) {
      handle.style.touchAction = "none";
      handle.addEventListener("pointerdown", function (event) {
        self.start(event, handle);
      });
    });
  };

  SurveyBuilderSortable.prototype.start = function (event, handle) {
    if (event.button !== undefined && event.button !== 0) return;
    var item = handle.closest("[data-sort-item]");
    var container = item && item.parentElement && item.parentElement.closest("[data-sortable]");
    if (!item || !container) return;
    event.preventDefault();

    var rect = item.getBoundingClientRect();
    var placeholder = document.createElement("div");
    placeholder.className = "survey-builder-placeholder";
    placeholder.style.height = rect.height + "px";
    container.insertBefore(placeholder, item.nextSibling);

    item.classList.add("is-dragging");
    item.style.position = "fixed";
    item.style.zIndex = "1080";
    item.style.width = rect.width + "px";
    item.style.left = rect.left + "px";
    item.style.top = rect.top + "px";
    item.style.pointerEvents = "none";

    handle.setPointerCapture(event.pointerId);
    this.drag = {
      handle: handle,
      pointerId: event.pointerId,
      item: item,
      placeholder: placeholder,
      type: container.dataset.sortable,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top
    };

    this.onMoveBound = this.move.bind(this);
    this.onEndBound = this.end.bind(this);
    handle.addEventListener("pointermove", this.onMoveBound);
    handle.addEventListener("pointerup", this.onEndBound);
    handle.addEventListener("pointercancel", this.onEndBound);
  };

  SurveyBuilderSortable.prototype.allowedContainer = function (event) {
    var drag = this.drag;
    var elements = document.elementsFromPoint(event.clientX, event.clientY);
    for (var index = 0; index < elements.length; index += 1) {
      var container = elements[index].closest && elements[index].closest("[data-sortable]");
      if (!container || !this.root.contains(container)) continue;
      if (drag.type === "sections" && container.dataset.sortable !== "sections") continue;
      if (drag.type === "questions" && container.dataset.sortable !== "questions") continue;
      return container;
    }
    return null;
  };

  SurveyBuilderSortable.prototype.move = function (event) {
    var drag = this.drag;
    if (!drag || event.pointerId !== drag.pointerId) return;
    event.preventDefault();

    drag.item.style.left = (event.clientX - drag.offsetX) + "px";
    drag.item.style.top = (event.clientY - drag.offsetY) + "px";
    this.autoScroll(event.clientY);

    var container = this.allowedContainer(event);
    this.root.querySelectorAll(".is-drag-over").forEach(function (node) {
      node.classList.remove("is-drag-over");
    });
    if (!container) return;
    container.classList.add("is-drag-over");

    var before = null;
    var items = Array.prototype.slice.call(container.children).filter(function (child) {
      return child.matches("[data-sort-item]") && child !== drag.item;
    });
    for (var index = 0; index < items.length; index += 1) {
      var rect = items[index].getBoundingClientRect();
      if (event.clientY < rect.top + rect.height / 2) {
        before = items[index];
        break;
      }
    }
    container.insertBefore(drag.placeholder, before);
  };

  SurveyBuilderSortable.prototype.autoScroll = function (clientY) {
    var edge = 72;
    var speed = 18;
    if (clientY < edge) {
      window.scrollBy(0, -speed);
    } else if (window.innerHeight - clientY < edge) {
      window.scrollBy(0, speed);
    }
  };

  SurveyBuilderSortable.prototype.end = function (event) {
    var drag = this.drag;
    if (!drag || event.pointerId !== drag.pointerId) return;

    drag.handle.removeEventListener("pointermove", this.onMoveBound);
    drag.handle.removeEventListener("pointerup", this.onEndBound);
    drag.handle.removeEventListener("pointercancel", this.onEndBound);
    try {
      drag.handle.releasePointerCapture(drag.pointerId);
    } catch (error) {
      // Pointer capture may already be released by the browser on cancel.
    }

    drag.placeholder.replaceWith(drag.item);
    drag.item.classList.remove("is-dragging");
    drag.item.style.position = "";
    drag.item.style.zIndex = "";
    drag.item.style.width = "";
    drag.item.style.left = "";
    drag.item.style.top = "";
    drag.item.style.pointerEvents = "";
    this.root.querySelectorAll(".is-drag-over").forEach(function (node) {
      node.classList.remove("is-drag-over");
    });

    if (drag.type === "questions") {
      this.postAllQuestionOrders();
    } else {
      var container = drag.item.parentElement.closest('[data-sortable="sections"]');
      this.postOrder("sections", idsFrom(container, "sectionId"));
    }
    this.drag = null;
  };

  window.SurveyBuilderSortable = SurveyBuilderSortable;
})();
