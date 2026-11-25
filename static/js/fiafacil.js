// FíaFácil: comportamiento común de todas las páginas (sin frameworks).
// El JavaScript solo muestra información; todos los cálculos financieros se hacen en el servidor.
(function () {
  "use strict";

  // Activa los tooltips de ayuda (ícono ⓘ de cada campo).
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
    new bootstrap.Tooltip(el);
  });

  // Evita el doble envío de formularios (doble clic en "Guardar" o "Registrar pago").
  document.querySelectorAll("form[data-un-envio]").forEach(function (form) {
    form.addEventListener("submit", function () {
      form.querySelectorAll('button[type="submit"]').forEach(function (b) {
        b.disabled = true;
        b.dataset.textoOriginal = b.innerHTML;
        b.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Procesando…';
      });
    });
  });

  // Utilidad para las pantallas con cálculo en vivo: envía JSON al servidor con el token CSRF.
  window.FiaFacil = {
    csrf: function () {
      var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
      return m ? decodeURIComponent(m[1]) : "";
    },
    postJSON: function (url, datos) {
      return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": window.FiaFacil.csrf() },
        credentials: "same-origin",
        body: JSON.stringify(datos),
      }).then(function (r) { return r.json(); });
    },
  };
})();
