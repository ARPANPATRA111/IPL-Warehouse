import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  startTransition,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from "react";
import type { FormEvent, ReactNode } from "react";

type ViewKey =
  | "overview"
  | "batting"
  | "bowling"
  | "teams"
  | "venues"
  | "head-to-head"
  | "insights-lab";

type Primitive = string | number | boolean | null;
type TableRow = Record<string, Primitive>;

type ReferenceOptions = {
  seasons: string[];
  teams: string[];
  venues: string[];
};

type HomeSummaryData = {
  metrics: Record<string, number>;
  season_summary: TableRow[];
};

type HomeLeadersData = {
  top_batsmen: TableRow[];
  top_bowlers: TableRow[];
};

type HomeData = HomeSummaryData & HomeLeadersData;

type QueryEngineContext = {
  schema_summary: string;
  examples: string[];
  row_limit: number;
};

type QueryAnswerMode = "table" | "text" | "scalar";

type QueryEngineResult = {
  title: string;
  explanation: string;
  sql: string;
  columns: string[];
  rows: TableRow[];
  row_count: number;
  execution_ms: number;
  answer_mode: QueryAnswerMode;
  answer_text: string | null;
  answer_source: "warehouse" | "external";
};

type QueryChartMode = "leaderboard" | "trend" | "stacked" | "scatter" | "heatmap";

type ApiState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
};

type ThemeMode = "dark" | "light";

const NAV_ITEMS: Array<{ key: ViewKey; label: string; eyebrow: string; mobileLabel: string }> = [
  { key: "overview", label: "Overview", eyebrow: "Warehouse pulse", mobileLabel: "Overview" },
  { key: "batting", label: "Batting", eyebrow: "Run creation", mobileLabel: "Batting" },
  { key: "bowling", label: "Bowling", eyebrow: "Wicket pressure", mobileLabel: "Bowling" },
  { key: "teams", label: "Teams", eyebrow: "Franchise shape", mobileLabel: "Teams" },
  { key: "venues", label: "Venues", eyebrow: "Ground behavior", mobileLabel: "Venues" },
  { key: "head-to-head", label: "Head to Head", eyebrow: "Rivalry lens", mobileLabel: "Rivalry" },
  { key: "insights-lab", label: "Query Lab", eyebrow: "Natural language SQL", mobileLabel: "Query" },
];

const PIE_COLORS = ["#f97316", "#14b8a6", "#facc15", "#38bdf8", "#fb7185"];
const SESSION_CACHE_PREFIX = "ipl-analytics-cache:";
const LOCAL_CACHE_PREFIX = "ipl-analytics-local:";
const QUERY_RECENT_KEY = `${LOCAL_CACHE_PREFIX}query-recent`;
const QUERY_SUCCESS_KEY = `${LOCAL_CACHE_PREFIX}query-success`;
const QUERY_FAVORITES_KEY = `${LOCAL_CACHE_PREFIX}query-favorites`;
const THEME_KEY = `${LOCAL_CACHE_PREFIX}theme`;
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const QUERY_CHART_MODE_META: Record<QueryChartMode, { label: string; summary: string }> = {
  leaderboard: {
    label: "Ranking",
    summary: "A compact ranked read of the strongest categories in the result set.",
  },
  trend: {
    label: "Trend",
    summary: "A time or sequence view that shows how the metric moves across the category axis.",
  },
  stacked: {
    label: "Comparison",
    summary: "A side-by-side comparison of the two strongest numeric signals in the answer.",
  },
  scatter: {
    label: "Relationship",
    summary: "A relationship plot to spot correlation, clustering, or outlier behavior in the result.",
  },
  heatmap: {
    label: "Intensity",
    summary: "A dense scan that highlights where the strongest values are concentrated.",
  },
};

function getDefaultTheme(now: Date = new Date()): ThemeMode {
  if (typeof window !== "undefined") {
    const savedTheme = window.localStorage.getItem(THEME_KEY);
    if (savedTheme === "dark" || savedTheme === "light") {
      return savedTheme;
    }
  }

  const hour = now.getHours();
  return hour >= 10 && hour < 18 ? "light" : "dark";
}

function applyDocumentTheme(theme: ThemeMode) {
  if (typeof document === "undefined") {
    return;
  }

  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

function buildApiPath(path: string, params?: Record<string, string | string[] | undefined>) {
  const searchParams = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item) {
          searchParams.append(key, item);
        }
      });
      return;
    }

    if (value) {
      searchParams.set(key, value);
    }
  });

  const query = searchParams.toString();
  const relative = query ? `${path}?${query}` : path;
  return API_BASE_URL ? `${API_BASE_URL}${relative}` : relative;
}

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

async function postJson<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }

  return (await response.json()) as T;
}

function readSessionCache<T>(path: string): T | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.sessionStorage.getItem(`${SESSION_CACHE_PREFIX}${path}`);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    window.sessionStorage.removeItem(`${SESSION_CACHE_PREFIX}${path}`);
    return null;
  }
}

function writeSessionCache<T>(path: string, data: T) {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.setItem(`${SESSION_CACHE_PREFIX}${path}`, JSON.stringify(data));
}

function readLocalCache<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") {
    return fallback;
  }

  const raw = window.localStorage.getItem(key);
  if (!raw) {
    return fallback;
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    window.localStorage.removeItem(key);
    return fallback;
  }
}

function writeLocalCache<T>(key: string, value: T) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(key, JSON.stringify(value));
}

function useApi<T>(path: string | null): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({
    data: null,
    loading: Boolean(path),
    error: null,
  });

  useEffect(() => {
    if (!path) {
      setState({ data: null, loading: false, error: null });
      return;
    }

    let active = true;
  const controller = new AbortController();
    const cachedData = readSessionCache<T>(path);

    if (cachedData) {
      setState({ data: cachedData, loading: false, error: null });
    } else {
      setState((current) => ({ ...current, loading: true, error: null }));
    }

    fetchJson<T>(path, controller.signal)
      .then((data) => {
        if (!active) {
          return;
        }
        writeSessionCache(path, data);
        setState({ data, loading: false, error: null });
      })
      .catch((error: Error) => {
        if (error.name === "AbortError") {
          return;
        }
        if (!active) {
          return;
        }
        setState((current) => ({
          data: current.data,
          loading: false,
          error: current.data ? null : error.message,
        }));
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [path]);

  return state;
}

function useViewportQuery(query: string) {
  const getMatch = () => {
    if (typeof window === "undefined") {
      return false;
    }

    return window.matchMedia(query).matches;
  };

  const [matches, setMatches] = useState(getMatch);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const mediaQuery = window.matchMedia(query);
    const updateMatch = (event: MediaQueryListEvent) => {
      setMatches(event.matches);
    };

    setMatches(mediaQuery.matches);

    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", updateMatch);
    } else {
      mediaQuery.addListener(updateMatch);
    }

    return () => {
      if (typeof mediaQuery.removeEventListener === "function") {
        mediaQuery.removeEventListener("change", updateMatch);
      } else {
        mediaQuery.removeListener(updateMatch);
      }
    };
  }, [query]);

  return matches;
}

function useEstimatedProgress(active: boolean) {
  const [progress, setProgress] = useState(active ? 14 : 100);

  useEffect(() => {
    if (!active) {
      setProgress(100);
      return;
    }

    setProgress((current) => (current > 0 && current < 100 ? current : 14));

    const intervalId = window.setInterval(() => {
      setProgress((current) => {
        if (current >= 94) {
          return 94;
        }

        if (current < 42) {
          return current + 8;
        }

        if (current < 72) {
          return current + 5;
        }

        if (current < 86) {
          return current + 3;
        }

        return current + 1;
      });
    }, 180);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [active]);

  return Math.min(progress, 100);
}

function toggleInList(items: string[], value: string) {
  return items.includes(value)
    ? items.filter((item) => item !== value)
    : [...items, value];
}

function formatValue(value: Primitive) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "number") {
    return Number.isInteger(value)
      ? new Intl.NumberFormat("en-US").format(value)
      : value.toFixed(2);
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return value;
}

function toChartNumber(row: TableRow, key: string) {
  const value = row[key];
  return typeof value === "number" ? value : Number(value ?? 0);
}

function toSafeNumber(value: Primitive) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : NaN;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : NaN;
  }
  return NaN;
}

function getNumericColumns(rows: TableRow[]) {
  if (!rows.length) {
    return [];
  }

  return Object.keys(rows[0]).filter((column) =>
    rows.every(
      (row) => row[column] === null || row[column] === undefined || Number.isFinite(toSafeNumber(row[column])),
    ),
  );
}

function getCategoryColumn(rows: TableRow[], numericColumns: string[]) {
  if (!rows.length) {
    return null;
  }

  return Object.keys(rows[0]).find((column) => !numericColumns.includes(column)) || null;
}

