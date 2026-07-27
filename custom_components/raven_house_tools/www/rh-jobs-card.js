class RHJobsCard extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    this.updateCard();
  }

  setConfig(config) {
    this._config = config;
  }

  async updateCard() {
    if (!this._hass || !this._config) return;

    const jobEntityIds = this._config.job_entities || [];
    const jobs = [];

    for (const entityId of jobEntityIds) {
      const state = this._hass.states[entityId];
      if (!state || state.state !== "on") continue;

      const attributes = state.attributes || {};
      const image = attributes.image || null;
      const priority = attributes.priority || 0;

      if (image) {
        jobs.push({
          entityId,
          image,
          priority,
          name: attributes.friendly_name || entityId,
        });
      }
    }

    jobs.sort((a, b) => b.priority - a.priority);
    this.innerHTML = this.renderJobs(jobs);
  }

  renderJobs(jobs) {
    if (jobs.length === 0) {
      return `
        <div style="display:flex;align-items:center;justify-content:center;min-height:200px;color:#666;">
          No due jobs
        </div>
      `;
    }

    const jobsHtml = jobs
      .map(
        (job) => `
      <div style="cursor:pointer;transition:opacity 0.2s;"
           class="job-image-container"
           data-entity-id="${job.entityId}"
           title="${job.name} (Priority: ${job.priority})">
        <img src="${job.image}"
             alt="${job.name}"
             style="max-width:100%;height:auto;display:block;border-radius:4px;" />
      </div>
    `
      )
      .join("");

    return `
      <div style="display:flex;flex-wrap:wrap;gap:16px;padding:16px;">
        ${jobsHtml}
      </div>
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
