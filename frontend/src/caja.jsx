import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./caja.css";

const money = new Intl.NumberFormat("es-VE", {
  style: "currency",
  currency: "USD",
});

function parseData() {
  const node = document.getElementById("caja-data");
  if (!node) {
    return null;
  }
  return JSON.parse(node.textContent);
}

function Metric({ label, value, tone = "neutral" }) {
  return (
    <article className={`cash-metric cash-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function TypeBadge({ movimiento }) {
  return (
    <span className={`cash-badge cash-badge--${movimiento.tipo}`}>
      {movimiento.tipoDisplay}
    </span>
  );
}

function Caja({ data }) {
  const [search, setSearch] = useState("");
  const [tipo, setTipo] = useState("todos");
  const [fechaDesde, setFechaDesde] = useState(data.fechaDesde || "");
  const [fechaHasta, setFechaHasta] = useState(data.fechaHasta || "");

  const categorias = useMemo(() => {
    const seen = new Map();
    data.movimientos.forEach((movimiento) => {
      seen.set(movimiento.categoria, movimiento.categoriaDisplay);
    });
    return Array.from(seen, ([value, label]) => ({ value, label }));
  }, [data.movimientos]);

  const [categoria, setCategoria] = useState("todas");

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return data.movimientos.filter((movimiento) => {
      const matchesTipo = tipo === "todos" || movimiento.tipo === tipo;
      const matchesCategoria = categoria === "todas" || movimiento.categoria === categoria;
      const matchesDesde = !fechaDesde || movimiento.fecha >= fechaDesde;
      const matchesHasta = !fechaHasta || movimiento.fecha <= fechaHasta;
      const haystack = `${movimiento.descripcion} ${movimiento.categoriaDisplay} ${movimiento.tipoDisplay}`.toLowerCase();
      const matchesSearch = !term || haystack.includes(term);
      return matchesTipo && matchesCategoria && matchesDesde && matchesHasta && matchesSearch;
    }).sort((a, b) => `${a.fecha}-${a.id}`.localeCompare(`${b.fecha}-${b.id}`));
  }, [categoria, data.movimientos, fechaDesde, fechaHasta, search, tipo]);

  const filteredSummary = useMemo(() => {
    const period = data.movimientos.filter((movimiento) => {
      const matchesDesde = !fechaDesde || movimiento.fecha >= fechaDesde;
      const matchesHasta = !fechaHasta || movimiento.fecha <= fechaHasta;
      return matchesDesde && matchesHasta;
    });
    const previous = fechaDesde
      ? data.movimientos.filter((movimiento) => movimiento.fecha < fechaDesde)
      : [];
    const summarize = (items) => items.reduce(
      (acc, movimiento) => {
        const monto = Number(movimiento.monto);
        if (movimiento.tipo === "ingreso") {
          acc.ingresos += monto;
        } else {
          acc.egresos += monto;
        }
        return acc;
      },
      { ingresos: 0, egresos: 0 },
    );
    const visible = summarize(filtered);
    const periodSummary = summarize(period);
    const previousSummary = summarize(previous);
    const saldoInicial = previousSummary.ingresos - previousSummary.egresos;
    const movimientoPeriodo = periodSummary.ingresos - periodSummary.egresos;
    return {
      ...visible,
      saldoInicial,
      movimientoPeriodo,
      saldoFinal: saldoInicial + movimientoPeriodo,
    };
  }, [data.movimientos, fechaDesde, fechaHasta, filtered]);

  const ledgerRows = useMemo(() => {
    let runningBalance = filteredSummary.saldoInicial;
    return filtered.map((movimiento) => {
      const monto = Number(movimiento.monto);
      runningBalance += movimiento.tipo === "ingreso" ? monto : -monto;
      return {
        ...movimiento,
        saldoAcumulado: runningBalance,
      };
    });
  }, [filtered, filteredSummary.saldoInicial]);

  return (
    <div className="cash-app">
      <header className="cash-header">
        <div>
          <p>Control financiero</p>
          <h1>Caja</h1>
        </div>
      </header>

      <section className="cash-metrics" aria-label="Resumen de caja">
        <Metric label="Saldo inicial" value={money.format(filteredSummary.saldoInicial)} tone={filteredSummary.saldoInicial >= 0 ? "cash" : "expense"} />
        <Metric label="Ingresos periodo" value={money.format(filteredSummary.ingresos)} tone="income" />
        <Metric label="Egresos periodo" value={money.format(filteredSummary.egresos)} tone="expense" />
        <Metric label="Diferencia periodo" value={money.format(filteredSummary.movimientoPeriodo)} tone={filteredSummary.movimientoPeriodo >= 0 ? "cash" : "expense"} />
        <Metric label="Saldo final" value={money.format(filteredSummary.saldoFinal)} tone={filteredSummary.saldoFinal >= 0 ? "cash" : "expense"} />
        <Metric label="Movimientos visibles" value={filtered.length} tone="count" />
      </section>

      <section className="cash-toolbar" aria-label="Filtros de caja">
        <label>
          <span>Buscar</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Descripcion, categoria o tipo"
          />
        </label>
        <label>
          <span>Tipo</span>
          <select value={tipo} onChange={(event) => setTipo(event.target.value)}>
            <option value="todos">Todos</option>
            {data.tipos.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Categoria</span>
          <select value={categoria} onChange={(event) => setCategoria(event.target.value)}>
            <option value="todas">Todas</option>
            {categorias.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Desde</span>
          <input type="date" value={fechaDesde} onChange={(event) => setFechaDesde(event.target.value)} />
        </label>
        <label>
          <span>Hasta</span>
          <input type="date" value={fechaHasta} onChange={(event) => setFechaHasta(event.target.value)} />
        </label>
      </section>

      <section className="cash-panel">
        <div className="cash-panel__head">
          <div>
            <h2>Movimientos</h2>
            <p>
              Filtrado: {money.format(filteredSummary.ingresos)} en ingresos y {money.format(filteredSummary.egresos)} en egresos.
            </p>
          </div>
        </div>

        <div className="cash-table-wrap">
          <table className="cash-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Tipo</th>
                <th>Categoria</th>
                <th>Descripcion</th>
                <th>Origen</th>
                <th>Monto</th>
                <th>Saldo</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {ledgerRows.length ? (
                ledgerRows.map((movimiento) => (
                  <tr key={movimiento.id}>
                    <td>{movimiento.fechaDisplay}</td>
                    <td><TypeBadge movimiento={movimiento} /></td>
                    <td>{movimiento.categoriaDisplay}</td>
                    <td>{movimiento.descripcion}</td>
                    <td>{movimiento.origen}</td>
                    <td className={`cash-amount cash-amount--${movimiento.tipo}`}>
                      {movimiento.tipo === "egreso" ? "-" : "+"}{money.format(Number(movimiento.monto))}
                    </td>
                    <td className={`cash-running ${movimiento.saldoAcumulado >= 0 ? "cash-running--ok" : "cash-running--low"}`}>
                      {money.format(movimiento.saldoAcumulado)}
                    </td>
                    <td>
                      {!movimiento.editable ? (
                        <span className="cash-locked">{movimiento.esEnvio ? "Desde envio" : "Desde orden"}</span>
                      ) : (
                        <div className="cash-actions">
                          <a href={movimiento.urls.editar}>Editar</a>
                          <form
                            method="post"
                            action={movimiento.urls.eliminar}
                            onSubmit={(event) => {
                              if (!window.confirm("Eliminar este movimiento de caja?")) {
                                event.preventDefault();
                              }
                            }}
                          >
                            <input type="hidden" name="csrfmiddlewaretoken" value={data.csrfToken} />
                            <button type="submit">Eliminar</button>
                          </form>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="8">Sin movimientos que coincidan con los filtros.</td>
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
const root = document.getElementById("caja-root");

if (data && root) {
  createRoot(root).render(<Caja data={data} />);
}
