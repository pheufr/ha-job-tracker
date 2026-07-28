class RHJobsCard extends HTMLElement {
  constructor() {
    super();
    this._resolvedMediaUrls = new Map();
    this._pendingResolutions = new Set();
  }

  set hass(hass) {
    this._hass = hass;
    this.updateCard();
  }

  setConfig(config) {
    this._config = config || {};
  }

  _title() {
    if (this._config.title === undefined) {
      return "RH Jobs";
    }
    return this._config.title;
  }

  _isDueState(state) {
    if (!state) return false;
    return !["off", "unavailable", "unknown", "none"].includes(state.state);
  }

  _orientation() {
    return this._config.orientation === "horizontal" ? "horizontal" : "vertical";
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
      .callWS({
        type: "media_source/resolve_media",
        media_content_id: mediaContentId,
      })
      .then((result) => {
        const url = typeof result?.url === "string" ? result.url : "";
        this._resolvedMediaUrls.set(mediaContentId, url);
      })
      .catch(() => {
        this._resolvedMediaUrls.set(mediaContentId, "");
      })
      .finally(() => {
        this._pendingResolutions.delete(mediaContentId);
        this.updateCard();
      });
  }

  _jobEntityIds() {
    if (Array.isArray(this._config.job_entities) && this._config.job_entities.length) {
      return this._config.job_entities;
    }

    return Object.entries(this._hass.states)
      .filter(([entityId, state]) => entityId.startsWith("binary_sensor.rh_jobs_") && state?.attributes?.job_id)
      .map(([entityId]) => entityId)
      .sort();
  }

  async updateCard() {
    if (!this._hass || !this._config) return;

    const jobEntityIds = this._jobEntityIds();
    const showAll = Boolean(this._config.show_all);
    const showImages = this._config.show_images !== false;
    const jobs = [];

    for (const entityId of jobEntityIds) {
      const state = this._hass.states[entityId];
      if (!state) continue;

      const isDue = this._isDueState(state);
      if (!showAll && !isDue) continue;

      const attributes = state.attributes || {};
      const image = showImages ? this._displayImage(attributes.image || "") : "";
      const priority = attributes.priority || 0;

      jobs.push({
        entityId,
        image,
        icon: attributes.icon || "",
        colour: attributes.colour || "",
        isDue,
        priority,
        name: attributes.friendly_name || entityId,
      });
    }

    jobs.sort((a, b) => Number(b.isDue) - Number(a.isDue) || b.priority - a.priority || a.name.localeCompare(b.name));
    this.innerHTML = this.renderJobs(jobs);
  }

  _renderHeader() {
    const title = this._title();
    return title === "" ? "" : ` header="${title}"`;
  }

  _renderJobTile(job) {
    const orientation = this._orientation();
    const tileDirection = orientation === "horizontal" ? "row" : "column";
    const tileWidth = orientation === "horizontal" ? "min-width:260px;" : "width:100%;";
    const isHorizontal = orientation === "horizontal";
    const imgSize = isHorizontal ? "72px" : "100%";
    const imgMaxWidth = isHorizontal ? "72px" : "320px";

    let mediaHtml = "";
    if (job.image) {
      mediaHtml = `<img src="${job.image}" alt="${job.name}" style="width:${imgSize};max-width:${imgMaxWidth};height:${isHorizontal ? "72px" : "auto"};aspect-ratio:${isHorizontal ? "1 / 1" : "auto"};object-fit:cover;display:block;border-radius:10px;" onerror="this.style.display='none'" />`;
    } else if (job.icon) {
      const iconBg = job.colour || "var(--primary-color)";
      const iconBoxStyle = isHorizontal
        ? `width:72px;min-width:72px;height:72px;border-radius:10px;background:${iconBg};display:flex;align-items:center;justify-content:center;`
        : `width:100%;max-width:320px;height:120px;border-radius:10px;background:${iconBg};display:flex;align-items:center;justify-content:center;`;
      mediaHtml = `<div style="${iconBoxStyle}"><ha-icon icon="${job.icon}" style="color:#fff;--mdi-icon-size:36px;"></ha-icon></div>`;
    }

    const baseStyle = job.isDue ? "" : "opacity:0.55;";
    return `
      <button style="cursor:pointer;border:0;border-radius:10px;padding:12px;background:var(--card-background-color, #fff);box-shadow:inset 0 0 0 1px rgba(128,128,128,0.25);font:inherit;text-align:left;display:flex;gap:12px;align-items:${isHorizontal ? "center" : "flex-start"};flex-direction:${tileDirection};${tileWidth}${baseStyle}" class="job-image-container" data-entity-id="${job.entityId}" title="${job.name} (Priority: ${job.priority})">
        ${mediaHtml}
        <div style="min-width:0;">
          <div style="font-size:12px;opacity:0.7;margin-bottom:6px;">${job.isDue ? "Due" : "Complete"} | Priority ${job.priority}</div>
          <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${job.name}</div>
        </div>
      </button>
    `;
  }

  renderJobs(jobs) {
    if (jobs.length === 0) {
      return `
        <ha-card${this._renderHeader()}>
          <div style="display:flex;align-items:center;justify-content:center;min-height:160px;color:#666;padding:16px;">
            No due jobs
          </div>
        </ha-card>
      `;
    }

    const jobsHtml = jobs.map((job) => this._renderJobTile(job)).join("");

    const orientation = this._orientation();
    const listStyle =
      orientation === "horizontal"
        ? "display:flex;flex-wrap:wrap;gap:12px;padding:16px;align-items:flex-start;"
        : "display:flex;flex-direction:column;gap:12px;padding:16px;";

    return `
      <ha-card${this._renderHeader()}>
        <div style="${listStyle}">
          ${jobsHtml}
        </div>
      </ha-card>
    `;
  }

  connectedCallback() {
    this.addEventListener("click", (e) => this.handleImageClick(e));
  }

  handleImageClick(e) {
    const container = e.target.closest(".job-image-container");
    if (!container) return;

    const entityId = container.getAttribute("data-entity-id");
    if (!entityId) return;

    this._hass.callService("raven_house_tools", "complete_job", {
      entity_id: entityId,
    });

    container.style.opacity = "0.5";
    setTimeout(() => {
      container.style.opacity = "1";
    }, 200);
  }
}

if (!customElements.get("rh-jobs-card")) {
  customElements.define("rh-jobs-card", RHJobsCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.find((card) => card.type === "rh-jobs-card")) {
  window.customCards.push({
    type: "rh-jobs-card",
    name: "RH Jobs Card",
    description: "Shows due Raven House Jobs with images",
  });
}
