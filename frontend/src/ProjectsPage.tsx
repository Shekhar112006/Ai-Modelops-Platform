import { useCallback, useEffect, useMemo, useState } from 'react'
import './ProjectsPage.css'

interface Project {
  id: string
  name: string
  description: string | null
  status: string
  created_at: string
  updated_at: string
}

interface ProjectCreate {
  name: string
  description: string
}

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')

const PAGE_SIZE = 10

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'An unexpected error occurred.'
}

function formatDate(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Unknown'
  }

  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const loadProjects = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/projects`)

      if (!response.ok) {
        throw new Error(`Unable to load projects (HTTP ${response.status}).`)
      }

      const data: unknown = await response.json()

      if (!Array.isArray(data)) {
        throw new Error('The API returned an unexpected project list.')
      }

      setProjects(data as Project[])
    } catch (err) {
      setError(
        `${getErrorMessage(err)} Check that the FastAPI server is running.`,
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function fetchInitialProjects() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/projects`)

        if (!response.ok) {
          throw new Error(
            `Unable to load projects (HTTP ${response.status}).`,
          )
        }

        const data: unknown = await response.json()

        if (!Array.isArray(data)) {
          throw new Error('The API returned an unexpected project list.')
        }

        if (!cancelled) {
          setProjects(data as Project[])
          setError('')
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            `${getErrorMessage(err)} Check that the FastAPI server is running.`,
          )
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void fetchInitialProjects()

    return () => {
      cancelled = true
    }
  }, [])

  const filteredProjects = useMemo(() => {
    const query = search.trim().toLowerCase()

    if (!query) {
      return projects
    }

    return projects.filter((project) =>
      `${project.name} ${project.description ?? ''}`
        .toLowerCase()
        .includes(query),
    )
  }, [projects, search])

  const pageCount = Math.max(1, Math.ceil(filteredProjects.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const visibleProjects = filteredProjects.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  )

  async function createProject(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSuccess('')

    const payload: ProjectCreate = {
      name: name.trim(),
      description: description.trim(),
    }

    if (!payload.name) {
      setError('Project name is required.')
      return
    }

    setSubmitting(true)

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: payload.name,
          description: payload.description || null,
        }),
      })

      if (!response.ok) {
        let message = `Project creation failed (HTTP ${response.status}).`

        try {
          const body = await response.json() as { detail?: string }
          if (typeof body.detail === 'string') {
            message = body.detail
          }
        } catch {
          // Keep the HTTP error message when the response isn't JSON.
        }

        throw new Error(message)
      }

      const created = await response.json() as Project

      setProjects((previous) => [
        created,
        ...previous.filter((project) => project.id !== created.id),
      ])
      setSearch('')
      setPage(1)
      setName('')
      setDescription('')
      setShowForm(false)
      setSuccess(`Project "${created.name}" was created successfully.`)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="projects-page">
      <div className="projects-toolbar">
        <div className="projects-summary">
          <strong>{loading ? 'Loading…' : filteredProjects.length}</strong>
          <span>
            {search.trim() ? 'matching projects' : 'projects'}
          </span>
          {!loading && (
            <span className="projects-total">
              {projects.length} total in workspace
            </span>
          )}
        </div>

        <div className="projects-actions">
          <label className="project-search">
            <span aria-hidden="true">⌕</span>
            <input
              type="search"
              placeholder="Search projects..."
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPage(1)
                setSuccess('')
              }}
              aria-label="Search projects by name or description"
            />
          </label>

          <button
            className="projects-button projects-button-secondary"
            type="button"
            onClick={() => void loadProjects()}
            disabled={loading}
          >
            ↻ Refresh
          </button>

          <button
            className="projects-button projects-button-primary"
            type="button"
            onClick={() => {
              setShowForm((visible) => !visible)
              setError('')
              setSuccess('')
            }}
          >
            ＋ New project
          </button>
        </div>
      </div>

      {showForm && (
        <form className="project-form" onSubmit={createProject}>
          <div className="project-form-heading">
            <div>
              <h2>Create a project</h2>
              <p>Start a workspace for your ML lifecycle.</p>
            </div>
            <button
              className="project-close-button"
              type="button"
              onClick={() => setShowForm(false)}
              aria-label="Close project form"
            >
              ×
            </button>
          </div>

          <label className="project-field">
            <span>Project name <span className="required-mark">*</span></span>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. House Price Prediction"
              maxLength={120}
              required
            />
          </label>

          <label className="project-field">
            <span>Description <span className="optional-label">Optional</span></span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What will this project accomplish?"
              maxLength={1000}
              rows={3}
            />
          </label>

          <div className="project-form-footer">
            <span>Project names must be unique.</span>
            <button
              className="projects-button projects-button-primary"
              type="submit"
              disabled={submitting || !name.trim()}
            >
              {submitting ? 'Creating…' : 'Create project'}
            </button>
          </div>
        </form>
      )}

      {error && (
        <div className="project-message project-message-error" role="alert">
          <span aria-hidden="true">!</span>
          <span>{error}</span>
          <button type="button" onClick={() => setError('')} aria-label="Dismiss error">
            ×
          </button>
        </div>
      )}

      {success && (
        <div className="project-message project-message-success" role="status">
          <span aria-hidden="true">✓</span>
          <span>{success}</span>
          <button type="button" onClick={() => setSuccess('')} aria-label="Dismiss message">
            ×
          </button>
        </div>
      )}

      <div className="projects-table-panel">
        <div className="projects-table-heading">
          <div>
            <h2>All projects</h2>
            <p>Projects stored in your ModelOps platform database.</p>
          </div>
          <span className="projects-live-label">
            <span className="projects-live-dot" />
            API DATA
          </span>
        </div>

        {loading ? (
          <div className="projects-state">
            <span className="projects-spinner" />
            <strong>Loading projects</strong>
            <p>Retrieving records from the platform API…</p>
          </div>
        ) : error && projects.length === 0 ? (
          <div className="projects-state">
            <div className="projects-state-icon">!</div>
            <h3>Projects couldn't be loaded</h3>
            <p>Check the API connection, then try again.</p>
            <button
              className="projects-button projects-button-secondary"
              type="button"
              onClick={() => void loadProjects()}
            >
              Try again
            </button>
          </div>
        ) : visibleProjects.length === 0 ? (
          <div className="projects-state">
            <div className="projects-state-icon">▦</div>
            <h3>{search.trim() ? 'No matching projects' : 'No projects yet'}</h3>
            <p>
              {search.trim()
                ? 'Try a different search term.'
                : 'Create a project to start organizing your ML work.'}
            </p>
            {search.trim() && (
              <button
                className="projects-button projects-button-secondary"
                type="button"
                onClick={() => setSearch('')}
              >
                Clear search
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="projects-table-scroll">
              <table className="projects-table">
                <thead>
                  <tr>
                    <th>PROJECT</th>
                    <th>STATUS</th>
                    <th>CREATED</th>
                    <th>PROJECT ID</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleProjects.map((project) => (
                    <tr key={project.id}>
                      <td>
                        <div className="project-name-cell">
                          <span className="project-avatar" aria-hidden="true">
                            {project.name.trim().charAt(0).toUpperCase() || 'P'}
                          </span>
                          <div>
                            <strong>{project.name}</strong>
                            <small>
                              {project.description || 'No description provided'}
                            </small>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span
                          className={`project-status project-status-${project.status.toLowerCase().replace(/[^a-z0-9-]/g, '-')}`}
                        >
                          <span />
                          {project.status}
                        </span>
                      </td>
                      <td className="project-date">{formatDate(project.created_at)}</td>
                      <td>
                        <code className="project-id" title={project.id}>
                          {project.id.slice(0, 8)}…
                        </code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="projects-pagination">
              <span>
                Showing {(currentPage - 1) * PAGE_SIZE + 1}–
                {Math.min(currentPage * PAGE_SIZE, filteredProjects.length)} of{' '}
                {filteredProjects.length}
              </span>
              <div className="projects-page-controls">
                <button
                  type="button"
                  className="projects-button projects-button-secondary"
                  disabled={currentPage === 1}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                >
                  ← Previous
                </button>
                <span>Page {currentPage} of {pageCount}</span>
                <button
                  type="button"
                  className="projects-button projects-button-secondary"
                  disabled={currentPage >= pageCount}
                  onClick={() => setPage((value) => Math.min(pageCount, value + 1))}
                >
                  Next →
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  )
}

export default ProjectsPage
