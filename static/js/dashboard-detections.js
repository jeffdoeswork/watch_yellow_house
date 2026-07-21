(() => {
  const dashboard = document.querySelector("[data-dashboard-detections-url]");
  if (!dashboard) return;

  const totalsContainer = dashboard.querySelector("[data-dashboard-totals]");
  const feedsContainer = dashboard.querySelector("[data-dashboard-feeds]");
  const summaryUrl = dashboard.dataset.dashboardDetectionsUrl;

  const element = (tagName, className, text) => {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
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

  const renderFeeds = (payload) => {
    if (!feedsContainer) return;
    feedsContainer.replaceChildren();

    payload.feeds.forEach((feed) => {
      const card = element("a", "feed-summary-card");
      card.href = feed.detail_url;

      const header = element("span", "feed-summary-card__header");
      const identity = element("span");
      identity.append(
        element("strong", "", feed.name),
        element("small", "", feed.connection_host),
      );
      const statusText = feed.is_active ? "Detecting" : feed.has_detection ? "Stale" : "Waiting";
      const status = element(
        "span",
        `feed-summary-card__status${feed.is_active ? " feed-summary-card__status--online" : ""}`,
        statusText,
      );
      header.append(identity, status);

      const counts = element("span", "feed-summary-card__counts");
      const entries = Object.entries(feed.stable_counts);
      if (!entries.length) {
        counts.append(element("span", "", "No stabilized detections"));
      } else {
        entries.forEach(([name, count]) => {
          const item = element("span");
          item.append(element("b", "", String(count)), ` ${name}`);
          counts.append(item);
        });
      }
      card.append(header, counts);
      feedsContainer.append(card);
    });
  };

  const refresh = async () => {
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
      window.setTimeout(refresh, document.hidden ? 5000 : 1000);
    }
  };

  window.setTimeout(refresh, 1000);
})();