function pickMaxRow(rows: TableRow[], key: string) {
  return rows.reduce((best, row) =>
    toChartNumber(row, key) > toChartNumber(best, key) ? row : best,
  rows[0]);
}

function pickMinRow(rows: TableRow[], key: string) {
  return rows.reduce((best, row) =>
    toChartNumber(row, key) < toChartNumber(best, key) ? row : best,
  rows[0]);
}

function rememberPrompt(prompts: string[], prompt: string, limit = 8) {
  const normalizedPrompt = prompt.trim();
  if (!normalizedPrompt) {
    return prompts;
  }

  return [normalizedPrompt, ...prompts.filter((item) => item !== normalizedPrompt)].slice(0, limit);
}

function getVerticalChartHeight(rowCount: number, minimum = 320, rowHeight = 38) {
  return Math.max(minimum, rowCount * rowHeight);
}

function uniqueChartModes(modes: QueryChartMode[]) {
  return modes.filter((mode, index) => modes.indexOf(mode) === index);
}

function getChartModeLabel(mode: QueryChartMode) {
  return QUERY_CHART_MODE_META[mode].label;
}

function getChartModeSummary(mode: QueryChartMode) {
  return QUERY_CHART_MODE_META[mode].summary;
}

function formatColumnLabel(column: string) {
  return column.replace(/_/g, " ");
}

function truncateChartLabel(value: Primitive, maxLength = 12) {
  const label = formatValue(value);
  if (label.length <= maxLength) {
    return label;
  }

  return `${label.slice(0, maxLength - 1)}…`;
}

function getChartSuggestions(rows: TableRow[]): QueryChartMode[] {
  const numericColumns = getNumericColumns(rows);
  const categoryColumn = getCategoryColumn(rows, numericColumns);

  if (!rows.length || !numericColumns.length) {
    return [];
  }

  const suggestions: QueryChartMode[] = [];
  if (categoryColumn) {
    if (/(season|date|year)/i.test(categoryColumn)) {
      suggestions.push("trend");
    }
    suggestions.push("leaderboard");
    suggestions.push("heatmap");
    if (numericColumns.length >= 2) {
      suggestions.push("stacked");
    }
  }

  if (numericColumns.length >= 2) {
    suggestions.push("scatter");
  }

  return uniqueChartModes(suggestions);
}

function SectionHeader(props: { eyebrow: string; title: string; subtitle: string }) {
  return (
    <div className="section-header">
      <span className="eyebrow">{props.eyebrow}</span>
      <h2>{props.title}</h2>
      <p>{props.subtitle}</p>
    </div>
  );
}

