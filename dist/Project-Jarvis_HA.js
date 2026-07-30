const JARVIS_UI_VERSION = "0.12.3";

const ICON_PATHS = {
  core: "M12 2 20.66 7v10L12 22 3.34 17V7L12 2m0 2.31L5.34 8.15v7.7L12 19.69l6.66-3.84v-7.7L12 4.31m0 2.19 4.75 2.74v5.52L12 17.5l-4.75-2.74V9.24L12 6.5m0 2.25-2.8 1.62v3.26l2.8 1.62 2.8-1.62v-3.26L12 8.75Z",
  bulb: "M9 21h6v-1H9v1m3-19a7 7 0 0 0-4 12.74V17h8v-2.26A7 7 0 0 0 12 2m-2 13v-1.35l-.43-.3A5 5 0 1 1 14.43 13l-.43.3V15h-4Z",
  spot: "M5 3h14l-2 8H7L5 3m3.5 10h7L17 21H7l1.5-8Z",
  strip: "M3 7h18v10H3V7m2 2v6h14V9H5m2 1h2v4H7v-4m4 0h2v4h-2v-4m4 0h2v4h-2v-4Z",
  ceiling: "M4 5h16v3H4V5m3 5h10l-2 7H9l-2-7m3.5 9h3v2h-3v-2Z",
  lamp: "M8 2h8l3 9H5l3-9m3 11h2v7h3v2H8v-2h3v-7Z",
  wall: "M4 3h3v18H4V3m5 3h9l2 6-2 6H9V6m2 2v8h5.56L18 12l-1.44-4H11Z",
  outdoor: "M7 2h10v3h-1l4 6v2h-2v9h-2v-9H8v9H6v-9H4v-2l4-6H7V2m3 3-3 6h10l-3-6h-4Z",
  switch: "M7 7h10a5 5 0 0 1 0 10H7A5 5 0 0 1 7 7m0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z",
  plug: "M8 2h2v5h4V2h2v5h2v4a6 6 0 0 1-5 5.91V22h-2v-5.09A6 6 0 0 1 6 11V7h2V2m0 7v2a4 4 0 0 0 8 0V9H8Z",
  button: "M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20m0 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14m-1 3h2v3h3v2h-3v3h-2v-3H8v-2h3V8Z",
  climate: "M10 4a2 2 0 1 1 4 0v8.17a5 5 0 1 1-4 0V4m2 0v9.27l-.67.38A3 3 0 1 0 14 16.3a3 3 0 0 0-1.33-2.65L12 13.27V4Z",
  heater: "M4 3h16v18H4V3m2 2v14h12V5H6m2 2h2v10H8V7m4 0h2v10h-2V7m4 0h1v10h-1V7Z",
  fan: "M12 10a2 2 0 1 1 0 4 2 2 0 0 1 0-4m1-8c4 0 5 4 2 8-.45-.55-1.08-.98-1.79-1.19C15 5 14 3 13 2m-4.65 3.5c2-3.46 6-2.33 7.4 2.5-.68-.24-1.45-.28-2.18-.08C11.17 4.45 8.85 4.5 8.35 5.5M4 14c-2-3.46 1-6.33 5.9-4.5-.14.7-.07 1.46.3 2.13C6 11.3 4.13 12.92 4 14m2 3.46c-2-3.46 1-6.33 5.9-4.5-.14.7-.07 1.46.3 2.13C8 14.76 6.13 16.38 6 17.46M15.65 18.5c-2 3.46-6 2.33-7.4-2.5.68.24 1.45.28 2.18.08 2.4 3.47 4.72 3.42 5.22 2.42M20 10c2 3.46-1 6.33-5.9 4.5.14-.7.07-1.46-.3-2.13C18 12.7 19.87 11.08 20 10Z",
  cover: "M3 3h18v3H3V3m2 5h14v13H5V8m2 2v2h10v-2H7m0 4v2h10v-2H7m0 4v1h10v-1H7Z",
  garage: "M3 3h18v18h-2V7H5v14H3V3m4 6h10v3H7V9m0 5h10v3H7v-3m0 5h10v2H7v-2Z",
  media: "M5 3h14v18H5V3m2 2v14h10V5H7m5 2a3 3 0 1 1 0 6 3 3 0 0 1 0-6m0 8a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Z",
  tv: "M3 5h18v13H3V5m2 2v9h14V7H5m4 13h6v2H9v-2Z",
  camera: "M4 5h4l2-2h4l2 2h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2m8 3a5 5 0 1 0 0 10 5 5 0 0 0 0-10m0 2a3 3 0 1 1 0 6 3 3 0 0 1 0-6Z",
  lock: "M6 10h1V7a5 5 0 0 1 10 0v3h1a2 2 0 0 1 2 2v8H4v-8a2 2 0 0 1 2-2m3 0h6V7a3 3 0 0 0-6 0v3m3 3a2 2 0 0 0-1 3.73V18h2v-1.27A2 2 0 0 0 12 13Z",
  motion: "M13 5a2 2 0 1 1-4 0 2 2 0 0 1 4 0m-1 4 3 2v4h-2v-3l-2-1-1 4 2 6H9l-2-6 1-5 2-1h2m5-5a8 8 0 0 1 0 16v-2a6 6 0 0 0 0-12V4m2-3a11 11 0 0 1 0 22v-2a9 9 0 0 0 0-18V1Z",
  sensor: "M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20m0 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14m0 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8m0 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z",
  battery: "M16 5h2v3h2v8h-2v3H4V5h12m0 2H6v10h10V7m-1 1-5 8v-5H8l5-3v5h2V8Z",
  energy: "M13 2 4 14h7l-1 8 9-12h-7l1-8Z",
  network: "M12 3a16 16 0 0 1 10.6 4L21 8.8a13.5 13.5 0 0 0-18 0L1.4 7A16 16 0 0 1 12 3m0 5a11 11 0 0 1 7.4 2.8l-1.7 1.8a8.5 8.5 0 0 0-11.4 0l-1.7-1.8A11 11 0 0 1 12 8m0 5a6 6 0 0 1 4.1 1.6L12 19l-4.1-4.4A6 6 0 0 1 12 13Z",
  room: "M3 3h18v18H3V3m2 2v14h14V5H5m7 7h5v5h-5v-5m-5-5h3v10H7V7Z",
  person: "M12 2a4 4 0 1 1 0 8 4 4 0 0 1 0-8m0 10c4.42 0 8 1.79 8 4v4H4v-4c0-2.21 3.58-4 8-4Z",
  weather: "M7 18a5 5 0 1 1 1.5-9.77A6 6 0 0 1 20 10.5 3.75 3.75 0 0 1 19.25 18H7m0-2h12.25a1.75 1.75 0 1 0-.35-3.46l-1.4-.28.07-1.43A4 4 0 0 0 10 8.7l-.42 1.18-1.25.14A3 3 0 0 0 7 16Z",
  appliance: "M5 2h14v20H5V2m2 2v4h10V4H7m5 6a5 5 0 1 0 0 10 5 5 0 0 0 0-10m0 2a3 3 0 1 1 0 6 3 3 0 0 1 0-6Z",
  vacuum: "M12 4a8 8 0 1 1-7.75 10H2v-2h2.25A8 8 0 0 1 12 4m0 2a6 6 0 1 0 0 12 6 6 0 0 0 0-12m-3 5h6v2H9v-2Z",
  vehicle: "M5 4h14l2 7v8h-2v2h-3v-2H8v2H5v-2H3v-8l2-7m1.5 2-1.43 5h13.86L17.5 6h-11M6 13a2 2 0 1 0 0 4 2 2 0 0 0 0-4m12 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z",
  automation: "M4 4h6v6H4V4m10 0h6v6h-6V4M4 14h6v6H4v-6m13-2 5 5-5 5v-3h-5v-4h5v-3Z",
};

const ICON_ALIASES = {
  "circle-double": "core", brain: "core", jarvis: "core",
  light: "bulb", lightbulb: "bulb", "filament-bulb": "bulb",
  spotlight: "spot", "light-strip": "strip", "ceiling-light": "ceiling",
  "pendant-light": "lamp", "floor-lamp": "lamp", "table-lamp": "lamp",
  "wall-light": "wall", "outdoor-light": "outdoor",
  switch: "switch", relay: "switch", plug: "plug", button: "button",
  thermostat: "climate", temperature: "climate", humidity: "climate",
  heater: "heater", radiator: "heater", fan: "fan", climate: "climate",
  blind: "cover", curtain: "cover", awning: "cover", cover: "cover",
  "garage-door": "garage", speaker: "media", "speaker-group": "media",
  media: "media", television: "tv", receiver: "media",
  camera: "camera", doorbell: "camera", lock: "lock", contact: "lock",
  motion: "motion", occupancy: "motion", smoke: "sensor", leak: "sensor",
  sensor: "sensor", battery: "battery", energy: "energy", power: "energy",
  network: "network", "air-quality": "sensor", room: "room", floor: "room",
  person: "person", presence: "person", weather: "weather", sun: "weather",
  vacuum: "vacuum", washer: "appliance", dryer: "appliance",
  dishwasher: "appliance", appliance: "appliance",
  vehicle: "vehicle", ev: "vehicle", charger: "energy", polestar: "vehicle",
  scene: "automation", script: "automation", automation: "automation",
  update: "automation", timer: "automation", mower: "vacuum",
  "robot-mower": "vacuum", washer: "appliance", "washing-machine": "appliance",
  spotify: "media", "ev-charger": "energy", tile: "button",
  markup: "core", alarm: "lock", security: "lock",
};

window.customIconsets = window.customIconsets || {};
window.customIconsets.jarvis = async (name) => ({
  path: ICON_PATHS[ICON_ALIASES[name] || name] || ICON_PATHS.core,
  viewBox: "0 0 24 24",
});

