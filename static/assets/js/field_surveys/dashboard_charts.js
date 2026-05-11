(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    if (typeof ApexCharts === "undefined") return;
    var raw = document.getElementById("dashboard-chart-data");
    if (!raw) return;
    var data;
    try { data = JSON.parse(raw.textContent); } catch (e) { return; }

    var styles = getComputedStyle(document.documentElement);
    var colorPrimary = styles.getPropertyValue("--bs-primary").trim() || "#009ef7";
    var bodyColor = styles.getPropertyValue("--bs-body-color").trim() || "#3f4254";
    var borderColor = styles.getPropertyValue("--bs-border-color").trim() || "#eff2f5";
    var isDark = document.documentElement.getAttribute("data-bs-theme") === "dark";

    renderResultsDonut(data, bodyColor, isDark);
    renderVisitsTrend(data, colorPrimary, bodyColor, borderColor, isDark);
  });

  function clearChildren(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function renderResultsDonut(data, bodyColor, isDark) {
    var chartEl = document.getElementById("kt_chart_results_distribution");
    var legendEl = document.getElementById("kt_chart_results_legend");
    if (!chartEl || !data.results) return;

    var labels = data.results.map(function (d) { return d.label; });
    var values = data.results.map(function (d) { return d.value; });
    var colors = data.results.map(function (d) { return d.color; });
    var total = values.reduce(function (a, b) { return a + b; }, 0);

    if (!total) {
      var empty = document.createElement("div");
      empty.className = "text-center py-10 w-100";
      var emptyIcon = document.createElement("i");
      emptyIcon.setAttribute("data-lucide", "pie-chart");
      emptyIcon.className = "fs-3hx text-muted mb-3 d-block";
      var emptyText = document.createElement("span");
      emptyText.className = "text-muted fs-6";
      emptyText.textContent = "Sin datos para los filtros activos.";
      empty.appendChild(emptyIcon);
      empty.appendChild(emptyText);
      chartEl.appendChild(empty);
      return;
    }

    new ApexCharts(chartEl, {
      chart: { type: "donut", height: 230 },
      series: values,
      labels: labels,
      colors: colors,
      legend: { show: false },
      dataLabels: { enabled: false },
      stroke: { width: 2 },
      plotOptions: {
        pie: {
          donut: {
            size: "70%",
            labels: {
              show: true,
              total: {
                show: true,
                label: "Total",
                fontSize: "12px",
                fontWeight: 600,
                color: bodyColor,
                formatter: function () { return String(total); }
              },
              value: { fontSize: "20px", fontWeight: 700, color: bodyColor }
            }
          }
        }
      },
      tooltip: { theme: isDark ? "dark" : "light" }
    }).render();

    if (!legendEl) return;
    data.results.forEach(function (d) {
      var pct = total ? Math.round((d.value / total) * 100) : 0;

      var row = document.createElement("div");
      row.className = "d-flex align-items-center justify-content-between";

      var leftSide = document.createElement("div");
      leftSide.className = "d-flex align-items-center gap-2";
      var dot = document.createElement("span");
      dot.className = "bullet bullet-dot h-8px w-8px";
      dot.style.backgroundColor = d.color;
      var label = document.createElement("span");
      label.className = "fs-7 text-gray-700";
      label.textContent = d.label;
      leftSide.appendChild(dot);
      leftSide.appendChild(label);

      var rightSide = document.createElement("div");
      rightSide.className = "d-flex align-items-center gap-2";
      var valueEl = document.createElement("span");
      valueEl.className = "fs-7 fw-bold text-gray-900";
      valueEl.textContent = String(d.value);
      var pctEl = document.createElement("span");
      pctEl.className = "fs-8 text-muted";
      pctEl.textContent = "(" + pct + "%)";
      rightSide.appendChild(valueEl);
      rightSide.appendChild(pctEl);

      row.appendChild(leftSide);
      row.appendChild(rightSide);
      legendEl.appendChild(row);
    });
  }

  function renderVisitsTrend(data, colorPrimary, bodyColor, borderColor, isDark) {
    var trendEl = document.getElementById("kt_chart_visits_trend");
    if (!trendEl || !data.trend) return;

    var values = data.trend.values || [];
    var hasData = values.some(function (v) { return v > 0; });
    if (!hasData) {
      clearChildren(trendEl);
      var empty = document.createElement("div");
      empty.className = "text-center py-10 w-100";
      var emptyIcon = document.createElement("i");
      emptyIcon.setAttribute("data-lucide", "trending-up");
      emptyIcon.className = "fs-3hx text-muted mb-3 d-block";
      var emptyTitle = document.createElement("h4");
      emptyTitle.className = "fs-5 fw-bold text-gray-900 mb-1";
      emptyTitle.textContent = "Sin visitas en el rango";
      var emptyText = document.createElement("p");
      emptyText.className = "text-muted fs-7 mb-0";
      emptyText.textContent = "Amplía el rango de fechas para ver la tendencia.";
      empty.appendChild(emptyIcon);
      empty.appendChild(emptyTitle);
      empty.appendChild(emptyText);
      trendEl.appendChild(empty);
      return;
    }

    new ApexCharts(trendEl, {
      chart: { type: "area", height: 275, toolbar: { show: false } },
      series: [{ name: "Visitas", data: values }],
      xaxis: {
        categories: data.trend.labels,
        labels: { style: { colors: bodyColor, fontSize: "11px" } },
        axisBorder: { show: false },
        axisTicks: { show: false },
        tickAmount: Math.min(data.trend.labels.length - 1, 8)
      },
      yaxis: {
        labels: {
          style: { colors: bodyColor, fontSize: "12px" },
          formatter: function (v) { return Math.round(v); }
        }
      },
      dataLabels: { enabled: false },
      stroke: { curve: "smooth", width: 3 },
      fill: {
        type: "gradient",
        gradient: { shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0.05, stops: [0, 90, 100] }
      },
      colors: [colorPrimary],
      grid: { borderColor: borderColor, strokeDashArray: 4 },
      tooltip: { theme: isDark ? "dark" : "light" },
      markers: { size: 4, colors: [colorPrimary], strokeColors: "#fff", strokeWidth: 2 }
    }).render();
  }
})();
