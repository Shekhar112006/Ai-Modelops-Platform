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

const metrics = [
  { label: 'Projects', icon: '▦', value: '—', note: 'Waiting for API data' },
  { label: 'Training jobs', icon: '⚙', value: '—', note: 'Waiting for API data' },
  { label: 'Registered models', icon: '◈', value: '—', note: 'Waiting for API data' },
  { label: 'Deployments', icon: '⇧', value: '—', note: 'Waiting for API data' },
]

const services = [
  { name: 'Platform API', detail: 'Control plane' },
  { name: 'PostgreSQL', detail: 'Metadata and records' },
  { name: 'Redis', detail: 'Cache and task queue' },
  { name: 'Model server', detail: 'Inference service' },
]

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')

function App() {
  const [activePage, setActivePage] = useState('Overview')
  const [apiConnected, setApiConnected] = useState(false)

  useEffect(() => {
    let cancelled = false

    const checkApi = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health/live`)

        if (!response.ok) {
          throw new Error(`Health check failed: HTTP ${response.status}`)
        }

        if (!cancelled) setApiConnected(true)
      } catch {
        if (!cancelled) setApiConnected(false)
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
                {metrics.map((metric) => (
                  <article className="metric-card" key={metric.label}>
                    <div className="metric-topline">
                      <span className="metric-label">{metric.label}</span>
                      <span className="metric-icon" aria-hidden="true">{metric.icon}</span>
                    </div>
                    <div className="metric-value">{metric.value}</div>
                    <div className="metric-note">
                      <span className="status-dot status-dot-muted" />
                      {metric.note}
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
                    <span className="subtle-tag">LIVE CHECK PENDING</span>
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
                          <span className="status-dot status-dot-muted" />
                          Not checked
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="panel-footnote">
                    Service health will appear here after API integration.
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

                  <div className="empty-state">
                    <div className="empty-state-icon" aria-hidden="true">⌁</div>
                    <h3>No activity to display</h3>
                    <p>
                      Events will appear when the dashboard is connected
                      to your platform APIs.
                    </p>
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