const DOMAIN_ICONS = {
  light: "jarvis:lightbulb", switch: "jarvis:switch", input_boolean: "jarvis:switch",
  button: "jarvis:button", input_button: "jarvis:button", climate: "jarvis:thermostat",
  fan: "jarvis:fan", cover: "jarvis:cover", media_player: "jarvis:speaker",
  camera: "jarvis:camera", lock: "jarvis:lock", binary_sensor: "jarvis:sensor",
  sensor: "jarvis:sensor", person: "jarvis:person", weather: "jarvis:weather",
  sun: "jarvis:sun", vacuum: "jarvis:vacuum", scene: "jarvis:scene",
  script: "jarvis:script", automation: "jarvis:automation", update: "jarvis:update",
  number: "jarvis:sensor", input_number: "jarvis:sensor",
  device_tracker: "jarvis:presence", fan: "jarvis:fan", vacuum: "jarvis:vacuum",
  lawn_mower: "jarvis:robot-mower", alarm_control_panel: "jarvis:alarm",
  timer: "jarvis:timer",
};

const DEVICE_CLASS_ICONS = {
  battery: "jarvis:battery", power: "jarvis:power", energy: "jarvis:energy",
  temperature: "jarvis:temperature", humidity: "jarvis:humidity",
  motion: "jarvis:motion", occupancy: "jarvis:occupancy",
  door: "jarvis:contact", window: "jarvis:contact", garage_door: "jarvis:garage-door",
  smoke: "jarvis:smoke", moisture: "jarvis:leak", connectivity: "jarvis:network",
  plug: "jarvis:plug",
};

function fireEvent(element, type, detail = {}) {
  const event = new CustomEvent(type, { bubbles: true, composed: true, detail });
  element.dispatchEvent(event);
}

function dispatchHassAction(element, config, action = "tap") {
  fireEvent(element, "hass-action", { config, action });
}

function entityDomain(entityId = "") {
  return entityId.split(".")[0];
}

function stateObject(hass, entityId) {
  return hass?.states?.[entityId];
}

function friendlyName(state, config) {
  return config.name || state?.attributes?.friendly_name || config.entity || "Jarvis";
}

function entityIcon(state, config) {
  if (config.icon) return config.icon;
  const deviceClass = state?.attributes?.device_class;
  return DEVICE_CLASS_ICONS[deviceClass] || state?.attributes?.icon ||
    DOMAIN_ICONS[entityDomain(config.entity)] || "jarvis:core";
}

function isActive(state) {
  return ["on", "open", "opening", "playing", "home", "heat", "cool", "cleaning"]
    .includes(state?.state);
}

function isUnavailable(state) {
  return !state || ["unknown", "unavailable"].includes(state.state);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function formatState(state, config) {
  if (!state) return "Entity unavailable";
  const raw = config.attribute ? state.attributes?.[config.attribute] : state.state;
  const unit = config.unit ?? state.attributes?.unit_of_measurement ?? "";
  return `${formatValue(raw)}${unit ? ` ${unit}` : ""}`;
}

// Numeric telemetry is deliberately normalized throughout the library. This
// keeps dense room and panel layouts stable while retaining meaningful detail.
function formatValue(value) {
  if (value === null || value === undefined || value === "") return "unknown";
  const numeric = typeof value === "number" ? value :
    (typeof value === "string" && value.trim() !== "" ? Number(value) : NaN);
  return Number.isFinite(numeric) ? numeric.toFixed(1) : String(value);
}

function accent(config, state) {
  if (config.entity && isUnavailable(state)) return "#667986";
  if (config.accent === "amber" || (config.accent === "auto" && isActive(state))) return "#ffc247";
  if (config.accent === "red") return "#ff6572";
  if (config.accent === "green") return "#55e6a5";
  return "#20d8ff";
}

function commonForm(entityRequired = true) {
  return {
    schema: [
      ...(entityRequired ? [{ name: "entity", required: true, selector: { entity: {} } }] : []),
      {
        type: "grid", name: "", flatten: true, schema: [
          { name: "name", selector: { text: {} } },
          { name: "icon", selector: { icon: {} }, context: { icon_entity: "entity" } },
          {
            name: "accent", selector: {
              select: {
                mode: "dropdown",
                options: ["auto", "cyan", "amber", "green", "red"],
              },
            },
          },
          {
            name: "layout", selector: {
              select: { options: ["compact", "standard", "wide"] },
            },
          },
        ],
      },
      {
        type: "expandable", name: "actions", flatten: true, title: "Actions", schema: [
          { name: "tap_action", selector: { ui_action: {} } },
          { name: "hold_action", selector: { ui_action: {} } },
          { name: "double_tap_action", selector: { ui_action: {} } },
        ],
      },
    ],
    computeLabel: (schema) => ({
      name: "Friendly name", icon: "Jarvis or Home Assistant icon",
      accent: "Accent colour", layout: "Card layout",
      tap_action: "Tap action", hold_action: "Hold action",
      double_tap_action: "Double-tap action",
    }[schema.name]),
  };
}

const HUD_STYLE = `
  :host {
    display:block;
    height:100%;
    min-height:0;
    box-sizing:border-box;
    padding:6px;
    container-type:inline-size;
    --j-cyan:var(--jarvis-cyan,#20d8ff);
    --j-amber:var(--jarvis-amber,#ffc247);
    --j-red:var(--jarvis-red,#ff6572);
    --j-green:var(--jarvis-green,#55e6a5);
    --j-surface:var(--jarvis-surface,rgba(3,16,27,.92));
    --j-space-1:var(--jarvis-space-1,6px);
    --j-space-2:var(--jarvis-space-2,10px);
    --j-space-3:var(--jarvis-space-3,14px);
    --j-space-4:var(--jarvis-space-4,18px);
    --j-control-size:var(--jarvis-control-size,42px);
    --j-line:color-mix(in srgb,var(--j-accent,var(--j-cyan)) 52%,transparent);
    font-family:var(--jarvis-font,var(--primary-font-family,sans-serif));
  }
  ha-card {
    --ha-card-border-radius:2px;
    position:relative;
    height:100%;
    min-height:0;
    box-sizing:border-box;
    overflow:hidden;
    color:var(--primary-text-color,#eafaff);
    background:
      linear-gradient(90deg,rgba(32,216,255,.035) 1px,transparent 1px) 0 0/24px 24px,
      linear-gradient(rgba(32,216,255,.025) 1px,transparent 1px) 0 0/24px 24px,
      linear-gradient(145deg,rgba(5,25,39,.97),var(--j-surface));
    border:1px solid var(--j-line);
    border-radius:2px!important;
    clip-path:polygon(0 10px,10px 0,72% 0,calc(72% + 8px) 8px,100% 8px,100% calc(100% - 10px),calc(100% - 10px) 100%,30% 100%,calc(30% - 8px) calc(100% - 8px),0 calc(100% - 8px))!important;
    box-shadow:inset 0 0 34px color-mix(in srgb,var(--j-accent) 7%,transparent),0 12px 30px rgba(0,0,0,.26);
    transition:transform 160ms ease,border-color 160ms ease,box-shadow 160ms ease,filter 160ms ease;
  }
  ha-card>div{height:100%;min-height:0!important;box-sizing:border-box}
  ha-card::before,ha-card::after{content:"";position:absolute;pointer-events:none;z-index:3}
  ha-card::before{left:16px;top:0;width:56px;height:2px;background:var(--j-accent);box-shadow:0 0 10px var(--j-accent)}
  ha-card::after{right:16px;bottom:0;width:34px;height:2px;background:var(--j-accent);box-shadow:0 0 10px var(--j-accent)}
  ha-card.interactive{cursor:pointer}
  ha-card.interactive:hover,ha-card.interactive:focus-visible,ha-card.engaged{
    transform:translateY(-2px);
    border-color:color-mix(in srgb,var(--j-accent) 82%,white 8%);
    box-shadow:inset 0 0 42px color-mix(in srgb,var(--j-accent) 12%,transparent),0 0 24px color-mix(in srgb,var(--j-accent) 22%,transparent),0 16px 34px rgba(0,0,0,.3);
    filter:saturate(1.1);
    outline:none;
  }
  .hud-corner{position:absolute;width:18px;height:18px;pointer-events:none;z-index:4}
  .hud-corner.tl{left:5px;top:5px;border-left:2px solid var(--j-accent);border-top:2px solid var(--j-accent)}
  .hud-corner.br{right:5px;bottom:5px;border-right:2px solid var(--j-accent);border-bottom:2px solid var(--j-accent)}
  .eyebrow{font:700 10px/1.2 ui-monospace,monospace;letter-spacing:.19em;text-transform:uppercase;color:var(--j-accent)}
  .copy{min-width:0}
  .name{font-size:16px;font-weight:650;line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .state{font:600 12px/1.3 ui-monospace,monospace;color:var(--secondary-text-color,#8bb5c7);text-transform:uppercase}
  .icon-shell{display:grid;place-items:center;color:var(--j-accent);border:1px solid var(--j-line);background:color-mix(in srgb,var(--j-accent) 9%,transparent);box-shadow:inset 0 0 16px color-mix(in srgb,var(--j-accent) 10%,transparent)}
  .icon-shell ha-icon{filter:drop-shadow(0 0 7px color-mix(in srgb,var(--j-accent) 70%,transparent))}
  button{font:600 11px/1 ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--primary-text-color,#eafaff);background:rgba(6,26,40,.82);border:1px solid var(--j-line);border-radius:1px;min-width:42px;min-height:38px;cursor:pointer}
  button:hover,button:focus-visible{border-color:var(--j-accent);box-shadow:0 0 12px color-mix(in srgb,var(--j-accent) 28%,transparent);outline:none}
  button.primary{color:#00131a;background:var(--j-accent);border-color:var(--j-accent)}
  input[type=range]{width:100%;height:5px;accent-color:var(--j-accent);cursor:pointer}
  .unavailable{opacity:.68}
  .j-layout{padding:var(--j-space-4);display:grid;gap:var(--j-space-3);min-height:126px;box-sizing:border-box}
  .j-header{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:var(--j-space-3);align-items:center}
  .j-header .icon-shell{width:46px;height:46px}
  .j-controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(72px,1fr));gap:var(--j-space-2)}
  .j-value{font:700 20px ui-monospace,monospace;color:var(--j-accent);white-space:nowrap}
  @container(max-width:430px){
    .j-layout{padding:var(--j-space-3);gap:var(--j-space-2)}
    .j-header{grid-template-columns:40px minmax(0,1fr) auto;gap:var(--j-space-2)}
    .j-header .icon-shell{width:38px;height:38px}
    .name{font-size:14px}.eyebrow{font-size:8px;letter-spacing:.13em}
    button{min-height:36px;min-width:36px;font-size:9px}
  }
  @media(max-width:680px){ha-card{clip-path:polygon(0 8px,8px 0,70% 0,calc(70% + 6px) 6px,100% 6px,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%)}}
  @media(prefers-reduced-motion:reduce){ha-card,*{animation:none!important;transition:none!important}}
`;

class JarvisBaseCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._holdTimer = undefined;
    this._holdFired = false;
  }

  setConfig(config) {
    if (this.constructor.requiresEntity !== false && !config.entity) {
      throw new Error(`${this.constructor.cardName || "Jarvis card"} requires an entity`);
    }
    this._config = {
      accent: config.accent || config.color || "auto", layout: "standard",
      tap_action: { action: "more-info" },
      hold_action: { action: "none" },
      double_tap_action: { action: "none" },
      ...config,
    };
    this.render();
  }

  set hass(value) {
    this._hass = value;
    this.render();
  }

  getCardSize() { return this._config?.layout === "compact" ? 2 : (this.constructor.gridRows || 3); }
  getGridOptions() {
    const wide = this._config?.layout === "wide";
    const rows = this._config?.layout === "compact" ? 2 : (this.constructor.gridRows || 3);
    return { rows, columns: wide ? 12 : 6, min_rows: rows, min_columns: 3 };
  }

  static getConfigForm() { return commonForm(this.requiresEntity !== false); }
  static getStubConfig(hass) {
    const domain = this.domains?.[0];
    const entity = Object.keys(hass?.states || {}).find((id) => !domain || entityDomain(id) === domain);
    return entity ? { entity } : {};
  }

  cardState() { return stateObject(this._hass, this._config?.entity); }

  shell(content, { interactive = true, ariaLabel } = {}) {
    const state = this.constructor.requiresEntity === false ? {} : this.cardState();
    const color = accent(this._config, state);
    this.shadowRoot.innerHTML = `
      <style>${HUD_STYLE}</style>
      <ha-card class="jarvis-hud-frame ${interactive ? "interactive" : ""} ${this.constructor.requiresEntity !== false && isUnavailable(state) ? "unavailable" : ""}"
        style="--j-accent:${color}" ${interactive ? 'tabindex="0" role="button"' : ""}>
        <i class="hud-corner tl"></i><i class="hud-corner br"></i>${content}
      </ha-card>`;
    const card = this.shadowRoot.querySelector("ha-card");
    if (ariaLabel) card.setAttribute("aria-label", ariaLabel);
    if (interactive) this.bindActions(card);
    return card;
  }

  bindActions(target) {
    target.addEventListener("click", (event) => {
      if (event.target.closest("button,input")) return;
      if (this._holdFired) { this._holdFired = false; return; }
      dispatchHassAction(this, this._config, "tap");
    });
    target.addEventListener("dblclick", (event) => {
      if (event.target.closest("button,input")) return;
      event.preventDefault();
      dispatchHassAction(this, this._config, "double_tap");
    });
    target.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button,input")) return;
      this._holdTimer = setTimeout(() => {
        this._holdFired = true;
        dispatchHassAction(this, this._config, "hold");
      }, 500);
    });
    ["pointerup", "pointerleave", "pointercancel"].forEach((name) =>
      target.addEventListener(name, () => clearTimeout(this._holdTimer)));
    target.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        dispatchHassAction(this, this._config, "tap");
      }
    });
  }

  call(domain, service, data = {}) {
    if (!this._hass?.callService) return;
    this._hass.callService(domain, service, { entity_id: this._config.entity, ...data });
  }

  entityHeader(kicker = "Entity interface") {
    const state = this.cardState();
    return `
      <div class="icon-shell"><ha-icon icon="${escapeHtml(entityIcon(state, this._config))}"></ha-icon></div>
      <div class="copy"><div class="eyebrow">${escapeHtml(kicker)}</div>
      <div class="name">${escapeHtml(friendlyName(state, this._config))}</div>
      <div class="state">${escapeHtml(formatState(state, this._config))}</div></div>`;
  }
}

