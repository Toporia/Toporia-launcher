const $ = (id) => document.getElementById(id);
const clone = (value) => JSON.parse(JSON.stringify(value));
const PARTS = "__parts__";
const ACTIVE_JOB_KEY = "toporia.activeJobId";
const SENSITIVITY_PATHS = [
  { label: "Sensitivity · Base value", path: "sens.base_value" },
  { label: "Sensitivity · Gap", path: "sens.gap" }
];

const MODE_DEFAULTS = {
  run_one: {},
  check_parts: {},
  sweep: { parameter: "volfrac", min_val: 0.08, max_val: 0.6, n_rows: 3, n_cols: 3 },
  sweep_2d: {
    row_param: "volfrac", row_min: 0.1, row_max: 0.4, n_rows: 2,
    col_param: "m", col_min: 0.4, col_max: 0.75, n_cols: 2
  },
  compare_two: { param_key: "volfrac", value_a: 0.2, value_b: 0.4 },
  compare_load_cases: {
    load_cases_a: [
      { Fmag: 1, Fa: 0, weight: 0.5, Fe: 0 },
      { Fmag: 1, Fa: 270, weight: 0.5, Fe: 0 }
    ],
    load_cases_b: [
      { Fmag: 1, Fa: 0, weight: 0.5, Fe: 0 },
      { Fmag: 1, Fa: 270, weight: 0.5, Fe: 0 }
    ]
  },
  compare_methods: { methods: ["q4+oc", "q4+mma", "q4+simpl", "q4+beso"] },
  sensitivity: { param_key: "volfrac", base_value: 0.3, gap: 0.05 },
  sensitivity_sweep: {
    sweep_param: "volfrac", min_val: 0.15, max_val: 0.45, n_rows: 2, n_cols: 3,
    sens_param: "volfrac", base_value: 0.3, gap: 0.05
  },
  sensitivity_sweep_2d: {
    row_param: "volfrac", row_min: 0.15, row_max: 0.45, n_rows: 2,
    col_param: "m", col_min: 0.02, col_max: 0.1, n_cols: 2,
    sens_param: "volfrac", base_value: 0.3, gap: 0.05
  }
};

const MODE_HINTS = {
  run_one: "Run one optimisation to convergence.",
  check_parts: "Check the selected pipeline's interfaces, gradients and benchmarks.",
  sweep: "Run a grid while varying one numeric parameter.",
  sweep_2d: "Run a grid while varying two numeric parameters.",
  compare_two: "Compare two runs that differ in one parameter.",
  compare_load_cases: "Compare two independent load-case sets.",
  compare_methods: "Run selected methods on the same problem.",
  sensitivity: "Measure how the final design responds to a parameter change.",
  sensitivity_sweep: "Compare sensitivity fields across a one-parameter sweep.",
  sensitivity_sweep_2d: "Compare sensitivity fields across a two-parameter sweep."
};

