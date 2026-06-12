/*
 * DDAC 2026 — Peta Anomali Anggaran · loader embed
 *
 * Cara pakai di web mana pun (CSS/JS terisolasi via iframe di shadow DOM):
 *
 *   <script src="https://HOST/embed.js"></script>
 *   <ddac-anomaly-map src="https://HOST/" height="640"></ddac-anomaly-map>
 *
 * Atribut:
 *   src    — base URL hasil build (default: lokasi embed.js ini)
 *   height — tinggi dalam px (default 640)
 *   mode   — "map" (default) atau "pipeline"
 */
(function () {
  if (customElements.get("ddac-anomaly-map")) return;

  function baseFromScript() {
    var s = document.currentScript;
    if (s && s.src) return s.src.replace(/embed\.js(\?.*)?$/, "");
    return "./";
  }
  var DEFAULT_BASE = baseFromScript();

  class DdacAnomalyMap extends HTMLElement {
    connectedCallback() {
      var base = this.getAttribute("src") || DEFAULT_BASE;
      if (base.slice(-1) !== "/") base += "/";
      var height = this.getAttribute("height") || "640";
      var view = this.getAttribute("mode") === "pipeline" ? "&view=pipeline" : "";

      var root = this.attachShadow({ mode: "open" });
      var wrap = document.createElement("div");
      wrap.style.cssText =
        "width:100%;height:" + height + "px;border-radius:14px;overflow:hidden;" +
        "border:1px solid rgba(120,140,180,.25);background:#0a0e1a";
      var iframe = document.createElement("iframe");
      iframe.src = base + "index.html?embed=1" + view;
      iframe.setAttribute("title", "DDAC 2026 — Peta Anomali Anggaran");
      iframe.setAttribute("loading", "lazy");
      iframe.style.cssText = "width:100%;height:100%;border:0;display:block";
      wrap.appendChild(iframe);
      root.appendChild(wrap);
    }
  }

  customElements.define("ddac-anomaly-map", DdacAnomalyMap);
})();
