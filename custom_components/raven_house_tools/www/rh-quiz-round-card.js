class RHQuizRoundCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _title() {
    if (this._config.title === undefined) {
      return "RH Quiz Round Summary";
    }
    return this._config.title;
  }

  _renderHeader() {
    const title = this._title();
    return title === "" ? "" : ` header="${title}"`;
  }

  _photo(photo, label) {
    if (!photo) {
      return `<div style="width:36px;height:36px;border-radius:50%;background:#999;color:white;display:flex;align-items:center;justify-content:center;font-size:13px;">${(label || "?").slice(0, 1).toUpperCase()}</div>`;
    }
    return `<img src="${photo}" alt="${label}" style="width:36px;height:36px;border-radius:50%;object-fit:cover;" />`;
  }

  _players() {
    const showDisabled = this._config.show_disabled ?? false;
    const maxPlayers = this._config.max_players ?? 10;
    const players = [];

    for (const [entityId, state] of Object.entries(this._hass.states)) {
      if (!entityId.startsWith("sensor.rh_quiz_")) {
        continue;
      }

      const attrs = state.attributes || {};
      if (attrs.player_metric !== "total_score") {
        continue;
      }

      const enabled = Boolean(attrs.enabled);
      if (!showDisabled && !enabled) {
        continue;
      }

      players.push({
        entityId,
        alias: attrs.player_alias || attrs.player_name || entityId,
        name: attrs.player_name || entityId,
        photo: attrs.player_photo || "",
        total: Number(state.state) || 0,
        round: Number(attrs.current_round_score || 0),
        enabled,
      });
    }

    players.sort((a, b) => b.round - a.round || b.total - a.total || a.alias.localeCompare(b.alias));
    return players.slice(0, maxPlayers);
  }

  _winners(players) {
    if (!players.length) {
      return [];
    }
    const highest = Math.max(...players.map((player) => player.total));
    return players.filter((player) => player.total === highest);
  }

  _rankLabels(players) {
    const labels = [];
    let previousRank = 0;

    players.forEach((player, index) => {
      if (index === 0) {
        previousRank = 1;
        labels.push("1st");
        return;
      }

      const previousPlayer = players[index - 1];
      const isTied =
        player.round === previousPlayer.round && player.total === previousPlayer.total;

      if (isTied) {
        labels.push("");
        return;
      }

      previousRank = index + 1;
      if (previousRank === 2) {
        labels.push("2nd");
      } else if (previousRank === 3) {
        labels.push("3rd");
      } else {
        labels.push(`#${previousRank}`);
      }
    });

    return labels;
  }

  _roundRows(players) {
    if (!players.length) {
      return '<div style="padding:8px 0;opacity:0.7;">No players to display</div>';
    }

    const rankLabels = this._rankLabels(players);

    return players
      .map(
        (player, index) => `
          <div style="display:flex;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid rgba(128,128,128,0.2);${player.enabled ? "" : "opacity:0.45;"}">
            <div style="min-width:34px;font-weight:700;">${rankLabels[index]}</div>
            ${this._photo(player.photo, player.alias)}
            <div style="flex:1;min-width:0;">
              <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${player.alias}</div>
              <div style="font-size:12px;opacity:0.8;">Total: ${player.total}</div>
            </div>
            <div style="text-align:right;font-weight:700;">${player.round >= 0 ? "+" : ""}${player.round}</div>
          </div>
        `
      )
      .join("");
  }

  _winnerBadges(winners) {
    if (!winners.length) {
      return '<div style="opacity:0.7;">No total winner yet</div>';
    }

    return winners
      .map(
        (player) => `
          <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:999px;background:rgba(128,128,128,0.12);">
            ${this._photo(player.photo, player.alias)}
            <div>
              <div style="font-weight:700;">${player.alias}</div>
              <div style="font-size:12px;opacity:0.75;">Total ${player.total}</div>
            </div>
          </div>
        `
      )
      .join("");
  }

  _render() {
    if (!this._hass) return;

    const players = this._players();
    const winners = this._winners(players);

    this.innerHTML = `
      <ha-card${this._renderHeader()}>
        <div style="padding:16px;display:grid;gap:18px;">
          <section>
            <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.65;margin-bottom:10px;">Current Total Winner${winners.length === 1 ? "" : "s"}</div>
            <div style="display:flex;flex-wrap:wrap;gap:10px;">${this._winnerBadges(winners)}</div>
          </section>
          <section>
            <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.65;margin-bottom:6px;">This Round Leaderboard</div>
            <div>${this._roundRows(players)}</div>
          </section>
        </div>
      </ha-card>
    `;
  }

  getCardSize() {
    return 5;
  }
}

if (!customElements.get("rh-quiz-round-card")) {
  customElements.define("rh-quiz-round-card", RHQuizRoundCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.find((card) => card.type === "rh-quiz-round-card")) {
  window.customCards.push({
    type: "rh-quiz-round-card",
    name: "RH Quiz Round Card",
    description: "Shows this round leaderboard and the current total winners",
  });
}
