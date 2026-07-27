class RHJobsCard extends HTMLElement {
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
    const jobs = [];

    for (const entityId of jobEntityIds) {
      const state = this._hass.states[entityId];
      if (!state) continue;

      const isDue = this._isDueState(state);
      if (!showAll && !isDue) continue;

      const attributes = state.attributes || {};
      const image = attributes.image || "";
      const priority = attributes.priority || 0;

      jobs.push({
        entityId,
        image,
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
    const baseStyle = job.isDue ? "" : "opacity:0.55;";
    if (job.image) {
      return `
        <div style="cursor:pointer;transition:opacity 0.2s;${baseStyle}" class="job-image-container" data-entity-id="${job.entityId}" title="${job.name} (Priority: ${job.priority})">
          <img src="${job.image}" alt="${job.name}" style="max-width:100%;height:auto;display:block;border-radius:10px;" />
        </div>
      `;
    }

    return `
      <button style="cursor:pointer;border:0;border-radius:10px;padding:18px 16px;background:var(--card-background-color, #fff);box-shadow:inset 0 0 0 1px rgba(128,128,128,0.25);font:inherit;text-align:left;min-width:160px;${baseStyle}" class="job-image-container" data-entity-id="${job.entityId}" title="${job.name} (Priority: ${job.priority})">
        <div style="font-size:12px;opacity:0.7;margin-bottom:6px;">${job.isDue ? "Due" : "Complete"} | Priority ${job.priority}</div>
        <div style="font-weight:600;">${job.name}</div>
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

    return `
      <ha-card${this._renderHeader()}>
        <div style="display:flex;flex-wrap:wrap;gap:16px;padding:16px;align-items:flex-start;">
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
