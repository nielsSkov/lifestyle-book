document.addEventListener("DOMContentLoaded", () => {
  for (const navigation of document.querySelectorAll("[data-date-navigation]")) {
    const dateInput = navigation.querySelector("[data-date-input]");
    const nextButton = navigation.querySelector('[data-date-step="1"]');
    const today = navigation.dataset.today;

    function selectDate(value) {
      const selected = value > today ? today : value;
      dateInput.value = selected;
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
