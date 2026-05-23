import React from "react";
import { createRoot } from "react-dom/client";
import "./dashboard.css";

const money = new Intl.NumberFormat("es-VE", {
  style: "currency",
  currency: "USD",
});

function parseData() {
  const node = document.getElementById("dashboard-data");
  if (!node) {
    return null;
  }
  return JSON.parse(node.textContent);
}

function MetricCard({ label, value, tone = "neutral" }) {
  return (
    <article className={`react-metric react-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function Status({ children }) {
  return <span className="react-status">{children}</span>;
}

function PaymentStatus({ paid, amount }) {
  return (
    <span className={`react-payment ${paid ? "react-payment--paid" : "react-payment--pending"}`}>
      {money.format(Number(amount))}
    </span>
  );
}

function Dashboard({ data }) {
  const metrics = [
    { label: "Pedidos activos", value: data.pedidosActivos, tone: "count" },
    { label: "Cobrado del mes", value: money.format(Number(data.cobradoMes)), tone: "income" },
    { label: "Pendiente por cobrar", value: money.format(Number(data.pendienteCobrar)), tone: "pending" },
    { label: "Saldo de caja", value: money.format(Number(data.saldoCaja)), tone: "cash" },
    { label: "Egresos del mes", value: money.format(Number(data.egresosMes)), tone: "expense" },
    { label: "Ganancia estimada", value: money.format(Number(data.gananciaEstimada)), tone: "profit" },
    { label: "Ganancia real", value: money.format(Number(data.gananciaReal)), tone: "profit" },
  ];

  return (
    <div className="react-dashboard">
      <header className="react-hero">
        <div>
          <p>Panel operativo</p>
          <h1>Dashboard</h1>
        </div>
        <a className="react-primary-action" href={data.urls.nuevaOrden}>Nueva orden</a>
      </header>

      <section className="react-metrics" aria-label="Metricas principales">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </section>

      <section className="react-panel">
        <div className="react-panel__header">
          <div>
            <h2>Ordenes recientes</h2>
            <p>Seguimiento rapido de cobros, estado y saldo pendiente.</p>
          </div>
          <a href={data.urls.ordenes}>Ver todas</a>
        </div>

        <div className="react-table-wrap">
          <table className="react-table">
            <thead>
              <tr>
                <th>Orden</th>
                <th>Cliente</th>
                <th>Estado</th>
                <th>Total</th>
                <th>Pagado</th>
                <th>Saldo</th>
              </tr>
            </thead>
            <tbody>
              {data.ordenes.length ? (
                data.ordenes.map((orden) => (
                  <tr key={orden.id}>
                    <td><a href={orden.url}>#{orden.id}</a></td>
                    <td>{orden.cliente}</td>
                    <td><Status>{orden.estado}</Status></td>
                    <td>{money.format(Number(orden.totalFinal))}</td>
                    <td>{money.format(Number(orden.totalPagado))}</td>
                    <td><PaymentStatus paid={orden.pagadoCompleto} amount={orden.saldoPendiente} /></td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6">Todavia no hay ordenes.</td>
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
const root = document.getElementById("dashboard-root");

if (data && root) {
  createRoot(root).render(<Dashboard data={data} />);
}
