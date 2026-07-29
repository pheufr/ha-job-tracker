class RHQuizMasterCard extends HTMLElement {
  constructor() {
    super();
    this._resolvedMediaUrls = new Map();
    this._pendingResolutions = new Set();
  }

  setConfig(config) {
    this._config = config || {};
    this._pointButtons = [5, 1, -1, -5];
  }

  _title() {
    if (this._config.title === undefined) {
      return "RH Quiz Master Control";
    }
    return this._config.title;
  }

  _renderHeader() {
    const title = this._title();
    return title === "" ? "" : ` header="${title}"`;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _players() {
    const players = [];
    for (const [entityId, state] of Object.entries(this._hass.states)) {
      if (!entityId.startsWith("sensor.rh_quiz_")) {
        continue;
      }

      const attrs = state.attributes || {};
      if (attrs.player_metric !== "total_score") {
        continue;
      }

      players.push({
        entityId,
        name: attrs.player_name || entityId,
        alias: attrs.player_alias || "",
        photo: attrs.player_photo || "",
        enabled: Boolean(attrs.enabled),
        round: Number(attrs.current_round_score || 0),
        total: Number(state.state || 0),
      });
    }

    players.sort((a, b) => a.name.localeCompare(b.name));
    return players;
  }

  _call(service, data = {}) {
    return this._hass.callService("raven_house_tools", service, data);
  }

  _renderPhoto(photo, name) {
    if (!this._config.show_photos) return "";
    const resolvedPhoto = this._displayImage(photo);
    if (!resolvedPhoto) {
      return `<div style="width:24px;height:24px;border-radius:50%;background:#999;color:white;display:inline-flex;align-items:center;justify-content:center;font-size:11px;">${name.slice(0, 1).toUpperCase()}</div>`;
    }
    return `<img src="${resolvedPhoto}" alt="${name}" style="width:24px;height:24px;border-radius:50%;object-fit:cover;" onerror="this.style.display='none'" />`;
  }

  _displayImage(image) {
    if (typeof image !== "string") {
      return "";
    }
    const trimmed = image.trim();
    if (!trimmed) {
      return "";
    }
    if (!trimmed.startsWith("media-source://")) {
      return trimmed;
    }
    if (this._resolvedMediaUrls.has(trimmed)) {
      return this._resolvedMediaUrls.get(trimmed) || "";
    }
    this._resolveMediaSource(trimmed);
    return "";
  }

  _resolveMediaSource(mediaContentId) {
    if (this._pendingResolutions.has(mediaContentId)) {
      return;
    }
    if (!this._hass || typeof this._hass.callWS !== "function") {
      return;
    }
    this._pendingResolutions.add(mediaContentId);
    this._hass
      .callWS({ type: "media_source/resolve_media", media_content_id: mediaContentId })
      .then((result) => {
        const url = typeof result?.url === "string" ? result.url : "";
        this._resolvedMediaUrls.set(mediaContentId, url);
      })
      .catch(() => {
        this._resolvedMediaUrls.set(mediaContentId, "");
      })
      .finally(() => {
        this._pendingResolutions.delete(mediaContentId);
        this._render();
      });
  }

  _row(player, compact) {
    const actionButtons = this._pointButtons
      .map((points) => {
        const action = points > 0 ? "add" : "remove";
        const label = points > 0 ? `+${points}` : `${points}`;
        return `<button data-action="${action}" data-entity="${player.entityId}" data-points="${Math.abs(points)}" style="min-width:48px;">${label}</button>`;
      })
      .join("");

    return `
      <div style="padding:10px 0;${player.enabled ? "" : "opacity:0.45;"}">
        <div style="display:flex;align-items:center;gap:8px;min-width:0;">
          ${this._renderPhoto(player.photo, player.name)}
          <div style="min-width:0;">
            <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${player.name}</div>
            <div style="font-size:12px;opacity:0.75;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${player.alias || "No alias"}</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-top:8px;">
          <div style="font-size:${compact ? "11px" : "12px"};">Round: <strong>${player.round}</strong> | Total: <strong>${player.total}</strong></div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;">${actionButtons}</div>
        </div>
      </div>
    `;
  }

  _render() {
    if (!this._hass) return;
    const compact = Boolean(this._config.compact);
    const players = this._players();

    this.innerHTML = `
      <ha-card${this._renderHeader()}>
        <div style="padding:12px;">
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
            <button data-action="new-round">Start New Round</button>
            <button data-action="new-quiz">Start New Quiz</button>
          </div>
          <div style="font-size:${compact ? "12px" : "14px"};">
            ${players.map((player, index) => `${this._row(player, compact)}${index < players.length - 1 ? '<hr style="border:none;border-top:1px solid rgba(128,128,128,0.25);margin:0;">' : ""}`).join("") || '<div>No players</div>'}
          </div>
        </div>
      </ha-card>
    `;

    this._attachHandlers();
  }

  _attachHandlers() {
    this.querySelectorAll("button").forEach((button) => {
      button.onclick = async (event) => {
        const action = event.currentTarget.dataset.action;
        const entityId = event.currentTarget.dataset.entity;

        if (action === "new-round") {
          await this._call("start_new_round");
          return;
        }

        if (action === "new-quiz") {
          if (confirm("Reset all RH Quiz scores and start a new quiz?")) {
            await this._call("start_new_quiz");
          }
          return;
        }

        if (action === "add" || action === "remove") {
          const points = Number(event.currentTarget.dataset.points || 0);
          await this._call(action === "add" ? "add_points" : "remove_points", {
            entity_id: entityId,
            points,
          });
          return;
        }

      };
    });
  }

  getCardSize() {
    return 6;
  }
}

if (!customElements.get("rh-quiz-master-card")) {
  customElements.define("rh-quiz-master-card", RHQuizMasterCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.find((card) => card.type === "rh-quiz-master-card")) {
  window.customCards.push({
    type: "rh-quiz-master-card",
    name: "RH Quiz Master Card",
    description: "Master control panel for Raven House Quiz",
  });
}
