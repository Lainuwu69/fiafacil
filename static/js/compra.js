// Nueva venta: líneas dinámicas y simulación en vivo.
// Todo el cálculo lo hace el servidor (/compras/simular/); este archivo solo arma la
// solicitud y dibuja la respuesta. Al confirmar, el servidor vuelve a calcular todo.
(function () {
  "use strict";
  var form = document.getElementById("form-venta");
  if (!form) return;
  var tbody = document.querySelector("#tabla-lineas tbody");
  var plantilla = document.getElementById("plantilla-linea");
  var resultado = document.getElementById("resultado");
  var boton = document.getElementById("btn-confirmar");
  var temporizador = null;

  function esc(t) { var d = document.createElement("div"); d.textContent = t == null ? "" : String(t); return d.innerHTML; }
  function miles(v) {
    if (v == null) return "—";
    var p = String(v).split("."), e = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return e + "." + ((p[1] || "") + "00").slice(0, 2);
  }

  function agregarLinea() {
    tbody.appendChild(plantilla.content.cloneNode(true));
    programar();
  }
  if (!tbody.querySelector(".ff-linea")) agregarLinea();
  document.getElementById("agregar-linea").addEventListener("click", agregarLinea);
  tbody.addEventListener("click", function (e) {
    var b = e.target.closest(".ff-quitar");
    if (b) { b.closest("tr").remove(); if (!tbody.querySelector(".ff-linea")) agregarLinea(); programar(); }
  });

  function modalidad() { var r = form.querySelector('input[name="modalidad"]:checked'); return r ? r.value : ""; }

  function datos() {
    return {
      cuenta: form.cuenta.value,
      fecha_compra: form.fecha_compra.value,
      modalidad: modalidad(),
      n_cuotas: modalidad() === "CUOTAS" ? form.n_cuotas.value : null,
      lineas: Array.prototype.map.call(tbody.querySelectorAll(".ff-linea"), function (tr) {
        return { articulo_id: tr.querySelector('[name="articulo"]').value, cantidad: tr.querySelector('[name="cantidad"]').value };
      }),
    };
  }

  function dibujar(r) {
    var s = r.simbolo ? r.simbolo + " " : "";
    var h = "";
    if (r.errores && r.errores.length) {
      h += '<div class="alert alert-danger"><strong>No se puede registrar:</strong><ul class="mb-0">' +
        r.errores.map(function (e) { return "<li>" + esc(e) + "</li>"; }).join("") + "</ul></div>";
    }
    if (r.corte) {
      h += '<h2 class="h5">Resultado del cálculo</h2><dl class="row small mb-2">' +
        '<dt class="col-6">Corte del ciclo</dt><dd class="col-6">' + esc(r.corte) + "</dd>" +
        '<dt class="col-6">' + (r.cuotas ? "Fin de la gracia (G)" : "Vence (fecha de pago)") + '</dt><dd class="col-6">' + esc(r.fecha_pago) + "</dd>" +
        '<dt class="col-6">Capital (precio de lista)</dt><dd class="col-6">' + s + miles(r.capital) + "</dd>" +
        '<dt class="col-6">Condiciones aplicadas</dt><dd class="col-6">versión ' + esc(r.condicion) + "</dd>";
      if (r.mensual) {
        h += '<dt class="col-6">Días financiados</dt><dd class="col-6">' + r.mensual.dias + "</dd>" +
          '<dt class="col-6">Tasa del periodo i(' + r.mensual.dias + ')</dt><dd class="col-6">' + esc(r.mensual.tasa) + "</dd>" +
          '<dt class="col-6">Interés</dt><dd class="col-6">' + s + miles(r.mensual.interes) + "</dd>" +
          '<dt class="col-6 fs-6">Total a pagar</dt><dd class="col-6 fs-6 fw-bold">' + s + miles(r.mensual.total) + "</dd>";
      }
      if (r.cuotas) {
        var c = r.cuotas;
        h += '<dt class="col-6">Días de gracia total</dt><dd class="col-6">' + c.dias_gracia + "</dd>" +
          '<dt class="col-6">TEM</dt><dd class="col-6">' + esc(c.tem) + "</dd>" +
          '<dt class="col-6">Capital tras la gracia (Pg)</dt><dd class="col-6">' + s + miles(c.capital_con_gracia) + "</dd>" +
          '<dt class="col-6 fs-6">Cuota</dt><dd class="col-6 fs-6 fw-bold">' + s + miles(c.cuota) + "</dd></dl>" +
          '<div class="table-responsive"><table class="table table-sm small mb-2"><thead><tr><th>N°</th><th>Vence</th><th class="text-end">Saldo</th><th class="text-end">Interés</th><th class="text-end">Amort.</th><th class="text-end">Cuota</th><th class="text-end">Saldo final</th></tr></thead><tbody>' +
          c.filas.map(function (f) {
            return "<tr><td>" + f.numero + "</td><td>" + f.vencimiento + '</td><td class="ff-num">' + miles(f.saldo_inicial) +
              '</td><td class="ff-num">' + miles(f.interes) + '</td><td class="ff-num">' + miles(f.amortizacion) +
              '</td><td class="ff-num">' + miles(f.cuota) + '</td><td class="ff-num">' + miles(f.saldo_final) + "</td></tr>";
          }).join("") +
          '</tbody><tfoot><tr class="fw-semibold"><td colspan="5">Total pagado</td><td class="ff-num">' + miles(c.total) + "</td><td></td></tr></tfoot></table></div><dl class=\"row small mb-2\">";
      }
      h += '<dt class="col-6">TCEA <span title="Costo efectivo anual: tasa que iguala lo recibido con lo que se paga (año de 360 días)." data-bs-toggle="tooltip"><i class="bi bi-info-circle"></i></span></dt><dd class="col-6">' + esc(r.tcea || "—") + "</dd>" +
        '<dt class="col-6">TCEA sobre precio contado</dt><dd class="col-6">' + esc(r.tcea_contado || "—") + "</dd>" +
        '<dt class="col-6">Disponible antes → después</dt><dd class="col-6">' + s + miles(r.disponible_antes) + " → <strong>" + s + miles(r.disponible_despues) + "</strong></dd></dl>";
      if (r.alternativas && r.alternativas.length) {
        h += '<details class="small"><summary>Comparar alternativas de pago (sobre el precio contado ' + s + miles(r.capital_contado) + ')</summary>' +
          '<table class="table table-sm mt-2"><thead><tr><th>Alternativa</th><th class="text-end">Total</th><th class="text-end">Costo</th><th class="text-end">TCEA</th></tr></thead><tbody>' +
          r.alternativas.map(function (a) {
            return "<tr><td>" + esc(a.nombre) + '</td><td class="ff-num">' + miles(a.total) + '</td><td class="ff-num">' + miles(a.costo) + '</td><td class="ff-num">' + esc(a.tcea || "—") + "</td></tr>";
          }).join("") + "</tbody></table></details>";
      }
    } else if (!(r.errores && r.errores.length)) {
      h = '<p class="text-body-secondary mb-0">Completa el cliente y los artículos para ver el cálculo.</p>';
    }
    resultado.innerHTML = h;
    resultado.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) { new bootstrap.Tooltip(el); });
    boton.disabled = !r.valida;
  }

  function simular() {
    var d = datos();
    if (!d.cuenta) { dibujar({ valida: false, errores: [] }); return; }
    FiaFacil.postJSON(form.dataset.api, d).then(dibujar).catch(function () {
      resultado.innerHTML = '<div class="alert alert-warning">No se pudo calcular ahora. Revisa tu conexión.</div>';
      boton.disabled = true;
    });
  }
  function programar() { clearTimeout(temporizador); temporizador = setTimeout(simular, 300); }

  form.addEventListener("input", programar);
  form.addEventListener("change", function (e) {
    if (e.target.name === "modalidad") document.getElementById("bloque-cuotas").classList.toggle("d-none", modalidad() !== "CUOTAS");
    programar();
  });
  simular();
})();
