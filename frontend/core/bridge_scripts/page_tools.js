(function () {
  if (window.__agent) return;

  const S = { next: 1, els: new Map(), ids: new WeakMap() };

  const SELECTOR = [
    'a[href]', 'button', 'input:not([type="hidden"])', 'textarea', 'select', 'summary',
    '[role="button"]', '[role="link"]', '[role="tab"]', '[role="menuitem"]',
    '[role="checkbox"]', '[role="switch"]', '[role="option"]', '[role="radio"]', '[role="treeitem"]',
    '[role="combobox"]', '[role="slider"]', '[role="menuitemcheckbox"]', '[contenteditable="true"]', 'canvas',
    'h1', 'h2', 'h3', 'h4', 'p', 'li',
  ].join(",");

  function clean(s, n) {
    s = (s || "").replace(/\s+/g, " ").trim();
    return s.length > n ? s.slice(0, n - 1) + "…" : s;
  }

  function isVisible(el, r) {
    if (r.width < 2 || r.height < 2) return false;
    const s = getComputedStyle(el);
    return s.visibility !== "hidden" && s.display !== "none" && parseFloat(s.opacity) !== 0;
  }

  function regionOf(el) {
    if (el.closest('dialog, [role="dialog"], [aria-modal="true"]')) return "dialog";
    if (el.closest('nav, [role="navigation"]')) return "nav";
    if (el.closest('header, [role="banner"]')) return "header";
    if (el.closest('footer, [role="contentinfo"]')) return "footer";
    if (el.closest('aside, [role="complementary"]')) return "aside";
    return "main";
  }

  function idFor(el) {
    let id = S.ids.get(el);
    if (!id) {
      id = "e" + S.next++;
      S.ids.set(el, id);
      S.els.set(id, el);
    }
    return id;
  }

  function kindOf(el) {
    const tag = el.tagName.toLowerCase();
    const role = (el.getAttribute("role") || "").toLowerCase();
    if (/^h[1-4]$/.test(tag)) return tag;
    if (tag === "a" && el.hasAttribute("href")) return "link";
    if (tag === "button" || tag === "summary" || role === "button") return "button";
    if (tag === "input") {
      const t = (el.type || "text").toLowerCase();
      if (["button", "submit", "reset", "image"].includes(t)) return "button";
      if (t === "checkbox" || t === "radio") return t;
      return "input";
    }
    if (tag === "textarea") return "textarea";
    if (tag === "select") return "select";
    if (role === "link") return "link";
    if (role === "tab") return "tab";
    if (role === "menuitem") return "menuitem";
    if (role === "checkbox" || role === "switch" || role === "menuitemcheckbox") return "checkbox";
    if (role === "radio") return "radio";
    if (role === "option") return "option";
    if (role === "treeitem") return "menuitem";
    if (role === "combobox") return "button";
    if (role === "slider") return "slider";
    if (tag === "canvas") return "canvas";
    if (el.isContentEditable) return "textarea";
    return "text";
  }

  function stateOf(el) {
    const out = [];
    const a = function (n) { return el.getAttribute(n); };
    if (a("aria-expanded") === "true") out.push("expanded");
    if (a("aria-expanded") === "false") out.push("collapsed");
    if (a("aria-selected") === "true") out.push("selected");
    if (a("aria-pressed") === "true") out.push("pressed");
    if (a("aria-current") && a("aria-current") !== "false") out.push("current");
    if (a("aria-invalid") === "true") out.push("invalid");
    if (el.required || a("aria-required") === "true") out.push("required");
    if (el === document.activeElement) out.push("focused");
    return out;
  }

  function labelOf(el, kind) {
    let t = el.getAttribute("aria-label") || "";
    if (!t && el.getAttribute("aria-labelledby")) {
      t = el.getAttribute("aria-labelledby").split(/\s+/).map(function (id) {
        const n = document.getElementById(id);
        return n ? n.innerText : "";
      }).join(" ");
    }
    if (!t && el.labels && el.labels[0]) t = el.labels[0].innerText;
    if (!t && kind !== "input" && kind !== "textarea" && kind !== "select") {
      t = el.innerText || el.value || "";
    }
    if (!t) {
      const img = el.querySelector("img[alt]");
      if (img) t = img.alt;
    }
    if (!t) t = el.getAttribute("title") || el.getAttribute("name") || "";
    return t;
  }

  function hrefOf(el) {
    try {
      const u = new URL(el.href);
      const s = u.origin === location.origin ? u.pathname + u.search : u.host + u.pathname;
      return clean(s, 90);
    } catch (e) {
      return "";
    }
  }

  function collect(maxEls) {
    const out = [];
    let truncated = false;

    for (const el of document.querySelectorAll(SELECTOR)) {
      if (out.length >= maxEls) { truncated = true; break; }

      const r = el.getBoundingClientRect();
      if (!isVisible(el, r)) continue;

      const kind = kindOf(el);
      const isText = kind === "text" || /^h[1-4]$/.test(kind);
      if (kind === "canvas" && (r.width < 80 || r.height < 80)) continue;   // tracking/chhote canvas chhodo

      if (isText) {
        if (el.closest('a, button, [role="button"]')) continue;
        if (kind === "text" && el.querySelector("p, li, h1, h2, h3, h4")) continue;
      }

      const item = {
        i: out.length,
        kind: kind,
        region: regionOf(el),
        inView: r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth,
        y: Math.round(r.top + scrollY),
      };

      if (isText) {
        item.text = clean(el.innerText, 160);
        if (!/[A-Za-z0-9]/.test(item.text)) continue;
      } else {
        item.id = idFor(el);
        item.text = kind === "canvas" ? Math.round(r.width) + "x" + Math.round(r.height) : clean(labelOf(el, kind), 80);
        const st = stateOf(el);
        if (st.length) item.state = st;
        if (kind === "link") item.href = hrefOf(el);
        if (kind === "input" || kind === "textarea" || kind === "select") {
          const t = (el.type || "text").toLowerCase();
          item.inputType = t;
          if (el.placeholder) item.placeholder = clean(el.placeholder, 50);
          if (t === "password") item.secret = true;           // password ki value kabhi nahi
          else if (el.value) item.value = clean(el.value, 60);
        }
        if (kind === "checkbox" || kind === "radio") {
          item.checked = typeof el.checked === "boolean" ? el.checked : el.getAttribute("aria-checked") === "true";
        }
        if (el.disabled) item.disabled = true;
      }
      out.push(item);
    }
    return { items: out, truncated: truncated };
  }

  function snapshot(maxEls) {
    const c = collect(maxEls);
    return {
      url: location.href,
      title: document.title,
      scrollY: Math.round(scrollY),
      scrollHeight: Math.round(document.documentElement.scrollHeight),
      viewportHeight: innerHeight,
      selection: clean(String(getSelection()), 300),
      total: c.items.length,
      truncated: c.truncated,
      elements: c.items,
    };
  }

  // ---- network: page ne kaunsi API (fetch/XHR) mangwayi, aur unka JSON seedha padhna ----
  function apiList(limit) {
    const seen = {};
    const out = [];
    const list = performance.getEntriesByType("resource");
    for (let i = list.length - 1; i >= 0 && out.length < (limit || 25); i--) {
      const e = list[i];
      if (e.initiatorType !== "fetch" && e.initiatorType !== "xmlhttprequest") continue;
      let u;
      try { u = new URL(e.name); } catch (x) { continue; }
      const key = u.origin + u.pathname;
      if (seen[key]) continue;
      seen[key] = 1;
      out.push({ url: clean(u.origin === location.origin ? u.pathname + u.search : u.href, 140), kb: Math.round((e.transferSize || 0) / 102.4) / 10 });
    }
    return out;
  }

  function shrink(v, depth) {
    if (v === null || typeof v !== "object") return typeof v === "string" ? clean(v, 140) : v;
    if (depth > 4) return Array.isArray(v) ? "[...]" : "{...}";
    if (Array.isArray(v)) {
      const arr = v.slice(0, 6).map(function (x) { return shrink(x, depth + 1); });
      if (v.length > 6) arr.push("... +" + (v.length - 6) + " more");
      return arr;
    }
    const o = {};
    Object.keys(v).slice(0, 25).forEach(function (k) { o[k] = shrink(v[k], depth + 1); });
    return o;
  }

  function fetchJson(url) {
    let u;
    try { u = new URL(url, location.href); } catch (e) { return { ok: false, error: "bad url" }; }
    if (u.origin !== location.origin) return { ok: false, error: "only same-site urls (" + location.origin + ") can be read" };
    try {
      const x = new XMLHttpRequest();
      x.open("GET", u.href, false);
      x.setRequestHeader("Accept", "application/json, text/plain, */*");
      x.send();
      if (x.status < 200 || x.status >= 300) return { ok: false, error: "HTTP " + x.status };
      let body = x.responseText || "";
      try { body = JSON.stringify(shrink(JSON.parse(body), 0)); } catch (e) { body = clean(body, 3000); }
      return { ok: true, status: x.status, body: body.slice(0, 3500) };
    } catch (e) {
      return { ok: false, error: String(e && e.message || e) };
    }
  }

  function fingerprint() {
    const body = document.body;
    return {
      url: location.href,
      title: document.title,
      textLen: body ? body.innerText.length : 0,
      nodes: document.getElementsByTagName("*").length,
      dialogs: document.querySelectorAll('dialog[open], [role="dialog"], [aria-modal="true"]').length,
    };
  }

  function find(query, limit) {
    const words = String(query || "").toLowerCase().trim().split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    const c = collect(2000);
    return c.items
      .filter(function (it) {
        const blob = ((it.text || "") + " " + (it.href || "") + " " + (it.placeholder || "")).toLowerCase();
        return words.every(function (w) { return blob.includes(w); });
      })
      .slice(0, limit || 10);
  }

  function target(id) {
    const el = S.els.get(id);
    if (!el) return { error: "unknown id " + id + " (take a fresh snapshot)" };
    if (!el.isConnected) return { error: "element " + id + " is gone from the page (take a fresh snapshot)" };
    return { el: el };
  }

  function click(id) {
    const t = target(id);
    if (t.error) return { ok: false, error: t.error };
    const el = t.el;
    const tag = el.tagName.toLowerCase();

    if (el.disabled) return { ok: false, error: "element is disabled" };
    if (tag === "select") return { ok: false, error: "use type(id, option text) for dropdowns" };

    el.scrollIntoView({ block: "center", inline: "center" });
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return { ok: false, error: "element is not visible" };

    // naye tab/window mein khulne wala link isi tab mein kholo (tab control saaf rahe)
    if (tag === "a" && el.href && el.target && el.target !== "_self") {
      window.location.href = el.href;
      return { ok: true, note: "link opened in this tab" };
    }

    el.focus({ preventScroll: true });
    ["mousedown", "mouseup"].forEach(function (type) {
      el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
    });
    el.click();
    return { ok: true };
  }

  function typeText(id, text, submit) {
    const t = target(id);
    if (t.error) return { ok: false, error: t.error };
    const el = t.el;
    const tag = el.tagName.toLowerCase();
    const type = (el.type || "").toLowerCase();

    if (type === "password") {
      return { ok: false, error: "password fields are filled by the user, never by the agent" };
    }
    if (type === "file") return { ok: false, error: "file inputs cannot be filled" };
    if (["checkbox", "radio", "button", "submit", "reset", "image"].includes(type)) {
      return { ok: false, error: "not a text field, use click" };
    }

    el.scrollIntoView({ block: "center", inline: "center" });
    el.focus({ preventScroll: true });

    if (tag === "select") {
      const want = String(text).toLowerCase();
      const opts = Array.from(el.options);
      const opt = opts.find(function (o) { return o.text.trim().toLowerCase() === want || o.value.toLowerCase() === want; })
        || opts.find(function (o) { return o.text.toLowerCase().includes(want); });
      if (!opt) return { ok: false, error: 'no option matching "' + text + '"' };
      el.value = opt.value;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return { ok: true, value: clean(opt.text, 80) };
    }

    if (tag === "input" || tag === "textarea") {
      const proto = tag === "input" ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype;
      Object.getOwnPropertyDescriptor(proto, "value").set.call(el, text);  // React/Vue wale inputs ke liye bhi chalta hai
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    } else if (el.isContentEditable) {
      document.execCommand("selectAll", false, null);
      document.execCommand("insertText", false, text);
    } else {
      return { ok: false, error: "element is not a text field" };
    }

    if (submit) {
      const form = el.form;
      if (form && typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        ["keydown", "keypress", "keyup"].forEach(function (type) {
          el.dispatchEvent(new KeyboardEvent(type, {
            key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true,
          }));
        });
      }
    }
    return { ok: true, value: clean(el.value !== undefined ? el.value : el.innerText, 80) };
  }

  function scrollPage(direction, amount) {
    const step = Math.round(innerHeight * (amount || 0.8));
    const root = document.documentElement;
    if (direction === "down") scrollBy({ top: step, behavior: "instant" });
    else if (direction === "up") scrollBy({ top: -step, behavior: "instant" });
    else if (direction === "top") scrollTo({ top: 0, behavior: "instant" });
    else if (direction === "bottom") scrollTo({ top: root.scrollHeight, behavior: "instant" });
    else return { ok: false, error: "direction must be down, up, top or bottom" };

    const max = root.scrollHeight - innerHeight;
    return {
      ok: true,
      scrollY: Math.round(scrollY),
      scrollHeight: Math.round(root.scrollHeight),
      atBottom: scrollY >= max - 2,
    };
  }

  // ---- insaan jesi typing: pehle prepare, phir chhote chhote insert, phir finish ----
  function prepareType(id) {
    const t = target(id);
    if (t.error) return { ok: false, error: t.error };
    const el = t.el;
    const tag = el.tagName.toLowerCase();
    const type = (el.type || "").toLowerCase();
    if (type === "password") return { ok: false, error: "password fields are filled by the user, never by the agent" };
    if (type === "file") return { ok: false, error: "file inputs cannot be filled" };
    if (["checkbox", "radio", "button", "submit", "reset", "image"].includes(type)) {
      return { ok: false, error: "not a text field, use click" };
    }
    if (tag === "select") return { ok: true, mode: "instant" };
    if (!(tag === "input" || tag === "textarea" || el.isContentEditable)) {
      return { ok: false, error: "element is not a text field" };
    }
    el.scrollIntoView({ block: "center", inline: "center" });
    el.focus({ preventScroll: true });
    if (tag === "input" || tag === "textarea") el.select();
    else document.execCommand("selectAll", false, null);
    document.execCommand("delete", false, null);
    return { ok: true, mode: "human" };
  }

  function insertChars(id, chunk) {
    const t = target(id);
    if (t.error) return false;
    const el = t.el;
    if (document.activeElement !== el) el.focus({ preventScroll: true });
    if (document.execCommand("insertText", false, chunk)) return true;
    const tag = el.tagName.toLowerCase();
    if (tag === "input" || tag === "textarea") {
      const proto = tag === "input" ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype;
      Object.getOwnPropertyDescriptor(proto, "value").set.call(el, el.value + chunk);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    }
    return false;
  }

  function finishType(id, submit) {
    const t = target(id);
    if (t.error) return { ok: false, error: t.error };
    const el = t.el;
    el.dispatchEvent(new Event("change", { bubbles: true }));
    if (submit) {
      const form = el.form;
      if (form && typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        ["keydown", "keypress", "keyup"].forEach(function (type) {
          el.dispatchEvent(new KeyboardEvent(type, {
            key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true,
          }));
        });
      }
    }
    return { ok: true, value: clean(el.value !== undefined ? el.value : el.innerText, 80) };
  }

  window.__agent = {
    snapshot: snapshot,
    fingerprint: fingerprint,
    find: find,
    click: click,
    type: typeText,
    prepareType: prepareType,
    insertChars: insertChars,
    finishType: finishType,
    scroll: scrollPage,
    apiList: apiList,
    fetchJson: fetchJson,
  };
})();