// Runs inside the captured page, right before the screenshot (scrolled to the top).
// Returns every rendered element with its box in document coordinates, which equal
// screenshot pixels because the page is captured at device scale factor 1.
//
// Kept: elements that are rendered (checkVisibility, incl. ancestors' opacity/visibility)
// and at least 1x1 px after clipping by scrolling/overflow ancestors (e.g. a sidebar that
// scrolls on its own): fully hidden ones are dropped, partly hidden ones are cut to their
// visible part and marked `clipped`. Skipped: non-visual tags and SVG inner shapes.
// Noise filtering (covered boxes, single-child wrappers) is left to the DOM suggester.
() => {
  const SKIP = new Set([
    "SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "LINK", "META", "BR", "WBR",
    "SOURCE", "TRACK", "PARAM", "HEAD", "TITLE",
  ]);
  const round = (v) => Math.round(v * 10) / 10;
  const sx = window.scrollX;
  const sy = window.scrollY;
  const root = document.scrollingElement || document.documentElement;
  const docW = Math.max(root.scrollWidth, document.body ? document.body.scrollWidth : 0);
  const docH = Math.max(root.scrollHeight, document.body ? document.body.scrollHeight : 0);
  const range = document.createRange();
  const kept = new Map(); // element -> index
  const elements = [];

  // The visible region (viewport coords) that `el`'s ancestors allow its children to show
  // in, or null for "no clipping". <html> and <body> overflow applies to the window (page
  // scrolling), not to a box, so they never clip.
  const clipCache = new Map();
  const childClip = (el) => {
    if (!el || el === document.body || el === document.documentElement) return null;
    if (clipCache.has(el)) return clipCache.get(el);
    let clip = childClip(el.parentElement);
    const cs = getComputedStyle(el);
    if (cs.overflowX !== "visible" || cs.overflowY !== "visible") {
      const r = el.getBoundingClientRect();
      const own = { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
      clip = clip ? intersect(clip, own) : own;
    }
    clipCache.set(el, clip);
    return clip;
  };
  const intersect = (a, b) => ({
    left: Math.max(a.left, b.left),
    top: Math.max(a.top, b.top),
    right: Math.min(a.right, b.right),
    bottom: Math.min(a.bottom, b.bottom),
  });

  const parentIndex = (el) => {
    for (let p = el.parentElement; p; p = p.parentElement) {
      if (kept.has(p)) return kept.get(p);
    }
    return null;
  };

  const textInfo = (el) => {
    // Only the element's own text nodes, so a <div> wrapping a <p> has no text itself.
    let length = 0;
    let box = null;
    for (const node of el.childNodes) {
      if (node.nodeType !== Node.TEXT_NODE) continue;
      const text = node.textContent.trim();
      if (!text) continue;
      length += text.length;
      range.selectNodeContents(node);
      const r = range.getBoundingClientRect();
      if (r.width <= 0 || r.height <= 0) continue;
      box = box
        ? {
            left: Math.min(box.left, r.left),
            top: Math.min(box.top, r.top),
            right: Math.max(box.right, r.right),
            bottom: Math.max(box.bottom, r.bottom),
          }
        : { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
    }
    return { length, box };
  };

  const visit = (el) => {
    if (SKIP.has(el.tagName)) return;
    if (el.ownerSVGElement) return; // shapes inside an <svg>; the <svg> itself is kept
    if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) return;
    const full = el.getBoundingClientRect();
    if (full.width < 1 || full.height < 1) return;
    const cs = getComputedStyle(el);
    // Fixed elements escape their ancestors' scroll boxes.
    const clip = cs.position === "fixed" ? null : childClip(el.parentElement);
    let r = { left: full.left, top: full.top, right: full.right, bottom: full.bottom };
    if (clip) r = intersect(r, clip);
    const width = r.right - r.left;
    const height = r.bottom - r.top;
    if (width < 1 || height < 1) return; // scrolled out of view inside its container
    const x = r.left + sx;
    const y = r.top + sy;
    if (x + width <= 0 || y + height <= 0 || x >= docW || y >= docH) return;

    const item = {
      i: elements.length,
      parent: parentIndex(el),
      tag: el.tagName.toLowerCase(),
      bbox: [round(x), round(y), round(width), round(height)],
      position: cs.position,
      font_size: parseFloat(cs.fontSize) || null,
      font_weight: parseInt(cs.fontWeight, 10) || null,
    };
    if (el.id) item.id = el.id.slice(0, 100);
    const classes = [...el.classList].slice(0, 3);
    if (classes.length) item.classes = classes;
    const role = el.getAttribute("role");
    if (role) item.role = role;
    const label = el.getAttribute("aria-label");
    if (label && label.trim()) item.aria_label = label.trim().slice(0, 200);
    if (el.tagName === "INPUT") item.input_type = (el.getAttribute("type") || "text").toLowerCase();
    if (el.hasAttribute("href")) item.href = true;
    if (cs.backgroundImage && cs.backgroundImage !== "none") item.bg_image = true;
    if (width < full.width - 0.5 || height < full.height - 0.5) item.clipped = true;
    const text = textInfo(el);
    if (text.length) item.text_len = text.length;
    const tbox = text.box && (clip ? intersect(text.box, clip) : text.box);
    if (tbox && tbox.right - tbox.left >= 1 && tbox.bottom - tbox.top >= 1) {
      item.text_bbox = [
        round(tbox.left + sx),
        round(tbox.top + sy),
        round(tbox.right - tbox.left),
        round(tbox.bottom - tbox.top),
      ];
    }
    kept.set(el, item.i);
    elements.push(item);
  };

  if (document.body) {
    visit(document.body);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
    for (let el = walker.nextNode(); el; el = walker.nextNode()) visit(el);
  }

  return {
    version: 1,
    page: { width: docW, height: docH },
    viewport: { width: window.innerWidth, height: window.innerHeight },
    scroll: { x: sx, y: sy },
    elements,
  };
}
