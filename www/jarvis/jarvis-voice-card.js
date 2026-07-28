const JARVIS_UI_VERSION = "0.8.2";

function dispatchHassAction(element, config, action = "tap") {
  const event = new Event("hass-action", {
    bubbles: true,
    composed: true,
  });
  event.detail = { config, action };
  element.dispatchEvent(event);
}

function setText(root, selector, value) {
  const target = root.querySelector(selector);
  if (target) {
    target.textContent = value;
  }
}

class JarvisVoiceCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._engagedTimer = undefined;
  }

  setConfig(config) {
    this._config = {
      title: "Ask Jarvis",
      description: "Open Project Jarvis and start listening",
      pipeline_id: "preferred",
      start_listening: true,
      ...config,
    };
    this._render();
  }

  set hass(value) {
    this._hass = value;
  }

  disconnectedCallback() {
    if (this._engagedTimer) {
      clearTimeout(this._engagedTimer);
    }
  }

  getCardSize() {
    return this._config?.compact ? 3 : 4;
  }

  getGridOptions() {
    return {
      rows: this._config?.compact ? 3 : 4,
      columns: 12,
      min_rows: 3,
      min_columns: 6,
    };
  }

  static getStubConfig() {
    return {
      title: "Ask Jarvis",
      description: "Open Project Jarvis and start listening",
      pipeline_id: "preferred",
      start_listening: true,
    };
  }

  _activate() {
    const card = this.shadowRoot.querySelector("ha-card");
    card?.classList.add("engaged");
    if (this._engagedTimer) {
      clearTimeout(this._engagedTimer);
    }
    this._engagedTimer = setTimeout(
      () => card?.classList.remove("engaged"),
      4000,
    );
    dispatchHassAction(this, {
      tap_action: {
        action: "assist",
        pipeline_id: this._config.pipeline_id,
        start_listening: this._config.start_listening !== false,
      },
    });
  }

  _render() {
    if (!this._config) {
      return;
    }
    const bars = Array.from(
      { length: 19 },
      (_, index) =>
        `<i style="--bar:${index};--height:${
          18 + ((index * 17) % 42)
        }%"></i>`,
    ).join("");
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          --jarvis-cyan: var(--primary-color, #36bffa);
          --jarvis-amber: var(--accent-color, #f5a340);
          --jarvis-surface: rgba(5, 20, 34, 0.92);
        }
        ha-card {
          position: relative;
          min-height: ${this._config.compact ? "146px" : "202px"};
          overflow: hidden;
          border: 1px solid color-mix(in srgb, var(--jarvis-cyan) 45%, transparent);
          border-radius: 22px;
          background:
            radial-gradient(circle at 82% 50%, rgba(54, 191, 250, 0.16), transparent 28%),
            linear-gradient(135deg, rgba(5, 17, 31, 0.97), var(--jarvis-surface));
          box-shadow:
            inset 0 0 32px rgba(54, 191, 250, 0.06),
            0 16px 36px rgba(0, 0, 0, 0.24);
          color: var(--primary-text-color, #eaf7ff);
          cursor: pointer;
          isolation: isolate;
          transition:
            transform 180ms ease,
            border-color 180ms ease,
            box-shadow 180ms ease;
        }
        ha-card::before,
        ha-card::after {
          content: "";
          position: absolute;
          pointer-events: none;
          z-index: -1;
        }
        ha-card::before {
          inset: 0;
          background:
            linear-gradient(90deg, transparent 0 8%, rgba(54, 191, 250, 0.08) 8.2%, transparent 8.5%),
            linear-gradient(0deg, transparent 0 76%, rgba(54, 191, 250, 0.06) 76.3%, transparent 76.6%);
          opacity: 0.8;
        }
        ha-card::after {
          width: 180px;
          height: 180px;
          right: -72px;
          top: -88px;
          border: 1px solid rgba(54, 191, 250, 0.16);
          border-radius: 50%;
          box-shadow:
            0 0 0 24px rgba(54, 191, 250, 0.025),
            0 0 0 52px rgba(54, 191, 250, 0.018);
        }
        ha-card:hover,
        ha-card:focus-visible,
        ha-card.engaged {
          transform: translateY(-2px);
          border-color: color-mix(in srgb, var(--jarvis-cyan) 78%, white 8%);
          box-shadow:
            inset 0 0 42px rgba(54, 191, 250, 0.10),
            0 0 26px rgba(54, 191, 250, 0.16),
            0 18px 40px rgba(0, 0, 0, 0.28);
          outline: none;
        }
        .layout {
          min-height: inherit;
          display: grid;
          grid-template-columns: minmax(150px, 1fr) auto minmax(190px, 1.15fr);
          align-items: center;
          gap: 22px;
          padding: 22px 28px;
        }
        .copy {
          min-width: 0;
        }
        .eyebrow {
          color: var(--jarvis-cyan);
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.22em;
          text-transform: uppercase;
          margin-bottom: 9px;
        }
        .title {
          font-size: clamp(22px, 2vw, 32px);
          line-height: 1.05;
          font-weight: 600;
          letter-spacing: 0.015em;
        }
        .description {
          color: var(--secondary-text-color, #91b7cb);
          font-size: 13px;
          line-height: 1.45;
          margin-top: 10px;
          max-width: 280px;
        }
        .orb {
          position: relative;
          width: ${this._config.compact ? "84px" : "112px"};
          height: ${this._config.compact ? "84px" : "112px"};
          display: grid;
          place-items: center;
          border: 1px solid rgba(54, 191, 250, 0.68);
          border-radius: 50%;
          background:
            radial-gradient(circle, rgba(54, 191, 250, 0.30), rgba(5, 22, 38, 0.92) 58%),
            var(--jarvis-surface);
          box-shadow:
            inset 0 0 24px rgba(54, 191, 250, 0.24),
            0 0 24px rgba(54, 191, 250, 0.22);
        }
        .orb::before,
        .orb::after {
          content: "";
          position: absolute;
          border-radius: 50%;
          border: 1px solid rgba(54, 191, 250, 0.22);
        }
        .orb::before {
          inset: -10px;
          border-style: dashed;
          animation: jarvis-spin 18s linear infinite;
        }
        .orb::after {
          inset: -19px;
          border-color: rgba(54, 191, 250, 0.10);
          border-left-color: var(--jarvis-amber);
          animation: jarvis-spin 28s linear infinite reverse;
        }
        .orb ha-icon {
          --mdc-icon-size: ${this._config.compact ? "35px" : "46px"};
          color: #eaf7ff;
          filter: drop-shadow(0 0 9px rgba(54, 191, 250, 0.76));
        }
        .signal {
          height: 74px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 4px;
          mask-image: linear-gradient(90deg, transparent, black 12%, black 88%, transparent);
        }
        .signal i {
          width: 3px;
          height: var(--height);
          min-height: 8px;
          border-radius: 3px;
          background: linear-gradient(180deg, #93e4ff, var(--jarvis-cyan));
          box-shadow: 0 0 7px rgba(54, 191, 250, 0.55);
          opacity: 0.54;
          transform-origin: center;
          animation: jarvis-signal 1.4s ease-in-out infinite alternate;
          animation-delay: calc(var(--bar) * -70ms);
        }
        ha-card:hover .signal i,
        ha-card.engaged .signal i {
          opacity: 1;
          animation-duration: 620ms;
        }
        .hint {
          margin-top: 10px;
          color: var(--secondary-text-color, #91b7cb);
          text-align: center;
          font-size: 10px;
          letter-spacing: 0.16em;
          text-transform: uppercase;
        }
        @keyframes jarvis-spin {
          to { transform: rotate(360deg); }
        }
        @keyframes jarvis-signal {
          from { transform: scaleY(0.48); }
          to { transform: scaleY(1.18); }
        }
        @media (max-width: 680px) {
          .layout {
            grid-template-columns: 1fr auto;
            padding: 20px;
          }
          .signal-wrap {
            grid-column: 1 / -1;
          }
          .signal {
            height: 40px;
          }
          .hint {
            display: none;
          }
        }
        @media (prefers-reduced-motion: reduce) {
          ha-card,
          .orb::before,
          .orb::after,
          .signal i {
            animation: none !important;
            transition: none !important;
          }
        }
      </style>
      <ha-card role="button" tabindex="0">
        <div class="layout">
          <div class="copy">
            <div class="eyebrow">Voice interface</div>
            <div class="title"></div>
            <div class="description"></div>
          </div>
          <div class="orb" aria-hidden="true">
            <ha-icon icon="mdi:microphone"></ha-icon>
          </div>
          <div class="signal-wrap" aria-hidden="true">
            <div class="signal">${bars}</div>
            <div class="hint">Tap to speak</div>
          </div>
        </div>
      </ha-card>
    `;
    const card = this.shadowRoot.querySelector("ha-card");
    card.setAttribute("aria-label", this._config.title);
    card.addEventListener("click", () => this._activate());
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        this._activate();
      }
    });
    setText(this.shadowRoot, ".title", this._config.title);
    setText(this.shadowRoot, ".description", this._config.description);
  }
}

class JarvisActionCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    if (!config.label) {
      throw new Error("Jarvis action card requires a label");
    }
    this._config = {
      icon: "mdi:chevron-right",
      description: "",
      color: "cyan",
      tap_action: { action: "none" },
      ...config,
    };
    this._render();
  }

  set hass(value) {
    this._hass = value;
  }

  getCardSize() {
    return 2;
  }

  getGridOptions() {
    return { rows: 2, columns: 6, min_rows: 2, min_columns: 3 };
  }

  _render() {
    const isAmber = this._config.color === "amber";
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          --action-color: ${isAmber ? "#f5a340" : "var(--primary-color, #36bffa)"};
        }
        ha-card {
          min-height: 104px;
          position: relative;
          overflow: hidden;
          display: grid;
          grid-template-columns: 48px 1fr 22px;
          align-items: center;
          gap: 14px;
          padding: 14px 18px;
          box-sizing: border-box;
          border: 1px solid color-mix(in srgb, var(--action-color) 38%, transparent);
          border-radius: 17px;
          background:
            linear-gradient(115deg, rgba(8, 27, 43, 0.96), rgba(5, 18, 31, 0.94));
          color: var(--primary-text-color, #eaf7ff);
          cursor: pointer;
          transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
        }
        ha-card::after {
          content: "";
          position: absolute;
          left: 18px;
          right: 18px;
          bottom: 0;
          height: 1px;
          background: linear-gradient(90deg, transparent, var(--action-color), transparent);
          opacity: 0.7;
        }
        ha-card:hover,
        ha-card:focus-visible {
          transform: translateY(-2px);
          border-color: color-mix(in srgb, var(--action-color) 76%, white 6%);
          box-shadow: 0 0 22px color-mix(in srgb, var(--action-color) 16%, transparent);
          outline: none;
        }
        .icon {
          width: 44px;
          height: 44px;
          display: grid;
          place-items: center;
          border-radius: 50%;
          color: var(--action-color);
          background: color-mix(in srgb, var(--action-color) 12%, transparent);
          border: 1px solid color-mix(in srgb, var(--action-color) 34%, transparent);
          box-shadow: inset 0 0 16px color-mix(in srgb, var(--action-color) 11%, transparent);
        }
        .icon ha-icon {
          --mdc-icon-size: 24px;
        }
        .label {
          font-size: 15px;
          font-weight: 600;
          line-height: 1.2;
        }
        .description {
          margin-top: 5px;
          color: var(--secondary-text-color, #91b7cb);
          font-size: 11px;
          line-height: 1.3;
        }
        .chevron {
          color: var(--action-color);
          opacity: 0.72;
        }
        @media (prefers-reduced-motion: reduce) {
          ha-card { transition: none !important; }
        }
      </style>
      <ha-card role="button" tabindex="0">
        <div class="icon"><ha-icon></ha-icon></div>
        <div>
          <div class="label"></div>
          <div class="description"></div>
        </div>
        <ha-icon class="chevron" icon="mdi:chevron-right"></ha-icon>
      </ha-card>
    `;
    const card = this.shadowRoot.querySelector("ha-card");
    const icon = this.shadowRoot.querySelector(".icon ha-icon");
    card.setAttribute("aria-label", this._config.label);
    icon.setAttribute("icon", this._config.icon);
    setText(this.shadowRoot, ".label", this._config.label);
    setText(this.shadowRoot, ".description", this._config.description);
    card.addEventListener("click", () =>
      dispatchHassAction(this, this._config),
    );
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        dispatchHassAction(this, this._config);
      }
    });
  }
}

if (!customElements.get("jarvis-voice-card")) {
  customElements.define("jarvis-voice-card", JarvisVoiceCard);
}
if (!customElements.get("jarvis-action-card")) {
  customElements.define("jarvis-action-card", JarvisActionCard);
}

window.customCards = window.customCards || [];
window.customCards.push(
  {
    type: "jarvis-voice-card",
    name: "Jarvis Voice Card",
    description: "Animated Project Jarvis Assist launcher",
    preview: true,
  },
  {
    type: "jarvis-action-card",
    name: "Jarvis Action Card",
    description: "Project Jarvis navigation and action button",
    preview: false,
  },
);

console.info(
  `%c JARVIS UI %c ${JARVIS_UI_VERSION} `,
  "background:#36bffa;color:#06111d;font-weight:700;padding:3px 6px",
  "background:#06111d;color:#91b7cb;padding:3px 6px",
);
