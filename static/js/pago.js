// Pago: muestra la liquidación que calcula el servidor (mora → interés → capital).
// El importe recibido lo escribe el usuario; el servidor exige que sea exactamente el total.
(function () {
  "use strict";
  var form = document.getElementById("form-pago");
  if (!form) return;
  var salida = document.getElementById("liquidacion");
  var usarTotal = document.getElementById("usar-total");
  var total = null;

  function esc(t) { var d = document.createElement("div"); d.textContent = t == null ? "" : String(t); return d.innerHTML; }
  function miles(v) { var p = String(v).split("."); return p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",") + "." + ((p[1] || "") + "00").slice(0, 2); }
  function seleccion() { return Array.prototype.map.call(form.querySelectorAll('input[name="obligacion"]:checked'), function (c) { return c.value; }); }

  function calcular() {
    var ids = seleccion();
    total = null; usarTotal.disabled = true;
    if (!ids.length) { salida.innerHTML = '<p class="text-body-secondary small">Marca al menos una obligación para ver el total.</p>'; return; }
    FiaFacil.postJSON(form.dataset.api, { obligaciones: ids, fecha: form.fecha_efectiva.value }).then(function (r) {
      if (!r.ok) { salida.innerHTML = '<div class="alert alert-danger small">' + esc(r.error) + "</div>"; return; }
      var s = r.simbolo + " ";
      salida.innerHTML =
        '<table class="table table-sm small"><thead><tr><th>Obligación</th><th class="text-end">Días mora</th><th class="text-end">Mora</th><th class="text-end">Interés</th><th class="text-end">Capital</th></tr></thead><tbody>' +
        r.items.map(function (i) {
          return "<tr><td>" + esc(i.concepto) + '</td><td class="ff-num">' + i.dias_mora + '</td><td class="ff-num">' + miles(i.mora) +
            '</td><td class="ff-num">' + miles(i.interes) + '</td><td class="ff-num">' + miles(i.capital) + "</td></tr>";
        }).join("") + "</tbody></table>" +
        '<dl class="row mb-2"><dt class="col-7">1. Intereses por mora</dt><dd class="col-5 ff-num">' + s + miles(r.mora) + "</dd>" +
        '<dt class="col-7">2. Interés compensatorio</dt><dd class="col-5 ff-num">' + s + miles(r.interes) + "</dd>" +
        '<dt class="col-7">3. Capital</dt><dd class="col-5 ff-num">' + s + miles(r.capital) + "</dd>" +
        '<dt class="col-7 fs-5">Total a pagar</dt><dd class="col-5 ff-num fs-5 fw-bold">' + s + miles(r.total) + "</dd></dl>" +
        '<p class="small text-body-secondary">El pago se aplica en ese orden (prelación del Anexo A).</p>';
      total = r.total; usarTotal.disabled = false;
    }).catch(function () { salida.innerHTML = '<div class="alert alert-warning small">No se pudo calcular ahora.</div>'; });
  }

  usarTotal.addEventListener("click", function () { if (total) form.importe.value = total; });
  document.getElementById("marcar-vencidas").addEventListener("click", function () {
    form.querySelectorAll('input[data-vencida="1"]').forEach(function (c) { c.checked = true; });
    calcular();
  });
  form.addEventListener("change", function (e) { if (e.target.name === "obligacion" || e.target.name === "fecha_efectiva") calcular(); });
  calcular();
})();
