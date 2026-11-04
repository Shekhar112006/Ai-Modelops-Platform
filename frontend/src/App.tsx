import { useEffect, useState } from 'react'
import ProjectsPage from './ProjectsPage'
import TrainingJobsPage from './TrainingJobsPage'
import ModelRegistryPage from './ModelRegistryPage'
import DeploymentPage from './DeploymentPage'
import PredictionsPage from './PredictionsPage'
import ObservabilityPage from './ObservabilityPage'
import DatasetManagementPage from './DatasetManagementPage'
import './App.css'

const navigation = [
  {
    heading: 'WORKSPACE',
    items: [
      { label: 'Overview', icon: '◫' },
      { label: 'Projects', icon: '▦' },
      { label: 'Datasets', icon: '▤' },
    ],
  },
  {
    heading: 'MACHINE LEARNING',
    items: [
      { label: 'Training Jobs', icon: '⚙' },
      { label: 'Model Registry', icon: '◈' },
      { label: 'Deployments', icon: '⇧' },
      { label: 'Predictions', icon: '⌁' },
    ],
  },
  {
    heading: 'OPERATIONS',
    items: [
      { label: 'Observability', icon: '▥' },
    ],
  },
]

type Activity = {
  id: string
  event_type: 'project' | 'dataset' | 'training' | 'deployment'
  title: string
  description: string
  status: string
  project_name: string
  timestamp: string
}

type OverviewMetrics = {
  projects: number | null
  trainingJobs: number | null
  registeredModels: number | null
  deployments: number | null
}

const initialOverviewMetrics: OverviewMetrics = {
  projects: null,
  trainingJobs: null,
  registeredModels: null,
  deployments: null,
}

type ServiceHealth = {
  api: string
  postgresql: string
  redis: string
  model_server: string
}

type ServiceHealthResponse = {
  status: string
  services: ServiceHealth
}

const initialServiceHealth: ServiceHealth = {
  api: 'unknown',
  postgresql: 'unknown',
  redis: 'unknown',
  model_server: 'unknown',
}

const services = [
  {
    name: 'Platform API',
    detail: 'Control plane',
    key: 'api',
  },
  {
    name: 'PostgreSQL',
    detail: 'Metadata and records',
    key: 'postgresql',
  },
  {
    name: 'Redis',
    detail: 'Cache and task queue',
    key: 'redis',
  },
  {
    name: 'Model server',
    detail: 'Inference service',
    key: 'model_server',
  },
] as const

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')