function Panel(props: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${props.className || ""}`}>
      <div className="panel-head">
        <div>
          <h3>{props.title}</h3>
          {props.subtitle ? <p>{props.subtitle}</p> : null}
        </div>
      </div>
      {props.children}
    </section>
  );
}

function SkeletonBlock(props: { className?: string }) {
  return <span aria-hidden="true" className={`skeleton-block ${props.className || ""}`.trim()} />;
}

function OverviewSkeleton() {
  return (
    <div className="view-stack loading-view-stack" aria-hidden="true">
      <div className="section-header loading-section-header">
        <SkeletonBlock className="skeleton-eyebrow" />
        <SkeletonBlock className="skeleton-heading" />
        <SkeletonBlock className="skeleton-copy" />
      </div>

      <div className="metric-grid loading-metric-grid">
        {Array.from({ length: 8 }, (_, index) => (
          <article className="metric-card loading-metric-card" key={`metric-skeleton-${index}`}>
            <SkeletonBlock className="skeleton-label" />
            <SkeletonBlock className="skeleton-value" />
          </article>
        ))}
      </div>

      <div className="panel-grid panel-grid-2 loading-panel-grid">
        {Array.from({ length: 2 }, (_, index) => (
          <section className="panel loading-panel" key={`overview-panel-skeleton-${index}`}>
            <div className="panel-head loading-panel-head">
              <div>
                <SkeletonBlock className="skeleton-panel-title" />
                <SkeletonBlock className="skeleton-panel-copy" />
              </div>
            </div>
            <SkeletonBlock className="skeleton-chart" />
            <div className="loading-table-preview">
              {Array.from({ length: 4 }, (_, rowIndex) => (
                <SkeletonBlock className="skeleton-table-row" key={`overview-table-row-${index}-${rowIndex}`} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function GenericSkeleton() {
  return (
    <div className="panel-grid panel-grid-2 loading-panel-grid" aria-hidden="true">
      {Array.from({ length: 2 }, (_, index) => (
        <section className="panel loading-panel" key={`generic-panel-skeleton-${index}`}>
          <div className="panel-head loading-panel-head">
            <div>
              <SkeletonBlock className="skeleton-panel-title" />
              <SkeletonBlock className="skeleton-panel-copy" />
            </div>
          </div>
          <SkeletonBlock className="skeleton-chart" />
        </section>
      ))}
    </div>
  );
}

function LeaderboardPanelsSkeleton() {
  return (
    <div className="panel-grid panel-grid-2 loading-panel-grid" aria-hidden="true">
      {Array.from({ length: 2 }, (_, index) => (
        <section className="panel loading-panel" key={`leaderboard-panel-skeleton-${index}`}>
          <div className="panel-head loading-panel-head">
            <div>
              <SkeletonBlock className="skeleton-panel-title" />
              <SkeletonBlock className="skeleton-panel-copy" />
            </div>
          </div>
          <SkeletonBlock className="skeleton-chart skeleton-chart-short" />
          <div className="loading-table-preview">
            {Array.from({ length: 5 }, (_, rowIndex) => (
              <SkeletonBlock className="skeleton-table-row" key={`leaderboard-table-row-${index}-${rowIndex}`} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function LoadingState(props: {
  label?: string;
  detail?: string;
  progressLabel?: string;
  variant?: "generic" | "boot" | "overview";
  showPercent?: boolean;
}) {
  const progress = useEstimatedProgress(true);
  const variant = props.variant || "generic";
  const label = props.label || "Loading dashboard data";
  const detail = props.detail || "Fetching the active warehouse slice and preparing lightweight visual components.";
  const progressLabel = props.progressLabel || "Warehouse readiness";
  const showPercent = props.showPercent ?? variant !== "generic";

  return (
    <div className={`loading-shell loading-shell-${variant}`.trim()} role="status" aria-live="polite">
      <section className="status-card loading-card">
        <div className="loading-copy-row">
          <div>
            <span className="eyebrow">{progressLabel}</span>
            <strong className="loading-title">{label}</strong>
          </div>
          {showPercent ? <span className="loading-percent">{Math.round(progress)}%</span> : null}
        </div>
        <div aria-hidden="true" className="loading-bar-track">
          <span className="loading-bar-fill" style={{ width: `${progress}%` }} />
        </div>
        <p className="loading-detail">{detail}</p>
      </section>

      {variant === "overview" ? <OverviewSkeleton /> : <GenericSkeleton />}
    </div>
  );
}

function ErrorState(props: { message: string }) {
  return (
    <div className="status-card error" role="alert">
      {props.message}
    </div>
  );
}

function EmptyState(props: { message: string }) {
  return (
    <div className="status-card muted" role="status">
      {props.message}
    </div>
  );
}

function PromptChipSection(props: {
  title: string;
  items: string[];
  activeValue?: string;
  onSelect: (value: string, source: string) => void;
}) {
  if (!props.items.length) {
    return null;
  }

  const normalizedActiveValue = props.activeValue?.trim().toLowerCase() || "";

  return (
    <div className="prompt-section">
      <span className="filter-title">{props.title}</span>
      <div className="chip-row">
        {props.items.map((item) => {
          const isActive = item.trim().toLowerCase() === normalizedActiveValue;

          return (
            <button
              key={`${props.title}-${item}`}
              aria-pressed={isActive}
              className={`chip chip-prompt ${isActive ? "chip-active chip-prompt-active" : ""}`.trim()}
              onClick={() => props.onSelect(item, props.title)}
              type="button"
            >
              {item}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ThemeToggle(props: { theme: ThemeMode; onToggle: () => void; className?: string }) {
  return (
    <button
      className={`theme-toggle ${props.className || ""}`.trim()}
      type="button"
      aria-label={props.theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => {
        startTransition(() => {
          props.onToggle();
        });
      }}
    >
      <span className="theme-toggle-track" aria-hidden="true">
        <span className="theme-toggle-thumb" />
      </span>
      <span className="theme-toggle-copy">
        <span className="theme-toggle-caption">Appearance</span>
        <strong>{props.theme === "dark" ? "Midnight" : "Paper"}</strong>
      </span>
    </button>
  );
}

function DataTable(props: { rows: TableRow[] }) {
  const isCompactLayout = useViewportQuery("(max-width: 720px)");
  const [pageSize, setPageSize] = useState(() =>
    typeof window !== "undefined" && window.matchMedia("(max-width: 720px)").matches
      ? 8
      : props.rows.length > 120
        ? 25
        : 12,
  );
  const [page, setPage] = useState(1);
  const [scrollTop, setScrollTop] = useState(0);
  const columns = props.rows.length ? Object.keys(props.rows[0]) : [];
  const pageSizeOptions = isCompactLayout ? [8, 12, 16] : [10, 12, 25, 50];
  const totalPages = Math.max(1, Math.ceil(props.rows.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageStart = (currentPage - 1) * pageSize;
  const pagedRows = props.rows.slice(pageStart, pageStart + pageSize);
  const virtualized = !isCompactLayout && pagedRows.length > 14;
  const rowHeight = isCompactLayout ? 40 : 46;
  const viewportHeight = Math.min(420, Math.max(220, pagedRows.length * rowHeight));
  const visibleCount = virtualized ? Math.ceil(viewportHeight / rowHeight) + 4 : pagedRows.length;
  const windowStart = virtualized ? Math.max(0, Math.floor(scrollTop / rowHeight) - 2) : 0;
  const windowEnd = virtualized ? Math.min(pagedRows.length, windowStart + visibleCount) : pagedRows.length;
  const visibleRows = pagedRows.slice(windowStart, windowEnd);
  const topSpacerHeight = windowStart * rowHeight;
  const bottomSpacerHeight = (pagedRows.length - windowEnd) * rowHeight;
  const shouldShowScrollHint = isCompactLayout && columns.length > 4;

  useEffect(() => {
    setPage(1);
  }, [props.rows]);

  useEffect(() => {
    const nextDefault = isCompactLayout
      ? 8
      : props.rows.length > 120
        ? 25
        : 12;

    setPageSize((currentValue) =>
      pageSizeOptions.includes(currentValue) ? currentValue : nextDefault,
    );
  }, [isCompactLayout, props.rows.length]);

  useEffect(() => {
    setScrollTop(0);
  }, [currentPage, pageSize]);

  if (!props.rows.length) {
    return <EmptyState message="No rows available for the current selection." />;
  }

  return (
    <div className="table-shell">
      <div className="table-toolbar">
        <span className="helper-copy">
          Showing {formatValue(pageStart + 1)} to {formatValue(pageStart + pagedRows.length)} of {formatValue(props.rows.length)} rows.
        </span>
        <div className="table-toolbar-controls">
          <label className="table-page-size">
            <span>Rows</span>
            <select className="select-input" value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))}>
              {pageSizeOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {shouldShowScrollHint ? <p className="table-mobile-hint">Swipe sideways to see the remaining columns.</p> : null}

      <div
        className={`table-wrap ${virtualized ? "table-wrap-virtualized" : ""} ${isCompactLayout ? "table-wrap-mobile" : ""}`.trim()}
        onScroll={virtualized ? (event) => setScrollTop(event.currentTarget.scrollTop) : undefined}
        style={virtualized ? { maxHeight: `${viewportHeight}px` } : undefined}
      >
        <table className={`data-table ${isCompactLayout ? "data-table-mobile" : ""}`.trim()}>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{formatColumnLabel(column)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {topSpacerHeight ? (
              <tr className="table-spacer-row">
                <td className="table-spacer-cell" colSpan={columns.length} style={{ height: `${topSpacerHeight}px` }} />
              </tr>
            ) : null}
            {visibleRows.map((row, rowIndex) => (
              <tr key={`${pageStart + windowStart + rowIndex}-${String(row[columns[0]])}`}>
                {columns.map((column) => (
                  <td key={column}>{formatValue(row[column])}</td>
                ))}
              </tr>
            ))}
            {bottomSpacerHeight ? (
              <tr className="table-spacer-row">
                <td className="table-spacer-cell" colSpan={columns.length} style={{ height: `${bottomSpacerHeight}px` }} />
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {totalPages > 1 ? (
        <div className="table-pagination">
          <button className="chip" disabled={currentPage === 1} onClick={() => setPage((value) => Math.max(1, value - 1))} type="button">
            Previous
          </button>
          <span className="helper-copy">
            Page {formatValue(currentPage)} of {formatValue(totalPages)}
          </span>
          <button className="chip" disabled={currentPage === totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))} type="button">
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}

function AutoInsightChart(props: { rows: TableRow[] }) {
  const numericColumns = getNumericColumns(props.rows);
  const categoryColumn = getCategoryColumn(props.rows, numericColumns);
  const suggestions = getChartSuggestions(props.rows);
  const [activeMode, setActiveMode] = useState<QueryChartMode | null>(suggestions[0] || null);

  useEffect(() => {
    setActiveMode(suggestions[0] || null);
  }, [props.rows]);

  if (!props.rows.length) {
    return <EmptyState message="Ask a question to generate a visual answer." />;
  }

  const chartRows = props.rows.slice(0, 12);

  if (!suggestions.length || !activeMode) {
    return <EmptyState message="The generated result is better viewed as a table than a chart." />;
  }

  const primaryMetric = numericColumns[0];
  const secondaryMetric = numericColumns[1];
  const metricSummary = [categoryColumn ? formatColumnLabel(categoryColumn) : null, primaryMetric ? formatColumnLabel(primaryMetric) : null]
    .filter(Boolean)
    .join(" x ");

  let chartContent: ReactNode = <EmptyState message="The generated result is better viewed as a table than a chart." />;

  if (activeMode === "trend" && categoryColumn && primaryMetric) {
    chartContent = (
      <div className="chart-box chart-box-short">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartRows}>
            <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
            <XAxis dataKey={categoryColumn} stroke="#9aa8c7" />
            <YAxis stroke="#9aa8c7" />
            <Tooltip />
            <Line type="monotone" dataKey={primaryMetric} stroke="#14b8a6" strokeWidth={3} dot={{ r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (activeMode === "leaderboard" && categoryColumn && primaryMetric) {
    chartContent = (
      <div className="chart-box chart-box-short">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartRows} layout="vertical" margin={{ top: 8, right: 12, bottom: 8, left: 12 }}>
            <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
            <XAxis type="number" stroke="#9aa8c7" />
            <YAxis type="category" dataKey={categoryColumn} width={170} interval={0} stroke="#9aa8c7" />
            <Tooltip />
            <Bar dataKey={primaryMetric} fill="#f97316" radius={[0, 8, 8, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (activeMode === "stacked" && categoryColumn && primaryMetric && secondaryMetric) {
    chartContent = (
      <div className="chart-box chart-box-short">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartRows}>
            <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
            <XAxis dataKey={categoryColumn} stroke="#9aa8c7" hide />
            <YAxis stroke="#9aa8c7" />
            <Tooltip />
            <Legend />
            <Bar dataKey={primaryMetric} fill="#f97316" radius={[8, 8, 0, 0]} />
            <Bar dataKey={secondaryMetric} fill="#38bdf8" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (activeMode === "scatter" && numericColumns.length >= 2) {
    chartContent = (
      <div className="chart-box chart-box-short">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart>
            <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
            <XAxis type="number" dataKey={numericColumns[0]} stroke="#9aa8c7" />
            <YAxis type="number" dataKey={numericColumns[1]} stroke="#9aa8c7" />
            <Tooltip />
            <Scatter
              data={props.rows.filter(
                (row) =>
                  Number.isFinite(toSafeNumber(row[numericColumns[0]])) &&
                  Number.isFinite(toSafeNumber(row[numericColumns[1]])),
              )}
              fill="#38bdf8"
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (activeMode === "heatmap" && categoryColumn && primaryMetric) {
    const maxValue = Math.max(...chartRows.map((item) => toChartNumber(item, primaryMetric)));
    chartContent = (
      <div className="heatmap-grid">
        {chartRows.map((row) => {
          const metricValue = toChartNumber(row, primaryMetric);
          const intensity = maxValue > 0 ? metricValue / maxValue : 0;
          return (
            <article
              className="heatmap-cell"
              key={`${String(row[categoryColumn])}-${String(row[primaryMetric])}`}
              style={{
                background: `linear-gradient(135deg, rgba(249, 115, 22, ${0.12 + intensity * 0.36}), rgba(56, 189, 248, ${0.08 + intensity * 0.24}))`,
              }}
            >
              <span>{formatValue(row[categoryColumn])}</span>
              <strong>{formatValue(row[primaryMetric])}</strong>
            </article>
          );
        })}
      </div>
    );
  }

  return (
    <div className="query-chart-stack">
      <div className="query-visual-shell">
        <div className="query-visual-header">
          <div className="query-visual-copy">
            <span className="query-visual-kicker">Visual explorer</span>
            <strong>{getChartModeLabel(activeMode)}</strong>
            <p>{getChartModeSummary(activeMode)}</p>
          </div>

          <div className="chart-suggestion-row" role="tablist" aria-label="Visualization options">
            {suggestions.map((mode) => (
              <button
                key={mode}
                aria-selected={activeMode === mode}
                className={`chip chart-mode-button ${activeMode === mode ? "chip-active" : ""}`.trim()}
                onClick={() => setActiveMode(mode)}
                role="tab"
                type="button"
              >
                {getChartModeLabel(mode)}
              </button>
            ))}
          </div>
        </div>

        <div className="query-visual-surface">{chartContent}</div>

        <div className="query-visual-footer">
          <span>Showing the first {formatValue(chartRows.length)} rows in the visual layer.</span>
          {metricSummary ? <strong>{metricSummary}</strong> : null}
        </div>
      </div>
    </div>
  );
}

function MultiChipFilter(props: {
  title: string;
  items: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <div className="filter-group">
      <span className="filter-title">{props.title}</span>
      <div className="chip-row">
        {props.items.map((item) => (
          <button
            key={item}
            className={`chip ${props.selected.includes(item) ? "chip-active" : ""}`}
            aria-pressed={props.selected.includes(item)}
            onClick={() => props.onToggle(item)}
            type="button"
          >
            {item}
          </button>
        ))}
      </div>
    </div>
  );
}

function OverviewView() {
  const isCompactLayout = useViewportQuery("(max-width: 720px)");
  const summaryState = useApi<HomeSummaryData>(buildApiPath("/api/home/summary"));
  const [loadLeaders, setLoadLeaders] = useState(false);
  const leadersState = useApi<HomeLeadersData>(
    loadLeaders ? buildApiPath("/api/home/leaders") : null,
  );

  useEffect(() => {
    if (!summaryState.data) {
      setLoadLeaders(false);
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      setLoadLeaders(true);
    });

    return () => {
      window.cancelAnimationFrame(frameId);
    };
  }, [summaryState.data]);

  if (summaryState.loading) {
    return (
      <LoadingState
        variant="overview"
        label="Loading IPL pulse board"
        detail="Pulling season trends, metric totals, and top performers while charts stay lightweight on first paint."
        progressLabel="Overview load"
      />
    );
  }
  if (summaryState.error) {
    return <ErrorState message={summaryState.error} />;
  }
  if (!summaryState.data) {
    return <EmptyState message="Overview data is unavailable." />;
  }

  const data: HomeData = {
    ...summaryState.data,
    top_batsmen: leadersState.data?.top_batsmen || [],
    top_bowlers: leadersState.data?.top_bowlers || [],
  };

  const metricEntries = [
    ["Matches", data.metrics.total_matches],
    ["Players", data.metrics.total_players],
    ["Active Teams", data.metrics.total_teams],
    ["Deliveries", data.metrics.total_deliveries],
    ["Runs", data.metrics.total_runs],
    ["Wickets", data.metrics.total_wickets],
    ["Sixes", data.metrics.total_sixes],
    ["Fours", data.metrics.total_fours],
  ];
  const seasonSummary = data.season_summary;
  const boundaryMix = [
    { name: "Fours", value: data.metrics.total_fours },
    { name: "Sixes", value: data.metrics.total_sixes },
  ];
  const highestRunSeason = pickMaxRow(seasonSummary, "total_runs");
  const mostExplosiveSeason = pickMaxRow(seasonSummary, "sixes");
  const fastestSeason = pickMaxRow(seasonSummary, "avg_runs_per_ball");
  const mobileSummaryEntries = metricEntries.slice(0, 3);
  const visibleMetricEntries = isCompactLayout ? metricEntries.slice(3, 7) : metricEntries;

  return (
    <div className="view-stack">
      <SectionHeader
        eyebrow="Warehouse pulse"
        title="IPL pulse board"
        subtitle="Read the season story fast: match load, run flow, wicket pressure, and the biggest names in the warehouse."
      />

      {isCompactLayout ? null : (
        <div className="insight-strip">
          <article className="insight-card">
            <span>Peak run engine</span>
            <strong>{highestRunSeason?.season || "-"}</strong>
            <p>{formatValue(highestRunSeason?.total_runs || null)} total runs in the loaded dataset.</p>
          </article>
          <article className="insight-card">
            <span>Biggest six burst</span>
            <strong>{mostExplosiveSeason?.season || "-"}</strong>
            <p>{formatValue(mostExplosiveSeason?.sixes || null)} sixes cleared the rope.</p>
          </article>
          <article className="insight-card">
            <span>Quickest scoring year</span>
            <strong>{fastestSeason?.season || "-"}</strong>
            <p>{formatValue(fastestSeason?.avg_runs_per_ball || null)} runs per ball on average.</p>
          </article>
        </div>
      )}

      {isCompactLayout ? (
        <article className="metric-card overview-cluster-card">
          {/* <span className="overview-cluster-title">Match base</span> */}
          <div className="overview-cluster-stats">
            {mobileSummaryEntries.map(([label, value]) => (
              <div className="overview-cluster-stat" key={label}>
                <span>{label}</span>
                <strong>{formatValue(value)}</strong>
              </div>
            ))}
          </div>
        </article>
      ) : null}

      <div className={`metric-grid ${isCompactLayout ? "overview-detail-grid" : ""}`.trim()}>
        {visibleMetricEntries.map(([label, value], index) => (
          <article className={`metric-card ${isCompactLayout ? "metric-card-detail" : ""}`.trim()} key={label}>
            <span>{label}</span>
            <strong>{formatValue(value)}</strong>
          </article>
        ))}
      </div>

      {isCompactLayout ? (
        <div className="panel-grid panel-grid-2">
          <Panel title="Total run engine" subtitle="Which seasons pumped the most runs into the league.">
            <div className="chart-box chart-box-short">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={seasonSummary}>
                  <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                  <XAxis dataKey="season" stroke="#9aa8c7" />
                  <YAxis stroke="#9aa8c7" />
                  <Tooltip />
                  <Line type="monotone" dataKey="total_runs" stroke="#14b8a6" strokeWidth={3} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title="Total wicket broker engine" subtitle="Which seasons created the most wickets.">
            <div className="chart-box chart-box-short">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={seasonSummary}>
                  <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                  <XAxis dataKey="season" stroke="#9aa8c7" />
                  <YAxis stroke="#9aa8c7" />
                  <Tooltip />
                  <Bar dataKey="wickets" fill="#38bdf8" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </div>
      ) : (
        <>
          <div className="panel-grid panel-grid-3">
            <Panel title="Boundary split" subtitle="How total scoring is distributed across rope shots.">
              <div className="chart-box chart-box-short">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={boundaryMix} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} innerRadius={52}>
                      {boundaryMix.map((entry, index) => (
                        <Cell key={`${entry.name}-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </Panel>

            <Panel title="Total run engine" subtitle="Which seasons pumped the most runs into the league.">
              <div className="chart-box chart-box-short">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={seasonSummary}>
                    <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                    <XAxis dataKey="season" stroke="#9aa8c7" />
                    <YAxis stroke="#9aa8c7" />
                    <Tooltip />
                    <Line type="monotone" dataKey="total_runs" stroke="#14b8a6" strokeWidth={3} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Panel>

            <Panel title="Total wicket broker engine" subtitle="Which seasons created the most wickets.">
              <div className="chart-box chart-box-short">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={seasonSummary}>
                    <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                    <XAxis dataKey="season" stroke="#9aa8c7" />
                    <YAxis stroke="#9aa8c7" />
                    <Tooltip />
                    <Bar dataKey="wickets" fill="#38bdf8" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          </div>

          <div className="panel-grid panel-grid-2">
            <Panel title="Season run arc" subtitle="How total scoring shifts season by season.">
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={seasonSummary}>
                    <defs>
                      <linearGradient id="run-fill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#f97316" stopOpacity={0.8} />
                        <stop offset="100%" stopColor="#f97316" stopOpacity={0.08} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                    <XAxis dataKey="season" stroke="#9aa8c7" />
                    <YAxis stroke="#9aa8c7" />
                    <Tooltip />
                    <Area type="monotone" dataKey="total_runs" stroke="#f97316" fill="url(#run-fill)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Panel>

            <Panel title="Six-hitting index" subtitle="Seasonal burst scoring from the rope.">
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={seasonSummary}>
                    <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                    <XAxis dataKey="season" stroke="#9aa8c7" />
                    <YAxis stroke="#9aa8c7" />
                    <Tooltip />
                    <Bar dataKey="sixes" fill="#14b8a6" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          </div>
        </>
      )}

      {leadersState.error ? <ErrorState message={leadersState.error} /> : null}
      {leadersState.loading && !data.top_batsmen.length && !data.top_bowlers.length ? <LeaderboardPanelsSkeleton /> : null}
      {data.top_batsmen.length || data.top_bowlers.length ? (
        <div className="panel-grid panel-grid-2">
          <Panel title="Top run engines" subtitle="The biggest run makers in the warehouse right now.">
            <div className="chart-box chart-box-short">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.top_batsmen.slice(0, 8)} layout="vertical">
                  <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                  <XAxis type="number" stroke="#9aa8c7" />
                  <YAxis
                    type="category"
                    dataKey="player_name"
                    width={isCompactLayout ? 96 : 150}
                    interval={0}
                    stroke="#9aa8c7"
                    tickFormatter={(value) => (isCompactLayout ? truncateChartLabel(value, 11) : truncateChartLabel(value, 18))}
                  />
                  <Tooltip />
                  <Bar dataKey="total_runs" fill="#f97316" radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <DataTable rows={data.top_batsmen} />
          </Panel>

          <Panel title="Top wicket brokers" subtitle="The wicket leaders with economy context beside them.">
            <div className="chart-box chart-box-short">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.top_bowlers.slice(0, 8)} layout="vertical">
                  <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                  <XAxis type="number" stroke="#9aa8c7" />
                  <YAxis
                    type="category"
                    dataKey="player_name"
                    width={isCompactLayout ? 96 : 150}
                    interval={0}
                    stroke="#9aa8c7"
                    tickFormatter={(value) => (isCompactLayout ? truncateChartLabel(value, 11) : truncateChartLabel(value, 18))}
                  />
                  <Tooltip />
                  <Bar dataKey="wickets" fill="#38bdf8" radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <DataTable rows={data.top_bowlers} />
          </Panel>
        </div>
      ) : null}
    </div>
  );
}