let metadata;
let presets = [];
let methods = [];
let models = [];
let updaters = [];
let activeJob = null;
let logOffset = 0;
let pollTimer = null;
let describeTimer = null;
let currentMethodName = "";
let state = { scenario: {}, solver: {}, output: {} };
let methodValues = {};
let modeValues = {};
let parameterItems = [];
let schedulableItems = [];

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok) {
    const error = new Error(data.error || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  if (!contentType.includes("application/json")) throw new Error("The server returned a non-JSON response.");
  return data;
}

function rememberJob(id) {
  try {
    localStorage.setItem(ACTIVE_JOB_KEY, id);
  } catch (error) {
    $("notice").textContent = `Job started, but refresh recovery is unavailable: ${error.message}`;
  }
}

function forgetJob() {
  try {
    localStorage.removeItem(ACTIVE_JOB_KEY);
  } catch (error) {
    $("notice").textContent = `Could not clear the saved job reference: ${error.message}`;
  }
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function selectedPreset() {
  return presets.find((preset) => preset.name === $("preset").value);
}

function option(select, value, label, disabled = false) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = label;
  item.disabled = disabled;
  select.append(item);
  return item;
}

function fillOptions(select, values, current) {
  select.replaceChildren();
  for (const entry of values) option(select, entry.value, entry.label, entry.disabled);
  if (values.some((entry) => entry.value === String(current))) select.value = String(current);
  else if (values.length) select.value = values[0].value;
}

function renderParamFields(container, params, values = {}, prefix = "param") {
  container.replaceChildren();
  for (const param of params || []) {
    const wrapper = document.createElement("div");
    wrapper.className = "field";
    const inputId = `${prefix}-${param.name}`;
    const label = document.createElement("label");
    label.htmlFor = inputId;
    label.textContent = param.units ? `${param.label} (${param.units})` : param.label;
    if (param.help) label.title = param.help;

    let input;
    const value = Object.hasOwn(values, param.name) ? values[param.name] : param.default;
    if (param.kind === "choice") {
      input = document.createElement("select");
      for (const [choice, text] of param.choices) {
        option(input, JSON.stringify(choice), text);
      }
      input.value = JSON.stringify(value);
    } else {
      input = document.createElement("input");
      input.type = param.kind === "bool" ? "checkbox" : "number";
      if (param.kind === "bool") input.checked = Boolean(value);
      else {
        input.value = value;
        if (param.kind === "int") input.step = "1";
        else if (param.step !== null) input.step = param.step;
        if (param.min !== null) input.min = param.min;
        if (param.max !== null) input.max = param.max;
      }
    }
    input.id = inputId;
    input.dataset.paramName = param.name;
    input.dataset.paramKind = param.kind;
    if (param.help) input.title = param.help;
    wrapper.append(label, input);
    container.append(wrapper);
  }
}

function readParamFields(container) {
  const values = {};
  for (const input of container.querySelectorAll("[data-param-name]")) {
    if (input.dataset.paramKind === "bool") values[input.dataset.paramName] = input.checked;
    else if (input.dataset.paramKind === "choice") values[input.dataset.paramName] = JSON.parse(input.value);
    else values[input.dataset.paramName] = Number(input.value);
  }
  return values;
}

function defaultSpec(plugin) {
  return {
    type: plugin.name,
    ...Object.fromEntries((plugin.params || []).map((param) => [param.name, param.default]))
  };
}

function renderSpecFields(container, plugins, spec, onTypeChange, prefix) {
  container.replaceChildren();
  const row = document.createElement("div");
  row.className = "spec-editor";
  const typeLabel = document.createElement("label");
  typeLabel.textContent = "Type";
  const select = document.createElement("select");
  select.className = "spec-type";
  for (const plugin of plugins) {
    const missing = plugin.missing_dependencies.length > 0;
    option(select, plugin.name, missing ? `${plugin.label} (needs ${plugin.missing_dependencies.join(", ")})`
      : plugin.label, missing);
  }
  const selected = plugins.find((plugin) => plugin.name === spec?.type) || plugins[0];
  if (!selected) {
    const warning = document.createElement("p");
    warning.className = "hint";
    warning.textContent = "No plugins are available for this section.";
    container.append(warning);
    return;
  }
  select.value = selected.name;
  select.addEventListener("change", () => {
    const next = defaultSpec(plugins.find((plugin) => plugin.name === select.value));
    renderSpecFields(container, plugins, next, onTypeChange, prefix);
    onTypeChange(next);
  });
  row.append(typeLabel, select);
  container.append(row);
  const values = { ...(spec || {}) };
  delete values.type;
  const fields = document.createElement("div");
  fields.className = "field-grid spec-parameters";
  renderParamFields(fields, selected.params, values, prefix);
  container.append(fields);
}

function readSpecFields(container) {
  const type = container.querySelector(".spec-type")?.value;
  return type ? { type, ...readParamFields(container) } : null;
}

function renderSpecList(container, plugins, specs, onUpdate, prefix, paths = null) {
  container.replaceChildren();
  const replaceList = (next) => {
    renderSpecList(container, plugins, next, onUpdate, prefix, paths);
    onUpdate(next);
  };
  (specs || []).forEach((spec, index) => {
    const row = document.createElement("div");
    row.className = "spec-list-row";
    const editor = document.createElement("div");
    renderSpecFields(editor, plugins, spec, (newSpec) => {
      const current = readSpecList(container, paths);
      current[index] = newSpec;
      replaceList(current);
    }, `${prefix}-${index}`);
    row.append(editor);
    if (paths) {
      const pathLabel = document.createElement("label");
      pathLabel.textContent = "Parameter to schedule";
      const pathSelect = document.createElement("select");
      pathSelect.className = "schedule-path";
      const wanted = spec.path;
      const available = [...paths];
      if (wanted && !available.some((entry) => entry.path === wanted)) {
        available.push({ label: `${wanted} (not changeable with this setup)`, path: wanted });
      }
      fillOptions(pathSelect, available.map((entry) => ({ value: entry.path, label: entry.label })), wanted);
      pathLabel.append(pathSelect);
      row.prepend(pathLabel);
    }
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-row";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      const current = readSpecList(container, paths);
      current.splice(index, 1);
      replaceList(current);
    });
    row.append(remove);
    container.append(row);
  });
  const add = document.createElement("button");
  add.type = "button";
  add.className = "add-row";
  add.textContent = "+ Add";
  add.disabled = !plugins.length || (paths && !paths.length);
  add.addEventListener("click", () => {
    const current = readSpecList(container, paths);
    const spec = defaultSpec(plugins[0]);
    if (paths) spec.path = paths[0].path;
    current.push(spec);
    replaceList(current);
  });
  container.append(add);
}

function readSpecList(container, withPaths = null) {
  return [...container.querySelectorAll(".spec-list-row")].map((row) => {
    const spec = readSpecFields(row);
    if (withPaths) spec.path = row.querySelector(".schedule-path")?.value || "";
    return spec;
  }).filter(Boolean);
}

function renderLoadCases(container, cases, onUpdate, prefix = "load-case") {
  container.replaceChildren();
  (cases || []).forEach((loadCase, index) => {
    const row = document.createElement("div");
    row.className = "load-case-row";
    const title = document.createElement("strong");
    title.textContent = `LC ${index + 1}`;
    row.append(title);
    for (const [key, label, min, max, step] of [
      ["Fmag", "Fmag", 0, 1000000, 0.1],
      ["Fa", "Angle°", -360, 360, 15],
      ["weight", "Weight", 0, 1, 0.1],
      ["Fe", "Elev°", -90, 90, 15]
    ]) {
      const field = document.createElement("div");
      field.className = "load-case-field";
      const fieldLabel = document.createElement("label");
      const input = document.createElement("input");
      input.type = "number";
      input.min = min;
      input.max = max;
      input.step = step;
      input.value = loadCase[key] ?? 0;
      input.dataset.loadCaseKey = key;
      input.id = `${prefix}-${index}-${key}`;
      fieldLabel.htmlFor = input.id;
      fieldLabel.textContent = label;
      field.append(fieldLabel, input);
      row.append(field);
    }
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-row";
    remove.textContent = "×";
    remove.title = "Remove load case";
    remove.disabled = cases.length < 2;
    remove.addEventListener("click", () => {
      const current = readLoadCases(container);
      current.splice(index, 1);
      onUpdate(current);
    });
    row.append(remove);
    container.append(row);
  });
  const add = document.createElement("button");
  add.type = "button";
  add.className = "add-row";
  add.textContent = "+ Add load case";
  add.addEventListener("click", () => {
    const current = readLoadCases(container);
    current.push({ Fmag: 1, Fa: 0, weight: 1, Fe: 0 });
    onUpdate(current);
  });
  container.append(add);
}

function readLoadCases(container) {
  return [...container.querySelectorAll(".load-case-row")].map((row) => {
    const values = {};
    for (const input of row.querySelectorAll("[data-load-case-key]")) {
      values[input.dataset.loadCaseKey] = Number(input.value);
    }
    return values;
  });
}

function methodFor(name) {
  return methods.find((entry) => entry.name === name);
}

