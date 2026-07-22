(() => {
  const monitor = document.querySelector("[data-detections-url]");
  if (!monitor) return;

  const video = monitor.querySelector("[data-high-quality-video]");
  const player = monitor.querySelector(".video-player");
  const fullscreenButton = monitor.querySelector("[data-fullscreen-button]");
  const fullscreenLabel = monitor.querySelector("[data-fullscreen-label]");
  const canvas = monitor.querySelector(".detection-overlay");
  const lowQualityFeed = monitor.querySelector("[data-low-quality-feed]");
  const lowQualityImage = monitor.querySelector("[data-low-quality-image]");
  const lowQualityPlaceholder = monitor.querySelector("[data-low-quality-placeholder]");
  const qualityButtons = monitor.querySelectorAll("[data-quality-mode]");
  const qualityDescription = monitor.querySelector("[data-quality-description]");
  const countsContainer = monitor.querySelector("[data-detection-counts]");
  const status = monitor.querySelector("[data-detection-status]");
  const context = canvas.getContext("2d");
  let qualityMode = "low";
  let detectionStatus = "waiting";
  let latestBoxes = [];
  let previewObjectUrl = null;
  let previewLoading = false;
  let previewTimer = null;

  const fullscreenElement = () =>
    document.fullscreenElement || document.webkitFullscreenElement || null;

  const updateFullscreenButton = () => {
    const isFullscreen = fullscreenElement() === player;
    fullscreenButton.setAttribute(
      "aria-label",
      isFullscreen ? "Exit fullscreen" : "Enter fullscreen",
    );
    fullscreenLabel.textContent = isFullscreen ? "Exit full screen" : "Full screen";
  };

  const toggleFullscreen = async () => {
    try {
      if (fullscreenElement() === player) {
        const exitFullscreen = document.exitFullscreen || document.webkitExitFullscreen;
        await exitFullscreen.call(document);
      } else {
        const requestFullscreen = player.requestFullscreen || player.webkitRequestFullscreen;
        await requestFullscreen.call(player);
      }
    } catch (error) {
      console.warn("Could not change fullscreen mode.", error);
    }
  };

  const classColor = (className) => {
    let hash = 0;
    for (const character of className) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
    return `hsl(${hash % 360} 80% 58%)`;
  };

  const clearLowQualityImage = () => {
    lowQualityImage.removeAttribute("src");
    lowQualityFeed.classList.remove("low-quality-feed--loaded");
    if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
    previewObjectUrl = null;
  };

  const schedulePreviewRefresh = (delay = 1000) => {
    window.clearTimeout(previewTimer);
    previewTimer = window.setTimeout(refreshLowQualityPreview, delay);
  };

  const refreshLowQualityPreview = async () => {
    const feedUnavailable = ["paused", "reconnecting", "stale"].includes(detectionStatus);
    if (qualityMode !== "low" || document.hidden || feedUnavailable || previewLoading) {
      schedulePreviewRefresh(document.hidden ? 5000 : 1000);
      return;
    }

    const separator = monitor.dataset.previewUrl.includes("?") ? "&" : "?";
    const previewUrl = `${monitor.dataset.previewUrl}${separator}time=${Date.now()}`;
    previewLoading = true;
    try {
      const response = await fetch(previewUrl, {
        credentials: "same-origin",
        cache: "no-store",
      });
      if (response.status === 204) return;
      if (!response.ok) throw new Error(`Preview returned ${response.status}`);
      const objectUrl = URL.createObjectURL(await response.blob());
      if (qualityMode !== "low") {
        URL.revokeObjectURL(objectUrl);
        return;
      }
      const previousObjectUrl = previewObjectUrl;
      previewObjectUrl = objectUrl;
      lowQualityImage.src = objectUrl;
      lowQualityFeed.classList.add("low-quality-feed--loaded");
      if (previousObjectUrl) URL.revokeObjectURL(previousObjectUrl);
    } catch (error) {
      console.warn("Could not refresh the low-quality feed preview.", error);
    } finally {
      previewLoading = false;
      schedulePreviewRefresh(1000);
    }
  };

  const setQualityMode = (mode) => {
    if (mode === qualityMode && mode !== "low") return;
    qualityMode = mode;
    qualityButtons.forEach((button) => {
      const active = button.dataset.qualityMode === mode;
      button.classList.toggle("quality-switcher__button--active", active);
      button.setAttribute("aria-pressed", String(active));
    });

    if (mode === "high") {
      lowQualityFeed.hidden = true;
      video.hidden = false;
      canvas.hidden = false;
      qualityDescription.textContent = "Full video + sound · higher bandwidth";
      if (!video.getAttribute("src")) {
        video.src = monitor.dataset.streamUrl;
        video.load();
      }
      video.play().catch(() => {
        // Browsers may still require the user to press the native play control.
      });
      drawBoxes();
      return;
    }

    video.pause();
    video.removeAttribute("src");
    video.load();
    video.hidden = true;
    canvas.hidden = true;
    lowQualityFeed.hidden = false;
    context.clearRect(0, 0, canvas.width, canvas.height);
    qualityDescription.textContent = "Annotated 1 FPS preview · no audio";
    schedulePreviewRefresh(0);
  };

  const playerGeometry = () => {
    const width = video.clientWidth;
    const height = video.clientHeight;
    const sourceWidth = video.videoWidth || width;
    const sourceHeight = video.videoHeight || height;
    const scale = Math.min(width / sourceWidth, height / sourceHeight);
    const renderedWidth = sourceWidth * scale;
    const renderedHeight = sourceHeight * scale;
    return {
      x: (width - renderedWidth) / 2,
      y: (height - renderedHeight) / 2,
      width: renderedWidth,
      height: renderedHeight,
    };
  };

  const drawBoxes = () => {
    if (qualityMode !== "high" || video.hidden) return;
    const displayWidth = video.clientWidth;
    const displayHeight = video.clientHeight;
    if (!displayWidth || !displayHeight) return;
    const pixelRatio = window.devicePixelRatio || 1;
    canvas.width = Math.round(displayWidth * pixelRatio);
    canvas.height = Math.round(displayHeight * pixelRatio);
    canvas.style.width = `${displayWidth}px`;
    canvas.style.height = `${displayHeight}px`;
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    context.clearRect(0, 0, displayWidth, displayHeight);

    const frame = playerGeometry();
    latestBoxes.forEach((box) => {
      const color = classColor(box.class_name);
      const x = frame.x + box.x1 * frame.width;
      const y = frame.y + box.y1 * frame.height;
      const width = (box.x2 - box.x1) * frame.width;
      const height = (box.y2 - box.y1) * frame.height;
      const label = `${box.class_name} ${Math.round(box.confidence * 100)}%`;

      context.strokeStyle = color;
      context.lineWidth = 2;
      context.strokeRect(x, y, width, height);
      context.font = "600 12px DM Sans, sans-serif";
      const labelWidth = context.measureText(label).width + 12;
      const labelY = Math.max(frame.y, y - 24);
      context.fillStyle = color;
      context.fillRect(x, labelY, labelWidth, 22);
      context.fillStyle = "#10201b";
      context.fillText(label, x + 6, labelY + 15);
    });
  };

  const renderCounts = (counts) => {
    countsContainer.replaceChildren();
    const entries = Object.entries(counts);
    if (!entries.length) {
      const empty = document.createElement("p");
      empty.className = "detection-counts__empty";
      empty.textContent = "No stabilized detections yet.";
      countsContainer.append(empty);
      return;
    }

    entries.forEach(([name, count]) => {
      const row = document.createElement("div");
      row.className = "detection-count";
      const label = document.createElement("span");
      label.textContent = name;
      const value = document.createElement("strong");
      value.textContent = count;
      row.append(label, value);
      countsContainer.append(row);
    });
  };

  const renderStatus = (payload) => {
    detectionStatus = payload.status;
    if (payload.status === "paused") {
      status.textContent = "Detection paused";
      lowQualityPlaceholder.textContent = "Detection is paused";
      clearLowQualityImage();
    } else if (payload.status === "waiting") {
      status.textContent = "Waiting for the detection worker";
      lowQualityPlaceholder.textContent = "Waiting for annotated preview";
    } else if (payload.status === "reconnecting") {
      status.textContent = "Reconnecting to detection feed";
    } else if (payload.status === "stale") {
      status.textContent = "Detection data is stale";
    } else {
      status.textContent = `Detection active · ${Number(payload.target_fps).toLocaleString()} FPS`;
    }
  };

  const refreshDetections = async () => {
    try {
      const response = await fetch(monitor.dataset.detectionsUrl, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`Detection state returned ${response.status}`);
      const payload = await response.json();
      latestBoxes = payload.is_active ? payload.boxes : [];
      renderCounts(payload.stable_counts);
      renderStatus(payload);
      drawBoxes();
    } catch (error) {
      status.textContent = "Detection status unavailable";
      console.warn("Could not refresh feed detections.", error);
    } finally {
      window.setTimeout(refreshDetections, document.hidden ? 5000 : 750);
    }
  };

  qualityButtons.forEach((button) => {
    button.addEventListener("click", () => setQualityMode(button.dataset.qualityMode));
  });
  const supportsFullscreen = Boolean(
    (player.requestFullscreen || player.webkitRequestFullscreen) &&
      (document.exitFullscreen || document.webkitExitFullscreen),
  );
  fullscreenButton.hidden = !supportsFullscreen;
  fullscreenButton.addEventListener("click", toggleFullscreen);
  document.addEventListener("fullscreenchange", updateFullscreenButton);
  document.addEventListener("webkitfullscreenchange", updateFullscreenButton);
  video.addEventListener("loadedmetadata", drawBoxes);
  window.addEventListener("resize", drawBoxes);
  window.addEventListener("beforeunload", () => {
    if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
  });
  if (window.ResizeObserver) new ResizeObserver(drawBoxes).observe(video);
  schedulePreviewRefresh(0);
  refreshDetections();
})();
