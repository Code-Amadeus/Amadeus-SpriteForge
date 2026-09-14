/* PNG uses the browser image decoder; KTX2 uses the same pinned Pixi/Basis loader as Amadeus. */
window.SpriteForgeMedia = (() => {
  let app, sprite, ready;
  let generation = 0;
  let busy = false;
  const cache = new Map();
  const bytes = new Map();
  const image = () => document.getElementById("frame");
  const holder = () => document.getElementById("ktxStage");
  const urlFor = (path) => "/frame?path=" + encodeURIComponent(path);
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.onload = resolve;
      script.onerror = () => reject(new Error("Cannot load " + src));
      document.head.appendChild(script);
    });
  }
  function initialize() {
    if (!ready) ready = (async () => {
      await loadScript("/static/vendor/pixi.min.js");
      await loadScript("/static/vendor/pixi-basis-ktx2.global.js");
      app = new PIXI.Application({ width: 512, height: 512, backgroundAlpha: 0, preserveDrawingBuffer: true });
      holder().appendChild(app.view);
      sprite = new PIXI.Sprite();
      sprite.anchor.set(.5);
      app.stage.addChild(sprite);
      await PixiBasisKtx2Shim.KTX2Parser.loadTranscoder("/static/vendor/basis_transcoder.js", "/static/vendor/basis_transcoder.wasm");
      await PIXI.Assets.init({ texturePreference: { format: ["ktx2"] } });
    })();
    return ready;
  }
  async function show(path) {
    const token = ++generation;
    busy = true;
    try {
      if (!path.toLowerCase().endsWith(".ktx2")) {
        image().style.display = "";
        holder().style.display = "none";
        image().src = urlFor(path);
        return;
      }
      image().style.display = "none";
      document.getElementById("mouthCanvas").style.display = "none";
      holder().style.display = "grid";
      await initialize();
      const url = urlFor(path);
      let texture = cache.get(url);
      if (!texture) {
        const loaded = await PIXI.Assets.load({ src: url, format: "ktx2", loadParser: "loadKTX2" });
        const raw = Array.isArray(loaded) ? loaded[0] : loaded;
        texture = raw.baseTexture ? raw : new PIXI.Texture(raw);
        cache.set(url, texture);
        // Conservative upper bound independent of actual GPU compression format.
        bytes.set(url, texture.width * texture.height * 4);
      }
      if (token !== generation) return;
      cache.delete(url); cache.set(url, texture);
      const width = Math.max(1, holder().clientWidth);
      const height = Math.max(1, holder().clientHeight);
      app.renderer.resize(width, height);
      sprite.texture = texture;
      sprite.scale.set(Math.min(width / texture.width, height / texture.height));
      sprite.position.set(width / 2, height / 2);
      app.renderer.render(app.stage);
      holder().dataset.frame = path;
      holder().dataset.width = String(texture.width);
      // Keep at most 12 frames / 64 MiB estimated decoded footprint, plus the current frame.
      let total = [...bytes.values()].reduce((a, b) => a + b, 0);
      for (const key of [...cache.keys()]) {
        if (token !== generation) break;
        if (cache.size <= 12 && total <= 64 * 1024 * 1024) break;
        if (key === url || cache.get(key) === sprite.texture) continue;
        total -= bytes.get(key) || 0;
        cache.delete(key); bytes.delete(key);
        await PIXI.Assets.unload(key);
      }
    } catch (error) {
      if (token === generation) document.getElementById("now").textContent = "Preview failed: " + error.message;
    } finally {
      if (token === generation) busy = false;
    }
  }
  return { show, get busy() { return busy; } };
})();