class JarvisEntityCard extends JarvisBaseCard {
  static cardName = "Jarvis Entity Card";
  static getStubConfig(hass) {
    const entity = Object.keys(hass?.states || {})[0];
    return entity ? { entity } : {};
  }
  render() {
    if (!this._config) return;
    this.shell(`<div class="entity">${this.entityHeader()}</div>
      <style>.entity{min-height:126px;padding:20px;display:grid;grid-template-columns:54px 1fr;gap:16px;align-items:center}.icon-shell{width:52px;height:52px}.icon-shell ha-icon{--mdc-icon-size:29px}.copy{min-width:0}.state{margin-top:7px}</style>`,
      { ariaLabel: friendlyName(this.cardState(), this._config) });
  }
}

class JarvisButtonCard extends JarvisBaseCard {
  static requiresEntity = false;
  static cardName = "Jarvis Button";
  static gridRows = 3;
  static getConfigForm() {
    const form = commonForm(false);
    form.schema.unshift({ name: "label", required: true, selector: { text: {} } });
    return form;
  }
  static getStubConfig() { return { label: "Jarvis Command", icon: "jarvis:button", tap_action: { action: "none" } }; }
  render() {
    if (!this._config) return;
    const label = this._config.label || this._config.name || "Jarvis Command";
    this.shell(`<div class="button-layout"><div class="icon-shell"><ha-icon icon="${escapeHtml(this._config.icon || "jarvis:button")}"></ha-icon></div><div><div class="eyebrow">Command node</div><div class="name">${escapeHtml(label)}</div><div class="state">${escapeHtml(this._config.description || "Ready")}</div></div><div class="chev">›</div></div>
      <style>.button-layout{min-height:112px;padding:18px;display:grid;grid-template-columns:48px 1fr 20px;gap:14px;align-items:center}.icon-shell{width:46px;height:46px}.chev{font:300 30px monospace;color:var(--j-accent)}</style>`,
      { ariaLabel: label });
  }
}

// A distinct constructor is required because the Custom Elements registry does
// not allow one constructor to be registered under two tag names.
class JarvisActionCard extends JarvisButtonCard {
  static cardName = "Jarvis Action Card";
}

class JarvisSwitchCard extends JarvisEntityCard {
  static cardName = "Jarvis Switch";
  static domains = ["switch", "input_boolean"];
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const on = state?.state === "on";
    const domain = entityDomain(this._config.entity);
    this.shell(`<div class="switch-layout">${this.entityHeader("Power control")}<button class="${on ? "primary" : ""}" aria-label="Toggle">${on ? "ON" : "OFF"}</button></div>
      <style>.switch-layout{min-height:126px;padding:20px;display:grid;grid-template-columns:50px 1fr auto;gap:14px;align-items:center}.icon-shell{width:48px;height:48px}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelector("button").addEventListener("click", () => this.call(domain === "input_boolean" ? "input_boolean" : "switch", "toggle"));
  }
}

class JarvisLightCard extends JarvisBaseCard {
  static cardName = "Jarvis Light";
  static domains = ["light"];
  static gridRows = 4;
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const on = state?.state === "on";
    const brightness = Math.round(((state?.attributes?.brightness || 0) / 255) * 100);
    this.shell(`<div class="light-layout"><div class="top"><button class="icon-shell light-toggle ${on ? "primary" : ""}" aria-label="Turn ${on ? "off" : "on"} ${escapeHtml(friendlyName(state, this._config))}" aria-pressed="${on}"><ha-icon icon="${escapeHtml(entityIcon(state, this._config))}"></ha-icon></button><div class="copy"><div class="eyebrow">Lighting array</div><div class="name">${escapeHtml(friendlyName(state, this._config))}</div><div class="state">${escapeHtml(formatState(state, this._config))}</div></div></div><div class="meter"><span>OUTPUT</span><b>${brightness}%</b><input aria-label="Brightness" type="range" min="0" max="100" value="${brightness}"></div></div>
      <style>.light-layout{min-height:160px;padding:18px}.top{display:grid;grid-template-columns:48px minmax(0,1fr);gap:14px;align-items:center}.light-toggle{width:46px;height:46px;min-width:46px;min-height:46px;padding:0}.light-toggle ha-icon{--mdc-icon-size:27px}.meter{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:12px;align-items:center;margin-top:20px;font:700 10px monospace;color:var(--secondary-text-color)}.meter input{grid-column:1/-1}.meter b{grid-column:3;color:var(--j-accent)}@media(max-width:900px){.light-layout{padding:14px}.top{grid-template-columns:40px minmax(0,1fr);gap:8px}.light-toggle{width:38px;height:38px;min-width:38px;min-height:38px}.light-toggle ha-icon{--mdc-icon-size:23px}.eyebrow{font-size:8px;letter-spacing:.13em}.name{font-size:14px}.meter{margin-top:14px;gap:8px}}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelector(".light-toggle").addEventListener("click", () => this.call("light", "toggle"));
    this.shadowRoot.querySelector("input").addEventListener("change", (event) => {
      const value = Number(event.target.value);
      this.call("light", "turn_on", { brightness_pct: value });
    });
  }
}

