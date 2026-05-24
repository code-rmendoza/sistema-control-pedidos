import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./envioDetalle.css";

const money = new Intl.NumberFormat("es-VE", {
  style: "currency",
  currency: "USD",
});

function parseData() {
  const node = document.getElementById("envio-detalle-data");
  return node ? JSON.parse(node.textContent) : null;
}

function Metric({ label, value, tone = "neutral" }) {
  return (
    <article className={`shipment-metric shipment-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return parts.pop().split(";").shift();
  }
  return "";
}

function EnvioDetalle({ data }) {
  const [estado, setEstado] = useState(data.estado);
  const [estadoDisplay, setEstadoDisplay] = useState(data.estadoDisplay);
  const [savedEstado, setSavedEstado] = useState(data.estado);
  const [fechaSalidaDisplay, setFechaSalidaDisplay] = useState(data.fechaSalidaDisplay);
  const [fechaLlegadaDisplay, setFechaLlegadaDisplay] = useState(data.fechaLlegadaDisplay);
  const [ordenes, setOrdenes] = useState(data.ordenes);
  const [savingStatus, setSavingStatus] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const selectedEstado = useMemo(
    () => data.estados.find((item) => item.value === estado),
    [data.estados, estado],
  );
  const metrics = [
    { label: "Total vendido", value: money.format(Number(data.totalVendido)), tone: "income" },
    { label: "Costo productos", value: money.format(Number(data.costoProductos)), tone: "neutral" },
    { label: "Flete total", value: money.format(Number(data.costoFlete)), tone: "expense" },
    { label: "Utilidad neta", value: money.format(Number(data.utilidadNeta)), tone: "profit" },
  ];

  const saveEstado = async () => {
    setSavingStatus(true);
    setStatusMessage("");
    try {
      const response = await fetch(data.urls.cambiarEstado, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({ estado }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || "No se pudo actualizar el estado.");
      }
      setEstado(payload.estado);
      setSavedEstado(payload.estado);
      setEstadoDisplay(payload.estadoDisplay);
      setFechaSalidaDisplay(payload.fechaSalidaDisplay);
      setFechaLlegadaDisplay(payload.fechaLlegadaDisplay);
      setOrdenes(payload.ordenes);
      setStatusMessage(`Estado actualizado. Ordenes sincronizadas: ${payload.ordenesActualizadas}.`);
    } catch (error) {
      setStatusMessage(error.message);
    } finally {
      setSavingStatus(false);
    }
  };

  return (
    <div className="shipment-app">
      <header className="shipment-header">
        <div>
          <a className="shipment-back" href="/envios/">Envios</a>
          <h1>{data.nombre}</h1>
          <p>
            <span>{estadoDisplay}</span>
            <span>{data.courier || "Sin courier"}</span>
            <span>Salida: {fechaSalidaDisplay}</span>
            <span>Pago flete: {data.fechaPagoFleteDisplay}</span>
            <span>Utilidad: {data.periodoUtilidadDisplay}</span>
            <span>Llegada: {fechaLlegadaDisplay}</span>
          </p>
        </div>
        <div className="shipment-actions">
          <a className="shipment-action shipment-action--light" href={data.urls.editar}>Editar envio</a>
        </div>
      </header>

      <section className="shipment-status-panel" aria-label="Cambio rapido de estado">
        <div>
          <span>Estado actual</span>
          <strong>{selectedEstado ? selectedEstado.label : estadoDisplay}</strong>
        </div>
        <label>
          <span>Cambiar estado</span>
          <select value={estado} onChange={(event) => setEstado(event.target.value)}>
            {data.estados.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </label>
        <button type="button" onClick={saveEstado} disabled={savingStatus || estado === savedEstado}>
          {savingStatus ? "Guardando..." : "Actualizar estado"}
        </button>
        <p className={statusMessage.includes("actualizado") ? "shipment-status-ok" : "shipment-status-error"}>
          {statusMessage}
        </p>
      </section>

      <section className="shipment-metrics" aria-label="Resumen financiero">
        {metrics.map((metric) => (
          <Metric key={metric.label} {...metric} />
        ))}
      </section>

      <section className="shipment-panel">
        <div className="shipment-panel__head">
          <div>
            <h2>Ordenes incluidas</h2>
            <p>{ordenes.length} ordenes asociadas a este envio.</p>
          </div>
        </div>
        <div className="shipment-table-wrap">
          <table className="shipment-table">
            <thead>
              <tr>
                <th>Orden</th>
                <th>Cliente</th>
                <th>Total</th>
                <th>Ganancia bruta</th>
                <th>Flete asignado</th>
                <th>Utilidad neta</th>
              </tr>
            </thead>
            <tbody>
              {ordenes.map((orden) => (
                <tr key={orden.id}>
                  <td><a href={orden.url}>#{orden.id}</a></td>
                  <td>{orden.cliente}</td>
                  <td>{money.format(Number(orden.totalFinal))}</td>
                  <td>{money.format(Number(orden.utilidadRealNeta) + Number(orden.fleteAsignado))}</td>
                  <td>{money.format(Number(orden.fleteAsignado))}</td>
                  <td>{money.format(Number(orden.utilidadRealNeta))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

const data = parseData();
const root = document.getElementById("envio-detalle-root");

if (data && root) {
  createRoot(root).render(<EnvioDetalle data={data} />);
}
