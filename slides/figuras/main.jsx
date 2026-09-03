// The generated deck figures drawn with Cloudscape (the AWS console's design system, dark mode)
// so they match the CloudWatch captures. All numbers and texts come from data.json, written by
// `python -m evals.charts`; nothing is computed here. Pick a figure with ?fig=<name>.
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
import Badge from "@cloudscape-design/components/badge";
import Grid from "@cloudscape-design/components/grid";
import SpaceBetween from "@cloudscape-design/components/space-between";
import ChatBubble from "@cloudscape-design/chat-components/chat-bubble";
import Avatar from "@cloudscape-design/chat-components/avatar";
import data from "./data.json";

applyMode(Mode.Dark);

const COMM = "FailureCommunicationEvaluator";
const V1_COLOR = "#8c8c94"; // v1 recedes when v2 is the point
const V2_COLOR = "#0972d3";

function Kpi({ label, value, hint }) {
  return (
    <div>
      <Box variant="awsui-key-label">{label}</Box>
      <Box variant="awsui-value-large">{value}</Box>
      {hint && <Box color="text-body-secondary" fontSize="body-s">{hint}</Box>}
    </div>
  );
}

// Runs in which the agent said the tool failed, per injected fault: the one behaviour the CI gate measures.
function communicated(version) {
  const { effects, by_evaluator, n_per_effect } = data.chaos;
  const per = effects.map((e) => ({ x: e.label, y: by_evaluator[version][e.key]?.[COMM] ?? 0 }));
  const total = per.reduce((s, p) => s + p.y, 0);
  return { per, total, n: n_per_effect * effects.length };
}

function ChaosChart({ versions, title, description }) {
  const { n_per_effect, effects } = data.chaos;
  const stats = Object.fromEntries(versions.map((v) => [v, communicated(v)]));
  const series = versions.map((v) => ({
    title: `prompt ${v}`,
    type: "bar",
    data: stats[v].per,
    color: versions.length === 1 || v === "v2" ? V2_COLOR : V1_COLOR,
    valueFormatter: (y) => `${y} de ${n_per_effect}`,
  }));
  return (
    <Container header={<Header variant="h2" description={description}>{title}</Header>}>
      <SpaceBetween size="l">
        <Grid gridDefinition={versions.map(() => ({ colspan: 12 / versions.length }))}>
          {versions.map((v) => (
            <Kpi key={v} label={`prompt ${v}: runs que comunicaron la falla`} value={`${stats[v].total} de ${stats[v].n}`}
                 hint={`${stats[v].n - stats[v].total} la escondieron`} />
          ))}
        </Grid>
        <BarChart
          series={series}
          xDomain={effects.map((e) => e.label)}
          yDomain={[0, n_per_effect]}
          xScaleType="categorical"
          height={260}
          hideFilter
          hideLegend={versions.length === 1}
          xTitle="falla inyectada"
          yTitle={`runs que comunicaron la falla (de ${n_per_effect})`}
          i18nStrings={{ yTickFormatter: (y) => `${y}` }}
          ariaLabel={title}
        />
      </SpaceBetween>
    </Container>
  );
}

const tools = () => Object.entries(data.chaos.tools).map(([k, t]) => `${data.chaos.effects.find((e) => e.key === k).label}: ${t}`).join(" · ");

const ChaosV1 = () => (
  <ChaosChart versions={["v1"]} title="Chaos testing · prompt v1"
    description={`FailureCommunicationEvaluator, revisado a mano · n=${data.chaos.n_per_effect} runs por condición · ${tools()}`} />
);
const ChaosV2 = () => (
  <ChaosChart versions={["v1", "v2"]} title="Chaos testing · prompt v2 contra v1"
    description={`Mismas preguntas, mismas fallas, mismas repeticiones; solo cambió el prompt · n=${data.chaos.n_per_effect} runs por condición`} />
);

function Cell({ c }) {
  if (!c) return <StatusIndicator type="pending">sin datos</StatusIndicator>;
  if (c.refused) return <StatusIndicator type="stopped">atacante rechazado</StatusIndicator>;
  const breach = c.layer === "ninguna";
  const passes = (c.scores ?? []).map((s) => s.toFixed(2)).join(" · ");
  return (
    <SpaceBetween size="xxs">
      <SpaceBetween direction="horizontal" size="xs" alignItems="center">
        <Box variant="strong" fontSize="heading-m">{c.score.toFixed(2)}</Box>
        {breach ? <Badge color="red">brecha</Badge> : <StatusIndicator type="success">{`capa: ${c.layer}`}</StatusIndicator>}
      </SpaceBetween>
      <Box color="text-body-secondary" fontSize="body-s">{breach && c.scores?.length > 1 ? `${passes} · en las ${c.scores.length} pasadas` : `pasadas: ${passes}`}</Box>
    </SpaceBetween>
  );
}

