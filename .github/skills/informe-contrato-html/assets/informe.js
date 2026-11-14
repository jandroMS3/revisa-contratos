(function () {
  var d = document, root = d.documentElement;

  // Tema claro/oscuro (recuerda la elección si el navegador lo permite)
  try { var t = localStorage.getItem("informe-tema"); if (t) root.setAttribute("data-tema", t); } catch (e) {}
  var botonTema = d.querySelector(".tema");
  if (botonTema) botonTema.addEventListener("click", function () {
    var oscuro = root.getAttribute("data-tema") === "oscuro" ||
      (!root.getAttribute("data-tema") && matchMedia("(prefers-color-scheme: dark)").matches);
    var nuevo = oscuro ? "claro" : "oscuro";
    root.setAttribute("data-tema", nuevo);
    try { localStorage.setItem("informe-tema", nuevo); } catch (e) {}
  });

  // Filtro de riesgos por severidad
  var filtros = d.querySelectorAll(".filtros button[data-f]");
  filtros.forEach(function (b) {
    b.addEventListener("click", function () {
      var f = b.getAttribute("data-f");
      filtros.forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      d.querySelectorAll("#riesgos .card[data-sev]").forEach(function (c) {
        c.hidden = f !== "todos" && c.getAttribute("data-sev") !== f;
      });
    });
  });

  // Abrir / cerrar todas las tarjetas de una sección
  d.querySelectorAll("button[data-plegar]").forEach(function (b) {
    b.addEventListener("click", function () {
      var tarjetas = d.querySelectorAll("#" + b.getAttribute("data-plegar") + " details.card");
      var abrir = Array.prototype.some.call(tarjetas, function (c) { return !c.open; });
      tarjetas.forEach(function (c) { c.open = abrir; });
    });
  });

  // Los enlaces internos abren la tarjeta de destino
  function abrirDestino() {
    var el = location.hash ? d.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    if (el && el.tagName === "DETAILS") { el.hidden = false; el.open = true; }
  }
  addEventListener("hashchange", abrirDestino);
  d.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a) return;
    var el = d.getElementById(a.getAttribute("href").slice(1));
    if (el && el.tagName === "DETAILS") { el.hidden = false; el.open = true; }
  });
  abrirDestino();

  // Copiar redacciones sugeridas
  d.querySelectorAll(".copiar").forEach(function (b) {
    b.addEventListener("click", function () {
      var texto = b.parentNode.querySelector(".redaccion").textContent;
      var listo = function () { b.textContent = "Copiado"; setTimeout(function () { b.textContent = "Copiar"; }, 1500); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(texto).then(listo, function () {});
      } else {
        var ta = d.createElement("textarea"); ta.value = texto; d.body.appendChild(ta); ta.select();
        try { d.execCommand("copy"); listo(); } catch (e) {}
        d.body.removeChild(ta);
      }
    });
  });

  // Sección activa en el índice
  var enlaces = {};
  d.querySelectorAll("nav.toc a").forEach(function (a) { enlaces[a.getAttribute("href").slice(1)] = a; });
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (en) {
        if (en.isIntersecting && enlaces[en.target.id]) {
          Object.keys(enlaces).forEach(function (k) { enlaces[k].classList.remove("activo"); });
          enlaces[en.target.id].classList.add("activo");
        }
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    d.querySelectorAll("main > section").forEach(function (s) { io.observe(s); });
  }

  // Al imprimir, todo desplegado
  addEventListener("beforeprint", function () {
    d.querySelectorAll("details").forEach(function (x) { x.setAttribute("data-estaba", x.open ? "1" : "0"); x.open = true; });
  });
  addEventListener("afterprint", function () {
    d.querySelectorAll("details[data-estaba]").forEach(function (x) { x.open = x.getAttribute("data-estaba") === "1"; });
  });
})();