function computeMethodName() {
  if ($("approach").value !== PARTS) return $("approach").value;
  return `${$("model").value}+${$("updater").value}`;
}

function methodParams() {
  if ($("approach").value === PARTS) {
    return { ...readParamFields($("model-parameters")), ...readParamFields($("updater-parameters")) };
  }
  return readParamFields($("whole-method-parameters"));
}

function rememberMethodParams() {
  if (currentMethodName) methodValues[currentMethodName] = methodParams();
}

function configureMethodSelectors(config) {
  const method = methodFor(config.solver.method);
  if (method?.composed) {
    $("approach").value = PARTS;
    $("model").value = method.model;
    $("updater").value = method.updater;
  } else {
    $("approach").value = config.solver.method;
  }
  currentMethodName = config.solver.method;
  methodValues[currentMethodName] = { ...(config.solver.method_params || {}) };
  const previous = currentMethodName;
  renderMethodForms();
  currentMethodName = previous;
}

function renderMethodForms() {
  const composed = $("approach").value === PARTS;
  $("parts-selector").hidden = !composed;
  $("whole-method-selector").hidden = composed;
  const name = computeMethodName();
  const method = methodFor(name);
  if (composed) {
    const model = models.find((entry) => entry.name === $("model").value);
    const updater = updaters.find((entry) => entry.name === $("updater").value);
    const values = methodValues[name] || {};
    renderParamFields($("model-parameters"), model?.params || [], values, "model");
    renderParamFields($("updater-parameters"), updater?.params || [], values, "updater");
  } else {
    renderParamFields($("whole-method-parameters"), method?.params || [], methodValues[name] || {}, "whole-method");
  }
  $("method-note").textContent = method?.missing_dependencies.length
    ? `Requires ${method.missing_dependencies.join(", ")}. Install that optional dependency before running.`
    : method ? "" : "This model/updater pairing has incompatible parameters.";
  updateCapabilitySections(method);
}

function updateCapabilitySections(method) {
  const caps = method?.capabilities || {};
  $("filters-section").hidden = !caps.accepts_filters;
  $("representation-editor").hidden = !caps.accepts_representation;
  $("material-section").hidden = !caps.accepts_interpolation;
  $("variants-section").hidden = !method?.composed;
  const allowedObjectives = new Set(caps.objectives || []);
  const allowedConstraints = new Set(caps.constraints || []);
  const objectivePlugins = metadata.objectives.filter((plugin) => allowedObjectives.has(plugin.name));
  const constraintPlugins = metadata.constraints.filter((plugin) => allowedConstraints.has(plugin.name));
  renderSpecFields($("objective-editor"), objectivePlugins, state.scenario.objective || {},
    (spec) => { state.scenario.objective = spec; updateFromControls(); },
    "objective");
  renderSpecList($("constraints-editor"), constraintPlugins, state.scenario.constraints || [],
    (specs) => { state.scenario.constraints = specs; updateFromControls(); }, "constraint");
  const canConstrain = Boolean(constraintPlugins.length && caps.max_constraints !== 0);
  $("constraints-editor").hidden = false;
  $("constraints-editor").classList.toggle("unavailable", !canConstrain);
  if (!canConstrain) {
    renderSpecList($("constraints-editor"), metadata.constraints, state.scenario.constraints || [],
      (specs) => { state.scenario.constraints = specs; updateFromControls(); }, "constraint");
    $("constraints-editor").classList.add("unavailable");
    $("constraints-editor").querySelectorAll("input, select, button").forEach((input) => { input.disabled = true; });
  } else $("constraints-editor").classList.remove("unavailable");
  $("constraint-note").textContent = canConstrain ? "" : method
    ? `${method.label} enforces only the volume budget.` : "";
  const scheduleAllowed = schedulableItems.length > 0;
  $("schedules-section").hidden = !scheduleAllowed;
  renderSpecList($("filters-editor"), metadata.filters, state.solver.filter_specs || [],
    (specs) => { state.solver.filter_specs = specs; updateFromControls(); }, "filter");
  renderSpecList($("schedules-editor"), metadata.schedules, state.solver.schedules || [],
    (specs) => { state.solver.schedules = specs; updateFromControls(); }, "schedule", schedulableItems);
  renderVariants();
}

function readVariantSpec() {
  if (!$("variants-enabled").checked || $("variants-section").hidden) return {};
  const raw = $("variant-values").value;
  const values = raw.split(/[;,]/).map((text) => text.trim()).filter(Boolean).map(Number);
  if (values.length < 2 || values.some((value) => !Number.isFinite(value))) {
    throw new Error("Variants need at least two finite values.");
  }
  if (Number($("variant-nominal").value) >= values.length) {
    throw new Error("The shown variant index must refer to one of the listed values.");
  }
  return {
    path: $("variant-path").value,
    values,
    combine: $("variant-combine").value,
    nominal: Number($("variant-nominal").value),
    sharpness: Number($("variant-sharpness").value)
  };
}