function Matrix() {
  const { strategies, rows, breach_threshold } = data.matrix;
  const columns = [
    { id: "cat", header: "categoría de riesgo", cell: (r) => <Box variant="strong" fontSize="heading-s">{r.category}</Box>, isRowHeader: true },
    ...strategies.map((s, j) => ({ id: s, header: s, cell: (r) => <Cell c={r.cells[j]} /> })),
  ];
  return (
    <Table
      variant="container"
      columnDefinitions={columns}
      items={rows}
      wrapLines
      header={<Header variant="h2" description={`peor score por categoría y estrategia, promedio de dos pasadas · brecha = score ≥ ${breach_threshold} · la capa nombrada es la que detuvo el ataque`}>Red team: qué capa te salvó</Header>}
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
    <Table variant="container" columnDefinitions={columns} items={data.layers}
      header={<Header variant="h2" description="cada categoría prueba una capa distinta; las dos últimas no tienen segunda capa">Cuatro categorías, tres capas</Header>} />
  );
}

const userAvatar = <Avatar ariaLabel="Persona de guardia" tooltipText="Persona de guardia" initials="PG" />;
const botAvatar = (loading) => <Avatar color="gen-ai" iconName="gen-ai" ariaLabel="Sentinel" tooltipText="Sentinel" loading={loading} />;

function EscenaPregunta() {
  const { question } = data.escena;
  return (
    <Container header={<Header variant="h2" description="canal de guardia · Sentinel, asistente de incident response">Una pregunta normal</Header>}>
      <SpaceBetween size="m">
        <ChatBubble type="outgoing" ariaLabel="Persona de guardia" avatar={userAvatar}>
          <Box fontSize="heading-m">{question}</Box>
        </ChatBubble>
        <ChatBubble type="incoming" ariaLabel="Sentinel" avatar={botAvatar(true)} showLoadingBar>
          <SpaceBetween size="xs">
            <Box>Leyendo la alarma y consultando la métrica…</Box>
            <SpaceBetween direction="horizontal" size="s">
              <StatusIndicator type="in-progress">get_alarms</StatusIndicator>
              <StatusIndicator type="in-progress">get_instances</StatusIndicator>
              <StatusIndicator type="in-progress">get_metric</StatusIndicator>
            </SpaceBetween>
          </SpaceBetween>
        </ChatBubble>
      </SpaceBetween>
    </Container>
  );
}

// Renders **bold** and `code` from the agent's markdown answer, nothing else.
function Md({ text }) {
  return text.split("\n").filter(Boolean).map((line, i) => (
    <Box key={i} margin={{ bottom: "xxs" }}>
      {line.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((part, j) =>
        part.startsWith("**") ? <strong key={j}>{part.slice(2, -2)}</strong> :
        part.startsWith("`") ? <code key={j}>{part.slice(1, -1)}</code> : part)}
    </Box>
  ));
}

function EscenaTimeout() {
  const { question, answer, spans, session_id } = data.escena;
  const shown = answer.split("\n\n").slice(0, 2).join("\n"); // instance line + the alarm/metric/motivo block
  const rows = spans.filter((s) => s.kind !== "agent");
  const columns = [
    { id: "span", header: "span", cell: (r) => <Box variant={r.error ? "strong" : "span"}><code>{r.span}</code>{r.kind === "model" ? " · modelo" : ""}</Box> },
    { id: "secs", header: "duración", cell: (r) => `${r.seconds.toFixed(2)} s` },
    { id: "res", header: "resultado", cell: (r) => r.kind === "model" ? <StatusIndicator type="info">respuesta</StatusIndicator>
        : r.error ? <StatusIndicator type="error">{r.error}</StatusIndicator> : <StatusIndicator type="success">ok</StatusIndicator> },
  ];
  return (
    <Grid gridDefinition={[{ colspan: 6 }, { colspan: 6 }]}>
      <Container header={<Header variant="h2" description="lo que vio la persona de guardia">La respuesta</Header>}>
        <SpaceBetween size="m">
          <ChatBubble type="outgoing" ariaLabel="Persona de guardia" avatar={userAvatar}>{question}</ChatBubble>
          <ChatBubble type="incoming" ariaLabel="Sentinel" avatar={botAvatar(false)}><Md text={shown} /></ChatBubble>
        </SpaceBetween>
      </Container>
      <Table variant="container" columnDefinitions={columns} items={rows} wrapLines
        header={<Header variant="h2" description={`lo que pasó de verdad · sesión ${session_id.slice(0, 8)} · prompt v1`}>El trace</Header>} />
    </Grid>
  );
}

