// Isolated world mein chalta hai: website ki JS is ko dekh ya badal nahi sakti.
// Python ko console.log se message jata hai; __NX_TOKEN__ har page ke liye random hai (website forge nahi kar sakti).
(function () {
  if (window.top !== window) return;
  const TOKEN = "__NX_TOKEN__";
  const send = (o) => { try { console.log("NXPW:" + TOKEN + ":" + JSON.stringify(o)); } catch (e) {} };

  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
  };
  const pwFields = (root) =>
    [...(root || document).querySelectorAll("input[type=password]")].filter((i) => !i.disabled && visible(i));
  const TEXT_TYPES = ["text", "email", "tel", ""];
  const userField = (pw) => {
    const scope = pw.form || document;
    let best = null;
    for (const c of scope.querySelectorAll("input")) {
      if (c === pw || c.disabled || !visible(c)) continue;
      if (!TEXT_TYPES.includes((c.getAttribute("type") || "").toLowerCase())) continue;
      if (c.compareDocumentPosition(pw) & Node.DOCUMENT_POSITION_FOLLOWING) best = c;
    }
    return best;
  };

  let lastSent = "";
  const capture = (form) => {
    const pws = pwFields(form || document).filter((p) => p.value);
    if (!pws.length) return;
    const pw = pws.length >= 3 ? pws[1] : pws[0];  // old/new/confirm ho to new password
    const u = userField(pw);
    const user = u ? u.value : "";
    const key = location.origin + "\n" + user + "\n" + pw.value;
    if (key === lastSent) return;
    lastSent = key;
    send({ t: "submit", origin: location.origin, user: user, pass: pw.value });
  };

  document.addEventListener("submit", (e) => { if (e.isTrusted) capture(e.target); }, true);
  document.addEventListener("keydown", (e) => {
    if (e.isTrusted && e.key === "Enter" && e.target && e.target.tagName === "INPUT") capture(e.target.form || null);
  }, true);
  document.addEventListener("click", (e) => {
    if (!e.isTrusted || !e.target.closest) return;
    const b = e.target.closest("button,input[type=submit],input[type=button],[role=button]");
    if (!b) return;
    const type = (b.getAttribute("type") || "").toLowerCase();
    const text = (b.innerText || b.value || "").toLowerCase();
    if (type === "submit" || /log ?in|sign ?in|sign ?up|register|create|continue|submit|save|change/.test(text)) {
      capture(b.form || null);
    }
  }, true);

  let lastField = null;
  document.addEventListener("focusin", (e) => {
    if (!e.isTrusted) return;  // sirf asli user focus se menu khulta hai
    const t = e.target;
    if (!t || t.tagName !== "INPUT") return;
    const type = (t.getAttribute("type") || "").toLowerCase();
    const isPw = type === "password";
    if (!isPw && !TEXT_TYPES.includes(type)) return;
    const scope = t.form || document;
    if (!isPw && !pwFields(scope).length) return;  // username field tabhi jab saath mein password field ho
    lastField = t;
    const r = t.getBoundingClientRect();
    send({ t: "query", origin: location.origin, x: r.left, y: r.bottom });
  }, true);

  const setValue = (el, v) => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, v);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  };
  window.__nxFill = function (user, pass) {
    const scope = (lastField && lastField.form) || document;
    const pw = pwFields(scope)[0] || pwFields(document)[0];
    if (!pw) return;
    const u = userField(pw);
    if (u && user) setValue(u, user);
    setValue(pw, pass);
  };
})();