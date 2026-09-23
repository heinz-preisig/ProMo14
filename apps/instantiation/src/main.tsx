import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { GRAPH_IRI } from './api'

/** Hub ticket #1: the graph choice is unavoidable — without ?graph=
 *  the app would silently edit the default ontology graph.  Render a
 *  guard instead of the app (a redirect to "/" would loop in dev,
 *  where Vite serves this app at "/"). */
const HUB_URL = import.meta.env.DEV ? 'http://localhost:8000/' : '/'

function MissingGraph() {
  return (
    <main style={{
      fontFamily: 'system-ui, sans-serif',
      margin: '4rem auto', maxWidth: '34rem', lineHeight: 1.5,
    }}>
      <h1>No artefact selected</h1>
      <p>
        This app instantiates one model artefact — open one from the{' '}
        <a href={HUB_URL}>hub</a> to start a session.
      </p>
    </main>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {GRAPH_IRI ? <App /> : <MissingGraph />}
  </StrictMode>,
)
