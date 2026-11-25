// Muestra la TEM y la TEA equivalentes mientras se escribe una tasa.
// El cálculo lo hace el servidor (API /clientes/api/tasa-equivalente/); aquí solo se muestra.
(function () {
  "use strict";
  var url = document.body.dataset.apiTasa;
  if (!url) return;

  document.querySelectorAll("[data-tasa-grupo]").forEach(function (grupo) {
    var salida = grupo.querySelector(".ff-equivalente");
    var campo = function (rol) { return grupo.querySelector('[data-rol="' + rol + '"]'); };
    var temporizador = null;

    function actualizarCapitalizacion() {
      // La capitalización solo aplica a tasas nominales.
      var esNominal = campo("tipo").value === "NOMINAL";
      campo("capitalizacion").disabled = !esNominal;
      if (!esNominal) campo("capitalizacion").value = "";
    }

    function consultar() {
      actualizarCapitalizacion();
      var porcentaje = campo("porcentaje").value.trim();
      if (!porcentaje) { salida.textContent = "Escribe la tasa para ver su TEM y TEA equivalentes."; return; }
      FiaFacil.postJSON(url, {
        tipo: campo("tipo").value, porcentaje: porcentaje,
        periodo: campo("periodo").value, capitalizacion: campo("capitalizacion").value,
      }).then(function (r) {
        salida.classList.toggle("alert-danger", !r.ok);
        salida.classList.toggle("alert-light", r.ok);
        if (!r.ok) { salida.textContent = r.error; return; }
        salida.innerHTML = "<strong>Equivale a</strong> TEM " + r.tem_texto + " · TEA " + r.tea_texto +
          (r.supuestos.length ? '<br><span class="text-body-secondary">' + r.supuestos.join(" ") + "</span>" : "");
      }).catch(function () { salida.textContent = "No se pudo calcular ahora; revisa tu conexión."; });
    }

    ["tipo", "porcentaje", "periodo", "capitalizacion"].forEach(function (rol) {
      var el = campo(rol);
      el.addEventListener("input", function () { clearTimeout(temporizador); temporizador = setTimeout(consultar, 300); });
      el.addEventListener("change", consultar);
    });
    consultar();
  });
})();
