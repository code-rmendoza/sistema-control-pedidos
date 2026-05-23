import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./clienteDetalle.css";

const money = new Intl.NumberFormat("es-VE", {
  style: "currency",
  currency: "USD",
});

function parseData() {
  const node = document.getElementById("cliente-detalle-data");
  if (!node) {
    return null;
  }
  return JSON.parse(node.textContent);
}

function Metric({ label, value, tone = "neutral" }) {
  return (
    <article className={`client-detail-metric client-detail-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function BalanceBadge({ paid, value }) {
  return (
    <span className={`client-detail-balance ${paid ? "client-detail-balance--paid" : "client-detail-balance--pending"}`}>
      {money.format(Number(value))}
    </span>
  );
}

function ClienteDetalle({ data }) {
  const [scope, setScope] = useState("todas");

  const ordenes = useMemo(() => {
    return data.ordenes.filter((orden) => {
      if (scope === "pagadas") {
        return orden.pagadoCompleto;
      }
      if (scope === "pendientes") {
        return !orden.pagadoCompleto;
      }
      return true;
    });
  }, [data.ordenes, scope]);

  const visibleSummary = useMemo(() => {
    return ordenes.reduce(
      (acc, orden) => {
        acc.total += Number(orden.totalFinal);
        acc.pagado += Number(orden.totalPagado);
        acc.saldo += Number(orden.saldoPendiente);
        return acc;
      },
      { total: 0, pagado: 0, saldo: 0 },
    );
  }, [ordenes]);

  return (
    <div className="client-detail-app">
      <header className="client-detail-header">
        <div>
          <a className="client-detail-back" href={data.urls.clientes}>Clientes</a>
          <h1>{data.nombre}</h1>
          <p>{data.telefono || "Sin telefono"} · Registro {data.creadoDisplay}</p>
        </div>
        <a className="client-detail-action" href={data.urls.nuevaOrden}>Nueva orden</a>
      </header>

      <section className="client-detail-metrics" aria-label="Resumen del cliente">
        <Metric label="Ordenes" value={data.ordenesCount} tone="count" />
        <Metric label="Vendido" value={money.format(Number(data.totalVendido))} tone="income" />
        <Metric label="Pagado" value={money.format(Number(data.totalPagado))} tone="cash" />
        <Metric label="Saldo" value={money.format(Number(data.saldoPendiente))} tone={Number(data.saldoPendiente) > 0 ? "pending" : "paid"} />
      </section>

      {data.notas ? (
        <section className="client-detail-notes">
          <h2>Notas</h2>
          <p>{data.notas}</p>
        </section>
      ) : null}

      <section className="client-detail-toolbar" aria-label="Filtro de ordenes">
        <label>
          <span>Vista</span>
          <select value={scope} onChange={(event) => setScope(event.target.value)}>
            <option value="todas">Todas</option>
            <option value="pendientes">Con saldo</option>
            <option value="pagadas">Pagadas</option>
          </select>
        </label>
        <div className="client-detail-visible-summary">
          <span>Visible</span>
          <strong>{money.format(visibleSummary.total)} total · {money.format(visibleSummary.saldo)} saldo</strong>
        </div>
      </section>

      <section className="client-detail-panel">
        <div className="client-detail-panel__head">
          <div>
            <h2>Ordenes</h2>
            <p>{ordenes.length} ordenes en la vista actual.</p>
          </div>
        </div>

        <div className="client-detail-table-wrap">
          <table className="client-detail-table">
            <thead>
              <tr>
                <th>Orden</th>
                <th>Fecha</th>
                <th>Estado</th>
                <th>Items</th>
                <th>Total</th>
                <th>Pagado</th>
                <th>Saldo</th>
              </tr>
            </thead>
            <tbody>
              {ordenes.length ? (
                ordenes.map((orden) => (
                  <tr key={orden.id}>
                    <td><a href={orden.url}>#{orden.id}</a></td>
                    <td>{orden.fechaDisplay}</td>
                    <td><span className="client-detail-status">{orden.estadoDisplay}</span></td>
                    <td>{orden.itemsCount}</td>
                    <td>{money.format(Number(orden.totalFinal))}</td>
                    <td>{money.format(Number(orden.totalPagado))}</td>
                    <td><BalanceBadge paid={orden.pagadoCompleto} value={orden.saldoPendiente} /></td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7">Este cliente no tiene ordenes en esta vista.</td>
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
const root = document.getElementById("cliente-detalle-root");

if (data && root) {
  createRoot(root).render(<ClienteDetalle data={data} />);
}
