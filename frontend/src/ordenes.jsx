import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./ordenes.css";

const money = new Intl.NumberFormat("es-VE", {
  style: "currency",
  currency: "USD",
});

function parseData() {
  const node = document.getElementById("ordenes-data");
  if (!node) {
    return null;
  }
  return JSON.parse(node.textContent);
}

function Metric({ label, value, tone = "neutral" }) {
  return (
    <article className={`orders-metric orders-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function EstadoBadge({ children }) {
  return <span className="orders-status">{children}</span>;
}

function SaldoBadge({ paid, value }) {
  return (
    <span className={`orders-balance ${paid ? "orders-balance--paid" : "orders-balance--pending"}`}>
      {money.format(Number(value))}
    </span>
  );
}

function Ordenes({ data }) {
  const [search, setSearch] = useState(data.q || "");
  const [estado, setEstado] = useState("todos");

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return data.ordenes.filter((orden) => {
      const matchesEstado = estado === "todos" || orden.estado === estado;
      const haystack = `${orden.id} ${orden.cliente} ${orden.estadoDisplay}`.toLowerCase();
      const matchesSearch = !term || haystack.includes(term);
      return matchesEstado && matchesSearch;
    });
  }, [data.ordenes, estado, search]);

  const summary = useMemo(() => {
    return filtered.reduce(
      (acc, orden) => {
        acc.total += Number(orden.totalFinal);
        acc.pagado += Number(orden.totalPagado);
        acc.saldo += Number(orden.saldoPendiente);
        if (!orden.pagadoCompleto) {
          acc.pendientes += 1;
        }
        return acc;
      },
      { total: 0, pagado: 0, saldo: 0, pendientes: 0 },
    );
  }, [filtered]);

  return (
    <div className="orders-app">
      <header className="orders-header">
        <div>
          <p>Gestion comercial</p>
          <h1>Ordenes</h1>
        </div>
        <a className="orders-action" href={data.urls.nuevaOrden}>Nueva orden</a>
      </header>

      <section className="orders-toolbar" aria-label="Filtros de ordenes">
        <label>
          <span>Buscar</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Cliente, numero u estado"
          />
        </label>
        <label>
          <span>Estado</span>
          <select value={estado} onChange={(event) => setEstado(event.target.value)}>
            <option value="todos">Todos</option>
            {data.estados.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </label>
      </section>

      <section className="orders-metrics" aria-label="Resumen de ordenes filtradas">
        <Metric label="Ordenes visibles" value={filtered.length} tone="count" />
        <Metric label="Total vendido" value={money.format(summary.total)} tone="income" />
        <Metric label="Pagado" value={money.format(summary.pagado)} tone="cash" />
        <Metric label="Saldo pendiente" value={money.format(summary.saldo)} tone="pending" />
      </section>

      <section className="orders-panel">
        <div className="orders-panel__head">
          <div>
            <h2>Listado operativo</h2>
            <p>{summary.pendientes} ordenes con saldo por cobrar.</p>
          </div>
        </div>

        <div className="orders-table-wrap">
          <table className="orders-table">
            <thead>
              <tr>
                <th>Orden</th>
                <th>Cliente</th>
                <th>Fecha</th>
                <th>Estado</th>
                <th>Items</th>
                <th>Total</th>
                <th>Pagado</th>
                <th>Saldo</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length ? (
                filtered.map((orden) => (
                  <tr key={orden.id}>
                    <td><a href={orden.url}>#{orden.id}</a></td>
                    <td>{orden.cliente}</td>
                    <td>{orden.fechaDisplay}</td>
                    <td><EstadoBadge>{orden.estadoDisplay}</EstadoBadge></td>
                    <td>{orden.itemsCount}</td>
                    <td>{money.format(Number(orden.totalFinal))}</td>
                    <td>{money.format(Number(orden.totalPagado))}</td>
                    <td><SaldoBadge paid={orden.pagadoCompleto} value={orden.saldoPendiente} /></td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="8">No hay ordenes que coincidan con los filtros.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

const data = parseData();
const root = document.getElementById("ordenes-root");

if (data && root) {
  createRoot(root).render(<Ordenes data={data} />);
}
