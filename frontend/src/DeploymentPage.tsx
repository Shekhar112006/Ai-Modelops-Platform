import { useCallback, useEffect, useState } from 'react'
import './DeploymentPage.css'

interface Project {
  id: string
  name: string
  description: string | null
  status: string
  created_at: string
}

interface Deployment {
  id: string
  project_id: string
  model_name: string
  model_version: string
  environment: string
  status: string
  traffic_percentage: number
  model_endpoint: string | null
  created_at: string
  updated_at: string
  started_at: string | null
  completed_at: string | null
}

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')

function getErrorMessage(error: unknown): string {
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
    // Use the HTTP status if the response is not JSON.
  }

  return `Request failed with HTTP ${response.status}.`
}

function formatDate(value: string | null): string {
  if (!value) return '—'

  const date = new Date(value)

  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleString()
}

function statusClass(status: string): string {
  return status.toLowerCase().replace(/[^a-z0-9-]/g, '-')
}

function DeploymentPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [deployments, setDeployments] = useState<Deployment[]>([])
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [loadingDeployments, setLoadingDeployments] = useState(false)
  const [projectError, setProjectError] = useState('')
  const [deploymentError, setDeploymentError] = useState('')

  const loadProjects = useCallback(async () => {
    setLoadingProjects(true)
    setProjectError('')

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/projects`)

      if (!response.ok) {
        throw new Error(await readError(response))
      }

      const data: unknown = await response.json()

      if (!Array.isArray(data)) {
        throw new Error('The API returned an unexpected project list.')
      }

      const loadedProjects = data as Project[]
      setProjects(loadedProjects)

      setSelectedProjectId((current) => {
        if (current && loadedProjects.some((p) => p.id === current)) {
          return current
        }

        return loadedProjects[0]?.id ?? ''
      })
    } catch (error) {
      setProjectError(getErrorMessage(error))
      setProjects([])
      setSelectedProjectId('')
    } finally {
      setLoadingProjects(false)
    }
  }, [])

  const loadDeployments = useCallback(async (projectId: string) => {
    if (!projectId) {
      setDeployments([])
      setDeploymentError('')
      setLoadingDeployments(false)
      return
    }

    setLoadingDeployments(true)
    setDeploymentError('')

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/projects/${encodeURIComponent(projectId)}/deployments`,
      )

      if (!response.ok) {
        throw new Error(await readError(response))
      }

      const data: unknown = await response.json()

      if (!Array.isArray(data)) {
        throw new Error('The API returned an unexpected deployment list.')
      }

      setDeployments(data as Deployment[])
    } catch (error) {
      setDeploymentError(getErrorMessage(error))
      setDeployments([])
    } finally {
      setLoadingDeployments(false)
    }
  }, [])

  useEffect(() => {
    void loadProjects()
  }, [loadProjects])

  useEffect(() => {
    void loadDeployments(selectedProjectId)
  }, [selectedProjectId, loadDeployments])

  const totalDeployments = deployments.length

  const stagingCount = deployments.filter(
    (deployment) => deployment.environment === 'staging',
  ).length

  const productionCount = deployments.filter(
    (deployment) => deployment.environment === 'production',
  ).length

  const rolledBackCount = deployments.filter(
    (deployment) => deployment.status === 'rolled_back',
  ).length

  return (
    <section className="deployments-page">
      <div className="deployments-toolbar">
        <div className="deployments-project-control">
          <label htmlFor="deployment-project">Project</label>

          <select
            id="deployment-project"
            value={selectedProjectId}
            onChange={(event) => setSelectedProjectId(event.target.value)}
            disabled={loadingProjects || projects.length === 0}
          >
            {projects.length === 0 && (
              <option value="">
                {loadingProjects ? 'Loading projects…' : 'No projects available'}
              </option>
            )}

            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>

        <button
          className="deployments-button"
          type="button"
          onClick={() => {
            void loadProjects()
            void loadDeployments(selectedProjectId)
          }}
          disabled={loadingProjects || loadingDeployments}
        >
          {loadingProjects || loadingDeployments
            ? 'Refreshing…'
            : '↻ Refresh'}
        </button>
      </div>

      {projectError && (
        <div className="deployments-alert" role="alert">
          <strong>Unable to load projects</strong>
          <span>{projectError}</span>
          <button type="button" onClick={() => void loadProjects()}>
            Retry
          </button>
        </div>
      )}

      {!projectError && !loadingProjects && projects.length === 0 && (
        <div className="deployments-empty">
          <span className="deployments-empty-icon" aria-hidden="true">
            ▦
          </span>
          <h2>No projects available</h2>
          <p>Create a project before viewing its deployments.</p>
        </div>
      )}

      {!projectError && projects.length > 0 && (
        <>
          <div className="deployments-metrics">
            <article className="deployment-metric">
              <span>Total deployments</span>
              <strong>
                {loadingDeployments ? '…' : totalDeployments}
              </strong>
              <small>Selected project</small>
            </article>

            <article className="deployment-metric">
              <span>Staging</span>
              <strong>{loadingDeployments ? '…' : stagingCount}</strong>
              <small>Staging environment</small>
            </article>

            <article className="deployment-metric">
              <span>Production</span>
              <strong>{loadingDeployments ? '…' : productionCount}</strong>
              <small>Production environment</small>
            </article>

            <article className="deployment-metric">
              <span>Rolled back</span>
              <strong>{loadingDeployments ? '…' : rolledBackCount}</strong>
              <small>Completed rollbacks</small>
            </article>
          </div>

          {deploymentError && (
            <div className="deployments-alert" role="alert">
              <strong>Unable to load deployments</strong>
              <span>{deploymentError}</span>
              <button
                type="button"
                onClick={() => void loadDeployments(selectedProjectId)}
              >
                Retry
              </button>
            </div>
          )}

          {!deploymentError &&
            !loadingDeployments &&
            deployments.length === 0 && (
              <div className="deployments-empty">
                <span
                  className="deployments-empty-icon"
                  aria-hidden="true"
                >
                  ⇧
                </span>
                <h2>No deployments yet</h2>
                <p>
                  Deployments for this project will appear here when
                  they are created through the platform API.
                </p>
              </div>
            )}

          {!deploymentError && deployments.length > 0 && (
            <div className="deployments-panel">
              <div className="deployments-panel-header">
                <div>
                  <h2>Deployment inventory</h2>
                  <p>
                    Model versions and their current deployment states
                  </p>
                </div>

                <span className="deployments-count">
                  {deployments.length} record
                  {deployments.length === 1 ? '' : 's'}
                </span>
              </div>

              <div className="deployments-table-wrapper">
                <table className="deployments-table">
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Version</th>
                      <th>Environment</th>
                      <th>Status</th>
                      <th>Traffic</th>
                      <th>Created</th>
                    </tr>
                  </thead>

                  <tbody>
                    {deployments.map((deployment) => (
                      <tr key={deployment.id}>
                        <td>
                          <div className="deployment-model">
                            <span
                              className="deployment-model-icon"
                              aria-hidden="true"
                            >
                              ◈
                            </span>
                            <div>
                              <strong>{deployment.model_name}</strong>
                              <small>
                                {deployment.id.slice(0, 8)}
                              </small>
                            </div>
                          </div>
                        </td>

                        <td>
                          <span className="deployment-version">
                            v{deployment.model_version}
                          </span>
                        </td>

                        <td>
                          <span
                            className={`deployment-badge environment-${statusClass(deployment.environment)}`}
                          >
                            {deployment.environment}
                          </span>
                        </td>

                        <td>
                          <span
                            className={`deployment-badge status-${statusClass(deployment.status)}`}
                          >
                            {deployment.status.replace(/_/g, ' ')}
                          </span>
                        </td>

                        <td>
                          <div className="deployment-traffic">
                            <div className="deployment-traffic-track">
                              <span
                                style={{
                                  width: `${Math.max(
                                    0,
                                    Math.min(
                                      100,
                                      deployment.traffic_percentage,
                                    ),
                                  )}%`,
                                }}
                              />
                            </div>
                            <span>{deployment.traffic_percentage}%</span>
                          </div>
                        </td>

                        <td>{formatDate(deployment.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="deployments-panel-footer">
                Deployment state and traffic values are read from the
                platform API. This page does not change deployment state.
              </div>
            </div>
          )}

          {loadingDeployments && deployments.length === 0 && (
            <div className="deployments-loading" role="status">
              Loading deployments for the selected project…
            </div>
          )}
        </>
      )}
    </section>
  )
}

export default DeploymentPage
