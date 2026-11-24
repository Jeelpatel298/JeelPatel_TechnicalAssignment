import { api, busy } from './client.js';

const shell = document.querySelector('.shell');
const admin = shell.dataset.admin === 'true';
const view = document.querySelector('#view');
const notice = document.querySelector('#notice');
const dialog = document.querySelector('#editor');
const dialogForm = document.querySelector('#dialog-form');
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[char]);
const currency = value => '₹' + String(value).replace(/\B(?=(\d{3})+(?!\d|\.))/g, ',');
const heading = (title, description, action = '') =>
  `<header class="heading"><div><h1>${title}</h1><p>${description}</p></div>${action}</header>`;
const badge = status => `<span class="badge ${escape(status.toLowerCase())}">${escape(status)}</span>`;
const state = row => row.active ? 'Active' : 'Inactive';
const statusOptions = selected => ['Active', 'Inactive'].map(option =>
  `<option ${option === selected ? 'selected' : ''}>${option}</option>`).join('');
const columns = {
  customers: [
    ['name', 'Name', 'text', 120], ['email', 'Email', 'email', 254],
    ['mobile', 'Mobile', 'tel', 30], ['city', 'City', 'text', 100],
  ],
  products: [
    ['code', 'Product code', 'text', 40], ['name', 'Name', 'text', 120],
    ['category', 'Category', 'text', 80], ['price', 'Price (INR)', 'number'],
  ],
};
let viewVersion = 0;
let dialogAction;

function feedback(message, error = false, rows, box = notice) {
  box.classList.toggle('error', error);
  box.hidden = false;
  box.textContent = message;
  if (rows?.length) {
    const list = document.createElement('ul');
    for (const row of rows) {
      const item = document.createElement('li');
      item.textContent = `Row ${row.row} · ${row.reason}`;
      list.append(item);
    }
    box.append(list);
  }
}
const failed = error => feedback(error.message, true, error.rows);