class JarvisSliderCard extends JarvisBaseCard {
  static cardName = "Jarvis Slider";
  static getConfigForm() {
    const form = commonForm(true);
    form.schema.splice(1, 0, {
      type: "grid", name: "", flatten: true, schema: [
        { name: "min", selector: { number: { mode: "box" } } },
        { name: "max", selector: { number: { mode: "box" } } },
        { name: "step", selector: { number: { mode: "box" } } },
      ],
    });
    return form;
  }
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const attrs = state?.attributes || {};
    const value = Number(state?.state) || 0;
    const min = this._config.min ?? attrs.min ?? 0;
    const max = this._config.max ?? attrs.max ?? 100;
    const step = this._config.step ?? attrs.step ?? 1;
    this.shell(`<div class="slider-layout">${this.entityHeader("Variable control")}<div class="readout">${escapeHtml(formatValue(value))}</div><input aria-label="Value" type="range" min="${min}" max="${max}" step="${step}" value="${value}"></div>
      <style>.slider-layout{min-height:140px;padding:18px;display:grid;grid-template-columns:48px 1fr auto;gap:14px;align-items:center}.icon-shell{width:46px;height:46px}.readout{font:700 18px monospace;color:var(--j-accent)}input{grid-column:1/-1}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelector("input").addEventListener("change", (event) => {
      const domain = entityDomain(this._config.entity);
      const valueNow = Number(event.target.value);
      const routes = {
        number: ["number", "set_value", { value: valueNow }],
        input_number: ["input_number", "set_value", { value: valueNow }],
        fan: ["fan", "set_percentage", { percentage: valueNow }],
        media_player: ["media_player", "volume_set", { volume_level: valueNow / 100 }],
        cover: ["cover", "set_cover_position", { position: valueNow }],
        climate: ["climate", "set_temperature", { temperature: valueNow }],
        light: ["light", "turn_on", { brightness_pct: valueNow }],
      };
      const route = routes[domain];
      if (route) this.call(route[0], route[1], route[2]);
    });
  }
}

class JarvisClimateCard extends JarvisBaseCard {
  static cardName = "Jarvis Climate";
  static domains = ["climate"];
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const attrs = state?.attributes || {};
    const temp = attrs.temperature ?? attrs.current_temperature ?? 20;
    this.shell(`<div class="climate-layout">${this.entityHeader("Climate regulation")}<div class="temp">${escapeHtml(formatValue(attrs.current_temperature))}°<small>CURRENT</small></div><div class="target"><span>TARGET ${escapeHtml(formatValue(temp))}°</span><input aria-label="Target temperature" type="range" min="${attrs.min_temp ?? 5}" max="${attrs.max_temp ?? 35}" step="${attrs.target_temp_step ?? .5}" value="${temp}"></div></div>
      <style>.climate-layout{min-height:168px;padding:18px;display:grid;grid-template-columns:48px 1fr auto;gap:14px;align-items:center}.icon-shell{width:46px;height:46px}.temp{font:700 28px monospace;color:var(--j-accent);text-align:right}.temp small{display:block;font-size:8px;letter-spacing:.16em}.target{grid-column:1/-1;display:grid;gap:9px;font:700 10px monospace;color:var(--secondary-text-color)}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelector("input").addEventListener("change", (event) => this.call("climate", "set_temperature", { temperature: Number(event.target.value) }));
  }
}

class JarvisCoverCard extends JarvisBaseCard {
  static cardName = "Jarvis Cover";
  static domains = ["cover"];
  static gridRows = 4;
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const pos = state?.attributes?.current_position;
    this.shell(`<div class="cover-layout">${this.entityHeader("Aperture control")}<div class="controls"><button data-service="open_cover">OPEN</button><button data-service="stop_cover">STOP</button><button data-service="close_cover">CLOSE</button></div>${pos == null ? "" : `<div class="position"><span>POSITION</span><b>${pos}%</b><input aria-label="Cover position" type="range" min="0" max="100" value="${pos}"></div>`}</div>
      <style>.cover-layout{min-height:164px;padding:18px;display:grid;grid-template-columns:48px 1fr;gap:14px;align-items:center}.icon-shell{width:46px;height:46px}.controls{grid-column:1/-1;display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.position{grid-column:1/-1;display:grid;grid-template-columns:1fr auto;gap:8px;font:700 10px monospace;color:var(--secondary-text-color)}.position b{color:var(--j-accent)}.position input{grid-column:1/-1}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => this.call("cover", button.dataset.service)));
    this.shadowRoot.querySelector("input")?.addEventListener("change", (event) => this.call("cover", "set_cover_position", { position: Number(event.target.value) }));
  }
}

class JarvisMediaCard extends JarvisBaseCard {
  static cardName = "Jarvis Media";
  static domains = ["media_player"];
  static gridRows = 4;
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const volume = Math.round((state?.attributes?.volume_level || 0) * 100);
    this.shell(`<div class="media-layout">${this.entityHeader("Media channel")}<div class="controls"><button data-service="media_previous_track">PREV</button><button class="primary" data-service="media_play_pause">PLAY</button><button data-service="media_next_track">NEXT</button></div><div class="volume"><span>VOLUME</span><b>${volume}%</b><input aria-label="Volume" type="range" min="0" max="100" value="${volume}"></div></div>
      <style>.media-layout{min-height:178px;padding:18px;display:grid;grid-template-columns:48px 1fr;gap:14px;align-items:center}.icon-shell{width:46px;height:46px}.controls{grid-column:1/-1;display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.volume{grid-column:1/-1;display:grid;grid-template-columns:1fr auto;gap:8px;font:700 10px monospace;color:var(--secondary-text-color)}.volume b{color:var(--j-accent)}.volume input{grid-column:1/-1}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => this.call("media_player", button.dataset.service)));
    this.shadowRoot.querySelector("input").addEventListener("change", (event) => this.call("media_player", "volume_set", { volume_level: Number(event.target.value) / 100 }));
  }
}

