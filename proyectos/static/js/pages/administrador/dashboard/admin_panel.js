document.addEventListener("DOMContentLoaded", function () {
  const dataNode = document.getElementById("adminDashboardData");
  if (!dataNode || typeof ApexCharts === "undefined") return;

  const parse = (name) => JSON.parse(dataNode.dataset[name] || "[]");
  const kpi3Labels = parse("kpi3Labels");
  const kpi3Data = parse("kpi3Data");
  const kpi4Labels = parse("kpi4Labels");
  const kpi4Data = parse("kpi4Data");
  const kpi6Labels = parse("kpi6Labels");
  const kpi6Data = parse("kpi6Data");

  function lineChart(selector, labels, values, seriesName, suffix) {
    const target = document.querySelector(selector);
    if (!target) return;
    new ApexCharts(target, {
      chart: { type: "line", height: 245, toolbar: { show: false }, foreColor: "#59616b" },
      series: [{ name: seriesName, data: values }],
      xaxis: { categories: labels, axisBorder: { color: "#e4e7eb" }, axisTicks: { color: "#e4e7eb" } },
      yaxis: { min: 0 },
      grid: { borderColor: "#e7eaed", strokeDashArray: 4 },
      stroke: { curve: "smooth", width: 3 },
      markers: { size: 4, strokeWidth: 2 },
      dataLabels: { enabled: false },
      colors: ["#d71920"],
      noData: { text: "Sin datos suficientes" },
      tooltip: { y: { formatter: (value) => `${suffix === "$" ? "$" : ""}${Number(value).toFixed(2)}${suffix === "$" ? "" : " " + suffix}` } }
    }).render();
  }

  lineChart("#kpi3", kpi3Labels, kpi3Data, "Consumo", "L");
  lineChart("#kpi4", kpi4Labels, kpi4Data, "Costo", "$");

  const pieTarget = document.querySelector("#kpi6");
  if (pieTarget) {
    new ApexCharts(pieTarget, {
      chart: { type: "donut", height: 245, foreColor: "#59616b" },
      series: kpi6Data,
      labels: kpi6Labels,
      colors: ["#d71920", "#23262b", "#6b7280", "#9ca3af"],
      legend: { position: "bottom", fontSize: "11px" },
      dataLabels: { enabled: true, formatter: (value) => `${value.toFixed(1)}%` },
      stroke: { colors: ["#ffffff"], width: 2 },
      plotOptions: { pie: { donut: { size: "58%" } } },
      noData: { text: "Sin datos suficientes" },
      tooltip: { y: { formatter: (value) => `${Number(value).toFixed(2)} L` } }
    }).render();
  }
});
