(function () {
  const installed = new WeakSet();

  function plotElement(target) {
    return typeof target === "string" ? document.getElementById(target) : target;
  }

  function dataWithoutFloatingLabels(data) {
    return data.map((trace) => trace.hoverinfo === "skip"
      ? trace
      : {...trace, hoverinfo: "none", hovertemplate: null});
  }

  function pointDate(value) {
    const parsed = value instanceof Date
      ? value
      : new Date(typeof value === "number" ? value : `${value}T12:00:00Z`);
    return Number.isFinite(parsed.getTime()) ? parsed : null;
  }

  function dateLabel(point, night) {
    if (night && typeof point.customdata?.[0] === "string") {
      return point.customdata[0].replace(/<br\s*\/?>/gi, " ");
    }
    const date = pointDate(point.x);
    return date
      ? new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      }).format(date)
      : String(point.x);
  }

  function formattedValue(point, format) {
    if (format === "sleep") return point.customdata?.[1] ?? "";
    if (format === "achievement") return "Recorded";
    const value = Number(point.y);
    if (!Number.isFinite(value)) return "";
    if (format === "duration") return point.customdata?.[1] ?? `${value.toFixed(1)} hours`;
    if (format === "rate") return `${value >= 0 ? "+" : ""}${value.toFixed(2)} kg/week`;
    if (format === "difference") return `${value >= 0 ? "+" : ""}${value.toFixed(1)} kg vs plan`;
    return `${value.toFixed(1)} kg`;
  }

  function ensureReadout(plot) {
    const card = plot.closest(".graph-card");
    let readout = card?.querySelector(":scope > [data-plot-readout]");
    if (!readout && card) {
      readout = document.createElement("div");
      readout.className = "plot-readout";
      readout.dataset.plotReadout = "";
      readout.setAttribute("aria-live", "polite");
      card.append(readout);
    }
    return readout;
  }

  function reset(plot) {
    const readout = ensureReadout(plot);
    if (readout) readout.replaceChildren();
  }

  function update(plot, event, options) {
    const available = event.points.filter((point) => {
      if (options.format === "sleep" || options.format === "duration") return point.customdata?.[1];
      if (options.format === "achievement") return true;
      return Number.isFinite(Number(point.y));
    });
    if (!available.length) return;
    const inspectedDate = pointDate(available[0].x)?.toISOString().slice(0, 10);
    const points = available.filter((point) => {
      const date = pointDate(point.x)?.toISOString().slice(0, 10);
      return !inspectedDate || !date || date === inspectedDate;
    });
    const readout = ensureReadout(plot);
    if (!readout) return;

    const date = document.createElement("strong");
    date.className = "plot-readout-date";
    date.textContent = dateLabel(points[0], options.night);
    const values = document.createElement("span");
    values.className = "plot-readout-values";
    for (const point of points) {
      const row = document.createElement("span");
      row.className = "plot-readout-value";
      const marker = document.createElement("i");
      marker.style.setProperty(
        "--readout-color",
        point.fullData.line?.color
          ?? point.fullData.marker?.color
          ?? point.fullData.colorscale?.[0]?.[1]
          ?? "#a99db9",
      );
      const label = document.createElement("span");
      label.textContent = `${point.fullData.name}: `;
      const value = document.createElement("strong");
      value.textContent = formattedValue(point, options.format);
      row.append(marker, label, value);
      values.append(row);
    }
    readout.replaceChildren(date, values);
  }

  function install(plot, options) {
    plot.dataset.readoutFormat = options.format;
    plot.dataset.readoutNight = options.night ? "true" : "false";
    ensureReadout(plot);
    if (installed.has(plot)) return;
    installed.add(plot);
    const show = (event) => update(plot, event, {
      format: plot.dataset.readoutFormat,
      night: plot.dataset.readoutNight === "true",
    });
    plot.on("plotly_hover", show);
    plot.on("plotly_click", show);
  }

  async function newPlot(target, figure, config, options) {
    const plot = plotElement(target);
    const rendered = await Plotly.newPlot(
      plot,
      dataWithoutFloatingLabels(figure.data),
      figure.layout,
      config,
    );
    install(rendered, options);
    return rendered;
  }

  async function react(target, figure, config, options) {
    const plot = plotElement(target);
    reset(plot);
    const rendered = await Plotly.react(
      plot,
      dataWithoutFloatingLabels(figure.data),
      figure.layout,
      config,
    );
    install(rendered, options);
    return rendered;
  }

  window.PlotlyReadout = {dataWithoutFloatingLabels, install, newPlot, react, reset};
}());
