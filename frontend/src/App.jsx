import { useEffect, useMemo, useState } from 'react'

const API_URL = import.meta.env.VITE_MIDWAY_API_URL || 'http://127.0.0.1:8000'

const menuItems = [
  'Dashboard',
  'Executivo 92/82',
  'Fila Técnica',
  'Ajustes IQS',
  'Auditoria',
  'Configurações',
]

function numberFormat(value) {
  return new Intl.NumberFormat('pt-BR').format(Number(value || 0))
}

function percent(value, total) {
  if (!total) return '0%'
  return `${((Number(value || 0) / Number(total)) * 100).toFixed(1)}%`
}

function Card({ label, value, hint, tone = 'blue' }) {
  return (
    <section className={`metric-card metric-card--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </section>
  )
}

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">M</div>
        <div>
          <strong>MIDWAY</strong>
          <span>IQS Platform</span>
        </div>
      </div>
      <nav>
        {menuItems.map((item, index) => (
          <button className={index === 0 ? 'active' : ''} key={item}>
            <span className="nav-icon">{item.slice(0, 1)}</span>
            {item}
          </button>
        ))}
      </nav>
      <div className="user-card">
        <div className="avatar">AD</div>
        <div>
          <strong>Admin</strong>
          <span>admin@midway.local</span>
        </div>
      </div>
    </aside>
  )
}

function StatusBadge({ health }) {
  const database = health?.database
  const ok = database?.status === 'ok'
  return (
    <div className={`status-badge ${ok ? 'online' : 'warning'}`}>
      <span />
      <div>
        <small>Ambiente</small>
        <strong>{ok ? 'API Online' : 'Verificar API'}</strong>
      </div>
    </div>
  )
}

export default function App() {
  const [health, setHealth] = useState(null)
  const [painel, setPainel] = useState([])
  const [fila, setFila] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      try {
        setLoading(true)
        const [healthResponse, painelResponse, filaResponse] = await Promise.all([
          fetch(`${API_URL}/api/health`),
          fetch(`${API_URL}/api/executivo/9282/painel`),
          fetch(`${API_URL}/api/executivo/9282/fila-tecnica?limit=8`),
        ])

        if (!healthResponse.ok || !painelResponse.ok || !filaResponse.ok) {
          throw new Error('Falha ao consultar a API MIDWAY.')
        }

        setHealth(await healthResponse.json())
        setPainel(await painelResponse.json())
        setFila(await filaResponse.json())
        setError('')
      } catch (requestError) {
        setError(requestError.message)
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [])

  const resumo = painel[0] || {}
  const filaTotal = Number(resumo.fila_tecnica_total || 0)

  const cards = useMemo(
    () => [
      {
        label: 'Ajustes automáticos',
        value: numberFormat(resumo.ajustes_auto_9282),
        hint: 'SERVIÇO + ROBUSTA',
        tone: 'green',
      },
      {
        label: 'Fila técnica',
        value: numberFormat(resumo.fila_tecnica_total),
        hint: `${numberFormat(resumo.fila_aberta)} em aberto`,
        tone: 'orange',
      },
      {
        label: 'Conflito serviço',
        value: numberFormat(resumo.fila_servico_conflito),
        hint: `${percent(resumo.fila_servico_conflito, filaTotal)} da fila`,
        tone: 'purple',
      },
      {
        label: 'Por reclamação',
        value: numberFormat(resumo.fila_reclamacao),
        hint: `${percent(resumo.fila_reclamacao, filaTotal)} da fila`,
        tone: 'blue',
      },
    ],
    [resumo, filaTotal],
  )

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main">
        <header className="topbar">
          <button className="hamburger">☰</button>
          <StatusBadge health={health} />
        </header>

        <section className="hero">
          <div>
            <p className="eyebrow">MIDWAY 7.0.0</p>
            <h1>Dashboard Executivo</h1>
            <p>Tratativa RA 92/82 com autorização em massa, fila técnica e auditoria PostgreSQL.</p>
          </div>
          <div className="hero-panel">
            <span>ANOMES</span>
            <strong>{resumo.anomes || '—'}</strong>
          </div>
        </section>

        {error && <div className="alert">Erro: {error}</div>}
        {loading && <div className="alert">Carregando indicadores da API...</div>}

        <section className="metrics-grid">
          {cards.map((card) => (
            <Card key={card.label} {...card} />
          ))}
        </section>

        <section className="content-grid">
          <article className="panel panel-large">
            <div className="panel-title">
              <div>
                <h2>Painel 92/82</h2>
                <p>Resumo consolidado vindo de `ddcq.vw_midway_9282_painel`.</p>
              </div>
            </div>
            <div className="summary-chart">
              <div style={{ '--value': percent(resumo.ajustes_auto_9282, Number(resumo.ajustes_auto_9282 || 0) + filaTotal) }} />
              <ul>
                <li><span className="dot green" /> Automáticos: {numberFormat(resumo.ajustes_auto_9282)}</li>
                <li><span className="dot orange" /> Fila aberta: {numberFormat(resumo.fila_aberta)}</li>
                <li><span className="dot purple" /> Conflitos: {numberFormat(resumo.fila_servico_conflito)}</li>
                <li><span className="dot blue" /> Reclamação: {numberFormat(resumo.fila_reclamacao)}</li>
              </ul>
            </div>
          </article>

          <article className="panel">
            <div className="panel-title">
              <div>
                <h2>Banco</h2>
                <p>Estado operacional da API.</p>
              </div>
            </div>
            <div className="db-status">
              <strong>{health?.database?.status || '—'}</strong>
              <span>{health?.database?.tables || 0} tabelas</span>
              <span>{health?.database?.views || 0} views</span>
              <span>{health?.database?.parameters || 0} parâmetros</span>
            </div>
          </article>
        </section>

        <section className="panel">
          <div className="panel-title">
            <div>
              <h2>Fila Técnica 92/82</h2>
              <p>Primeiros itens para análise manual do técnico.</p>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Prioridade</th>
                  <th>Interrupção</th>
                  <th>Fonte</th>
                  <th>Evidência</th>
                  <th>Sugestão</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {fila.map((item) => (
                  <tr key={item.id_fila}>
                    <td>{item.prioridade}</td>
                    <td>{item.num_seq_intrp}</td>
                    <td>{item.fonte_sugestao}</td>
                    <td>{item.nivel_evidencia}</td>
                    <td>{item.cod_comp_sugerido || '—'}/{item.cod_causa_sugerida || '—'}</td>
                    <td><span className="pill">{item.status_fila}</span></td>
                  </tr>
                ))}
                {!fila.length && !loading && (
                  <tr>
                    <td colSpan="6">Nenhum item encontrado.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  )
}
