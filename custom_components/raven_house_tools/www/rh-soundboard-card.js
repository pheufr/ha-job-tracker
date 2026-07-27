class RHSoundboardCard extends HTMLElement {
  constructor() {
    super();
    this._connected = false;
    this._busy = false;
    this._selectedTarget = "";
  }

  setConfig(config) {
    this._config = config || {};
    this._columns = Number(this._config.columns || 4);

    if (!Array.isArray(this._config.clips)) {
      this._config.clips = [];
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._selectedTarget) {
      this._selectedTarget = this._config.target || "";
    }
    this._render();
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
        return {
          id: clip.id || `clip_${index}`,
          label: clip.label || clip.name || `Clip ${index + 1}`,
          icon: clip.icon || "mdi:music-note",
          media,
        };
      })
      .filter((clip) => clip !== null);
  }

  async _call(service, data = {}) {
    await this._hass.callService("raven_house_tools", service, data);
  }

  _statusText() {
    if (!this._selectedTarget) {
      return "Choose a media player";
    }
    if (this._busy) {
      return "Working...";
    }
    return this._connected ? `Connected to ${this._selectedTarget}` : `Ready: ${this._selectedTarget}`;
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

    await this._call("soundboard_play_clip", {
      entity_id: target,
      media: clip.media,
      connected: this._connected,
      dead_air_media: this._config.dead_air_media || "",
    });
  }

  _renderTargetSelector(players) {
    const allowTargetSwitch = this._config.allow_target_switch !== false;
    if (!allowTargetSwitch) {
      return "";
    }

    const options = players
      .map((player) => {
        const selected = player.entityId === this._selectedTarget ? "selected" : "";
        return `<option value="${player.entityId}" ${selected}>${player.name}</option>`;
      })
      .join("");

    return `
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
        <label for="rh-soundboard-target" style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.7;">Target</label>
        <select id="rh-soundboard-target" style="flex:1;min-width:220px;padding:8px 10px;border-radius:8px;">
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

    this.innerHTML = `
      <ha-card${this._renderHeader()}>
        <div style="padding:16px;display:grid;gap:14px;">
          ${this._renderTargetSelector(players)}
          <div style="display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;">
            <button id="rh-soundboard-connect" style="padding:10px 14px;border:none;border-radius:10px;cursor:pointer;font-weight:600;">
              ${buttonLabel}
            </button>
            <div style="font-size:12px;opacity:0.75;">${this._statusText()}</div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(${columns}, minmax(0, 1fr));gap:10px;">
            ${
              clips
                .map(
                  (clip) => `
              <button
                class="rh-soundboard-clip"
                data-id="${clip.id}"
                style="min-height:74px;padding:10px;border:none;border-radius:12px;cursor:pointer;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;font-weight:600;"
              >
                <ha-icon icon="${clip.icon}"></ha-icon>
                <span style="font-size:12px;text-align:center;line-height:1.2;">${clip.label}</span>
              </button>
            `
                )
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
