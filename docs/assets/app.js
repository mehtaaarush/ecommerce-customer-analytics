/* E-commerce customer analytics dashboard: renders docs/data/dashboard.json (computed by `python -m retail.pipeline`). */
(function () {
  'use strict';

  const fmt = Viz.fmt;
  const el = (id) => document.getElementById(id);
  let D;

  const COUNTRY_NAMES = { EIRE: 'Ireland', RSA: 'South Africa', USA: 'United States' };
  const DAY_NAMES = { Mon: 'Monday', Tue: 'Tuesday', Wed: 'Wednesday', Thu: 'Thursday', Fri: 'Friday', Sat: 'Saturday', Sun: 'Sunday' };
  const MEASURES = {
    net_revenue: { label: 'Net revenue', value: (v) => fmt.gbp(v), axis: { tickprefix: '£', tickformat: '~s' } },
    orders: { label: 'Orders', value: (v) => fmt.int(v), axis: { tickformat: ',.0f' } },
    aov: { label: 'Average order value', value: (v) => fmt.gbp(v), axis: { tickprefix: '£', tickformat: ',.0f' } },
    customers: { label: 'Active customers', value: (v) => fmt.int(v), axis: { tickformat: ',.0f' } },
  };

  /* Product descriptions are upper case in the source; show them in sentence case. */
  const nice = (s) => {
    const t = String(s || '').toLowerCase().replace(/\s+/g, ' ').replace(/ ,/g, ',').trim();
    return t.charAt(0).toUpperCase() + t.slice(1);
  };
  const short = (s, n) => (s.length > (n || 30) ? s.slice(0, (n || 30) - 1) + '…' : s);
  const country = (c) => COUNTRY_NAMES[c] || c;
  const times = (v) => fmt.num(v, 1) + '×';
  const signed = (v, d) => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(d);
  const tone = (change, upIsGood) => (change >= 0 ? (upIsGood ? 'up-good' : 'up-bad') : (upIsGood ? 'down-bad' : 'down-good'));

  /* Label ink on a sequential cell: dark or light, whichever reads on that cell's colour in the current theme. */
  const rgbOf = (hex) => [1, 3, 5].map((k) => parseInt(hex.trim().slice(k, k + 2), 16));
  const luminance = (rgb) => rgb.map((c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; })
    .reduce((sum, c, k) => sum + c * [0.2126, 0.7152, 0.0722][k], 0);
  const inkOn = (t, v) => {
    const pos = Math.max(0, Math.min(1, v)) * (t.seq.length - 1);
    const i = Math.min(Math.floor(pos), t.seq.length - 2);
    const lo = rgbOf(t.seq[i]), hi = rgbOf(t.seq[i + 1]);
    const cell = luminance(lo.map((c, k) => c + (hi[k] - c) * (pos - i)));
    const [dark, light] = luminance(rgbOf(t.text)) < luminance(rgbOf(t.surface)) ? [t.text, t.surface] : [t.surface, t.text];
    return cell > 0.25 ? dark : light;
  };
  const inYear = (row, year) => row.month >= D.meta[year][0] && row.month < D.meta[year][1];
  const monthShort = (iso) => fmt.month(iso).slice(0, 3);

  function segmented(id, attr, onChange) {
    const buttons = Array.from(el(id).querySelectorAll('button'));
    buttons.forEach((b) => b.addEventListener('click', () => {
      buttons.forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      onChange(b.dataset[attr]);
    }));
  }

  function insights(id, items) {
    const box = el(id);
    box.textContent = '';
    items.forEach(([title, body]) => {
      const div = document.createElement('div');
      div.className = 'insight';
      const s = document.createElement('strong');
      s.textContent = title;
      div.append(s, document.createTextNode(body));
      box.appendChild(div);
    });
  }

  function readout(box, big, lines) {
    box.textContent = '';
    const b = document.createElement('span');
    b.className = 'big';
    b.textContent = big;
    box.appendChild(b);
    lines.forEach((l) => { const p = document.createElement('p'); p.style.margin = '6px 0 0'; p.textContent = l; box.appendChild(p); });
  }

  /* Horizontal bars, one series: labels run top to bottom, values labelled at the bar end. */
  function hbar(t, node, spec) {
    return {
      data: [{
        type: 'bar', orientation: 'h', y: spec.labels, x: spec.values,
        marker: { color: spec.color || t.series[0], cornerradius: 4 },
        width: Viz.barWidth(node, spec.labels.length, true, 22, 0.7),
        text: spec.text, textposition: 'outside', textfont: { color: t.text2, size: 12 }, cliponaxis: false,
        error_x: spec.error_x,
        customdata: spec.hover, hovertemplate: '%{customdata}<extra></extra>',
      }],
      layout: {
        margin: { l: 8, r: spec.right == null ? 64 : spec.right, t: 8, b: 8 },
        xaxis: Object.assign({ showgrid: true, showline: false }, spec.xaxis || {}),
        yaxis: { autorange: 'reversed', showgrid: false, tickfont: { color: t.text2, size: 12 } },
      },
    };
  }

  /* ---------- Hero ---------- */
  function hero() {
    const k = D.kpis;
    el('hero-value').textContent = fmt.gbpCompact(k.net_revenue.year2, 2);
    el('hero-caption').textContent = fmt.signedPct(k.net_revenue.change, 1) + ' on the previous twelve months (' +
      fmt.gbpCompact(k.net_revenue.year1, 2) + '), with ' + fmt.signedPct(k.orders.change, 1) + ' orders and ' +
      fmt.signedPct(k.aov.change, 1) + ' average order value.';
    Viz.tile('kpi-orders', { label: 'Orders', value: fmt.int(k.orders.year2), delta: fmt.signedPct(k.orders.change, 1),
      tone: tone(k.orders.change, true), note: 'vs. ' + fmt.int(k.orders.year1) });
    Viz.tile('kpi-aov', { label: 'Average order value', value: fmt.gbp(k.aov.year2), delta: fmt.signedPct(k.aov.change, 1),
      tone: tone(k.aov.change, true), note: 'vs. ' + fmt.gbp(k.aov.year1) });
    Viz.tile('kpi-customers', { label: 'Active customer accounts', value: fmt.int(k.customers.year2), delta: fmt.signedPct(k.customers.change, 1),
      tone: tone(k.customers.change, true), note: 'vs. ' + fmt.int(k.customers.year1) });
    Viz.tile('kpi-repeat', { label: 'Customers with 2+ orders in the year', value: fmt.pct(k.repeat_rate.year2, 1),
      delta: fmt.pp(k.repeat_rate.change, 1), tone: tone(k.repeat_rate.change, true), note: 'vs. ' + fmt.pct(k.repeat_rate.year1, 1) });
    el('meta-size').textContent = fmt.int(D.meta.raw_rows) + ' invoice lines · ' + fmt.date(D.meta.first_invoice.slice(0, 10)) + ' – ' +
      fmt.date(D.meta.last_invoice.slice(0, 10));
  }

  /* ---------- Data quality ---------- */
  function quality() {
    const f = D.funnel;
    const total = f.reduce((s, r) => s + r.lines, 0);
    Viz.card('card-funnel', {
      build: (t) => {
        const trace = (kept, name, color) => {
          const rows = f.filter((r) => r.kept === kept);
          return {
            type: 'bar', orientation: 'h', name, y: rows.map((r) => r.label), x: rows.map((r) => r.lines),
            marker: { color, cornerradius: 4 },
            width: Viz.barWidth('chart-funnel', f.length, true, 22, 0.7),
            text: rows.map((r) => fmt.int(r.lines)), textposition: 'outside', textfont: { color: t.text2, size: 12 }, cliponaxis: false,
            customdata: rows.map((r) => [fmt.pct(r.share, r.share < 0.001 ? 3 : 1), fmt.gbp(r.amount), fmt.int(r.lines_without_customer)]),
            hovertemplate: '<b>%{y}</b><br>%{x:,} lines (%{customdata[0]})<br>Amount: %{customdata[1]}<br>Without a customer ID: %{customdata[2]}<extra>' + name + '</extra>',
          };
        };
        return {
          data: [trace(true, 'Kept for analysis', t.series[0]), trace(false, 'Removed', t.series[1])],
          layout: {
            showlegend: true, barmode: 'overlay', margin: { l: 8, r: 70, t: 30, b: 8 },
            xaxis: { type: 'log', showgrid: true, showline: false, range: [0, 6.75], tickvals: [1, 10, 100, 1e3, 1e4, 1e5, 1e6],
              ticktext: ['1', '10', '100', '1k', '10k', '100k', '1M'] },
            yaxis: { autorange: 'reversed', showgrid: false, categoryorder: 'array', categoryarray: f.map((r) => r.label),
              tickfont: { color: t.text2, size: 12 } },
          },
        };
      },
      table: () => ({ columns: ['Outcome', 'Lines', 'Share of raw lines', 'Amount', 'Without customer ID', 'Kept'],
        rows: f.map((r) => [r.label, fmt.int(r.lines), fmt.pct(r.share, 2), fmt.gbp(r.amount), fmt.int(r.lines_without_customer), r.kept ? 'Yes' : 'No']) }),
    });

    const by = Object.fromEntries(f.map((r) => [r.status, r]));
    const err = by['price error'];
    insights('insights-quality', [
      [fmt.pct(by.sale.share, 1) + ' of lines are product sales', fmt.int(by.sale.lines) + ' of ' + fmt.int(total) + ' lines. The ' +
        fmt.int(by.cancellation.lines) + ' cancellation lines stay in and are netted against revenue.'],
      ['Duplicates would have inflated revenue', fmt.int(by.duplicate.lines) + ' exact duplicate lines worth ' + fmt.gbp(by.duplicate.amount) + ', ' +
        fmt.pct(by.duplicate.amount / by.sale.amount, 1) + ' of gross product sales.'],
      [fmt.int(err.lines) + ' price keying errors, ' + fmt.gbp(err.amount), 'Lines priced over ' + D.meta.price_error_factor +
        "× the product's median price, such as a 60-piece hamper price charged for each of 60 hampers (£38,970, later reversed by a manual credit)."],
      ['A fifth of sales are guest checkouts', fmt.pct(by.sale.lines_without_customer / by.sale.lines, 1) +
        ' of sale lines have no customer ID. They count toward revenue and orders, not toward customer metrics.'],
    ]);
  }

  /* ---------- Trading ---------- */
  function trading() {
    const state = { measure: 'net_revenue' };
    const y1 = D.monthly.filter((r) => inYear(r, 'year1'));
    const y2 = D.monthly.filter((r) => inYear(r, 'year2'));
    const labels = y2.map((r) => monthShort(r.month));

    const values = () => [y1.map((r) => r[state.measure]), y2.map((r) => r[state.measure])];
    const monthly = Viz.card('card-monthly', {
      build: (t) => {
        const m = MEASURES[state.measure];
        const [v1, v2] = values();
        const marker = (c) => ({ size: 8, color: c, line: { color: t.surface, width: 2 } });
        return {
          data: [
            { type: 'scatter', mode: 'lines+markers', name: 'Year 1', x: labels, y: v1, line: { color: t.muted, width: 2, dash: 'dash' },
              marker: marker(t.muted), customdata: v1.map(m.value), hovertemplate: 'Year 1: %{customdata}<extra></extra>' },
            { type: 'scatter', mode: 'lines+markers', name: 'Year 2', x: labels, y: v2, line: { color: t.series[0], width: 2 },
              marker: marker(t.series[0]), customdata: v2.map((v, i) => [m.value(v), fmt.signedPct(v / v1[i] - 1, 1)]),
              hovertemplate: 'Year 2: %{customdata[0]} (%{customdata[1]})<extra></extra>' },
          ],
          layout: {
            showlegend: true, hovermode: 'x unified', margin: { l: 8, r: 14, t: 30, b: 8 },
            xaxis: Object.assign({}, Viz.crosshair(t)),
            yaxis: Object.assign({ rangemode: 'tozero' }, m.axis),
          },
        };
      },
      table: () => {
        const m = MEASURES[state.measure];
        const [v1, v2] = values();
        return { columns: ['Month', 'Year 1', 'Year 2', 'Change'],
          rows: labels.map((l, i) => [l, m.value(v1[i]), m.value(v2[i]), fmt.signedPct(v2[i] / v1[i] - 1, 1)]) };
      },
    });
    segmented('trend-control', 'measure', (v) => {
      state.measure = v;
      el('monthly-title').textContent = MEASURES[v].label + ' by month';
      monthly.update();
    });

    const W = D.weekday_hour;
    const hours = W.hours.map((h) => String(h).padStart(2, '0') + ':00');
    Viz.card('card-timing', {
      build: (t) => ({
        data: [{
          type: 'heatmap', z: W.orders, x: hours, y: W.weekdays.map((d) => DAY_NAMES[d]), colorscale: t.seqScale, zmin: 0, xgap: 2, ygap: 2,
          colorbar: { thickness: 10, outlinewidth: 0, tickfont: { color: t.muted, size: 11 }, tickformat: ',.0f',
            title: { text: 'Orders', font: { color: t.text2, size: 12 } } },
          hovertemplate: '%{y} %{x}: %{z:,} orders<extra></extra>',
        }],
        layout: {
          margin: { l: 8, r: 8, t: 8, b: 8 },
          xaxis: { showgrid: false, showline: false, tickvals: hours.filter((_, i) => i % 2 === 0), tickangle: 0 },
          yaxis: { autorange: 'reversed', showgrid: false, tickfont: { color: t.text2, size: 12 } },
        },
      }),
      table: () => ({ columns: ['Weekday'].concat(hours), rows: W.weekdays.map((d, i) => [DAY_NAMES[d]].concat(W.orders[i].map(fmt.int))) }),
    });
    const sun = W.orders[W.weekdays.indexOf('Sun')] || [];
    const sunHours = W.hours.filter((_, j) => sun[j] >= 5);
    el('timing-note').textContent = 'Saturday is left out: ' + fmt.int(D.meta.saturday_orders) + ' orders in two years.' +
      (sunHours.length ? ' Sunday orders arrive only between ' + String(sunHours[0]).padStart(2, '0') + ':00 and ' +
        String(sunHours[sunHours.length - 1] + 1).padStart(2, '0') + ':00.' : '');

    const total2 = y2.reduce((s, r) => s + r.net_revenue, 0);
    const peak = y2.filter((r) => ['09', '10', '11'].includes(r.month.slice(5, 7))).reduce((s, r) => s + r.net_revenue, 0);
    const nov = y2.find((r) => r.month.slice(5, 7) === '11');
    const hourTotals = W.hours.map((_, j) => W.orders.reduce((s, row) => s + row[j], 0));
    const dayTotals = W.orders.map((row) => row.reduce((s, v) => s + v, 0));
    const bestHour = W.hours[hourTotals.indexOf(Math.max(...hourTotals))];
    const bestDay = W.weekdays[dayTotals.indexOf(Math.max(...dayTotals))];
    const allOrders = hourTotals.reduce((a, b) => a + b, 0);
    const offHours = W.hours.reduce((s, h, j) => s + (h < 8 || h >= 18 ? hourTotals[j] : 0), 0);
    const k = D.kpis;
    insights('insights-trading', [
      ['Christmas makes the year', 'September to November brought ' + fmt.pct(peak / total2, 0) + ' of year-2 revenue; November alone ' +
        fmt.gbpCompact(nov.net_revenue, 2) + '. Wholesale buyers stock up well before December.'],
      ['Fewer, larger orders', 'Year-2 orders fell ' + fmt.pct(Math.abs(k.orders.change), 1) + ' but the average order rose ' +
        fmt.pct(k.aov.change, 1) + ' to ' + fmt.gbp(k.aov.year2) + ', so revenue still grew ' + fmt.pct(k.net_revenue.change, 1) + '.'],
      ['Orders follow office hours', 'The busiest hour is ' + bestHour + ':00–' + (bestHour + 1) + ':00 and the busiest day ' + DAY_NAMES[bestDay] +
        '. Only ' + fmt.pct(offHours / allOrders, 0) + ' of orders arrive before 08:00 or after 18:00.'],
    ]);
  }

  /* ---------- Revenue mix ---------- */
  function mix() {
    const y2 = D.monthly.filter((r) => inYear(r, 'year2'));
    const TYPES = [['revenue_returning', 'Returning customers'], ['revenue_new', 'New customers'], ['revenue_guest', 'Guest checkouts']];
    const months = y2.map((r) => fmt.month(r.month));
    Viz.card('card-mix', {
      build: (t) => ({
        data: TYPES.map(([key, name], i) => ({
          type: 'bar', name, x: months, y: y2.map((r) => r[key]),
          marker: { color: t.series[i], line: { color: t.surface, width: 1 } },
          width: Viz.barWidth('chart-mix', months.length, false, 30, 0.7),
          customdata: y2.map((r) => fmt.gbp(r[key])), hovertemplate: name + ': %{customdata}<extra></extra>',
        })),
        layout: {
          barmode: 'stack', barcornerradius: 4, showlegend: true, legend: { traceorder: 'normal' }, hovermode: 'x unified', margin: { l: 8, r: 14, t: 30, b: 8 },
          xaxis: { tickvals: months, ticktext: months.map((m) => m.slice(0, 3)), tickangle: 0 },
          yaxis: { tickprefix: '£', tickformat: '~s' },
        },
      }),
      table: () => ({ columns: ['Month', 'Returning', 'New', 'Guest', 'Total', 'New customers'],
        rows: y2.map((r, i) => [months[i], fmt.gbp(r.revenue_returning), fmt.gbp(r.revenue_new), fmt.gbp(r.revenue_guest),
          fmt.gbp(r.net_revenue), fmt.int(r.new_customers)]) }),
    });

    const C = D.countries;
    Viz.card('card-countries', {
      build: (t) => hbar(t, 'chart-countries', {
        labels: C.map((c) => country(c.country)), values: C.map((c) => c.revenue_share), text: C.map((c) => fmt.pct(c.revenue_share, 1)),
        hover: C.map((c) => '<b>' + country(c.country) + '</b><br>' + fmt.gbp(c.net_revenue) + ' (' + fmt.pct(c.revenue_share, 1) + ')<br>' +
          fmt.int(c.orders) + ' orders · ' + fmt.int(c.customers) + ' customer accounts'),
        xaxis: { tickformat: '.0%', range: [0, 1.0] },
      }),
      table: () => ({ columns: ['Country', 'Net revenue', 'Share', 'Orders', 'Customer accounts'],
        rows: C.map((c) => [country(c.country), fmt.gbp(c.net_revenue), fmt.pct(c.revenue_share, 1), fmt.int(c.orders), fmt.int(c.customers)]) }),
    });

    const P = D.products;
    const top = P.top.slice(0, 10);
    Viz.card('card-products', {
      build: (t) => hbar(t, 'chart-products', {
        labels: top.map((p) => short(nice(p.description), 28)), values: top.map((p) => p.net_revenue),
        text: top.map((p) => fmt.gbpCompact(p.net_revenue, 0)),
        hover: top.map((p) => '<b>' + nice(p.description) + '</b> (' + p.stock_code + ')<br>' + fmt.gbp(p.net_revenue) + ' · ' +
          fmt.int(p.net_units) + ' units<br>' + fmt.int(p.orders) + ' orders · ' + fmt.int(p.customers) + ' customer accounts'),
        xaxis: { tickprefix: '£', tickformat: '~s' }, right: 50,
      }),
      table: () => ({ columns: ['Product', 'Code', 'Net revenue', 'Units', 'Orders', 'Customer accounts'],
        rows: P.top.map((p) => [nice(p.description), p.stock_code, fmt.gbp(p.net_revenue), fmt.int(p.net_units), fmt.int(p.orders), fmt.int(p.customers)]) }),
    });

    const par = P.pareto;
    Viz.card('card-pareto', {
      build: (t) => {
        const x = par.curve.product_share.map((v) => v * 100);
        const y = par.curve.revenue_share.map((v) => v * 100);
        const sx = par.share_for_80 * 100;
        return {
          data: [{ type: 'scatter', mode: 'lines', x, y, line: { color: t.series[0], width: 2 },
            hovertemplate: 'Top %{x:.0f}% of products: %{y:.1f}% of revenue<extra></extra>' }],
          layout: {
            hovermode: 'x', margin: { l: 8, r: 14, t: 12, b: 8 },
            xaxis: Object.assign({ title: { text: 'Share of products, best sellers first' }, ticksuffix: '%', range: [0, 100] }, Viz.crosshair(t)),
            yaxis: { title: { text: 'Share of revenue' }, ticksuffix: '%', range: [0, 102] },
            shapes: [
              { type: 'line', x0: 0, x1: sx, y0: 80, y1: 80, line: { color: t.baseline, width: 1, dash: 'dot' } },
              { type: 'line', x0: sx, x1: sx, y0: 0, y1: 80, line: { color: t.baseline, width: 1, dash: 'dot' } },
            ],
            annotations: [{ x: sx, y: 80, xanchor: 'left', yanchor: 'top', xshift: 8, yshift: -6, showarrow: false, align: 'left',
              text: fmt.pct(par.share_for_80, 0) + ' of products (' + fmt.int(par.products_for_80) + ')<br>earn 80% of revenue',
              font: { color: t.text2, size: 12 } }],
          },
        };
      },
      table: () => ({ columns: ['Share of products', 'Share of revenue'],
        rows: par.curve.product_share.map((s, i) => [fmt.pct(s, 0), fmt.pct(par.curve.revenue_share[i], 1)]).filter((_, i) => i % 5 === 0) }),
    });

    const m = D.kpis.mix_year2;
    const byCountry = Object.fromEntries(C.map((c) => [c.country, c]));
    const uk = byCountry['United Kingdom'], ie = byCountry.EIRE, nl = byCountry.Netherlands;
    insights('insights-mix', [
      ['Returning customers carry the business', 'In year 2, ' + fmt.pct(m.returning, 0) + ' of revenue came from customers who had ordered in an earlier month, ' +
        fmt.pct(m.new, 0) + ' from new customers and ' + fmt.pct(m.guest, 0) + ' from guest checkouts.'],
      ['A long tail of products', fmt.int(par.products_for_80) + ' of ' + fmt.int(par.products) + ' products (' + fmt.pct(par.share_for_80, 0) +
        ') earn 80% of revenue. The best seller (' + nice(P.top[0].description) + ') earned ' + fmt.gbpCompact(P.top[0].net_revenue, 0) + '.'],
      ['Abroad, a few large accounts', 'The UK is ' + fmt.pct(uk.revenue_share, 0) + ' of revenue. ' +
        (ie && nl ? "Ireland's " + fmt.pct(ie.revenue_share, 1) + ' came mostly from ' + ie.customers + " customer accounts, the Netherlands' " +
          fmt.pct(nl.revenue_share, 1) + ' from ' + nl.customers + '.' : '')],
    ]);
  }

  /* ---------- Cohorts ---------- */
  function cohortsSection() {
    const C = D.cohorts;
    const state = { view: 'retention' };
    const rows = C.cohorts.slice(0, -1); // the newest cohort has only its first month
    const label = (c) => fmt.month(c + '-01');
    const TABLE_MONTHS = { retention: [1, 2, 3, 6, 9, 12, 18], value: [0, 1, 3, 6, 12, 18] };
    const cellText = (v) => (v == null ? '' : state.view === 'retention' ? fmt.pct(v, 1) : fmt.gbp(v));

    const card = Viz.card('card-cohorts', {
      build: (t) => {
        const ret = state.view === 'retention';
        const months = ret ? C.months.filter((m) => m > 0) : C.months;
        const src = ret ? C.retention : C.value;
        const z = rows.map((_, i) => months.map((m) => src[i][m]));
        const max = Math.max(...z.flat().filter((v) => v != null));
        return {
          data: [{
            type: 'heatmap', z, x: months, y: rows.map(label), colorscale: t.seqScale, zmin: 0, zmax: ret ? Math.ceil(max * 20) / 20 : max,
            xgap: 2, ygap: 2, hoverongaps: false,
            customdata: rows.map((_, i) => months.map(() => fmt.int(C.sizes[i]))),
            hovertemplate: ret
              ? '<b>%{y} cohort</b> (%{customdata} new customers)<br>Month %{x}: %{z:.1%} ordered<extra></extra>'
              : '<b>%{y} cohort</b> (%{customdata} new customers)<br>By month %{x}: £%{z:,.0f} per customer<extra></extra>',
            colorbar: { thickness: 10, outlinewidth: 0, tickfont: { color: t.muted, size: 11 }, tickformat: ret ? '.0%' : ',.0f', tickprefix: ret ? '' : '£' },
          }],
          layout: {
            margin: { l: 8, r: 8, t: 8, b: 8 },
            xaxis: { title: { text: 'Months since first order' }, showgrid: false, showline: false, dtick: 2 },
            yaxis: { autorange: 'reversed', showgrid: false, tickfont: { color: t.text2, size: 11 } },
          },
        };
      },
      table: () => {
        const ms = TABLE_MONTHS[state.view];
        const src = state.view === 'retention' ? C.retention : C.value;
        return { columns: ['Cohort', 'New customers'].concat(ms.map((m) => 'Month ' + m)),
          rows: rows.map((c, i) => [label(c), fmt.int(C.sizes[i])].concat(ms.map((m) => cellText(src[i][m])))) };
      },
    });
    segmented('cohort-control', 'view', (v) => {
      state.view = v;
      el('cohort-title').textContent = v === 'retention' ? 'Cohort retention' : 'Cumulative revenue per new customer';
      el('cohort-sub').textContent = v === 'retention'
        ? "Share of each month's new customers who ordered in each later month"
        : "Net revenue per acquired customer up to each month, including the first";
      card.update();
    });

    const R = C.avg_retention;
    const rv = (m) => R.value[R.months.indexOf(m)];
    const marker = (t) => ({ size: 8, color: t.series[0], line: { color: t.surface, width: 2 } });
    Viz.card('card-retention', {
      build: (t) => {
        const xs = R.months.filter((m) => m > 0);
        return {
          data: [{ type: 'scatter', mode: 'lines+markers', x: xs, y: xs.map(rv), line: { color: t.series[0], width: 2 }, marker: marker(t),
            hovertemplate: 'Month %{x}: %{y:.1%} ordered<extra></extra>' }],
          layout: {
            hovermode: 'x', margin: { l: 8, r: 14, t: 12, b: 8 },
            xaxis: Object.assign({ title: { text: 'Months since first order' }, dtick: 2 }, Viz.crosshair(t)),
            yaxis: { tickformat: '.0%', rangemode: 'tozero' },
            annotations: xs.includes(12) ? [{ x: 12, y: rv(12), text: 'Back for the same season', showarrow: true, arrowcolor: t.baseline,
              arrowwidth: 1, ax: 0, ay: -34, font: { color: t.text2, size: 12 } }] : [],
          },
        };
      },
      table: () => ({ columns: ['Months since first order', 'Share ordering'],
        rows: R.months.filter((m) => m > 0).map((m) => [String(m), fmt.pct(rv(m), 1)]) }),
    });

    const V = C.avg_value;
    const vv = (m) => V.value[V.months.indexOf(m)];
    Viz.card('card-value', {
      build: (t) => ({
        data: [{ type: 'scatter', mode: 'lines+markers', x: V.months, y: V.value, line: { color: t.series[0], width: 2 }, marker: marker(t),
          hovertemplate: 'By month %{x}: £%{y:,.0f} per customer<extra></extra>' }],
        layout: {
          hovermode: 'x', margin: { l: 8, r: 14, t: 12, b: 8 },
          xaxis: Object.assign({ title: { text: 'Months since first order (0 = the first month)' }, dtick: 2 }, Viz.crosshair(t)),
          yaxis: { tickprefix: '£', tickformat: ',.0f', rangemode: 'tozero' },
          annotations: [
            { x: 0, y: vv(0), text: fmt.gbp(vv(0)) + ' in the first month', showarrow: true, arrowcolor: t.baseline, arrowwidth: 1, ax: 30, ay: 20, yanchor: 'top',
              xanchor: 'left', font: { color: t.text2, size: 12 } },
            { x: 11, y: vv(11), text: fmt.gbp(vv(11)) + ' over the first year', showarrow: true, arrowcolor: t.baseline, arrowwidth: 1, ax: -20, ay: -46,
              xanchor: 'right', font: { color: t.text2, size: 12 } },
          ],
        },
      }),
      table: () => ({ columns: ['Months since first order', 'Revenue per customer to date'], rows: V.months.map((m, i) => [String(m), fmt.gbp(V.value[i])]) }),
    });

    const early = [1, 2, 3, 4, 5, 6, 7].map(rv);
    const late = [8, 9, 10, 11];
    const dip = Math.min(...late.map(rv));
    const dec = C.cohorts.indexOf('2010-12');
    insights('insights-cohorts', [
      ['One in five come back the next month', fmt.pct(rv(1), 0) + ' of new customers order again in the month after their first order, and ' +
        fmt.pct(Math.min(...early), 0).replace('%', '') + '–' + fmt.pct(Math.max(...early), 0) + ' are active in each of months 1–7.'],
      ['They return for the same season', 'Activity sags to ' + fmt.pct(dip, 1) + ' by month ' + late[late.map(rv).indexOf(dip)] +
        ' and rebounds to ' + fmt.pct(rv(12), 1) + ' at month 12, when the season that brought them in comes round again.'],
      ['First-year value is ' + times(vv(11) / vv(0)) + ' the first month', 'A new customer brings ' + fmt.gbp(vv(0)) +
        ' in the month they are acquired and ' + fmt.gbp(vv(11)) + ' over their first twelve months.'],
      ['Christmas shoppers churn', dec >= 0 ? 'Only ' + fmt.pct(C.retention[dec][1], 0) + " of December 2010's new customers ordered in January, against " +
        fmt.pct(rv(1), 0) + ' for the average cohort.' : ''],
    ]);
  }

  /* ---------- RFM ---------- */
  function rfmSection() {
    const R = D.rfm;
    const segs = R.segments;
    const seg = Object.fromEntries(segs.map((s) => [s.segment, s]));
    const testWindow = D.model.windows.find((w) => w.role === 'test');

    Viz.card('card-segments', {
      build: (t) => {
        const bar = (key, name, color) => ({
          type: 'bar', orientation: 'h', name, y: segs.map((s) => s.segment), x: segs.map((s) => s[key]),
          marker: { color, cornerradius: 4 },
          customdata: segs.map((s) => [fmt.int(s.customers), fmt.gbp(s.revenue)]),
          hovertemplate: '<b>%{y}</b><br>' + name + ': %{x:.1%}<br>%{customdata[0]} customers · %{customdata[1]}<extra></extra>',
        });
        return {
          data: [bar('customer_share', 'Share of customers', t.series[0]), bar('revenue_share', 'Share of revenue', t.series[1])],
          layout: {
            showlegend: true, barmode: 'group', bargap: 0.28, bargroupgap: 0.12, margin: { l: 8, r: 16, t: 30, b: 8 },
            xaxis: { tickformat: '.0%', showgrid: true, showline: false },
            yaxis: { autorange: 'reversed', showgrid: false, tickfont: { color: t.text2, size: 12 } },
          },
        };
      },
      table: () => ({ columns: ['Segment', 'Customers', 'Share of customers', 'Revenue', 'Share of revenue'],
        rows: segs.map((s) => [s.segment, fmt.int(s.customers), fmt.pct(s.customer_share, 1), fmt.gbp(s.revenue), fmt.pct(s.revenue_share, 1)]) }),
    });

    const RS = [5, 4, 3, 2, 1];
    const FS = [1, 2, 3, 4, 5];
    const cell = (r, f) => R.grid.find((g) => g.r_score === r && g.f_score === f);
    const yLabels = RS.map((r) => 'R' + r);
    const wrapName = (s) => (s.length > 12 ? s.replace(' ', '<br>') : s);
    Viz.card('card-rfgrid', {
      build: (t) => {
        const z = RS.map((r) => FS.map((f) => cell(r, f).customers));
        const max = Math.max(...z.flat());
        const annotations = [];
        RS.forEach((r, i) => FS.forEach((f, j) => {
          const c = cell(r, f);
          annotations.push({ x: R.f_labels[j], y: yLabels[i], showarrow: false, text: wrapName(c.segment) + '<br>' + fmt.int(c.customers),
            font: { size: 11, color: inkOn(t, c.customers / max) } });
        }));
        return {
          data: [{
            type: 'heatmap', z, x: R.f_labels, y: yLabels, colorscale: t.seqScale, zmin: 0, xgap: 2, ygap: 2, showscale: false,
            customdata: RS.map((r) => FS.map((f) => [cell(r, f).segment, fmt.gbp(cell(r, f).revenue)])),
            hovertemplate: '<b>%{customdata[0]}</b><br>Recency %{y}, %{x}<br>%{z:,} customers · %{customdata[1]}<extra></extra>',
          }],
          layout: {
            annotations, margin: { l: 8, r: 8, t: 8, b: 8 },
            xaxis: { title: { text: 'Orders to date' }, showgrid: false, showline: false },
            yaxis: { title: { text: 'Recency score (R5 = most recent fifth)' }, autorange: 'reversed', showgrid: false, tickfont: { color: t.text2, size: 12 } },
          },
        };
      },
      table: () => ({ columns: ['Recency score'].concat(R.f_labels),
        rows: RS.map((r) => ['R' + r].concat(FS.map((f) => cell(r, f).segment + ': ' + fmt.int(cell(r, f).customers)))) }),
    });

    const box = el('segment-table');
    Viz.renderTable(box, {
      columns: ['Segment', 'Customers', 'Share of revenue', 'Median days since last order', 'Median orders', 'Median spend',
        'Ordered in next 90 days*', 'Predicted now', 'Recommended action'],
      rows: segs.map((s) => [s.segment, fmt.int(s.customers), fmt.pct(s.revenue_share, 1), fmt.int(s.median_recency), fmt.num(s.median_frequency, 0),
        fmt.gbp(s.median_monetary), fmt.pct(s.repurchase_rate, 0), fmt.pct(s.mean_propensity, 0), s.action]),
    });
    box.querySelectorAll('tbody td:last-child').forEach((td) => { td.classList.add('wrap-cell'); td.style.minWidth = '260px'; });
    el('playbook-note').textContent = '* Backtest: segments assigned as of ' + fmt.date(testWindow.cutoff) +
      ' and checked against orders in the following 90 days. "Predicted now" is the repurchase model\'s average probability of an order in the next 90 days, as of ' +
      fmt.date(D.meta.snapshot) + '.';

    const sum = (key, names) => names.reduce((s, n) => s + seg[n][key], 0);
    const best = ['Champions', 'Loyal'];
    const risk = ['At risk', "Can't lose them"];
    insights('insights-rfm', [
      ['A third of customers, four-fifths of revenue', 'Champions and Loyal customers are ' + fmt.pct(sum('customer_share', best), 0) +
        ' of the base and ' + fmt.pct(sum('revenue_share', best), 0) + ' of revenue.'],
      ['The segments predict behaviour', 'Assigned on ' + fmt.date(testWindow.cutoff) + ', ' + fmt.pct(seg.Champions.repurchase_rate, 0) +
        ' of Champions ordered in the next 90 days, against ' + fmt.pct(seg.Lost.repurchase_rate, 0) + ' of Lost customers.'],
      [fmt.gbpCompact(sum('revenue', risk), 2) + ' of past revenue has gone quiet', fmt.int(sum('customers', risk)) + " At-risk and Can't-lose customers (" +
        fmt.pct(sum('customer_share', risk), 0) + ' of the base) used to order often but have not ordered for about a year: the win-back list.'],
    ]);
  }

  /* ---------- Repurchase model ---------- */
  function modelSection() {
    const M = D.model;
    const sel = M.selected;
    const met = Object.fromEntries(M.metrics.map((r) => [r.key, r]));
    const val = Object.fromEntries(M.selection.map((r) => [r.key, r]));
    const test = M.windows.find((w) => w.role === 'test');
    const fitWindows = M.windows.filter((w) => w.role !== 'test');
    const count = ['No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six'][fitWindows.length] || String(fitWindows.length);
    el('model-lede').textContent = 'Will a customer order again within ' + M.horizon_days + ' days? Each customer is described only by their history ' +
      'before a cutoff date and labelled by what they did in the ' + M.horizon_days + ' days after it. ' + count + ' quarterly cutoffs (' +
      fmt.int(M.n_train) + ' customer-quarters) train the models and the most recent of them picks the winner; the quarter from ' +
      fmt.date(test.cutoff) + ' (' + fmt.int(M.n_test) + ' customers, ' + fmt.pct(test.base_rate, 0) + ' of whom ordered) is held out for one final test.';

    const state = { measure: 'buyers', share: Number(el('model-share').value) };
    const gains = Viz.card('card-gains', {
      build: (t) => {
        const g = M.gains;
        const x = g[sel].fraction.map((f) => f * 100);
        const y = (key) => g[key][state.measure].map((v) => v * 100);
        return {
          data: [
            { type: 'scatter', mode: 'lines', name: 'Random', x, y: x, line: { color: t.muted, width: 2, dash: 'dash' },
              hovertemplate: 'Random: %{y:.0f}%<extra></extra>' },
            { type: 'scatter', mode: 'lines', name: 'RFM score', x, y: y('rfm'), line: { color: t.series[1], width: 2 },
              hovertemplate: 'RFM score: %{y:.1f}%<extra></extra>' },
            { type: 'scatter', mode: 'lines', name: met[sel].name, x, y: y(sel), line: { color: t.series[0], width: 2 },
              hovertemplate: met[sel].name + ': %{y:.1f}%<extra></extra>' },
          ],
          layout: {
            showlegend: true, hovermode: 'x unified', margin: { l: 8, r: 14, t: 30, b: 8 },
            xaxis: Object.assign({ title: { text: 'Customers contacted, highest score first' }, ticksuffix: '%', range: [0, 100] }, Viz.crosshair(t)),
            yaxis: { title: { text: state.measure === 'buyers' ? 'Next-quarter buyers reached' : 'Next-quarter revenue reached' },
              ticksuffix: '%', range: [0, 102] },
            shapes: [{ type: 'line', yref: 'paper', y0: 0, y1: 1, x0: state.share, x1: state.share, line: { color: t.text2, width: 1, dash: 'dot' } }],
          },
        };
      },
      table: () => {
        const g = M.gains;
        return { columns: ['Contacted', met[sel].name, 'RFM score', 'Random'],
          rows: g[sel].fraction.map((f, i) => [fmt.pct(f, 0), fmt.pct(g[sel][state.measure][i], 1), fmt.pct(g.rfm[state.measure][i], 1), fmt.pct(f, 0)])
            .filter((_, i) => i % 5 === 0) };
      },
    });

    function updateReadout() {
      const g = M.gains;
      const i = Math.round(state.share);
      const b = g[sel].buyers[i], br = g.rfm.buyers[i], r = g[sel].revenue[i], rr = g.rfm.revenue[i];
      const n = Math.round((M.n_test * state.share) / 100);
      el('out-share').textContent = state.share + '%';
      el('model-sub').textContent = 'Top ' + state.share + '% of ' + fmt.int(M.n_test) + ' held-out customers, ranked by the model';
      readout(el('model-readout'), fmt.pct(b, 0), [
        'of next-quarter buyers reached by contacting ' + fmt.int(n) + ' customers: ' + fmt.int(Math.round(b * M.test_buyers)) + ' of ' +
          fmt.int(M.test_buyers) + '.',
        'Ranking by RFM score reaches ' + fmt.pct(br, 0) + '; picking at random, ' + state.share + '%.',
        'These customers went on to place ' + fmt.pct(r, 0) + ' of next-quarter revenue (RFM ranking: ' + fmt.pct(rr, 0) + '), ' +
          times(r / (state.share / 100)) + ' their share of the list.',
      ]);
    }
    el('model-share').addEventListener('input', (e) => { state.share = Number(e.target.value); updateReadout(); gains.update(); });
    segmented('gains-control', 'measure', (v) => {
      state.measure = v;
      el('gains-title').textContent = v === 'buyers' ? 'Next-quarter buyers reached' : 'Next-quarter revenue reached';
      gains.update();
    });
    updateReadout();

    const dec = M.deciles;
    Viz.card('card-deciles', {
      build: (t) => ({
        data: [
          { type: 'bar', name: 'Actually ordered', x: dec.map((r) => r.decile), y: dec.map((r) => r.observed),
            marker: { color: t.series[0], cornerradius: 4 }, width: Viz.barWidth('chart-deciles', 10, false, 28, 0.6),
            hovertemplate: 'Actually ordered: %{y:.1%}<extra></extra>' },
          { type: 'scatter', mode: 'markers', name: 'Model prediction', x: dec.map((r) => r.decile), y: dec.map((r) => r.predicted),
            marker: { color: t.series[1], size: 10, symbol: 'diamond', line: { color: t.surface, width: 2 } },
            hovertemplate: 'Predicted: %{y:.1%}<extra></extra>' },
        ],
        layout: {
          showlegend: true, hovermode: 'x unified', margin: { l: 8, r: 14, t: 30, b: 8 },
          xaxis: { title: { text: 'Score decile (1 = highest predicted probability)' }, dtick: 1 },
          yaxis: { tickformat: '.0%', range: [0, 1] },
        },
      }),
      table: () => ({ columns: ['Decile', 'Customers', 'Predicted', 'Actually ordered', 'Revenue per customer', 'Share of revenue'],
        rows: dec.map((r) => [String(r.decile), fmt.int(r.customers), fmt.pct(r.predicted, 1), fmt.pct(r.observed, 1), fmt.gbp(r.revenue_per_customer),
          fmt.pct(r.revenue_share, 1)]) }),
    });

    const imp = M.importance.slice(0, 10);
    Viz.card('card-importance', {
      build: (t) => hbar(t, 'chart-importance', {
        labels: imp.map((r) => r.label), values: imp.map((r) => r.importance), text: imp.map((r) => r.importance.toFixed(3)),
        error_x: { type: 'data', array: imp.map((r) => r.std), thickness: 1.5, width: 0, color: t.text2 },
        hover: imp.map((r) => '<b>' + r.label + '</b><br>' + r.importance.toFixed(4) + ' ± ' + r.std.toFixed(4)),
        xaxis: { title: { text: 'Drop in average precision when shuffled' }, rangemode: 'tozero' },
      }),
      table: () => ({ columns: ['Feature', 'Importance', 'Std. dev. (10 shuffles)'],
        rows: M.importance.map((r) => [r.label, r.importance.toFixed(4), r.std.toFixed(4)]) }),
    });

    Viz.renderTable(el('model-table'), {
      columns: ['Model', 'Validation PR AUC', 'Test ROC AUC', 'Test PR AUC', 'Brier score', 'Top-decile lift', 'Buyers in top 20%', 'Revenue in top 20%'],
      rows: M.metrics.map((r) => [r.name + (r.key === sel ? ' (selected)' : ''), val[r.key].pr_auc.toFixed(3), r.roc_auc.toFixed(3), r.pr_auc.toFixed(3),
        r.brier.toFixed(3), times(r.top_decile_lift), fmt.pct(r.buyers_captured, 1), fmt.pct(r.revenue_captured, 1)]),
    });
    const bs = M.bootstrap;
    el('model-note').textContent = 'Paired bootstrap of the held-out quarter (' + M.n_boot + ' resamples), ' + met[sel].name.toLowerCase() +
      ' minus RFM score: ROC AUC ' + signed(met[sel].roc_auc - met.rfm.roc_auc, 3) + ' (95% CI ' + signed(bs.roc_auc.low, 3) + ' to ' +
      signed(bs.roc_auc.high, 3) + '); revenue in the top 20% ' + fmt.pp(met[sel].revenue_captured - met.rfm.revenue_captured, 1) + ' (' +
      fmt.pp(bs.revenue_captured.low, 1) + ' to ' + fmt.pp(bs.revenue_captured.high, 1) + '). Lower Brier score is better.';

    const top = dec[0];
    const recency = M.importance.find((r) => r.feature === 'recency_days');
    insights('insights-model', [
      ['Beats the RFM rule out of time', 'ROC AUC ' + met[sel].roc_auc.toFixed(3) + ' against ' + met.rfm.roc_auc.toFixed(3) + ' (' +
        signed(met[sel].roc_auc - met.rfm.roc_auc, 3) + ', 95% CI ' + signed(bs.roc_auc.low, 3) + ' to ' + signed(bs.roc_auc.high, 3) +
        '), and average precision ' + met[sel].pr_auc.toFixed(3) + ' against ' + met.rfm.pr_auc.toFixed(3) + '. At the very top the two agree.'],
      ['The top decile almost always reorders', fmt.pct(top.observed, 0) + ' of the highest-scored tenth ordered within ' + M.horizon_days + ' days (' +
        times(top.observed / test.base_rate) + ' the average) and they brought ' + fmt.pct(top.revenue_share, 0) + " of the quarter's revenue."],
      ['Breadth of engagement matters most', M.importance[0].label + ' and ' + M.importance[1].label.toLowerCase() + ' carry most of the signal.' +
        (recency && recency.importance < 0.002 ? ' Days since the last order adds almost nothing once recent order counts are known.' : '')],
      ['Rank, then recalibrate', 'The held-out quarter is the Christmas peak: ' + fmt.pct(test.base_rate, 0) + ' ordered against ' +
        fmt.pct(met[sel].mean_predicted, 0) + ' predicted on average. The ranking holds; recalibrate on the latest quarter before reading the probabilities as forecasts.'],
    ]);
  }

  /* ---------- Market basket ---------- */
  function basketSection() {
    const B = D.basket;
    const name = (code) => nice(B.names[code] || code);
    const select = el('basket-item');
    B.items.forEach((it) => {
      const o = document.createElement('option');
      o.value = it.code;
      o.textContent = nice(it.name) + ' (' + fmt.int(it.invoices) + ' orders)';
      select.appendChild(o);
    });
    const rulesFor = (code) => B.rules.filter((r) => r.antecedent === code).sort((a, b) => b.lift - a.lift);
    el('basket-lede').textContent = 'Orders here are wholesale-sized: the median order holds ' + fmt.int(B.sizes.median_products) +
      ' different products and ' + fmt.pct(B.sizes.multi_product_share, 0) + ' contain more than one. Among the ' + B.top_products +
      ' most-ordered products, ' + fmt.int(B.n_pairs) + ' pairs share at least ' + B.min_together + ' orders. Pick a product to see what goes with it.';

    const card = Viz.card('card-basket', {
      build: (t) => {
        const rs = rulesFor(select.value);
        return hbar(t, 'chart-basket', {
          labels: rs.map((r) => short(name(r.consequent), 30)), values: rs.map((r) => r.lift), text: rs.map((r) => times(r.lift)),
          hover: rs.map((r) => '<b>' + name(r.consequent) + '</b><br>In ' + fmt.pct(r.confidence, 0) + ' of orders with the selected product (' +
            fmt.int(r.together) + ' orders)<br>Lift ' + times(r.lift)),
          xaxis: { title: { text: 'Lift (times more often than chance)' }, rangemode: 'tozero' }, right: 48,
        });
      },
      table: () => ({ columns: ['Bought with it', 'Orders together', 'Confidence', 'Lift'],
        rows: rulesFor(select.value).map((r) => [name(r.consequent), fmt.int(r.together), fmt.pct(r.confidence, 0), times(r.lift)]) }),
    });
    function relabel() {
      el('basket-title').textContent = 'Bought with: ' + short(name(select.value), 44);
    }
    select.addEventListener('change', () => { relabel(); card.update(); });
    relabel();
    el('basket-note').textContent = 'Confidence: share of orders containing the selected product that also contain the other. Lift: how many times ' +
      'more often the two are ordered together than if they were bought independently.';

    Viz.renderTable(el('pairs-table'), {
      columns: ['Product A', 'Product B', 'Orders together', 'Confidence (A → B)', 'Lift'],
      rows: B.top_rules.map((r) => [short(name(r.antecedent), 34), short(name(r.consequent), 34), fmt.int(r.together), fmt.pct(r.confidence, 0), times(r.lift)]),
    });
    el('pairs-table').querySelectorAll('tbody td:nth-child(-n+2)').forEach((td) => td.classList.add('wrap-cell'));

    const r0 = B.top_rules[0];
    insights('insights-basket', [
      ['Matching sets sell together', fmt.pct(r0.confidence, 0) + ' of orders with ' + name(r0.antecedent) + ' also include ' +
        name(r0.consequent) + ': ' + times(r0.lift) + ' more often than chance.'],
      ['Colourways go in pairs', 'Most of the strongest rules pair a product with its twin in another colour or design, such as pink and blue polka-dot cups. ' +
        'Show the other colourway on the product page and in the basket.'],
      ['Room to cross-sell', 'With ' + fmt.int(B.sizes.median_products) + ' products in the median order (mean ' + fmt.num(B.sizes.mean_products, 0) +
        '), buyers already build large mixed baskets; the rules give each product a ready-made "goes with" list.'],
    ]);
  }

  async function main() {
    Viz.initTheme(el('theme-toggle'));
    try {
      D = await Viz.loadJSON('data/dashboard.json');
    } catch (err) {
      el('meta-size').textContent = 'Could not load the data: ' + err.message;
      return;
    }
    hero();
    quality();
    trading();
    mix();
    cohortsSection();
    rfmSection();
    modelSection();
    basketSection();
  }

  main();
})();
