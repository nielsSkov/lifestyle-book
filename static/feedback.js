document.addEventListener("DOMContentLoaded", () => {
  const feedbackMessages = [...document.querySelectorAll("[data-feedback]")];
  if (!feedbackMessages.length) return;

  const cleanUrl = new URL(window.location.href);
  for (const parameter of ["saved", "deleted", "error"]) {
    cleanUrl.searchParams.delete(parameter);
  }
  window.history.replaceState(
    {},
    "",
    `${cleanUrl.pathname}${cleanUrl.search}${cleanUrl.hash}`,
  );

  window.setTimeout(() => {
    for (const message of feedbackMessages) message.remove();
  }, 3000);
});
