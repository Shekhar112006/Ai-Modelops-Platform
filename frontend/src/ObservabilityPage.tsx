import { useCallback, useEffect, useState } from 'react'
import './ObservabilityPage.css'

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')

type ServiceState = 'checking' | 'healthy' | 'unavailable'

type MetricSample = {
  name: string
  labels: Record<string, string>
  value: number
}

type ServiceHealth = {
  name: string
  detail: string
  state: ServiceState
}

type ObservationData = {
  totalRequests: number
  totalErrors: number
  predictionSuccesses: number
  predictionFailures: number
  predictionTotal: number
  averageLatencyMs: number | null
  requestCounts: Array<{ method: string; count: number }>
  services: ServiceHealth[]
  metricsAvailable: boolean
  metricsError: string | null
  refreshedAt: Date | null
}

const initialData: ObservationData = {
  totalRequests: 0,
  totalErrors: 0,
  predictionSuccesses: 0,
  predictionFailures: 0,
  predictionTotal: 0,
  averageLatencyMs: null,
  requestCounts: [],
  services: [
    { name: 'Platform API', detail: 'Application liveness', state: 'checking' },
    { name: 'PostgreSQL', detail: 'Database readiness', state: 'checking' },
    { name: 'Prometheus metrics', detail: 'Application instrumentation', state: 'checking' },
  ],
  metricsAvailable: false,
  metricsError: null,
  refreshedAt: null,
}