// Three defence layers and how far each attack category gets before something stops it.
function CapasDiagrama() {
  const F = "'Open Sans', Helvetica, Arial, sans-serif";
  const bands = [
    { y: 170, title: "CAPA 1 · MODELO", sub: "prompt v1 / v2", color: "#539fe5" },
    { y: 400, title: "CAPA 2 · SANDBOX", sub: "Strands Shell: solo /runbooks", color: "#e07941" },
    { y: 630, title: "CAPA 3 · PERMISOS", sub: "IAM: Deny si env=prod", color: "#eb6f6f" },
  ];
  const lanes = [
    { x: 620, label: ["fuga del", "system prompt"], stop: 290, layer: "modelo", color: "#d5dbdb" },
    { x: 880, label: ["bypass de", "guías"], stop: 340, layer: "modelo", color: "#d5dbdb" },
    { x: 1140, label: ["exfiltración", "de datos"], stop: 530, layer: "sandbox", color: "#2ea597" },
    { x: 1400, label: ["agencia", "excesiva"], stop: 760, layer: "IAM (Deny)", color: "#c33d69" },
  ];
  return (
    <svg viewBox="0 0 1560 880" width="100%" style={{ fontFamily: F, display: "block" }} role="img" aria-label="Tres capas de defensa">
      <text x="780" y="52" textAnchor="middle" fontSize="40" fontWeight="700" fill="#fff">Tres capas de defensa</text>
      <text x="780" y="92" textAnchor="middle" fontSize="26" fill="#b6bec9">cuánto avanza cada ataque antes de que algo lo detenga</text>
      {bands.map((b) => (
        <g key={b.title}>
          <rect x="60" y={b.y} width="1440" height="210" rx="16" fill={b.color} fillOpacity="0.14" stroke={b.color} strokeWidth="3" />
          <text x="90" y={b.y + 52} fontSize="30" fontWeight="700" fill={b.color}>{b.title}</text>
          <text x="90" y={b.y + 92} fontSize="24" fontStyle="italic" fill="#e9ebed">{b.sub}</text>
        </g>
      ))}
      {lanes.map((l) => (
        <g key={l.x}>
          <text x={l.x} y="128" textAnchor="middle" fontSize="27" fontWeight="700" fill={l.color}>{l.label[0]}</text>
          <text x={l.x} y="158" textAnchor="middle" fontSize="27" fontWeight="700" fill={l.color}>{l.label[1]}</text>
          <line x1={l.x} y1="168" x2={l.x} y2={l.stop - 14} stroke={l.color} strokeWidth="5" />
          <polygon points={`${l.x},${l.stop} ${l.x - 13},${l.stop - 22} ${l.x + 13},${l.stop - 22}`} fill={l.color} />
          <rect x={l.x - 44} y={l.stop + 2} width="88" height="10" rx="4" fill="#fff" />
          <text x={l.x} y={l.stop + 46} textAnchor="middle" fontSize="26" fontWeight="700" fill="#fff">{l.layer}</text>
        </g>
      ))}
      <line x1="30" y1="180" x2="30" y2="830" stroke="#8d99a8" strokeWidth="3" />
      <polygon points="30,846 20,826 40,826" fill="#8d99a8" />
      <text x="1500" y="866" textAnchor="end" fontSize="22" fill="#b6bec9">▬ = capa que detiene el ataque</text>
    </svg>
  );
}

const FIGURES = { "chaos-v1": ChaosV1, "chaos-v2": ChaosV2, matrix: Matrix, capas: Capas,
  "escena-pregunta": EscenaPregunta, "escena-timeout": EscenaTimeout, "capas-diagrama": CapasDiagrama };
const params = new URLSearchParams(location.search);
const Fig = FIGURES[params.get("fig")] ?? ChaosV1;
document.getElementById("root").style.width = `${params.get("w") ?? 992}px`;
createRoot(document.getElementById("root")).render(<Fig />);
