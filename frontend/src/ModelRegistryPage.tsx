import { useCallback, useEffect, useState } from 'react'
import './ModelRegistryPage.css'

interface ModelVersion {
  name: string
  version: string
  status: string
  run_id: string | null
  source: string | null
  description: string | null
  tags: Record<string, string>
  creation_timestamp: number | null
  last_updated_timestamp: number | null
}

interface RegisteredModel {
  name: string
  description: string | null
  tags: Record<string, string>
  aliases: Record<string, string>
  latest_versions: ModelVersion[]
}

interface ModelListResponse {
  models: RegisteredModel[]
  total: number
}

interface VersionListResponse {
  model_name: string
  versions: ModelVersion[]
  total: number
}

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : 'An unexpected error occurred.'
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: unknown }

    if (typeof body.detail === 'string') {
      return body.detail
    }
  } catch {
    // Retain the HTTP status when the response is not JSON.
  }

  return `Request failed with HTTP ${response.status}.`
}

function formatTimestamp(value: number | null): string {
  if (value === null) return 'Unknown'

  const date = new Date(value)

  return Number.isNaN(date.getTime())
    ? 'Unknown'
    : date.toLocaleString()
}

function statusClass(status: string): string {
  return status.toLowerCase().replace(/[^a-z0-9-]/g, '-')
}

