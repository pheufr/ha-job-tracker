class RcQuizLeaderboardCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _collectPlayers() {
    const showDisabled = this._config.show_disabled ?? false;
    const maxPlayers = this._config.max_players ?? 10;
    const players = [];

    for (const [entityId, state] of Object.entries(this._hass.states)) {
      if (!entityId.startsWith("sensor.rc_quiz_") || entityId.endsWith("_round")) {
        continue;
      }

      const attrs = state.attributes || {};
      const enabled = Boolean(attrs.enabled);
      if (!showDisabled && !enabled) {
        continue;
      }

      players.push({
        entityId,
        alias: attrs.alias || attrs.name || entityId,
        photo: attrs.photo || "",
        total: Number(state.state) || 0,
        round: Number(attrs.current_round_score || 0),
        lastRound: Number(attrs.last_round_score || 0),
        enabled,
      });
    }

    players.sort((a, b) => b.total - a.total || b.round - a.round || a.alias.localeCompare(b.alias));
    return players.slice(0, maxPlayers);
  }

  _medal(rank) {
    if (rank === 0) return "🥇";
    if (rank === 1) return "🥈";
    if (rank === 2) return "🥉";
    return `#${rank + 1}`;
  }

  _photo(photo, alias) {
    if (!photo) {
      return `<div style="width:40px;height:40px;border-radius:50%;background:#999;color:white;display:flex;align-items:center;justify-content:center;font-size:14px;">${(alias || "?").slice(0, 1).toUpperCase()}</div>`;
    }
    return `<img src="${photo}" alt="${alias}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;" />`;
  }

  _render() {
    if (!this._hass) return;

    const players = this._collectPlayers();
    const rows = players
      .map(
        (player, index) => `
          <div style="display:flex;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid rgba(128,128,128,0.2);${player.enabled ? "" : "opacity:0.45;"}">
            <div style="min-width:34px;font-weight:700;">${this._medal(index)}</div>
            ${this._photo(player.photo, player.alias)}
            <div style="flex:1;min-width:0;">
              <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${player.alias}</div>
              <div style="font-size:12px;opacity:0.8;">Round: ${player.round >= 0 ? "+" : ""}${player.round} | Last: ${player.lastRound >= 0 ? "+" : ""}${player.lastRound}</div>
            </div>
            <div style="text-align:right;font-weight:700;">Total: ${player.total}</div>
          </div>
        `
      )
      .join("");

    this.innerHTML = `
      <ha-card header="RC Quiz Leaderboard">
        <div style="padding:0 16px 12px;">
          ${rows || '<div style="padding:12px 0;opacity:0.7;">No players to display</div>'}
        </div>
      </ha-card>
    `;
  }

  getCardSize() {
    return 4;
  }
}

customElements.define("rc-quiz-leaderboard-card", RcQuizLeaderboardCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "rc-quiz-leaderboard-card",
  name: "RC Quiz Leaderboard Card",
  description: "Shows RC Quiz leaderboard sorted by score",
});
