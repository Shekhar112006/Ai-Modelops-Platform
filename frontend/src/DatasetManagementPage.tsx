import { useCallback, useEffect, useState } from 'react'
import './DatasetManagementPage.css'

interface Project {
  id: string
  name: string
  description: string | null
  status: string
  created_at: string
  updated_at: string
}

interface Dataset {
  id: string
  project_id: string
  name: string
  original_filename: string
  content_type: string
  file_size_bytes: number
  row_count: number
  column_count: number
  columns: string[]
  sha256: string
  status: string
  created_at: string
}

interface DatasetPreview {
  dataset_id: string
  name: string
  columns: string[]
  row_count: number
  preview_rows: Record<string, string | null>[]
  preview_limit: number
}

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')

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
    // Keep a useful HTTP message when the response is not JSON.
  }

  return `Request failed with HTTP ${response.status}.`
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`

  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function formatDate(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return 'Unknown'

  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function DatasetManagementPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [selectedDatasetId, setSelectedDatasetId] = useState('')
  const [preview, setPreview] = useState<DatasetPreview | null>(null)

  const [datasetName, setDatasetName] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const [loadingProjects, setLoadingProjects] = useState(true)
  const [loadingDatasets, setLoadingDatasets] = useState(false)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [uploading, setUploading] = useState(false)

  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const loadProjects = useCallback(async () => {
    setLoadingProjects(true)
    setError('')

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/projects`)

      if (!response.ok) {
        throw new Error(await getResponseError(response))
      }

      const data: unknown = await response.json()

      if (!Array.isArray(data)) {
        throw new Error('The API returned an unexpected project list.')
      }

      const availableProjects = data as Project[]
      setProjects(availableProjects)

      setSelectedProjectId((current) => {
        if (availableProjects.some((project) => project.id === current)) {
          return current
        }

        return availableProjects[0]?.id ?? ''
      })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoadingProjects(false)
    }
  }, [])

  const loadDatasets = useCallback(async (projectId: string) => {
    if (!projectId) {
      setDatasets([])
      setSelectedDatasetId('')
      setPreview(null)
      setLoadingDatasets(false)
      return
    }

    setLoadingDatasets(true)
    setError('')
    setPreview(null)

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/projects/${projectId}/datasets`,
      )

      if (!response.ok) {
        throw new Error(await getResponseError(response))
      }

      const data: unknown = await response.json()

      if (!Array.isArray(data)) {
        throw new Error('The API returned an unexpected dataset list.')
      }

      const availableDatasets = data as Dataset[]
      setDatasets(availableDatasets)

      setSelectedDatasetId((current) => {
        if (availableDatasets.some((dataset) => dataset.id === current)) {
          return current
        }

        return availableDatasets[0]?.id ?? ''
      })
    } catch (err) {
      setDatasets([])
      setSelectedDatasetId('')
      setPreview(null)
      setError(getErrorMessage(err))
    } finally {
      setLoadingDatasets(false)
    }
  }, [])

  const loadPreview = useCallback(async (datasetId: string) => {
    if (!datasetId) {
      setPreview(null)
      setLoadingPreview(false)
      return
    }

    setLoadingPreview(true)
    setError('')

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/datasets/${datasetId}/preview?limit=10`,
      )

      if (!response.ok) {
        throw new Error(await getResponseError(response))
      }

      const data = await response.json() as DatasetPreview
      setPreview(data)
    } catch (err) {
      setPreview(null)
      setError(getErrorMessage(err))
    } finally {
      setLoadingPreview(false)
    }
  }, [])

  useEffect(() => {
    void loadProjects()
  }, [loadProjects])

  useEffect(() => {
    void loadDatasets(selectedProjectId)
  }, [selectedProjectId, loadDatasets])

  useEffect(() => {
    void loadPreview(selectedDatasetId)
  }, [selectedDatasetId, loadPreview])

  async function uploadDataset(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSuccess('')

    if (!selectedProjectId) {
      setError('Create or select a project before uploading a dataset.')
      return
    }

    if (!selectedFile) {
      setError('Choose a CSV file to upload.')
      return
    }

    if (!selectedFile.name.toLowerCase().endsWith('.csv')) {
      setError('Only CSV files are supported.')
      return
    }

    const formData = new FormData()
    formData.append('name', datasetName.trim() || selectedFile.name)
    formData.append('file', selectedFile)

    setUploading(true)

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/projects/${selectedProjectId}/datasets`,
        {
          method: 'POST',
          body: formData,
        },
      )

      if (!response.ok) {
        throw new Error(await getResponseError(response))
      }

      const created = await response.json() as Dataset

      setDatasets((current) => [
        created,
        ...current.filter((dataset) => dataset.id !== created.id),
      ])
      setSelectedDatasetId(created.id)
      setDatasetName('')
      setSelectedFile(null)

      const fileInput = document.getElementById(
        'dataset-file-input',
      ) as HTMLInputElement | null

      if (fileInput) fileInput.value = ''

      setSuccess(
        `Dataset "${created.name}" uploaded successfully. ` +
        `${created.row_count.toLocaleString()} rows detected.`,
      )
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  const selectedProject = projects.find(
    (project) => project.id === selectedProjectId,
  )

  const selectedDataset = datasets.find(
    (dataset) => dataset.id === selectedDatasetId,
  )

  return (
    <section className="datasets-page">
      <div className="datasets-summary-grid">
        <article className="dataset-stat-card">
          <span className="dataset-stat-icon">▤</span>
          <div>
            <span className="dataset-stat-label">Datasets</span>
            <strong>
              {loadingDatasets ? '…' : datasets.length.toLocaleString()}
            </strong>
            <small>In selected project</small>
          </div>
        </article>

        <article className="dataset-stat-card">
          <span className="dataset-stat-icon">▦</span>
          <div>
            <span className="dataset-stat-label">Total rows</span>
            <strong>
              {loadingDatasets
                ? '…'
                : datasets.reduce((sum, item) => sum + item.row_count, 0)
                    .toLocaleString()}
            </strong>
            <small>Across available datasets</small>
          </div>
        </article>

        <article className="dataset-stat-card">
          <span className="dataset-stat-icon">✓</span>
          <div>
            <span className="dataset-stat-label">Ready</span>
            <strong>
              {loadingDatasets
                ? '…'
                : datasets.filter((item) => item.status === 'ready').length}
            </strong>
            <small>Available for next steps</small>
          </div>
        </article>
      </div>

      {error && (
        <div className="dataset-message dataset-message-error" role="alert">
          <span aria-hidden="true">!</span>
          <span>{error}</span>
          <button
            type="button"
            aria-label="Dismiss error"
            onClick={() => setError('')}
          >
            ×
          </button>
        </div>
      )}

      {success && (
        <div className="dataset-message dataset-message-success" role="status">
          <span aria-hidden="true">✓</span>
          <span>{success}</span>
          <button
            type="button"
            aria-label="Dismiss success message"
            onClick={() => setSuccess('')}
          >
            ×
          </button>
        </div>
      )}

      <article className="dataset-panel">
        <div className="dataset-panel-heading">
          <div>
            <h2>Upload dataset</h2>
            <p>Add a CSV dataset to a project for future training workflows.</p>
          </div>
          <span className="dataset-heading-icon" aria-hidden="true">↑</span>
        </div>

        <form className="dataset-upload-form" onSubmit={uploadDataset}>
          <label className="dataset-field">
            <span>Project <b>*</b></span>
            <select
              value={selectedProjectId}
              onChange={(event) => {
                setSelectedProjectId(event.target.value)
                setSuccess('')
              }}
              disabled={loadingProjects || projects.length === 0}
              required
            >
              <option value="">
                {loadingProjects ? 'Loading projects…' : 'Select a project'}
              </option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>

          <label className="dataset-field">
            <span>Dataset name <small>Optional</small></span>
            <input
              type="text"
              value={datasetName}
              onChange={(event) => setDatasetName(event.target.value)}
              placeholder="e.g. Customer training data"
              maxLength={200}
            />
          </label>

          <label className="dataset-field dataset-file-field">
            <span>CSV file <b>*</b></span>
            <input
              id="dataset-file-input"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => {
                setSelectedFile(event.target.files?.[0] ?? null)
                setSuccess('')
              }}
              required
            />
            <small>CSV format · Maximum file size: 20 MB</small>
          </label>

          <div className="dataset-upload-footer">
            <span>
              {selectedFile
                ? `${selectedFile.name} · ${formatBytes(selectedFile.size)}`
                : 'Choose a CSV file from your computer.'}
            </span>
            <button
              className="dataset-button dataset-button-primary"
              type="submit"
              disabled={
                uploading ||
                loadingProjects ||
                !selectedProjectId ||
                !selectedFile
              }
            >
              {uploading ? 'Uploading…' : '↑ Upload dataset'}
            </button>
          </div>

          {!loadingProjects && projects.length === 0 && (
            <p className="dataset-inline-note">
              No projects found. Create a project on the Projects page first.
            </p>
          )}
        </form>
      </article>

      <article className="dataset-panel">
        <div className="dataset-panel-heading dataset-library-heading">
          <div>
            <h2>Dataset library</h2>
            <p>
              {selectedProject
                ? `Datasets belonging to ${selectedProject.name}.`
                : 'Select a project to view its datasets.'}
            </p>
          </div>
          <button
            className="dataset-button dataset-button-secondary"
            type="button"
            onClick={() => void loadDatasets(selectedProjectId)}
            disabled={loadingDatasets || !selectedProjectId}
          >
            ↻ Refresh
          </button>
        </div>

        <div className="dataset-table-scroll">
          <table className="dataset-table">
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Columns</th>
                <th>File size</th>
                <th>Uploaded</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {loadingDatasets ? (
                <tr>
                  <td className="dataset-table-empty" colSpan={7}>
                    Loading datasets…
                  </td>
                </tr>
              ) : datasets.length === 0 ? (
                <tr>
                  <td className="dataset-table-empty" colSpan={7}>
                    <span className="dataset-empty-icon">▤</span>
                    <strong>No datasets yet</strong>
                    <span>Upload a CSV file above to get started.</span>
                  </td>
                </tr>
              ) : (
                datasets.map((dataset) => (
                  <tr
                    className={
                      selectedDatasetId === dataset.id
                        ? 'dataset-row-selected'
                        : ''
                    }
                    key={dataset.id}
                  >
                    <td>
                      <div className="dataset-name-cell">
                        <span className="dataset-file-icon">CSV</span>
                        <div>
                          <strong>{dataset.name}</strong>
                          <small>{dataset.original_filename}</small>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span
                        className={`dataset-status dataset-status-${dataset.status}`}
                      >
                        <span />
                        {dataset.status}
                      </span>
                    </td>
                    <td>{dataset.row_count.toLocaleString()}</td>
                    <td>{dataset.column_count.toLocaleString()}</td>
                    <td>{formatBytes(dataset.file_size_bytes)}</td>
                    <td>{formatDate(dataset.created_at)}</td>
                    <td>
                      <button
                        className="dataset-preview-button"
                        type="button"
                        onClick={() => setSelectedDatasetId(dataset.id)}
                        aria-pressed={selectedDatasetId === dataset.id}
                      >
                        Preview →
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="dataset-table-footer">
          <span>
            {loadingDatasets
              ? 'Retrieving dataset metadata…'
              : `${datasets.length} dataset${datasets.length === 1 ? '' : 's'} in this project`}
          </span>
          <span>CSV · Metadata stored in PostgreSQL</span>
        </div>
      </article>

      <article className="dataset-panel dataset-preview-panel">
        <div className="dataset-panel-heading">
          <div>
            <h2>Data preview</h2>
            <p>
              {selectedDataset
                ? `${selectedDataset.name} · First 10 rows`
                : 'Choose a dataset from the library to inspect its contents.'}
            </p>
          </div>
          <span className="dataset-preview-count">
            {preview
              ? `${preview.preview_rows.length} / ${preview.row_count.toLocaleString()} rows`
              : 'CSV preview'}
          </span>
        </div>

        {loadingPreview ? (
          <div className="dataset-preview-empty">Loading preview…</div>
        ) : preview ? (
          <>
            <div className="dataset-preview-meta">
              <span>{preview.columns.length} columns</span>
              <span>Read-only preview</span>
            </div>
            <div className="dataset-table-scroll dataset-preview-scroll">
              <table className="dataset-table dataset-data-table">
                <thead>
                  <tr>
                    <th className="dataset-row-number">#</th>
                    {preview.columns.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.preview_rows.map((row, index) => (
                    <tr key={`${preview.dataset_id}-${index}`}>
                      <td className="dataset-row-number">{index + 1}</td>
                      {preview.columns.map((column) => (
                        <td key={column}>
                          {row[column] === null || row[column] === undefined
                            ? 'NULL'
                            : row[column]}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {preview.preview_rows.length === 0 && (
                    <tr>
                      <td
                        className="dataset-table-empty"
                        colSpan={preview.columns.length + 1}
                      >
                        This dataset has no data rows.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <p className="dataset-preview-footnote">
              Preview only. The full dataset remains stored on the server.
            </p>
          </>
        ) : (
          <div className="dataset-preview-empty">
            <span className="dataset-empty-icon">⌕</span>
            <strong>No preview selected</strong>
            <span>Select a dataset and its sample rows will appear here.</span>
          </div>
        )}
      </article>
    </section>
  )
}

export default DatasetManagementPage