function table(titles, rows, empty = 'No records found.') {
  if (!rows.length) return `<p class="empty">${escape(empty)}</p>`;
  return `<div class="table-wrap"><table><thead><tr>${titles.map(title =>
    `<th scope="col">${escape(title)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(row => `<tr>${row.map(value => `<td>${value}</td>`).join('')}</tr>`).join('')}</tbody>
    </table></div>`;
}

function panel(title, contents) {
  return `<section class="panel"><h2 class="panel-title">${escape(title)}</h2>${contents}</section>`;
}

function input(name, label, value = '', type = 'text', extra = '') {
  return `<label>${label}<input name="${name}" type="${type}" value="${escape(value)}" ${extra}></label>`;
}

function openDialog(title, fields, action) {
  dialog.querySelector('h2').textContent = title;
  dialog.querySelector('#dialog-fields').innerHTML = fields;
  dialog.querySelector('#dialog-error').hidden = true;
  dialogAction = action;
  dialog.showModal();
}

dialog.querySelector('#dialog-close').onclick = () => dialog.close();
dialogForm.onsubmit = event => {
  event.preventDefault();
  const box = dialog.querySelector('#dialog-error');
  box.hidden = true;
  busy(event.submitter, async () => {
    const result = await dialogAction(Object.fromEntries(new FormData(dialogForm)));
    dialog.close();
    await result.refresh();
    feedback(result.message);
  }, error => feedback(error.message, true, error.rows, box));
};
dialog.addEventListener('cancel', event => {
  if (dialogForm.querySelector('button:disabled')) event.preventDefault();
});

function recordEditor(kind, row, refresh) {
  const product = kind === 'products';
  const label = product ? 'product' : 'customer';
  let fields = columns[kind].map(([name, caption, type, length]) =>
    input(name, caption, row?.[name], type, length ? `required maxlength="${length}"`
      : 'required min="0" max="9999999999.99" step="0.01"')).join('');
  if (product && !row) fields += input('stock', 'Opening stock', 0, 'number',
    'required min="0" max="2147483647" step="1"');
  fields += `<label>Status<select name="status">${statusOptions(row ? state(row) : 'Active')}</select></label>`;
  openDialog(`${row ? 'Edit' : 'New'} ${label}`, fields, async data => {
    await api(`/catalog/${kind}${row ? '/' + row.id : ''}`, row ? 'PUT' : 'POST', data);
    return { refresh, message: `${product ? 'Product' : 'Customer'} saved.` };
  });
}

async function showCatalog(kind, version) {
  const product = kind === 'products';
  const noun = product ? 'product' : 'customer';
  view.innerHTML = heading(product ? 'Products' : 'Customers',
    product ? 'Browse prices and current stock.' : 'Find customer contact details.',
    admin ? `<button id="new-record">New ${noun}</button>` : '') +
    `<form id="catalog-filter" class="filters">${input('q', 'Search', '', 'search', 'maxlength="120"')}
    ${product ? input('category', 'Category', '', 'text', 'maxlength="80"') : ''}
    ${admin ? `<label>Status<select name="status"><option value="">All statuses</option>
      ${statusOptions('')}</select></label>` : ''}<button class="secondary">Apply filters</button></form>
    <section id="catalog-table" class="panel"></section>`;
  const form = view.querySelector('form');
  const target = view.querySelector('#catalog-table');
  let page = 1;
  let filters = {};
  let requestVersion = 0;
  async function refresh() {
    const current = ++requestVersion;
    const result = await api(`/catalog/${kind}?` + new URLSearchParams({ ...filters, page }));
    if (version !== viewVersion || current !== requestVersion) return;
    if (page > 1 && !result.items.length) {
      page -= 1;
      return refresh();
    }
    const titles = product ? ['Code', 'Name', 'Category', 'Price', 'Stock'] : ['Name', 'Email', 'Mobile', 'City'];
    const rows = result.items.map(row => {
      const cells = (product ? [row.code, row.name, row.category, currency(row.price), row.stock]
        : [row.name, row.email, row.mobile, row.city]).map(escape);
      cells.push(badge(state(row)));
      if (admin) cells.push(`<div class="actions">
        <button class="secondary" data-action="edit" data-id="${row.id}">Edit</button>
        ${product ? `<button class="secondary" data-action="adjust" data-id="${row.id}">Adjust stock</button>` : ''}
        <button class="danger" data-action="delete" data-id="${row.id}">Delete</button></div>`);
      return cells;
    });
    const pages = Math.max(1, Math.ceil(result.total / result.per_page));
    target.innerHTML = table([...titles, 'Status', ...(admin ? ['Actions'] : [])], rows) +
      `<div class="pager"><span class="muted">Page ${page} of ${pages} · ${result.total} records</span>
      <button class="secondary" data-action="previous" ${page === 1 ? 'disabled' : ''}>Previous</button>
      <button class="secondary" data-action="next" ${page >= pages ? 'disabled' : ''}>Next</button></div>`;
    target.onclick = event => {
      const button = event.target.closest('button[data-action]');
      if (!button) return;
      const action = button.dataset.action;
      const row = result.items.find(item => item.id === Number(button.dataset.id));
      if (action === 'edit') recordEditor(kind, row, refresh);
      if (action === 'adjust') openDialog('Adjust stock · ' + row.code,
        input('change', 'Quantity change', '', 'number', 'required step="1"') +
        input('reason', 'Reason', '', 'text', 'required maxlength="255"'), async data => {
          await api('/products/' + row.id + '/adjust', 'POST', data);
          return { refresh, message: 'Stock adjusted.' };
        });
      if (action === 'delete' && confirm(`Delete ${row.name}?`)) {
        busy(button, async () => {
          await api(`/catalog/${kind}/${row.id}`, 'DELETE');
          await refresh();
          feedback('Record deleted.');
        }, failed);
      }
      if (action === 'next' || action === 'previous') {
        page += action === 'next' ? 1 : -1;
        busy(button, refresh, failed);
      }
    };
  }
  form.onsubmit = event => {
    event.preventDefault();
    filters = Object.fromEntries(new FormData(form));
    page = 1;
    busy(event.submitter, refresh, failed);
  };
  if (admin) view.querySelector('#new-record').onclick = () => recordEditor(kind, null, refresh);
  await refresh();
}

async function showOrders(version) {
  const { items } = await api('/orders');
  if (version !== viewVersion) return;
  const totals = ['Draft', 'Confirmed', 'Cancelled'].map(status =>
    `<div class="metric"><span class="muted">${status}</span>
      <strong>${items.filter(row => row.status === status).length}</strong></div>`).join('');
  view.innerHTML = heading('Sales orders', admin ? 'Review and manage all customer orders.' :
    'Review and manage your customer orders.', '<a class="button" href="#orders/new">New order</a>') +
    `<div class="metrics">${totals}</div>` + panel('Order list',
    table(['Order', 'Customer', 'Date', 'Status', ...(admin ? ['Created by'] : []), 'Total'],
      items.map(row => [
        `<a href="#orders/${row.id}" class="order-number">${escape(row.number)}</a>`,
        escape(row.customer_name), escape(row.order_date), badge(row.status),
        ...(admin ? [escape(row.owner)] : []), escape(currency(row.grand_total)),
      ]), 'No orders yet.'));
}

const cents = value => {
  const [whole, fractional = ''] = String(value).split('.');
  return BigInt(whole || '0') * 100n + BigInt(fractional.padEnd(2, '0'));
};
const fromCents = value => currency(`${value / 100n}.${String(value % 100n).padStart(2, '0')}`);

async function allRecords(kind) {
  const path = '/catalog/' + kind + '?status=Active&per_page=100&page=';
  const first = await api(path + '1');
  const results = [first.items];
  for (let page = 2; page <= Math.ceil(first.total / first.per_page); page += 1) {
    results.push((await api(path + page)).items);
  }
  return results.flat();
}

function totalsBlock(subtotal, discount, grandTotal) {
  return `<div class="totals currency"><div><span>Subtotal</span><output id="subtotal">${subtotal}</output></div>
    <div><span>Discount</span><output id="discount">${discount}</output></div>
    <div><span>Grand total</span><output id="grand-total">${grandTotal}</output></div></div>`;
}

function orderActions(order, version) {
  for (const button of view.querySelectorAll('[data-transition]')) {
    button.onclick = () => {
      const action = button.dataset.transition;
      const warning = action === 'confirm' ? 'Confirm this order and deduct stock?' :
        order.status === 'Confirmed' ? 'Cancel this order and restore stock?' : 'Cancel this draft order?';
      if (!confirm(warning)) return;
      busy(button, async () => {
        const result = await api(`/orders/${order.id}/${action}`, 'POST');
        if (version === viewVersion) {
          await navigate();
          feedback(`Order ${result.status.toLowerCase()}.`);
        }
      }, failed);
    };
  }
}

async function showOrder(id, version) {
  const order = id === 'new' ? null : await api('/orders/' + id);
  if (version !== viewVersion) return;
  const back = '<a class="back" href="#orders">← Sales orders</a>';
  const details = order ? `<div class="detail-meta"><span class="order-number">${escape(order.number)}</span>
    ${badge(order.status)}</div>` : '';
  if (order && order.status !== 'Draft') {
    view.innerHTML = back + heading('Order details', escape(order.customer_name) + ' · ' + escape(order.order_date),
      order.status === 'Confirmed' ? '<button class="danger" data-transition="cancel">Cancel order</button>' : '') +
      details + '<div class="panel padded">' + table(['Product', 'Quantity', 'Rate', 'Amount'],
        order.items.map(row => [escape(row.name), escape(row.quantity),
          escape(currency(row.rate)), escape(currency(row.amount))])) +
      totalsBlock(currency(order.subtotal), currency(order.discount_amount), currency(order.grand_total)) + '</div>';
    orderActions(order, version);
    return;
  }

  const [customers, products] = await Promise.all([allRecords('customers'), allRecords('products')]);
  if (version !== viewVersion) return;
  if (order && !customers.some(row => row.id === order.customer_id)) {
    customers.unshift({ id: order.customer_id, name: order.customer_name + ' (inactive)', active: false });
  }
  const customersOptions = customers.map(row =>
    `<option value="${row.id}" ${order?.customer_id === row.id ? 'selected' : ''}
      ${row.active ? '' : 'disabled'}>${escape(row.name)}</option>`).join('');
  view.innerHTML = back + heading(order ? 'Edit draft' : 'New order', 'Set the customer, items and discount.') +
    details + `<form class="order-form"><section class="panel padded fields">
      <label>Customer<select name="customer_id" required><option value="">Select customer</option>${customersOptions}</select></label>
      ${input('order_date', 'Order date', order?.order_date || shell.dataset.today, 'date',
        'required min="1000-01-01" max="9999-12-31"')}
      ${input('discount_pct', 'Discount (%)', order?.discount_pct ?? 0, 'number',
        'required min="0" max="20" step="0.01"')}
    </section><section class="panel padded"><h2>Order items</h2><div id="order-lines"></div>
      <button type="button" id="add-line" class="secondary">Add item</button>
      ${totalsBlock('₹0.00', '₹0.00', '₹0.00')}
      <div class="actions"><button>${order ? 'Save draft changes' : 'Save draft'}</button>
        ${order ? '<button type="button" data-transition="confirm">Confirm order</button>' +
          '<button type="button" class="danger" data-transition="cancel">Cancel draft</button>' : ''}</div>
    </section></form>`;
  const form = view.querySelector('form');
  const lines = form.querySelector('#order-lines');
  const saved = new Map((order?.items || []).map(row => [row.product_id, row]));
  const options = [...products, ...[...saved.values()].filter(row => !row.active).map(row =>
    ({ ...row, id: row.product_id }))];
  const byId = new Map(options.map(row => [row.id, row]));
  const productOptions = options.map(row => `<option value="${row.id}" ${row.active ? '' : 'disabled'}>
    ${escape(row.code)} · ${escape(row.name)}${row.active ? '' : ' (inactive)'}</option>`).join('');

  function updateTotals() {
    let subtotal = 0n;
    for (const row of lines.children) {
      const qty = row.querySelector('.qty');
      const amount = qty.validity.valid && qty.value && row.dataset.rate
        ? BigInt(qty.valueAsNumber) * cents(row.dataset.rate) : 0n;
      row.querySelector('.line-amount').value = fromCents(amount);
      subtotal += amount;
    }
    const pct = form.elements.discount_pct;
    const discount = pct.validity.valid && pct.value ? (subtotal * cents(pct.valueAsNumber) + 5000n) / 10000n : 0n;
    form.querySelector('#subtotal').value = fromCents(subtotal);
    form.querySelector('#discount').value = fromCents(discount);
    form.querySelector('#grand-total').value = fromCents(subtotal - discount);
  }

  function updateStock(row, product, select) {
    const rate = saved.get(product?.id)?.rate ?? product?.price;
    row.dataset.rate = rate ?? '';
    row.querySelector('.rate').value = rate === undefined ? '—' : currency(rate);
    row.querySelector('.stock').textContent = product ? `${product.stock} in stock` : '';
    if (product && !product.active) select.setCustomValidity('Choose an active product.');
    updateTotals();
  }

  function addLine(existing) {
    if (lines.children.length >= 100) return feedback('An order can contain up to 100 items.', true);
    const row = document.createElement('div');
    row.className = 'order-line';
    row.innerHTML = `<label>Product<select class="product" required><option value="">Select product</option>
      ${productOptions}</select></label>
      <label>Quantity<input class="qty" type="number" min="1" max="2147483647" step="1"
        value="${escape(existing?.quantity ?? 1)}" required></label>
      <div class="line-data"><small>Rate</small><output class="rate currency">—</output><small class="stock"></small></div>
      <div class="line-data"><small>Amount</small><output class="line-amount currency">₹0.00</output></div>
      <button class="secondary" type="button">Remove</button>`;
    lines.append(row);
    const select = row.querySelector('select');
    if (existing) {
      select.value = existing.product_id;
      updateStock(row, byId.get(existing.product_id), select);
    }
    select.onchange = async () => {
      select.setCustomValidity('');
      const selected = select.value;
      updateStock(row, null, select);
      if (!selected) return;
      select.setCustomValidity('Loading product details.');
      try {
        const product = await api('/catalog/products/' + selected);
        if (select.value !== selected || !row.isConnected) return;
        select.setCustomValidity('');
        updateStock(row, product, select);
      } catch (error) {
        if (select.value === selected && row.isConnected) {
          select.setCustomValidity('Select the product again to retry.');
          failed(error);
        }
      }
    };
    row.querySelector('input').oninput = updateTotals;
    row.querySelector('button').onclick = () => {
      row.remove();
      updateTotals();
    };
  }

  const customer = form.elements.customer_id;
  if (order && !order.customer_active) customer.setCustomValidity('Choose an active customer.');
  customer.onchange = () => customer.setCustomValidity('');
  form.elements.discount_pct.oninput = updateTotals;
  form.querySelector('#add-line').onclick = () => addLine();
  if (order) order.items.forEach(addLine);
  else addLine();

  function draftChanged() {
    if (!order) return;
    const button = form.querySelector('[data-transition="confirm"]');
    button.disabled = true;
    button.title = 'Save draft changes before confirming.';
    button.textContent = 'Save before confirming';
  }
  form.addEventListener('input', draftChanged);
  lines.addEventListener('click', event => { if (event.target.closest('button')) draftChanged(); });
  form.querySelector('#add-line').addEventListener('click', draftChanged);

  form.onsubmit = event => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    data.items = [...lines.children].map(row => ({
      product_id: Number(row.querySelector('select').value),
      quantity: row.querySelector('input').valueAsNumber,
    }));
    if (!data.items.length) return feedback('Add at least one item.', true);
    if (new Set(data.items.map(row => row.product_id)).size !== data.items.length) {
      return feedback('A product can appear only once per order.', true);
    }
    busy(event.submitter, async () => {
      const savedOrder = await api(order ? '/orders/' + order.id : '/orders', order ? 'PUT' : 'POST', data);
      if (version !== viewVersion) return;
      history.replaceState(null, '', '#orders/' + savedOrder.id);
      await navigate();
      feedback('Draft saved.');
    }, failed);
  };
  if (order) orderActions(order, version);
}

async function showReports(version) {
  view.innerHTML = heading('Reports', 'Review confirmed sales and stock activity.') +
    `<form class="filters">
      ${input('start', 'Customer sales from', '', 'date')}
      ${input('end', 'Customer sales through', '', 'date')}
      ${input('threshold', 'Stock below', 10, 'number', 'required min="0" max="2147483647" step="1"')}
      <button class="secondary">Run reports</button>
    </form><div id="results"></div>`;
  const form = view.querySelector('form');
  const results = view.querySelector('#results');
  let requestVersion = 0;
  async function refresh() {
    const current = ++requestVersion;
    const data = await api('/reports?' + new URLSearchParams(new FormData(form)));
    if (version !== viewVersion || current !== requestVersion) return;
    results.innerHTML = panel('Customer sales summary',
      table(['Customer', 'Confirmed orders', 'Total sales'], data.customers.map(row =>
        [row.name, row.order_count, currency(row.total)].map(escape)))) +
      panel('Product sales summary · all dates', table(['Code', 'Product', 'Quantity sold', 'Gross item value'],
        data.products.map(row => [row.code, row.name, row.quantity, currency(row.gross)].map(escape)))) +
      panel('Low stock', table(['Code', 'Product', 'Stock', 'Status'], data.low_stock.map(row =>
        [escape(row.code), escape(row.name), escape(row.stock), badge(state(row))]))) +
      panel('Stock movement history', table(['Code', 'Product', 'Type', 'Change', 'Order', 'Reason', 'Timestamp (UTC)'],
        data.movements.map(row => [row.code, row.name, row.movement_type, row.quantity_change,
          row.order_number || '—', row.reason, row.created_at].map(escape))));
  }
  form.onsubmit = event => {
    event.preventDefault();
    busy(event.submitter, refresh, failed);
  };
  await refresh();
}

function showImport() {
  view.innerHTML = heading('CSV import', 'Create products and log their opening stock.') +
    `<section class="panel padded"><form id="upload-form">
      <label>Product CSV<input name="file" type="file" accept=".csv,text/csv" required></label>
      <p class="muted">Use a UTF-8 CSV with product_code, product_name, category, price, stock_quantity and status.</p>
      <div class="actions import-actions"><button>Import products</button></div>
    </form></section>`;
  view.querySelector('form').onsubmit = event => {
    event.preventDefault();
    const form = event.currentTarget;
    notice.hidden = true;
    busy(event.submitter, async () => {
      const result = await api('/products/import', 'POST', new FormData(form));
      feedback(`Imported ${result.imported} products.`);
      form.reset();
    }, failed);
  };
}

async function navigate() {
  const version = ++viewVersion;
  const [tab, record] = (location.hash.slice(1) || 'orders').split('/');
  notice.hidden = true;
  view.innerHTML = '<p class="muted">Loading…</p>';
  for (const link of document.querySelectorAll('nav a')) {
    if (link.hash === '#' + tab) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  try {
    if (tab === 'orders' && (record === 'new' || /^[0-9]+$/.test(record || ''))) {
      await showOrder(record, version);
    } else if (tab === 'customers' || tab === 'products') {
      await showCatalog(tab, version);
    } else if (tab === 'reports' && admin) {
      await showReports(version);
    } else if (tab === 'import' && admin) {
      showImport();
    } else {
      await showOrders(version);
    }
  } catch (error) {
    if (version === viewVersion) {
      if (view.textContent === 'Loading…') view.innerHTML = '';
      failed(error);
    }
  }
}

document.querySelector('#logout').onclick = event => {
  busy(event.currentTarget, async () => {
    await api('/logout', 'POST');
    location.assign('/login');
  }, failed);
};
window.addEventListener('hashchange', navigate);
navigate();
