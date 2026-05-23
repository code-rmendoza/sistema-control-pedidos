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
      const haystack = `${movimiento.descripcion} ${movimiento.categoriaDisplay} ${movimiento.tipoDisplay}`.toLowerCase();
      const matchesSearch = !term || haystack.includes(term);
      return matchesTipo && matchesCategoria && matchesSearch;
    });
  }, [categoria, data.movimientos, search, tipo]);

  const filteredSummary = useMemo(() => {
    return filtered.reduce(
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
  }, [filtered]);

  return (
    <div className="cash-app">
      <header className="cash-header">
        <div>
          <p>Control financiero</p>
          <h1>Caja</h1>
        </div>
      </header>

      <section className="cash-metrics" aria-label="Resumen de caja">
        <Metric label="Ingresos" value={money.format(Number(data.ingresos))} tone="income" />
        <Metric label="Egresos" value={money.format(Number(data.egresos))} tone="expense" />
        <Metric label="Saldo" value={money.format(Number(data.saldo))} tone={Number(data.saldo) >= 0 ? "cash" : "expense"} />
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
              </tr>
            </thead>
            <tbody>
              {filtered.length ? (
                filtered.map((movimiento) => (
                  <tr key={movimiento.id}>
                    <td>{movimiento.fechaDisplay}</td>
                    <td><TypeBadge movimiento={movimiento} /></td>
                    <td>{movimiento.categoriaDisplay}</td>
                    <td>{movimiento.descripcion}</td>
                    <td>{movimiento.esPago ? "Pago de orden" : "Manual"}</td>
                    <td className={`cash-amount cash-amount--${movimiento.tipo}`}>
                      {movimiento.tipo === "egreso" ? "-" : "+"}{money.format(Number(movimiento.monto))}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6">Sin movimientos que coincidan con los filtros.</td>
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
