document.addEventListener("DOMContentLoaded", () => {
  for (const navigation of document.querySelectorAll("[data-date-navigation]")) {
    const dateInput = navigation.querySelector("[data-date-input]");
    const nightLabel = navigation.querySelector("[data-night-label]");
    const nextButton = navigation.querySelector('[data-date-step="1"]');
    const today = navigation.dataset.today;

    function selectDate(value) {
      const selected = value > today ? today : value;
      dateInput.value = selected;
      if (nightLabel) nightLabel.textContent = formatNight(selected);
      nextButton.disabled = selected >= today;
      navigation.dispatchEvent(new CustomEvent("datechange", {detail: {date: selected}}));
    }

    function shiftDate(days) {
      const shifted = new Date(`${dateInput.value}T00:00:00Z`);
      shifted.setUTCDate(shifted.getUTCDate() + days);
      selectDate(shifted.toISOString().slice(0, 10));
    }

    for (const button of navigation.querySelectorAll("[data-date-step]")) {
      button.addEventListener("click", () => shiftDate(Number(button.dataset.dateStep)));
    }
    dateInput.addEventListener("change", () => selectDate(dateInput.value));
    selectDate(dateInput.value);
  }
});

function formatNight(value) {
  const start = new Date(`${value}T00:00:00Z`);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 1);
  const month = new Intl.DateTimeFormat("en-GB", {month: "short", timeZone: "UTC"});

  if (start.getUTCFullYear() !== end.getUTCFullYear()) {
    return `${start.getUTCDate()} ${month.format(start)} ${start.getUTCFullYear()}–${end.getUTCDate()} ${month.format(end)} ${end.getUTCFullYear()}`;
  }
  if (start.getUTCMonth() !== end.getUTCMonth()) {
    return `${start.getUTCDate()} ${month.format(start)}–${end.getUTCDate()} ${month.format(end)} ${start.getUTCFullYear()}`;
  }
  return `${start.getUTCDate()}–${end.getUTCDate()} ${month.format(start)} ${start.getUTCFullYear()}`;
}