function renderVariants() {
  const container = $("variants-editor");
  container.replaceChildren();
  const spec = state.solver.variants || {};
  const enabled = document.createElement("label");
  enabled.className = "check-field";
  const toggle = document.createElement("input");
  toggle.type = "checkbox";
  toggle.id = "variants-enabled";
  toggle.checked = Boolean(Object.keys(spec).length);
  enabled.append(toggle, document.createTextNode(" Evaluate several versions of each design"));
  container.append(enabled);
  const fields = document.createElement("div");
  fields.className = "field-grid";
  const pathOptions = parameterItems.filter((item) => item.path !== "m");
  const pathLabel = document.createElement("label");
  pathLabel.textContent = "Parameter";
  const path = document.createElement("select");
  path.id = "variant-path";
  const paths = pathOptions.map((item) => ({ value: item.path, label: item.label }));
  if (spec.path && !paths.some((item) => item.value === spec.path)) paths.push({ value: spec.path, label: spec.path });
  fillOptions(path, paths, spec.path);
  pathLabel.append(path);

  const valuesLabel = document.createElement("label");
  valuesLabel.textContent = "Values (comma separated)";
  const values = document.createElement("input");
  values.type = "text";
  values.id = "variant-values";
  values.value = (spec.values || [0.75, 0.5, 0.25]).join(", ");
  valuesLabel.append(values);

  const combineLabel = document.createElement("label");
  combineLabel.textContent = "Combine";
  const combine = document.createElement("select");
  combine.id = "variant-combine";
  option(combine, "worst", "Worst case");
  option(combine, "mean", "Mean");
  combine.value = spec.combine || "worst";
  combineLabel.append(combine);

  for (const [id, labelText, defaultValue, min, max, step] of [
    ["variant-nominal", "Shown version (0-based)", 1, 0, 20, 1],
    ["variant-sharpness", "Worst-case sharpness", 50, 1, 1000, 10]
  ]) {
    const label = document.createElement("label");
    label.textContent = labelText;
    const input = document.createElement("input");
    input.id = id;
    input.type = "number";
    input.min = min;
    input.max = max;
    input.step = step;
    input.value = spec[id === "variant-nominal" ? "nominal" : "sharpness"] ?? defaultValue;
    label.append(input);
    fields.append(label);
  }
  fields.prepend(pathLabel, valuesLabel, combineLabel);
  const robust = document.createElement("button");
  robust.type = "button";
  robust.className = "secondary robust-button";
  robust.textContent = "Robust projection: eroded / intermediate / dilated";
  robust.addEventListener("click", () => {
    let specs = readSpecList($("filters-editor"));
    let index = specs.findIndex((entry) => entry.type === "heaviside");
    if (index < 0) {
      const plugin = metadata.filters.find((entry) => entry.name === "heaviside");
      if (!plugin) return;
      specs.push(defaultSpec(plugin));
      index = specs.length - 1;
      state.solver.filter_specs = specs;
      renderSpecList($("filters-editor"), metadata.filters, specs,
        (next) => { state.solver.filter_specs = next; updateFromControls(); }, "filter");
    }
    $("variant-path").value = `filters[${index}].eta`;
    $("variant-values").value = "0.75, 0.5, 0.25";
    $("variant-combine").value = "worst";
    $("variant-nominal").value = "1";
    $("variant-sharpness").value = "50";
    $("variants-enabled").checked = true;
    updateFromControls();
  });
  container.append(fields, robust);
  const setFieldsEnabled = (enabled) => {
    fields.querySelectorAll("input, select").forEach((input) => { input.disabled = !enabled; });
  };
  setFieldsEnabled(toggle.checked);
  toggle.addEventListener("change", () => { setFieldsEnabled(toggle.checked); updateFromControls(); });
}

function captureState() {
  const method = methodFor(currentMethodName);
  if (!validateInputs()) throw new Error("Please correct the highlighted fields before continuing.");
  state.scenario.volfrac = readParamFields($("core-fields")).volfrac;
  state.scenario.Lz = Number($("dimensions").value) === 3 ? Number($("depth").value) : 0;
  state.scenario.load_cases = readLoadCases($("load-cases-editor"));
  state.scenario.objective = readSpecFields($("objective-editor")) || state.scenario.objective;
  const methodCanUseConstraints = Boolean(method?.capabilities.constraints?.length
    && method.capabilities.max_constraints !== 0);
  if (methodCanUseConstraints) state.scenario.constraints = readSpecList($("constraints-editor"));

  state.solver.method = currentMethodName;
  state.solver.method_params = methodParams();
  state.solver.m = $("resolution-mode").value === "size"
    ? 1 / Number($("resolution").value) : Number($("resolution").value);
  Object.assign(state.solver, readParamFields($("convergence-fields")));
  if (method?.capabilities.accepts_filters) state.solver.filter_specs = readSpecList($("filters-editor"));
  state.solver.interpolation = readSpecFields($("material-editor")) || state.solver.interpolation;
  state.solver.representation = readSpecFields($("representation-editor")) || state.solver.representation;
  if (!$("schedules-section").hidden) state.solver.schedules = readSpecList($("schedules-editor"), schedulableItems);
  if (method?.composed) state.solver.variants = readVariantSpec();
  Object.assign(state.output, readParamFields($("output-fields")));
  state.output.postprocess = readSpecList($("postprocess-editor"));
  return state;
}

function validateInputs() {
  for (const input of document.querySelectorAll("input[type=number]:not(:disabled)")) {
    if (input.closest("[hidden]")) continue;
    const validity = input.validity;
    if (input.value.trim() === "" || validity.badInput || validity.rangeUnderflow || validity.rangeOverflow) {
      input.focus();
      return false;
    }
  }
  return true;
}

function runPayload() {
  captureState();
  const solver = clone(state.solver);
  const scenario = clone(state.scenario);
  const method = methodFor(solver.method);
  if (!method?.capabilities.accepts_filters) solver.filter_specs = [];
  if (!method?.capabilities.constraints?.length || method.capabilities.max_constraints === 0) scenario.constraints = [];
  if (!method?.composed) solver.variants = {};
  return {
    preset: selectedPreset().name,
    scenario,
    solver,
    output: clone(state.output)
  };
}

function updateAdvancedJson() {
  $("scenario-json").value = pretty(state.scenario);
  $("solver-json").value = pretty(state.solver);
  $("output-json").value = pretty(state.output);
}

