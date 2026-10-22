import { useState } from 'react'
import './PredictionsPage.css'

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')

const FEATURE_COUNT = 10

interface PredictionResult {
  status: string
  model_name: string
  model_version: string
  prediction: unknown[]
  latency_ms: number
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : 'An unexpected error occurred.'
}

async function getResponseError(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: unknown }

    if (typeof body.detail === 'string') {
      return body.detail
    }
  } catch {
    // The server may return a non-JSON response.
  }

  return `Request failed with HTTP ${response.status}.`
}

function PredictionsPage() {
  const [features, setFeatures] = useState<string[]>(
    Array(FEATURE_COUNT).fill('0') as string[],
  )
  const [result, setResult] = useState<PredictionResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function updateFeature(index: number, value: string) {
    setFeatures((current) =>
      current.map((feature, position) =>
        position === index ? value : feature,
      ),
    )
    setResult(null)
    setError('')
  }

  function resetFeatures() {
    setFeatures(Array(FEATURE_COUNT).fill('0') as string[])
    setResult(null)
    setError('')
  }

  async function runPrediction() {
    if (loading) return

    const invalidIndex = features.findIndex(
      (value) => value.trim() === '' || !Number.isFinite(Number(value)),
    )

    if (invalidIndex !== -1) {
      setError(`Enter a valid number for Feature ${invalidIndex + 1}.`)
      setResult(null)
      return
    }

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/predictions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          features: features.map((value) => Number(value)),
        }),
      })

      if (!response.ok) {
        throw new Error(await getResponseError(response))
      }

      const data: unknown = await response.json()

      if (
        typeof data !== 'object' ||
        data === null ||
        !('status' in data) ||
        !('model_name' in data) ||
        !('model_version' in data) ||
        !('prediction' in data) ||
        !('latency_ms' in data) ||
        typeof data.status !== 'string' ||
        typeof data.model_name !== 'string' ||
        typeof data.model_version !== 'string' ||
        !Array.isArray(data.prediction) ||
        typeof data.latency_ms !== 'number'
      ) {
        throw new Error('The API returned an unexpected prediction response.')
      }

      setResult(data as PredictionResult)
    } catch (err) {
      setError(
        `${getErrorMessage(err)} Check that the API and model server are running.`,
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="predictions-page">
      <header className="predictions-intro">
        <div>
          <p className="predictions-eyebrow">MODEL INFERENCE</p>
          <h2>Prediction Playground</h2>
          <p>
            Submit a feature vector to the deployed model and inspect the
            actual inference response.
          </p>
        </div>

        <span className="predictions-live-badge">
          <span aria-hidden="true" />
          API inference
        </span>
      </header>

      <div className="predictions-notice">
        <strong>Input format</strong>
        <span>
          This model expects exactly 10 numeric features. The feature names
          are positional because domain-specific feature labels are not
          currently defined by the API.
        </span>
      </div>

      <div className="predictions-workspace">
        <section className="predictions-panel">
          <div className="predictions-panel-heading">
            <div>
              <h3>Input features</h3>
              <p>Enter the values to send to the model.</p>
            </div>
            <span className="predictions-count">10 FEATURES</span>
          </div>

          <div className="predictions-feature-grid">
            {features.map((value, index) => (
              <label className="predictions-feature" key={index}>
                <span>
                  Feature {index + 1}
                  <small>F{index + 1}</small>
                </span>
                <input
                  type="number"
                  step="any"
                  value={value}
                  onChange={(event) =>
                    updateFeature(index, event.target.value)
                  }
                  aria-label={`Feature ${index + 1}`}
                  disabled={loading}
                />
              </label>
            ))}
          </div>

          <div className="predictions-actions">
            <button
              className="predictions-button predictions-button-secondary"
              type="button"
              onClick={resetFeatures}
              disabled={loading}
            >
              Reset values
            </button>
            <button
              className="predictions-button predictions-button-primary"
              type="button"
              onClick={() => void runPrediction()}
              disabled={loading}
            >
              {loading ? 'Running inference…' : 'Run prediction →'}
            </button>
          </div>
        </section>

        <section className="predictions-panel predictions-result-panel">
          <div className="predictions-panel-heading">
            <div>
              <h3>Prediction result</h3>
              <p>Output returned by the live model endpoint.</p>
            </div>
            <span className={`predictions-result-status ${loading ? 'is-running' : result ? 'is-success' : 'is-idle'}`}>
              {loading ? 'RUNNING' : result ? 'SUCCESS' : 'READY'}
            </span>
          </div>

          {loading ? (
            <div className="predictions-empty" role="status">
              <span className="predictions-spinner" />
              <strong>Running model inference</strong>
              <p>Waiting for the model server to return its prediction.</p>
            </div>
          ) : error ? (
            <div className="predictions-error" role="alert">
              <strong>Prediction failed</strong>
              <p>{error}</p>
            </div>
          ) : result ? (
            <div className="predictions-result-content" aria-live="polite">
              <span className="predictions-result-label">MODEL OUTPUT</span>
              <div className="predictions-output">
                <code>{JSON.stringify(result.prediction)}</code>
              </div>

              <div className="predictions-metadata">
                <div>
                  <span>Model</span>
                  <strong>{result.model_name}</strong>
                </div>
                <div>
                  <span>Version</span>
                  <strong>v{result.model_version}</strong>
                </div>
                <div>
                  <span>Latency</span>
                  <strong>{result.latency_ms.toFixed(2)} ms</strong>
                </div>
                <div>
                  <span>Status</span>
                  <strong className="predictions-success-text">
                    {result.status}
                  </strong>
                </div>
              </div>

              <p className="predictions-result-note">
                This is the model's raw output. Its business meaning depends
                on the model's documented class mapping.
              </p>
            </div>
          ) : (
            <div className="predictions-empty">
              <span className="predictions-empty-icon" aria-hidden="true">
                ƒ(x)
              </span>
              <strong>No prediction yet</strong>
              <p>
                Enter feature values and run a prediction to see the result
                here.
              </p>
            </div>
          )}
        </section>
      </div>

      <footer className="predictions-footer">
        <span>Endpoint</span>
        <code>POST /api/v1/predictions</code>
        <span className="predictions-footer-separator">·</span>
        <span>10 numeric features required</span>
      </footer>
    </section>
  )
}

export default PredictionsPage
