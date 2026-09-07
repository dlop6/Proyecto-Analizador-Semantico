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
  const fileEl = document.getElementById("source-file");
  const fileNameEl = document.getElementById("file-name");
  const fileStatusEl = document.getElementById("file-status");
  const maxSourceBytes = Number(fileEl.dataset.maxSourceBytes);

  function clearResult() {
    listEl.innerHTML = "";
    statusEl.textContent = "";
    statusEl.className = "";
    astEl.innerHTML = '<p class="hint">Compilá para ver el árbol.</p>';
  }

  function setFileStatus(message, className) {
    fileStatusEl.textContent = message;
    fileStatusEl.className = `file-status ${className}`;
  }

  function loadSelectedFile() {
    const file = fileEl.files[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".cps")) {
      setFileStatus("Seleccioná un archivo con extensión .cps.", "fail");
      fileEl.value = "";
      return;
    }
    if (file.size > maxSourceBytes) {
      setFileStatus("El archivo excede el límite de 5 MiB.", "fail");
      fileEl.value = "";
      return;
    }

    const reader = new FileReader();
    reader.onload = function () {
      sourceEl.value = String(reader.result);
      fileNameEl.textContent = file.name;
      setFileStatus("Archivo cargado. Podés editarlo antes de compilar.", "ok");
      clearResult();
    };
    reader.onerror = function () {
      setFileStatus("No se pudo leer el archivo seleccionado.", "fail");
    };
    reader.readAsText(file, "UTF-8");
  }

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
      const code = document.createElement("span");
      code.className = "code";
      code.textContent = diag.code;
      const pos = document.createElement("span");
      pos.className = "pos";
      pos.textContent = `${diag.line}:${diag.column}`;
      li.append(code, " ", pos, " — ", diag.message);
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
  fileEl.addEventListener("change", loadSelectedFile);
})();
