// Cliente del IDE: renderiza resultados del compilador y ofrece ayudas locales de
// edición. El resaltado es léxico y visual; la semántica sigue siendo exclusiva del
// backend y de compiler_service.compile_source.
(function () {
  const sourceEl = document.getElementById("source");
  const workspaceEl = document.getElementById("workspace");
  const lineNumbersEl = document.getElementById("line-numbers");
  const highlightLayerEl = document.getElementById("highlight-layer");
  const highlightCodeEl = document.getElementById("highlight-code");
  const statusEl = document.getElementById("status");
  const listEl = document.getElementById("diagnostics-list");
  const filterEl = document.getElementById("diagnostic-filters");
  const copyBtnEl = document.getElementById("copy-diagnostics-btn");
  const copyStatusEl = document.getElementById("copy-status");
  const astEl = document.getElementById("ast-container");
  const symbolsEl = document.getElementById("symbols-container");
  const viewTabsEl = document.getElementById("view-tabs");
  const astControlsGroupEl = document.getElementById("ast-controls");
  const btnEl = document.getElementById("compile-btn");
  const fileEl = document.getElementById("source-file");
  const fileNameEl = document.getElementById("file-name");
  const fileStatusEl = document.getElementById("file-status");
  const astZoomOutEl = document.getElementById("ast-zoom-out");
  const astZoomInEl = document.getElementById("ast-zoom-in");
  const astResetEl = document.getElementById("ast-reset");
  const astFitEl = document.getElementById("ast-fit");
  const astDownloadEl = document.getElementById("ast-download");
  const astControlEls = [astZoomOutEl, astZoomInEl, astResetEl, astFitEl, astDownloadEl];
  const maxSourceBytes = Number(fileEl.dataset.maxSourceBytes);

  const TYPES = new Set(["integer", "string", "boolean"]);
  const LITERALS = new Set(["true", "false", "null"]);
  const KEYWORDS = new Set([
    "let", "var", "const", "function", "class", "if", "else", "while", "do", "for",
    "foreach", "in", "break", "continue", "return", "try", "catch", "switch", "case",
    "default", "new", "this", "print",
  ]);

  let animationFrame = 0;
  let compiling = false;
  let activeFilter = "all";
  let currentDiagnostics = [];
  let selectedDiagnosticKey = null;
  let loadedSource = null;
  let loadedFileName = "";
  let manuallyEdited = false;
  let currentAstSvg = null;
  let astScale = 1;
  let astDimensions = null;
  let activeView = "ast";

  function createTextNode(text, className) {
    if (!className) return document.createTextNode(text);
    const token = document.createElement("span");
    token.className = className;
    token.textContent = text;
    return token;
  }

  function nextNonWhitespace(source, start) {
    let index = start;
    while (index < source.length && /\s/.test(source[index])) index += 1;
    return source[index] || "";
  }

  function tokenize(source) {
    const tokens = [];
    let index = 0;
    let declarationKind = null;

    while (index < source.length) {
      const rest = source.slice(index);
      if (rest.startsWith("//")) {
        const end = source.indexOf("\n", index);
        const finish = end === -1 ? source.length : end;
        tokens.push([source.slice(index, finish), "token-comment"]);
        index = finish;
        continue;
      }
      if (rest.startsWith("/*")) {
        const end = source.indexOf("*/", index + 2);
        const finish = end === -1 ? source.length : end + 2;
        tokens.push([source.slice(index, finish), "token-comment"]);
        index = finish;
        continue;
      }
      if (source[index] === '"') {
        let finish = index + 1;
        while (finish < source.length && source[finish] !== '"' && source[finish] !== "\n") finish += 1;
        if (source[finish] === '"') finish += 1;
        tokens.push([source.slice(index, finish), "token-string"]);
        index = finish;
        continue;
      }
      if (/\d/.test(source[index])) {
        let finish = index + 1;
        while (finish < source.length && /\d/.test(source[finish])) finish += 1;
        tokens.push([source.slice(index, finish), "token-number"]);
        index = finish;
        continue;
      }
      if (/[A-Za-z_]/.test(source[index])) {
        let finish = index + 1;
        while (finish < source.length && /[A-Za-z0-9_]/.test(source[finish])) finish += 1;
        const word = source.slice(index, finish);
        let className = "";
        if (declarationKind === "function") className = "token-function";
        else if (declarationKind === "class" || declarationKind === "new") className = "token-class";
        else if (TYPES.has(word)) className = "token-type";
        else if (LITERALS.has(word)) className = "token-literal";
        else if (KEYWORDS.has(word)) className = "token-keyword";
        else if (nextNonWhitespace(source, finish) === "(") className = "token-function";
        tokens.push([word, className]);
        declarationKind = word === "function" || word === "class" || word === "new" ? word : null;
        index = finish;
        continue;
      }
      if (/[+\-*/%!=<>&|?:=.;,()[\]{}]/.test(source[index])) {
        tokens.push([source[index], "token-operator"]);
        index += 1;
        continue;
      }
      tokens.push([source[index], ""]);
      index += 1;
    }
    return tokens;
  }

  function syncEditorScroll() {
    highlightLayerEl.scrollTop = sourceEl.scrollTop;
    highlightLayerEl.scrollLeft = sourceEl.scrollLeft;
    lineNumbersEl.scrollTop = sourceEl.scrollTop;
  }

  function renderEditor() {
    animationFrame = 0;
    const fragment = document.createDocumentFragment();
    for (const [text, className] of tokenize(sourceEl.value)) {
      fragment.appendChild(createTextNode(text, className));
    }
    highlightCodeEl.replaceChildren(fragment);

    const lineFragment = document.createDocumentFragment();
    const count = sourceEl.value.split("\n").length;
    for (let line = 1; line <= count; line += 1) {
      const number = document.createElement("span");
      number.textContent = String(line);
      lineFragment.appendChild(number);
    }
    lineNumbersEl.replaceChildren(lineFragment);
    syncEditorScroll();
  }

  function scheduleEditorRender() {
    if (animationFrame) return;
    animationFrame = requestAnimationFrame(renderEditor);
  }

  function setFileStatus(message, className) {
    fileStatusEl.textContent = message;
    fileStatusEl.className = `file-status ${className || ""}`.trim();
  }

  function refreshFileName() {
    if (loadedSource !== null) {
      fileNameEl.textContent = loadedFileName + (sourceEl.value === loadedSource ? "" : " • modificado");
      return;
    }
    fileNameEl.textContent = manuallyEdited ? "Edición manual" : "Sin archivo seleccionado";
  }

  function setStatus(message, className) {
    statusEl.textContent = message;
    statusEl.className = className || "";
  }

  function setCopyStatus(message, className) {
    copyStatusEl.textContent = message;
    copyStatusEl.className = `utility-status ${className || ""}`.trim();
  }

  function setAstControls(enabled) {
    for (const control of astControlEls) control.disabled = !enabled;
  }

  function setAstEmpty(message) {
    currentAstSvg = null;
    astDimensions = null;
    astScale = 1;
    workspaceEl.classList.add("ast-empty");
    const hint = document.createElement("p");
    hint.className = "hint";
    hint.textContent = message;
    astEl.replaceChildren(hint);
    setAstControls(false);
  }

  function updateFilterButtons() {
    for (const button of filterEl.querySelectorAll("button[data-filter]")) {
      const active = button.dataset.filter === activeFilter;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    }
  }

  // AST y tabla de símbolos comparten la 3ra columna como pestañas: solo uno de
  // los dos paneles está visible a la vez, y los controles de zoom del AST solo
  // tienen sentido cuando esa pestaña está activa.
  function setActiveView(view) {
    activeView = view;
    astEl.hidden = view !== "ast";
    symbolsEl.hidden = view !== "symbols";
    astControlsGroupEl.hidden = view !== "ast";
    for (const button of viewTabsEl.querySelectorAll("button[data-view]")) {
      const active = button.dataset.view === view;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    }
  }

  function clearResult() {
    currentDiagnostics = [];
    activeFilter = "all";
    selectedDiagnosticKey = null;
    listEl.replaceChildren();
    setStatus("", "");
    setCopyStatus("", "");
    copyBtnEl.disabled = true;
    updateFilterButtons();
    setAstEmpty("Compilá para generar el árbol.");
    renderSymbols(null);
  }

  function diagnosticKey(diag) {
    return `${diag.code}:${diag.line}:${diag.column}`;
  }

  function lineColumnIndex(line, column) {
    const lines = sourceEl.value.split("\n");
    const lineIndex = Math.max(0, Math.min(lines.length - 1, Number(line) - 1));
    let index = 0;
    for (let current = 0; current < lineIndex; current += 1) index += lines[current].length + 1;
    const columnIndex = Math.max(0, Math.min(lines[lineIndex].length, Number(column) - 1));
    return index + columnIndex;
  }

  function jumpToDiagnostic(diag) {
    selectedDiagnosticKey = diagnosticKey(diag);
    renderDiagnostics();
    const start = lineColumnIndex(diag.line, diag.column);
    const end = Math.min(sourceEl.value.length, start + (start < sourceEl.value.length ? 1 : 0));
    sourceEl.focus();
    sourceEl.setSelectionRange(start, end);
    const lineHeight = Number.parseFloat(getComputedStyle(sourceEl).lineHeight) || 20;
    sourceEl.scrollTop = Math.max(0, (Number(diag.line) - 1) * lineHeight - sourceEl.clientHeight / 2);
    syncEditorScroll();
  }

  function renderDiagnostics() {
    const fragment = document.createDocumentFragment();
    const visible = currentDiagnostics.filter((diag) => activeFilter === "all" || diag.severity === activeFilter);
    for (const diag of visible) {
      const item = document.createElement("li");
      item.className = diag.severity;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "diagnostic-jump";
      if (diagnosticKey(diag) === selectedDiagnosticKey) button.classList.add("selected");
      const code = document.createElement("span");
      code.className = "code";
      code.textContent = diag.code;
      const pos = document.createElement("span");
      pos.className = "pos";
      pos.textContent = `${diag.line}:${diag.column}`;
      const message = document.createElement("span");
      message.className = "message";
      message.textContent = diag.message;
      button.append(code, " ", pos, " — ", message);
      button.addEventListener("click", () => jumpToDiagnostic(diag));
      item.appendChild(button);
      fragment.appendChild(item);
    }
    if (currentDiagnostics.length === 0) {
      const item = document.createElement("li");
      item.className = "empty-diagnostics";
      item.textContent = "Sin diagnósticos.";
      fragment.appendChild(item);
    } else if (visible.length === 0) {
      const item = document.createElement("li");
      item.className = "empty-diagnostics";
      item.textContent = "No hay diagnósticos en este filtro.";
      fragment.appendChild(item);
    }
    listEl.replaceChildren(fragment);
  }

  function formatCount(count, singular, plural) {
    return `${count} ${count === 1 ? singular : plural}`;
  }

  function setAstSvg(svgText) {
    currentAstSvg = svgText;
    astScale = 1;
    workspaceEl.classList.remove("ast-empty");
    // Graphviz escapa las etiquetas del AST; el servidor ya conserva esta garantía.
    astEl.innerHTML = svgText;
    const svg = astEl.querySelector("svg");
    if (!svg || !svg.viewBox || !svg.viewBox.baseVal.width || !svg.viewBox.baseVal.height) {
      setAstEmpty("No se pudo preparar el SVG del AST.");
      return;
    }
    astDimensions = { width: svg.viewBox.baseVal.width, height: svg.viewBox.baseVal.height };
    applyAstScale();
    setAstControls(true);
  }

  function applyAstScale() {
    const svg = astEl.querySelector("svg");
    if (!svg || !astDimensions) return;
    svg.style.width = `${astDimensions.width * astScale}px`;
    svg.style.height = `${astDimensions.height * astScale}px`;
  }

  function changeAstScale(delta) {
    astScale = Math.min(2.5, Math.max(0.25, Math.round((astScale + delta) * 100) / 100));
    applyAstScale();
  }

  function fitAst() {
    if (!astDimensions) return;
    const width = Math.max(1, astEl.clientWidth - 16);
    const height = Math.max(1, astEl.clientHeight - 16);
    astScale = Math.min(2.5, Math.max(0.25, Math.min(width / astDimensions.width, height / astDimensions.height)));
    applyAstScale();
  }

  function renderAstResult(data) {
    if (data.ast_svg) {
      setAstSvg(data.ast_svg);
      return;
    }
    const hasFrontendError = data.diagnostics.some((diag) => diag.code === "CPS-000" || diag.code === "CPS-001");
    setAstEmpty(hasFrontendError
      ? "No se construye AST cuando existen errores léxicos o sintácticos."
      : "El análisis terminó, pero Graphviz no está disponible para generar el AST.");
  }

  // representación mínima de un símbolo: nombre, tipo y detalle según su categoría
  // (variable/función/clase). todo por textContent, nunca por innerHTML con datos
  // del servidor -- misma garantía que ya aplica al resto del ide.
  function buildSymbolItem(symbol) {
    const item = document.createElement("li");
    item.className = `symbol-item kind-${symbol.kind}`;

    const name = document.createElement("span");
    name.className = "symbol-name";
    name.textContent = symbol.name;
    item.appendChild(name);

    if (symbol.kind === "function") {
      const signature = document.createElement("span");
      signature.className = "symbol-type";
      const params = symbol.params.join(", ");
      const returnType = symbol.return_type ? `: ${symbol.return_type}` : "";
      signature.textContent = `(${params})${returnType}`;
      item.appendChild(signature);
      if (symbol.is_constructor) item.appendChild(buildFlag("constructor"));
    } else if (symbol.kind === "class") {
      if (symbol.parent_name) {
        const parent = document.createElement("span");
        parent.className = "symbol-type";
        parent.textContent = `: ${symbol.parent_name}`;
        item.appendChild(parent);
      }
    } else {
      if (symbol.type) {
        const type = document.createElement("span");
        type.className = "symbol-type";
        type.textContent = `: ${symbol.type}`;
        item.appendChild(type);
      }
      if (symbol.is_const) item.appendChild(buildFlag("const"));
      if (symbol.is_param) item.appendChild(buildFlag("param"));
    }

    if (symbol.kind === "class" && (symbol.fields.length || symbol.methods.length)) {
      const members = document.createElement("ul");
      members.className = "symbol-list class-members";
      for (const field of symbol.fields) members.appendChild(buildSymbolItem(field));
      for (const method of symbol.methods) members.appendChild(buildSymbolItem(method));
      item.appendChild(members);
    }
    return item;
  }

  function buildFlag(text) {
    const flag = document.createElement("span");
    flag.className = "symbol-flag";
    flag.textContent = text;
    return flag;
  }

  // un nodo del árbol de scopes (Scope.kind/name/symbols/children ya serializados
  // por ide/app.py): sus símbolos propios como lista, y sus hijos anidados debajo.
  function buildScopeNode(scope) {
    const node = document.createElement("div");
    node.className = "scope-node";

    const header = document.createElement("div");
    header.className = "scope-header";
    const kind = document.createElement("span");
    kind.className = "scope-kind";
    kind.textContent = scope.kind;
    const name = document.createElement("span");
    name.textContent = scope.name;
    header.append(kind, name);
    node.appendChild(header);

    if (scope.symbols.length) {
      const list = document.createElement("ul");
      list.className = "symbol-list";
      for (const symbol of scope.symbols) list.appendChild(buildSymbolItem(symbol));
      node.appendChild(list);
    }
    for (const child of scope.children) node.appendChild(buildScopeNode(child));
    return node;
  }

  function renderSymbols(symbolTable) {
    if (!symbolTable) {
      symbolsEl.replaceChildren(Object.assign(document.createElement("p"), {
        className: "hint",
        textContent: "No hay tabla de símbolos disponible para esta solicitud.",
      }));
      return;
    }
    symbolsEl.replaceChildren(buildScopeNode(symbolTable));
  }

  function renderResult(data) {
    if (data.error) {
      currentDiagnostics = [];
      renderDiagnostics();
      copyBtnEl.disabled = true;
      setStatus(data.error, "fail");
      setAstEmpty("No hay AST disponible para esta solicitud.");
      renderSymbols(null);
      return;
    }
    currentDiagnostics = Array.isArray(data.diagnostics) ? data.diagnostics : [];
    selectedDiagnosticKey = null;
    const errors = currentDiagnostics.filter((diag) => diag.severity === "error").length;
    const warnings = currentDiagnostics.filter((diag) => diag.severity === "warning").length;
    const summary = data.success
      ? "Compilación exitosa | sin errores"
      : `Compilación fallida | ${formatCount(errors, "error", "errores")} | ${formatCount(warnings, "advertencia", "advertencias")}`;
    setStatus(summary, data.success ? "ok" : "fail");
    copyBtnEl.disabled = currentDiagnostics.length === 0;
    setCopyStatus("", "");
    renderDiagnostics();
    renderAstResult(data);
    renderSymbols(data.symbols);
  }

  function diagnosticsText() {
    return currentDiagnostics
      .map((diag) => [diag.code, `${diag.line}:${diag.column}`, "—", diag.message].join(" "))
      .join("\n");
  }

  async function copyDiagnostics() {
    if (currentDiagnostics.length === 0) return;
    try {
      await navigator.clipboard.writeText(diagnosticsText());
      setCopyStatus("Diagnósticos copiados.", "ok");
    } catch (_error) {
      setCopyStatus("El navegador no permitió copiar los diagnósticos.", "fail");
    }
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
      loadedSource = sourceEl.value;
      loadedFileName = file.name;
      manuallyEdited = false;
      refreshFileName();
      setFileStatus("Archivo cargado. Podés editarlo antes de compilar.", "ok");
      scheduleEditorRender();
      clearResult();
    };
    reader.onerror = function () {
      setFileStatus("No se pudo leer el archivo seleccionado.", "fail");
    };
    reader.readAsText(file, "UTF-8");
  }

  async function compile() {
    if (compiling) return;
    compiling = true;
    btnEl.disabled = true;
    btnEl.textContent = "Compilando…";
    btnEl.setAttribute("aria-busy", "true");
    setStatus("Compilando…", "");
    try {
      const response = await fetch("/api/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: sourceEl.value }),
      });
      const data = await response.json();
      if (!data || typeof data !== "object" || !Array.isArray(data.diagnostics)) {
        throw new Error("respuesta inesperada del servidor");
      }
      renderResult(data);
    } catch (_error) {
      setStatus("No se pudo compilar: respuesta inválida o error de red.", "fail");
      setAstEmpty("No hay AST disponible mientras no haya una respuesta válida.");
      renderSymbols(null);
    } finally {
      compiling = false;
      btnEl.disabled = false;
      btnEl.textContent = "Compilar";
      btnEl.setAttribute("aria-busy", "false");
    }
  }

  sourceEl.addEventListener("input", () => {
    if (loadedSource === null) manuallyEdited = true;
    refreshFileName();
    scheduleEditorRender();
  });
  sourceEl.addEventListener("scroll", syncEditorScroll);
  sourceEl.addEventListener("keydown", (event) => {
    if (event.key === "Tab") {
      event.preventDefault();
      // El textarea es la fuente de verdad: insertar espacios conserva el
      // comportamiento de un editor sin dejar que el navegador cambie el foco.
      const start = sourceEl.selectionStart;
      const end = sourceEl.selectionEnd;
      sourceEl.setRangeText("    ", start, end, "end");
      sourceEl.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      compile();
    }
  });
  btnEl.addEventListener("click", compile);
  fileEl.addEventListener("change", loadSelectedFile);
  filterEl.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-filter]");
    if (!button) return;
    activeFilter = button.dataset.filter;
    updateFilterButtons();
    renderDiagnostics();
  });
  copyBtnEl.addEventListener("click", copyDiagnostics);
  viewTabsEl.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-view]");
    if (!button) return;
    setActiveView(button.dataset.view);
  });
  astZoomInEl.addEventListener("click", () => changeAstScale(0.1));
  astZoomOutEl.addEventListener("click", () => changeAstScale(-0.1));
  astResetEl.addEventListener("click", () => { astScale = 1; applyAstScale(); });
  astFitEl.addEventListener("click", fitAst);
  astDownloadEl.addEventListener("click", () => {
    if (!currentAstSvg) return;
    const blob = new Blob([currentAstSvg], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "compiscript-ast.svg";
    link.click();
    URL.revokeObjectURL(url);
  });

  renderEditor();
  refreshFileName();
  setActiveView("ast");
  clearResult();
})();
