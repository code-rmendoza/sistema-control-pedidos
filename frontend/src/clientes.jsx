import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./clientes.css";

const money = new Intl.NumberFormat("es-VE", {
  style: "currency",
  currency: "USD",
});

function parseData() {
  const node = document.getElementById("clientes-data");
  if (!node) {
    return null;
  }
  return JSON.parse(node.textContent);
}

function Metric({ label, value, tone = "neutral" }) {
  return (
    <article className={`clients-metric clients-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function BalanceBadge({ value }) {
  const amount = Number(value);
  return (
    <span className={`clients-balance ${amount > 0 ? "clients-balance--pending" : "clients-balance--paid"}`}>
      {money.format(amount)}
    </span>
  );
}

function Clientes({ data }) {
  const [search, setSearch] = useState(data.q || "");
  const [scope, setScope] = useState("todos");

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return data.clientes.filter((cliente) => {
      const haystack = `${cliente.nombre} ${cliente.telefono} ${cliente.notas}`.toLowerCase();
      const matchesSearch = !term || haystack.includes(term);
      const saldo = Number(cliente.saldoPendiente);
      const matchesScope =
        scope === "todos" ||
        (scope === "con_saldo" && saldo > 0) ||
        (scope === "sin_ordenes" && cliente.ordenesCount === 0);
      return matchesSearch && matchesScope;
    });
  }, [data.clientes, scope, search]);

  const summary = useMemo(() => {
    return filtered.reduce(
      (acc, cliente) => {
        acc.ordenes += cliente.ordenesCount;
        acc.total += Number(cliente.totalVendido);
        acc.saldo += Number(cliente.saldoPendiente);
        if (Number(cliente.saldoPendiente) > 0) {
          acc.conSaldo += 1;
        }
        return acc;
      },
      { ordenes: 0, total: 0, saldo: 0, conSaldo: 0 },
    );
  }, [filtered]);

  return (
    <div className="clients-app">
      <header className="clients-header">
        <div>
          <p>Base comercial</p>
          <h1>Clientes</h1>
        </div>
        <a className="clients-action" href={data.urls.nuevoCliente}>Nuevo cliente</a>
      </header>

      <section className="clients-toolbar" aria-label="Filtros de clientes">
        <label>
          <span>Buscar</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Nombre, telefono o notas"
          />
        </label>
        <label>
          <span>Vista</span>
          <select value={scope} onChange={(event) => setScope(event.target.value)}>
            <option value="todos">Todos</option>
            <option value="con_saldo">Con saldo</option>
            <option value="sin_ordenes">Sin ordenes</option>
          </select>
        </label>
      </section>

      <section className="clients-metrics" aria-label="Resumen de clientes">
        <Metric label="Clientes visibles" value={filtered.length} tone="count" />
        <Metric label="Ordenes" value={summary.ordenes} tone="orders" />
        <Metric label="Vendido" value={money.format(summary.total)} tone="income" />
        <Metric label="Saldo pendiente" value={money.format(summary.saldo)} tone="pending" />
      </section>

      <section className="clients-panel">
        <div className="clients-panel__head">
          <div>
            <h2>Listado de clientes</h2>
            <p>{summary.conSaldo} clientes visibles tienen saldo por cobrar.</p>
          </div>
        </div>

        <div className="clients-table-wrap">
          <table className="clients-table">
            <thead>
              <tr>
                <th>Cliente</th>
                <th>Telefono</th>
                <th>Ordenes</th>
                <th>Vendido</th>
                <th>Saldo</th>
                <th>Registro</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length ? (
                filtered.map((cliente) => (
                  <tr key={cliente.id}>
                    <td><a href={cliente.url}>{cliente.nombre}</a></td>
                    <td>{cliente.telefono || "-"}</td>
                    <td>{cliente.ordenesCount}</td>
                    <td>{money.format(Number(cliente.totalVendido))}</td>
                    <td><BalanceBadge value={cliente.saldoPendiente} /></td>
                    <td>{cliente.creadoDisplay}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6">No hay clientes que coincidan con los filtros.</td>
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
const root = document.getElementById("clientes-root");

if (data && root) {
  createRoot(root).render(<Clientes data={data} />);
}
