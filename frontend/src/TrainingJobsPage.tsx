import { useCallback, useEffect, useState } from 'react'
import './TrainingJobsPage.css'

interface Project {
  id: string
  name: string
  description: string | null
  status: string
  created_at: string
  updated_at: string
}

interface TrainingJob {
  id: string
  project_id: string
  workload: string
  status: string
  celery_task_id: string | null
  selected_model_name: string | null
  selected_model_version: string | null
  error_message: string | null
  created_at: string
  started_at: string | null
}

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')

const WORKLOAD = 'demo-classification'
const ACTIVE_STATUSES = new Set(['queued', 'running'])

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

function formatDate(value: string | null): string {
  if (!value) return 'Not started'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return 'Unknown'

  return date.toLocaleString()
}

function statusClass(status: string): string {
  return status.toLowerCase().replace(/[^a-z0-9-]/g, '-')
}

function TrainingJobsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [jobs, setJobs] = useState<TrainingJob[]>([])
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [loadingJobs, setLoadingJobs] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [search, setSearch] = useState('')

  const loadJobs = useCallback(async (projectId: string) => {
    if (!projectId) {
      setJobs([])
      setLoadingJobs(false)
      return
    }

    setLoadingJobs(true)
    setError('')

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/projects/${projectId}/training-jobs`,
      )

      if (!response.ok) {
        throw new Error(await getResponseError(response))
      }

      const data: unknown = await response.json()

      if (!Array.isArray(data)) {
        throw new Error('The API returned an unexpected training-job list.')
      }

      setJobs(data as TrainingJob[])
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoadingJobs(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function fetchProjects() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/projects`)

        if (!response.ok) {
          throw new Error(await getResponseError(response))
        }

        const data: unknown = await response.json()

        if (!Array.isArray(data)) {
          throw new Error('The API returned an unexpected project list.')
        }

        if (!cancelled) {
          const availableProjects = data as Project[]
          setProjects(availableProjects)

          if (availableProjects.length > 0) {
            setSelectedProjectId(availableProjects[0].id)
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            `${getErrorMessage(err)} Check that the FastAPI server is running.`,
          )
        }
      } finally {
        if (!cancelled) {
          setLoadingProjects(false)
        }
      }
    }

    void fetchProjects()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function fetchJobs() {
      if (!selectedProjectId) {
        setJobs([])
        setLoadingJobs(false)
        return
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/v1/projects/${selectedProjectId}/training-jobs`,
        )

        if (!response.ok) {
          throw new Error(await getResponseError(response))
        }

        const data: unknown = await response.json()

        if (!Array.isArray(data)) {
          throw new Error('The API returned an unexpected training-job list.')
        }

        if (!cancelled) {
          setJobs(data as TrainingJob[])
          setError('')
        }
      } catch (err) {
        if (!cancelled) {
          setError(getErrorMessage(err))
        }
      } finally {
        if (!cancelled) {
          setLoadingJobs(false)
        }
      }
    }

    void fetchJobs()

    return () => {
      cancelled = true
    }
  }, [selectedProjectId])

  useEffect(() => {
    if (!selectedProjectId) return

    const hasActiveJobs = jobs.some((job) =>
      ACTIVE_STATUSES.has(job.status.toLowerCase()),
    )

    if (!hasActiveJobs) return

    const intervalId = window.setInterval(() => {
      void loadJobs(selectedProjectId)
    }, 5000)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [jobs, selectedProjectId, loadJobs])

  async function startTraining() {
    if (!selectedProjectId || submitting) return

    setSubmitting(true)
    setError('')
    setSuccess('')

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/projects/${selectedProjectId}/training-jobs`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ workload: WORKLOAD }),
        },
      )

      if (!response.ok) {
        throw new Error(await getResponseError(response))
      }

      const created = await response.json() as TrainingJob

      setJobs((previous) => [
        created,
        ...previous.filter((job) => job.id !== created.id),
      ])

      setSuccess(
        `Training job ${created.id.slice(0, 8)} was accepted. Status: ${created.status}.`,
      )

      void loadJobs(selectedProjectId)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const filteredJobs = jobs.filter((job) => {
    const query = search.trim().toLowerCase()

    if (!query) return true

    return [
      job.id,
      job.workload,
      job.status,
      job.selected_model_name ?? '',
      job.error_message ?? '',
    ].some((value) => value.toLowerCase().includes(query))
  })

  const activeCount = jobs.filter((job) =>
    ACTIVE_STATUSES.has(job.status.toLowerCase()),
  ).length

  const succeededCount = jobs.filter(
    (job) => job.status.toLowerCase() === 'succeeded',
  ).length

  const failedCount = jobs.filter(
    (job) => job.status.toLowerCase() === 'failed',
  ).length

  return (
    <section className="training-page">
      <div className="training-intro">
        <div>
          <p className="training-eyebrow">MODEL DEVELOPMENT</p>
          <h2>Training jobs</h2>
          <p>
            Submit training runs and monitor their actual status through
            the ModelOps API.
          </p>
        </div>

        <button
          type="button"
          className="training-button training-button-primary"
          onClick={() => void startTraining()}
          disabled={
            submitting ||
            loadingProjects ||
            !selectedProjectId
          }
        >
          {submitting ? 'Submitting…' : '▶ Start training'}
        </button>
      </div>

      <div className="training-controls">
        <label className="training-field">
          <span>Project</span>
          <select
            value={selectedProjectId}
            disabled={loadingProjects || projects.length === 0}
            onChange={(event) => {
              setSelectedProjectId(event.target.value)
              setLoadingJobs(true)
              setError('')
              setSuccess('')
            }}
          >
            {loadingProjects && <option value="">Loading projects…</option>}

            {!loadingProjects && projects.length === 0 && (
              <option value="">No projects available</option>
            )}

            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>

        <div className="training-workload">
          <span>Workload</span>
          <strong>{WORKLOAD}</strong>
          <small>Existing backend workload</small>
        </div>

        <button
          type="button"
          className="training-button training-button-secondary"
          disabled={!selectedProjectId || loadingJobs}
          onClick={() => void loadJobs(selectedProjectId)}
        >
          ↻ Refresh jobs
        </button>
      </div>

      {error && (
        <div className="training-message training-message-error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError('')} aria-label="Dismiss error">
            ×
          </button>
        </div>
      )}

      {success && (
        <div className="training-message training-message-success" role="status">
          <span>{success}</span>
          <button type="button" onClick={() => setSuccess('')} aria-label="Dismiss message">
            ×
          </button>
        </div>
      )}

      <div className="training-stats">
        <article className="training-stat">
          <span>Total jobs</span>
          <strong>{jobs.length}</strong>
          <small>Selected project</small>
        </article>

        <article className="training-stat">
          <span>Active jobs</span>
          <strong>{activeCount}</strong>
          <small>Queued or running</small>
        </article>

        <article className="training-stat">
          <span>Succeeded</span>
          <strong>{succeededCount}</strong>
          <small>Reported by backend</small>
        </article>

        <article className="training-stat">
          <span>Failed</span>
          <strong>{failedCount}</strong>
          <small>Reported by backend</small>
        </article>
      </div>

      <div className="training-table-panel">
        <div className="training-table-heading">
          <div>
            <h3>Training history</h3>
            <p>Job state and model information from the API</p>
          </div>

          <label className="training-search">
            <span className="sr-only">Search training jobs</span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search jobs…"
            />
          </label>
        </div>

        {loadingProjects || loadingJobs ? (
          <div className="training-empty">
            <strong>Loading training jobs…</strong>
            <p>Retrieving job records from the platform API.</p>
          </div>
        ) : !selectedProjectId ? (
          <div className="training-empty">
            <strong>Select a project to continue</strong>
            <p>Create a project first if your workspace is empty.</p>
          </div>
        ) : filteredJobs.length === 0 ? (
          <div className="training-empty">
            <strong>{search.trim() ? 'No matching jobs' : 'No training jobs yet'}</strong>
            <p>
              {search.trim()
                ? 'Try another search term.'
                : 'Start training to submit the first job for this project.'}
            </p>
          </div>
        ) : (
          <div className="training-table-scroll">
            <table className="training-table">
              <thead>
                <tr>
                  <th>JOB</th>
                  <th>STATUS</th>
                  <th>WORKLOAD</th>
                  <th>MODEL</th>
                  <th>CREATED</th>
                  <th>ERROR</th>
                </tr>
              </thead>

              <tbody>
                {filteredJobs.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <code title={job.id}>{job.id.slice(0, 8)}…</code>
                      {job.celery_task_id && (
                        <small className="training-task-id">
                          Celery: {job.celery_task_id.slice(0, 8)}…
                        </small>
                      )}
                    </td>

                    <td>
                      <span
                        className={`training-status training-status-${statusClass(job.status)}`}
                      >
                        <span />
                        {job.status}
                      </span>
                    </td>

                    <td>{job.workload}</td>

                    <td>
                      {job.selected_model_name ? (
                        <>
                          <strong>{job.selected_model_name}</strong>
                          <small className="training-model-version">
                            Version {job.selected_model_version ?? 'Unknown'}
                          </small>
                        </>
                      ) : (
                        <span className="training-muted">Not selected yet</span>
                      )}
                    </td>

                    <td>{formatDate(job.created_at)}</td>

                    <td>
                      {job.error_message ? (
                        <span
                          className="training-error-detail"
                          title={job.error_message}
                        >
                          {job.error_message}
                        </span>
                      ) : (
                        <span className="training-muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="training-table-footer">
          <span>
            Showing {filteredJobs.length} of {jobs.length} jobs
          </span>
          <span>Refresh interval: 5 seconds while jobs are active</span>
        </div>
      </div>

      <p className="training-footnote">
        Training runs execute asynchronously. A job is considered complete
        only when the backend reports a terminal status.
      </p>
    </section>
  )
}

export default TrainingJobsPage
