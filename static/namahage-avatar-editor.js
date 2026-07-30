(function () {
  "use strict";

  const sourceSrc = "/static/images/namahage/namahage-room-9x16.png";
  const canvas = document.getElementById("maskCanvas");
  const select = document.getElementById("shapeSelect");
  const statusBox = document.getElementById("statusBox");
  const renderButton = document.getElementById("renderButton");
  const resetButton = document.getElementById("resetButton");
  const preview = document.getElementById("avatarPreview");
  const ctx = canvas.getContext("2d");
  const image = new Image();

  const defaults = [
    {
      id: "lowerTeeth",
      label: "下歯列",
      target: "jaw",
      mode: "include",
      color: "#ffd166",
      points: [[0.342, 0.585], [0.660, 0.585], [0.675, 0.675], [0.625, 0.710], [0.375, 0.710], [0.325, 0.675]],
    },
    {
      id: "leftLowerFang",
      label: "左下牙",
      target: "jaw",
      mode: "include",
      color: "#f78c6b",
      points: [[0.350, 0.558], [0.388, 0.705], [0.337, 0.745], [0.318, 0.690]],
    },
    {
      id: "rightLowerFang",
      label: "右下牙",
      target: "jaw",
      mode: "include",
      color: "#f78c6b",
      points: [[0.655, 0.558], [0.690, 0.690], [0.664, 0.745], [0.614, 0.705]],
    },
    {
      id: "lowerLip",
      label: "下唇・下顎",
      target: "jaw",
      mode: "include",
      color: "#ef476f",
      points: [[0.245, 0.660], [0.315, 0.625], [0.405, 0.650], [0.500, 0.668], [0.595, 0.650], [0.690, 0.625], [0.758, 0.660], [0.724, 0.760], [0.650, 0.806], [0.505, 0.830], [0.352, 0.806], [0.272, 0.760]],
    },
    {
      id: "leftUpperFangCut",
      label: "除外: 左上牙",
      target: "jaw",
      mode: "exclude",
      color: "#5cc8ff",
      points: [[0.190, 0.405], [0.330, 0.405], [0.330, 0.700], [0.230, 0.700]],
    },
    {
      id: "rightUpperFangCut",
      label: "除外: 右上牙",
      target: "jaw",
      mode: "exclude",
      color: "#5cc8ff",
      points: [[0.670, 0.405], [0.812, 0.405], [0.770, 0.700], [0.670, 0.700]],
    },
    {
      id: "upperTeethCut",
      label: "除外: 上歯列",
      target: "jaw",
      mode: "exclude",
      color: "#5cc8ff",
      points: [[0.380, 0.505], [0.620, 0.505], [0.620, 0.565], [0.380, 0.565]],
    },
    {
      id: "knifeBlade",
      label: "包丁",
      target: "knife",
      mode: "include",
      color: "#8ecae6",
      points: [[0.064, 0.405], [0.220, 0.378], [0.150, 0.925], [0.012, 0.885]],
    },
    {
      id: "leftHorn",
      label: "左角",
      target: "horns",
      mode: "include",
      color: "#c77dff",
      points: [[0.105, 0.035], [0.192, 0.020], [0.330, 0.270], [0.250, 0.300]],
    },
    {
      id: "rightHorn",
      label: "右角",
      target: "horns",
      mode: "include",
      color: "#c77dff",
      points: [[0.795, 0.020], [0.885, 0.035], [0.755, 0.300], [0.670, 0.270]],
    },
  ];

  let shapes = clone(defaults);
  let activeShapeId = shapes[0].id;
  let activePoint = null;

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function setStatus(text) {
    statusBox.textContent = text;
  }

  function pointToPx(point) {
    return [point[0] * canvas.width, point[1] * canvas.height];
  }

  function pxToPoint(x, y) {
    return [
      Math.max(0, Math.min(1, x / canvas.width)),
      Math.max(0, Math.min(1, y / canvas.height)),
    ];
  }

  function eventToCanvas(event) {
    const rect = canvas.getBoundingClientRect();
    return [
      (event.clientX - rect.left) * (canvas.width / rect.width),
      (event.clientY - rect.top) * (canvas.height / rect.height),
    ];
  }

  function populateSelect() {
    select.innerHTML = "";
    shapes.forEach((shape) => {
      const option = document.createElement("option");
      option.value = shape.id;
      const targetLabel = shape.target === "knife" ? "包丁" : shape.target === "horns" ? "角" : "下顎";
      option.textContent = `${targetLabel} / ${shape.mode === "exclude" ? "除外" : "含める"} / ${shape.label}`;
      select.appendChild(option);
    });
    select.value = activeShapeId;
  }

  function drawShape(shape) {
    const selected = shape.id === activeShapeId;
    ctx.save();
    ctx.beginPath();
    shape.points.forEach((point, index) => {
      const [x, y] = pointToPx(point);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fillStyle = shape.target === "knife"
      ? "rgba(142, 202, 230, 0.22)"
      : shape.target === "horns"
        ? "rgba(199, 125, 255, 0.22)"
        : shape.mode === "exclude" ? "rgba(92, 200, 255, 0.18)" : "rgba(239, 71, 111, 0.18)";
    ctx.strokeStyle = shape.color;
    ctx.lineWidth = selected ? 5 : 3;
    ctx.fill();
    ctx.stroke();

    shape.points.forEach((point, index) => {
      const [x, y] = pointToPx(point);
      ctx.beginPath();
      ctx.arc(x, y, selected ? 8 : 6, 0, Math.PI * 2);
      ctx.fillStyle = shape.color;
      ctx.fill();
      ctx.fillStyle = "#111";
      ctx.font = "18px Consolas, monospace";
      ctx.fillText(String(index + 1), x + 10, y - 8);
    });
    ctx.restore();
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "rgba(0, 0, 0, 0.18)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    shapes.forEach(drawShape);
  }

  function hitTest(x, y) {
    let best = null;
    let bestDistance = 18;
    shapes.forEach((shape) => {
      shape.points.forEach((point, pointIndex) => {
        const [px, py] = pointToPx(point);
        const distance = Math.hypot(px - x, py - y);
        if (distance < bestDistance) {
          bestDistance = distance;
          best = { shapeId: shape.id, pointIndex };
        }
      });
    });
    return best;
  }

  function getActiveShape() {
    return shapes.find((shape) => shape.id === activeShapeId);
  }

  canvas.addEventListener("pointerdown", (event) => {
    const [x, y] = eventToCanvas(event);
    const hit = hitTest(x, y);
    if (hit) {
      activeShapeId = hit.shapeId;
      select.value = activeShapeId;
      activePoint = hit;
      canvas.setPointerCapture(event.pointerId);
      draw();
    }
  });

  canvas.addEventListener("pointermove", (event) => {
    if (!activePoint) return;
    const [x, y] = eventToCanvas(event);
    const shape = shapes.find((item) => item.id === activePoint.shapeId);
    shape.points[activePoint.pointIndex] = pxToPoint(x, y);
    draw();
  });

  canvas.addEventListener("pointerup", () => {
    activePoint = null;
  });

  canvas.addEventListener("dblclick", (event) => {
    const [x, y] = eventToCanvas(event);
    const shape = getActiveShape();
    shape.points.push(pxToPoint(x, y));
    draw();
  });

  window.addEventListener("keydown", (event) => {
    if (!activePoint || (event.key !== "Delete" && event.key !== "Backspace")) return;
    const shape = shapes.find((item) => item.id === activePoint.shapeId);
    if (shape.points.length <= 3) return;
    shape.points.splice(activePoint.pointIndex, 1);
    activePoint = null;
    draw();
  });

  select.addEventListener("change", () => {
    activeShapeId = select.value;
    activePoint = null;
    draw();
  });

  resetButton.addEventListener("click", () => {
    shapes = clone(defaults);
    activeShapeId = shapes[0].id;
    activePoint = null;
    populateSelect();
    draw();
    setStatus("reset");
  });

  renderButton.addEventListener("click", async () => {
    setStatus("writing...");
    renderButton.disabled = true;
    try {
      const response = await fetch("/api/namahage-avatar/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shapes }),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || "render failed");
      setStatus(JSON.stringify(result, null, 2));
      preview.src = `/avatar/namahage?debug=1&mic=0&assetv=${encodeURIComponent(result.assetv)}`;
    } catch (error) {
      setStatus(`error: ${error.message}`);
    } finally {
      renderButton.disabled = false;
    }
  });

  image.onload = () => {
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    populateSelect();
    draw();
    setStatus("ready");
  };
  image.src = sourceSrc;
})();
