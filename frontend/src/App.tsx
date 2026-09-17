import { useState } from 'react'
import SessionRunner from './components/SessionRunner'
import BenchmarkView from './components/BenchmarkView'
import './app.css'

type Tab = 'demo' | 'benchmark'

export default function App() {
  const [tab, setTab] = useState<Tab>('demo')

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>AgentShield</h1>
          <p className="tagline">
            Detecting aggregation-inference in agent sessions — individually-authorized calls
            composed into a synthesized capability the recipient isn't cleared for.
          </p>
        </div>
        <nav className="tabs">
          <button className={tab === 'demo' ? 'tab active' : 'tab'} onClick={() => setTab('demo')}>
            Live demo
          </button>
          <button className={tab === 'benchmark' ? 'tab active' : 'tab'} onClick={() => setTab('benchmark')}>
            Benchmark
          </button>
        </nav>
      </header>

      <main>{tab === 'demo' ? <SessionRunner /> : <BenchmarkView />}</main>

      <footer className="app-footer">
        Deterministic, rule-based decision engine — no LLM/ML in the authorization path.
        Reference implementation of a known, previously-unsolved-in-deployment problem.
      </footer>
    </div>
  )
}
