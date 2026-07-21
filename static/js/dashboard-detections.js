(() => {
  const dashboard = document.querySelector("[data-dashboard-detections-url]");
  if (!dashboard) return;

  const totalsContainer = dashboard.querySelector("[data-dashboard-totals]");
  const feedsContainer = dashboard.querySelector("[data-dashboard-feeds]");
  const summaryUrl = dashboard.dataset.dashboardDetectionsUrl;
  const visibleCards = new Set();
  const cards = new Map();

  const element = (tagName, className, text) => {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const observer = "IntersectionObserver" in window
    ? new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) visibleCards.add(entry.target);
        else visibleCards.delete(entry.target);
      });
    }, { rootMargin: "120px" })
    : null;

  const registerCard = (card) => {
    cards.set(Number(card.dataset.feedId), card);
    if (observer) observer.observe(card);
    else visibleCards.add(card);
  };

  const unregisterCard = (card) => {
    if (observer) observer.unobserve(card);
    visibleCards.delete(card);
    if (card.dataset.previewObjectUrl) URL.revokeObjectURL(card.dataset.previewObjectUrl);
    cards.delete(Number(card.dataset.feedId));
    card.remove();
  };

  const metricCard = (count, label, modifier = "") => {
    const card = element("article", `metric-card${modifier}`);
    card.append(
      element("span", "metric-card__value", String(count)),
      element("span", "metric-card__label", label),
    );
    return card;
  };

  const renderTotals = (payload) => {
    if (!totalsContainer) return;
    totalsContainer.replaceChildren(
      metricCard(payload.total_objects, "Total objects", " metric-card--total"),
    );
    const counts = Object.entries(payload.stable_counts);
    if (!counts.length) {
      totalsContainer.append(metricCard(0, "Waiting for detections", " metric-card--quiet"));
      return;
    }
    counts.forEach(([name, count]) => totalsContainer.append(metricCard(count, name)));
  };

  const buildCard = (feed) => {
    const card = element("a", "feed-summary-card");
    card.dataset.feedCard = "";
    card.dataset.feedId = feed.id;

    const preview = element("span", "feed-summary-card__preview");
    preview.dataset.feedPreview = "";
    const image = element("img");
    image.dataset.feedPreviewImage = "";
    const placeholder = element("span", "feed-summary-card__placeholder");
    placeholder.dataset.feedPreviewPlaceholder = "";
    preview.append(image, placeholder);

    const header = element("span", "feed-summary-card__header");
    const identity = element("span");
    identity.append(element("strong"), element("small"));
    const status = element("span", "feed-summary-card__status");
    status.dataset.feedStatus = "";
    header.append(identity, status);

    const counts = element("span", "feed-summary-card__counts");
    counts.dataset.feedCounts = "";
    card.append(preview, header, counts);
    feedsContainer.append(card);
    registerCard(card);
    return card;
  };

  const renderCounts = (container, counts) => {
    container.replaceChildren();
    const entries = Object.entries(counts);
    if (!entries.length) {
      container.append(element("span", "", "No stabilized detections"));
      return;
    }
    entries.forEach(([name, count]) => {
      const item = element("span");
      item.append(element("b", "", String(count)), ` ${name}`);
      container.append(item);
    });
  };

  const updateCard = (feed) => {
    const card = cards.get(feed.id) || buildCard(feed);
    card.href = feed.detail_url;
    card.dataset.previewUrl = feed.preview_url;
    card.dataset.feedEnabled = String(feed.is_enabled);
    card.dataset.feedStatusValue = feed.status;
    card.querySelector("strong").textContent = feed.name;
    card.querySelector(".feed-summary-card__header small").textContent = feed.connection_host;

    const image = card.querySelector("[data-feed-preview-image]");
    image.alt = `Annotated preview from ${feed.name}`;
    const placeholder = card.querySelector("[data-feed-preview-placeholder]");
    placeholder.textContent = feed.is_enabled ? "Waiting for preview" : "Detection paused";

    const status = card.querySelector("[data-feed-status]");
    status.textContent = feed.status.charAt(0).toUpperCase() + feed.status.slice(1);
    status.classList.toggle("feed-summary-card__status--online", feed.status === "detecting");
    renderCounts(card.querySelector("[data-feed-counts]"), feed.stable_counts);

    if (!feed.is_enabled) {
      image.removeAttribute("src");
      if (card.dataset.previewObjectUrl) {
        URL.revokeObjectURL(card.dataset.previewObjectUrl);
        delete card.dataset.previewObjectUrl;
      }
      card.querySelector("[data-feed-preview]").classList.remove("feed-summary-card__preview--loaded");
    }
  };

  const renderFeeds = (payload) => {
    if (!feedsContainer) return;
    const currentIds = new Set(payload.feeds.map((feed) => feed.id));
    [...cards.entries()].forEach(([feedId, card]) => {
      if (!currentIds.has(feedId)) unregisterCard(card);
    });
    payload.feeds.forEach(updateCard);
  };

  const refreshPreview = async (card) => {
    if (
      card.dataset.feedEnabled !== "true"
      || card.dataset.feedStatusValue === "reconnecting"
      || card.dataset.feedStatusValue === "stale"
      || card.dataset.previewLoading === "true"
      || !card.dataset.previewUrl
    ) return;
    const separator = card.dataset.previewUrl.includes("?") ? "&" : "?";
    const previewUrl = `${card.dataset.previewUrl}${separator}time=${Date.now()}`;
    card.dataset.previewLoading = "true";
    try {
      const response = await fetch(previewUrl, {
        credentials: "same-origin",
        cache: "no-store",
      });
      if (response.status === 204) return;
      if (!response.ok) throw new Error(`Preview returned ${response.status}`);
      const objectUrl = URL.createObjectURL(await response.blob());
      if (!card.isConnected || card.dataset.feedEnabled !== "true") {
        URL.revokeObjectURL(objectUrl);
        return;
      }
      const previousObjectUrl = card.dataset.previewObjectUrl;
      card.dataset.previewObjectUrl = objectUrl;
      card.querySelector("[data-feed-preview-image]").src = objectUrl;
      card.querySelector("[data-feed-preview]").classList.add("feed-summary-card__preview--loaded");
      if (previousObjectUrl) URL.revokeObjectURL(previousObjectUrl);
    } catch (error) {
      console.warn(`Could not refresh preview for feed ${card.dataset.feedId}.`, error);
    } finally {
      card.dataset.previewLoading = "false";
    }
  };

  const refreshVisiblePreviews = () => {
    if (!document.hidden) visibleCards.forEach(refreshPreview);
    window.setTimeout(refreshVisiblePreviews, 1000);
  };

  const refreshSummary = async () => {
    try {
      const response = await fetch(summaryUrl, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`Detection summary returned ${response.status}`);
      const payload = await response.json();
      renderTotals(payload);
      renderFeeds(payload);
    } catch (error) {
      console.warn("Could not refresh detection summary.", error);
    } finally {
      window.setTimeout(refreshSummary, document.hidden ? 5000 : 1000);
    }
  };

  dashboard.querySelectorAll("[data-feed-card]").forEach(registerCard);
  window.setTimeout(refreshSummary, 1000);
  window.setTimeout(refreshVisiblePreviews, 250);
})();
