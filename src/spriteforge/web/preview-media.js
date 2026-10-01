/* PNG uses the browser image decoder; KTX2 uses the same pinned Pixi/Basis loader as Amadeus. */
(() => {
let dependencies;
function create(root = document, options = {}) {
  let app, sprite, ready;
  let observer, disposed = false, cancelImage;
  const q = (id) => root.querySelector('#' + id);
  let generation = 0;
  let busy = false;
  const cache = new Map();
  const bytes = new Map();
  const image = () => q("frame");
  const holder = () => q("ktxStage");
  const urlFor = (path) => "/frame?path=" + encodeURIComponent(path);
  function fitTexture() {
    if(disposed || !app || !sprite || !cache.size) return;
    const width=holder().clientWidth, height=holder().clientHeight;
    if(!width || !height) return;
    app.renderer.resize(width,height);
    sprite.scale.set(Math.min(width/sprite.texture.width,height/sprite.texture.height));
    sprite.position.set(width/2,height/2);
    app.renderer.render(app.stage);
  }
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
      if (!dependencies) dependencies = (async () => {
        if (!window.PIXI) await loadScript("/static/vendor/pixi.min.js");
        if (!window.PixiBasisKtx2Shim) await loadScript("/static/vendor/pixi-basis-ktx2.global.js");
        await PixiBasisKtx2Shim.KTX2Parser.loadTranscoder("/static/vendor/basis_transcoder.js", "/static/vendor/basis_transcoder.wasm");
        await PIXI.Assets.init({ texturePreference: { format: ["ktx2"] } });
      })();
      await dependencies;
      if (disposed) return;
      app = new PIXI.Application({ width: 512, height: 512, backgroundAlpha: 0, preserveDrawingBuffer: true });
      holder().appendChild(app.view);
      sprite = new PIXI.Sprite();
      sprite.anchor.set(.5);
      app.stage.addChild(sprite);
      observer = new ResizeObserver(fitTexture); observer.observe(holder());
    })();
    return ready;
  }
  async function show(path) {
    if (disposed) return false;
    if (cancelImage) cancelImage();
    const token = ++generation;
    busy = true;
    try {
      if (!path.toLowerCase().endsWith(".ktx2")) {
        image().style.display = "";
        holder().style.display = "none";
        const img = image();
        await new Promise((resolve, reject) => {
          const finish = (error) => { img.onload = img.onerror = null; cancelImage = null; error ? reject(error) : resolve(); };
          cancelImage = () => finish();
          img.onload = () => finish(); img.onerror = () => finish(new Error("Cannot decode frame"));
          img.src = urlFor(path);
        });
        if(disposed || token !== generation) return false;
        img.dataset.frame = path;
        return true;
      }
      image().style.display = "none";
      if(q("mouthCanvas")) q("mouthCanvas").style.display = "none";
      holder().style.display = "grid";
      await initialize();
      if(disposed || token !== generation) return false;
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
      if (disposed || token !== generation) { if (disposed) await PIXI.Assets.unload(url); return false; }
      cache.delete(url); cache.set(url, texture);
      sprite.texture = texture;
      fitTexture();
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
      return true;
    } catch (error) {
      if (!disposed && token === generation) {
        if(options.onError)options.onError(error);
        else if(q("now"))q("now").textContent = "Preview failed: " + error.message;
      }
      return false;
    } finally {
      if (token === generation) busy = false;
    }
  }
  return { show, get busy() { return busy; }, dispose() {
    disposed = true; generation++; if(cancelImage) cancelImage(); busy = false;
    if(observer) observer.disconnect();
    if(app) app.destroy(true, {children:true,texture:false,baseTexture:false});
    for(const key of cache.keys()) PIXI.Assets.unload(key);
    cache.clear(); bytes.clear();
  } };
}
window.SpriteForgeMedia = Object.assign(create(), {create});
})();
