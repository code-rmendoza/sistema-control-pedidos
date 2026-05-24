import React from "react";
import { createRoot } from "react-dom/client";
import "./envios.css";

const money = new Intl.NumberFormat("es-VE", {
  style: "currency",
  currency: "USD",
});

function parseData() {
  const node = document.getElementById("envios-data");
  return node ? JSON.parse(node.textContent) : null;
}

function Metric({ label, value, tone = "neutral" }) {
  return (
    <article className={`ship-metric ship-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function Envios({ data }) {
  const totalFlete = data.envios.reduce((acc, envio) => acc + Number(envio.costoFlete), 0);
  const utilidadNeta = data.envios.reduce((acc, envio) => acc + Number(envio.utilidadNeta), 0);
  const ordenesEnviadas = data.envios.reduce((acc, envio) => acc + envio.ordenesCount, 0);

  return (
    <div className="ship-app">
      <header className="ship-header">
        <div>
          <p>Logistica</p>
          <h1>Envios</h1>
        </div>
        <a className="ship-action" href={data.urls.nuevoEnvio}>Nuevo envio</a>
      </header>

      <section className="ship-metrics" aria-label="Resumen de envios">
        <Metric label="Envios" value={data.envios.length} tone="count" />
        <Metric label="Ordenes enviadas" value={ordenesEnviadas} tone="count" />
        <Metric label="Fletes registrados" value={money.format(totalFlete)} tone="expense" />
        <Metric label="Utilidad neta" value={money.format(utilidadNeta)} tone="profit" />
      </section>

      <section className="ship-panel">
        <div className="ship-panel__head">
          <div>
            <h2>Envios registrados</h2>
            <p>{data.ordenesDisponibles.length} ordenes compradas listas para agrupar.</p>
          </div>
        </div>
        <div className="ship-table-wrap">
          <table className="ship-table">
            <thead>
              <tr>
                <th>Envio</th>
                <th>Estado</th>
                <th>Courier</th>
                <th>Periodo utilidad</th>
                <th>Ordenes</th>
                <th>Flete</th>
                <th>Utilidad neta</th>
              </tr>
            </thead>
            <tbody>
              {data.envios.length ? (
                data.envios.map((envio) => (
                  <tr key={envio.id}>
                    <td><a href={envio.url}>{envio.nombre}</a></td>
                    <td><span className="ship-status">{envio.estadoDisplay}</span></td>
                    <td>{envio.courier || "-"}</td>
                    <td>{envio.periodoUtilidadDisplay}</td>
                    <td>{envio.ordenesCount}</td>
                    <td>{money.format(Number(envio.costoFlete))}</td>
                    <td>{money.format(Number(envio.utilidadNeta))}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7">Todavia no hay envios registrados.</td>
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
const root = document.getElementById("envios-root");

if (data && root) {
  createRoot(root).render(<Envios data={data} />);
}