function ModelRegistryPage() {
  const [models, setModels] = useState<RegisteredModel[]>([])
  const [selectedModelName, setSelectedModelName] = useState('')
  const [versions, setVersions] = useState<ModelVersion[]>([])
  const [selectedVersion, setSelectedVersion] = useState<ModelVersion | null>(null)
  const [loadingModels, setLoadingModels] = useState(true)
  const [loadingVersions, setLoadingVersions] = useState(false)
  const [loadingDetails, setLoadingDetails] = useState(false)
  const [error, setError] = useState('')
  const [versionError, setVersionError] = useState('')
  const [detailsError, setDetailsError] = useState('')

  const loadModels = useCallback(async () => {
    setLoadingModels(true)
    setError('')

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/registry/models`)

      if (!response.ok) {
        throw new Error(await readError(response))
      }

      const data = await response.json() as ModelListResponse

      if (!Array.isArray(data.models)) {
        throw new Error('The API returned an unexpected model list.')
      }

      setModels(data.models)

      setSelectedModelName((current) => {
        if (current && data.models.some((model) => model.name === current)) {
          return current
        }

        return data.models[0]?.name ?? ''
      })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoadingModels(false)
    }
  }, [])

  useEffect(() => {
    void loadModels()
  }, [loadModels])

  useEffect(() => {
    if (!selectedModelName) {
      setVersions([])
      setSelectedVersion(null)
      setLoadingVersions(false)
      return
    }

    let cancelled = false

    async function loadVersions() {
      setLoadingVersions(true)
      setVersionError('')
      setDetailsError('')
      setSelectedVersion(null)

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/v1/registry/models/${encodeURIComponent(selectedModelName)}/versions`,
        )

        if (!response.ok) {
          throw new Error(await readError(response))
        }

        const data = await response.json() as VersionListResponse

        if (!Array.isArray(data.versions)) {
          throw new Error('The API returned an unexpected version list.')
        }

        if (!cancelled) {
          setVersions(data.versions)
        }
      } catch (err) {
        if (!cancelled) {
          setVersionError(errorMessage(err))
          setVersions([])
        }
      } finally {
        if (!cancelled) {
          setLoadingVersions(false)
        }
      }
    }

    void loadVersions()

    return () => {
      cancelled = true
    }
  }, [selectedModelName])

  async function showVersionDetails(version: ModelVersion) {
    setSelectedVersion(null)
    setDetailsError('')
    setLoadingDetails(true)

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/registry/models/${encodeURIComponent(version.name)}/versions/${encodeURIComponent(version.version)}`,
      )

      if (!response.ok) {
        throw new Error(await readError(response))
      }

      const data = await response.json() as ModelVersion
      setSelectedVersion(data)
    } catch (err) {
      setDetailsError(errorMessage(err))
    } finally {
      setLoadingDetails(false)
    }
  }

  const selectedModel = models.find(
    (model) => model.name === selectedModelName,
  )

  const candidateVersion = selectedModel?.aliases.candidate

  return (
    <section className="registry-page">
      <div className="registry-toolbar">
        <div className="registry-summary">
          <strong>{loadingModels ? '…' : models.length}</strong>
          <span>registered models</span>
        </div>

        <button
          className="registry-button registry-button-secondary"
          type="button"
          onClick={() => void loadModels()}
          disabled={loadingModels}
        >
          {loadingModels ? 'Refreshing…' : '↻ Refresh registry'}
        </button>
      </div>

      {error && (
        <div className="registry-alert registry-alert-error" role="alert">
          <strong>Unable to load registry</strong>
          <span>{error}</span>
          <button type="button" onClick={() => void loadModels()}>
            Retry
          </button>
        </div>
      )}

      {!error && !loadingModels && models.length === 0 && (
        <div className="registry-empty">
          <span className="registry-empty-icon" aria-hidden="true">◈</span>
          <h2>No registered models</h2>
          <p>Models will appear here after they are registered with MLflow.</p>
        </div>
      )}

      {models.length > 0 && (
        <>
          <div className="registry-model-layout">
            <section className="registry-panel registry-model-panel">
              <div className="registry-panel-header">
                <div>
                  <h2>Registered models</h2>
                  <p>Models tracked by MLflow</p>
                </div>
              </div>

              <label className="registry-select-label" htmlFor="registry-model">
                Select model
              </label>

              <select
                id="registry-model"
                className="registry-select"
                value={selectedModelName}
                onChange={(event) => setSelectedModelName(event.target.value)}
              >
                {models.map((model) => (
                  <option key={model.name} value={model.name}>
                    {model.name}
                  </option>
                ))}
              </select>

              {selectedModel && (
                <div className="registry-model-summary">
                  <div className="registry-model-icon" aria-hidden="true">◈</div>
                  <h3>{selectedModel.name}</h3>
                  <p>{selectedModel.description || 'No description provided.'}</p>

                  <div className="registry-summary-stat">
                    <span>Latest version</span>
                    <strong>
                      {selectedModel.latest_versions[0]?.version ?? '—'}
                    </strong>
                  </div>

                  <div className="registry-summary-stat">
                    <span>Candidate alias</span>
                    <strong>
                      {candidateVersion ? `Version ${candidateVersion}` : 'Not assigned'}
                    </strong>
                  </div>

                  <div className="registry-summary-stat">
                    <span>Versions available</span>
                    <strong>{versions.length}</strong>
                  </div>

                  <div className="registry-tag-list">
                    {selectedModel.tags &&
                      Object.entries(selectedModel.tags).map(([key, value]) => (
                        <span className="registry-tag" key={key}>
                          {key}: {value}
                        </span>
                      ))}
                  </div>
                </div>
              )}
            </section>

            <section className="registry-panel registry-versions-panel">
              <div className="registry-panel-header">
                <div>
                  <h2>Version history</h2>
                  <p>Newest versions appear first</p>
                </div>
                <span className="registry-count">{versions.length} versions</span>
              </div>

              {loadingVersions && (
                <p className="registry-message">Loading model versions…</p>
              )}

              {versionError && (
                <div className="registry-alert registry-alert-error" role="alert">
                  {versionError}
                </div>
              )}

              {!loadingVersions && !versionError && versions.length === 0 && (
                <p className="registry-message">No versions found for this model.</p>
              )}

              {versions.length > 0 && (
                <div className="registry-table-wrap">
                  <table className="registry-table">
                    <thead>
                      <tr>
                        <th>Version</th>
                        <th>Status</th>
                        <th>Validation</th>
                        <th>Created</th>
                        <th>Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {versions.map((version) => (
                        <tr key={`${version.name}-${version.version}`}>
                          <td>
                            <strong>v{version.version}</strong>
                            {candidateVersion === version.version && (
                              <span className="registry-candidate">Candidate</span>
                            )}
                          </td>
                          <td>
                            <span className={`registry-status status-${statusClass(version.status)}`}>
                              {version.status}
                            </span>
                          </td>
                          <td>
                            <span className={`registry-status status-${statusClass(version.tags.validation_status ?? 'unknown')}`}>
                              {version.tags.validation_status ?? 'Unknown'}
                            </span>
                          </td>
                          <td>{formatTimestamp(version.creation_timestamp)}</td>
                          <td>
                            <button
                              className="registry-link-button"
                              type="button"
                              onClick={() => void showVersionDetails(version)}
                            >
                              View details →
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>

          {(loadingDetails || detailsError || selectedVersion) && (
            <section className="registry-panel registry-details-panel">
              <div className="registry-panel-header">
                <div>
                  <h2>Version details</h2>
                  <p>
                    {selectedVersion
                      ? `${selectedVersion.name} · Version ${selectedVersion.version}`
                      : 'Details for the selected version'}
                  </p>
                </div>
                {selectedVersion && (
                  <button
                    className="registry-button registry-button-secondary"
                    type="button"
                    onClick={() => setSelectedVersion(null)}
                  >
                    Close
                  </button>
                )}
              </div>

              {loadingDetails && (
                <p className="registry-message">Loading version details…</p>
              )}

              {detailsError && (
                <div className="registry-alert registry-alert-error" role="alert">
                  {detailsError}
                </div>
              )}

              {selectedVersion && !loadingDetails && (
                <div className="registry-details-grid">
                  <div>
                    <span>Version</span>
                    <strong>{selectedVersion.version}</strong>
                  </div>
                  <div>
                    <span>MLflow status</span>
                    <strong>{selectedVersion.status}</strong>
                  </div>
                  <div>
                    <span>Run ID</span>
                    <code>{selectedVersion.run_id || 'Not available'}</code>
                  </div>
                  <div>
                    <span>Source</span>
                    <code>{selectedVersion.source || 'Not available'}</code>
                  </div>
                  <div>
                    <span>Created</span>
                    <strong>{formatTimestamp(selectedVersion.creation_timestamp)}</strong>
                  </div>
                  <div>
                    <span>Last updated</span>
                    <strong>{formatTimestamp(selectedVersion.last_updated_timestamp)}</strong>
                  </div>
                  <div className="registry-detail-tags">
                    <span>Version tags</span>
                    <div className="registry-tag-list">
                      {Object.entries(selectedVersion.tags).map(([key, value]) => (
                        <span className="registry-tag" key={key}>
                          {key}: {value}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </section>
          )}
        </>
      )}
    </section>
  )
}

export default ModelRegistryPage
