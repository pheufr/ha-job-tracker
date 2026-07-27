class RcQuizMasterCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._pointButtons = Array.isArray(this._config.point_buttons) && this._config.point_buttons.length
      ? this._config.point_buttons
      : [5];
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _players() {
    const players = [];
    for (const [entityId, state] of Object.entries(this._hass.states)) {
      if (!entityId.startsWith("sensor.rc_quiz_")) {
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
    return this._hass.callService("raven_castle_quiz", service, data);
  }

  _renderPhoto(photo, name) {
    if (!this._config.show_photos) return "";
    if (!photo) {
      return `<div style="width:24px;height:24px;border-radius:50%;background:#999;color:white;display:inline-flex;align-items:center;justify-content:center;font-size:11px;">${name.slice(0, 1).toUpperCase()}</div>`;
    }
    return `<img src="${photo}" alt="${name}" style="width:24px;height:24px;border-radius:50%;object-fit:cover;" />`;
  }

  _row(player, compact) {
    const actionButtons = this._pointButtons
      .map((points) => `<button data-action="add" data-entity="${player.entityId}" data-points="${points}">+${points}</button><button data-action="remove" data-entity="${player.entityId}" data-points="${points}">-${points}</button>`)
      .join(" ");

    return `
      <tr style="${player.enabled ? "" : "opacity:0.45;"}">
        <td>${this._renderPhoto(player.photo, player.name)} ${player.name}</td>
        <td>${player.alias}</td>
        <td>${player.round}</td>
        <td>${player.total}</td>
        <td>
          ${actionButtons}
          <input type="number" style="width:${compact ? "50px" : "60px"};" data-action="custom-points" data-entity="${player.entityId}" value="0" />
          <button data-action="apply-custom" data-entity="${player.entityId}">Apply</button>
          <button data-action="toggle" data-entity="${player.entityId}" data-enabled="${player.enabled}">${player.enabled ? "✗" : "✓"}</button>
        </td>
      </tr>
    `;
  }

  _render() {
    if (!this._hass) return;
    const compact = Boolean(this._config.compact);
    const players = this._players();

    this.innerHTML = `
      <ha-card header="RC Quiz Master Control">
        <div style="padding:12px;">
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
            <button data-action="new-round">Start New Round</button>
            <button data-action="new-quiz">Start New Quiz</button>
          </div>
          <div style="overflow:auto;">
            <table style="width:100%;border-collapse:collapse;font-size:${compact ? "12px" : "14px"};">
              <thead>
                <tr>
                  <th style="text-align:left;">Name</th>
                  <th style="text-align:left;">Alias</th>
                  <th style="text-align:left;">Round</th>
                  <th style="text-align:left;">Total</th>
                  <th style="text-align:left;">Actions</th>
                </tr>
              </thead>
              <tbody>
                ${players.map((player) => this._row(player, compact)).join("") || '<tr><td colspan="5">No players</td></tr>'}
              </tbody>
            </table>
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
          if (confirm("Reset all RC Quiz scores and start a new quiz?")) {
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

        if (action === "toggle") {
          const enabled = event.currentTarget.dataset.enabled === "true";
          await this._call(enabled ? "disable_player" : "enable_player", {
            entity_id: entityId,
          });
          return;
        }

        if (action === "apply-custom") {
          const input = this.querySelector(`input[data-action='custom-points'][data-entity='${entityId}']`);
          const value = Number(input?.value || 0);
          if (value === 0) return;
          await this._call(value > 0 ? "add_points" : "remove_points", {
            entity_id: entityId,
            points: Math.abs(value),
          });
          input.value = "0";
        }
      };
    });
  }

  getCardSize() {
    return 6;
  }
}

customElements.define("rc-quiz-master-card", RcQuizMasterCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "rc-quiz-master-card",
  name: "RC Quiz Master Card",
  description: "Master control panel for Raven Castle Quiz",
});