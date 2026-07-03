/*
 * The vendored SheetJS build parses the <borders> section of styles.xml but
 * discards each side's style/color (see its "case '<left':...break;" style
 * handling) - cell.s never carries border info. To render real cell borders
 * we read the raw xlsx zip ourselves and pull border definitions straight
 * out of xl/styles.xml + the target sheet's XML.
 */
(function () {
  function u16(dv, off) { return dv.getUint16(off, true); }
  function u32(dv, off) { return dv.getUint32(off, true); }

  async function inflateRaw(bytes) {
    const ds = new DecompressionStream("deflate-raw");
    const stream = new Blob([bytes]).stream().pipeThrough(ds);
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }

  function findEOCD(bytes) {
    const start = Math.max(0, bytes.length - 65557);
    for (let i = bytes.length - 22; i >= start; i--) {
      if (bytes[i] === 0x50 && bytes[i + 1] === 0x4b && bytes[i + 2] === 0x05 && bytes[i + 3] === 0x06) return i;
    }
    return -1;
  }

  function parseZipEntries(bytes) {
    const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const eocd = findEOCD(bytes);
    if (eocd < 0) throw new Error("zip EOCD not found");
    const cdCount = u16(dv, eocd + 10);
    const cdOffset = u32(dv, eocd + 16);
    const entries = {};
    let off = cdOffset;
    const dec = new TextDecoder();
    for (let i = 0; i < cdCount; i++) {
      if (u32(dv, off) !== 0x02014b50) break;
      const method = u16(dv, off + 10);
      const compSize = u32(dv, off + 20);
      const nameLen = u16(dv, off + 28);
      const extraLen = u16(dv, off + 30);
      const commentLen = u16(dv, off + 32);
      const lhOffset = u32(dv, off + 42);
      const name = dec.decode(bytes.subarray(off + 46, off + 46 + nameLen));
      entries[name] = { method, compSize, lhOffset };
      off += 46 + nameLen + extraLen + commentLen;
    }
    return { dv, entries };
  }

  async function readZipFile(bytes, dv, entry) {
    const off = entry.lhOffset;
    const nameLen = u16(dv, off + 26);
    const extraLen = u16(dv, off + 28);
    const dataStart = off + 30 + nameLen + extraLen;
    const raw = bytes.subarray(dataStart, dataStart + entry.compSize);
    if (entry.method === 0) return raw;
    if (entry.method === 8) return inflateRaw(raw);
    throw new Error("unsupported zip compression method " + entry.method);
  }

  function firstChildByTag(el, tag) {
    for (const c of el.children) if (c.tagName === tag || c.tagName.endsWith(":" + tag)) return c;
    return null;
  }
  function childrenByTag(el, tag) {
    const out = [];
    for (const c of el.children) if (c.tagName === tag || c.tagName.endsWith(":" + tag)) out.push(c);
    return out;
  }

  function borderSideCss(sideEl) {
    if (!sideEl) return null;
    const style = sideEl.getAttribute("style");
    if (!style || style === "none") return null;
    const colorEl = firstChildByTag(sideEl, "color");
    let rgb = "000000";
    if (colorEl) {
      const argb = colorEl.getAttribute("rgb");
      if (argb) rgb = argb.slice(-6);
    }
    const width = /^(thick|medium)/.test(style) ? "2px" : "1px";
    return `${width} solid #${rgb}`;
  }

  function parseStylesXml(xml) {
    const doc = new DOMParser().parseFromString(xml, "application/xml");
    const bordersRoot = doc.getElementsByTagName("borders")[0];
    const borders = bordersRoot ? childrenByTag(bordersRoot, "border").map((b) => ({
      left: borderSideCss(firstChildByTag(b, "left")),
      right: borderSideCss(firstChildByTag(b, "right")),
      top: borderSideCss(firstChildByTag(b, "top")),
      bottom: borderSideCss(firstChildByTag(b, "bottom")),
    })) : [];
    const cellXfsRoot = doc.getElementsByTagName("cellXfs")[0];
    const cellXfs = cellXfsRoot ? childrenByTag(cellXfsRoot, "xf").map((xf) => ({
      borderId: xf.hasAttribute("borderId") ? parseInt(xf.getAttribute("borderId"), 10) : 0,
    })) : [];
    return { borders, cellXfs };
  }

  function resolveSheetTarget(workbookXml, relsXml, sheetName) {
    const wbDoc = new DOMParser().parseFromString(workbookXml, "application/xml");
    const sheetsRoot = wbDoc.getElementsByTagName("sheets")[0];
    if (!sheetsRoot) return null;
    const sheetEl = childrenByTag(sheetsRoot, "sheet").find((s) => s.getAttribute("name") === sheetName);
    if (!sheetEl) return null;
    const rid = sheetEl.getAttribute("r:id") || sheetEl.getAttribute("id");
    if (!rid) return null;
    const relsDoc = new DOMParser().parseFromString(relsXml, "application/xml");
    const relEl = Array.from(relsDoc.getElementsByTagName("Relationship")).find((r) => r.getAttribute("Id") === rid);
    if (!relEl) return null;
    let target = relEl.getAttribute("Target") || "";
    target = target.replace(/^\.?\//, "");
    if (!target.startsWith("xl/")) target = "xl/" + target;
    return target;
  }

  function parseSheetCellStyles(sheetXml) {
    const styleByAddr = {};
    const re = /<c\s[^>]*\br="([A-Z]+\d+)"[^>]*\/?>|<c\s[^>]*\br="([A-Z]+\d+)"[^>]*>/g;
    const sRe = /\bs="(\d+)"/;
    let m;
    while ((m = re.exec(sheetXml))) {
      const tagEnd = sheetXml.indexOf(">", m.index);
      const tag = sheetXml.slice(m.index, tagEnd + 1);
      const sMatch = sRe.exec(tag);
      if (sMatch) styleByAddr[m[1] || m[2]] = parseInt(sMatch[1], 10);
    }
    return styleByAddr;
  }

  /** Returns { "A1": "border-top:1px solid #000000;...", ... } or {} on any failure. */
  async function extract(bytes, sheetName) {
    try {
      if (typeof DecompressionStream === "undefined") return {};
      const { dv, entries } = parseZipEntries(bytes);
      const need = ["xl/styles.xml", "xl/workbook.xml", "xl/_rels/workbook.xml.rels"];
      if (need.some((n) => !entries[n])) return {};
      const [stylesBuf, wbBuf, relsBuf] = await Promise.all(need.map((n) => readZipFile(bytes, dv, entries[n])));
      const dec = new TextDecoder();
      const target = resolveSheetTarget(dec.decode(wbBuf), dec.decode(relsBuf), sheetName);
      if (!target || !entries[target]) return {};
      const sheetBuf = await readZipFile(bytes, dv, entries[target]);
      const sheetXml = dec.decode(sheetBuf);

      const { borders, cellXfs } = parseStylesXml(dec.decode(stylesBuf));
      const styleByAddr = parseSheetCellStyles(sheetXml);

      const out = {};
      Object.keys(styleByAddr).forEach((addr) => {
        const xf = cellXfs[styleByAddr[addr]];
        const b = xf ? borders[xf.borderId] : null;
        if (!b) return;
        const parts = [];
        if (b.top) parts.push(`border-top:${b.top}`);
        if (b.bottom) parts.push(`border-bottom:${b.bottom}`);
        if (b.left) parts.push(`border-left:${b.left}`);
        if (b.right) parts.push(`border-right:${b.right}`);
        if (parts.length) out[addr] = parts.join(";");
      });
      return out;
    } catch (err) {
      console.warn("XlsxBorders.extract failed:", err);
      return {};
    }
  }

  window.XlsxBorders = { extract };
})();
