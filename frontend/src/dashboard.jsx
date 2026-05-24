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

function percentTone(value) {
  if (value >= 30) {
    return "excellent";
  }
  if (value >= 20) {
    return "warning";
  }
  return "critical";
}

function MetricCard({ label, value, tone = "neutral", detail = "" }) {
  return (
    <article className={`react-metric react-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </article>
  );
}

function MiniStat({ label, value, tone = "neutral", detail = "" }) {
  return (
    <div className={`react-mini-stat react-mini-stat--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

function StatSection({ title, children }) {
  return (
    <section className="react-stat-section">
      <h2>{title}</h2>
      <div className="react-stat-grid">
        {children}
      </div>
    </section>
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
  const rentabilidad = Number(data.rentabilidadNeta);
  const rentabilidadLabel = `${rentabilidad.toFixed(2)}% sobre invertido`;
  const rentabilidadTone = percentTone(rentabilidad);
  const rentabilidadAnual = Number(data.rentabilidadNetaAnio);
  const rentabilidadAnualLabel = `${rentabilidadAnual.toFixed(2)}% sobre invertido`;
  const rentabilidadAnualTone = percentTone(rentabilidadAnual);

  return (
    <div className="react-dashboard">
      <header className="react-hero">
        <div>
          <p>Panel operativo</p>
          <h1>Dashboard</h1>
          <form className="react-month-filter" method="get">
            <label>
              <span>Mes historico</span>
              <input type="month" name="mes" defaultValue={data.mes} />
            </label>
            <button type="submit">Ver mes</button>
          </form>
        </div>
        <a className="react-primary-action" href={data.urls.nuevaOrden}>Nueva orden</a>
      </header>

      <section className="react-metrics react-metrics--featured" aria-label="Resumen principal">
        <MetricCard label="Saldo final" value={money.format(Number(data.saldoCaja))} tone={Number(data.saldoCaja) >= 0 ? "cash" : "expense"} detail="Caja acumulada al cierre del mes" />
        <MetricCard label="Utilidad neta mensual" value={money.format(Number(data.utilidadNeta))} tone={rentabilidadTone} detail={rentabilidadLabel} />
        <MetricCard label={`Utilidad neta ${data.anio}`} value={money.format(Number(data.utilidadNetaAnio))} tone={rentabilidadAnualTone} detail={rentabilidadAnualLabel} />
        <MetricCard label="Pendiente por cobrar" value={money.format(Number(data.pendienteCobrar))} tone="pending" />
      </section>

      <div className="react-stat-layout">
        <StatSection title="Operacion mensual">
          <MiniStat label="Ordenes" value={data.ordenesMes} tone="count" />
          <MiniStat label="Activas" value={data.pedidosActivos} tone="count" />
          <MiniStat label={`Vendido ${data.mesLabel}`} value={money.format(Number(data.vendidoMes))} tone="income" />
          <MiniStat label="Cobrado" value={money.format(Number(data.cobradoMes))} tone="income" />
        </StatSection>

        <StatSection title="Caja mensual">
          <MiniStat label="Saldo inicial" value={money.format(Number(data.saldoInicialCaja))} tone={Number(data.saldoInicialCaja) >= 0 ? "cash" : "expense"} />
          <MiniStat label="Ingresos" value={money.format(Number(data.cobradoMes))} tone="income" />
          <MiniStat label="Egresos" value={money.format(Number(data.egresosMes))} tone="expense" />
          <MiniStat label="Diferencia" value={money.format(Number(data.movimientoCaja))} tone={Number(data.movimientoCaja) >= 0 ? "cash" : "expense"} />
        </StatSection>

        <StatSection title="Rentabilidad mensual">
          <MiniStat label="Invertido productos" value={money.format(Number(data.inversionProductos))} />
          <MiniStat label="Fletes" value={money.format(Number(data.fletesAsignados))} tone="expense" />
          <MiniStat label="Invertido total" value={money.format(Number(data.inversionTotal))} />
          <MiniStat label="Ganancia real" value={money.format(Number(data.gananciaReal))} tone="profit" />
        </StatSection>

        <StatSection title={`Rentabilidad anual ${data.anio}`}>
          <MiniStat label="Vendido" value={money.format(Number(data.vendidoAnio))} tone="income" />
          <MiniStat label="Invertido total" value={money.format(Number(data.inversionAnio))} />
          <MiniStat label="Fletes" value={money.format(Number(data.fletesAnio))} tone="expense" />
          <MiniStat label="Ganancia real" value={money.format(Number(data.gananciaRealAnio))} tone="profit" />
        </StatSection>
      </div>

      <section className="react-panel">
        <div className="react-panel__header">
          <div>
            <h2>Ordenes del mes</h2>
            <p>Seguimiento de cobros, estado y saldo del periodo seleccionado.</p>
          </div>
          <a href={data.urls.ordenes}>Ver todas</a>
          <a href={data.urls.envios}>Envios</a>
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
                    <td><Status>{orden.estadoDisplay}</Status></td>
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
