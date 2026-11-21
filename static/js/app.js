/* ShopSphere storefront JS – no frameworks, talks to /api/ */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const csrf = () => (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
  const money = (v) => '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function toast(msg, type) {
    const box = $('#toasts'); if (!box) return;
    const el = document.createElement('div'); el.className = 'toast ' + (type || ''); el.textContent = msg;
    box.appendChild(el); setTimeout(() => el.remove(), 3200);
  }

  async function api(url, method, data) {
    const opts = { method: method || 'GET', headers: { 'Accept': 'application/json' }, credentials: 'same-origin' };
    if (opts.method !== 'GET') { opts.headers['Content-Type'] = 'application/json'; opts.headers['X-CSRFToken'] = csrf(); opts.body = JSON.stringify(data || {}); }
    const res = await fetch(url, opts);
    let json = {}; try { json = await res.json(); } catch (e) { /* ignore */ }
    if (res.status === 401) { location.href = '/accounts/login/?next=' + encodeURIComponent(location.pathname); throw new Error('auth'); }
    if (!res.ok) throw new Error(json.error || 'Something went wrong');
    return json;
  }

  function setBadge(n) { const b = $('#cart-badge'); if (!b) return; b.textContent = n; b.hidden = !n; }

  /* ---- theme ---- */
  const tt = $('#theme-toggle');
  if (tt) tt.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next; try { localStorage.setItem('theme', next); } catch (e) { /* ignore */ }
  });

  /* ---- add to cart (cards + product page) ---- */
  document.addEventListener('click', async (e) => {
    const add = e.target.closest('[data-add-to-cart]');
    if (add) {
      add.disabled = true;
      try { const c = await api('/api/cart/add/', 'POST', { product_id: +add.dataset.id, quantity: 1 }); setBadge(c.count); toast('Added to cart 🛒'); }
      catch (err) { if (/option/i.test(err.message) && add.dataset.url) location.href = add.dataset.url; else toast(err.message, 'error'); }
      add.disabled = false; return;
    }
    const wish = e.target.closest('[data-wishlist]');
    if (wish) {
      try {
        const r = await api('/api/wishlist/toggle/', 'POST', { product_id: +wish.dataset.id });
        const big = wish.classList.contains('btn');
        wish.textContent = (r.wishlisted ? '♥' : '♡') + (big ? ' Wishlist' : '');
        toast(r.wishlisted ? 'Saved to wishlist' : 'Removed from wishlist');
      } catch (err) { if (err.message !== 'auth') toast(err.message, 'error'); }
    }
    const th = e.target.closest('[data-thumb]');
    if (th) { const m = $('#main-img'); if (m) m.src = th.src; }
  });

  const pdpAdd = $('#pdp-add');
  if (pdpAdd) {
    const variant = $('#variant'), price = $('#pdp-price');
    if (variant && price) variant.addEventListener('change', () => { const o = variant.selectedOptions[0]; if (o && o.dataset.price) price.textContent = money(o.dataset.price); });
    pdpAdd.addEventListener('click', async () => {
      pdpAdd.disabled = true;
      try {
        const c = await api('/api/cart/add/', 'POST', { product_id: +pdpAdd.dataset.id, variant_id: variant ? +variant.value : null, quantity: +($('#qty').value || 1) });
        setBadge(c.count); toast('Added to cart 🛒');
      } catch (err) { toast(err.message, 'error'); }
      pdpAdd.disabled = false;
    });
  }

  /* ---- live search suggestions ---- */
  const si = $('#search-input'), box = $('#suggest'); let timer;
  if (si && box) {
    si.addEventListener('input', () => {
      clearTimeout(timer); const q = si.value.trim();
      if (q.length < 2) { box.hidden = true; return; }
      timer = setTimeout(async () => {
        try {
          const r = await api('/api/suggest/?q=' + encodeURIComponent(q));
          box.innerHTML = r.results.map((p) => `<a href="${esc(p.url)}"><span>${esc(p.icon)}</span><span style="flex:1">${esc(p.name)}</span><strong>${money(p.price)}</strong></a>`).join('') || '<p class="muted" style="padding:.6rem">No matches</p>';
          box.hidden = false;
        } catch (e) { box.hidden = true; }
      }, 220);
    });
    document.addEventListener('click', (e) => { if (!e.target.closest('.search')) box.hidden = true; });
  }

  /* ---- checkout address toggle ---- */
  $$('input[name="address_id"]').forEach((r) => r.addEventListener('change', () => { const n = $('#new-address'); if (n) n.hidden = r.value !== '' || !r.checked; }));

  /* ---- cart page ---- */
  const root = $('#cart-root');
  function renderCart(c) {
    setBadge(c.count);
    if (!c.items.length) { root.innerHTML = '<div class="card pad center" style="grid-column:1/-1"><h2>Your cart is empty</h2><a class="btn" href="/shop/">Continue shopping</a></div>'; return; }
    const pct = Math.min(100, Math.round((1 - c.free_shipping_remaining / c.free_shipping_threshold) * 100));
    const items = c.items.map((i) => `
      <div class="card cart-item">
        ${i.image ? `<img src="${esc(i.image)}" alt="">` : `<div class="ph">${esc(i.icon)}</div>`}
        <div><a href="${esc(i.url)}"><strong>${esc(i.name)}</strong></a>${i.variant ? `<br><small class="muted">${esc(i.variant)}</small>` : ''}<br><small class="muted">Sold by ${esc(i.vendor)} · ${money(i.unit_price)}</small><br>
          <span class="qty"><button data-q="${i.id}" data-d="-1" aria-label="Decrease">−</button><span>${i.quantity}</span><button data-q="${i.id}" data-d="1" aria-label="Increase">+</button></span>
          <button class="link danger" data-rm="${i.id}">Remove</button></div>
        <strong>${money(i.line_total)}</strong></div>`).join('');
    root.innerHTML = `<div>${items}</div>
      <aside class="card pad"><h2 style="margin-top:0">Summary</h2>
        ${c.free_shipping_remaining > 0 ? `<small class="muted">Add ${money(c.free_shipping_remaining)} more for free shipping</small><div class="progress"><i style="width:${pct}%"></i></div>` : '<small class="ok">🎉 You get free shipping!</small>'}
        <form class="coupon" id="coupon-form"><input name="code" placeholder="Coupon code" value="${esc(c.coupon || '')}"><button class="btn btn-ghost">${c.coupon ? 'Remove' : 'Apply'}</button></form>
        <dl class="totals"><dt>Subtotal</dt><dd>${money(c.subtotal)}</dd>${+c.discount ? `<dt>Discount (${esc(c.coupon)})</dt><dd class="ok">-${money(c.discount)}</dd>` : ''}
        <dt>Shipping</dt><dd>${+c.shipping ? money(c.shipping) : 'Free'}</dd><dt>Tax</dt><dd>${money(c.tax)}</dd><dt class="grand">Total</dt><dd class="grand">${money(c.total)}</dd></dl>
        <a class="btn btn-lg btn-block" href="/checkout/">Checkout</a></aside>`;
  }
  async function cartCall(url, data) { try { renderCart(await api(url, 'POST', data)); } catch (e) { if (e.message !== 'auth') toast(e.message, 'error'); } }
  if (root) {
    api('/api/cart/').then(renderCart).catch(() => { root.innerHTML = '<p class="bad">Could not load cart.</p>'; });
    root.addEventListener('click', (e) => {
      const q = e.target.closest('[data-q]'), rm = e.target.closest('[data-rm]');
      if (q) { const qty = +q.parentElement.querySelector('span').textContent + +q.dataset.d; cartCall('/api/cart/update/', { item_id: +q.dataset.q, quantity: qty }); }
      if (rm) cartCall('/api/cart/remove/', { item_id: +rm.dataset.rm });
    });
    root.addEventListener('submit', (e) => {
      if (e.target.id !== 'coupon-form') return; e.preventDefault();
      const input = e.target.code; const removing = e.submitter && e.submitter.textContent.trim() === 'Remove';
      cartCall('/api/cart/coupon/', { code: removing ? '' : input.value });
    });
  }

  /* ---- vendor revenue chart ---- */
  const chart = $('#revenue-chart');
  if (chart) api(chart.dataset.url).then((d) => {
    const max = Math.max.apply(null, d.revenue.concat([1]));
    chart.innerHTML = d.revenue.map((v, i) => `<i style="height:${Math.max(2, (v / max) * 100)}%" title="${esc(d.labels[i])}: ${money(v)}"></i>`).join('');
  }).catch(() => { chart.textContent = 'No data'; });

  /* ---- service worker (PWA) ---- */
  if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
})();
