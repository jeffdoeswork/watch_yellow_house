(() => {
  const monitor = document.querySelector("[data-detections-url]");
  if (!monitor) return;

  const video = monitor.querySelector("video");
  const canvas = monitor.querySelector(".detection-overlay");
  const countsContainer = monitor.querySelector("[data-detection-counts]");
  const status = monitor.querySelector("[data-detection-status]");
  const context = canvas.getContext("2d");
  let latestBoxes = [];

  const classColor = (className) => {
    let hash = 0;
    for (const character of className) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
    return `hsl(${hash % 360} 80% 58%)`;
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
    const displayWidth = video.clientWidth;
    const displayHeight = video.clientHeight;
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
    if (payload.status === "paused") {
      status.textContent = "Detection paused";
    } else if (payload.status === "waiting") {
      status.textContent = "Waiting for the detection worker";
    } else if (payload.status === "reconnecting") {
      status.textContent = "Reconnecting to detection feed";
    } else if (payload.status === "stale") {
      status.textContent = "Detection data is stale";
    } else {
      status.textContent = `Detection active · frame ${payload.frame_number} · ${payload.inference_ms.toFixed(1)}ms`;
    }
  };

  const refresh = async () => {
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
      window.setTimeout(refresh, document.hidden ? 5000 : 750);
    }
  };

  video.addEventListener("loadedmetadata", drawBoxes);
  window.addEventListener("resize", drawBoxes);
  if (window.ResizeObserver) new ResizeObserver(drawBoxes).observe(video);
  refresh();
})();