class JarvisCameraCard extends JarvisBaseCard {
  static cardName = "Jarvis Camera";
  static domains = ["camera"];
  getCardSize() { return 5; }
  getGridOptions() {
    return { rows: 5, columns: 6, min_rows: 5, min_columns: 3 };
  }
  constructor() {
    super();
    this._cameraCard = undefined;
    this._cameraEntity = undefined;
    this._cameraMounting = undefined;
    this._fallbackTimer = undefined;
  }
  set hass(value) {
    this._hass = value;
    if (!this.shadowRoot.querySelector(".camera-host")) this.render();
    this._mountCamera();
  }
  disconnectedCallback() {
    clearInterval(this._fallbackTimer);
  }
  render() {
    if (!this._config) return;
    const state = this.cardState();
    this.shell(`<div class="camera-layout card-layout"><div class="camera-host" aria-label="Live camera stream"></div><div class="live-badge"><i></i>LIVE</div><div class="overlay">${this.entityHeader("Visual channel")}</div></div>
      <style>.camera-layout{min-height:230px;position:relative;background:#01070b}.camera-host{position:absolute;inset:0;overflow:hidden}.camera-host>*{display:block;width:100%;height:100%;--ha-card-border-radius:0;--ha-card-box-shadow:none;--ha-card-background:transparent}.camera-host img{width:100%;height:100%;object-fit:cover;opacity:.78}.live-badge{position:absolute;right:14px;top:13px;display:flex;gap:6px;align-items:center;padding:5px 7px;border:1px solid var(--j-line);background:rgba(2,13,22,.82);font:700 9px monospace;letter-spacing:.14em;color:var(--j-accent)}.live-badge i{width:6px;height:6px;background:var(--j-red);box-shadow:0 0 7px var(--j-red);animation:live-pulse 1.4s ease-in-out infinite}.overlay{position:absolute;left:0;right:0;bottom:0;padding:28px 18px 16px;display:grid;grid-template-columns:42px 1fr;gap:12px;align-items:center;background:linear-gradient(transparent,rgba(2,13,22,.96));pointer-events:none}.icon-shell{width:40px;height:40px}.state{color:#b8dce8}@keyframes live-pulse{50%{opacity:.35}}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
    this._cameraCard = undefined;
    this._cameraEntity = undefined;
    this._mountCamera();
  }
  async _mountCamera() {
    const host = this.shadowRoot.querySelector(".camera-host");
    if (!host || !this._hass || !this._config?.entity) return;
    if (this._cameraCard && this._cameraEntity === this._config.entity) {
      this._cameraCard.hass = this._hass;
      return;
    }
    if (this._cameraMounting === this._config.entity) return;
    this._cameraMounting = this._config.entity;
    clearInterval(this._fallbackTimer);
    try {
      const helpers = await window.loadCardHelpers();
      if (!this.shadowRoot.contains(host)) return;
      const card = await helpers.createCardElement({
        type: "picture-entity",
        entity: this._config.entity,
        camera_view: "live",
        show_name: false,
        show_state: false,
        tap_action: { action: "none" },
        hold_action: { action: "none" },
      });
      card.style.height = "100%";
      host.replaceChildren(card);
      card.hass = this._hass;
      requestAnimationFrame(() => {
        if (this.shadowRoot.contains(card)) {
          card.hass = this._hass;
          card.requestUpdate?.();
        }
      });
      this._cameraCard = card;
      this._cameraEntity = this._config.entity;
    } catch (_error) {
      this._mountSnapshotFallback(host);
    } finally {
      this._cameraMounting = undefined;
    }
  }
  _mountSnapshotFallback(host) {
    const image = document.createElement("img");
    image.alt = "";
    const refresh = () => {
      image.src = `/api/camera_proxy/${this._config.entity}?jarvis=${Date.now()}`;
    };
    refresh();
    host.replaceChildren(image);
    this._fallbackTimer = setInterval(refresh, 5000);
  }
}

class JarvisSensorCard extends JarvisBaseCard {
  static cardName = "Jarvis Sensor";
  static domains = ["sensor", "binary_sensor", "sun", "weather"];
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const value = formatState(state, this._config);
    this.shell(`<div class="sensor-layout">${this.entityHeader("Telemetry")}<div class="value">${escapeHtml(value)}</div><div class="trace">${Array.from({ length: 18 }, (_, i) => `<i style="height:${15 + ((i * 23) % 65)}%"></i>`).join("")}</div></div>
      <style>.sensor-layout{min-height:148px;padding:18px;display:grid;grid-template-columns:48px 1fr auto;gap:14px;align-items:center}.icon-shell{width:46px;height:46px}.value{font:700 21px monospace;color:var(--j-accent)}.trace{grid-column:1/-1;height:30px;display:flex;gap:4px;align-items:end;border-bottom:1px solid var(--j-line)}.trace i{flex:1;background:var(--j-accent);opacity:.42;box-shadow:0 0 5px var(--j-accent)}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
  }
}

class JarvisSecurityCard extends JarvisSwitchCard {
  static cardName = "Jarvis Security";
  static domains = ["lock", "alarm_control_panel", "binary_sensor"];
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const domain = entityDomain(this._config.entity);
    this.shell(`<div class="security-layout">${this.entityHeader("Security monitor")}<button>${domain === "lock" ? (state?.state === "locked" ? "UNLOCK" : "LOCK") : "DETAILS"}</button></div>
      <style>.security-layout{min-height:126px;padding:20px;display:grid;grid-template-columns:50px 1fr auto;gap:14px;align-items:center}.icon-shell{width:48px;height:48px}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelector("button").addEventListener("click", () => {
      if (domain === "lock") this.call("lock", state?.state === "locked" ? "unlock" : "lock");
      else fireEvent(this, "hass-more-info", { entityId: this._config.entity });
    });
  }
}

class JarvisStatusCard extends JarvisBaseCard {
  static requiresEntity = false;
  static cardName = "Jarvis Status";
  static getConfigForm() {
    return {
      schema: [
        { name: "name", selector: { text: {} } },
        { name: "entities", required: true, selector: { entity: { multiple: true } } },
        { name: "accent", selector: { select: { options: ["cyan", "amber", "green", "red"] } } },
      ],
    };
  }
  static getStubConfig(hass) { return { name: "System status", entities: Object.keys(hass?.states || {}).slice(0, 4) }; }
  render() {
    if (!this._config) return;
    const entities = this._config.entities || [];
    const rows = entities.slice(0, 12).map((id) => {
      const state = stateObject(this._hass, id);
      return `<div class="row"><ha-icon icon="${escapeHtml(entityIcon(state, { entity: id }))}"></ha-icon><span>${escapeHtml(state?.attributes?.friendly_name || id)}</span><b class="${isUnavailable(state) ? "bad" : ""}">${escapeHtml(state ? formatState(state, { entity: id }) : "missing")}</b></div>`;
    }).join("");
    this.shell(`<div class="status-layout"><div class="eyebrow">System summary</div><div class="title">${escapeHtml(this._config.name || "Jarvis Status")}</div><div class="rows">${rows || '<div class="empty">Select entities in the visual editor.</div>'}</div></div>
      <style>.status-layout{min-height:150px;padding:20px}.title{font-size:20px;font-weight:650;margin:5px 0 14px}.rows{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:7px 16px}.row{display:grid;grid-template-columns:24px 1fr auto;gap:8px;align-items:center;padding:7px 0;border-bottom:1px solid rgba(32,216,255,.1)}.row ha-icon{--mdc-icon-size:18px;color:var(--j-accent)}.row span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row b{font:700 10px monospace;color:var(--j-green);text-transform:uppercase}.row b.bad{color:var(--j-red)}.empty{color:var(--secondary-text-color)}</style>`,
      { interactive: false });
  }
}

class JarvisVoiceCard extends JarvisBaseCard {
  static requiresEntity = false;
  static cardName = "Jarvis Voice";
  static getConfigForm() {
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { name: "description", selector: { text: {} } },
        { name: "pipeline_id", selector: { text: {} } },
        { name: "start_listening", selector: { boolean: {} } },
        { name: "compact", selector: { boolean: {} } },
      ],
    };
  }
  static getStubConfig() { return { title: "Ask Jarvis", description: "Open Assist and start listening", pipeline_id: "preferred", start_listening: true }; }
  getCardSize() { return this._config?.compact ? 3 : 4; }
  getGridOptions() {
    return {
      rows: this._config?.compact ? 3 : 4,
      columns: 12,
      min_rows: this._config?.compact ? 3 : 4,
      min_columns: 6,
    };
  }
  setConfig(config) {
    super.setConfig({ title: "Ask Jarvis", description: "Open Assist and start listening", pipeline_id: "preferred", start_listening: true, ...config });
  }
  render() {
    if (!this._config) return;
    const bars = Array.from({ length: 25 }, (_, i) => `<i style="--i:${i};--h:${16 + ((i * 19) % 62)}%"></i>`).join("");
    const card = this.shell(`<div class="voice-layout card-layout"><div class="copy"><div class="eyebrow">Voice interface</div><div class="voice-title">${escapeHtml(this._config.title)}</div><div class="description">${escapeHtml(this._config.description)}</div></div><div class="voice-node"><i class="node-corner tl"></i><i class="node-corner br"></i><div class="orb"><ha-icon icon="mdi:microphone"></ha-icon></div></div><div class="signal">${bars}</div><div class="hint">TAP TO SPEAK // CHANNEL READY</div></div>
      <style>.voice-layout{min-height:${this._config.compact ? "150px" : "204px"};padding:22px 28px;display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:22px;align-items:center}.voice-layout>.copy{min-width:0;overflow:hidden}.voice-title{font-size:clamp(22px,2vw,31px);font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.description{margin-top:9px;color:var(--secondary-text-color);font-size:12px;overflow:hidden;text-overflow:ellipsis}.voice-node{width:${this._config.compact ? "98px" : "130px"};height:${this._config.compact ? "98px" : "130px"};display:grid;place-items:center;position:relative;border:1px solid var(--j-line);clip-path:polygon(0 12px,12px 0,78% 0,100% 22%,100% calc(100% - 12px),calc(100% - 12px) 100%,22% 100%,0 78%);background:linear-gradient(145deg,rgba(32,216,255,.07),rgba(3,16,27,.7));box-shadow:inset 0 0 22px rgba(32,216,255,.08)}.node-corner{position:absolute;width:18px;height:18px;z-index:2}.node-corner.tl{left:5px;top:5px;border-left:2px solid var(--j-accent);border-top:2px solid var(--j-accent)}.node-corner.br{right:5px;bottom:5px;border-right:2px solid var(--j-accent);border-bottom:2px solid var(--j-accent)}.orb{width:${this._config.compact ? "60px" : "78px"};height:${this._config.compact ? "60px" : "78px"};display:grid;place-items:center;border:1px solid var(--j-accent);border-radius:50%;background:radial-gradient(circle,rgba(32,216,255,.28),rgba(3,16,27,.95) 62%);box-shadow:inset 0 0 24px rgba(32,216,255,.24),0 0 20px rgba(32,216,255,.22);position:relative}.orb:before,.orb:after{content:"";position:absolute;border-radius:50%;border:1px dashed rgba(32,216,255,.35);inset:-7px;animation:spin 16s linear infinite}.orb:after{inset:-13px;border-color:rgba(32,216,255,.14);border-left-color:var(--j-amber);animation-direction:reverse;animation-duration:24s}.orb ha-icon{--mdc-icon-size:34px;filter:drop-shadow(0 0 8px var(--j-accent))}.signal{height:68px;display:flex;align-items:center;gap:4px;min-width:0;overflow:hidden}.signal i{width:3px;flex:0 1 3px;height:var(--h);background:var(--j-accent);box-shadow:0 0 7px var(--j-accent);opacity:.55;animation:pulse 1.2s ease-in-out infinite alternate;animation-delay:calc(var(--i) * -55ms)}ha-card:hover .signal i,ha-card.engaged .signal i{opacity:1;animation-duration:.55s}.hint{grid-column:1/-1;text-align:right;font:700 9px monospace;letter-spacing:.15em;color:var(--j-accent)}@keyframes spin{to{transform:rotate(360deg)}}@keyframes pulse{from{transform:scaleY(.45)}to{transform:scaleY(1.2)}}@media(max-width:900px){.voice-layout{grid-template-columns:minmax(0,1fr) 88px minmax(72px,.7fr);padding:14px 16px;gap:10px}.voice-title{font-size:23px}.description{font-size:10px;margin-top:6px}.voice-node{width:86px;height:86px}.orb{width:52px;height:52px}.orb ha-icon{--mdc-icon-size:27px}.signal{height:44px;gap:2px}.signal i{width:2px;flex-basis:2px}.hint{display:none}}@container(max-width:520px){.voice-layout{grid-template-columns:minmax(0,1fr) 76px;padding:12px;gap:8px}.voice-title{font-size:18px}.description{font-size:9px;white-space:normal}.voice-node{width:72px;height:72px}.orb{width:46px;height:46px}.signal{grid-column:1/-1;height:24px}.hint{display:none}}@media(max-width:680px){.voice-layout{grid-template-columns:minmax(0,1fr) 82px;padding:14px}.voice-node{width:80px;height:80px}.signal{grid-column:1/-1;height:30px}.hint{display:none}}</style>`,
      { interactive: false, ariaLabel: this._config.title });
    card.classList.add("interactive");
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    const activate = () => {
      card.classList.add("engaged");
      setTimeout(() => card.classList.remove("engaged"), 3500);
      dispatchHassAction(this, {
        tap_action: { action: "assist", pipeline_id: this._config.pipeline_id, start_listening: this._config.start_listening !== false },
      });
    };
    card.addEventListener("click", activate);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activate();
      }
    });
  }
}

function multiEntityForm(extra = []) {
  return {
    schema: [
      { name: "name", selector: { text: {} } },
      { name: "icon", selector: { icon: {} } },
      { name: "entities", selector: { entity: { multiple: true } } },
      ...extra,
      { name: "accent", selector: { select: { options: ["auto", "cyan", "amber", "green", "red"] } } },
      { name: "layout", selector: { select: { options: ["compact", "standard", "wide"] } } },
      { type: "expandable", name: "actions", flatten: true, title: "Actions", schema: [
        { name: "tap_action", selector: { ui_action: {} } },
        { name: "hold_action", selector: { ui_action: {} } },
      ] },
    ],
  };
}

class JarvisRoomCard extends JarvisBaseCard {
  static requiresEntity = false;
  static cardName = "Jarvis Room Summary";
  static gridRows = 4;
  static getConfigForm() {
    return multiEntityForm([
      { name: "navigation_path", selector: { text: {} } },
      { name: "temperature_entity", selector: { entity: { domain: "sensor" } } },
    ]);
  }
  static getStubConfig(hass) {
    return { name: "Room", icon: "jarvis:room", entities: Object.keys(hass?.states || {}).slice(0, 4) };
  }
  render() {
    if (!this._config) return;
    const entities = (this._config.entities || []).slice(0, 8);
    const active = entities.filter((id) => isActive(stateObject(this._hass, id))).length;
    const unavailable = entities.filter((id) => isUnavailable(stateObject(this._hass, id))).length;
    const temperature = stateObject(this._hass, this._config.temperature_entity);
    const rows = entities.slice(0, 4).map((id) => {
      const state = stateObject(this._hass, id);
      return `<span><ha-icon icon="${escapeHtml(entityIcon(state, { entity: id }))}"></ha-icon>${escapeHtml(state?.attributes?.friendly_name || id)}</span>`;
    }).join("");
    this.shell(`<div class="j-layout room"><div class="j-header"><div class="icon-shell"><ha-icon icon="${escapeHtml(this._config.icon || "jarvis:room")}"></ha-icon></div><div class="copy"><div class="eyebrow">Room node</div><div class="name">${escapeHtml(this._config.name || "Room")}</div><div class="state">${active} active // ${unavailable} unavailable</div></div>${temperature ? `<div class="j-value">${escapeHtml(formatState(temperature, {}))}</div>` : ""}</div><div class="room-entities">${rows || "<span>Select room entities</span>"}</div></div>
      <style>.room{min-height:170px}.room-entities{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.room-entities span{display:flex;align-items:center;gap:7px;padding:7px;border:1px solid rgba(32,216,255,.12);font:600 9px monospace;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.room-entities ha-icon{--mdc-icon-size:17px;color:var(--j-accent)}@container(max-width:360px){.room-entities{grid-template-columns:1fr}.room-entities span:nth-child(n+4){display:none}}</style>`,
      { ariaLabel: this._config.name || "Room" });
    if (this._config.navigation_path) {
      this._config.tap_action = { action: "navigate", navigation_path: this._config.navigation_path };
    }
  }
}

class JarvisPresenceCard extends JarvisEntityCard {
  static cardName = "Jarvis Presence";
  static domains = ["person", "device_tracker", "binary_sensor"];
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const home = ["home", "on"].includes(state?.state);
    this.shell(`<div class="j-layout"><div class="j-header">${this.entityHeader("Presence channel")}<div class="j-value">${home ? "HOME" : "AWAY"}</div></div><div class="state">${escapeHtml(state?.attributes?.source_type || state?.attributes?.device_class || "Location status")}</div></div>`,
      { ariaLabel: friendlyName(state, this._config) });
  }
}

class JarvisWeatherCard extends JarvisEntityCard {
  static cardName = "Jarvis Weather";
  static domains = ["weather"];
  static gridRows = 6;
  static getConfigForm() {
    const form = commonForm(true);
    form.schema.splice(1, 0, {
      name: "forecast_days",
      selector: { number: { min: 3, max: 5, step: 1, mode: "slider" } },
    });
    return form;
  }
  getCardSize() { return 6; }
  getGridOptions() { return { rows: 6, columns: 6, min_rows: 6, min_columns: 3 }; }
  constructor() {
    super();
    this._forecastCard = undefined;
    this._forecastEntity = undefined;
    this._forecastMounting = false;
    this._weatherSignature = undefined;
  }
  set hass(value) {
    const nextState = stateObject(value, this._config?.entity);
    const attrs = nextState?.attributes || {};
    const nextSignature = JSON.stringify([
      nextState?.state, attrs.temperature, attrs.temperature_unit,
      attrs.humidity, attrs.wind_speed, attrs.wind_speed_unit,
      attrs.friendly_name, attrs.icon,
    ]);
    const stateChanged = nextSignature !== this._weatherSignature;
    this._hass = value;
    this._weatherSignature = nextSignature;
    if (!this.shadowRoot.querySelector(".forecast-host") || stateChanged) {
      this.render();
    } else if (this._forecastCard) {
      this._forecastCard.hass = value;
    } else {
      this._mountForecast();
    }
  }
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const attrs = state?.attributes || {};
    const facts = [["TEMP", attrs.temperature, attrs.temperature_unit], ["HUM", attrs.humidity, "%"], ["WIND", attrs.wind_speed, attrs.wind_speed_unit]];
    this.shell(`<div class="j-layout weather"><div class="j-header">${this.entityHeader("Weather channel")}<div class="j-value">${escapeHtml(String(state?.state || "unknown").toUpperCase())}</div></div><div class="facts">${facts.map(([label,value,unit]) => `<span><b>${label}</b>${escapeHtml(formatValue(value))}${unit ? ` ${escapeHtml(unit)}` : ""}</span>`).join("")}</div><div class="forecast-host" aria-label="Daily weather forecast"></div></div>
      <style>.weather{min-height:270px}.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.facts span{padding:9px;border:1px solid rgba(32,216,255,.13);font:700 11px monospace}.facts b{display:block;color:var(--secondary-text-color);font-size:8px;margin-bottom:4px}.forecast-host{min-height:118px;overflow:hidden;border-top:1px solid var(--j-line)}.forecast-host>*{display:block;--ha-card-border-width:0;--ha-card-border-radius:0;--ha-card-box-shadow:none;--ha-card-background:transparent}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
    this._forecastCard = undefined;
    this._mountForecast();
  }
  async _mountForecast() {
    const host = this.shadowRoot.querySelector(".forecast-host");
    if (!host || !this._hass || this._forecastMounting) return;
    this._forecastMounting = true;
    try {
      const helpers = await window.loadCardHelpers();
      if (!this.shadowRoot.contains(host)) return;
      const card = await helpers.createCardElement({
        type: "weather-forecast",
        entity: this._config.entity,
        show_current: false,
        show_forecast: true,
        forecast_type: "daily",
        forecast_slots: Math.min(5, Math.max(3, Number(this._config.forecast_days) || 5)),
      });
      host.replaceChildren(card);
      card.hass = this._hass;
      this._forecastCard = card;
      this._forecastEntity = this._config.entity;
    } finally {
      this._forecastMounting = false;
      if (!this._forecastCard && this.shadowRoot.querySelector(".forecast-host")) {
        queueMicrotask(() => this._mountForecast());
      }
    }
  }
}

class JarvisEnergyCard extends JarvisSensorCard {
  static cardName = "Jarvis Energy";
  static domains = ["sensor"];
  render() {
    if (!this._config) return;
    const state = this.cardState();
    this.shell(`<div class="j-layout"><div class="j-header">${this.entityHeader("Energy telemetry")}<div class="j-value">${escapeHtml(formatState(state, this._config))}</div></div><div class="energy-bar"><i style="width:${Math.min(100, Math.max(4, Number(state?.state) || 0))}%"></i></div></div>
      <style>.energy-bar{height:9px;border:1px solid var(--j-line);padding:2px}.energy-bar i{display:block;height:100%;background:var(--j-accent);box-shadow:0 0 12px var(--j-accent)}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
  }
}

class JarvisFanCard extends JarvisEntityCard {
  static cardName = "Jarvis Fan";
  static domains = ["fan"];
  static gridRows = 4;
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const percentage = state?.attributes?.percentage ?? 0;
    this.shell(`<div class="j-layout"><div class="j-header">${this.entityHeader("Airflow control")}<button class="${state?.state === "on" ? "primary" : ""}">POWER</button></div><div class="j-controls"><button data-pct="33">LOW</button><button data-pct="66">MED</button><button data-pct="100">HIGH</button></div><input aria-label="Fan percentage" type="range" min="0" max="100" value="${percentage}"></div>`,
      { ariaLabel: friendlyName(state, this._config) });
    const buttons = this.shadowRoot.querySelectorAll("button");
    buttons[0].addEventListener("click", () => this.call("fan", "toggle"));
    buttons.forEach((button) => button.dataset.pct && button.addEventListener("click", () => this.call("fan", "set_percentage", { percentage: Number(button.dataset.pct) })));
    this.shadowRoot.querySelector("input").addEventListener("change", (event) => this.call("fan", "set_percentage", { percentage: Number(event.target.value) }));
  }
}

class JarvisVacuumCard extends JarvisEntityCard {
  static cardName = "Jarvis Vacuum";
  static domains = ["vacuum"];
  static gridRows = 4;
  render() {
    if (!this._config) return;
    const state = this.cardState();
    this.shell(`<div class="j-layout"><div class="j-header">${this.entityHeader("Cleaning unit")}<div class="j-value">${escapeHtml(String(state?.state || "unknown").toUpperCase())}</div></div><div class="j-controls"><button data-service="start">START</button><button data-service="pause">PAUSE</button><button data-service="return_to_base">DOCK</button></div></div>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => this.call("vacuum", button.dataset.service)));
  }
}

class JarvisLockCard extends JarvisEntityCard {
  static cardName = "Jarvis Lock";
  static domains = ["lock"];
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const locked = state?.state === "locked";
    this.shell(`<div class="j-layout"><div class="j-header">${this.entityHeader("Access control")}<button class="${locked ? "primary" : ""}">${locked ? "UNLOCK" : "LOCK"}</button></div></div>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelector("button").addEventListener("click", () => this.call("lock", locked ? "unlock" : "lock"));
  }
}

class JarvisAlarmCard extends JarvisEntityCard {
  static cardName = "Jarvis Alarm Panel";
  static domains = ["alarm_control_panel"];
  static getConfigForm() {
    const form = commonForm(true);
    form.schema.splice(1, 0, { name: "code", selector: { text: { type: "password" } } });
    return form;
  }
  render() {
    if (!this._config) return;
    const state = this.cardState();
    this.shell(`<div class="j-layout"><div class="j-header">${this.entityHeader("Alarm control")}<div class="j-value">${escapeHtml(String(state?.state || "unknown").toUpperCase())}</div></div><div class="j-controls"><button data-service="alarm_disarm">DISARM</button><button data-service="alarm_arm_home">HOME</button><button data-service="alarm_arm_away">AWAY</button></div></div>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => this.call("alarm_control_panel", button.dataset.service, this._config.code ? { code: this._config.code } : {})));
  }
}

class JarvisSceneCard extends JarvisEntityCard {
  static cardName = "Jarvis Scene / Script";
  static domains = ["scene", "script"];
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const domain = entityDomain(this._config.entity);
    this.shell(`<div class="j-layout"><div class="j-header">${this.entityHeader("Routine command")}<button class="primary">RUN</button></div></div>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelector("button").addEventListener("click", () => this.call(domain, "turn_on"));
  }
}

class JarvisTimerCard extends JarvisEntityCard {
  static cardName = "Jarvis Timer";
  static domains = ["timer"];
  static gridRows = 4;
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const remaining = state?.attributes?.remaining || state?.attributes?.duration || "00:00:00";
    this.shell(`<div class="j-layout"><div class="j-header">${this.entityHeader("Timer channel")}<div class="j-value">${escapeHtml(remaining)}</div></div><div class="j-controls"><button data-service="start">START</button><button data-service="pause">PAUSE</button><button data-service="cancel">CANCEL</button></div></div>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => this.call("timer", button.dataset.service)));
  }
}

