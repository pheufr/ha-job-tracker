class RHSoundboardCard extends HTMLElement {
  constructor() {
    super();
    this._connected = false;
    this._busy = false;
    this._selectedTarget = "";
    this._playMode = "connected";
    this._sessionState = null;
  }

  setConfig(config) {
    const safeConfig = config && typeof config === "object" ? config : {};
    this._config = {
      ...safeConfig,
      clips: Array.isArray(safeConfig.clips)
        ? safeConfig.clips.map((clip) => ({ ...clip }))
        : [],
    };
    this._columns = Number(this._config.columns || 4);

    const configuredMode = String(this._config.default_mode || "connected").toLowerCase();
    this._playMode = configuredMode === "direct" ? "direct" : "connected";
  }

  set hass(hass) {
    this._hass = hass;
    this._syncSessionState();
    if (!this._selectedTarget) {
      this._selectedTarget = this._config.target || "";
    }
    this._render();
  }

  _syncSessionState() {
    const state = this._hass?.states?.["sensor.rh_soundboard_session"];
    if (!state) {
      this._sessionState = null;
      return;
    }

    const attrs = state.attributes || {};
    this._sessionState = attrs;

    const activeTarget = attrs.active_target || "";
    if (!this._selectedTarget && activeTarget) {
      this._selectedTarget = activeTarget;
    }

    const modeByTarget = attrs.mode_by_target || {};
    const stateMode = modeByTarget[this._selectedTarget] || modeByTarget[activeTarget] || "";
    if (stateMode === "connected" || stateMode === "direct") {
      this._playMode = stateMode;
    }

    const selected = this._selectedTarget || activeTarget;
    this._connected = Boolean(attrs.connected) && Boolean(selected) && activeTarget === selected;
  }

  _title() {
    if (this._config.title === undefined) {
      return "RH Soundboard";
    }
    return this._config.title;
  }

  _renderHeader() {
    const title = this._title();
    return title === "" ? "" : ` header="${title}"`;
  }

  _mediaPlayers() {
    const players = [];
    for (const [entityId, state] of Object.entries(this._hass.states || {})) {
      if (!entityId.startsWith("media_player.")) {
        continue;
      }
      players.push({
        entityId,
        name: state.attributes?.friendly_name || entityId,
        available: state.state !== "unavailable",
      });
    }
    players.sort((a, b) => a.name.localeCompare(b.name));
    return players;
  }

  _clips() {
    return this._config.clips
      .map((clip, index) => {
        const media = typeof clip?.media === "string" ? clip.media.trim() : "";
        if (!media) {
          return null;
        }
        const sourceLabel = media.replace("media-source://", "");
        const mediaTypeRaw = String(clip.type || clip.media_type || "audio").trim().toLowerCase();
        const mediaType = mediaTypeRaw || "audio";
        return {
          id: clip.id || `clip_${index}`,
          label: clip.label || clip.name || `Clip ${index + 1}`,
          icon: clip.icon || "mdi:music-note",
          media,
          mediaType,
          sourceLabel,
          fgColor: typeof clip.fg_color === "string" ? clip.fg_color : (typeof clip.text_color === "string" ? clip.text_color : ""),
          bgColor: typeof clip.bg_color === "string" ? clip.bg_color : (typeof clip.background_color === "string" ? clip.background_color : ""),
        };
      })
      .filter((clip) => clip !== null);
  }

  async _call(service, data = {}) {
    await this._hass.callService("raven_house_tools", service, data);
  }

  _serviceDef(domain, service) {
    return this._hass?.services?.[domain]?.[service] || null;
  }

  _hasService(domain, service) {
    return Boolean(this._serviceDef(domain, service));
  }

  _serviceHasField(domain, service, fieldName) {
    const def = this._serviceDef(domain, service);
    if (!def || !def.fields || typeof def.fields !== "object") {
      return false;
    }
    return Object.prototype.hasOwnProperty.call(def.fields, fieldName);
  }

  _statusText() {
    if (!this._selectedTarget) {
      return "Choose a media player";
    }
    if (this._busy) {
      return "Working...";
    }
    if (this._sessionState) {
      const pending = Number(this._sessionState.pending_requests || 0);
      if (pending > 0) {
        return `Queued: ${pending} request(s)`;
      }
    }
    return this._connected
      ? `Connected to ${this._selectedTarget}`
      : `Ready (${this._playMode}): ${this._selectedTarget}`;
  }

  _clipStatusText(clip) {
    if (this._busy) {
      return "Sending...";
    }
    const lastClip = String(this._sessionState?.last_clip || "");
    if (lastClip && lastClip === clip.media) {
      return "Last triggered";
    }
    return this._connected ? "Live" : "Ready";
  }

  _optionInputsDisabled() {
    return this._connected || this._busy;
  }

  async _toggleConnection() {
    if (this._busy) {
      return;
    }
    const target = this._selectedTarget || this._config.target || "";
    if (!target) {
      return;
    }

    this._busy = true;
    this._render();

    try {
      if (this._connected) {
        await this._call("soundboard_disconnect", { entity_id: target });
        this._connected = false;
      } else {
        if (this._hasService("raven_house_tools", "soundboard_set_mode")) {
          await this._call("soundboard_set_mode", {
            entity_id: target,
            mode: this._playMode,
          });
        }
        await this._call("soundboard_connect", {
          entity_id: target,
          dead_air_media: this._config.dead_air_media || "",
        });
        this._connected = true;
      }
    } finally {
      this._busy = false;
      this._render();
    }
  }

  async _playClip(clip) {
    if (this._busy) {
      return;
    }
    const target = this._selectedTarget || this._config.target || "";
    if (!target) {
      return;
    }

    const payload = {
      entity_id: target,
      media: clip.media,
      connected: this._playMode === "connected",
      dead_air_media: this._config.dead_air_media || "",
    };

    if (this._serviceHasField("raven_house_tools", "soundboard_play_clip", "mode")) {
      payload.mode = this._playMode;
    }

    await this._call("soundboard_play_clip", payload);
  }

  _renderModeSelector() {
    if (this._config.show_mode_selector === false) {
      return "";
    }

    const disabledAttr = this._optionInputsDisabled() ? "disabled" : "";

    return `
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
        <label for="rh-soundboard-mode" style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.7;">Mode</label>
        <select id="rh-soundboard-mode" ${disabledAttr} style="padding:8px 10px;border-radius:8px;min-width:180px;">
          <option value="connected" ${this._playMode === "connected" ? "selected" : ""}>Connected session</option>
          <option value="direct" ${this._playMode === "direct" ? "selected" : ""}>Direct play</option>
        </select>
      </div>
    `;
  }

  _renderTargetSelector(players) {
    const allowTargetSwitch = this._config.allow_target_switch !== false;
    if (!allowTargetSwitch) {
      return "";
    }

    const disabledAttr = this._optionInputsDisabled() ? "disabled" : "";

    const options = players
      .map((player) => {
        const selected = player.entityId === this._selectedTarget ? "selected" : "";
        return `<option value="${player.entityId}" ${selected}>${player.name}</option>`;
      })
      .join("");

    return `
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
        <label for="rh-soundboard-target" style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.7;">Target</label>
        <select id="rh-soundboard-target" ${disabledAttr} style="flex:1;min-width:220px;padding:8px 10px;border-radius:8px;">
          <option value="">Select media player</option>
          ${options}
        </select>
      </div>
    `;
  }

  _render() {
    if (!this._hass) {
      return;
    }

    const players = this._mediaPlayers();
    const clips = this._clips();
    const columns = Math.max(1, this._columns);
    const buttonLabel = this._connected ? "Disconnect" : "Connect";
    const optionsLocked = this._optionInputsDisabled();

    this.innerHTML = `
      <ha-card${this._renderHeader()}>
        <div style="padding:16px;display:grid;gap:14px;">
          <div style="display:grid;gap:10px;padding:12px;border-radius:12px;border:1px solid rgba(128,128,128,0.24);background:rgba(128,128,128,0.06);">
            ${this._renderTargetSelector(players)}
            ${this._renderModeSelector()}
            <div style="display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;">
              <button id="rh-soundboard-connect" style="padding:10px 14px;border:none;border-radius:10px;cursor:pointer;font-weight:600;">
                ${buttonLabel}
              </button>
              <div style="font-size:12px;opacity:0.72;">${optionsLocked ? "Options locked while connected" : "Options unlocked"}</div>
            </div>
            <div style="font-size:12px;opacity:0.86;line-height:1.3;">Status: ${this._statusText()}</div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(${columns}, minmax(0, 1fr));gap:10px;">
            ${
              clips
                .map((clip) => {
                  const styleParts = [
                    "min-height:96px",
                    "padding:10px",
                    "border:none",
                    "border-radius:12px",
                    "cursor:pointer",
                    "display:flex",
                    "flex-direction:column",
                    "align-items:flex-start",
                    "justify-content:flex-start",
                    "gap:6px",
                    "font-weight:600",
                  ];
                  if (clip.bgColor) {
                    styleParts.push(`background:${clip.bgColor}`);
                  }
                  if (clip.fgColor) {
                    styleParts.push(`color:${clip.fgColor}`);
                  }
                  const style = styleParts.join(";");
                  return `
              <button
                class="rh-soundboard-clip"
                data-id="${clip.id}"
                style="${style}"
              >
                <div style="display:flex;align-items:center;gap:8px;width:100%;">
                  <ha-icon icon="${clip.icon}"></ha-icon>
                  <span style="font-size:13px;line-height:1.2;">${clip.label}</span>
                </div>
                <div style="font-size:11px;opacity:0.78;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:100%;">${clip.sourceLabel} • ${clip.mediaType}</div>
                <div style="font-size:11px;opacity:0.72;line-height:1.2;">${this._clipStatusText(clip)}</div>
              </button>
            `;
                })
                .join("") || '<div style="grid-column:1 / -1;opacity:0.7;">No clips configured</div>'
            }
          </div>
        </div>
      </ha-card>
    `;

    this._attachHandlers(clips);
  }

  _attachHandlers(clips) {
    const connect = this.querySelector("#rh-soundboard-connect");
    if (connect) {
      connect.onclick = () => this._toggleConnection();
    }

    const targetSelect = this.querySelector("#rh-soundboard-target");
    if (targetSelect) {
      targetSelect.onchange = async (event) => {
        this._selectedTarget = event.currentTarget.value || "";
        if (this._selectedTarget) {
          await this._call("soundboard_set_target", { entity_id: this._selectedTarget });
          if (this._hasService("raven_house_tools", "soundboard_set_mode")) {
            await this._call("soundboard_set_mode", {
              entity_id: this._selectedTarget,
              mode: this._playMode,
            });
          }
        }
        this._render();
      };
    }

    const modeSelect = this.querySelector("#rh-soundboard-mode");
    if (modeSelect) {
      modeSelect.onchange = async (event) => {
        const nextMode = String(event.currentTarget.value || "connected").toLowerCase();
        this._playMode = nextMode === "direct" ? "direct" : "connected";
        if (this._selectedTarget && this._hasService("raven_house_tools", "soundboard_set_mode")) {
          await this._call("soundboard_set_mode", {
            entity_id: this._selectedTarget,
            mode: this._playMode,
          });
        }
        this._render();
      };
    }

    const clipById = new Map(clips.map((clip) => [clip.id, clip]));
    this.querySelectorAll(".rh-soundboard-clip").forEach((button) => {
      button.onclick = async (event) => {
        const id = event.currentTarget.dataset.id;
        const clip = clipById.get(id);
        if (!clip) {
          return;
        }
        await this._playClip(clip);
      };
    });
  }

  getCardSize() {
    const clips = this._clips();
    const rows = Math.ceil(clips.length / Math.max(1, this._columns));
    return Math.max(3, rows + 3);
  }
}

if (!customElements.get("rh-soundboard-card")) {
  customElements.define("rh-soundboard-card", RHSoundboardCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.find((card) => card.type === "rh-soundboard-card")) {
  window.customCards.push({
    type: "rh-soundboard-card",
    name: "RH Soundboard Card",
    description: "Grid soundboard with connect/disconnect session playback",
  });
}