function refreshCounts() {
  const filters = state.solver.filter_specs || [];
  const constraints = state.scenario.constraints || [];
  const schedules = state.solver.schedules || [];
  const postprocess = state.output.postprocess || [];
  $("filters-title").textContent = `Filters (${filters.length} active)`;
  $("constraints-title").textContent = `Constraints (${constraints.length ? `${constraints.length} active` : "none active"})`;
  $("schedules-title").textContent = `Schedules (${schedules.length ? `${schedules.length} active` : "none active"})`;
  $("postprocess-title").textContent = `Post-processing (${postprocess.length ? `${postprocess.length} active` : "none active"})`;
  $("variants-title").textContent = `Variants (${Object.keys(state.solver.variants || {}).length ? "on" : "robust design"})`;
  $("load-cases-title").textContent = `Load Cases (${(state.scenario.load_cases || []).length})`;
  $("depth-field").hidden = Number($("dimensions").value) !== 3;
  for (const input of $("load-cases-editor").querySelectorAll('[data-load-case-key="Fe"]')) {
    input.closest(".load-case-field").hidden = Number($("dimensions").value) !== 3;
  }
  const preset = selectedPreset();
  const m = $("resolution-mode").value === "size"
    ? 1 / Number($("resolution").value) : Number($("resolution").value);
  if (preset && Number.isFinite(m) && m > 0) {
    const sx = Math.round(preset.scenario.Lx * m);
    const sy = Math.max(1, Math.round(preset.scenario.Ly * m));
    if (Number($("dimensions").value) === 3) {
      const sz = Math.max(1, Math.round(Number($("depth").value) * m));
      $("mesh-counts").textContent = `${sx} × ${sy} × ${sz} = ${(sx * sy * sz).toLocaleString()} elements`;
    } else {
      $("mesh-counts").textContent = `${sx} × ${sy} = ${(sx * sy).toLocaleString()} elements`;
    }
  }
}

function updateFromControls(describe = true) {
  try {
    captureState();
    refreshCounts();
    updateAdvancedJson();
    if (describe) queueDescription();
  } catch (error) {
    $("notice").textContent = error.message;
  }
}

function queueDescription() {
  clearTimeout(describeTimer);
  describeTimer = setTimeout(async () => {
    try {
      const description = await requestJson("/api/describe", {
        method: "POST",
        body: JSON.stringify(runPayload())
      });
      const parametersChanged = JSON.stringify(parameterItems) !== JSON.stringify(description.parameters);
      const schedulesChanged = JSON.stringify(schedulableItems) !== JSON.stringify(description.schedulable);
      parameterItems = description.parameters;
      schedulableItems = description.schedulable;
      $("schedules-section").hidden = !schedulableItems.length;
      if (schedulesChanged) {
        renderSpecList($("schedules-editor"), metadata.schedules, state.solver.schedules || [],
          (specs) => { state.solver.schedules = specs; updateFromControls(); }, "schedule", schedulableItems);
      }
      if (parametersChanged) {
        renderModeEditor();
        renderVariants();
      }
      $("pipeline-stages").replaceChildren(...description.stages.map(([stage, text]) => {
        const row = document.createElement("li");
        const heading = document.createElement("strong");
        heading.textContent = stage;
        row.append(heading, document.createTextNode(`: ${text}`));
        return row;
      }));
      $("pipeline-notes").replaceChildren(...description.notes.map((note) => {
        const row = document.createElement("li");
        row.textContent = note;
        return row;
      }));
    } catch (error) {
      $("pipeline-stages").replaceChildren();
      const note = document.createElement("li");
      note.textContent = `Cannot describe this selection: ${error.message}`;
      $("pipeline-notes").replaceChildren(note);
    }
  }, 300);
}

function updateMethodSelection(remember = true) {
  if (remember) rememberMethodParams();
  const method = methodFor(computeMethodName());
  if (method) {
    currentMethodName = method.name;
    if (!methodValues[currentMethodName]) methodValues[currentMethodName] = {};
  } else {
    currentMethodName = computeMethodName();
  }
  renderMethodForms();
  updateFromControls();
}

function fillLoadCaseSection(cases) {
  renderLoadCases($("load-cases-editor"), cases, (next) => {
    state.scenario.load_cases = next;
    fillLoadCaseSection(next);
    updateFromControls();
  });
}