function parsePrometheus(text: string): MetricSample[] {
  const samples: MetricSample[] = []

  for (const line of text.split('\n')) {
    const trimmed = line.trim()

    if (!trimmed || trimmed.startsWith('#')) continue

    const match = trimmed.match(
      /^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(.*)\})?\s+([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|NaN|[+-]?Inf)(?:\s+\d+)?$/,
    )

    if (!match) continue

    const [, name, labelText = '', rawValue] = match
    const labels: Record<string, string> = {}

    const labelPattern = /([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\.|[^"\\])*)"/g

    for (const labelMatch of labelText.matchAll(labelPattern)) {
      labels[labelMatch[1]] = labelMatch[2]
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, '\\')
        .replace(/\\n/g, '\n')
    }

    const value = Number(rawValue)

    if (Number.isFinite(value)) {
      samples.push({ name, labels, value })
    }
  }

  return samples
}

function sumMetric(
  samples: MetricSample[],
  name: string,
  predicate: (sample: MetricSample) => boolean = () => true,
): number {
  return samples
    .filter((sample) => sample.name === name && predicate(sample))
    .reduce((total, sample) => total + sample.value, 0)
}

function formatCount(value: number): string {
  return Math.round(value).toLocaleString()
}

function formatLatency(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '—'
  return `${value.toFixed(2)} ms`
}

function formatTime(value: Date | null): string {
  if (!value) return 'Not refreshed yet'
  return value.toLocaleTimeString()
}

function StatusBadge({ state }: { state: ServiceState }) {
  const label = state === 'healthy'
    ? 'Healthy'
    : state === 'unavailable'
      ? 'Unavailable'
      : 'Checking'

  return (
    <span className={`obs-status obs-status-${state}`}>
      <span className="obs-status-dot" />
      {label}
    </span>
  )
}

function MetricCard({
  label,
  value,
  note,
  icon,
}: {
  label: string
  value: string
  note: string
  icon: string
}) {
  return (
    <article className="obs-metric-card">
      <div className="obs-metric-top">
        <span>{label}</span>
        <span className="obs-metric-icon" aria-hidden="true">{icon}</span>
      </div>
      <strong className="obs-metric-value">{value}</strong>
      <span className="obs-metric-note">{note}</span>
    </article>
  )
}

function ObservabilityPage() {
  const [data, setData] = useState<ObservationData>(initialData)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [pageError, setPageError] = useState<string | null>(null)

  const refresh = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true)

    try {
      const [liveResult, readyResult, metricsResult] = await Promise.allSettled([
        fetch(`${API_BASE_URL}/health/live`, { cache: 'no-store' }),
        fetch(`${API_BASE_URL}/health/ready`, { cache: 'no-store' }),
        fetch(`${API_BASE_URL}/metrics`, { cache: 'no-store' }),
      ])

      const liveHealthy =
        liveResult.status === 'fulfilled' && liveResult.value.ok

      const databaseHealthy =
        readyResult.status === 'fulfilled' && readyResult.value.ok

      let samples: MetricSample[] = []
      let metricsAvailable = false
      let metricsError: string | null = null

      if (metricsResult.status === 'fulfilled' && metricsResult.value.ok) {
        try {
          samples = parsePrometheus(await metricsResult.value.text())
          metricsAvailable = true
        } catch {
          metricsError = 'The metrics response could not be read.'
        }
      } else {
        metricsError = metricsResult.status === 'rejected'
          ? 'Could not connect to the metrics endpoint.'
          : `Metrics endpoint returned HTTP ${metricsResult.value.status}.`
      }

      const totalRequests = sumMetric(samples, 'modelops_http_requests_total')
      const totalErrors = sumMetric(samples, 'modelops_http_request_errors_total')

      const predictionFilter = (sample: MetricSample) =>
        sample.labels.service === 'modelops-api'

      const predictionSuccesses = sumMetric(
        samples,
        'modelops_predictions_total',
        (sample) => predictionFilter(sample) && sample.labels.outcome === 'success',
      )

      const predictionFailures = sumMetric(
        samples,
        'modelops_predictions_total',
        (sample) =>
          predictionFilter(sample) &&
          sample.labels.outcome !== 'success',
      )

      const predictionTotal = predictionSuccesses + predictionFailures

      const predictionDurationCount = sumMetric(
        samples,
        'modelops_http_request_duration_seconds_count',
        (sample) =>
          sample.labels.service === 'modelops-api' &&
          sample.labels.method === 'POST' &&
          sample.labels.path === '/predictions',
      )

      const predictionDurationSum = sumMetric(
        samples,
        'modelops_http_request_duration_seconds_sum',
        (sample) =>
          sample.labels.service === 'modelops-api' &&
          sample.labels.method === 'POST' &&
          sample.labels.path === '/predictions',
      )

      const requestCounts = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']
        .map((method) => ({
          method,
          count: sumMetric(
            samples,
            'modelops_http_requests_total',
            (sample) =>
              sample.labels.service === 'modelops-api' &&
              sample.labels.method === method,
          ),
        }))
        .filter((item) => item.count > 0)

      setData({
        totalRequests,
        totalErrors,
        predictionSuccesses,
        predictionFailures,
        predictionTotal,
        averageLatencyMs: predictionDurationCount > 0
          ? (predictionDurationSum / predictionDurationCount) * 1000
          : null,
        requestCounts,
        services: [
          {
            name: 'Platform API',
            detail: 'Application liveness endpoint',
            state: liveHealthy ? 'healthy' : 'unavailable',
          },
          {
            name: 'PostgreSQL',
            detail: 'Database readiness endpoint',
            state: readyResult.status === 'rejected' ||
              (readyResult.status === 'fulfilled' && !readyResult.value.ok)
              ? 'unavailable'
              : 'healthy',
          },
          {
            name: 'Prometheus metrics',
            detail: 'HTTP and prediction instrumentation',
            state: metricsAvailable ? 'healthy' : 'unavailable',
          },
        ],
        metricsAvailable,
        metricsError,
        refreshedAt: new Date(),
      })

      setPageError(
        !liveHealthy && !databaseHealthy
          ? 'The API and database readiness checks are unavailable.'
          : null,
      )
    } catch {
      setPageError('Unable to refresh observability data.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void refresh()

    const intervalId = window.setInterval(() => {
      void refresh()
    }, 15000)

    return () => window.clearInterval(intervalId)
  }, [refresh])

  const errorRate = data.totalRequests > 0
    ? (data.totalErrors / data.totalRequests) * 100
    : 0

  return (
    <div className="observability-page">
      <section className="obs-toolbar">
        <div>
          <p className="obs-eyebrow">LIVE PLATFORM TELEMETRY</p>
          <h2>System observability</h2>
          <p className="obs-description">
            Monitor API health, HTTP traffic, prediction outcomes, and request latency.
          </p>
        </div>
        <div className="obs-refresh-controls">
          <span className="obs-updated">
            Updated {formatTime(data.refreshedAt)}
          </span>
          <button
            className="obs-refresh-button"
            type="button"
            onClick={() => void refresh(true)}
            disabled={refreshing}
          >
            {refreshing ? 'Refreshing…' : '↻ Refresh'}
          </button>
        </div>
      </section>

      {pageError && (
        <div className="obs-alert" role="alert">{pageError}</div>
      )}

      <section className="obs-section">
        <div className="obs-section-heading">
          <div>
            <h3>Service health</h3>
            <p>Current endpoint checks; these do not replace full infrastructure monitoring.</p>
          </div>
          <span className="obs-auto-refresh">AUTO-REFRESH · 15 SEC</span>
        </div>

        <div className="obs-service-grid">
          {data.services.map((service) => (
            <article className="obs-service-card" key={service.name}>
              <div className="obs-service-symbol" aria-hidden="true">
                {service.name === 'Platform API' ? '⌘'
                  : service.name === 'PostgreSQL' ? '▤' : '◉'}
              </div>
              <div className="obs-service-copy">
                <strong>{service.name}</strong>
                <span>{service.detail}</span>
              </div>
              <StatusBadge state={service.state} />
            </article>
          ))}
        </div>
      </section>

      <section className="obs-section">
        <div className="obs-section-heading">
          <div>
            <h3>Request overview</h3>
            <p>Cumulative metrics since the API process started.</p>
          </div>
          {loading && <span className="obs-muted">Loading metrics…</span>}
        </div>

        <div className="obs-metrics-grid">
          <MetricCard
            label="HTTP requests"
            value={data.metricsAvailable ? formatCount(data.totalRequests) : '—'}
            note="All recorded HTTP methods"
            icon="⇄"
          />
          <MetricCard
            label="HTTP errors"
            value={data.metricsAvailable ? formatCount(data.totalErrors) : '—'}
            note="Responses with status 400 or higher"
            icon="!"
          />
          <MetricCard
            label="HTTP error rate"
            value={data.metricsAvailable ? `${errorRate.toFixed(2)}%` : '—'}
            note="Errors divided by recorded requests"
            icon="%"
          />
          <MetricCard
            label="Average prediction request"
            value={data.metricsAvailable ? formatLatency(data.averageLatencyMs) : '—'}
            note="FastAPI duration for POST /predictions"
            icon="◷"
          />
        </div>
      </section>

      <section className="obs-detail-grid">
        <article className="panel obs-panel">
          <div className="panel-header">
            <div>
              <h3>HTTP request distribution</h3>
              <p>Requests grouped by method</p>
            </div>
            <span className="obs-panel-icon">⇄</span>
          </div>

          {data.metricsAvailable && data.requestCounts.length > 0 ? (
            <div className="obs-method-list">
              {data.requestCounts.map((item) => {
                const width = data.totalRequests > 0
                  ? Math.min((item.count / data.totalRequests) * 100, 100)
                  : 0

                return (
                  <div className="obs-method-row" key={item.method}>
                    <div className="obs-method-label">
                      <code>{item.method}</code>
                      <strong>{formatCount(item.count)}</strong>
                    </div>
                    <div className="obs-bar-track">
                      <div className="obs-bar-fill" style={{ width: `${width}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="obs-empty">
              {data.metricsAvailable
                ? 'No HTTP requests have been recorded yet.'
                : 'HTTP metrics are currently unavailable.'}
            </div>
          )}
        </article>

        <article className="panel obs-panel">
          <div className="panel-header">
            <div>
              <h3>Prediction outcomes</h3>
              <p>Recorded outcomes from the prediction API</p>
            </div>
            <span className="obs-panel-icon">⌁</span>
          </div>

          {data.metricsAvailable ? (
            <>
              <div className="obs-prediction-total">
                <strong>{formatCount(data.predictionTotal)}</strong>
                <span>recorded outcomes</span>
              </div>
              <div className="obs-outcome-row">
                <span><i className="obs-outcome-dot obs-outcome-success" /> Successful</span>
                <strong>{formatCount(data.predictionSuccesses)}</strong>
              </div>
              <div className="obs-outcome-row">
                <span><i className="obs-outcome-dot obs-outcome-failure" /> Failed</span>
                <strong>{formatCount(data.predictionFailures)}</strong>
              </div>
              {data.predictionTotal === 0 && (
                <p className="obs-footnote">
                  No prediction outcomes have been recorded since this API process started.
                </p>
              )}
            </>
          ) : (
            <div className="obs-empty">Prediction metrics are currently unavailable.</div>
          )}
        </article>
      </section>

      <section className="obs-source-note">
        <span className="obs-source-icon">ⓘ</span>
        <p>
          {data.metricsAvailable
            ? 'Metrics are read directly from the API Prometheus endpoint. Counters reset when the API process restarts; historical charts require a time-series collector.'
            : data.metricsError || 'Waiting for metrics from the API.'}
        </p>
      </section>
    </div>
  )
}

export default ObservabilityPage
