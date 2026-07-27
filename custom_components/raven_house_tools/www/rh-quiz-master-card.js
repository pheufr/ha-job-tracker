class RHQuizMasterCard extends HTMLElement {
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
    if (!photo) {
      return `<div style="width:24px;height:24px;border-radius:50%;background:#999;color:white;display:inline-flex;align-items:center;justify-content:center;font-size:11px;">${name.slice(0, 1).toUpperCase()}</div>`;
    }
    return `<img src="${photo}" alt="${name}" style="width:24px;height:24px;border-radius:50%;object-fit:cover;" />`;
  }

  _row(player, compact) {
    const actionButtons = this._pointButtons
      .map((points) => {
        const action = points > 0 ? "add" : "remove";
        const label = points > 0 ? `+${points}` : `${points}`;
        return `<button data-action="${action}" data-entity="${player.entityId}" data-points="${Math.abs(points)}">${label}</button>`;
      })
      .join(" ");

    return `
      <tr style="${player.enabled ? "" : "opacity:0.45;"}">
        <td>${this._renderPhoto(player.photo, player.name)} ${player.name}</td>
        <td>${player.alias}</td>
        <td>${player.round}</td>
        <td>${player.total}</td>
        <td>${actionButtons}</td>
      </tr>
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