function renderModeEditor() {
  const mode = $("mode").value;
  const container = $("mode-fields");
  if (!container) return;
  container.replaceChildren();
  $("mode-note").textContent = MODE_HINTS[mode] || "";
  const values = modeValues[mode] || clone(MODE_DEFAULTS[mode] || {});
  const paths = [...parameterItems];
  const pathOptions = (includeSensitivity = false) => [
    ...paths.map((item) => ({ value: item.path, label: item.label })),
    ...(includeSensitivity ? SENSITIVITY_PATHS.map((item) => ({ value: item.path, label: item.label })) : [])
  ];
  const selectField = (key, labelText, options, includeSensitivity = false) => {
    const label = document.createElement("label");
    label.textContent = labelText;
    const select = document.createElement("select");
    select.dataset.modeKey = key;
    fillOptions(select, options || pathOptions(includeSensitivity), values[key]);
    label.append(select);
    container.append(label);
  };
  const numberField = (key, labelText, min, max, step, defaultValue) => {
    const label = document.createElement("label");
    label.textContent = labelText;
    const input = document.createElement("input");
    input.type = "number";
    input.dataset.modeKey = key;
    input.min = min;
    input.max = max;
    input.step = step;
    input.value = values[key] ?? defaultValue;
    label.append(input);
    container.append(label);
  };
  const addGridCount = (key, label) => numberField(key, label, 1, 20, 1, values[key] || 2);
  const drawCaseSet = (key, title) => {
    const heading = document.createElement("h4");
    heading.textContent = title;
    container.append(heading);
    const caseContainer = document.createElement("div");
    caseContainer.className = "mode-load-cases";
    renderLoadCases(caseContainer, values[key] || [], (next) => {
      values[key] = next;
      modeValues[mode] = values;
      renderModeEditor();
    }, `mode-${key}`);
    caseContainer.dataset.modeCases = key;
    container.append(caseContainer);
  };
  if (mode === "sweep") {
    selectField("parameter", "Parameter");
    numberField("min_val", "Minimum", -1e6, 1e6, 0.05, 0.08);
    numberField("max_val", "Maximum", -1e6, 1e6, 0.05, 0.6);
    addGridCount("n_rows", "Rows");
    addGridCount("n_cols", "Columns");
  } else if (mode === "sweep_2d") {
    selectField("row_param", "Row parameter");
    numberField("row_min", "Row minimum", -1e6, 1e6, 0.05, 0.1);
    numberField("row_max", "Row maximum", -1e6, 1e6, 0.05, 0.4);
    addGridCount("n_rows", "Rows");
    selectField("col_param", "Column parameter");
    numberField("col_min", "Column minimum", -1e6, 1e6, 0.05, 0.4);
    numberField("col_max", "Column maximum", -1e6, 1e6, 0.05, 0.75);
    addGridCount("n_cols", "Columns");
  } else if (mode === "compare_two") {
    selectField("param_key", "Parameter");
    numberField("value_a", "Value A", -1e6, 1e6, 0.05, 0.2);
    numberField("value_b", "Value B", -1e6, 1e6, 0.05, 0.4);
  } else if (mode === "compare_load_cases") {
    drawCaseSet("load_cases_a", "Design A load cases");
    drawCaseSet("load_cases_b", "Design B load cases");
  } else if (mode === "compare_methods") {
    const chosen = new Set(values.methods || []);
    for (const method of methods) {
      const label = document.createElement("label");
      label.className = "check-field method-check";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = method.name;
      input.dataset.methodCheck = "true";
      input.checked = chosen.has(method.name) && method.missing_dependencies.length === 0;
      input.disabled = method.missing_dependencies.length > 0;
      label.append(input, document.createTextNode(`${method.label}${input.disabled
        ? ` (needs ${method.missing_dependencies.join(", ")})` : ""}`));
      container.append(label);
    }
  } else if (mode === "sensitivity") {
    selectField("param_key", "Parameter");
    numberField("base_value", "Base value", -1e6, 1e6, 0.05, 0.3);
    numberField("gap", "Gap (Δ)", 0.000001, 1e6, 0.01, 0.05);
  } else if (mode === "sensitivity_sweep") {
    selectField("sens_param", "Sensitivity parameter");
    numberField("base_value", "Base value", -1e6, 1e6, 0.05, 0.3);
    numberField("gap", "Gap (Δ)", 0.000001, 1e6, 0.01, 0.05);
    selectField("sweep_param", "Sweep parameter", pathOptions(true), true);
    numberField("min_val", "Minimum", -1e6, 1e6, 0.05, 0.15);
    numberField("max_val", "Maximum", -1e6, 1e6, 0.05, 0.45);
    addGridCount("n_rows", "Rows");
    addGridCount("n_cols", "Columns");
  } else if (mode === "sensitivity_sweep_2d") {
    selectField("sens_param", "Sensitivity parameter");
    numberField("base_value", "Base value", -1e6, 1e6, 0.05, 0.3);
    numberField("gap", "Gap (Δ)", 0.000001, 1e6, 0.01, 0.05);
    selectField("row_param", "Row parameter", pathOptions(true), true);
    numberField("row_min", "Row minimum", -1e6, 1e6, 0.05, 0.15);
    numberField("row_max", "Row maximum", -1e6, 1e6, 0.05, 0.45);
    addGridCount("n_rows", "Rows");
    selectField("col_param", "Column parameter", pathOptions(true), true);
    numberField("col_min", "Column minimum", -1e6, 1e6, 0.01, 0.02);
    numberField("col_max", "Column maximum", -1e6, 1e6, 0.01, 0.1);
    addGridCount("n_cols", "Columns");
  } else {
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = mode === "check_parts" ? "No additional settings." : "No additional options.";
    container.append(note);
  }
  container.dataset.mode = mode;
}

function readModeOptions(modeOverride = null) {
  const mode = modeOverride || $("mode").value;
  const values = {};
  const container = $("mode-fields");
  for (const input of container.querySelectorAll("[data-mode-key]")) {
    const key = input.dataset.modeKey;
    values[key] = input.type === "number" ? Number(input.value) : input.value;
  }
  for (const cases of container.querySelectorAll("[data-mode-cases]")) {
    values[cases.dataset.modeCases] = readLoadCases(cases);
  }
  if (mode === "compare_methods") {
    values.methods = [...container.querySelectorAll("[data-method-check]:checked")].map((input) => input.value);
  }
  modeValues[mode] = values;
  return values;
}

function modePayload() {
  const values = readModeOptions();
  const mode = $("mode").value;
  if (mode === "run_one" || mode === "check_parts") return {};
  return values;
}

function loadConfiguration(config) {
  state = { scenario: clone(config.scenario), solver: clone(config.solver), output: clone(config.output) };
  const selectedMethod = methodFor(state.solver.method);
  if (!selectedMethod) throw new Error(`Unknown method ${state.solver.method}`);
  state.solver.method = selectedMethod.name;
  $("dimensions").value = Number(state.scenario.Lz || 0) > 0 ? "3" : "2";
  $("depth").value = Number(state.scenario.Lz || Math.max(state.scenario.Ly / 4, 1));
  $("resolution-mode").value = "per_mm";
  $("resolution").value = state.solver.m;
  renderParamFields($("core-fields"), metadata.params.scenario, state.scenario, "core");
  renderParamFields($("convergence-fields"),
    metadata.params.solver.filter((param) => ["max_iter", "tol"].includes(param.name)),
    state.solver, "convergence");
  renderParamFields($("output-fields"), metadata.params.output, state.output, "output");
  configureMethodSelectors(state);
  renderParamFields($("representation-editor"), [], {});
  renderSpecFields($("representation-editor"), metadata.representations, state.solver.representation,
    (spec) => { state.solver.representation = spec; updateFromControls(); }, "representation");
  renderSpecFields($("material-editor"), metadata.interpolations, state.solver.interpolation,
    (spec) => { state.solver.interpolation = spec; updateFromControls(); }, "material");
  renderSpecFields($("objective-editor"), metadata.objectives, state.scenario.objective,
    (spec) => { state.scenario.objective = spec; updateFromControls(); }, "objective");
  renderSpecList($("constraints-editor"), metadata.constraints, state.scenario.constraints || [],
    (specs) => { state.scenario.constraints = specs; updateFromControls(); }, "constraint");
  renderSpecList($("filters-editor"), metadata.filters, state.solver.filter_specs || [],
    (specs) => { state.solver.filter_specs = specs; updateFromControls(); }, "filter");
  renderSpecList($("schedules-editor"), metadata.schedules, state.solver.schedules || [],
    (specs) => { state.solver.schedules = specs; updateFromControls(); }, "schedule", schedulableItems);
  renderSpecList($("postprocess-editor"), metadata.postprocessors, state.output.postprocess || [],
    (specs) => { state.output.postprocess = specs; updateFromControls(); }, "postprocess");
  fillLoadCaseSection(state.scenario.load_cases || []);
  updateCapabilitySections(selectedMethod);
  refreshCounts();
  updateAdvancedJson();
  updateMeshResolution();
  queueDescription();
}