class JarvisMowerCard extends JarvisEntityCard {
  static cardName = "Jarvis Robot Mower";
  static domains = ["lawn_mower", "vacuum"];
  static gridRows = 4;
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const domain = entityDomain(this._config.entity);
    const services = domain === "lawn_mower" ? ["start_mowing", "pause", "dock"] : ["start", "pause", "return_to_base"];
    this.shell(`<div class="j-layout"><div class="j-header">${this.entityHeader("Robotic Mower")}<div class="j-value">${escapeHtml(String(state?.state || "unknown").toUpperCase())}</div></div><div class="j-controls">${services.map((service) => `<button data-service="${service}">${service.replaceAll("_", " ")}</button>`).join("")}</div></div>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => this.call(domain, button.dataset.service)));
  }
}

class JarvisWasherCard extends JarvisEntityCard {
  static cardName = "Jarvis Washing Machine";
  static domains = ["sensor", "switch"];
  static getConfigForm() {
    const form = commonForm(true);
    form.schema.splice(1, 0, { name: "progress_entity", selector: { entity: { domain: "sensor" } } });
    return form;
  }
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const progress = stateObject(this._hass, this._config.progress_entity);
    const value = Math.min(100, Math.max(0, Number(progress?.state) || 0));
    this.shell(`<div class="j-layout"><div class="j-header">${this.entityHeader("Laundry unit")}<div class="j-value">${progress ? `${formatValue(value)}%` : escapeHtml(String(state?.state || "unknown").toUpperCase())}</div></div><div class="energy-bar"><i style="width:${value}%"></i></div></div>
      <style>.energy-bar{height:9px;border:1px solid var(--j-line);padding:2px}.energy-bar i{display:block;height:100%;background:var(--j-accent)}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
  }
}

