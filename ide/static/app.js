// cliente minimo del ide: junta el codigo del textarea, lo manda a POST /api/compile,
// y pinta la respuesta (diagnosticos + svg del ast). cero logica semantica aca: solo
// arma el request y renderiza lo que devuelve compiler_service.compile_source (via
// ide/app.py), que es quien de verdad compila.
(function () {
  const sourceEl = document.getElementById("source");
  const statusEl = document.getElementById("status");
  const listEl = document.getElementById("diagnostics-list");
  const astEl = document.getElementById("ast-container");
  const btnEl = document.getElementById("compile-btn");

  async function compile() {
    btnEl.disabled = true;
    statusEl.textContent = "Compilando...";
    statusEl.className = "";
    try {
      const response = await fetch("/api/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: sourceEl.value }),
      });
      const data = await response.json();
      renderResult(data);
    } catch (err) {
      statusEl.textContent = "Error de red al compilar: " + err;
      statusEl.className = "fail";
    } finally {
      btnEl.disabled = false;
    }
  }

  function renderResult(data) {
    statusEl.textContent = data.success
      ? "Compilación exitosa, sin errores."
      : `Compilación con ${data.diagnostics.length} diagnóstico(s).`;
    statusEl.className = data.success ? "ok" : "fail";

    listEl.innerHTML = "";
    for (const diag of data.diagnostics) {
      const li = document.createElement("li");
      li.className = diag.severity;
      li.innerHTML =
        `<span class="code">${diag.code}</span> ` +
        `<span class="pos">${diag.line}:${diag.column}</span> &mdash; ${diag.message}`;
      listEl.appendChild(li);
    }
    if (data.diagnostics.length === 0) {
      const li = document.createElement("li");
      li.className = "";
      li.style.borderLeftColor = "#81c995";
      li.textContent = "Sin diagnósticos.";
      listEl.appendChild(li);
    }

    astEl.innerHTML = data.ast_svg
      ? data.ast_svg
      : '<p class="hint">No hay AST disponible (error de sintaxis, o Graphviz no está instalado en el servidor).</p>';
  }

  btnEl.addEventListener("click", compile);
})();