function updateMeshResolution() {
  if ($("resolution-mode").value === "size") {
    $("resolution").value = 1 / Number(state.solver.m || 1);
  } else {
    $("resolution").value = Number(state.solver.m || 1);
  }
}

function applyAdvancedJson() {
  try {
    const config = {
      scenario: JSON.parse($("scenario-json").value),
      solver: JSON.parse($("solver-json").value),
      output: JSON.parse($("output-json").value)
    };
    if (!config.scenario || !config.solver || !config.output) throw new Error("Each JSON value must be an object.");
    const method = methodFor(config.solver.method);
    if (!method) throw new Error(`Unknown method ${config.solver.method}`);
    methodValues = {};
    $("preset").value = selectedPreset()?.name || $("preset").value;
    loadConfiguration(config);
  } catch (error) {
    $("notice").textContent = `Could not apply JSON: ${error.message}`;
  }
}

function setStatus(status) {
  const badge = $("job-status");
  badge.textContent = status;
  badge.className = `badge ${status.toLowerCase()}`;
}

function formatAxisValue(value) {
  const magnitude = Math.abs(value);
  if (value === 0) return "0";
  if (magnitude >= 10000 || magnitude < 0.001) return value.toExponential(1);
  return Number(value.toPrecision(3)).toString();
}

function drawConvergence(values) {
  const canvas = $("convergence");
  const bounds = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(bounds.width * ratio));
  canvas.height = Math.max(1, Math.floor(bounds.height * ratio));
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  ctx.clearRect(0, 0, bounds.width, bounds.height);
  const left = 54, right = bounds.width - 10, top = 18, bottom = bounds.height - 35;
  ctx.font = "9px Consolas, monospace";
  ctx.fillStyle = "#a9aaa3";
  ctx.textBaseline = "middle";
  ctx.strokeStyle = "#545853";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(left, top);
  ctx.lineTo(left, bottom);
  ctx.lineTo(right, bottom);
  ctx.stroke();
  if (!values || values.length < 1) return;

  const low = Math.min(...values);
  const high = Math.max(...values);
  const spread = high - low;
  const padding = spread ? spread * 0.08 : Math.max(Math.abs(high) * 0.05, 1e-6);
  const axisLow = low - padding;
  const axisHigh = high + padding;
  const axisRange = axisHigh - axisLow;

  for (let tick = 0; tick <= 4; tick += 1) {
    const fraction = tick / 4;
    const y = top + (bottom - top) * fraction;
    const value = axisHigh - axisRange * fraction;
    ctx.strokeStyle = tick === 4 ? "#545853" : "#30332f";
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(right, y);
    ctx.stroke();
    ctx.textAlign = "right";
    ctx.fillText(formatAxisValue(value), left - 7, y);
  }

  const xTicks = [...new Set([0, Math.floor((values.length - 1) / 2), values.length - 1])];
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (const index of xTicks) {
    const x = left + (right - left) * (values.length === 1 ? 0 : index / (values.length - 1));
    ctx.fillText(String(index + 1), x, bottom + 8);
  }

  ctx.strokeStyle = "#c8a56b";
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((value, index) => {
    const x = left + (right - left) * (values.length === 1 ? 0 : index / (values.length - 1));
    const y = bottom - (bottom - top) * ((value - axisLow) / axisRange);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  const lastX = left + (right - left);
  const lastY = bottom - (bottom - top) * ((values[values.length - 1] - axisLow) / axisRange);
  ctx.fillStyle = "#c8a56b";
  ctx.beginPath();
  ctx.arc(lastX, lastY, 3, 0, Math.PI * 2);
  ctx.fill();
}

function displayArtifacts(job) {
  const list = $("artifacts");
  list.replaceChildren();
  const files = job.artifacts || [];
  $("artifact-placeholder").hidden = files.length > 0;
  for (const file of files) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    const path = file.split("/").map(encodeURIComponent).join("/");
    link.href = `/api/jobs/${encodeURIComponent(job.id)}/files/${path}`;
    link.textContent = file;
    link.download = file.split("/").pop();
    item.append(link);
    list.append(item);
  }
}

function appendLogs(lines) {
  if (!lines?.length) return;
  const log = $("log");
  log.textContent += `${lines.join("\n")}\n`;
  log.scrollTop = log.scrollHeight;
}

async function pollJob() {
  if (!activeJob) return;
  try {
    const job = await requestJson(`/api/jobs/${encodeURIComponent(activeJob)}?after=${logOffset}`);
    logOffset = job.next_log;
    appendLogs(job.logs);
    $("iteration-label").textContent = job.iteration
      ? `Iteration ${job.iteration} / ${job.total_iterations}` : "Iteration —";
    if (job.density_png) {
      $("density").src = `data:image/png;base64,${job.density_png}`;
      $("density").hidden = false;
      $("empty-view").hidden = true;
    }
    drawConvergence(job.objectives);
    $("stop").disabled = !job.cancellable;
    setStatus(job.status);
    displayArtifacts({ id: job.id, artifacts: job.artifacts });
    if (["completed", "cancelled", "failed"].includes(job.status)) {
      clearInterval(pollTimer);
      pollTimer = null;
      $("run").disabled = false;
      $("stop").disabled = true;
      activeJob = null;
    }
  } catch (error) {
    clearInterval(pollTimer);
    pollTimer = null;
    $("run").disabled = false;
    $("stop").disabled = true;
    setStatus("Failed");
    $("notice").textContent = error.message;
    if (error.status === 404) forgetJob();
    activeJob = null;
  }
}

