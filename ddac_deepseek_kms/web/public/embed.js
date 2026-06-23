/*
 * SENTINEL — Spending Intelligence for National Alignment Review · loader embed
 *
 * Cara pakai di web mana pun (CSS/JS terisolasi via iframe di shadow DOM):
 *
 *   <script src="https://HOST/embed.js"></script>
 *   <sentinel-map src="https://HOST/" height="640"></sentinel-map>
 *
 * Atribut:
 *   src    — base URL hasil build (default: lokasi embed.js ini)
 *   height — tinggi dalam px (default 640)
 *   mode   — "map" (default) atau "pipeline"
 */
(function () {
  if (customElements.get("sentinel-map")) return;

  function baseFromScript() {
    var s = document.currentScript;
    if (s && s.src) return s.src.replace(/embed\.js(\?.*)?$/, "");
    return "./";
  }
  var DEFAULT_BASE = baseFromScript();

  class SentinelMap extends HTMLElement {
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
      iframe.setAttribute("title", "SENTINEL — Spending Intelligence for National Alignment Review");
      iframe.setAttribute("loading", "lazy");
      iframe.style.cssText = "width:100%;height:100%;border:0;display:block";
      wrap.appendChild(iframe);
      root.appendChild(wrap);
    }
  }

  customElements.define("sentinel-map", SentinelMap);
})();
