class RHQuizCard extends HTMLElement {
  constructor() {
    super();
    this._resolvedMediaUrls = new Map();
    this._pendingResolutions = new Set();
  }

  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _title() {
    if (this._config.title === undefined) {
      return "RH Quiz Card";
    }
    return this._config.title;
  }

  _renderHeader() {
    const title = this._title();
    return title === "" ? "" : ` header="${title}"`;
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

      const round = Number(attrs.current_round_score || 0);
      const total = Number(state.state) || 0;

      players.push({
        entityId,
        alias: attrs.player_alias || attrs.player_name || entityId,
        photo: attrs.player_photo || "",
        enabled,
        round,
        total,
        overall: total - round,
      });
    }

    return players.slice(0, maxPlayers);
  }

  _rankLabels(players, scoreField) {
    const labels = [];
    let previousRank = 0;

    players.forEach((player, index) => {
      if (index === 0) {
        previousRank = 1;
        labels.push("1st");
        return;
      }

      const previousPlayer = players[index - 1];
      if (player[scoreField] === previousPlayer[scoreField]) {
        labels.push("");
        return;
      }

      previousRank = index + 1;
      if (previousRank === 2) labels.push("2nd");
      else if (previousRank === 3) labels.push("3rd");
      else labels.push(`#${previousRank}`);
    });

    return labels;
  }

  _photo(photo, label, size = 36, radius = "50%") {
    const resolvedPhoto = this._displayImage(photo);
    if (!resolvedPhoto) {
      return `<div style="width:${size}px;height:${size}px;border-radius:${radius};background:#999;color:white;display:flex;align-items:center;justify-content:center;font-size:${Math.max(12, Math.floor(size * 0.33))}px;">${(label || "?").slice(0, 1).toUpperCase()}</div>`;
    }
    return `<img src="${resolvedPhoto}" alt="${label}" style="width:${size}px;height:${size}px;border-radius:${radius};object-fit:cover;" onerror="this.style.display='none'" />`;
  }

  _winnerSection(roundPlayers) {
    if (!roundPlayers.length) {
      return `
        <section>
          <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.65;margin-bottom:8px;">Winner</div>
          <div style="opacity:0.7;">No winner yet</div>
        </section>
      `;
    }

    const winner = roundPlayers[0];
    const winnerImage = this._displayImage(winner.photo);
    const winnerScore = `${winner.round >= 0 ? "+" : ""}${winner.round}`;

    return `
      <section>
        <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.65;margin-bottom:8px;">Winner</div>
        <div style="position:relative;min-height:200px;border-radius:14px;overflow:hidden;background:${winnerImage ? "center / cover no-repeat url('" + winnerImage + "')" : "var(--primary-color)"};">
          <div style="position:absolute;inset:0;background:linear-gradient(to top, rgba(0,0,0,0.72), rgba(0,0,0,0.25));"></div>
          <div style="position:absolute;left:14px;right:14px;bottom:14px;color:#fff;">
            <div style="font-size:20px;font-weight:700;line-height:1.2;">${winner.alias}</div>
            <div style="font-size:14px;opacity:0.95;">${winnerScore}</div>
          </div>
        </div>
      </section>
    `;
  }

  _leaderboardRows(players, scoreField, withPhoto = true) {
    if (!players.length) {
      return '<div style="padding:8px 0;opacity:0.7;">No players to display</div>';
    }

    const labels = this._rankLabels(players, scoreField);
    return players
      .map(
        (player, index) => `
          <div style="display:flex;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid rgba(128,128,128,0.2);${player.enabled ? "" : "opacity:0.45;"}">
            <div style="min-width:34px;font-weight:700;">${labels[index]}</div>
            ${withPhoto ? this._photo(player.photo, player.alias) : ""}
            <div style="flex:1;min-width:0;">
              <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${player.alias}</div>
            </div>
            <div style="text-align:right;font-weight:700;">${player[scoreField] >= 0 ? "+" : ""}${player[scoreField]}</div>
          </div>
        `
      )
      .join("");
  }

  _render() {
    if (!this._hass) return;

    const players = this._players();
    const roundPlayers = [...players].sort((a, b) => b.round - a.round || a.alias.localeCompare(b.alias));
    const overallPlayers = [...players].sort((a, b) => b.overall - a.overall || a.alias.localeCompare(b.alias));

    const showWinner = this._config.show_winner !== false;
    const showLeaderboard = this._config.show_leaderboard !== false;
    const showRoundLeaderboard = this._config.show_round_leaderboard !== false;

    this.innerHTML = `
      <ha-card${this._renderHeader()}>
        <div style="padding:16px;display:grid;gap:18px;">
          ${showWinner ? this._winnerSection(roundPlayers) : ""}
          ${showLeaderboard ? `
          <section>
            <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.65;margin-bottom:6px;">Leaderboard</div>
            <div>${this._leaderboardRows(overallPlayers, "overall")}</div>
          </section>` : ""}
          ${showRoundLeaderboard ? `
          <section>
            <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.65;margin-bottom:6px;">This Round</div>
            <div>${this._leaderboardRows(roundPlayers, "round")}</div>
          </section>` : ""}
        </div>
      </ha-card>
    `;
  }

  getCardSize() {
    return 6;
  }
}

if (!customElements.get("rh-quiz-card")) {
  customElements.define("rh-quiz-card", RHQuizCard);
}

if (!customElements.get("rh-quiz-round-card")) {
  customElements.define("rh-quiz-round-card", RHQuizCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.find((card) => card.type === "rh-quiz-card")) {
  window.customCards.push({
    type: "rh-quiz-card",
    name: "RH Quiz Card",
    description: "Shows winner, leaderboard and round leaderboard",
  });
}