async function startRun() {
  $("run").disabled = true;
  $("stop").disabled = true;
  $("notice").textContent = "";
  $("log").textContent = "";
  $("artifacts").replaceChildren();
  $("artifact-placeholder").hidden = false;
  $("density").hidden = true;
  $("empty-view").hidden = false;
  drawConvergence([]);
  logOffset = 0;
  try {
    const payload = runPayload();
    payload.mode = $("mode").value;
    payload.options = modePayload();
    const job = await requestJson("/api/jobs", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    activeJob = job.id;
    rememberJob(job.id);
    $("stop").disabled = false;
    setStatus(job.status);
    pollTimer = setInterval(pollJob, 650);
    await pollJob();
  } catch (error) {
    $("run").disabled = false;
    $("notice").textContent = error.message;
  }
}

async function restoreJob() {
  let savedJobId;
  try {
    savedJobId = localStorage.getItem(ACTIVE_JOB_KEY);
  } catch (error) {
    $("notice").textContent = `Refresh recovery is unavailable: ${error.message}`;
    return;
  }
  if (!savedJobId) return;

  activeJob = savedJobId;
  logOffset = 0;
  $("log").textContent = "";
  $("run").disabled = true;
  $("stop").disabled = true;
  setStatus("Reconnecting");
  await pollJob();
  if (activeJob) pollTimer = setInterval(pollJob, 650);
}

async function stopRun() {
  if (!activeJob) return;
  $("stop").disabled = true;
  try {
    await requestJson(`/api/jobs/${encodeURIComponent(activeJob)}/cancel`, { method: "POST", body: "{}" });
    $("notice").textContent = "Cancellation requested; stopping after the current solver step.";
  } catch (error) {
    $("notice").textContent = error.message;
  }
}

function onModeChange() {
  if ($("mode-fields").dataset.mode) {
    const previousMode = $("mode-fields").dataset.mode;
    modeValues[previousMode] = readModeOptions(previousMode);
  }
  $("load-cases-section").hidden = $("mode").value === "compare_load_cases";
  renderModeEditor();
}

function onDimensionChange() {
  if (currentMethodName.includes("+")) {
    const dimension = Number($("dimensions").value);
    const current = models.find((entry) => entry.name === $("model").value);
    if (current && !current.capabilities?.dims?.includes(dimension)) {
      const compatible = models.find((entry) => entry.capabilities?.dims?.includes(dimension));
      if (compatible) {
        $("model").value = compatible.name;
        updateMethodSelection();
      }
    }
  }
  refreshCounts();
  updateFromControls();
}

function bindEvents() {
  $("preset").addEventListener("change", () => {
    const preset = selectedPreset();
    if (preset) {
      methodValues = {};
      loadConfiguration(preset);
    }
  });
  $("approach").addEventListener("change", () => updateMethodSelection());
  $("model").addEventListener("change", () => updateMethodSelection());
  $("updater").addEventListener("change", () => updateMethodSelection());
  $("dimensions").addEventListener("change", onDimensionChange);
  $("resolution-mode").addEventListener("change", () => {
    updateMeshResolution();
    updateFromControls();
  });
  $("mode").addEventListener("change", onModeChange);
  $("apply-json").addEventListener("click", applyAdvancedJson);
  $("run").addEventListener("click", startRun);
  $("stop").addEventListener("click", stopRun);
  $("mode-fields").addEventListener("input", () => modeValues[$("mode").value] = readModeOptions());
  $("mode-fields").addEventListener("change", () => modeValues[$("mode").value] = readModeOptions());
  document.addEventListener("input", (event) => {
    if (event.target.closest(".controls") && !event.target.matches("textarea")) updateFromControls();
  });
  document.addEventListener("change", (event) => {
    if (event.target.closest(".controls") && !event.target.matches("textarea")
      && !["preset", "approach", "model", "updater", "mode", "dimensions", "resolution-mode"].includes(event.target.id)) {
      updateFromControls();
    }
  });
  window.addEventListener("resize", () => drawConvergence([]));
}

function initializeMethodSelectors() {
  const approaches = [{ value: PARTS, label: "Physics model + updater" }];
  for (const method of methods.filter((entry) => !entry.composed)) {
    approaches.push({
      value: method.name,
      label: `${method.label} (whole method)`,
      disabled: method.missing_dependencies.length > 0
    });
  }
  fillOptions($("approach"), approaches, PARTS);
  fillOptions($("model"), models.map((model) => ({
    value: model.name,
    label: model.missing_dependencies.length ? `${model.label} (needs ${model.missing_dependencies.join(", ")})` : model.label,
    disabled: model.missing_dependencies.length > 0
  })), models[0]?.name);
  fillOptions($("updater"), updaters.map((updater) => ({
    value: updater.name,
    label: updater.missing_dependencies.length ? `${updater.label} (needs ${updater.missing_dependencies.join(", ")})` : updater.label,
    disabled: updater.missing_dependencies.length > 0
  })), updaters[0]?.name);
}

async function initialize() {
  try {
    metadata = await requestJson("/api/metadata");
    presets = metadata.presets;
    methods = metadata.methods;
    models = metadata.models;
    updaters = metadata.updaters;
    for (const preset of presets) option($("preset"), preset.name, preset.name);
    for (const mode of metadata.modes) option($("mode"), mode.id, mode.label);
    initializeMethodSelectors();
    bindEvents();
    $("mode").value = "run_one";
    const preset = presets.find((entry) => entry.name === "MBB Beam") || presets[0];
    $("preset").value = preset.name;
    for (const method of methods) {
      methodValues[method.name] = {};
    }
    loadConfiguration(preset);
    renderModeEditor();
    drawConvergence([]);
    await restoreJob();
  } catch (error) {
    $("notice").textContent = `Could not load Toporia configuration: ${error.message}`;
    setStatus("Failed");
  }
}

initialize();