function App() {
  const [activePage, setActivePage] = useState('Overview')
  const [activities, setActivities] = useState<Activity[]>([])
  const [activityLoading, setActivityLoading] = useState(true)
  const [activityError, setActivityError] = useState<string | null>(null)
  const [apiConnected, setApiConnected] = useState(false)
  const [overviewMetrics, setOverviewMetrics] =
    useState<OverviewMetrics>(initialOverviewMetrics)

  const [metricsLoading, setMetricsLoading] = useState(true)
  const [metricsError, setMetricsError] = useState<string | null>(null)
  const [serviceHealth, setServiceHealth] =
    useState<ServiceHealth>(initialServiceHealth)

  const [serviceHealthLoading, setServiceHealthLoading] =
    useState(true)

  const [serviceHealthError, setServiceHealthError] =
    useState<string | null>(null)
  useEffect(() => {
    let cancelled = false

    type ProjectSummary = {
      id: string
    }

    type RegistryResponse = {
      models: unknown[]
      total: number
    }

    const getJson = async <T,>(url: string): Promise<T> => {
      const response = await fetch(`${API_BASE_URL}${url}`)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${url}`)
      }

      return response.json() as Promise<T>
    }

    const loadOverviewMetrics = async () => {
      if (!cancelled) {
        setMetricsLoading(true)
        setMetricsError(null)
      }

      const [projectsResult, registryResult] = await Promise.allSettled([
        getJson<ProjectSummary[]>('/api/v1/projects'),
        getJson<RegistryResponse>('/api/v1/registry/models'),
      ])


      let projectsCount: number | null = null
      let trainingJobsCount: number | null = null
      let deploymentsCount: number | null = null
      let registeredModelsCount: number | null = null

      const errors: string[] = []

      if (projectsResult.status === 'fulfilled') {
        const projects = projectsResult.value
        projectsCount = projects.length

        const projectResults = await Promise.all(
          projects.map(async (project) => {
            const [jobsResult, deploymentsResult] =
              await Promise.allSettled([
                getJson<unknown[]>(
                  `/api/v1/projects/${project.id}/training-jobs`,
                ),
                getJson<unknown[]>(
                  `/api/v1/projects/${project.id}/deployments`,
                ),
              ])

            return { jobsResult, deploymentsResult }
          }),
        )

        let totalJobs = 0
        let totalDeployments = 0
        let jobsComplete = true
        let deploymentsComplete = true

        for (const result of projectResults) {
          if (result.jobsResult.status === 'fulfilled') {
            totalJobs += result.jobsResult.value.length
          } else {
            jobsComplete = false
          }

          if (result.deploymentsResult.status === 'fulfilled') {
            totalDeployments += result.deploymentsResult.value.length
          } else {
            deploymentsComplete = false
          }
        }

        trainingJobsCount = jobsComplete ? totalJobs : null
        deploymentsCount = deploymentsComplete ? totalDeployments : null

        if (!jobsComplete) errors.push('Some training job data could not load.')
        if (!deploymentsComplete) errors.push('Some deployment data could not load.')
      } else {
        errors.push('Project data could not load.')
      }

      if (registryResult.status === 'fulfilled') {
        registeredModelsCount = registryResult.value.total
      } else {
        errors.push('Model registry data could not load.')
      }

      if (cancelled) return

      setOverviewMetrics({
        projects: projectsCount,
        trainingJobs: trainingJobsCount,
        registeredModels: registeredModelsCount,
        deployments: deploymentsCount,
      })

      setMetricsError(errors.length > 0 ? errors.join(' ') : null)
      setMetricsLoading(false)
    }

    void loadOverviewMetrics()

    const intervalId = window.setInterval(() => {
      void loadOverviewMetrics()
    }, 30000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])


    // Service health monitoring
  useEffect(() => {
    let cancelled = false

    const loadServiceHealth = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/health/services`,
        )

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const result: ServiceHealthResponse = await response.json()

        if (!cancelled) {
          setServiceHealth(result.services)
          setServiceHealthError(null)
        }
      } catch {
        if (!cancelled) {
          setServiceHealthError(
            'Unable to retrieve service health.',
          )
        }
      } finally {
        if (!cancelled) {
          setServiceHealthLoading(false)
        }
      }
    }

    void loadServiceHealth()

    const intervalId = window.setInterval(() => {
      void loadServiceHealth()
    }, 30000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])
  // Recent activity monitoring
  useEffect(() => {
    let cancelled = false

    const loadActivities = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/v1/activity?limit=10`,
        )

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const result: Activity[] = await response.json()

        if (!cancelled) {
          setActivities(result)
          setActivityError(null)
        }
      } catch {
        if (!cancelled) {
          setActivityError('Unable to retrieve recent activity.')
        }
      } finally {
        if (!cancelled) {
          setActivityLoading(false)
        }
      }
    }

    void loadActivities()

    const intervalId = window.setInterval(() => {
      void loadActivities()
    }, 30000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])

  // API liveness monitoring
  useEffect(() => {
    let cancelled = false

    const checkApi = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health/live`)

        if (!response.ok) {
          throw new Error(`Health check failed: HTTP ${response.status}`)
        }

        if (!cancelled) {
          setApiConnected(true)
        }
      } catch {
        if (!cancelled) {
          setApiConnected(false)
        }
      }
    }

    void checkApi()

    const intervalId = window.setInterval(() => {
      void checkApi()
    }, 15000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])

  const isOverview = activePage === 'Overview'

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(event) => {
          event.preventDefault()
          setActivePage('Overview')
        }}>
          <span className="brand-mark">M</span>
          <span className="brand-copy">
            <strong>ModelOps</strong>
            <small>AI PLATFORM</small>
          </span>
        </a>

        <div className="workspace-switcher">
          <span className="workspace-avatar">A</span>
          <span className="workspace-copy">
            <strong>AI Workspace</strong>
            <small>Development environment</small>
          </span>
          <span className="switcher-chevron">⌄</span>
        </div>

        <nav className="main-navigation" aria-label="Main navigation">
          {navigation.map((group) => (
            <div className="nav-group" key={group.heading}>
              <p className="nav-heading">{group.heading}</p>
              {group.items.map((item) => (
                <button
                  className={`nav-item ${activePage === item.label ? 'active' : ''}`}
                  key={item.label}
                  onClick={() => setActivePage(item.label)}
                  type="button"
                >
                  <span className="nav-icon" aria-hidden="true">{item.icon}</span>
                  <span>{item.label}</span>
                  {item.label === 'Deployments' && (
                    <span className="nav-count">—</span>
                  )}
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="environment-card">
            <span className="environment-dot" />
            <div>
              <strong>Local environment</strong>
              <small>Development mode</small>
            </div>
          </div>
          <div className="sidebar-footer">
            <span className="footer-symbol">⌘</span>
            <span>AI ModelOps Platform</span>
            <span className="version-tag">v0.1</span>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="breadcrumb-separator">/</span>
            <strong>{activePage}</strong>
          </div>
          <div className="topbar-right">
            <div className="connection-status">
              <span
                className={`status-dot ${apiConnected ? 'status-dot-connected' : 'status-dot-muted'}`}
              />
              <span>{apiConnected ? 'API connected' : 'API not connected'}</span>
            </div>
            <button
              className="icon-button"
              type="button"
              aria-label="Notifications"
              title="Notifications"
            >
              ♧
            </button>
            <div className="user-avatar" title="Local development user">D</div>
          </div>
        </header>

        <div className="page-content">
          <section className="page-heading">
            <div>
              <p className="eyebrow">
                {isOverview ? 'PLATFORM CONTROL CENTER' : 'WORKSPACE / ' + activePage.toUpperCase()}
              </p>
              <h1>{isOverview ? 'Platform overview' : activePage}</h1>
              <p className="page-description">
                {isOverview
                  ? 'Monitor your machine learning lifecycle from one place.'
                  : `Manage and monitor ${activePage.toLowerCase()} across your ML lifecycle.`}
              </p>
            </div>
            <div className="heading-actions">
              <span className="environment-pill">
                <span className="status-dot status-dot-muted" />
                Development
              </span>
              <button
                className="primary-button"
                type="button"
                onClick={() => setActivePage('Projects')}
              >
                <span aria-hidden="true">＋</span> View projects
              </button>
            </div>
          </section>

          {isOverview ? (
            <>
              <section className="metrics-grid" aria-label="Platform metrics">
                {[
                  {
                    label: 'Projects',
                    icon: '▦',
                    value: overviewMetrics.projects,
                  },
                  {
                    label: 'Training jobs',
                    icon: '⚙',
                    value: overviewMetrics.trainingJobs,
                  },
                  {
                    label: 'Registered models',
                    icon: '◈',
                    value: overviewMetrics.registeredModels,
                  },
                  {
                    label: 'Deployments',
                    icon: '⇧',
                    value: overviewMetrics.deployments,
                  },
                ].map((metric) => (
                  <article className="metric-card" key={metric.label}>
                    <div className="metric-topline">
                      <span className="metric-label">{metric.label}</span>
                      <span className="metric-icon" aria-hidden="true">
                        {metric.icon}
                      </span>
                    </div>

                    <div className="metric-value">
                      {metricsLoading ? '...' : metric.value ?? '—'}
                    </div>

                    <div className="metric-note">
                      <span className="status-dot status-dot-muted" />
                      {metricsLoading
                        ? 'Loading platform data'
                        : metricsError
                          ? 'Data may be incomplete'
                          : 'Live platform data'}
                    </div>
                  </article>
                ))}
              </section>

              <section className="content-grid">
                <article className="panel services-panel">
                  <div className="panel-header">
                    <div>
                      <h2>Platform services</h2>
                      <p>Infrastructure components used by the platform</p>
                    </div>
                    <span className="subtle-tag">
                      {serviceHealthLoading
                        ? 'CHECKING SERVICES'
                        : serviceHealthError
                          ? 'CHECK UNAVAILABLE'
                          : Object.values(serviceHealth).every(
                              (value) => value === 'healthy',
                            )
                            ? 'ALL SYSTEMS OPERATIONAL'
                            : 'SERVICE DEGRADED'}
                    </span>
                  </div>

                  <div className="service-list">
                    {services.map((service) => (
                      <div className="service-row" key={service.name}>
                        <span className="service-icon" aria-hidden="true">
                          {service.name === 'Platform API' ? '⌘'
                            : service.name === 'PostgreSQL' ? '▤'
                              : service.name === 'Redis' ? 'ϟ' : '◈'}
                        </span>
                        <div className="service-copy">
                          <strong>{service.name}</strong>
                          <small>{service.detail}</small>
                        </div>
                        <span className="service-status">
                          <span
                            className={`status-dot ${
                              serviceHealth[service.key] === 'healthy'
                                ? 'status-dot-success'
                                : serviceHealth[service.key] === 'unhealthy'
                                  ? 'status-dot-error'
                                  : 'status-dot-muted'
                            }`}
                          />
                          {serviceHealthLoading
                            ? 'Checking'
                            : serviceHealthError
                              ? 'Unavailable'
                              : serviceHealth[service.key] === 'healthy'
                                ? 'Healthy'
                                : serviceHealth[service.key] === 'unhealthy'
                                  ? 'Unhealthy'
                                  : 'Unknown'}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="panel-footnote">
                    {serviceHealthError
                      ? serviceHealthError
                      : 'Service health refreshes automatically every 30 seconds.'}
                  </div>
                </article>

                <article className="panel activity-panel">
                  <div className="panel-header">
                    <div>
                      <h2>Recent activity</h2>
                      <p>Latest events across your ML projects</p>
                    </div>
                    <button
                      className="text-button"
                      type="button"
                      onClick={() => setActivePage('Observability')}
                    >
                      View logs <span aria-hidden="true">→</span>
                    </button>
                  </div>

                  <div className="activity-list">
                    {activityLoading ? (
                      <div className="empty-state">
                        <h3>Loading activity...</h3>
                        <p>Retrieving the latest platform events.</p>
                      </div>
                    ) : activityError ? (
                      <div className="empty-state">
                        <div className="empty-state-icon" aria-hidden="true">!</div>
                        <h3>Activity unavailable</h3>
                        <p>{activityError}</p>
                      </div>
                    ) : activities.length === 0 ? (
                      <div className="empty-state">
                        <div className="empty-state-icon" aria-hidden="true">⌁</div>
                        <h3>No activity yet</h3>
                        <p>Platform events will appear here as you use your workspace.</p>
                      </div>
                    ) : (
                      activities.map((activity) => (
                        <div className="activity-item" key={`${activity.event_type}-${activity.id}`}>
                          <div className={`activity-icon activity-icon-${activity.event_type}`}>
                            {activity.event_type === 'project'
                              ? '▦'
                              : activity.event_type === 'dataset'
                                ? '▤'
                                : activity.event_type === 'training'
                                  ? '⚙'
                                  : '⇧'}
                          </div>

                          <div className="activity-details">
                            <strong>{activity.title}</strong>
                            <p>{activity.description}</p>
                            <small>
                              {activity.project_name} ·{' '}
                              {new Date(activity.timestamp).toLocaleString()}
                            </small>
                          </div>

                          <span className={`activity-status activity-status-${activity.status.toLowerCase()}`}>
                            {activity.status}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </article>
              </section>

              <section className="panel getting-started-panel">
                <div className="getting-started-icon" aria-hidden="true">✳</div>
                <div className="getting-started-copy">
                  <h2>Your ML lifecycle, in one place</h2>
                  <p>
                    Create projects, run training jobs, register model versions,
                    and manage deployments through a unified platform.
                  </p>
                </div>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setActivePage('Projects')}
                >
                  Explore projects <span aria-hidden="true">→</span>
                </button>
              </section>
            </>
          ) : activePage === 'Datasets' ? (
            <DatasetManagementPage />
          ) : activePage === 'Projects' ? (
            <ProjectsPage />
          ) : activePage === 'Training Jobs' ? (
            <TrainingJobsPage />
          ) : activePage === 'Model Registry' ? (
            <ModelRegistryPage />
          ) : activePage === 'Deployments' ? (
            <DeploymentPage />
          ) : activePage === 'Predictions' ? (
            <PredictionsPage />
          ) : activePage === 'Observability' ? (
            <ObservabilityPage />
          ) : (
            <section className="panel section-placeholder">
              <div className="placeholder-icon" aria-hidden="true">
                {navigation.flatMap((group) => group.items)
                  .find((item) => item.label === activePage)?.icon ?? '◫'}
              </div>
              <p className="eyebrow">DASHBOARD SECTION</p>
              <h2>{activePage}</h2>
              <p className="placeholder-description">
                This section is ready for implementation. In the next steps,
                we'll connect it to the existing backend endpoints and display
                real platform data.
              </p>
              <div className="integration-notice">
                <span className="status-dot status-dot-muted" />
                API integration pending — no live data is being shown.
              </div>
              <button
                className="secondary-button"
                type="button"
                onClick={() => setActivePage('Overview')}
              >
                ← Back to overview
              </button>
            </section>
          )}

          <footer className="page-footer">
            <span>AI ModelOps Platform</span>
            <span>Built for the end-to-end ML lifecycle</span>
          </footer>
        </div>
      </main>
    </div>
  )
}

export default App