class JarvisSpotifyCard extends JarvisMediaCard {
  static cardName = "Jarvis Spotify";
  static domains = ["media_player"];
  static gridRows = 6;
  getCardSize() { return 6; }
  getGridOptions() { return { rows: 6, columns: 6, min_rows: 6, min_columns: 3 }; }
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const attrs = state?.attributes || {};
    const volume = Math.round((attrs.volume_level || 0) * 100);
    const picture = attrs.entity_picture ?
      (attrs.entity_picture.startsWith("http") ? attrs.entity_picture : this._hass?.hassUrl?.(attrs.entity_picture) || attrs.entity_picture) : "";
    const sources = attrs.source_list || [];
    this.shell(`<div class="spotify"><div class="art">${picture ? `<img src="${escapeHtml(picture)}" alt="">` : '<ha-icon icon="jarvis:spotify"></ha-icon>'}</div><div class="track"><div class="eyebrow">Spotify channel</div><div class="song">${escapeHtml(attrs.media_title || "Nothing playing")}</div><div class="artist">${escapeHtml(attrs.media_artist || attrs.media_album_name || friendlyName(state, this._config))}</div></div><div class="j-controls"><button data-service="media_previous_track">PREV</button><button class="primary" data-service="media_play_pause">${state?.state === "playing" ? "PAUSE" : "PLAY"}</button><button data-service="media_next_track">NEXT</button></div><label class="output"><span>SPEAKER OUTPUT</span><select aria-label="Speaker output">${sources.map((source) => `<option ${source === attrs.source ? "selected" : ""}>${escapeHtml(source)}</option>`).join("")}</select></label><label class="volume"><span>VOLUME</span><b>${volume}%</b><input aria-label="Volume" type="range" min="0" max="100" value="${volume}"></label></div>
      <style>.spotify{min-height:270px;padding:18px;display:grid;grid-template-columns:92px minmax(0,1fr);gap:14px}.art{width:92px;height:92px;display:grid;place-items:center;border:1px solid var(--j-line);background:rgba(32,216,255,.05);overflow:hidden}.art img{width:100%;height:100%;object-fit:cover}.art ha-icon{--mdc-icon-size:42px;color:var(--j-accent)}.track{min-width:0;align-self:center}.song{font-size:19px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.artist{margin-top:6px;color:var(--secondary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.j-controls,.output,.volume{grid-column:1/-1}.output,.volume{display:grid;grid-template-columns:1fr auto;gap:8px;font:700 9px monospace;color:var(--secondary-text-color)}select{grid-column:1/-1;min-height:36px;color:var(--primary-text-color);background:#061a28;border:1px solid var(--j-line);padding:0 8px}.volume b{color:var(--j-accent)}.volume input{grid-column:1/-1}@container(max-width:390px){.spotify{grid-template-columns:64px minmax(0,1fr);padding:14px}.art{width:64px;height:64px}.song{font-size:15px}}</style>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => this.call("media_player", button.dataset.service)));
    this.shadowRoot.querySelector("input").addEventListener("change", (event) => this.call("media_player", "volume_set", { volume_level: Number(event.target.value) / 100 }));
    this.shadowRoot.querySelector("select")?.addEventListener("change", (event) => this.call("media_player", "select_source", { source: event.target.value }));
  }
}

class JarvisEvChargerCard extends JarvisEntityCard {
  static cardName = "Jarvis EV Charger";
  static domains = ["switch", "sensor"];
  static getConfigForm() {
    const form = commonForm(true);
    form.schema.splice(1, 0, { name: "power_entity", selector: { entity: { domain: "sensor" } } });
    return form;
  }
  render() {
    if (!this._config) return;
    const state = this.cardState();
    const power = stateObject(this._hass, this._config.power_entity);
    const controllable = entityDomain(this._config.entity) === "switch";
    this.shell(`<div class="j-layout"><div class="j-header">${this.entityHeader("Vehicle charging")}<div class="j-value">${power ? escapeHtml(formatState(power, {})) : escapeHtml(String(state?.state || "unknown").toUpperCase())}</div></div>${controllable ? '<div class="j-controls"><button class="primary">TOGGLE CHARGE</button></div>' : ""}</div>`,
      { ariaLabel: friendlyName(state, this._config) });
    this.shadowRoot.querySelector("button")?.addEventListener("click", () => this.call("switch", "toggle"));
  }
}

class JarvisTileCard extends JarvisEntityCard {
  static cardName = "Jarvis Tile";
  render() {
    if (!this._config) return;
    const state = this.cardState();
    this.shell(`<div class="j-layout"><div class="j-header"><div class="icon-shell"><ha-icon icon="${escapeHtml(entityIcon(state, this._config))}"></ha-icon></div><div class="copy"><div class="eyebrow">Quick tile</div><div class="name">${escapeHtml(friendlyName(state, this._config))}</div></div><div class="j-value">${escapeHtml(formatState(state, this._config))}</div></div></div>`,
      { ariaLabel: friendlyName(state, this._config) });
  }
}

class JarvisCarCard extends JarvisBaseCard {
  static requiresEntity = false;
  static cardName = "Jarvis Car";
  static gridRows = 5;
  static getConfigForm() {
    return {
      schema: [
        { name: "name", selector: { text: {} } },
        { name: "icon", selector: { icon: {} } },
        { name: "location_entity", selector: { entity: {} } },
        { name: "battery_entity", selector: { entity: { domain: "sensor" } } },
        { name: "range_entity", selector: { entity: { domain: "sensor" } } },
        { name: "odometer_entity", selector: { entity: { domain: "sensor" } } },
        { name: "charging_entity", selector: { entity: {} } },
        { name: "lock_entity", selector: { entity: { domain: "lock" } } },
        { name: "accent", selector: { select: { options: ["cyan", "amber", "green", "red"] } } },
      ],
    };
  }
  static getStubConfig() { return { name: "Vehicle", icon: "jarvis:vehicle" }; }
  getCardSize() { return 5; }
  getGridOptions() { return { rows: 5, columns: 6, min_rows: 5, min_columns: 3 }; }
  render() {
    if (!this._config) return;
    const read = (key) => stateObject(this._hass, this._config[key]);
    const location = read("location_entity");
    const battery = read("battery_entity");
    const range = read("range_entity");
    const odometer = read("odometer_entity");
    const charging = read("charging_entity");
    const lock = read("lock_entity");
    const facts = [
      ["BATTERY", battery], ["RANGE", range], ["ODOMETER", odometer],
      ["CHARGING", charging], ["LOCK", lock],
    ].filter(([, state]) => state);
    this.shell(`<div class="j-layout car"><div class="j-header"><div class="icon-shell"><ha-icon icon="${escapeHtml(this._config.icon || "jarvis:vehicle")}"></ha-icon></div><div class="copy"><div class="eyebrow">Vehicle telemetry</div><div class="name">${escapeHtml(this._config.name || "Vehicle")}</div><div class="state">${escapeHtml(location?.state || "Location unavailable")}</div></div></div><div class="car-facts">${facts.map(([label,state]) => `<span><b>${label}</b>${escapeHtml(formatState(state, {}))}</span>`).join("") || "<span><b>SETUP</b>Select vehicle entities in the visual editor</span>"}</div></div>
      <style>.car{min-height:220px}.car-facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:8px}.car-facts span{padding:10px;border:1px solid rgba(32,216,255,.13);font:700 11px monospace;overflow:hidden;text-overflow:ellipsis}.car-facts b{display:block;color:var(--secondary-text-color);font-size:8px;margin-bottom:5px}</style>`,
      { interactive: false, ariaLabel: this._config.name || "Vehicle" });
  }
}

class JarvisMarkupCard extends JarvisBaseCard {
  static requiresEntity = false;
  static cardName = "Jarvis Markup";
  static getConfigForm() {
    return { schema: [
      { name: "title", selector: { text: {} } },
      { name: "content", required: true, selector: { text: { multiline: true } } },
      { name: "icon", selector: { icon: {} } },
      { name: "accent", selector: { select: { options: ["cyan", "amber", "green", "red"] } } },
    ] };
  }
  static getStubConfig() { return { title: "Jarvis briefing", content: "Home systems ready.", icon: "jarvis:core" }; }
  render() {
    if (!this._config) return;
    const content = escapeHtml(this._config.content || "").replaceAll("\n", "<br>");
    this.shell(`<div class="j-layout markup"><div class="j-header"><div class="icon-shell"><ha-icon icon="${escapeHtml(this._config.icon || "jarvis:core")}"></ha-icon></div><div class="copy"><div class="eyebrow">Information panel</div><div class="name">${escapeHtml(this._config.title || "Jarvis")}</div></div></div><div class="markup-body">${content}</div></div>
      <style>.markup{min-height:126px}.markup-body{color:var(--secondary-text-color);line-height:1.55;font-size:13px}</style>`,
      { interactive: false });
  }
}

class JarvisIconCatalogCard extends JarvisBaseCard {
  static requiresEntity = false;
  static cardName = "Jarvis Icon Catalog";
  static getConfigForm() { return { schema: [{ name: "filter", selector: { text: {} } }] }; }
  static getStubConfig() { return { filter: "" }; }
  render() {
    if (!this._config) return;
    const filter = String(this._config.filter || "").toLowerCase();
    const icons = Object.keys(ICON_ALIASES).filter((name) => name.includes(filter)).map((name) =>
      `<div class="icon-item"><ha-icon icon="jarvis:${name}"></ha-icon><span>jarvis:${name}</span></div>`).join("");
    this.shell(`<div class="catalog"><div class="eyebrow">Asset registry</div><div class="title">Jarvis Icon Catalog</div><div class="icons">${icons}</div></div>
      <style>.catalog{padding:20px}.title{font-size:20px;font-weight:650;margin:5px 0 16px}.icons{display:grid;grid-template-columns:repeat(auto-fill,minmax(145px,1fr));gap:8px}.icon-item{display:grid;grid-template-columns:28px 1fr;gap:8px;align-items:center;padding:9px;border:1px solid rgba(32,216,255,.13);background:rgba(32,216,255,.025)}.icon-item ha-icon{color:var(--j-accent)}.icon-item span{font:600 9px monospace;overflow:hidden;text-overflow:ellipsis}</style>`,
      { interactive: false });
  }
}

class JarvisCoverageCard extends JarvisBaseCard {
  static requiresEntity = false;
  static cardName = "Jarvis Entity Coverage";
  static getConfigForm() {
    return { schema: [{ name: "include_disabled", selector: { boolean: {} } }] };
  }
  static getStubConfig() { return {}; }
  render() {
    if (!this._config || !this._hass) return;
    const states = Object.values(this._hass.states || {});
    const domains = {};
    let mapped = 0;
    for (const state of states) {
      const domain = entityDomain(state.entity_id);
      domains[domain] = (domains[domain] || 0) + 1;
      if (DOMAIN_ICONS[domain] || DEVICE_CLASS_ICONS[state.attributes?.device_class]) mapped += 1;
    }
    const unmapped = Object.entries(domains).filter(([domain]) => !DOMAIN_ICONS[domain]).sort((a, b) => b[1] - a[1]);
    const coverage = states.length ? Math.round(mapped / states.length * 100) : 0;
    this.shell(`<div class="coverage"><div class="eyebrow">Local inventory audit</div><div class="headline"><strong>${coverage}%</strong><span>automatic Jarvis icon coverage<br>${mapped} of ${states.length} entities</span></div><div class="bar"><i style="width:${coverage}%"></i></div><div class="unmapped"><b>Fallback domains</b>${unmapped.length ? unmapped.map(([domain, count]) => `<span>${escapeHtml(domain)} <em>${count}</em></span>`).join("") : "<span>None</span>"}</div><p>No state leaves Home Assistant. Unmapped entities retain their existing icon.</p></div>
      <style>.coverage{padding:20px}.headline{display:flex;align-items:end;gap:14px;margin:7px 0 12px}.headline strong{font:700 34px monospace;color:var(--j-accent)}.headline span{font:600 10px monospace;color:var(--secondary-text-color);text-transform:uppercase}.bar{height:7px;border:1px solid var(--j-line);padding:2px}.bar i{display:block;height:100%;background:var(--j-accent);box-shadow:0 0 10px var(--j-accent)}.unmapped{margin-top:16px;display:flex;flex-wrap:wrap;gap:7px}.unmapped b{width:100%;font:700 9px monospace;text-transform:uppercase;color:var(--secondary-text-color)}.unmapped span{padding:5px 7px;border:1px solid rgba(32,216,255,.14);font:600 9px monospace}.unmapped em{color:var(--j-amber);font-style:normal}p{font-size:10px;color:var(--secondary-text-color);margin:14px 0 0}</style>`,
      { interactive: false });
  }
}

const CARD_DEFINITIONS = [
  ["jarvis-button-card", JarvisButtonCard, "Jarvis Button", "HUD action, navigation, scene or script button"],
  ["jarvis-action-card", JarvisActionCard, "Jarvis Action Card", "Backward-compatible Jarvis action button"],
  ["jarvis-entity-card", JarvisEntityCard, "Jarvis Entity", "Generic entity state card"],
  ["jarvis-light-card", JarvisLightCard, "Jarvis Light", "Light power and brightness control"],
  ["jarvis-switch-card", JarvisSwitchCard, "Jarvis Switch", "Switch, plug and relay control"],
  ["jarvis-slider-card", JarvisSliderCard, "Jarvis Slider", "Numeric, brightness, volume or position control"],
  ["jarvis-climate-card", JarvisClimateCard, "Jarvis Climate", "Climate state and target temperature"],
  ["jarvis-cover-card", JarvisCoverCard, "Jarvis Cover", "Cover movement and position"],
  ["jarvis-media-card", JarvisMediaCard, "Jarvis Media", "Playback and volume control"],
  ["jarvis-camera-card", JarvisCameraCard, "Jarvis Camera", "Camera view in the Jarvis HUD"],
  ["jarvis-sensor-card", JarvisSensorCard, "Jarvis Sensor", "Sensor telemetry and state"],
  ["jarvis-security-card", JarvisSecurityCard, "Jarvis Security", "Lock and safety entity display"],
  ["jarvis-status-card", JarvisStatusCard, "Jarvis Status", "Multi-entity system summary"],
  ["jarvis-voice-card", JarvisVoiceCard, "Jarvis Voice", "Animated Project Jarvis Assist launcher"],
  ["jarvis-room-card", JarvisRoomCard, "Jarvis Room Summary", "Room state, telemetry and navigation"],
  ["jarvis-presence-card", JarvisPresenceCard, "Jarvis Presence", "Person and presence status"],
  ["jarvis-weather-card", JarvisWeatherCard, "Jarvis Weather", "Current weather telemetry"],
  ["jarvis-energy-card", JarvisEnergyCard, "Jarvis Energy", "Power and energy telemetry"],
  ["jarvis-fan-card", JarvisFanCard, "Jarvis Fan", "Fan power and airflow control"],
  ["jarvis-vacuum-card", JarvisVacuumCard, "Jarvis Vacuum", "Robot vacuum controls"],
  ["jarvis-lock-card", JarvisLockCard, "Jarvis Lock", "Lock state and access control"],
  ["jarvis-alarm-card", JarvisAlarmCard, "Jarvis Alarm Panel", "Alarm arming controls"],
  ["jarvis-scene-card", JarvisSceneCard, "Jarvis Scene / Script", "Run a Home Assistant scene or script"],
  ["jarvis-timer-card", JarvisTimerCard, "Jarvis Timer", "Timer state and controls"],
  ["jarvis-mower-card", JarvisMowerCard, "Jarvis Robot Mower", "Robot mower state and controls"],
  ["jarvis-washer-card", JarvisWasherCard, "Jarvis Washing Machine", "Laundry state and progress"],
  ["jarvis-spotify-card", JarvisSpotifyCard, "Jarvis Spotify", "Spotify media playback controls"],
  ["jarvis-ev-charger-card", JarvisEvChargerCard, "Jarvis EV Charger", "EV charging state and power"],
  ["jarvis-tile-card", JarvisTileCard, "Jarvis Tile", "Compact universal entity tile"],
  ["jarvis-markup-card", JarvisMarkupCard, "Jarvis Markup", "Editable Jarvis information panel"],
  ["jarvis-car-card", JarvisCarCard, "Jarvis Car", "Vehicle location, battery, range and status"],
  ["jarvis-icon-catalog-card", JarvisIconCatalogCard, "Jarvis Icon Catalog", "Browse every bundled Jarvis icon"],
  ["jarvis-coverage-card", JarvisCoverageCard, "Jarvis Entity Coverage", "Audit automatic icon coverage locally"],
];

const CARD_DOMAINS = new Map([
  [JarvisLightCard, ["light"]], [JarvisSwitchCard, ["switch", "input_boolean"]],
  [JarvisClimateCard, ["climate"]], [JarvisCoverCard, ["cover"]],
  [JarvisMediaCard, ["media_player"]], [JarvisCameraCard, ["camera"]],
  [JarvisSensorCard, ["sensor", "binary_sensor", "sun", "weather"]],
  [JarvisSecurityCard, ["lock", "alarm_control_panel"]],
  [JarvisPresenceCard, ["person", "device_tracker", "binary_sensor"]],
  [JarvisWeatherCard, ["weather"]], [JarvisEnergyCard, ["sensor"]],
  [JarvisFanCard, ["fan"]], [JarvisVacuumCard, ["vacuum"]],
  [JarvisLockCard, ["lock"]], [JarvisAlarmCard, ["alarm_control_panel"]],
  [JarvisSceneCard, ["scene", "script"]], [JarvisTimerCard, ["timer"]],
  [JarvisMowerCard, ["lawn_mower", "vacuum"]],
  [JarvisWasherCard, ["sensor", "switch"]],
  [JarvisSpotifyCard, ["media_player"]],
  [JarvisEvChargerCard, ["switch", "sensor"]],
]);

window.customCards = window.customCards || [];
for (const [tag, klass, name, description] of CARD_DEFINITIONS) {
  if (!customElements.get(tag)) customElements.define(tag, klass);
  if (!window.customCards.some((card) => card.type === tag)) {
    const domains = CARD_DOMAINS.get(klass);
    window.customCards.push({
      type: tag, name, description, preview: !klass.requiresEntity,
      documentationURL: "https://github.com/bennyseather/Project-Jarvis_HA",
      ...(domains ? {
        getEntitySuggestion: (_hass, entityId) =>
          domains.includes(entityDomain(entityId))
            ? { config: { type: `custom:${tag}`, entity: entityId } }
            : null,
      } : {}),
    });
  }
}

console.info(
  `%c JARVIS UI %c ${JARVIS_UI_VERSION} `,
  "background:#20d8ff;color:#00131a;font-weight:800;padding:3px 7px",
  "background:#03101b;color:#9dd8e8;padding:3px 7px",
);
