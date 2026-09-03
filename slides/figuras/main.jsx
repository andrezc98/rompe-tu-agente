// The three generated deck figures drawn with Cloudscape (the AWS console's design system, dark
// mode) so they match the CloudWatch captures. All numbers come from data.json, written by
// `python -m evals.charts`; nothing is computed here. Pick a figure with ?fig=chaos|matrix|capas.
import React from "react";
import { createRoot } from "react-dom/client";
import "@cloudscape-design/global-styles/index.css";
import { applyMode, Mode } from "@cloudscape-design/global-styles";
import BarChart from "@cloudscape-design/components/bar-chart";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Container from "@cloudscape-design/components/container";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Box from "@cloudscape-design/components/box";
import data from "./data.json";

applyMode(Mode.Dark);

const pct = (y) => `${y}%`;

function Chaos() {
  const { effects, tools, n_per_effect } = data.chaos;
  const series = ["v1", "v2"].map((v) => ({
    title: `prompt ${v}`,
    type: "bar",
    data: effects.map((e) => ({ x: e.label, y: Math.round(100 * (data.chaos[v][e.key] ?? 0)) })),
    valueFormatter: pct,
  }));
  const legend = Object.entries(tools).map(([k, t]) => `${effects.find((e) => e.key === k).label}: ${t}`).join(" · ");
  return (
    <Container header={<Header variant="h2" description={`corridas aprobadas por los cuatro evaluadores · n=${n_per_effect} por condición y versión · ${legend}`}>Chaos testing: prompt v1 contra v2</Header>}>
      <BarChart
        series={series}
        xDomain={effects.map((e) => e.label)}
        yDomain={[0, 100]}
        xScaleType="categorical"
        height={300}
        hideFilter
        xTitle="falla inyectada"
        yTitle="corridas aprobadas"
        i18nStrings={{ yTickFormatter: pct }}
        ariaLabel="chaos v1 contra v2"
      />
    </Container>
  );
}

function Cell({ c }) {
  if (!c) return <StatusIndicator type="pending">sin datos</StatusIndicator>;
  if (c.refused) return <StatusIndicator type="stopped">atacante rechazado</StatusIndicator>;
  const breach = c.layer === "ninguna";
  return (
    <span>
      <Box variant="strong" display="inline">{c.score.toFixed(2)}</Box>
      {"  "}
      <StatusIndicator type={breach ? "error" : "success"}>{breach ? "ninguna capa" : `capa: ${c.layer}`}</StatusIndicator>
    </span>
  );
}

function Matrix() {
  const { strategies, rows, breach_threshold } = data.matrix;
  const columns = [
    { id: "cat", header: "categoría de riesgo", cell: (r) => <Box variant="strong">{r.category}</Box>, isRowHeader: true },
    ...strategies.map((s, j) => ({ id: s, header: s, cell: (r) => <Cell c={r.cells[j]} /> })),
  ];
  return (
    <Table
      variant="container"
      columnDefinitions={columns}
      items={rows}
      header={<Header variant="h2" description={`peor score por categoría y estrategia, promedio de dos pasadas · ninguna capa = score ≥ ${breach_threshold}`}>Red team: qué capa te salvó</Header>}
    />
  );
}

function Capas() {
  const columns = [
    { id: "cat", header: "categoría", cell: (r) => <Box variant="strong">{r[0]}</Box>, isRowHeader: true },
    { id: "want", header: "qué quiere el atacante", cell: (r) => r[1] },
    { id: "layers", header: "capas que pueden detenerlo", cell: (r) => r[2] },
  ];
  return (
    <Table
      variant="container"
      columnDefinitions={columns}
      items={data.layers}
      header={<Header variant="h2" description="cada categoría prueba una capa distinta; las dos últimas no tienen segunda capa">Cuatro categorías, tres capas</Header>}
    />
  );
}

const FIGURES = { chaos: Chaos, matrix: Matrix, capas: Capas };
const Fig = FIGURES[new URLSearchParams(location.search).get("fig")] ?? Chaos;
createRoot(document.getElementById("root")).render(<Fig />);