function BattingView(props: { seasons: string[] }) {
  const isCompactLayout = useViewportQuery("(max-width: 720px)");
  const [selectedSeasons, setSelectedSeasons] = useState<string[]>([]);
  const leaderboardState = useApi<{ leaderboard: TableRow[] }>(buildApiPath("/api/batting", { seasons: selectedSeasons }));
  const battingRows = leaderboardState.data?.leaderboard || [];
  const battingHighlights = battingRows.length
    ? [
        ["Top run engine", battingRows[0]?.player_name || "-"],
        ["Fastest bat", formatValue(pickMaxRow(battingRows, "strike_rate").strike_rate)],
        ["Biggest six burst", formatValue(pickMaxRow(battingRows, "sixes").sixes)],
        ["Tracked names", formatValue(battingRows.length)],
      ]
    : [];

  return (
    <div className="view-stack">
      <SectionHeader
        eyebrow="Run creation"
        title="Batting run engine board"
        subtitle="See who piles up runs, who scores fastest, and who keeps the boundary pressure high."
      />

      <Panel title="Season filters" subtitle="Trim the leaderboard to the seasons you want to compare.">
        <MultiChipFilter
          title="Seasons"
          items={props.seasons}
          selected={selectedSeasons}
          onToggle={(value) => setSelectedSeasons((current) => toggleInList(current, value))}
        />
      </Panel>

      {leaderboardState.loading ? <LoadingState /> : null}
      {leaderboardState.error ? <ErrorState message={leaderboardState.error} /> : null}
      {leaderboardState.data ? (
        <>
          <div className="metric-grid metric-grid-4">
            {battingHighlights.map(([label, value]) => (
              <article className="metric-card" key={String(label)}>
                <span>{label}</span>
                <strong>{String(value)}</strong>
              </article>
            ))}
          </div>

          <Panel title="Batting leaderboard" subtitle="Minimum 100 runs to keep the board honest.">
            <div className="chart-box">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={battingRows.slice(0, isCompactLayout ? 8 : 12)} layout="vertical">
                  <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                  <XAxis type="number" stroke="#9aa8c7" />
                  <YAxis
                    type="category"
                    dataKey="player_name"
                    width={isCompactLayout ? 96 : 156}
                    interval={0}
                    stroke="#9aa8c7"
                    tickFormatter={(value) => (isCompactLayout ? truncateChartLabel(value, 10) : truncateChartLabel(value, 18))}
                  />
                  <Tooltip />
                  <Bar dataKey="total_runs" fill="#f97316" radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <DataTable rows={battingRows} />
          </Panel>

          {isCompactLayout ? null : (
            <div className="panel-grid panel-grid-2 batting-support-grid">
              <Panel title="Strike rate versus output" subtitle="Runs on one axis, strike rate on the other, six power in the mix.">
                <div className="chart-box chart-box-short">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart>
                      <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                      <XAxis type="number" dataKey="total_runs" name="Runs" stroke="#9aa8c7" />
                      <YAxis type="number" dataKey="strike_rate" name="Strike rate" stroke="#9aa8c7" />
                      <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                      <Scatter data={battingRows} fill="#14b8a6" />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </Panel>

              <Panel title="Boundary pressure by batter" subtitle="Fours and sixes side by side for the top 10 volume scorers.">
                <div className="chart-box chart-box-short">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={battingRows.slice(0, 10)}>
                      <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                      <XAxis dataKey="player_name" stroke="#9aa8c7" hide />
                      <YAxis stroke="#9aa8c7" />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="fours" fill="#f97316" radius={[8, 8, 0, 0]} />
                      <Bar dataKey="sixes" fill="#38bdf8" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Panel>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

function BowlingView(props: { seasons: string[] }) {
  const isCompactLayout = useViewportQuery("(max-width: 720px)");
  const [selectedSeasons, setSelectedSeasons] = useState<string[]>([]);
  const [playerInput, setPlayerInput] = useState("");
  const [selectedPlayer, setSelectedPlayer] = useState("");

  const deferredPlayerInput = useDeferredValue(playerInput);
  const leaderboardState = useApi<{ leaderboard: TableRow[] }>(buildApiPath("/api/bowling", { seasons: selectedSeasons }));
  const playersState = useApi<{ items: string[] }>(
    deferredPlayerInput ? buildApiPath("/api/players", { search: deferredPlayerInput }) : null,
  );
  const profileState = useApi<{ player_name: string; seasons: TableRow[] }>(
    selectedPlayer ? buildApiPath("/api/bowling/profile", { player: selectedPlayer }) : null,
  );
  const bowlingRows = leaderboardState.data?.leaderboard || [];
  const bowlingHighlights = bowlingRows.length
    ? [
        ["Wicket leader", bowlingRows[0]?.player_name || "-"],
        ["Best economy", formatValue(pickMinRow(bowlingRows, "economy").economy)],
        ["Most dot balls", formatValue(pickMaxRow(bowlingRows, "dot_balls").dot_balls)],
        ["Leaderboard rows", formatValue(bowlingRows.length)],
      ]
    : [];

  return (
    <div className="view-stack">
      <SectionHeader
        eyebrow="Wicket pressure"
        title="Bowling efficiency patterns"
        subtitle="Track wicket volume, economy, and dot-ball squeeze across the loaded IPL seasons."
      />

      <Panel title="Filters" subtitle="Season slices and optional bowler focus.">
        <MultiChipFilter
          title="Seasons"
          items={props.seasons}
          selected={selectedSeasons}
          onToggle={(value) => setSelectedSeasons((current) => toggleInList(current, value))}
        />
        <div className="filter-group">
          <label className="field-label" htmlFor="bowling-player-search">Bowler spotlight</label>
          <p className="field-hint" id="bowling-player-search-hint">
            Type a few letters, then choose the bowler from the suggestion list.
          </p>
          <input
            aria-describedby="bowling-player-search-hint"
            aria-label="Search for a bowler"
            className="text-input"
            list="bowling-player-list"
            id="bowling-player-search"
            placeholder="Search a bowler"
            value={playerInput}
            onChange={(event) => {
              setPlayerInput(event.target.value);
              setSelectedPlayer(event.target.value);
            }}
          />
          <datalist id="bowling-player-list">
            {(playersState.data?.items || []).map((player) => (
              <option key={player} value={player} />
            ))}
          </datalist>
        </div>
      </Panel>

      {leaderboardState.loading ? <LoadingState /> : null}
      {leaderboardState.error ? <ErrorState message={leaderboardState.error} /> : null}
      {leaderboardState.data ? (
        <>
          <div className="metric-grid metric-grid-4">
            {bowlingHighlights.map(([label, value]) => (
              <article className="metric-card" key={String(label)}>
                <span>{label}</span>
                <strong>{String(value)}</strong>
              </article>
            ))}
          </div>

          <div className="panel-grid panel-grid-2">
            <Panel title="Bowling leaderboard" subtitle="Only bowlers with more than five wickets are shown.">
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={bowlingRows.slice(0, isCompactLayout ? 8 : 12)} layout="vertical">
                    <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                    <XAxis type="number" stroke="#9aa8c7" />
                    <YAxis
                      type="category"
                      dataKey="player_name"
                      width={isCompactLayout ? 88 : 140}
                      interval={0}
                      stroke="#9aa8c7"
                      tickFormatter={(value) => (isCompactLayout ? truncateChartLabel(value, 10) : truncateChartLabel(value, 18))}
                    />
                    <Tooltip />
                    <Bar dataKey="wickets" fill="#38bdf8" radius={[0, 8, 8, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <DataTable rows={bowlingRows} />
            </Panel>

            {isCompactLayout ? null : (
              <Panel title="Economy versus wickets" subtitle="Dot-ball count acts as hidden pressure context.">
                <div className="chart-box">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart>
                      <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                      <XAxis type="number" dataKey="wickets" stroke="#9aa8c7" />
                      <YAxis type="number" dataKey="economy" stroke="#9aa8c7" />
                      <Tooltip />
                      <Scatter data={bowlingRows} fill="#14b8a6" />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </Panel>
            )}
          </div>

          {isCompactLayout ? null : (
            <Panel title="Dot-ball pressure leaders" subtitle="Who squeezes scoring volume most often.">
              <div className="chart-box chart-box-short">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={bowlingRows.slice(0, 10)} layout="vertical">
                    <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                    <XAxis type="number" stroke="#9aa8c7" />
                    <YAxis type="category" dataKey="player_name" width={160} stroke="#9aa8c7" />
                    <Tooltip />
                    <Bar dataKey="dot_balls" fill="#f97316" radius={[0, 8, 8, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          )}
        </>
      ) : null}

      {selectedPlayer && profileState.data ? (
        <div className="panel-grid panel-grid-2">
          <Panel title={`${profileState.data.player_name} wickets by season`} subtitle="Wicket haul profile over time.">
            <div className="chart-box chart-box-short">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={profileState.data.seasons}>
                  <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                  <XAxis dataKey="season" stroke="#9aa8c7" />
                  <YAxis stroke="#9aa8c7" />
                  <Tooltip />
                  <Bar dataKey="wickets" fill="#38bdf8" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title={`${profileState.data.player_name} economy trend`} subtitle="Run control across seasons.">
            <div className="chart-box chart-box-short">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={profileState.data.seasons}>
                  <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                  <XAxis dataKey="season" stroke="#9aa8c7" />
                  <YAxis stroke="#9aa8c7" />
                  <Tooltip />
                  <Line type="monotone" dataKey="economy" stroke="#f97316" strokeWidth={3} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <DataTable rows={profileState.data.seasons} />
          </Panel>
        </div>
      ) : null}
    </div>
  );
}

function TeamsView(props: { teams: string[]; seasons: string[] }) {
  const [selectedTeam, setSelectedTeam] = useState("");
  const [selectedSeasons, setSelectedSeasons] = useState<string[]>([]);

  useEffect(() => {
    if (!selectedTeam && props.teams.length) {
      setSelectedTeam(props.teams[0]);
    }
  }, [props.teams, selectedTeam]);

  const overviewState = useApi<{ items: TableRow[] }>(buildApiPath("/api/teams/overview"));
  const detailState = useApi<{ season_performance: TableRow[]; toss_analysis: TableRow[] }>(
    selectedTeam ? buildApiPath("/api/teams/detail", { team: selectedTeam, seasons: selectedSeasons }) : null,
  );

  return (
    <div className="view-stack">
      <SectionHeader
        eyebrow="Franchise shape"
        title="Team performance fingerprints"
        subtitle="Win-rate posture, seasonal lifts, and toss choices for each IPL franchise."
      />

      <Panel title="Filters" subtitle="Focus on a single team and optional season slices.">
        <div className="filter-group">
          <label className="field-label" htmlFor="team-detail-select">Team</label>
          <select
            aria-label="Choose a team"
            className="select-input"
            id="team-detail-select"
            value={selectedTeam}
            onChange={(event) => setSelectedTeam(event.target.value)}
          >
            {props.teams.map((team) => (
              <option key={team} value={team}>
                {team}
              </option>
            ))}
          </select>
        </div>
        <MultiChipFilter
          title="Seasons"
          items={props.seasons}
          selected={selectedSeasons}
          onToggle={(value) => setSelectedSeasons((current) => toggleInList(current, value))}
        />
      </Panel>

      {overviewState.loading ? <LoadingState /> : null}
      {overviewState.error ? <ErrorState message={overviewState.error} /> : null}
      {overviewState.data ? (
        <Panel title="League-wide win percentage" subtitle="Franchise ranking across the current warehouse state.">
          <div
            className="chart-box"
            style={{ height: `${getVerticalChartHeight(overviewState.data.items.length, 420, 34)}px` }}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={overviewState.data.items} layout="vertical" margin={{ top: 8, right: 16, bottom: 8, left: 12 }}>
                <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                <XAxis type="number" stroke="#9aa8c7" />
                <YAxis type="category" dataKey="team_name" width={196} interval={0} stroke="#9aa8c7" tickFormatter={(value) => truncateChartLabel(value, 24)} />
                <Tooltip />
                <Bar dataKey="win_pct" fill="#14b8a6" radius={[0, 8, 8, 0]} barSize={22} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <DataTable rows={overviewState.data.items} />
        </Panel>
      ) : null}

      {selectedTeam && detailState.data ? (
        <div className="panel-grid panel-grid-2">
          <Panel title={`${selectedTeam} seasonal win shape`} subtitle="Wins and win percentage through time.">
            <div className="chart-box chart-box-short">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={detailState.data.season_performance}>
                  <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                  <XAxis dataKey="season" stroke="#9aa8c7" />
                  <YAxis stroke="#9aa8c7" />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="wins" stroke="#f97316" strokeWidth={3} />
                  <Line type="monotone" dataKey="win_pct" stroke="#38bdf8" strokeWidth={3} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <DataTable rows={detailState.data.season_performance} />
          </Panel>

          <Panel title={`${selectedTeam} toss posture`} subtitle="Decision split when winning the toss.">
            <div className="chart-box chart-box-short">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={detailState.data.toss_analysis}
                    dataKey="times"
                    nameKey="toss_decision"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    innerRadius={52}
                  >
                    {detailState.data.toss_analysis.map((entry, index) => (
                      <Cell key={`${entry.toss_decision}-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <DataTable rows={detailState.data.toss_analysis} />
          </Panel>
        </div>
      ) : null}
    </div>
  );
}

function VenuesView(props: { seasons: string[]; venues: string[] }) {
  const isCompactLayout = useViewportQuery("(max-width: 720px)");
  const [selectedSeasons, setSelectedSeasons] = useState<string[]>([]);
  const [selectedVenues, setSelectedVenues] = useState<string[]>([]);

  const venueState = useApi<{ venue_stats: TableRow[]; chase_stats: TableRow[] }>(
    buildApiPath("/api/venues", { seasons: selectedSeasons, venues: selectedVenues }),
  );

  return (
    <div className="view-stack">
      <SectionHeader
        eyebrow="Ground behavior"
        title="Venue scoring environments"
        subtitle="Surface tempo, boundary pressure, and chase success across IPL grounds."
      />

      <Panel title="Filters" subtitle="Narrow by season bands and specific venues.">
        <MultiChipFilter
          title="Seasons"
          items={props.seasons}
          selected={selectedSeasons}
          onToggle={(value) => setSelectedSeasons((current) => toggleInList(current, value))}
        />
        <MultiChipFilter
          title="Venues"
          items={props.venues.slice(0, 18)}
          selected={selectedVenues}
          onToggle={(value) => setSelectedVenues((current) => toggleInList(current, value))}
        />
      </Panel>

      {venueState.loading ? <LoadingState /> : null}
      {venueState.error ? <ErrorState message={venueState.error} /> : null}
      {venueState.data ? (
        <>
          <div className="panel-grid panel-grid-2">
            <Panel title="Average run rate by venue" subtitle="Minimum three matches required to appear.">
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={venueState.data.venue_stats.slice(0, 15)} layout="vertical">
                    <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                    <XAxis type="number" stroke="#9aa8c7" />
                    <YAxis type="category" dataKey="venue_name" width={196} interval={0} stroke="#9aa8c7" tickFormatter={(value) => truncateChartLabel(value, 24)} />
                    <Tooltip />
                    <Bar dataKey="avg_run_rate" fill="#f97316" radius={[0, 8, 8, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <DataTable rows={venueState.data.venue_stats} />
            </Panel>

            <Panel title="Chase win rate" subtitle="Normal-result matches only.">
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={venueState.data.chase_stats.slice(0, 15)}>
                    <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                    <XAxis dataKey="venue_name" stroke="#9aa8c7" hide />
                    <YAxis stroke="#9aa8c7" />
                    <Tooltip />
                    <Bar dataKey="chase_win_pct" fill="#14b8a6" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <DataTable rows={venueState.data.chase_stats} />
            </Panel>
          </div>

          {isCompactLayout ? null : (
            <Panel title="Run rate versus boundary rate" subtitle="Quick read on how explosive each ground plays.">
              <div className="chart-box chart-box-short">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart>
                    <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                    <XAxis type="number" dataKey="avg_run_rate" stroke="#9aa8c7" />
                    <YAxis type="number" dataKey="boundary_pct" stroke="#9aa8c7" />
                    <Tooltip />
                    <Scatter data={venueState.data.venue_stats} fill="#38bdf8" />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          )}
        </>
      ) : null}
    </div>
  );
}

function HeadToHeadView(props: { teams: string[]; seasons: string[] }) {
  const isCompactLayout = useViewportQuery("(max-width: 720px)");
  const [team1, setTeam1] = useState("");
  const [team2, setTeam2] = useState("");
  const [selectedSeasons, setSelectedSeasons] = useState<string[]>([]);

  useEffect(() => {
    if (!team1 && props.teams.length) {
      setTeam1(props.teams[0]);
    }
    if (!team2 && props.teams.length > 1) {
      setTeam2(props.teams[1]);
    }
  }, [props.teams, team1, team2]);

  const headToHeadState = useApi<{
    overall: TableRow;
    season_breakdown: TableRow[];
    performers: TableRow[];
  }>(
    team1 && team2 && team1 !== team2
      ? buildApiPath("/api/head-to-head", {
          team1,
          team2,
          seasons: selectedSeasons,
        })
      : null,
  );

  return (
    <div className="view-stack">
      <SectionHeader
        eyebrow="Rivalry lens"
        title="Direct matchup patterns"
        subtitle="Compare rivalry balance, seasonal splits, and batting leaders in the selected matchup."
      />

      <Panel title="Filters" subtitle="Choose two different teams and optional season filters.">
        <div className="dual-selects">
          <div className="filter-group">
            <label className="field-label" htmlFor="head-to-head-team-1">Team 1</label>
            <select
              aria-label="Choose the first team"
              className="select-input"
              id="head-to-head-team-1"
              value={team1}
              onChange={(event) => setTeam1(event.target.value)}
            >
              {props.teams.map((team) => (
                <option key={team} value={team}>
                  {team}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-group">
            <label className="field-label" htmlFor="head-to-head-team-2">Team 2</label>
            <select
              aria-label="Choose the second team"
              className="select-input"
              id="head-to-head-team-2"
              value={team2}
              onChange={(event) => setTeam2(event.target.value)}
            >
              {props.teams.map((team) => (
                <option key={team} value={team}>
                  {team}
                </option>
              ))}
            </select>
          </div>
        </div>
        <MultiChipFilter
          title="Seasons"
          items={props.seasons}
          selected={selectedSeasons}
          onToggle={(value) => setSelectedSeasons((current) => toggleInList(current, value))}
        />
      </Panel>

      {team1 === team2 ? <EmptyState message="Choose two different teams to unlock rivalry analysis." /> : null}
      {headToHeadState.loading ? <LoadingState /> : null}
      {headToHeadState.error ? <ErrorState message={headToHeadState.error} /> : null}
      {headToHeadState.data ? (
        <>
          <div className="metric-grid metric-grid-4">
            {Object.entries(headToHeadState.data.overall).slice(0, isCompactLayout ? 4 : undefined).map(([label, value]) => (
              <article className="metric-card" key={label}>
                <span>{label.replace(/_/g, " ")}</span>
                <strong>{formatValue(value)}</strong>
              </article>
            ))}
          </div>

          <div className="panel-grid panel-grid-2">
            <Panel title="Win split" subtitle={`${team1} versus ${team2} result mix.`} className="panel-compact">
              <div className="chart-box chart-box-compact">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        { name: team1, value: toChartNumber(headToHeadState.data.overall, "team1_wins") },
                        { name: team2, value: toChartNumber(headToHeadState.data.overall, "team2_wins") },
                        { name: "No result", value: toChartNumber(headToHeadState.data.overall, "no_result") },
                      ].filter((item) => item.value > 0)}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      innerRadius={52}
                    >
                      {PIE_COLORS.map((color, index) => (
                        <Cell key={`${color}-${index}`} fill={color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </Panel>

            <Panel title="Season breakdown" subtitle="How the rivalry swings by season.">
              <div className="chart-box chart-box-short">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={headToHeadState.data.season_breakdown}>
                    <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                    <XAxis dataKey="season" stroke="#9aa8c7" />
                    <YAxis stroke="#9aa8c7" />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="team1_wins" stroke="#f97316" strokeWidth={3} />
                    <Line type="monotone" dataKey="team2_wins" stroke="#14b8a6" strokeWidth={3} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <DataTable rows={headToHeadState.data.season_breakdown} />
            </Panel>
          </div>

          <Panel title="Top matchup batters" subtitle="Run leaders in the selected rivalry.">
            <div className="chart-box chart-box-short">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={headToHeadState.data.performers} layout="vertical">
                  <CartesianGrid stroke="#26354f" strokeDasharray="3 3" />
                  <XAxis type="number" stroke="#9aa8c7" />
                  <YAxis type="category" dataKey="player_name" width={170} interval={0} stroke="#9aa8c7" tickFormatter={(value) => truncateChartLabel(value, 20)} />
                  <Tooltip />
                  <Bar dataKey="runs" fill="#38bdf8" radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <DataTable rows={headToHeadState.data.performers} />
          </Panel>
        </>
      ) : null}
    </div>
  );
}

function InsightsLabView() {
  const isCompactLayout = useViewportQuery("(max-width: 720px)");
  const contextState = useApi<QueryEngineContext>(buildApiPath("/api/query-engine/context"));
  const [question, setQuestion] = useState("Show the top 10 batsmen by total runs with strike rate.");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [recentPrompts, setRecentPrompts] = useState<string[]>(() => readLocalCache<string[]>(QUERY_RECENT_KEY, []));
  const [successfulPrompts, setSuccessfulPrompts] = useState<string[]>(() => readLocalCache<string[]>(QUERY_SUCCESS_KEY, []));
  const [favoritePrompts, setFavoritePrompts] = useState<string[]>(() => readLocalCache<string[]>(QUERY_FAVORITES_KEY, []));
  const [promptFeedback, setPromptFeedback] = useState("Tap a prompt to preload it into the question box.");
  const [hasPerformedQuery, setHasPerformedQuery] = useState(false);
  const [queryState, setQueryState] = useState<ApiState<QueryEngineResult>>({
    data: null,
    loading: false,
    error: null,
  });
  const questionInputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    writeLocalCache(QUERY_RECENT_KEY, recentPrompts);
  }, [recentPrompts]);

  useEffect(() => {
    writeLocalCache(QUERY_SUCCESS_KEY, successfulPrompts);
  }, [successfulPrompts]);

  useEffect(() => {
    writeLocalCache(QUERY_FAVORITES_KEY, favoritePrompts);
  }, [favoritePrompts]);

  function handlePromptSelection(prompt: string, source: string) {
    setQuestion(prompt);
    setPromptFeedback(`${source} prompt loaded into the question box${isCompactLayout ? " above" : ""}.`);

    requestAnimationFrame(() => {
      const questionInput = questionInputRef.current;
      if (!questionInput) {
        return;
      }

      questionInput.scrollIntoView({ behavior: "smooth", block: "center" });
      questionInput.focus();
      questionInput.setSelectionRange(questionInput.value.length, questionInput.value.length);
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      return;
    }

    setHasPerformedQuery(true);
    setRecentPrompts((current) => rememberPrompt(current, trimmedQuestion));
    setSubmittedQuestion(trimmedQuestion);
    setPromptFeedback("Query submitted. Results will appear below when the warehouse responds.");
    setQueryState((current) => ({ ...current, loading: true, error: null }));

    try {
      const data = await postJson<QueryEngineResult>(buildApiPath("/api/query-engine"), {
        question: trimmedQuestion,
      });
      setSuccessfulPrompts((current) => rememberPrompt(current, trimmedQuestion));
      setPromptFeedback("Query completed. You can review the chart, SQL, and result table below.");
      setQueryState({ data, loading: false, error: null });
    } catch (error) {
      setPromptFeedback("The query failed. Review the error message and adjust the prompt.");
      setQueryState({
        data: null,
        loading: false,
        error: error instanceof Error ? error.message : "Query execution failed.",
      });
    }
  }

  const trimmedQuestion = question.trim();
  const isFavoritePrompt = trimmedQuestion ? favoritePrompts.includes(trimmedQuestion) : false;
  const visibleRecentPrompts = recentPrompts.slice(0, 3);

  return (
    <div className="view-stack">
      <SectionHeader
        eyebrow="Natural language SQL"
        title="Ask the warehouse in plain English"
        subtitle="Groq turns your cricket question into a grounded SQL query, executes it safely, and returns a chart-ready answer."
      />

      <Panel title="Prompt the analyst" subtitle="Ask for trends, rankings, comparisons, or season slices.">
        <form className="query-form" onSubmit={handleSubmit}>
          <label className="field-label" htmlFor="analytics-question">Ask a question</label>
          <p className="field-hint" id="analytics-question-hint">
            Use plain language. Example: Which venues have the highest average first innings score?
          </p>
          <textarea
            aria-describedby="analytics-question-hint"
            className="text-area text-input"
            id="analytics-question"
            placeholder="Example: Which venues have the highest average first innings score?"
            ref={questionInputRef}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <div className="button-row">
            <button className="primary-button" type="submit" disabled={queryState.loading}>
              {queryState.loading ? "Thinking…" : "Run query"}
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => {
                if (!trimmedQuestion) {
                  return;
                }
                setFavoritePrompts((current) => toggleInList(current, trimmedQuestion));
              }}
            >
              {isFavoritePrompt ? "Saved prompt" : "Save prompt"}
            </button>
            <span className="helper-copy">
              Read-only SQL only. Result sets are capped at {contextState.data?.row_limit || 200} rows.
            </span>
          </div>
        </form>

        <div className="prompt-feedback-status" role="status" aria-live="polite">
          {promptFeedback}
        </div>

        {contextState.data ? (
          <div className="prompt-memory-grid">
            <PromptChipSection title="Starter prompts" items={contextState.data.examples} activeValue={question} onSelect={handlePromptSelection} />
            {hasPerformedQuery ? (
              <PromptChipSection title="Saved prompts" items={favoritePrompts} activeValue={question} onSelect={handlePromptSelection} />
            ) : null}
            {hasPerformedQuery ? (
              <PromptChipSection title="Successful" items={successfulPrompts} activeValue={question} onSelect={handlePromptSelection} />
            ) : null}
            <PromptChipSection title="Recent" items={visibleRecentPrompts} activeValue={question} onSelect={handlePromptSelection} />
          </div>
        ) : null}
      </Panel>

      {queryState.loading ? <LoadingState /> : null}
      {queryState.error ? <ErrorState message={queryState.error} /> : null}

      {queryState.data ? (
        <>
          <div className="metric-grid metric-grid-4">
            <article className="metric-card">
              <span>Rows returned</span>
              <strong>{formatValue(queryState.data.row_count)}</strong>
            </article>
            <article className="metric-card">
              <span>Execution time</span>
              <strong>{queryState.data.execution_ms} ms</strong>
            </article>
            <article className="metric-card">
              <span>Columns</span>
              <strong>{formatValue(queryState.data.columns.length)}</strong>
            </article>
            <article className="metric-card">
              <span>Prompt</span>
              <strong>{submittedQuestion ? "Live" : "Ready"}</strong>
            </article>
          </div>

          {queryState.data.answer_text ? (
            <Panel
              title="Warehouse answer"
              subtitle={queryState.data.answer_source === "warehouse" ? "Derived directly from the loaded warehouse data." : "This response includes non-warehouse context."}
            >
              <div className="answer-callout">
                <strong>{queryState.data.answer_text}</strong>
              </div>
            </Panel>
          ) : null}

          <div className="panel-grid panel-grid-2">
            {queryState.data.answer_mode === "table" && queryState.data.row_count > 1 ? (
              <Panel title={queryState.data.title} subtitle={queryState.data.explanation}>
                <AutoInsightChart rows={queryState.data.rows} />
              </Panel>
            ) : (
              <Panel title={queryState.data.title} subtitle={queryState.data.explanation}>
                <div className="answer-callout answer-callout-muted">
                  <strong>
                    {queryState.data.answer_text || "This result is better read directly as text or a compact result set."}
                  </strong>
                </div>
              </Panel>
            )}

            <details className="details-card sql-details">
              <summary>Generated SQL</summary>
              <p className="details-copy">
                Expand to inspect the exact read-only SQL executed by the backend.
              </p>
              <pre className="code-block">{queryState.data.sql}</pre>
            </details>
          </div>

          {queryState.data.row_count > 0 ? (
            <Panel title="Result set" subtitle="Tabular answer returned by the warehouse.">
              <DataTable rows={queryState.data.rows} />
            </Panel>
          ) : null}
        </>
      ) : null}

      {contextState.data ? (
        <details className="details-card">
          <summary>Schema grounding used by the model</summary>
          <pre className="code-block schema-block">{contextState.data.schema_summary}</pre>
        </details>
      ) : null}
    </div>
  );
}

export default function App() {
  const [view, setView] = useState<ViewKey>("overview");
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const initialTheme = getDefaultTheme();
    applyDocumentTheme(initialTheme);
    return initialTheme;
  });
  const optionsState = useApi<ReferenceOptions>(buildApiPath("/api/reference/options"));

  useEffect(() => {
    applyDocumentTheme(theme);
    writeLocalCache(THEME_KEY, theme);
  }, [theme]);

  const activeNavItem = NAV_ITEMS.find((item) => item.key === view) || NAV_ITEMS[0];

  function toggleTheme() {
    setTheme((currentTheme) => (currentTheme === "dark" ? "light" : "dark"));
  }

  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to dashboard content
      </a>

      <div className="shell">
      <aside className="rail">
        <div className="brand-block">
          <span className="eyebrow">IPL Analytics Studio</span>
          <h1>Warehouse command deck</h1>
          <p>
            A modern front end for the IPL warehouse, tuned for fast reads on scoring,
            rivalry pressure, and franchise shape.
          </p>
        </div>

        <nav className="nav-stack">
          {NAV_ITEMS.map((item, index) => (
            <button
              key={item.key}
              aria-current={view === item.key ? "page" : undefined}
              aria-pressed={view === item.key}
              className={`nav-card ${view === item.key ? "nav-card-active" : ""}`}
              onClick={() => {
                startTransition(() => setView(item.key));
              }}
              type="button"
            >
              <span className="nav-index">0{index + 1}</span>
              <div>
                <strong>{item.label}</strong>
                <span>{item.eyebrow}</span>
              </div>
            </button>
          ))}
        </nav>

        <div className="rail-footer">
          <span>Data source</span>
          <strong>Cricsheet IPL JSON</strong>
          <small>Frontend port 5173 · API port 8000</small>
        </div>
      </aside>

      <main className="stage" id="main-content" tabIndex={-1}>
        <header className="hero">
          <div className="hero-head">
            <div className="hero-copy">
              <span className="eyebrow">IPL Analytics Studio</span>
              <h2>IPL analytics, tuned like a product.</h2>
            </div>
            <ThemeToggle className="hero-theme-toggle" theme={theme} onToggle={toggleTheme} />
          </div>
          <div className="hero-meta">
            <span className="hero-pill">{activeNavItem.label}</span>
            <span className="hero-pill hero-pill-muted">{activeNavItem.eyebrow}</span>
          </div>
          <p>
            Explore batting, bowling, venues, rivalries, and natural-language SQL in a cleaner
            React shell built for quick reading on desktop, tablet, and phone.
          </p>
        </header>

        {optionsState.loading ? (
          <LoadingState
            variant="boot"
            label="Preparing the warehouse shell"
            detail="Loading filters, warming the first screen, and staging visible components before deeper analytics hydrate."
            progressLabel="App boot"
          />
        ) : null}
        {optionsState.error ? <ErrorState message={optionsState.error} /> : null}
        {optionsState.data ? (
          <>
            {view === "overview" ? <OverviewView /> : null}
            {view === "batting" ? <BattingView seasons={optionsState.data.seasons} /> : null}
            {view === "bowling" ? <BowlingView seasons={optionsState.data.seasons} /> : null}
            {view === "teams" ? <TeamsView teams={optionsState.data.teams} seasons={optionsState.data.seasons} /> : null}
            {view === "venues" ? <VenuesView seasons={optionsState.data.seasons} venues={optionsState.data.venues} /> : null}
            {view === "head-to-head" ? <HeadToHeadView teams={optionsState.data.teams} seasons={optionsState.data.seasons} /> : null}
            {view === "insights-lab" ? <InsightsLabView /> : null}
          </>
        ) : null}
      </main>

      <nav aria-label="Mobile navigation" className="mobile-dock">
        {NAV_ITEMS.map((item, index) => (
          <button
            key={`mobile-${item.key}`}
            aria-current={view === item.key ? "page" : undefined}
            aria-pressed={view === item.key}
            className={`mobile-dock-button ${view === item.key ? "mobile-dock-button-active" : ""}`}
            onClick={() => {
              startTransition(() => setView(item.key));
            }}
            type="button"
          >
            <span className="mobile-dock-index">0{index + 1}</span>
            <strong>{item.mobileLabel}</strong>
          </button>
        ))}
      </nav>
      </div>
    </>
  );
}