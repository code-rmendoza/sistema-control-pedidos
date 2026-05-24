import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./ordenDetalle.css";

const money = new Intl.NumberFormat("es-VE", {
  style: "currency",
  currency: "USD",
});

function parseData() {
  const node = document.getElementById("orden-detalle-data");
  if (!node) {
    return null;
  }
  return JSON.parse(node.textContent);
}

function Metric({ label, value, tone = "neutral" }) {
  return (
    <article className={`detail-metric detail-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function Money({ value }) {
  if (value === "") {
    return "-";
  }
  return money.format(Number(value));
}

function ReferenceList({ referencias }) {
  const entries = Object.entries(referencias).filter(([, value]) => value);
  if (!entries.length) {
    return <span className="detail-muted">Sin refs.</span>;
  }
  return (
    <div className="detail-refs">
      {entries.map(([label, value]) => (
        <span key={label}>{label}: {money.format(Number(value))}</span>
      ))}
    </div>
  );
}

function ProductImage({ item }) {
  if (!item.imagen) {
    return <div className="detail-product-image detail-product-image--empty">Sin imagen</div>;
  }
  return <img className="detail-product-image" src={item.imagen} alt={item.descripcion} />;
}

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return parts.pop().split(";").shift();
  }
  return "";
}

function OrdenDetalle({ data }) {
  const [estado, setEstado] = useState(data.estado);
  const [estadoDisplay, setEstadoDisplay] = useState(data.estadoDisplay);
  const [savedEstado, setSavedEstado] = useState(data.estado);
  const [savingStatus, setSavingStatus] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const selectedEstado = useMemo(
    () => data.estados.find((item) => item.value === estado),
    [data.estados, estado],
  );
  const saldoTone = data.pagadoCompleto ? "paid" : "pending";
  const metrics = [
    { label: "Total", value: money.format(Number(data.totalFinal)), tone: "income" },
    { label: "Inicial sugerida", value: money.format(Number(data.inicialSugerida)), tone: "neutral" },
    { label: "Pagado", value: money.format(Number(data.totalPagado)), tone: "cash" },
    { label: "Saldo", value: money.format(Number(data.saldoPendiente)), tone: saldoTone },
    { label: "Ganancia estimada", value: money.format(Number(data.gananciaEstimada)), tone: "profit" },
    { label: "Ganancia real", value: money.format(Number(data.gananciaReal)), tone: "profit" },
    { label: "Flete asignado", value: money.format(Number(data.fleteAsignado)), tone: "pending" },
    { label: "Utilidad neta", value: money.format(Number(data.utilidadRealNeta)), tone: "profit" },
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
      setStatusMessage("Estado actualizado.");
    } catch (error) {
      setStatusMessage(error.message);
    } finally {
      setSavingStatus(false);
    }
  };

  return (
    <div className="detail-app">
      <header className="detail-header">
        <div>
          <a className="detail-back" href={data.urls.ordenes}>Ordenes</a>
          <h1>Orden #{data.id}</h1>
          <p>
            <a href={data.clienteUrl}>{data.cliente}</a>
            <span>{estadoDisplay}</span>
            <span>{data.fechaDisplay}</span>
            {data.envio ? <a href={data.envio.url}>{data.envio.nombre}</a> : null}
          </p>
        </div>
        <div className="detail-actions">
          <a className="detail-action detail-action--light" href={data.urls.editar}>Editar</a>
          <a className="detail-action" href={data.urls.pdf}>Reporte PDF</a>
        </div>
      </header>

      <section className="detail-status-panel" aria-label="Cambio rapido de estado">
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
        <p className={statusMessage.includes("actualizado") ? "detail-status-ok" : "detail-status-error"}>
          {statusMessage}
        </p>
      </section>

      <section className="detail-metrics" aria-label="Resumen financiero">
        {metrics.map((metric) => (
          <Metric key={metric.label} {...metric} />
        ))}
      </section>

      <section className="detail-panel">
        <div className="detail-panel__head">
          <div>
            <h2>Productos</h2>
            <p>{data.items.length} productos en esta orden.</p>
          </div>
        </div>
        <div className="detail-products">
          {data.items.length ? (
            data.items.map((item) => (
              <article className="detail-product" key={item.id}>
                <ProductImage item={item} />
                <div className="detail-product-main">
                  <h3>{item.descripcion}</h3>
                  <p>{item.tienda} / {item.proveedorVersion}</p>
                  <div className="detail-product-meta">
                    <span>SKU: {item.sku || "-"}</span>
                    {item.link ? <a href={item.link} target="_blank" rel="noreferrer">Ver producto</a> : null}
                  </div>
                  <ReferenceList referencias={item.referencias} />
                  <div className="detail-product-actions">
                    <a href={item.urls.editar}>Editar</a>
                    <form
                      method="post"
                      action={item.urls.eliminar}
                      onSubmit={(event) => {
                        if (!window.confirm("Eliminar este producto de la orden?")) {
                          event.preventDefault();
                        }
                      }}
                    >
                      <input type="hidden" name="csrfmiddlewaretoken" value={data.csrfToken} />
                      <button type="submit">Eliminar</button>
                    </form>
                  </div>
                </div>
                <div className="detail-product-money">
                  <span>Costo est. <strong><Money value={item.costoEstimado} /></strong></span>
                  <span>Costo real <strong><Money value={item.costoReal} /></strong></span>
                  <span>Final <strong><Money value={item.precioFinal} /></strong></span>
                  <span>Rent. <strong>{item.rentabilidadReal ? `${item.rentabilidadReal}%` : "-"}</strong></span>
                </div>
              </article>
            ))
          ) : (
            <div className="detail-empty">Agrega al menos un producto.</div>
          )}
        </div>
      </section>

      <section className="detail-panel">
        <div className="detail-panel__head">
          <div>
            <h2>Pagos</h2>
            <p>{data.pagos.length} pagos registrados.</p>
          </div>
        </div>
        <div className="detail-table-wrap">
          <table className="detail-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Monto</th>
                <th>Metodo</th>
                <th>Nota</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {data.pagos.length ? (
                data.pagos.map((pago) => (
                  <tr key={pago.id}>
                    <td>{pago.fechaDisplay}</td>
                    <td>{money.format(Number(pago.monto))}</td>
                    <td>{pago.metodo || "-"}</td>
                    <td>{pago.nota || "-"}</td>
                    <td>
                      <div className="detail-payment-actions">
                        <a href={pago.urls.editar}>Editar</a>
                        <form
                          method="post"
                          action={pago.urls.eliminar}
                          onSubmit={(event) => {
                            if (!window.confirm("Eliminar este pago tambien eliminara su ingreso de caja. Continuar?")) {
                              event.preventDefault();
                            }
                          }}
                        >
                          <input type="hidden" name="csrfmiddlewaretoken" value={data.csrfToken} />
                          <button type="submit">Eliminar</button>
                        </form>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="5">Sin pagos registrados.</td>
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
const root = document.getElementById("orden-detalle-root");

if (data && root) {
  createRoot(root).render(<OrdenDetalle data={data} />);
}
