import React, { useCallback, useEffect, useMemo, useState } from 'react'

const API_URL = import.meta.env.VITE_MIDWAY_API_URL || 'http://127.0.0.1:8001'

const menuItems = [
  { id: 'dashboard', label: 'Visão Geral', icon: 'V' },
  { id: 'tratativas_massa', label: 'Tratativas em Massa', icon: 'T' },
  { id: 'aprovacao', label: 'Aprovação', icon: 'A', profiles: ['GESTOR', 'ADM'] },
  { id: 'ocorrencias', label: 'Ocorrências', icon: 'O' },
  { id: 'alteracoes_manuais', label: 'Ajustes Manuais', icon: 'M' },
  { id: 'executivo', label: 'Saída IQS', icon: 'I', profiles: ['GESTOR', 'ADM'] },
  { id: 'administracao', label: 'Administração', icon: 'G', profiles: ['ADM'] },
]

const EXECUCAO_MODULO_MAP = {
  CORRECAO_9282: 'correcao_9282',
  COMPONENTE_CAUSA: 'agente_comp_causa',
  FALHA_EQUIPAMENTO_RA: 'suspeita_falha_ra',
  DURACAO_IMPACTO: 'analise_tecnica_cache',
  RESSARCIMENTO_ATIPICO: 'analise_tecnica_cache',
  SOBREPOSICAO_UC: 'exportacao_sobreposicao',
  INTERRUPCAO_SEM_UC: 'interrupcao_sem_uc',
  DUPLICIDADE_TIPO: 'auditoria_duplicidade_tipo',
  DIA_CRITICO_ISE: 'simulacao_ise',
}

function numberFormat(value) {
  return new Intl.NumberFormat('pt-BR').format(Number(value || 0))
}

function normalizeDecimalParam(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  if (text.includes(',')) {
    return text.replace(/\./g, '').replace(',', '.')
  }
  return text
}

function decimalFormat(value, digits = 4) {
  return new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number(value || 0))
}

function currencyFormat(value) {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(Number(value || 0))
}

function percent(value, total) {
  if (!total) return '0%'
  return `${decimalFormat((Number(value || 0) / Number(total)) * 100, 1)}%`
}

function dateTime(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'medium',
  }).format(new Date(value))
}

function textValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function hasProfile(user, profiles) {
  return profiles.includes(user?.perfil)
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

function SeverityBadge({ value }) {
  const normalized = String(value || '').toLowerCase()
  const tone = normalized.includes('crítica') ? 'critical' : normalized.includes('alta') ? 'danger' : normalized.includes('média') ? 'warning' : 'info'
  return <span className={`pill pill-${tone}`}>{value || '—'}</span>
}

function ConfidenceBadge({ value }) {
  const number = Number(value || 0)
  const tone = number >= 0.9 ? 'success' : number >= 0.75 ? 'warning' : 'danger'
  return <span className={`pill pill-${tone}`}>{decimalFormat(number * 100, 1)}%</span>
}

function StatusPill({ value }) {
  const normalized = String(value || '').toLowerCase()
  const tone = normalized.includes('erro') || normalized.includes('cancel')
    ? 'danger'
    : normalized.includes('process') || normalized.includes('aberto') || normalized.includes('pendente')
      ? 'warning'
      : normalized.includes('concl') || normalized.includes('aprov')
        ? 'success'
        : 'info'
  return <span className={`pill pill-${tone}`}>{value || '—'}</span>
}

function CodeLabel({ codigo, nome, descricao }) {
  const text = nome || descricao || 'descrição não disponível'
  return (
    <span className={`code-label ${nome || descricao ? '' : 'code-label-missing'}`}>
      <strong>{codigo || '—'}</strong>
      <span>{text}</span>
    </span>
  )
}

function MetricPair({ topLabel, topValue, bottomLabel, bottomValue }) {
  return (
    <span className="metric-pair">
      <span><small>{topLabel}</small><strong>{topValue}</strong></span>
      <span><small>{bottomLabel}</small><strong>{bottomValue}</strong></span>
    </span>
  )
}

function ImpactCard({ label, antes, depois, ganho, ganhoPct }) {
  return (
    <article className="impact-card">
      <div className="impact-card-title">
        <span>{label}</span>
        <strong>{decimalFormat(ganho)}</strong>
      </div>
      <div className="impact-flow">
        <span>
          <small>Antes</small>
          <strong>{decimalFormat(antes)}</strong>
        </span>
        <span className="impact-arrow">→</span>
        <span>
          <small>Depois</small>
          <strong>{decimalFormat(depois)}</strong>
        </span>
      </div>
      <p>Ganho da tratativa: {decimalFormat(ganho)} ({decimalFormat(ganhoPct, 1)}%)</p>
    </article>
  )
}

function Sidebar({ activePage, onChangePage, user, onLogout }) {
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
        {menuItems.filter((item) => !item.profiles || item.profiles.includes(user?.perfil)).map((item) => (
          <button
            className={activePage === item.id ? 'active' : ''}
            key={item.id}
            onClick={() => onChangePage(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>
      <div className="user-card">
        <div className="avatar">{(user?.nome || user?.login || 'AD').slice(0, 2).toUpperCase()}</div>
        <div>
          <strong>{user?.nome || 'Admin'}</strong>
          <span>{user?.perfil || 'perfil'} · {user?.login || 'local'}</span>
        </div>
        <button className="logout-button" onClick={onLogout}>Sair</button>
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

function PageHero({ eyebrow = 'MIDWAY 7.0.0', title, description, sideLabel, sideValue, sideContent }) {
  return (
    <section className="hero">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="hero-side">
        <div className="hero-panel">
          <span>{sideLabel}</span>
          <strong>{sideValue || '—'}</strong>
        </div>
        {sideContent}
      </div>
    </section>
  )
}

function MiniDatabaseStatus({ health }) {
  return (
    <div className="hero-panel hero-panel-compact">
      <span>Banco</span>
      <strong>{health?.database?.status || '—'}</strong>
      <small>
        {numberFormat(health?.database?.tables)} tabelas · {numberFormat(health?.database?.views)} views
      </small>
    </div>
  )
}

function DataTable({ columns, rows, empty = 'Nenhum item encontrado.', sortable = false, initialSort = null, onRowClick = null, rowKey = null }) {
  const [sortConfig, setSortConfig] = useState(initialSort)
  const sortedRows = useMemo(() => {
    if (!sortable || !sortConfig?.key) return rows
    const column = columns.find((item) => item.key === sortConfig.key)
    const accessor = column?.sortValue || ((row) => row[sortConfig.key])
    const direction = sortConfig.direction === 'asc' ? 1 : -1
    return [...rows].sort((left, right) => {
      const leftValue = accessor(left)
      const rightValue = accessor(right)
      const leftNumber = Number(leftValue)
      const rightNumber = Number(rightValue)
      if (!Number.isNaN(leftNumber) && !Number.isNaN(rightNumber)) {
        return (leftNumber - rightNumber) * direction
      }
      return String(leftValue ?? '').localeCompare(String(rightValue ?? ''), 'pt-BR', { numeric: true }) * direction
    })
  }, [columns, rows, sortConfig, sortable])

  function toggleSort(column) {
    if (!sortable || column.sortable === false) return
    setSortConfig((current) => {
      if (current?.key === column.key) {
        return { key: column.key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
      }
      return { key: column.key, direction: column.defaultDirection || 'desc' }
    })
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>
                {sortable && column.sortable !== false ? (
                  <button className="table-sort-button" type="button" onClick={() => toggleSort(column)}>
                    {column.label}
                    {sortConfig?.key === column.key && <span>{sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}</span>}
                  </button>
                ) : (
                  column.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row, rowIndex) => (
            <tr
              key={rowKey ? rowKey(row, rowIndex) : row.id_fila || row.id_ajuste || row.id_evento || `${rowIndex}`}
              className={onRowClick ? 'clickable-row' : ''}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((column) => (
                <td key={column.key}>
                  {column.render ? column.render(row) : textValue(row[column.key])}
                </td>
              ))}
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan={columns.length}>{empty}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function Modal({ title, children, onClose }) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <section className="modal-card">
        <div className="modal-title">
          <h2>{title}</h2>
          <button className="secondary-button" onClick={onClose}>Fechar</button>
        </div>
        {children}
      </section>
    </div>
  )
}

function KeyValueGrid({ data }) {
  if (!data) return <p>Nenhum dado encontrado.</p>
  return (
    <div className="key-grid">
      {Object.entries(data).map(([key, value]) => (
        <span key={key}>
          <small>{key}</small>
          <strong>{textValue(value)}</strong>
        </span>
      ))}
    </div>
  )
}

function OccurrenceModal({ detail, loading, onClose }) {
  return (
    <Modal title={`Ocorrência ${detail?.num_ocorrencia_adms || ''}`} onClose={onClose}>
      {loading && <div className="alert">Carregando ocorrência...</div>}
      {!loading && (
        <div className="modal-sections">
          <section>
            <h3>Resumo da Ocorrência</h3>
            <KeyValueGrid data={detail?.ocorrencia} />
          </section>
          <section>
            <h3>Interrupções Vinculadas</h3>
            <DataTable
              columns={[
                { key: 'NUM_SEQ_INTRP', label: 'Interrupção' },
                { key: 'ALIM_INTRP', label: 'Alim.' },
                { key: 'COD_COMP_INTRP', label: 'Comp.' },
                { key: 'COD_CAUSA_INTRP', label: 'Causa' },
                { key: 'VALID_POS_OPERACAO', label: 'Pós' },
                { key: 'QTD_UCS_APURADAS', label: 'UCs' },
                { key: 'QTD_LINHAS_BASE', label: 'Linhas base' },
                { key: 'DATA_HORA_INIC_INTRP', label: 'Início', render: (item) => dateTime(item.DATA_HORA_INIC_INTRP) },
              ]}
              rows={detail?.interrupcoes || []}
            />
          </section>
          <section>
            <h3>Serviços ADMS Vinculados</h3>
            <DataTable
              columns={[
                { key: 'NUM_SEQ_INTRP', label: 'Interrupção' },
                { key: 'NUM_SEQ_SERV', label: 'Serviço' },
                { key: 'INDIC_EST_SERV_SRV', label: 'Estado' },
                { key: 'COD_COMP_SRVE', label: 'Comp.' },
                { key: 'DESC_COMP_SRVE', label: 'Desc. Comp.' },
                { key: 'COD_CAUSA_SRVE', label: 'Causa' },
                { key: 'DESC_CAUSA_SRVE', label: 'Desc. Causa' },
                { key: 'DTHR_INIC_SRV', label: 'Início', render: (item) => dateTime(item.DTHR_INIC_SRV) },
                { key: 'DTHR_FECH_SRV', label: 'Fechamento', render: (item) => dateTime(item.DTHR_FECH_SRV) },
              ]}
              rows={detail?.servicos || []}
              empty="Nenhum serviço ADMS vinculado às interrupções desta ocorrência."
            />
          </section>
          <section>
            <h3>Apuração UC</h3>
            <DataTable
              columns={[
                { key: 'NUM_UC_UCI', label: 'UC' },
                { key: 'DURACAO_HORA', label: 'Duração', render: (item) => `${decimalFormat(item.DURACAO_HORA, 2)} h` },
                { key: 'CHI_LIQUIDO', label: 'CHI Liq.', render: (item) => decimalFormat(item.CHI_LIQUIDO, 2) },
                { key: 'CI_LIQUIDO', label: 'CI Liq.', render: (item) => numberFormat(item.CI_LIQUIDO) },
                { key: 'CHI_BRUTO', label: 'CHI Bruto', render: (item) => decimalFormat(item.CHI_BRUTO, 2) },
                { key: 'CI_BRUTO', label: 'CI Bruto', render: (item) => numberFormat(item.CI_BRUTO) },
                { key: 'CLASSE_TENSAO_PRODIST', label: 'Classe' },
                { key: 'GRUPO_TENSAO', label: 'Tensão' },
                { key: 'VALOR_RESSARCIMENTO', label: 'Ressarcimento', render: (item) => currencyFormat(item.VALOR_RESSARCIMENTO) },
              ]}
              rows={detail?.apuracao_uc || []}
            />
          </section>
          <section>
            <h3>Reclamações Vinculadas</h3>
            <DataTable
              columns={[
                { key: 'ID_RECLAMACAO', label: 'ID' },
                { key: 'UC', label: 'UC' },
                { key: 'TIPO_RECLAMACAO_PROVAVEL', label: 'Tipo' },
                { key: 'CAUSA_PROVAVEL_RECLAMACAO', label: 'Causa provável' },
                { key: 'SCORE_VINCULO_RECLAMACAO', label: 'Score', render: (item) => numberFormat(item.SCORE_VINCULO_RECLAMACAO) },
                { key: 'TEXTO_RECLAMACAO', label: 'Texto' },
              ]}
              rows={detail?.reclamacoes || []}
            />
          </section>
        </div>
      )}
    </Modal>
  )
}

function LoginPage({ onLogin, error, loading }) {
  const [email, setEmail] = useState('admin@midway.local')
  const [senha, setSenha] = useState('')
  const [authMode, setAuthMode] = useState('login')
  const [resetPreparadoLogin, setResetPreparadoLogin] = useState(null)
  const [resetFormLogin, setResetFormLogin] = useState({
    codigo: '',
    nova_senha: '',
  })
  const [resetMessage, setResetMessage] = useState('')
  const [resetError, setResetError] = useState('')
  const [resetLoading, setResetLoading] = useState(false)

  function submit(event) {
    event.preventDefault()
    onLogin(email, senha)
  }

  function voltarLogin() {
    setAuthMode('login')
    setResetPreparadoLogin(null)
    setResetFormLogin({ codigo: '', nova_senha: '' })
    setResetMessage('')
    setResetError('')
  }

  async function solicitarResetLogin(event) {
    event.preventDefault()
    try {
      setResetLoading(true)
      setResetError('')
      setResetMessage('')
      const response = await fetch(`${API_URL}/api/auth/reset-senha/solicitar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao solicitar troca de senha.')
      }
      setResetPreparadoLogin(result)
      setResetFormLogin({ codigo: '', nova_senha: '' })
      setResetMessage(`Código gerado para ${result.login}.`)
    } catch (requestError) {
      setResetError(requestError.message)
    } finally {
      setResetLoading(false)
    }
  }

  async function confirmarResetLogin(event) {
    event.preventDefault()
    if (!resetPreparadoLogin?.id_reset) return
    try {
      setResetLoading(true)
      setResetError('')
      setResetMessage('')
      const response = await fetch(`${API_URL}/api/auth/reset-senha/${resetPreparadoLogin.id_reset}/confirmar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(resetFormLogin),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao confirmar troca de senha.')
      }
      setSenha('')
      setResetMessage(`Senha redefinida para ${result.login}. Entre com a nova senha.`)
      setResetPreparadoLogin(null)
      setResetFormLogin({ codigo: '', nova_senha: '' })
      setAuthMode('login')
    } catch (requestError) {
      setResetError(requestError.message)
    } finally {
      setResetLoading(false)
    }
  }

  return (
    <div className="login-shell">
      <section className="login-card">
        <div className="brand login-brand">
          <div className="brand-mark">M</div>
          <div>
            <strong>MIDWAY</strong>
            <span>Governança operacional</span>
          </div>
        </div>
        <div className="login-mode-tabs">
          <button className={authMode === 'login' ? 'active' : ''} type="button" onClick={voltarLogin}>Entrar</button>
          <button className={authMode === 'reset' ? 'active' : ''} type="button" onClick={() => setAuthMode('reset')}>Trocar senha</button>
        </div>
        {authMode === 'login' ? (
          <>
            <h1>Entrar</h1>
            <p>Use seu e-mail MIDWAY. Perfis: ADM, GESTOR ou ANALISTA.</p>
            {error && <div className="alert">Erro: {error}</div>}
            {resetMessage && <div className="alert alert-success">{resetMessage}</div>}
            <form onSubmit={submit} className="login-form">
              <label>
                E-mail
                <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="username" />
              </label>
              <label>
                Senha
                <input
                  value={senha}
                  onChange={(event) => setSenha(event.target.value)}
                  type="password"
                  autoComplete="current-password"
                />
              </label>
              <button className="primary-button" disabled={loading} type="submit">
                {loading ? 'Entrando...' : 'Entrar'}
              </button>
            </form>
          </>
        ) : (
          <>
            <h1>Trocar senha</h1>
            <p>Informe seu e-mail, gere o código de confirmação e cadastre uma nova senha.</p>
            {resetError && <div className="alert">Erro: {resetError}</div>}
            {resetMessage && <div className="alert alert-success">{resetMessage}</div>}
            {!resetPreparadoLogin ? (
              <form onSubmit={solicitarResetLogin} className="login-form">
                <label>
                  E-mail
                  <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="username" required />
                </label>
                <button className="primary-button" disabled={resetLoading} type="submit">
                  {resetLoading ? 'Gerando...' : 'Gerar código'}
                </button>
              </form>
            ) : (
              <form onSubmit={confirmarResetLogin} className="login-form">
                <div className="reset-code-card">
                  <span>Código exibido</span>
                  <strong>{resetPreparadoLogin.codigo}</strong>
                  <small>E-mail: {resetPreparadoLogin.login} · expira em {dateTime(resetPreparadoLogin.expira_em)}</small>
                </div>
                <label>
                  Confirmar código
                  <input
                    value={resetFormLogin.codigo}
                    onChange={(event) => setResetFormLogin((current) => ({ ...current, codigo: event.target.value }))}
                    maxLength={4}
                    inputMode="numeric"
                    required
                  />
                </label>
                <label>
                  Nova senha
                  <input
                    value={resetFormLogin.nova_senha}
                    onChange={(event) => setResetFormLogin((current) => ({ ...current, nova_senha: event.target.value }))}
                    type="password"
                    minLength={12}
                    autoComplete="new-password"
                    required
                  />
                </label>
                <button className="primary-button" disabled={resetLoading} type="submit">
                  {resetLoading ? 'Confirmando...' : 'Confirmar troca'}
                </button>
              </form>
            )}
          </>
        )}
        <small>
          Primeiro acesso: rode `run.bat postgres_governanca` e depois `run.bat admin_bootstrap`.
        </small>
      </section>
    </div>
  )
}

function CockpitMacroPanel({ cockpit }) {
  const cockpitCards = cockpit?.cards || []

  function formatProductMetric(item) {
    if (item.unidade === 'BRL') return currencyFormat(item.valor)
    if (item.codigo === 'fec_liquido') return decimalFormat(item.valor, 2)
    if (item.codigo === 'dic_liquido') return decimalFormat(item.valor, 2)
    if (item.codigo === 'dec_liquido') return decimalFormat(item.valor, 2)
    if (item.unidade === 'hora' || item.unidade === 'hora/cons' || item.unidade === 'freq/cons') return decimalFormat(item.valor, 4)
    return numberFormat(item.valor)
  }

  return (
    <section id="dashboard-cockpit" className="panel product-section-anchor dashboard-section">
      <div className="panel-title">
        <div>
          <h2>Visão Geral</h2>
          <p>Priorização por impacto regulatório e operacional, sem substituir análise humana.</p>
        </div>
        <span className={`pill pill-${cockpit?.status === 'ok' ? 'success' : 'warning'}`}>{cockpit?.status || 'carregando'}</span>
      </div>
      {(cockpit?.alertas || []).map((alerta, index) => (
        <div className="alert" key={`${alerta.tipo}-${index}`}>{alerta.mensagem}</div>
      ))}
      <div className="metrics-grid compact">
        {cockpitCards.map((item) => (
          <Card
            key={item.codigo}
            label={item.titulo}
            value={formatProductMetric(item)}
            hint={`${item.lente} · ${item.descricao}`}
            tone={item.lente === 'regulatoria' ? 'blue' : 'orange'}
          />
        ))}
        {!cockpitCards.length && (
          <Card label="Cockpit" value="—" hint="fonte analítica indisponível no momento" tone="orange" />
        )}
      </div>
    </section>
  )
}

function RankingRegionalPanel({ cockpit }) {
  const regionalColumns = [
    { key: 'regional_exibicao', label: 'Regional' },
    { key: 'ocorrencias', label: 'Ocorrências', render: (row) => numberFormat(row.ocorrencias) },
    { key: 'ucs', label: 'UCs', render: (row) => numberFormat(row.ucs) },
    { key: 'chi_liquido', label: 'DIC/CHI líq.', render: (row) => decimalFormat(row.chi_liquido, 2) },
    { key: 'ci_liquido', label: 'FIC/CI líq.', render: (row) => numberFormat(row.ci_liquido) },
    { key: 'comp_total_prodist', label: 'Compensação', render: (row) => currencyFormat(row.comp_total_prodist) },
  ]

  return (
    <section id="dashboard-ranking-regional" className="panel product-section-anchor dashboard-section">
      <div className="panel-title">
        <div>
          <h2>Ranking regional</h2>
          <p>Ordenável por impacto de DIC/CHI, FIC/CI e compensação.</p>
        </div>
      </div>
      <DataTable
        columns={regionalColumns}
        rows={cockpit?.rankings?.regional || []}
        sortable
        initialSort={{ key: 'chi_liquido', direction: 'desc' }}
        empty="Ranking regional indisponível."
      />
    </section>
  )
}

function AjustesGovernadosPanel({
  resumo,
  modulos,
  analiseTecnicaResumos,
  suspeitasRa,
  execucoes = [],
  onAtualizarAlgoritmo,
  onAceitarAlgoritmo,
  onRejeitarAlgoritmo,
  actionDisabled = false,
  accepting = false,
  runningAlgorithm = '',
}) {
  const [algoritmoVisualizado, setAlgoritmoVisualizado] = useState(null)
  const manualModuleCodes = new Set(['GOVERNANCA_IQS', 'AJUSTE_MANUAL_IQS'])
  const modules = (modulos || []).map((module) => {
    const enriched = { ...module }
    const applyTechnicalSummary = (key) => {
      const technicalSummary = analiseTecnicaResumos?.[key]?.resumo || {}
      const total = Number(technicalSummary.QTD_OCORRENCIAS || 0)
      enriched.metricas_materializadas = total > 0 || Number(technicalSummary.RESSARCIMENTO_ESTIMADO_TOTAL || 0) > 0
      enriched.total = enriched.metricas_materializadas ? total : enriched.total
      enriched.impacto_chi = enriched.metricas_materializadas ? Number(technicalSummary.CHI_LIQUIDO_TOTAL || 0) : enriched.impacto_chi
      enriched.impacto_ci = enriched.metricas_materializadas ? Number(technicalSummary.CI_LIQUIDO_TOTAL || 0) : enriched.impacto_ci
      enriched.impacto_ressarcimento = enriched.metricas_materializadas
        ? Number(technicalSummary.RESSARCIMENTO_ESTIMADO_TOTAL || 0)
        : enriched.impacto_ressarcimento
      enriched.origem_metricas = enriched.metricas_materializadas ? 'análise técnica' : enriched.origem_metricas
    }

    if (module.codigo === 'COMPONENTE_CAUSA') applyTechnicalSummary('violacao_componente_causa')
    if (module.codigo === 'DURACAO_IMPACTO') applyTechnicalSummary('duracao_suspeita')
    if (module.codigo === 'RESSARCIMENTO_ATIPICO') applyTechnicalSummary('ressarcimento')
    if (module.codigo === 'FALHA_EQUIPAMENTO_RA') {
      const raResumo = suspeitasRa?.resumo || {}
      const total = Number(raResumo.equipamentos_dia || 0)
      enriched.metricas_materializadas = Boolean(suspeitasRa?.status) || total > 0
      enriched.total = total
      enriched.impacto_chi = Number(raResumo.chi_liquido || 0)
      enriched.impacto_ci = Number(raResumo.ci_liquido || 0)
      enriched.impacto_ressarcimento = Number(raResumo.comp_fic_estimado || 0)
      enriched.origem_metricas = 'suspeita falha RA'
    }
    if (module.codigo === 'RECLAMACOES_SERVICOS') {
      enriched.metricas_materializadas = true
      enriched.total = Number(resumo.fila_reclamacao || 0)
      enriched.origem_metricas = 'fila técnica'
    }
    enriched.metricas_materializadas = Boolean(
      enriched.metricas_materializadas ||
      Number(enriched.total || 0) > 0 ||
      Number(enriched.impacto_chi || 0) > 0 ||
      Number(enriched.impacto_ci || 0) > 0 ||
      Number(enriched.impacto_ressarcimento || 0) > 0,
    )
    return enriched
  })
  const automatedModules = modules.filter((module) => !manualModuleCodes.has(module.codigo))
  const latestExecucaoByTipo = useMemo(() => {
    const latest = new Map()
    ;(execucoes || []).forEach((execucao) => {
      const tipo = String(execucao.tipo_lote || '').toLowerCase()
      if (!tipo || latest.has(tipo)) return
      latest.set(tipo, execucao)
    })
    return latest
  }, [execucoes])
  const correcao9282Module = {
    codigo: 'CORRECAO_9282',
    nome: 'Correção especializada 92/82',
    descricao: 'Reclassificação componente/causa com evidência robusta; módulo específico, não eixo central do produto.',
    escopo: 'ocorrência/interrupção',
    documento: 'docs/modulos/correcao_9282.md',
    criterio_curto: 'serviço robusto e evidência técnica para troca de componente/causa',
    orientacao_analista: 'Verificar coerência do lote 92/82, amostra de ocorrências e impacto antes de aceitar.',
    origem_metricas: 'governança PostgreSQL',
    metricas_materializadas: true,
    total: resumo.ajustes_auto_9282,
    impacto_chi: 0,
    impacto_ci: 0,
    impacto_ressarcimento: 0,
  }

  function metricDisplay(module, value, formatter = numberFormat) {
    if (!module.metricas_materializadas && Number(value || 0) === 0) return '—'
    return formatter(value)
  }

  function detalhesAlgoritmo(module) {
    if (!module) return {}
    return {
      algoritmo: module.nome || module.codigo,
      codigo_modulo: module.codigo,
      escopo: module.escopo,
      documento: module.documento,
      origem_metricas: module.origem_metricas || 'pendente de materialização',
      quantidade_casos: metricDisplay(module, module.total),
      impacto_chi: metricDisplay(module, module.impacto_chi, (value) => decimalFormat(value, 2)),
      impacto_ci: metricDisplay(module, module.impacto_ci),
      impacto_ressarcimento: metricDisplay(module, module.impacto_ressarcimento, currencyFormat),
      regra: module.criterio_curto || module.descricao || 'Regra do módulo catalogado.',
      orientacao_aprovador: module.orientacao_analista || 'Verificar coerência do lote, impacto e risco antes de aceitar ou rejeitar.',
      decisao: 'A decisão nesta tela vale para a tratativa em massa do algoritmo, não para ocorrência isolada.',
    }
  }

  function tipoExecucaoModulo(module) {
    return EXECUCAO_MODULO_MAP[module?.codigo] || null
  }

  function ultimaExecucaoModulo(module) {
    const tipoExecucao = tipoExecucaoModulo(module)
    return tipoExecucao ? latestExecucaoByTipo.get(tipoExecucao) : null
  }

  function statusExecucaoModulo(module) {
    return String(ultimaExecucaoModulo(module)?.status_lote || '').toUpperCase()
  }

  function moduloEmExecucao(module) {
    const status = statusExecucaoModulo(module)
    return status === 'ABERTO' || status === 'PROCESSANDO'
  }

  function moduloPodeSerDecidido(module) {
    return module?.codigo === 'CORRECAO_9282' && Boolean(tipoExecucaoModulo(module)) && module.metricas_materializadas && statusExecucaoModulo(module) === 'CONCLUIDO'
  }

  function mensagemExecucao(ultimaExecucao) {
    const mensagem = String(ultimaExecucao?.mensagem || '').trim()
    if (!mensagem) return ''
    const linhas = mensagem.split('\n').map((line) => line.trim()).filter(Boolean)
    const linhaErro = [...linhas].reverse().find((line) => (
      line.includes('IO Error') ||
      line.includes('Cannot open file') ||
      line.includes('already open') ||
      line.includes('sendo usado') ||
      line.includes('PID ') ||
      line.includes('ModuleNotFoundError') ||
      line.includes('Exception:')
    ))
    const linhaUtil = linhaErro || [...linhas].reverse().find((line) => !line.startsWith('File ') && !line.startsWith('Traceback'))
    return (linhaUtil || mensagem).slice(0, 360)
  }

  function renderExecucaoStatus(module) {
    const tipoExecucao = tipoExecucaoModulo(module)
    const ultimaExecucao = ultimaExecucaoModulo(module)
    const dataReferencia = ultimaExecucao?.finalizado_em || ultimaExecucao?.iniciado_em
    const mensagem = mensagemExecucao(ultimaExecucao)
    return (
      <div className="module-run-status">
        <span><strong>Executor backend</strong><small>{tipoExecucao || 'não mapeado'}</small></span>
        <span><strong>Última atualização</strong><small>{dataReferencia ? dateTime(dataReferencia) : 'sem execução registrada'}</small></span>
        <span><strong>Status</strong><small><StatusPill value={tipoExecucao ? (ultimaExecucao?.status_lote || 'SEM EXECUÇÃO') : 'PENDENTE DE MATERIALIZAÇÃO'} /></small></span>
        <span><strong>Lote</strong><small>{ultimaExecucao?.id_lote ? String(ultimaExecucao.id_lote).slice(0, 8) : '—'}</small></span>
        {mensagem && <span className="module-run-message"><strong>Mensagem</strong><small>{mensagem}</small></span>}
      </div>
    )
  }

  function moduleCard(module, mode) {
    const isAuto = mode === 'auto'
    const updateDisabled = actionDisabled || !tipoExecucaoModulo(module) || runningAlgorithm === module.codigo
    const decisionDisabled = actionDisabled || accepting || !moduloPodeSerDecidido(module)
    return (
      <article className="module-summary-card" key={`${mode}-${module.codigo}`}>
        <div>
          <span className={`pill pill-${mode === 'auto' ? 'success' : 'warning'}`}>{mode === 'auto' ? 'algoritmo' : 'manual'}</span>
          <h3>{module.nome || module.codigo}</h3>
          <p>{module.descricao || module.criterio_curto || 'Módulo catalogado para análise governada.'}</p>
          <small className="module-summary-source">{module.origem_metricas || 'pendente de materialização'}</small>
        </div>
        <div className="module-summary-metrics">
          <span><strong>{metricDisplay(module, module.total)}</strong><small>casos</small></span>
          <span><strong>{metricDisplay(module, module.impacto_chi, (value) => decimalFormat(value, 2))}</strong><small>CHI</small></span>
          <span><strong>{metricDisplay(module, module.impacto_ci)}</strong><small>CI</small></span>
          <span><strong>{metricDisplay(module, module.impacto_ressarcimento, currencyFormat)}</strong><small>R$</small></span>
        </div>
        {isAuto && renderExecucaoStatus(module)}
        {isAuto && (
          <div className="module-action-row">
            <button className="secondary-button" type="button" onClick={() => setAlgoritmoVisualizado(module)}>
              Visualizar
            </button>
            <button className="secondary-button" type="button" disabled={updateDisabled} onClick={() => onAtualizarAlgoritmo?.(module)}>
              {runningAlgorithm === module.codigo ? 'Solicitando...' : moduloEmExecucao(module) ? 'Rodar novamente' : 'Atualizar'}
            </button>
            <button className="primary-button" type="button" disabled={decisionDisabled} onClick={() => onAceitarAlgoritmo?.(module)}>
              Aceitar
            </button>
            <button className="secondary-button danger-button" type="button" disabled={decisionDisabled} onClick={() => onRejeitarAlgoritmo?.(module)}>
              Rejeitar
            </button>
          </div>
        )}
      </article>
    )
  }

  return (
    <section className="panel dashboard-section">
      <div className="panel-title">
        <div>
          <h2>Painel de ajustes</h2>
          <p>Módulos tratados por algoritmo separados dos itens que exigem decisão humana e justificativa.</p>
        </div>
      </div>

      <div className="adjustment-panel-grid">
        <div className="adjustment-lane adjustment-lane-auto">
          <div className="compact-title">
            <h3>Automático / Algoritmos</h3>
            <p>Detecta, calcula impacto e sugere ação. Só exporta quando houver regra aprovada.</p>
          </div>
          <article className="module-summary-card module-summary-card-featured">
            <div>
              <span className="pill pill-success">exportável com governança</span>
              <h3>Correção especializada 92/82</h3>
              <p>Reclassificação componente/causa com evidência robusta; módulo específico, não eixo central do produto.</p>
              <small className="module-summary-source">governança PostgreSQL</small>
            </div>
            <div className="module-summary-metrics">
              <span><strong>{numberFormat(resumo.ajustes_auto_9282)}</strong><small>automáticos</small></span>
              <span><strong>{numberFormat(resumo.qtd_candidatos_autorizacao)}</strong><small>candidatos</small></span>
              <span><strong>{numberFormat(resumo.qtd_autorizados_autorizacao)}</strong><small>autorizados</small></span>
              <span><strong>{numberFormat(resumo.qtd_rejeitados_autorizacao)}</strong><small>rejeitados</small></span>
            </div>
            {renderExecucaoStatus(correcao9282Module)}
            <div className="module-action-row">
              <button className="secondary-button" type="button" onClick={() => setAlgoritmoVisualizado(correcao9282Module)}>
                Visualizar
              </button>
              <button className="secondary-button" type="button" disabled={actionDisabled || runningAlgorithm === correcao9282Module.codigo} onClick={() => onAtualizarAlgoritmo?.(correcao9282Module)}>
                {runningAlgorithm === correcao9282Module.codigo ? 'Solicitando...' : moduloEmExecucao(correcao9282Module) ? 'Rodar novamente' : 'Atualizar'}
              </button>
              <button className="primary-button" type="button" disabled={actionDisabled || accepting || !moduloPodeSerDecidido(correcao9282Module)} onClick={() => onAceitarAlgoritmo?.(correcao9282Module)}>
                Aceitar
              </button>
              <button className="secondary-button danger-button" type="button" disabled={actionDisabled || !moduloPodeSerDecidido(correcao9282Module)} onClick={() => onRejeitarAlgoritmo?.(correcao9282Module)}>
                Rejeitar
              </button>
            </div>
          </article>
          {automatedModules.map((module) => moduleCard(module, 'auto'))}
          {!automatedModules.length && <p className="muted-text">Catálogo de módulos automáticos ainda não carregado.</p>}
          {algoritmoVisualizado && (
            <article className="adjustment-detail-preview">
              <div className="panel-title compact-title">
                <div>
                  <h3>Visualização intermediária do algoritmo</h3>
                  <p>Dados do lote, regra aplicada e orientação antes da decisão em massa.</p>
                </div>
                <button className="secondary-button" type="button" onClick={() => setAlgoritmoVisualizado(null)}>Fechar</button>
              </div>
              <KeyValueGrid data={detalhesAlgoritmo(algoritmoVisualizado)} />
            </article>
          )}
        </div>
      </div>
    </section>
  )
}

function DashboardPage({ resumo, health, decFec, cockpit, modulos, analiseTecnicaResumos, suspeitasRa, token, onOpenOccurrence }) {
  return (
    <>
      <PageHero
        title="Visão Geral MIDWAY"
        description="História executiva dos ganhos da ferramenta: impacto regulatório, anomalias detectadas, automações, decisões humanas e prontidão para IQS."
        sideLabel="ANOMES"
        sideValue={resumo.anomes}
        sideContent={<MiniDatabaseStatus health={health} />}
      />

      <section className="panel dashboard-section">
        <div className="panel-title">
          <div>
            <h2>Fluxo da ferramenta</h2>
            <p>Leitura para gestores, Pós Operação e TI: da identificação do problema até a saída controlada para o IQS.</p>
          </div>
        </div>
        <div className="decision-steps">
          <span><strong>1</strong><em>Visão Geral</em><small>Mostra ganhos, impactos e saúde do ciclo.</small></span>
          <span><strong>2</strong><em>Anomalias</em><small>Aponta outliers e suspeitas por módulo.</small></span>
          <span><strong>3</strong><em>Análise Técnica</em><small>Investiga ocorrência, alimentador, conjunto e evidências.</small></span>
          <span><strong>4</strong><em>Automáticos</em><small>Gerencia saídas dos algoritmos aprováveis.</small></span>
          <span><strong>5</strong><em>Manuais</em><small>Registra decisão humana e justificativa.</small></span>
          <span><strong>6</strong><em>Saída IQS</em><small>Autoriza e gera o pacote final governado.</small></span>
        </div>
      </section>

      <CockpitMacroPanel cockpit={cockpit} />

      <section className="panel dashboard-section">
        <div className="panel-title">
          <div>
            <h2>DEC/FEC Antes e Depois das Tratativas</h2>
            <p>Comparativo direto do RAW antes das correções contra a apuração prévia IQS após as tratativas.</p>
          </div>
        </div>
        <div className="impact-grid">
          <ImpactCard
            label="DEC Bruto"
            antes={decFec?.dec_bruto_antes}
            depois={decFec?.dec_bruto_depois}
            ganho={decFec?.dec_bruto_ganho}
            ganhoPct={decFec?.dec_bruto_ganho_pct}
          />
          <ImpactCard
            label="FEC Bruto"
            antes={decFec?.fec_bruto_antes}
            depois={decFec?.fec_bruto_depois}
            ganho={decFec?.fec_bruto_ganho}
            ganhoPct={decFec?.fec_bruto_ganho_pct}
          />
          <ImpactCard
            label="DEC Líquido"
            antes={decFec?.dec_liquido_antes}
            depois={decFec?.dec_liquido_depois}
            ganho={decFec?.dec_liquido_ganho}
            ganhoPct={decFec?.dec_liquido_ganho_pct}
          />
          <ImpactCard
            label="FEC Líquido"
            antes={decFec?.fec_liquido_antes}
            depois={decFec?.fec_liquido_depois}
            ganho={decFec?.fec_liquido_ganho}
            ganhoPct={decFec?.fec_liquido_ganho_pct}
          />
        </div>
        <p className="panel-note">
          Premissa: RAW com `ESTADO_INTRP=4`, duração ≥ 3 min e UC faturada; líquido usa protocolo `0`.
          Fonte: {decFec?.fonte || '—'} · Linhas RAW/BDO: {numberFormat(decFec?.linhas_raw)} / {numberFormat(decFec?.linhas_bdo)}.
          A linha “Demais filtros/ajustes” fecha a diferença entre modelos identificados e ganho total.
        </p>
        <DataTable
          columns={[
            { key: 'tratamento', label: 'Tratamento' },
            { key: 'dec_bruto_ganho', label: 'DEC bruto', render: (item) => decimalFormat(item.dec_bruto_ganho) },
            { key: 'fec_bruto_ganho', label: 'FEC bruto', render: (item) => decimalFormat(item.fec_bruto_ganho) },
            { key: 'dec_liquido_ganho', label: 'DEC líq.', render: (item) => decimalFormat(item.dec_liquido_ganho) },
            { key: 'fec_liquido_ganho', label: 'FEC líq.', render: (item) => decimalFormat(item.fec_liquido_ganho) },
            { key: 'chi_bruto_ganho', label: 'CHI ganho', render: (item) => decimalFormat(item.chi_bruto_ganho, 1) },
            { key: 'ci_bruto_ganho', label: 'CI ganho', render: (item) => numberFormat(item.ci_bruto_ganho) },
          ]}
          rows={decFec?.tratamentos || []}
        />
        <p className="panel-note">
          Abertura diagnóstica: {decFec?.observacao_filtros_apuracao || 'não faturados ficam fora do DEC/FEC oficial; demais filtros explicam parte do residual.'}
        </p>
        <DataTable
          columns={[
            { key: 'tratamento', label: 'Filtro' },
            { key: 'grupo', label: 'Grupo' },
            { key: 'dec_bruto_referencia', label: 'DEC bruto ref.', render: (item) => decimalFormat(item.dec_bruto_referencia) },
            { key: 'fec_bruto_referencia', label: 'FEC bruto ref.', render: (item) => decimalFormat(item.fec_bruto_referencia) },
            { key: 'dec_liquido_referencia', label: 'DEC líq. ref.', render: (item) => decimalFormat(item.dec_liquido_referencia) },
            { key: 'fec_liquido_referencia', label: 'FEC líq. ref.', render: (item) => decimalFormat(item.fec_liquido_referencia) },
            { key: 'chi_bruto_referencia', label: 'CHI ref.', render: (item) => decimalFormat(item.chi_bruto_referencia, 1) },
            { key: 'ci_bruto_referencia', label: 'CI ref.', render: (item) => numberFormat(item.ci_bruto_referencia) },
          ]}
          rows={decFec?.filtros_apuracao || []}
        />
      </section>

      <RankingRegionalPanel cockpit={cockpit} />

      <AjustesGovernadosPanel
        resumo={resumo}
        modulos={modulos}
        analiseTecnicaResumos={analiseTecnicaResumos}
        suspeitasRa={suspeitasRa}
      />

    </>
  )
}

function ExecutivoPage({
  resumo,
  cards,
  modelosIqs,
  geracoesIqs,
  validacaoIqs,
  user,
  onAutorizar,
  onCreateGeracaoIqs,
  actionMessage,
  authorizing,
  generatingIqs,
}) {
  const canManage = hasProfile(user, ['GESTOR', 'ADM'])
  return (
    <>
      <PageHero
        title="Saída IQS"
        description="Etapa final governada: revisar impacto, autorizar alterações aprovadas e gerar o pacote físico aceito pelo IQS."
        sideLabel="Perfil"
        sideValue={user?.perfil}
      />

      {!canManage && (
        <div className="alert">Seu perfil pode consultar esta página, mas apenas GESTOR/ADM executa autorização em massa e geração IQS.</div>
      )}

      <section className="metrics-grid compact">
        {cards.map((card) => (
          <Card key={card.label} {...card} />
        ))}
      </section>

      <section className="executive-layout">
        <article className="panel executive-action-panel">
          <div className="panel-title">
            <div>
              <h2>Aprovação das Alterações</h2>
              <p>Autoriza alterações automáticas com evidência robusta. Duplicidades são ignoradas pela API.</p>
            </div>
            <button className="primary-button" disabled={!canManage || authorizing} onClick={onAutorizar}>
              {authorizing ? 'Autorizando...' : 'Autorizar alterações'}
            </button>
          </div>
          <div className="stat-list">
            <span>Candidatos na autorização: <strong>{numberFormat(resumo.qtd_candidatos_autorizacao)}</strong></span>
            <span>Autorizados: <strong>{numberFormat(resumo.qtd_autorizados_autorizacao)}</strong></span>
            <span>Rejeitados/duplicados: <strong>{numberFormat(resumo.qtd_rejeitados_autorizacao)}</strong></span>
            <span>Última autorização: <strong>{dateTime(resumo.ultima_autorizacao_em)}</strong></span>
          </div>
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <h2>Fluxo de Decisão</h2>
              <p>Sequência recomendada para fechar o lote operacional antes da implantação no IQS.</p>
            </div>
          </div>
          <div className="decision-steps">
            <span><strong>1</strong><em>Autorizar alterações</em><small>Aprovar itens automáticos com evidência robusta.</small></span>
            <span><strong>2</strong><em>Revisar pendências</em><small>Manter conflitos para apoio técnico ou análise manual.</small></span>
            <span><strong>3</strong><em>Gerar IQS</em><small>Aprovar pacote de arquivos/modelos com justificativa única.</small></span>
          </div>
        </article>
      </section>

      {actionMessage && <div className="alert alert-success">{actionMessage}</div>}

      <IqsValidationPanel validacaoIqs={validacaoIqs} />

      <IqsGenerationPanel
        modelos={modelosIqs}
        geracoes={geracoesIqs}
        user={user}
        onCreate={onCreateGeracaoIqs}
        generating={generatingIqs}
        title="Geração do Arquivo para IQS"
        description="Após a autorização em massa, selecione os modelos que compõem o pacote de envio ao IQS."
      />
    </>
  )
}

function TratativasMassaPage({
  resumo,
  modulos,
  analiseTecnicaResumos,
  suspeitasRa,
  execucoes,
  onRefresh,
  onAtualizarAlgoritmo,
  onAceitarAlgoritmo,
  onRejeitarAlgoritmo,
  accepting,
  runningAlgorithm,
  loading,
  loaded,
}) {
  if (loading || !loaded) {
    return (
      <>
        <PageHero
          title="Tratativas em Massa"
          description="Rode, atualize e revise os lotes gerados por algoritmos antes de encaminhar para aprovação governada."
          sideLabel="API"
          sideValue={loading ? 'carregando' : 'sem dados'}
        />
        <section className="panel dashboard-section">
          <div className="panel-title">
            <div>
              <h2>Aguardando carga da API</h2>
              <p>Os indicadores de tratativas em massa serão exibidos somente após a resposta atual da API.</p>
            </div>
            <button className="secondary-button" type="button" onClick={onRefresh}>Atualizar</button>
          </div>
          <div className="summary-strip">
            <span><strong>—</strong> ajustes automáticos</span>
            <span><strong>—</strong> candidatos</span>
            <span><strong>—</strong> fila técnica</span>
            <span><strong>—</strong> conflitos</span>
          </div>
        </section>
      </>
    )
  }

  return (
    <>
      <PageHero
        title="Tratativas em Massa"
        description="Rode, atualize e revise os lotes gerados por algoritmos antes de encaminhar para aprovação governada."
        sideLabel="API"
        sideValue={loading ? 'atualizando' : 'carregada'}
      />

      <section className="panel dashboard-section">
        <div className="panel-title">
          <div>
            <h2>Ciclo da tratativa em massa</h2>
            <p>O algoritmo gera o lote, o analista verifica coerência e somente os itens governados seguem para aprovação.</p>
          </div>
          <button className="secondary-button" type="button" onClick={onRefresh}>Atualizar lote</button>
        </div>
        <div className="decision-steps">
          <span><strong>1</strong><em>Rodar algoritmo</em><small>Atualiza candidatos e impactos.</small></span>
          <span><strong>2</strong><em>Verificar coerência</em><small>Compara original, sugerido e evidências.</small></span>
          <span><strong>3</strong><em>Separar exceções</em><small>Conflitos vão para ocorrência/manual.</small></span>
          <span><strong>4</strong><em>Enviar aprovação</em><small>Lote coerente segue para gestor.</small></span>
        </div>
      </section>

      <AjustesGovernadosPanel
        resumo={resumo}
        modulos={modulos}
        analiseTecnicaResumos={analiseTecnicaResumos}
        suspeitasRa={suspeitasRa}
        execucoes={execucoes}
        onAtualizarAlgoritmo={onAtualizarAlgoritmo}
        onAceitarAlgoritmo={onAceitarAlgoritmo}
        onRejeitarAlgoritmo={onRejeitarAlgoritmo}
        accepting={accepting}
        runningAlgorithm={runningAlgorithm}
      />
    </>
  )
}

function AprovacaoPage({
  resumo,
  ajustes,
  user,
  onAutorizar,
  actionMessage,
  authorizing,
  onOpenOccurrence,
}) {
  const canManage = hasProfile(user, ['GESTOR', 'ADM'])
  return (
    <>
      <PageHero
        title="Aprovação"
        description="Mesa do gestor para aprovar tratativas em massa antes de qualquer implantação ou geração de arquivo IQS."
        sideLabel="Perfil"
        sideValue={user?.perfil}
      />

      {!canManage && (
        <div className="alert">Seu perfil pode consultar esta página, mas apenas GESTOR/ADM aprova tratativas em massa.</div>
      )}

      <section className="metrics-grid compact">
        <Card label="Candidatos" value={numberFormat(resumo.qtd_candidatos_autorizacao)} hint="aguardando decisão" tone="blue" />
        <Card label="Autorizados" value={numberFormat(resumo.qtd_autorizados_autorizacao)} hint="liberados para IQS" tone="green" />
        <Card label="Rejeitados/duplicados" value={numberFormat(resumo.qtd_rejeitados_autorizacao)} hint="não implantados" tone="orange" />
        <Card label="Última autorização" value={dateTime(resumo.ultima_autorizacao_em)} hint="trilha de auditoria" tone="purple" />
      </section>

      <section className="executive-layout">
        <article className="panel executive-action-panel">
          <div className="panel-title">
            <div>
              <h2>Aprovar lote automático</h2>
              <p>Autoriza alterações automáticas com evidência robusta. Duplicidades são ignoradas pela API.</p>
            </div>
            <button className="primary-button" disabled={!canManage || authorizing} onClick={onAutorizar}>
              {authorizing ? 'Autorizando...' : 'Aprovar tratativas'}
            </button>
          </div>
          <p className="panel-note">
            Use esta ação após revisar a coerência do lote em Tratativas em Massa. Pendências devem ficar para Ocorrências ou Ajustes Manuais.
          </p>
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <h2>Regra de governança</h2>
              <p>A aprovação em massa não substitui decisão humana quando houver baixa confiança, conflito ou evidência operacional divergente.</p>
            </div>
          </div>
          <div className="decision-steps">
            <span><strong>1</strong><em>Revisar lote</em><small>Impacto e amostras coerentes.</small></span>
            <span><strong>2</strong><em>Aprovar</em><small>Gestor autoriza em massa.</small></span>
            <span><strong>3</strong><em>Liberar IQS</em><small>Somente aprovados entram no pacote.</small></span>
          </div>
        </article>
      </section>

      {actionMessage && <div className="alert alert-success">{actionMessage}</div>}

      <AjustesPage ajustes={ajustes} resumo={resumo} onOpenOccurrence={onOpenOccurrence} embedded />
    </>
  )
}

function SaidaIqsPage({
  modelosIqs,
  geracoesIqs,
  validacaoIqs,
  user,
  onCreateGeracaoIqs,
  generatingIqs,
}) {
  return (
    <>
      <PageHero
        title="Saída IQS"
        description="Última etapa operacional: validar pré-requisitos e gerar o pacote físico no padrão aceito pelo IQS."
        sideLabel="Perfil"
        sideValue={user?.perfil}
      />

      <IqsValidationPanel validacaoIqs={validacaoIqs} />

      <IqsGenerationPanel
        modelos={modelosIqs}
        geracoes={geracoesIqs}
        user={user}
        onCreate={onCreateGeracaoIqs}
        generating={generatingIqs}
        title="Geração do Arquivo para IQS"
        description="Gere somente após aprovação governada das tratativas. O pacote físico deve respeitar layout, encoding, datas e quebras exigidas pelo IQS."
      />
    </>
  )
}

function FilaPreview({ anomes, token, onOpenOccurrence }) {
  const [tipo, setTipo] = useState('ocorrencia')
  const [valor, setValor] = useState('')
  const [resultados, setResultados] = useState([])
  const [buscando, setBuscando] = useState(false)
  const [buscaErro, setBuscaErro] = useState('')
  const [buscaRealizada, setBuscaRealizada] = useState(false)

  async function handleBuscar(event) {
    event.preventDefault()
    if (!valor.trim()) {
      setBuscaErro('Informe uma ocorrência, interrupção ou UC para pesquisar.')
      return
    }

    try {
      setBuscando(true)
      setBuscaErro('')
      setBuscaRealizada(true)
      const params = new URLSearchParams({
        tipo,
        valor: valor.trim(),
        anomes: anomes || '202606',
        limit: '20',
      })
      const response = await fetch(`${API_URL}/api/qualidade/busca?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao executar a busca técnica.')
      }
      setResultados(result)
    } catch (requestError) {
      setBuscaErro(requestError.message)
      setResultados([])
    } finally {
      setBuscando(false)
    }
  }

  return (
    <section className="panel">
      <div className="panel-title">
        <div>
          <h2>Busca</h2>
          <p>Pesquise por ocorrência, interrupção ou UC e abra painéis expansíveis para investigação.</p>
        </div>
      </div>
      <form className="search-panel" onSubmit={handleBuscar}>
        <label>
          Tipo de busca
          <select value={tipo} onChange={(event) => setTipo(event.target.value)}>
            <option value="ocorrencia">Ocorrência</option>
            <option value="interrupcao">Interrupção</option>
            <option value="uc">UC</option>
          </select>
        </label>
        <label>
          Valor
          <input
            value={valor}
            onChange={(event) => setValor(event.target.value)}
            placeholder="Digite o número para localizar"
          />
        </label>
        <button type="submit" disabled={buscando}>
          {buscando ? 'Buscando...' : 'Buscar'}
        </button>
      </form>
      {buscaErro && <div className="alert">{buscaErro}</div>}
      {!buscando && buscaRealizada && !resultados.length && !buscaErro && (
        <div className="alert">Nenhum registro encontrado para a busca informada.</div>
      )}
      <div className="accordion-list">
        {resultados.map((item, index) => (
          <details className="result-accordion" key={`${item.NUM_OCORRENCIA_ADMS}-${index}`} open={index === 0}>
            <summary>
              <strong>Ocorrência {item.NUM_OCORRENCIA_ADMS}</strong>
              <span>
                {numberFormat(item.QTD_INTERRUPCOES)} interrupção(ões) · {numberFormat(item.QTD_UCS_APURACAO)} UC(s) · {numberFormat(item.QTD_RECLAMACOES)} reclamação(ões)
              </span>
            </summary>
            <div className="result-grid">
              <span><small>Período</small><strong>{dateTime(item.PRIMEIRO_INICIO)} → {dateTime(item.ULTIMO_FIM)}</strong></span>
              <span><small>Componente/Causa</small><strong>{textValue(item.PARES_COMPONENTE_CAUSA)}</strong></span>
              <span><small>CHI líquido</small><strong>{decimalFormat(item.CHI_LIQUIDO, 2)}</strong></span>
              <span><small>CI líquido</small><strong>{numberFormat(item.CI_LIQUIDO)}</strong></span>
              <span><small>Score reclamação</small><strong>{numberFormat(item.MAX_SCORE_RECLAMACAO)}</strong></span>
              <span><small>Grupos IQS</small><strong>{textValue(item.GRUPOS_COMPONENTE_IQS || item.GRUPOS_CAUSA_IQS)}</strong></span>
            </div>
            <div className="result-text">
              <strong>Interrupções:</strong> {textValue(item.INTERRUPCOES)}
            </div>
            <div className="result-text">
              <strong>Reclamações:</strong> {textValue(item.TIPOS_RECLAMACAO)} · {textValue(item.CAUSAS_RECLAMACAO)}
            </div>
            <button className="secondary-button" onClick={() => onOpenOccurrence(item.NUM_OCORRENCIA_ADMS)}>
              Abrir ocorrência completa
            </button>
          </details>
        ))}
      </div>
    </section>
  )
}

function AnomalyDetailModal({ detail, loading, onClose, onRegisterDecision }) {
  const suggestion = detail?.sugestao || {}
  const impact = detail?.impacto || {}
  return (
    <Modal title={`Anomalia ${detail?.id_anomalia || ''}`} onClose={onClose}>
      {loading && <div className="alert">Carregando anomalia...</div>}
      {!loading && detail && (
        <div className="modal-sections">
          <section className="anomaly-detail-head">
            <div>
              <h3>{detail.nome}</h3>
              <p>{detail.explicacao_simples}</p>
              <div className="tag-list">
                <SeverityBadge value={detail.severidade} />
                <ConfidenceBadge value={detail.confianca} />
                <StatusPill value={detail.status} />
                <span className="pill pill-success">{detail.modulo?.codigo || detail.categoria}</span>
                <span className="pill pill-info">{detail.categoria}</span>
              </div>
            </div>
            <div className="decision-box">
              <strong>{suggestion.acao || 'sem sugestão'}</strong>
              <span>{suggestion.justificativa || '—'}</span>
              <div className="row-actions">
                <button className="mini-button mini-button-success" onClick={() => onRegisterDecision(detail, 'aprovar')}>
                  Propor aprovação
                </button>
                <button className="mini-button mini-button-danger" onClick={() => onRegisterDecision(detail, 'rejeitar')}>
                  Propor rejeição
                </button>
              </div>
            </div>
          </section>

          <section className="content-grid">
            <div className="panel">
              <div className="panel-title">
                <div>
                  <h3>Módulo de anomalia</h3>
                  <p>{detail.modulo?.descricao || 'Módulo não classificado.'}</p>
                </div>
              </div>
              <KeyValueGrid
                data={{
                  codigo: detail.modulo?.codigo,
                  nome: detail.modulo?.nome,
                  escopo: detail.modulo?.escopo,
                  criterio: detail.modulo?.criterio_curto,
                  orientacao_analista: detail.modulo?.orientacao_analista,
                  documento: detail.modulo?.documento,
                }}
              />
            </div>

            <div className="panel">
              <div className="panel-title">
                <div>
                  <h3>Explicação técnica</h3>
                  <p>{detail.explicacao_tecnica}</p>
                </div>
              </div>
              <KeyValueGrid
                data={{
                  regra_violada: detail.regra_violada,
                  impacto_possivel: detail.impacto_possivel,
                  campos_envolvidos: (detail.campos_envolvidos || []).join(', '),
                  registro_id: detail.registro_id,
                  ocorrencia: detail.ocorrencia,
                  interrupcao: detail.interrupcao,
                }}
              />
            </div>

            <div className="panel">
              <div className="panel-title">
                <div>
                  <h3>Impacto estimado</h3>
                  <p>Valores calculados a partir do processamento RAW, SILVER e GOLD.</p>
                </div>
              </div>
              <div className="stat-list">
                <span><strong>DEC</strong> {decimalFormat(impact.dec)}</span>
                <span><strong>FEC</strong> {decimalFormat(impact.fec)}</span>
                <span><strong>DIC</strong> {decimalFormat(impact.dic, 2)}</span>
                <span><strong>FIC</strong> {decimalFormat(impact.fic, 2)}</span>
                <span><strong>Ressarcimento</strong> {currencyFormat(impact.ressarcimento)}</span>
              </div>
            </div>
          </section>

          <section className="comparison-grid">
            <div className="panel">
              <h3>Original</h3>
              <KeyValueGrid data={detail.original} />
            </div>
            <div className="panel">
              <h3>Sugerido</h3>
              <KeyValueGrid data={detail.tratado_sugerido} />
            </div>
          </section>

          <section className="content-grid">
            <div className="panel">
              <h3>Evidências</h3>
              <DataTable
                columns={[
                  { key: 'campo', label: 'Campo' },
                  { key: 'valor', label: 'Valor' },
                  { key: 'origem', label: 'Origem' },
                ]}
                rows={detail.evidencias || []}
              />
            </div>
            <div className="panel">
              <h3>Linha do tempo</h3>
              <div className="timeline-list">
                {(detail.linha_tempo || []).map((item) => (
                  <span key={`${item.momento}-${item.evento}`}>
                    <small>{dateTime(item.momento)}</small>
                    <strong>{item.evento}</strong>
                  </span>
                ))}
              </div>
            </div>
          </section>
        </div>
      )}
    </Modal>
  )
}

function AnomaliasPage({ resumo, items, modulos, suspeitasRa, loading, onOpenDetail }) {
  const total = Number(resumo?.total || 0)
  const [tipoAtivo, setTipoAtivo] = useState('todos')
  const [anomaliaSelecionadaId, setAnomaliaSelecionadaId] = useState('')
  const [notaDecisao, setNotaDecisao] = useState('')

  function posStatus(item) {
    const valor = String(item.valid_pos_operacao || item.VALID_POS_OPERACAO || '').trim().toUpperCase()
    if (['S', 'SIM', 'VALIDO', 'VÁLIDO', 'TRUE', '1'].includes(valor)) return 'validado'
    if (['N', 'NAO', 'NÃO', 'INVALIDO', 'INVÁLIDO', 'FALSE', '0'].includes(valor)) return 'nao_validado'
    return 'sem_info'
  }

  const anomaliasPorSeveridade = useMemo(() => {
    const base = { critica: 0, alta: 0, media: 0, baixa: 0 }
    ;(items || []).forEach((item) => {
      const severidade = String(item.severidade || '').toLowerCase()
      if (severidade.includes('crítica') || severidade.includes('critica')) base.critica += 1
      else if (severidade.includes('alta')) base.alta += 1
      else if (severidade.includes('média') || severidade.includes('media')) base.media += 1
      else base.baixa += 1
    })
    return base
  }, [items])
  const tiposAnomalia = useMemo(() => {
    const moduleRows = (modulos || []).filter((modulo) => Number(modulo.total || 0) > 0)
    if (moduleRows.length) {
      return [
        { id: 'todos', label: 'Todos os módulos', total, descricao: 'Visão geral das suspeitas.' },
        ...moduleRows
          .sort((a, b) => Number(b.total || 0) - Number(a.total || 0) || String(a.nome).localeCompare(String(b.nome)))
          .map((modulo) => ({
            id: modulo.codigo,
            label: modulo.nome,
            total: modulo.total,
            descricao: modulo.descricao,
            orientacao: modulo.orientacao_analista,
            impacto: modulo.impacto || [],
            documento: modulo.documento,
          })),
      ]
    }
    const mapa = new Map()
    ;(items || []).forEach((item) => {
      const categoria = item.modulo_codigo || item.categoria || item.anomalia_codigo || 'Outras'
      mapa.set(categoria, {
        label: item.modulo_nome || item.categoria || item.anomalia_codigo || 'Outras',
        total: (mapa.get(categoria)?.total || 0) + 1,
        descricao: item.modulo_descricao,
        orientacao: item.modulo_orientacao,
      })
    })
    return [
      { id: 'todos', label: 'Todos os módulos', total, descricao: 'Visão geral das suspeitas.' },
      ...Array.from(mapa.entries())
        .sort((a, b) => b[1].total - a[1].total || String(a[1].label).localeCompare(String(b[1].label)))
        .map(([id, data]) => ({ id, label: data.label, total: data.total, descricao: data.descricao, orientacao: data.orientacao })),
    ]
  }, [items, modulos, total])
  const itensFiltrados = useMemo(() => {
    return (items || []).filter((item) => {
      return tipoAtivo === 'todos' || item.modulo_codigo === tipoAtivo || item.categoria === tipoAtivo || item.anomalia_codigo === tipoAtivo
    })
  }, [items, tipoAtivo])
  const topAnomalias = useMemo(() => {
    return [...itensFiltrados]
      .sort((a, b) => {
        const impactoB = Number(b.impacto_ressarcimento || 0) + Number(b.impacto_dec || 0) * 1000
        const impactoA = Number(a.impacto_ressarcimento || 0) + Number(a.impacto_dec || 0) * 1000
        return impactoB - impactoA
      })
      .slice(0, 12)
  }, [itensFiltrados])
  const anomaliaSelecionada = useMemo(() => {
    return topAnomalias.find((item) => item.id_anomalia === anomaliaSelecionadaId) || topAnomalias[0] || null
  }, [anomaliaSelecionadaId, topAnomalias])
  const posResumo = useMemo(() => {
    return (items || []).reduce(
      (acc, item) => {
        acc[posStatus(item)] += 1
        return acc
      },
      { validado: 0, nao_validado: 0, sem_info: 0 },
    )
  }, [items])
  const moduloAtivo = useMemo(() => {
    return tiposAnomalia.find((tipo) => tipo.id === tipoAtivo) || tiposAnomalia[0] || null
  }, [tipoAtivo, tiposAnomalia])
  const timelineResumo = useMemo(() => {
    if (!anomaliaSelecionada) return []
    return [
      { label: 'Detecção', value: dateTime(anomaliaSelecionada.criado_em), tone: 'info' },
      { label: 'Registro', value: textValue(anomaliaSelecionada.registro_id), tone: 'blue' },
      { label: 'Ocorrência', value: textValue(anomaliaSelecionada.ocorrencia || anomaliaSelecionada.interrupcao || anomaliaSelecionada.uc), tone: 'warning' },
      { label: 'Sugestão', value: textValue(anomaliaSelecionada.acao_sugerida), tone: 'success' },
    ]
  }, [anomaliaSelecionada])
  return (
    <>
      <PageHero
        eyebrow="Triagem"
        title="Anomalias"
        description="Mesa de investigação por módulo: priorize suspeitas, veja evidências e encaminhe a decisão humana sem navegar por tabelas extensas."
        sideLabel="Fonte dos dados"
        sideValue={resumo?.fonte || 'RAW/SILVER/GOLD'}
      />

      <div className="metrics-grid compact">
        <Card label="Anomalias" value={numberFormat(total)} hint="suspeitas materializadas" tone="blue" />
        <Card label="Pendentes" value={numberFormat(resumo?.pendentes)} hint={`${percent(resumo?.pendentes, total)} aguardando decisão`} tone="orange" />
        <Card label="Alto risco" value={numberFormat(resumo?.alto_risco)} hint="alta ou crítica" tone="purple" />
        <Card label="Impacto estimado" value={currencyFormat(resumo?.impacto_ressarcimento)} hint="ressarcimento em anomalias" tone="green" />
      </div>

      <section className="panel dashboard-section">
        <div className="decision-steps">
          <span><strong>1</strong><em>Detectar</em><small>Agentes localizam outliers por módulo.</small></span>
          <span><strong>2</strong><em>Priorizar</em><small>Impacto, severidade e confiança ordenam a fila.</small></span>
          <span><strong>3</strong><em>Evidenciar</em><small>Analista confere regra, origem e Pós Operação.</small></span>
          <span><strong>4</strong><em>Decidir</em><small>Proposta manual ou automática segue governança.</small></span>
        </div>
      </section>

      <section className="anomaly-triage-shell">
        <aside className="panel anomaly-module-sidebar">
          <div className="compact-title">
            <h2>Módulos</h2>
            <p>Escolha o tipo de suspeita para filtrar a investigação.</p>
          </div>
          <div className="anomaly-module-list">
            {tiposAnomalia.map((tipo) => (
              <button
                key={tipo.id}
                className={tipoAtivo === tipo.id ? 'active' : ''}
                onClick={() => {
                  setTipoAtivo(tipo.id)
                  setAnomaliaSelecionadaId('')
                }}
              >
                <span>
                  <strong>{tipo.label}</strong>
                  <small>{tipo.descricao || 'Suspeitas do módulo.'}</small>
                </span>
                <em>{numberFormat(tipo.total)}</em>
              </button>
            ))}
          </div>
          <div className="anomaly-mini-summary">
            <span><strong>{numberFormat(posResumo.validado)}</strong><small>validado Pós</small></span>
            <span><strong>{numberFormat(posResumo.sem_info)}</strong><small>sem info Pós</small></span>
          </div>
        </aside>

        <section className="panel anomaly-results-panel">
          <div className="panel-title">
            <div>
              <span className="pill pill-info">{moduloAtivo?.id || 'todos'}</span>
              <h2>{moduloAtivo?.label || 'Suspeitas priorizadas'}</h2>
              <p>{numberFormat(itensFiltrados.length)} caso(s) no recorte. {moduloAtivo?.descricao || 'Selecione um caso para montar o dossiê.'}</p>
            </div>
          </div>
          {loading && <div className="alert">Carregando anomalias...</div>}
          <div className="anomaly-priority-list">
            {topAnomalias.map((item, index) => (
              <button
                className={`anomaly-priority-card ${anomaliaSelecionada?.id_anomalia === item.id_anomalia ? 'active' : ''}`}
                key={item.id_anomalia || item.anomalia_codigo}
                onClick={() => setAnomaliaSelecionadaId(item.id_anomalia)}
              >
                <span className="anomaly-rank">{index + 1}</span>
                <span className="anomaly-priority-main">
                  <strong>{item.nome || item.categoria || item.anomalia_codigo}</strong>
                  <small>{item.modulo_nome || item.modulo_codigo || 'Sem módulo'} · {item.anomalia_codigo || 'sem código'}</small>
                  <small>Ocorrência {textValue(item.ocorrencia)} · Conjunto {textValue(item.conjunto)}</small>
                </span>
                <span className="anomaly-priority-metrics">
                  <SeverityBadge value={item.severidade} />
                  <small>{decimalFormat(Number(item.confianca || 0) * 100, 1)}% confiança</small>
                  <small>{currencyFormat(item.impacto_ressarcimento)}</small>
                </span>
              </button>
            ))}
            {!topAnomalias.length && <p className="muted-text">Nenhuma anomalia no recorte escolhido.</p>}
          </div>
        </section>

        <aside className="panel anomaly-dossier-panel">
          <div className="panel-title compact-title">
            <div>
              <h2>Dossiê da suspeita</h2>
              <p>{anomaliaSelecionada ? 'Resumo para decisão e aprofundamento.' : 'Selecione uma suspeita no centro.'}</p>
            </div>
            {anomaliaSelecionada && <StatusPill value={anomaliaSelecionada.status} />}
          </div>

          {anomaliaSelecionada ? (
            <>
              <div className="anomaly-dossier-head">
                <strong>{anomaliaSelecionada.nome || anomaliaSelecionada.anomalia_codigo}</strong>
                <p>{anomaliaSelecionada.descricao || 'Sem descrição resumida.'}</p>
                <div className="tag-list">
                  <span className="pill pill-success">{anomaliaSelecionada.modulo_codigo || 'módulo não informado'}</span>
                  <span className="pill pill-info">{anomaliaSelecionada.origem || 'origem não informada'}</span>
                  <span className="pill">Pós {posStatus(anomaliaSelecionada).replace('_', ' ')}</span>
                </div>
              </div>

              <div className="anomaly-dossier-metrics">
                <span><small>Confiança</small><strong>{decimalFormat(Number(anomaliaSelecionada.confianca || 0) * 100, 1)}%</strong></span>
                <span><small>DEC</small><strong>{decimalFormat(anomaliaSelecionada.impacto_dec)}</strong></span>
                <span><small>FIC</small><strong>{decimalFormat(anomaliaSelecionada.impacto_fic, 2)}</strong></span>
                <span><small>R$</small><strong>{currencyFormat(anomaliaSelecionada.impacto_ressarcimento)}</strong></span>
              </div>

              <div className="decision-box">
                <strong>O que verificar</strong>
                <span>{anomaliaSelecionada.modulo_orientacao || moduloAtivo?.orientacao || 'Revisar evidências, impacto e recomendação antes de decidir.'}</span>
              </div>

              <div className="anomaly-timeline">
                {timelineResumo.map((item) => (
                  <span key={item.label} className={`timeline-dot timeline-dot-${item.tone}`}>
                    <small>{item.label}</small>
                    <strong>{item.value}</strong>
                  </span>
                ))}
              </div>

              <label className="anomaly-note">
                Nota técnica
                <textarea value={notaDecisao} onChange={(event) => setNotaDecisao(event.target.value)} placeholder="Registre hipótese, evidência pendente ou encaminhamento..." />
              </label>

              <div className="row-actions">
                <button className="primary-button" onClick={() => onOpenDetail(anomaliaSelecionada.id_anomalia)}>
                  Abrir detalhe/decisão
                </button>
                <button className="secondary-button" onClick={() => setNotaDecisao('')}>
                  Limpar nota
                </button>
              </div>
            </>
          ) : (
            <p className="muted-text">Sem anomalia selecionada.</p>
          )}
        </aside>
      </section>

      <section className="anomaly-support-grid">
        <details className="panel anomaly-support-panel">
          <summary>Agente específico: Suspeita falha RA</summary>
          <SuspeitaRaPanel suspeitasRa={suspeitasRa} />
        </details>

        <section className="panel anomaly-chart-panel">
          <div className="panel-title compact-title">
            <div>
              <h2>Distribuição por módulo</h2>
              <p>Visão de volume para priorização gerencial.</p>
            </div>
          </div>
          <div className="anomaly-bar-list">
            {tiposAnomalia.filter((tipo) => tipo.id !== 'todos').slice(0, 8).map((tipo) => (
              <span key={tipo.id}>
                <small>{tipo.label}</small>
                <strong style={{ width: `${Math.max(8, (tipo.total / Math.max(total, 1)) * 100)}%` }}>{numberFormat(tipo.total)}</strong>
              </span>
            ))}
          </div>
        </section>
      </section>
    </>
  )
}

function AnaliseImpactoPanel({ anomes, token, onOpenOccurrence }) {
  const filtrosPadrao = {
    min_chi: '',
    min_ci: '',
    min_ressarcimento: '',
    componente: '',
    causa: '',
    grupo: '',
    problema: 'impacto',
    duracao_suspeita_min: '24',
    limit: '50',
  }
  const [filtros, setFiltros] = useState(filtrosPadrao)
  const [resumo, setResumo] = useState({})
  const [itens, setItens] = useState([])
  const [fonte, setFonte] = useState('')
  const [opcoesReferencia, setOpcoesReferencia] = useState({ grupos: [], componentes: [], causas: [] })
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState('')

  function optionLabel(item) {
    const descricao = item.descricao ? ` - ${item.descricao}` : ''
    return `${item.codigo}${descricao}`
  }

  const componentesFiltrados = useMemo(() => {
    const componentes = opcoesReferencia.componentes || []
    if (!filtros.grupo) return componentes
    return componentes.filter((item) => item.grupo_codigo === filtros.grupo)
  }, [filtros.grupo, opcoesReferencia.componentes])

  const causasFiltradas = useMemo(() => {
    const causas = opcoesReferencia.causas || []
    return causas.filter((item) => {
      if (filtros.grupo && item.grupo_codigo !== filtros.grupo) return false
      if (filtros.componente && item.componente_codigo !== filtros.componente) return false
      return true
    })
  }, [filtros.componente, filtros.grupo, opcoesReferencia.causas])
  const topCasosTecnicos = useMemo(() => [...(itens || [])].slice(0, 3), [itens])
  const criteriosAtivos = useMemo(() => {
    const criterios = []
    if (filtros.problema && filtros.problema !== 'impacto') criterios.push(`Problema: ${filtros.problema}`)
    if (filtros.grupo) criterios.push(`Grupo ${filtros.grupo}`)
    if (filtros.componente) criterios.push(`Componente ${filtros.componente}`)
    if (filtros.causa) criterios.push(`Causa ${filtros.causa}`)
    if (filtros.min_chi) criterios.push(`CHI ≥ ${filtros.min_chi}`)
    if (filtros.min_ci) criterios.push(`CI ≥ ${filtros.min_ci}`)
    if (filtros.min_ressarcimento) criterios.push(`R$ ≥ ${filtros.min_ressarcimento}`)
    if (filtros.duracao_suspeita_min) criterios.push(`Duração ≥ ${filtros.duracao_suspeita_min}h`)
    return criterios.length ? criterios : ['Maior impacto', 'Duração ≥ 24h', `Limite ${filtros.limit}`]
  }, [filtros])

  function updateFiltro(campo, valor) {
    setFiltros((current) => {
      const next = { ...current, [campo]: valor }
      if (campo === 'grupo') {
        next.componente = ''
        next.causa = ''
      }
      if (campo === 'componente') {
        next.causa = ''
      }
      return next
    })
  }

  async function carregar(filtrosAtuais = filtros) {
    try {
      setLoading(true)
      setErro('')
      const params = new URLSearchParams({
        anomes: anomes || '202606',
        problema: filtrosAtuais.problema || 'impacto',
        duracao_suspeita_min: normalizeDecimalParam(filtrosAtuais.duracao_suspeita_min) || '24',
        limit: filtrosAtuais.limit || '50',
      })
      ;['componente', 'causa', 'grupo'].forEach((campo) => {
        if (String(filtrosAtuais[campo] || '').trim()) {
          params.set(campo, String(filtrosAtuais[campo]).trim())
        }
      })
      ;['min_chi', 'min_ci', 'min_ressarcimento'].forEach((campo) => {
        const valorNormalizado = normalizeDecimalParam(filtrosAtuais[campo])
        if (valorNormalizado) {
          params.set(campo, valorNormalizado)
        }
      })
      const response = await fetch(`${API_URL}/api/qualidade/analise-tecnica?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao carregar ranking técnico.')
      }
      setResumo(result.resumo || {})
      setItens(result.itens || [])
      setFonte(result.fonte || '')
    } catch (requestError) {
      setErro(requestError.message)
      setResumo({})
      setItens([])
      setFonte('')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (token) {
      carregar(filtrosPadrao)
    }
  }, [anomes, token])

  useEffect(() => {
    if (!token) return

    async function carregarOpcoesReferencia() {
      try {
        const params = new URLSearchParams({ anomes: anomes || '202606' })
        const response = await fetch(`${API_URL}/api/qualidade/analise-tecnica/opcoes?${params.toString()}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        })
        const result = await response.json()
        if (response.ok) {
          setOpcoesReferencia({
            grupos: result.grupos || [],
            componentes: result.componentes || [],
            causas: result.causas || [],
          })
        }
      } catch {
        setOpcoesReferencia({ grupos: [], componentes: [], causas: [] })
      }
    }

    carregarOpcoesReferencia()
  }, [anomes, token])

  function submit(event) {
    event.preventDefault()
    carregar()
  }

  function limpar() {
    setFiltros(filtrosPadrao)
    carregar(filtrosPadrao)
  }

  return (
    <section className="panel panel-large">
      <div className="panel-title">
        <div>
          <h2>Priorização por Impacto</h2>
          <p>Filtre as maiores distorções por CHI, CI, ressarcimento, duração suspeita e violação rígida de componente/causa.</p>
        </div>
        <button className="secondary-button" onClick={() => carregar()} disabled={loading}>
          {loading ? 'Atualizando...' : 'Atualizar ranking'}
        </button>
      </div>

      <form className="analysis-filter-grid" onSubmit={submit}>
        <label>
          Problema
          <select value={filtros.problema} onChange={(event) => updateFiltro('problema', event.target.value)}>
            <option value="impacto">Maior impacto</option>
            <option value="9282">Componente/Causa crítica</option>
            <option value="violacao_componente_causa">Violação componente/causa</option>
            <option value="duracao_suspeita">Duração suspeita</option>
            <option value="ressarcimento">Com ressarcimento</option>
            <option value="todos">Todos</option>
          </select>
        </label>
        <label>
          CHI mín.
          <input inputMode="decimal" value={filtros.min_chi} onChange={(event) => updateFiltro('min_chi', event.target.value)} placeholder="Ex.: 1.000,50" />
        </label>
        <label>
          CI mín.
          <input inputMode="decimal" value={filtros.min_ci} onChange={(event) => updateFiltro('min_ci', event.target.value)} placeholder="Ex.: 1.000" />
        </label>
        <label>
          Ressarcimento mín.
          <input inputMode="decimal" value={filtros.min_ressarcimento} onChange={(event) => updateFiltro('min_ressarcimento', event.target.value)} placeholder="Ex.: 10.000,00" />
        </label>
        <label>
          Duração suspeita ≥ h
          <input inputMode="decimal" value={filtros.duracao_suspeita_min} onChange={(event) => updateFiltro('duracao_suspeita_min', event.target.value)} placeholder="Ex.: 24,5" />
        </label>
        <label>
          Grupo comp./causa (GCR)
          <select value={filtros.grupo} onChange={(event) => updateFiltro('grupo', event.target.value)}>
            <option value="">Todos os grupos</option>
            {opcoesReferencia.grupos.map((item) => (
              <option key={item.codigo} value={item.codigo}>
                {optionLabel(item)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Componente
          <select value={filtros.componente} onChange={(event) => updateFiltro('componente', event.target.value)}>
            <option value="">Todos os componentes</option>
            {componentesFiltrados.map((item) => (
              <option key={`${item.grupo_codigo}-${item.codigo}`} value={item.codigo}>
                {optionLabel(item)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Causa
          <select value={filtros.causa} onChange={(event) => updateFiltro('causa', event.target.value)}>
            <option value="">Todas as causas</option>
            {causasFiltradas.map((item) => (
              <option key={`${item.grupo_codigo}-${item.componente_codigo}-${item.codigo}`} value={item.codigo}>
                {optionLabel(item)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Limite
          <select value={filtros.limit} onChange={(event) => updateFiltro('limit', event.target.value)}>
            <option value="25">25</option>
            <option value="50">50</option>
            <option value="100">100</option>
            <option value="200">200</option>
          </select>
        </label>
        <div className="analysis-filter-actions">
          <button type="button" className="secondary-button" onClick={limpar} disabled={loading}>
            Limpar
          </button>
          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? 'Filtrando...' : 'Aplicar filtros'}
          </button>
        </div>
      </form>

      {erro && <div className="alert">Erro: {erro}</div>}

      <section className="metrics-grid compact">
        <Card label="Ocorrências" value={numberFormat(resumo.QTD_OCORRENCIAS)} hint="após filtros" tone="blue" />
        <Card label="CHI líquido" value={decimalFormat(resumo.CHI_LIQUIDO_TOTAL, 1)} hint="impacto filtrado" tone="orange" />
        <Card label="CI líquido" value={numberFormat(resumo.CI_LIQUIDO_TOTAL)} hint="impacto filtrado" tone="purple" />
        <Card label="Ressarcimento" value={currencyFormat(resumo.RESSARCIMENTO_ESTIMADO_TOTAL)} hint="estimado PRODIST" tone="green" />
      </section>

      <div className="analysis-summary-strip">
        <span><strong>{numberFormat(resumo.QTD_OCORRENCIAS_COM_VIOLACAO)}</strong> ocorrência(s) com violação componente/causa</span>
        <span><strong>{numberFormat(resumo.QTD_OCORRENCIAS_9282)}</strong> ocorrência(s) com componente/causa crítica</span>
        <span><strong>{numberFormat(resumo.QTD_DURACAO_SUSPEITA)}</strong> ocorrência(s) com duração suspeita</span>
        <span><strong>{fonte === 'cache' ? 'Cache' : 'Ao vivo'}</strong> fonte · score máx. {decimalFormat(resumo.MAIOR_IMPACTO_SCORE, 1)}</span>
      </div>

      <section className="technical-case-deck">
        <article className="investigation-card investigation-card-wide">
          <div className="panel-title compact-title">
            <div>
              <h2>Casos que merecem leitura humana</h2>
              <p>Inspirado nos cards do v1: antes da planilha, mostre impacto, sinais e caminho de decisão.</p>
            </div>
          </div>
          <div className="technical-card-grid">
            {topCasosTecnicos.map((item) => (
              <article className="technical-case-card" key={item.NUM_OCORRENCIA_ADMS}>
                <div className="technical-case-head">
                  <button className="link-button" onClick={() => onOpenOccurrence(item.NUM_OCORRENCIA_ADMS)}>
                    Ocorrência {item.NUM_OCORRENCIA_ADMS}
                  </button>
                  <strong>{decimalFormat(item.IMPACTO_SCORE, 1)}</strong>
                </div>
                <div className="tag-list">
                  {Number(item.TEM_9282 || 0) > 0 && <span className="pill">Comp/Causa</span>}
                  {Number(item.QTD_VIOLACAO_COMP_CAUSA || 0) > 0 && <span className="pill pill-danger">Violação</span>}
                  {Number(item.RESSARCIMENTO_ESTIMADO || 0) > 0 && <span className="pill pill-money">Ressarcimento</span>}
                </div>
                <div className="case-metric-grid">
                  <span><small>CHI</small><strong>{decimalFormat(item.CHI_LIQUIDO, 2)}</strong></span>
                  <span><small>CI/FIC</small><strong>{numberFormat(item.CI_LIQUIDO)}</strong></span>
                  <span><small>Ressarc.</small><strong>{currencyFormat(item.RESSARCIMENTO_ESTIMADO)}</strong></span>
                  <span><small>Duração</small><strong>{decimalFormat(item.DURACAO_MAX_HORA, 1)}h</strong></span>
                </div>
                <p>{textValue(item.COD_GRUPO_PRINCIPAL)}/{textValue(item.COD_COMP_PRINCIPAL)}/{textValue(item.COD_CAUSA_PRINCIPAL)} · {textValue(item.PARES_COMPONENTE_CAUSA)}</p>
              </article>
            ))}
            {!topCasosTecnicos.length && <p className="muted-text">Aplique filtros ou atualize o ranking para ver os cartões investigativos.</p>}
          </div>
        </article>

        <aside className="investigation-card decision-lens-card">
          <h2>Lente de decisão</h2>
          <p>Use como triagem: primeiro confirme contexto, depois detalhe a ocorrência.</p>
          <div className="decision-step-list">
            <span><strong>1</strong><small>Verifique grupo/comp/causa</small></span>
            <span><strong>2</strong><small>Compare CHI, CI/FIC e ressarcimento</small></span>
            <span><strong>3</strong><small>Abra ocorrência e valide serviços/reclamações</small></span>
          </div>
          <div className="filter-chip-list">
            {criteriosAtivos.map((criterio) => <span key={criterio}>{criterio}</span>)}
          </div>
        </aside>
      </section>

      <DataTable
        empty={loading ? 'Carregando ranking técnico...' : 'Nenhuma ocorrência encontrada para os filtros.'}
        sortable
        initialSort={{ key: 'IMPACTO_SCORE', direction: 'desc' }}
        columns={[
          { key: 'IMPACTO_SCORE', label: 'Score', render: (item) => decimalFormat(item.IMPACTO_SCORE, 1) },
          {
            key: 'NUM_OCORRENCIA_ADMS',
            label: 'Ocorrência',
            defaultDirection: 'asc',
            render: (item) => (
              <button className="link-button" onClick={() => onOpenOccurrence(item.NUM_OCORRENCIA_ADMS)}>
                {item.NUM_OCORRENCIA_ADMS}
              </button>
            ),
          },
          { key: 'CHI_LIQUIDO', label: 'CHI Líq.', render: (item) => decimalFormat(item.CHI_LIQUIDO, 2) },
          { key: 'CI_LIQUIDO', label: 'CI Líq.', render: (item) => numberFormat(item.CI_LIQUIDO) },
          { key: 'RESSARCIMENTO_ESTIMADO', label: 'Ressarc.', render: (item) => currencyFormat(item.RESSARCIMENTO_ESTIMADO) },
          { key: 'DURACAO_MAX_HORA', label: 'Duração máx.', render: (item) => `${decimalFormat(item.DURACAO_MAX_HORA, 2)} h` },
          {
            key: 'principal',
            label: 'Grupo/Comp/Causa',
            sortValue: (item) => `${item.COD_GRUPO_PRINCIPAL || ''}/${item.COD_COMP_PRINCIPAL || ''}/${item.COD_CAUSA_PRINCIPAL || ''}`,
            render: (item) => `${item.COD_GRUPO_PRINCIPAL || '—'}/${item.COD_COMP_PRINCIPAL || '—'}/${item.COD_CAUSA_PRINCIPAL || '—'}`,
          },
          { key: 'PARES_COMPONENTE_CAUSA', label: 'Pares', render: (item) => textValue(item.PARES_COMPONENTE_CAUSA) },
          {
            key: 'sinais',
            label: 'Sinais',
            sortable: false,
            render: (item) => (
              <div className="tag-list">
                {Number(item.TEM_9282 || 0) > 0 && <span className="pill">Comp/Causa</span>}
                {Number(item.QTD_VIOLACAO_COMP_CAUSA || 0) > 0 && <span className="pill pill-danger">Violação</span>}
                {Number(item.RESSARCIMENTO_ESTIMADO || 0) > 0 && <span className="pill pill-money">R$</span>}
              </div>
            ),
          },
        ]}
        rows={itens}
      />
    </section>
  )
}

function FilaTable({ fila, onOpenOccurrence }) {
  return (
    <DataTable
      columns={[
        { key: 'prioridade', label: 'Prioridade' },
        { key: 'num_seq_intrp', label: 'Interrupção' },
        {
          key: 'num_ocorrencia_adms',
          label: 'Ocorrência',
          render: (item) => (
            <button className="link-button" onClick={() => onOpenOccurrence(item.num_ocorrencia_adms)}>
              {item.num_ocorrencia_adms || '—'}
            </button>
          ),
        },
        { key: 'fonte_sugestao', label: 'Fonte' },
        { key: 'nivel_evidencia', label: 'Evidência' },
        {
          key: 'sugestao',
          label: 'Sugestão',
          render: (item) => `${item.cod_comp_sugerido || '—'}/${item.cod_causa_sugerida || '—'}`,
        },
        {
          key: 'status_fila',
          label: 'Status',
          render: (item) => <span className="pill">{item.status_fila}</span>,
        },
      ]}
      rows={fila}
    />
  )
}

function FilaPage({ fila, resumo, onOpenOccurrence, embedded = false }) {
  return (
    <>
      {!embedded && (
        <>
          <PageHero
            title="Fila Técnica"
            description="Casos problemáticos para suporte técnico: conflito de serviço ou evidência por reclamação."
            sideLabel="Abertos"
            sideValue={numberFormat(resumo.fila_aberta)}
          />
          <section className="metrics-grid compact">
            <Card label="Total na fila" value={numberFormat(resumo.fila_tecnica_total)} hint="revisão técnica" tone="orange" />
            <Card label="Conflito de serviço" value={numberFormat(resumo.fila_servico_conflito)} hint="revisão técnica prioritária" tone="purple" />
            <Card label="Por reclamação" value={numberFormat(resumo.fila_reclamacao)} hint="melhor classificação textual" tone="blue" />
            <Card label="Tratados" value={numberFormat(resumo.fila_tratada)} hint="baixados da fila" tone="green" />
          </section>
        </>
      )}
      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Itens em Aberto</h2>
            <p>Ordenado por prioridade e data de criação.</p>
          </div>
        </div>
        <FilaTable fila={fila} onOpenOccurrence={onOpenOccurrence} />
      </section>
    </>
  )
}

function AjustesPage({ ajustes, resumo, onOpenOccurrence, embedded = false }) {
  return (
    <>
      {!embedded && (
        <PageHero
          title="Gerenciamento de automáticos"
          description="Módulos e registros tratados por algoritmo, com evidência, autorização e trilha para exportação governada."
          sideLabel="Ajustes"
          sideValue={numberFormat(resumo.ajustes_auto_9282)}
        />
      )}
      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Registros automáticos governados</h2>
            <p>Saídas dos agentes e algoritmos que podem seguir para autorização quando a regra estiver aprovada.</p>
          </div>
        </div>
        <DataTable
          columns={[
            { key: 'num_seq_intrp', label: 'Interrupção' },
            {
              key: 'num_ocorrencia_adms',
              label: 'Ocorrência',
              render: (item) => (
                <button className="link-button" onClick={() => onOpenOccurrence(item.num_ocorrencia_adms)}>
                  {item.num_ocorrencia_adms || '—'}
                </button>
              ),
            },
            { key: 'sigla_regional', label: 'Regional' },
            {
              key: 'original',
              label: 'Original',
              render: (item) => `${item.cod_comp_intrp_original}/${item.cod_causa_intrp_original}`,
            },
            {
              key: 'novo',
              label: 'Novo',
              render: (item) => `${item.novo_cod_comp_intrp}/${item.novo_cod_causa_intrp}`,
            },
            {
              key: 'aprovado',
              label: 'Aprovado',
              render: (item) => <span className="pill">{item.aprovado ? 'SIM' : 'NÃO'}</span>,
            },
            { key: 'criado_em', label: 'Criado em', render: (item) => dateTime(item.criado_em) },
          ]}
          rows={ajustes}
        />
      </section>
    </>
  )
}

function OcorrenciasPage({
  resumo,
  fila,
  token,
  onOpenOccurrence,
}) {
  return (
    <>
      <PageHero
        title="Ocorrências"
        description="Busca e investigação pontual para localizar ocorrências problemáticas por impacto, data/hora, componente, causa, alimentador, conjunto e evidências."
        sideLabel="Fila"
        sideValue={numberFormat(resumo.fila_aberta)}
      />

      <section className="metrics-grid compact">
        <Card label="Fila técnica" value={numberFormat(resumo.fila_tecnica_total)} hint={`${numberFormat(resumo.fila_aberta)} em aberto`} tone="orange" />
        <Card label="Conflito serviço" value={numberFormat(resumo.fila_servico_conflito)} hint="revisão técnica" tone="purple" />
        <Card label="Por reclamação" value={numberFormat(resumo.fila_reclamacao)} hint="evidência textual" tone="blue" />
        <Card label="Ajustes IQS" value={numberFormat(resumo.ajustes_auto_9282)} hint="autorizados" tone="green" />
      </section>

      <AnaliseImpactoPanel anomes={resumo.anomes} token={token} onOpenOccurrence={onOpenOccurrence} />
      <FilaPreview anomes={resumo.anomes} token={token} onOpenOccurrence={onOpenOccurrence} />
      <FilaPage fila={fila} resumo={resumo} onOpenOccurrence={onOpenOccurrence} embedded />
    </>
  )
}

function IqsGenerationPanel({
  modelos,
  geracoes,
  user,
  onCreate,
  generating,
  title = 'Modelos de Tratamento',
  description = 'Selecione um ou vários arquivos. A justificativa será única para todo o processamento.',
}) {
  const canGenerate = hasProfile(user, ['GESTOR', 'ADM'])
  const [selected, setSelected] = useState([])
  const [anomes, setAnomes] = useState('202606')
  const [justificativa, setJustificativa] = useState('')

  function toggleModelo(codigo) {
    setSelected((current) =>
      current.includes(codigo) ? current.filter((item) => item !== codigo) : [...current, codigo],
    )
  }

  async function submit(event) {
    event.preventDefault()
    await onCreate({ anomes, modelos: selected, justificativa })
    setSelected([])
    setJustificativa('')
  }

  return (
    <>
      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>{title}</h2>
            <p>{description}</p>
          </div>
        </div>
        {!canGenerate && (
          <div className="alert">Seu perfil pode consultar os modelos, mas apenas GESTOR/ADM aprova geração IQS.</div>
        )}
        <form className="iqs-generation-form" onSubmit={submit}>
          <label>
            ANOMES
            <input value={anomes} onChange={(event) => setAnomes(event.target.value)} disabled={!canGenerate} />
          </label>
          <div className="model-grid">
            {modelos.map((modelo) => (
              <label className="model-card" key={modelo.codigo_modelo}>
                <input
                  type="checkbox"
                  checked={selected.includes(modelo.codigo_modelo)}
                  disabled={!canGenerate}
                  onChange={() => toggleModelo(modelo.codigo_modelo)}
                />
                <strong>{modelo.nome_modelo}</strong>
                <span>{modelo.codigo_modelo}</span>
                <small>{modelo.descricao}</small>
              </label>
            ))}
          </div>
          <label className="form-wide">
            Justificativa única do gestor
            <textarea
              required
              minLength={20}
              value={justificativa}
              disabled={!canGenerate}
              onChange={(event) => setJustificativa(event.target.value)}
              placeholder="Descreva o motivo da geração, evidências consideradas e abrangência dos arquivos."
            />
          </label>
          <div className="form-actions">
            <button className="primary-button" type="submit" disabled={!canGenerate || generating || selected.length === 0}>
              {generating ? 'Aprovando geração...' : 'Aprovar geração IQS'}
            </button>
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Histórico de Gerações</h2>
            <p>Pacotes aprovados por gestor, com modelos e justificativa única.</p>
          </div>
        </div>
        <DataTable
          columns={[
            { key: 'aprovado_em', label: 'Aprovado em', render: (item) => dateTime(item.aprovado_em) },
            { key: 'anomes', label: 'ANOMES' },
            { key: 'status_geracao', label: 'Status', render: (item) => <span className="pill">{item.status_geracao}</span> },
            { key: 'qtd_modelos', label: 'Modelos' },
            { key: 'modelos', label: 'Lista' },
            { key: 'aprovado_por', label: 'Aprovado por' },
            { key: 'justificativa', label: 'Justificativa' },
          ]}
          rows={geracoes}
        />
      </section>
    </>
  )
}

function GeracaoIqsPage({ modelos, geracoes, user, onCreate, generating }) {
  return (
    <>
      <PageHero
        title="Geração IQS"
        description="Gestor aprova um pacote de modelos/arquivos com justificativa única para implantação no IQS."
        sideLabel="Modelos"
        sideValue={numberFormat(modelos.length)}
      />

      <IqsGenerationPanel
        modelos={modelos}
        geracoes={geracoes}
        user={user}
        onCreate={onCreate}
        generating={generating}
      />
    </>
  )
}

function AuditoriaPage({ auditoria, embedded = false }) {
  return (
    <>
      {!embedded && (
        <PageHero
          title="Auditoria"
          description="Evidência de autorização em massa, usuário, entidade e resumo operacional."
          sideLabel="Eventos"
          sideValue={numberFormat(auditoria.length)}
        />
      )}
      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Eventos de Autorização</h2>
            <p>Trilha de auditoria da autorização executiva.</p>
          </div>
        </div>
        <DataTable
          columns={[
            { key: 'criado_em', label: 'Data', render: (item) => dateTime(item.criado_em) },
            { key: 'tipo_evento', label: 'Evento' },
            { key: 'usuario', label: 'Usuário' },
            { key: 'entidade', label: 'Entidade' },
            { key: 'id_entidade', label: 'ID Entidade' },
            { key: 'detalhe', label: 'Detalhe', render: (item) => textValue(item.detalhe) },
          ]}
          rows={auditoria}
        />
      </section>
    </>
  )
}

function VerificacaoPage({ verificacoes, health, embedded = false }) {
  const missingTables = verificacoes?.missing_tables || []
  const missingViews = verificacoes?.missing_views || []
  const missingParameters = verificacoes?.missing_parameters || []
  return (
    <>
      {!embedded && (
        <PageHero
          title="Verificação dos Dados"
          description="Checagens operacionais do PostgreSQL, schema, tabelas, views e parâmetros obrigatórios."
          sideLabel="Status"
          sideValue={verificacoes?.database_ok ? 'OK' : 'Atenção'}
        />
      )}
      <section className="metrics-grid compact">
        <Card label="Tabelas" value={numberFormat(verificacoes?.tables || health?.database?.tables)} hint="esperadas no ddcq" tone="green" />
        <Card label="Views" value={numberFormat(verificacoes?.views || health?.database?.views)} hint="camadas de leitura" tone="blue" />
        <Card label="Parâmetros" value={numberFormat(verificacoes?.parameters || health?.database?.parameters)} hint="configuração operacional" tone="purple" />
        <Card label="Pendências" value={numberFormat(missingTables.length + missingViews.length + missingParameters.length)} hint="objetos ausentes" tone="orange" />
      </section>
      <section className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <h2>Pendências</h2>
              <p>Itens ausentes na validação do banco.</p>
            </div>
          </div>
          <div className="stat-list">
            <span>Tabelas ausentes: <strong>{missingTables.join(', ') || 'nenhuma'}</strong></span>
            <span>Views ausentes: <strong>{missingViews.join(', ') || 'nenhuma'}</strong></span>
            <span>Parâmetros ausentes: <strong>{missingParameters.join(', ') || 'nenhum'}</strong></span>
          </div>
        </article>
        <article className="panel">
          <div className="panel-title">
            <div>
              <h2>Próxima ação</h2>
              <p>Padronização para correção segura.</p>
            </div>
          </div>
          <div className="stacked-notes">
            <span><strong>Banco parado</strong> rode `run.bat postgres_start`.</span>
            <span><strong>Schema incompleto</strong> rode os SQL versionados.</span>
            <span><strong>Governança ausente</strong> rode `run.bat postgres_governanca`.</span>
          </div>
        </article>
      </section>
    </>
  )
}

function SqlPage({ scripts, embedded = false }) {
  return (
    <>
      {!embedded && (
        <PageHero
          title="SQL Versionado"
          description="Catálogo dos scripts SQL do schema `ddcq` para revisão, aplicação controlada e auditoria."
          sideLabel="Scripts"
          sideValue={numberFormat(scripts.length)}
        />
      )}
      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Scripts PostgreSQL</h2>
            <p>Lista somente leitura. Execução deve ocorrer por comando versionado ou processo aprovado.</p>
          </div>
        </div>
        <DataTable
          columns={[
            { key: 'nome', label: 'Arquivo' },
            { key: 'caminho', label: 'Caminho' },
            { key: 'tamanho', label: 'Tamanho', render: (item) => `${numberFormat(item.tamanho)} bytes` },
            { key: 'alterado_em', label: 'Alterado em', render: (item) => dateTime(item.alterado_em * 1000) },
          ]}
          rows={scripts}
        />
      </section>
    </>
  )
}

function AlteracoesPage({ alteracoes, user, onCreate, onApprove, onReject, savingDecision, embedded = false }) {
  const canCreate = hasProfile(user, ['ANALISTA', 'GESTOR'])
  const canDecide = hasProfile(user, ['GESTOR', 'ADM'])
  const [form, setForm] = useState({
    anomes: '202606',
    modulo: 'QUALIDADE_INTERRUPCOES',
    entidade: 'interrupcao',
    id_entidade: '',
    tipo_alteracao: 'UPDATE',
    justificativa: '',
    antes: '',
    depois: '',
  })

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function parseJsonField(value) {
    if (!value.trim()) return {}
    return JSON.parse(value)
  }

  async function submitProposal(event) {
    event.preventDefault()
    try {
      await onCreate({
        ...form,
        status_alteracao: 'PENDENTE',
        antes: parseJsonField(form.antes),
        depois: parseJsonField(form.depois),
      })
      setForm((current) => ({
        ...current,
        id_entidade: '',
        justificativa: '',
        antes: '',
        depois: '',
      }))
    } catch {
      window.alert('Campos Antes/Depois precisam ser JSON válido.')
    }
  }

  return (
    <>
      {!embedded && (
        <PageHero
          title="Alterações manuais"
          description="Fluxo de decisão humana: analista propõe, gestor aprova ou rejeita, e toda divergência da recomendação fica justificada."
          sideLabel="Registros"
          sideValue={numberFormat(alteracoes.length)}
        />
      )}

      {canCreate && (
        <section className="panel">
          <div className="panel-title">
            <div>
              <h2>Nova proposta manual</h2>
              <p>Use antes/depois em JSON para deixar a decisão auditável.</p>
            </div>
          </div>
          <form className="governed-form" onSubmit={submitProposal}>
            <label>
              ANOMES
              <input value={form.anomes} onChange={(event) => updateForm('anomes', event.target.value)} />
            </label>
            <label>
              Módulo
              <select value={form.modulo} onChange={(event) => updateForm('modulo', event.target.value)}>
                <option value="QUALIDADE_INTERRUPCOES">Qualidade de Interrupções</option>
                <option value="AJUSTE_MANUAL_IQS">Ajuste Manual IQS</option>
                <option value="EXECUTIVO_9282">Executivo</option>
                <option value="EXPORTACAO_IQS">Exportação IQS</option>
              </select>
            </label>
            <label>
              Entidade
              <input value={form.entidade} onChange={(event) => updateForm('entidade', event.target.value)} />
            </label>
            <label>
              ID Entidade
              <input value={form.id_entidade} onChange={(event) => updateForm('id_entidade', event.target.value)} />
            </label>
            <label>
              Tipo
              <select value={form.tipo_alteracao} onChange={(event) => updateForm('tipo_alteracao', event.target.value)}>
                <option value="UPDATE">UPDATE</option>
                <option value="INSERT">INSERT</option>
                <option value="DELETE">DELETE</option>
                <option value="OUTRO">OUTRO</option>
              </select>
            </label>
            <label className="form-wide">
              Justificativa
              <textarea
                required
                value={form.justificativa}
                onChange={(event) => updateForm('justificativa', event.target.value)}
                placeholder="Explique a evidência, impacto e motivo da alteração."
              />
            </label>
            <label className="form-wide">
              Antes (JSON)
              <textarea
                value={form.antes}
                onChange={(event) => updateForm('antes', event.target.value)}
                placeholder='{"COD_COMP_INTRP":"92","COD_CAUSA_INTRP":"82"}'
              />
            </label>
            <label className="form-wide">
              Depois (JSON)
              <textarea
                value={form.depois}
                onChange={(event) => updateForm('depois', event.target.value)}
                placeholder='{"COD_COMP_INTRP":"XX","COD_CAUSA_INTRP":"YY"}'
              />
            </label>
            <div className="form-actions">
              <button className="primary-button" type="submit">Enviar para aprovação</button>
            </div>
          </form>
        </section>
      )}

      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Mesa de Decisão</h2>
            <p>Propostas pendentes exigem decisão de Gestor diferente do solicitante.</p>
          </div>
        </div>
        <DataTable
          columns={[
            { key: 'criado_em', label: 'Data', render: (item) => dateTime(item.criado_em) },
            { key: 'modulo', label: 'Módulo' },
            { key: 'entidade', label: 'Entidade' },
            { key: 'tipo_alteracao', label: 'Tipo' },
            { key: 'status_alteracao', label: 'Status', render: (item) => <span className="pill">{item.status_alteracao}</span> },
            { key: 'solicitado_por', label: 'Solicitado por' },
            { key: 'aprovado_por', label: 'Decidido por' },
            { key: 'justificativa', label: 'Justificativa' },
            {
              key: 'acoes',
              label: 'Ações',
              render: (item) => {
                const canAct = canDecide && item.status_alteracao === 'PENDENTE' && item.solicitado_por !== user?.login
                if (!canAct) return <span className="muted">—</span>
                return (
                  <div className="row-actions">
                    <button
                      className="mini-button mini-button-success"
                      disabled={savingDecision}
                      onClick={() => onApprove(item)}
                    >
                      Aprovar
                    </button>
                    <button
                      className="mini-button mini-button-danger"
                      disabled={savingDecision}
                      onClick={() => onReject(item)}
                    >
                      Rejeitar
                    </button>
                  </div>
                )
              },
            },
          ]}
          rows={alteracoes}
        />
      </section>
    </>
  )
}

function GovernancaPage({
  usuarios,
  sessoes,
  resetSenhaEventos,
  perfisFuncoes,
  execucoes,
  tiposExecucao,
  activeSection = 'usuarios',
  user,
  token,
  onRefresh,
  embedded = false,
}) {
  const [usuarioForm, setUsuarioForm] = useState({
    nome: '',
    email: '',
    perfil: 'ANALISTA',
    senha: '',
  })
  const [usuarioEditando, setUsuarioEditando] = useState(null)
  const [resetPreparado, setResetPreparado] = useState(null)
  const [resetForm, setResetForm] = useState({
    codigo: '',
    nova_senha: '',
    justificativa: '',
  })
  const [execucaoForm, setExecucaoForm] = useState({
    tipo_lote: 'extract',
    anomes: '202606',
  })
  const [governancaMessage, setGovernancaMessage] = useState('')
  const [governancaError, setGovernancaError] = useState('')
  const [savingGovernanca, setSavingGovernanca] = useState(false)
  const [startingExecucao, setStartingExecucao] = useState(false)
  const [savingPermissao, setSavingPermissao] = useState('')
  const isAdmin = user?.perfil === 'ADM'
  const selectedExecucao = tiposExecucao.find((item) => item.tipo_lote === execucaoForm.tipo_lote)

  function updateUsuarioForm(field, value) {
    setUsuarioForm((current) => ({ ...current, [field]: value }))
  }

  function updateResetForm(field, value) {
    setResetForm((current) => ({ ...current, [field]: value }))
  }

  function updateUsuarioEditando(field, value) {
    setUsuarioEditando((current) => ({ ...current, [field]: value }))
  }

  function updateExecucaoForm(field, value) {
    setExecucaoForm((current) => ({ ...current, [field]: value }))
  }

  function editarUsuario(item) {
    setUsuarioEditando({
      id_usuario: item.id_usuario,
      nome: item.nome || '',
      email: item.email || item.login || '',
      perfil: item.perfil || 'ANALISTA',
      status_usuario: item.status_usuario || 'ATIVO',
    })
  }

  async function criarUsuario(event) {
    event.preventDefault()
    try {
      setSavingGovernanca(true)
      setGovernancaError('')
      setGovernancaMessage('')
      const response = await fetch(`${API_URL}/api/governanca/usuarios`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(usuarioForm),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao criar usuário.')
      }
      setUsuarioForm({ nome: '', email: '', perfil: 'ANALISTA', senha: '' })
      setGovernancaMessage(`Usuário criado: ${result.id_usuario}`)
      await onRefresh()
    } catch (requestError) {
      setGovernancaError(requestError.message)
    } finally {
      setSavingGovernanca(false)
    }
  }

  async function salvarUsuario(event) {
    event.preventDefault()
    if (!usuarioEditando?.id_usuario) return
    try {
      setSavingGovernanca(true)
      setGovernancaError('')
      setGovernancaMessage('')
      const response = await fetch(`${API_URL}/api/governanca/usuarios/${usuarioEditando.id_usuario}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          nome: usuarioEditando.nome,
          email: usuarioEditando.email,
          perfil: usuarioEditando.perfil,
          status_usuario: usuarioEditando.status_usuario,
        }),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao atualizar usuário.')
      }
      setUsuarioEditando(null)
      setGovernancaMessage(`Usuário atualizado: ${result.id_usuario}`)
      await onRefresh()
    } catch (requestError) {
      setGovernancaError(requestError.message)
    } finally {
      setSavingGovernanca(false)
    }
  }

  async function inativarUsuario(item) {
    if (!window.confirm(`Inativar o usuário ${item.email || item.login}?`)) return
    try {
      setSavingGovernanca(true)
      setGovernancaError('')
      setGovernancaMessage('')
      const response = await fetch(`${API_URL}/api/governanca/usuarios/${item.id_usuario}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao inativar usuário.')
      }
      setGovernancaMessage(`Usuário inativado: ${result.id_usuario}`)
      await onRefresh()
    } catch (requestError) {
      setGovernancaError(requestError.message)
    } finally {
      setSavingGovernanca(false)
    }
  }

  async function prepararReset(item) {
    try {
      setSavingGovernanca(true)
      setGovernancaError('')
      setGovernancaMessage('')
      const response = await fetch(`${API_URL}/api/governanca/usuarios/${item.id_usuario}/reset-senha/preparar`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao preparar reset de senha.')
      }
      setResetPreparado(result)
      setResetForm({ codigo: '', nova_senha: '', justificativa: '' })
      setGovernancaMessage(`Código de confirmação gerado para ${result.login}.`)
      await onRefresh()
    } catch (requestError) {
      setGovernancaError(requestError.message)
    } finally {
      setSavingGovernanca(false)
    }
  }

  async function confirmarReset(event) {
    event.preventDefault()
    if (!resetPreparado?.id_reset) return
    try {
      setSavingGovernanca(true)
      setGovernancaError('')
      setGovernancaMessage('')
      const response = await fetch(`${API_URL}/api/governanca/reset-senha/${resetPreparado.id_reset}/confirmar`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(resetForm),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao confirmar reset de senha.')
      }
      setResetPreparado(null)
      setResetForm({ codigo: '', nova_senha: '', justificativa: '' })
      setGovernancaMessage(`Senha redefinida para ${result.login}. Sessões ativas foram revogadas.`)
      await onRefresh()
    } catch (requestError) {
      setGovernancaError(requestError.message)
    } finally {
      setSavingGovernanca(false)
    }
  }

  async function iniciarExecucao(event) {
    event.preventDefault()
    try {
      setStartingExecucao(true)
      setGovernancaError('')
      setGovernancaMessage('')
      const response = await fetch(`${API_URL}/api/governanca/execucoes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(execucaoForm),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao iniciar processamento.')
      }
      setGovernancaMessage(`Processamento enviado para backend: ${result.tipo_lote}.`)
      await onRefresh()
    } catch (requestError) {
      setGovernancaError(requestError.message)
    } finally {
      setStartingExecucao(false)
    }
  }

  async function atualizarPermissao(perfil, permissao, campo, value) {
    const next = {
      pode_visualizar: campo === 'pode_visualizar' ? value : Boolean(permissao.pode_visualizar),
      pode_editar: campo === 'pode_editar' ? value : Boolean(permissao.pode_editar),
    }
    if (next.pode_editar) {
      next.pode_visualizar = true
    }
    if (!next.pode_visualizar) {
      next.pode_editar = false
    }
    const savingKey = `${perfil}:${permissao.pagina}:${campo}`
    try {
      setSavingPermissao(savingKey)
      setGovernancaError('')
      setGovernancaMessage('')
      const response = await fetch(`${API_URL}/api/governanca/perfis/${perfil}/permissoes/${permissao.pagina}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(next),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao atualizar permissão.')
      }
      setGovernancaMessage(`Permissão atualizada: ${perfil} / ${permissao.pagina_label}.`)
      await onRefresh()
    } catch (requestError) {
      setGovernancaError(requestError.message)
    } finally {
      setSavingPermissao('')
    }
  }

  return (
    <>
      {!embedded && (
        <PageHero
          title="Governança"
          description="Controle de usuários, sessões, perfis e segregação de funções."
          sideLabel="Perfil"
          sideValue={user?.perfil}
        />
      )}
      {governancaMessage && <div className="alert alert-success">{governancaMessage}</div>}
      {governancaError && <div className="alert">{governancaError}</div>}
      {activeSection === 'usuarios' && isAdmin && (
        <section className="content-grid">
          <article className="panel panel-large">
            <div className="panel-title">
              <div>
                <h2>Incluir Usuário</h2>
                <p>Cadastro local governado. Senhas são gravadas somente como hash PBKDF2.</p>
              </div>
            </div>
            <form className="governed-form" onSubmit={criarUsuario}>
              <label>
                Nome
                <input value={usuarioForm.nome} onChange={(event) => updateUsuarioForm('nome', event.target.value)} required />
              </label>
              <label>
                E-mail
                <input value={usuarioForm.email} onChange={(event) => updateUsuarioForm('email', event.target.value)} type="email" required />
              </label>
              <label>
                Perfil
                <select value={usuarioForm.perfil} onChange={(event) => updateUsuarioForm('perfil', event.target.value)}>
                  <option value="ANALISTA">ANALISTA</option>
                  <option value="GESTOR">GESTOR</option>
                  <option value="CONSULTA">CONSULTA</option>
                  <option value="AUDITOR">AUDITOR</option>
                  <option value="ADM">ADM</option>
                </select>
              </label>
              <label>
                Senha inicial
                <input
                  value={usuarioForm.senha}
                  onChange={(event) => updateUsuarioForm('senha', event.target.value)}
                  type="password"
                  minLength={12}
                  required
                />
              </label>
              <div className="form-actions">
                <button className="primary-button" type="submit" disabled={savingGovernanca}>
                  {savingGovernanca ? 'Salvando...' : 'Criar usuário'}
                </button>
              </div>
            </form>
          </article>
        </section>
      )}
      {activeSection === 'usuarios' && isAdmin && usuarioEditando && (
        <section className="content-grid">
          <article className="panel panel-large">
            <div className="panel-title">
              <div>
                <h2>Editar Usuário</h2>
                <p>Atualiza dados, perfil e status. Inativação revoga sessões ativas.</p>
              </div>
            </div>
            <form className="governed-form" onSubmit={salvarUsuario}>
              <label>
                Nome
                <input value={usuarioEditando.nome} onChange={(event) => updateUsuarioEditando('nome', event.target.value)} required />
              </label>
              <label>
                E-mail
                <input value={usuarioEditando.email} onChange={(event) => updateUsuarioEditando('email', event.target.value)} type="email" required />
              </label>
              <label>
                Perfil
                <select value={usuarioEditando.perfil} onChange={(event) => updateUsuarioEditando('perfil', event.target.value)}>
                  <option value="ANALISTA">ANALISTA</option>
                  <option value="GESTOR">GESTOR</option>
                  <option value="CONSULTA">CONSULTA</option>
                  <option value="AUDITOR">AUDITOR</option>
                  <option value="ADM">ADM</option>
                </select>
              </label>
              <label>
                Status
                <select value={usuarioEditando.status_usuario} onChange={(event) => updateUsuarioEditando('status_usuario', event.target.value)}>
                  <option value="ATIVO">ATIVO</option>
                  <option value="BLOQUEADO">BLOQUEADO</option>
                  <option value="INATIVO">INATIVO</option>
                </select>
              </label>
              <div className="form-actions">
                <button className="secondary-button" type="button" onClick={() => setUsuarioEditando(null)}>
                  Cancelar
                </button>
                <button className="primary-button" type="submit" disabled={savingGovernanca}>
                  {savingGovernanca ? 'Salvando...' : 'Salvar alterações'}
                </button>
              </div>
            </form>
          </article>
        </section>
      )}
      {activeSection === 'usuarios' && (
      <section className="content-grid">
        <article className="panel panel-large">
          <div className="panel-title">
            <div>
              <h2>Usuários e Acessos</h2>
              <p>Perfis disponíveis: ADM, GESTOR, ANALISTA, CONSULTA e AUDITOR.</p>
            </div>
          </div>
          <DataTable
            columns={[
              { key: 'email', label: 'E-mail' },
              { key: 'nome', label: 'Nome' },
              { key: 'perfil', label: 'Perfil', render: (item) => <span className="pill">{item.perfil}</span> },
              { key: 'status_usuario', label: 'Status' },
              { key: 'ultimo_login_em', label: 'Último login', render: (item) => dateTime(item.ultimo_login_em) },
              ...(isAdmin ? [{
                key: 'acoes',
                label: 'Ações',
                render: (item) => (
                  <div className="row-actions">
                    <button className="mini-button" disabled={savingGovernanca} onClick={() => editarUsuario(item)}>
                      Editar
                    </button>
                    <button className="mini-button mini-button-danger" disabled={savingGovernanca} onClick={() => inativarUsuario(item)}>
                      Inativar
                    </button>
                  </div>
                ),
              }] : []),
            ]}
            rows={usuarios}
          />
        </article>
        <article className="panel">
          <div className="panel-title">
            <div>
              <h2>Sessões Ativas</h2>
              <p>Tokens são armazenados no banco apenas como hash.</p>
            </div>
          </div>
          <DataTable
            columns={[
              { key: 'email', label: 'E-mail' },
              { key: 'perfil', label: 'Perfil' },
              { key: 'expira_em', label: 'Expira', render: (item) => dateTime(item.expira_em) },
            ]}
            rows={sessoes}
          />
        </article>
        {isAdmin && (
          <article className="panel panel-large">
            <div className="panel-title">
              <div>
                <h2>Monitoramento de Reset</h2>
                <p>Eventos de reset de senha sem exposição do código/hash.</p>
              </div>
            </div>
            <DataTable
              columns={[
                { key: 'email', label: 'E-mail' },
                { key: 'perfil', label: 'Perfil' },
                { key: 'status_reset', label: 'Status', render: (item) => <span className="pill">{item.status_reset}</span> },
                { key: 'solicitado_por', label: 'Solicitado por' },
                { key: 'tentativas', label: 'Tentativas', render: (item) => numberFormat(item.tentativas) },
                { key: 'expira_em', label: 'Expira', render: (item) => dateTime(item.expira_em) },
                { key: 'confirmado_por', label: 'Confirmado por' },
                { key: 'confirmado_em', label: 'Confirmado em', render: (item) => dateTime(item.confirmado_em) },
              ]}
              rows={resetSenhaEventos}
            />
          </article>
        )}
      </section>
      )}
      {activeSection === 'perfis' && (
      <section className="content-grid">
        <article className="panel panel-large">
          <div className="panel-title">
            <div>
              <h2>Perfis e Funções</h2>
              <p>Defina o que cada perfil pode visualizar ou editar em cada página.</p>
            </div>
          </div>
          <div className="permission-grid">
            {perfisFuncoes.map((perfilItem) => (
              <section className="permission-card" key={perfilItem.perfil}>
                <div className="permission-card-title">
                  <span className="pill">{perfilItem.perfil}</span>
                  <small>{perfilItem.descricao}</small>
                </div>
                <div className="permission-rows">
                  {(perfilItem.permissoes || []).map((permissao) => {
                    const disabled = !isAdmin || savingPermissao.startsWith(`${perfilItem.perfil}:${permissao.pagina}`) || perfilItem.perfil === 'ADM'
                    return (
                      <div className="permission-row" key={`${perfilItem.perfil}-${permissao.pagina}`}>
                        <strong>{permissao.pagina_label}</strong>
                        <label>
                          <input
                            type="checkbox"
                            checked={Boolean(permissao.pode_visualizar)}
                            disabled={disabled}
                            onChange={(event) => atualizarPermissao(perfilItem.perfil, permissao, 'pode_visualizar', event.target.checked)}
                          />
                          Visualizar
                        </label>
                        <label>
                          <input
                            type="checkbox"
                            checked={Boolean(permissao.pode_editar)}
                            disabled={disabled || !permissao.pode_visualizar}
                            onChange={(event) => atualizarPermissao(perfilItem.perfil, permissao, 'pode_editar', event.target.checked)}
                          />
                          Editar
                        </label>
                      </div>
                    )
                  })}
                </div>
              </section>
            ))}
          </div>
          {!perfisFuncoes.length && (
            <div className="alert">
              Matriz de permissões não carregada. Clique em `Atualizar`; se continuar vazio, reinicie a API para carregar as novas rotas de governança.
            </div>
          )}
          {!isAdmin && <p className="panel-note">Seu perfil pode visualizar a matriz, mas somente ADM altera permissões.</p>}
        </article>
      </section>
      )}
      {activeSection === 'processamentos' && (
      <section className="content-grid">
        {isAdmin && (
          <article className="panel">
            <div className="panel-title">
              <div>
                <h2>Processamentos Backend</h2>
                <p>Dispare cargas pesadas sem travar a utilização da tela.</p>
              </div>
            </div>
            <form className="governed-form governed-form-compact" onSubmit={iniciarExecucao}>
              <label>
                Processamento
                <select
                  value={execucaoForm.tipo_lote}
                  onChange={(event) => updateExecucaoForm('tipo_lote', event.target.value)}
                  disabled={!tiposExecucao.length}
                >
                  {!tiposExecucao.length && <option value="">Lista do run.bat não carregada</option>}
                  {tiposExecucao.map((item) => (
                    <option key={item.tipo_lote} value={item.tipo_lote}>{item.titulo}</option>
                  ))}
                </select>
              </label>
              <label>
                ANOMES
                <input value={execucaoForm.anomes} onChange={(event) => updateExecucaoForm('anomes', event.target.value)} maxLength={6} required />
              </label>
              <div className="form-actions">
                <button className="primary-button" type="submit" disabled={startingExecucao || !tiposExecucao.length}>
                  {startingExecucao ? 'Enviando...' : 'Executar no backend'}
                </button>
              </div>
            </form>
            {selectedExecucao && (
              <p className="panel-note">
                Comando: <strong>{selectedExecucao.comando || `run.bat ${selectedExecucao.tipo_lote}`}</strong> · {selectedExecucao.descricao}
              </p>
            )}
            {!tiposExecucao.length && (
              <div className="alert">
                A lista de processamentos do `run.bat` não foi carregada. Clique em `Atualizar`; se continuar vazio, reinicie a API.
              </div>
            )}
          </article>
        )}
        <article className={isAdmin ? 'panel' : 'panel panel-large'}>
          <div className="panel-title">
            <div>
              <h2>Fila de Execuções</h2>
              <p>Status dos lotes executados pelo backend.</p>
            </div>
          </div>
          <DataTable
            columns={[
              { key: 'tipo_lote', label: 'Tipo' },
              { key: 'anomes', label: 'ANOMES' },
              { key: 'status_lote', label: 'Status', render: (item) => <StatusPill value={item.status_lote} /> },
              { key: 'criado_por', label: 'Solicitado por' },
              { key: 'iniciado_em', label: 'Início', render: (item) => dateTime(item.iniciado_em) },
              { key: 'finalizado_em', label: 'Fim', render: (item) => dateTime(item.finalizado_em) },
              { key: 'mensagem', label: 'Mensagem', render: (item) => String(item.mensagem || '—').slice(0, 180) },
            ]}
            rows={execucoes}
          />
        </article>
      </section>
      )}
    </>
  )
}

function ConfiguracoesPage({ health, embedded = false }) {
  const database = health?.database || {}
  return (
    <>
      {!embedded && (
        <PageHero
          title="Configurações"
          description="Estado da API, conexão PostgreSQL e variáveis utilizadas pelo frontend."
          sideLabel="API"
          sideValue={health?.status || '—'}
        />
      )}
      <section className="content-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <h2>Frontend</h2>
              <p>Configuração local do React.</p>
            </div>
          </div>
          <div className="stat-list">
            <span>API URL: <strong>{API_URL}</strong></span>
            <span>Versão UI: <strong>7.0.0</strong></span>
            <span>Runtime: <strong>Vite + React</strong></span>
          </div>
        </article>
        <article className="panel">
          <div className="panel-title">
            <div>
              <h2>PostgreSQL</h2>
              <p>Validação operacional do schema `ddcq`.</p>
            </div>
          </div>
          <div className="stat-list">
            <span>Status: <strong>{database.status || '—'}</strong></span>
            <span>Schema: <strong>{database.schema || '—'}</strong></span>
            <span>Tabelas: <strong>{database.tables || 0}</strong></span>
            <span>Views: <strong>{database.views || 0}</strong></span>
            <span>Parâmetros: <strong>{database.parameters || 0}</strong></span>
          </div>
        </article>
      </section>
    </>
  )
}

function AdministracaoPage({
  usuarios,
  sessoes,
  resetSenhaEventos,
  perfisFuncoes,
  execucoes,
  tiposExecucao,
  auditoria,
  sqlScripts,
  verificacoes,
  health,
  user,
  token,
  onRefresh,
}) {
  const [activeAdminTab, setActiveAdminTab] = useState('usuarios')
  const adminTabs = [
    { id: 'usuarios', label: 'Usuários' },
    { id: 'perfis', label: 'Perfis e Funções' },
    { id: 'processamentos', label: 'Processamentos' },
    { id: 'auditoria', label: 'Auditoria' },
    { id: 'sistema', label: 'Sistema' },
  ]

  return (
    <>
      <PageHero
        title="Administração"
        description="Controle administrativo organizado por áreas: acessos, funções, processamentos, auditoria e sistema."
        sideLabel="Perfil"
        sideValue={user?.perfil}
      />

      <nav className="admin-tabs" aria-label="Seções da administração">
        {adminTabs.map((tab) => (
          <button
            key={tab.id}
            className={activeAdminTab === tab.id ? 'active' : ''}
            type="button"
            onClick={() => setActiveAdminTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {['usuarios', 'perfis', 'processamentos'].includes(activeAdminTab) && (
        <GovernancaPage
          usuarios={usuarios}
          sessoes={sessoes}
          resetSenhaEventos={resetSenhaEventos}
          perfisFuncoes={perfisFuncoes}
          execucoes={execucoes}
          tiposExecucao={tiposExecucao}
          activeSection={activeAdminTab}
          user={user}
          token={token}
          onRefresh={onRefresh}
          embedded
        />
      )}
      {activeAdminTab === 'auditoria' && <AuditoriaPage auditoria={auditoria} embedded />}
      {activeAdminTab === 'sistema' && (
        <>
          <SqlPage scripts={sqlScripts} embedded />
          <VerificacaoPage verificacoes={verificacoes} health={health} embedded />
          <ConfiguracoesPage health={health} embedded />
        </>
      )}
    </>
  )
}

function DrillIcon({ children }) {
  return <span className="drill-icon">{children}</span>
}

function DrillMetric({ icon, label, value, hint }) {
  return (
    <div className="drill-metric">
      <span><DrillIcon>{icon}</DrillIcon>{label}</span>
      <strong>{value}</strong>
      {hint && <small>{hint}</small>}
    </div>
  )
}

function DrillStatus({ children, tone = 'info' }) {
  return <span className={`drill-status drill-status-${tone}`}>{children}</span>
}

function ProdutoDrillDownBI({ cockpit }) {
  const drillData = useMemo(() => {
    const regional = cockpit?.rankings?.regional || []
    const conjuntos = cockpit?.rankings?.conjunto || []
    return {
      id: 'copel',
      nome: 'COPEL Distribuição',
      cards: cockpit?.cards || [],
      regionais: regional.map((item) => ({
        ...item,
        id: item.regional,
        nome: item.regional_exibicao || item.regional,
        conjuntos: conjuntos.filter((conjunto) => conjunto.regional === item.regional),
      })),
      conjuntos,
    }
  }, [cockpit])

  const [selected, setSelected] = useState({ type: 'distribuidora', title: 'COPEL Distribuição', data: drillData })
  const [history, setHistory] = useState([])

  useEffect(() => {
    setSelected((current) => {
      if (current.type !== 'distribuidora') return current
      return { type: 'distribuidora', title: drillData.nome, data: drillData }
    })
  }, [drillData])

  function openLevel(type, title, data) {
    setHistory((current) => [...current, selected])
    setSelected({ type, title, data })
  }

  function goBack() {
    setHistory((current) => {
      if (!current.length) return current
      const previous = current[current.length - 1]
      setSelected(previous)
      return current.slice(0, -1)
    })
  }

  function renderSelected() {
    if (selected.type === 'distribuidora') {
      return <DrillDistribuidora data={selected.data} />
    }
    if (selected.type === 'regional') {
      return <DrillRegional data={selected.data} />
    }
    if (selected.type === 'conjunto') {
      return <DrillConjunto data={selected.data} />
    }
    return null
  }

  if (!cockpit?.rankings) {
    return (
      <section id="produto-drilldown" className="panel product-section-anchor">
        <div className="panel-title">
          <div>
            <h2>Navegação BI por Drill-down</h2>
            <p>Aguardando dados reais do cockpit para montar a hierarquia.</p>
          </div>
          <span className="pill pill-warning">sem dados</span>
        </div>
      </section>
    )
  }

  return (
    <section id="produto-drilldown" className="panel product-section-anchor">
      <div className="panel-title">
        <div>
          <h2>Navegação BI por Drill-down</h2>
          <p>Dados reais do cockpit: COPEL → regional → conjunto. A lista navega à esquerda e o detalhe muda à direita.</p>
        </div>
        <span className="pill pill-success">dados reais</span>
      </div>

      <div className="drill-shell">
        <aside className="drill-left">
          <button className="drill-root-button" type="button" onClick={() => openLevel('distribuidora', drillData.nome, drillData)}>
            <DrillIcon>🏢</DrillIcon>
            <span>
              <strong>{drillData.nome}</strong>
              <small>Métricas globais reais</small>
            </span>
          </button>

          <div className="drill-tree">
            {drillData.regionais.map((regional) => (
              <details className="drill-details" key={regional.id}>
                <summary>
                  <button type="button" onClick={(event) => {
                    event.preventDefault()
                    openLevel('regional', regional.nome, regional)
                  }}>
                    <DrillIcon>📍</DrillIcon>
                    <span>
                      <strong>{regional.nome}</strong>
                      <small>CHI {decimalFormat(regional.chi_liquido, 2)} · CI {numberFormat(regional.ci_liquido)}</small>
                    </span>
                  </button>
                  <em>›</em>
                </summary>
                <div className="drill-children">
                  {regional.conjuntos.map((conjunto) => (
                    <details className="drill-details drill-details-child" key={conjunto.id}>
                      <summary>
                        <button type="button" onClick={(event) => {
                          event.preventDefault()
                          openLevel('conjunto', conjunto.nome, conjunto)
                        }}>
                          <DrillIcon>⚡</DrillIcon>
                          <span>
                            <strong>{conjunto.conjunto_exibicao || conjunto.conjunto}</strong>
                            <small>{numberFormat(conjunto.ocorrencias)} ocorrências · CHI {decimalFormat(conjunto.chi_liquido, 2)}</small>
                          </span>
                        </button>
                        <em>›</em>
                      </summary>
                      <div className="drill-children">
                        <button className="drill-leaf" type="button" onClick={() => openLevel('conjunto', conjunto.conjunto_exibicao || conjunto.conjunto, conjunto)}>
                          <strong>Resumo do conjunto</strong>
                          <small>Longas {numberFormat(conjunto.ocorrencias_longas)} · Curtas {numberFormat(conjunto.ocorrencias_curtas)} · Não faturado CI {numberFormat(conjunto.ci_nao_faturado)}</small>
                        </button>
                      </div>
                    </details>
                  ))}
                  {!regional.conjuntos.length && <div className="drill-empty">Nenhum conjunto no limite atual do cockpit para esta regional.</div>}
                </div>
              </details>
            ))}
          </div>
        </aside>

        <section className="drill-right">
          <div className="drill-detail-header">
            <div>
              <span>{selected.type}</span>
              <h3>{selected.title}</h3>
            </div>
            <button className="secondary-button" type="button" disabled={!history.length} onClick={goBack}>← Voltar nível</button>
          </div>
          <div className="drill-detail-body">{renderSelected()}</div>
        </section>
      </div>
    </section>
  )
}

function DrillDistribuidora({ data }) {
  const cardMap = new Map((data.cards || []).map((item) => [item.codigo, item.valor]))
  return (
    <div className="drill-view">
      <div className="drill-metric-grid">
        <DrillMetric icon="D" label="DEC Global" value={decimalFormat(cardMap.get('dec_liquido'), 2)} />
        <DrillMetric icon="F" label="FEC Global" value={decimalFormat(cardMap.get('fec_liquido'), 2)} />
        <DrillMetric icon="R$" label="Ressarcimento" value={currencyFormat(cardMap.get('comp_total_prodist'))} />
      </div>
      <div className="drill-list">
        {data.regionais.map((regional) => (
          <article key={regional.id}>
            <strong>{regional.nome}</strong>
            <span>{numberFormat(regional.ocorrencias)} ocorrências · CHI {decimalFormat(regional.chi_liquido, 2)} · CI {numberFormat(regional.ci_liquido)} · {currencyFormat(regional.comp_total_prodist)}</span>
          </article>
        ))}
      </div>
    </div>
  )
}

function DrillRegional({ data }) {
  return (
    <div className="drill-view">
      <div className="drill-metric-grid">
        <DrillMetric icon="!" label="Ocorrências" value={numberFormat(data.ocorrencias)} />
        <DrillMetric icon="CHI" label="CHI líquido" value={decimalFormat(data.chi_liquido, 2)} />
        <DrillMetric icon="CI" label="CI líquido" value={numberFormat(data.ci_liquido)} />
      </div>
      <div className="drill-list">
        {data.conjuntos.map((conjunto) => (
          <article key={conjunto.id}>
            <strong>{conjunto.conjunto_exibicao || conjunto.conjunto}</strong>
            <span>{numberFormat(conjunto.ocorrencias)} ocorrências · CHI {decimalFormat(conjunto.chi_liquido, 2)} · CI {numberFormat(conjunto.ci_liquido)}</span>
          </article>
        ))}
        {!data.conjuntos.length && <article><strong>Sem conjunto no Top atual</strong><span>Aumente o limite do cockpit ou use os rankings abaixo para abrir mais detalhes.</span></article>}
      </div>
    </div>
  )
}

function DrillConjunto({ data }) {
  return (
    <div className="drill-view">
      <div className="drill-metric-grid drill-metric-grid-five">
        <DrillMetric icon="!" label="Ocorrências" value={numberFormat(data.ocorrencias)} />
        <DrillMetric icon="CHI" label="CHI líquido" value={decimalFormat(data.chi_liquido, 2)} />
        <DrillMetric icon="CI" label="CI líquido" value={numberFormat(data.ci_liquido)} />
        <DrillMetric icon="LONG" label="Longas" value={numberFormat(data.ocorrencias_longas)} />
        <DrillMetric icon="NF" label="CI não faturado" value={numberFormat(data.ci_nao_faturado)} />
      </div>
      <article className="drill-card">
        <div className="drill-card-title">
          <strong>{data.conjunto_exibicao || data.conjunto}</strong>
          <DrillStatus tone="warning">{data.regional_exibicao || data.regional}</DrillStatus>
        </div>
        <p>Expurgo dia crítico: CHI {decimalFormat(data.chi_expurgo_dia_critico, 2)} · CI {numberFormat(data.ci_expurgo_dia_critico)}</p>
        <p>Expurgo ISE/DISE: CHI {decimalFormat(data.chi_expurgo_ise, 2)} · CI {numberFormat(data.ci_expurgo_ise)}</p>
        <p>Não faturados: CHI {decimalFormat(data.chi_nao_faturado, 2)} · CI {numberFormat(data.ci_nao_faturado)}</p>
        <p>Para ocorrências e correção, use o detalhe real abaixo: clique no conjunto em `Top conjuntos`, depois no alimentador e ocorrência.</p>
      </article>
    </div>
  )
}

function SuspeitaRaPanel({ suspeitasRa }) {
  const raColumns = [
    { key: 'CLASSIFICACAO', label: 'Classificação' },
    { key: 'REGIONAL', label: 'Regional' },
    { key: 'CONJUNTO', label: 'Conjunto' },
    { key: 'ALIM_INTRP', label: 'Alimentador' },
    { key: 'NUM_OPER_CHV_INTRP', label: 'Equipamento' },
    { key: 'DIA_OPERACAO', label: 'Dia' },
    { key: 'SCORE_SUSPEITA_RA', label: 'Score', render: (row) => decimalFormat(row.SCORE_SUSPEITA_RA, 1) },
    { key: 'QTD_OCORRENCIAS_RA', label: 'Ocorrências RA', render: (row) => numberFormat(row.QTD_OCORRENCIAS_RA) },
    {
      key: 'QTD_SERVICOS_TOTAL',
      label: 'Serviços',
      render: (row) => <MetricPair topLabel="Serviços" topValue={numberFormat(row.QTD_SERVICOS_TOTAL)} bottomLabel="Sem serviço" bottomValue={numberFormat(row.QTD_INTERRUPCOES_SEM_SERVICO)} />,
      sortValue: (row) => row.QTD_SERVICOS_TOTAL,
    },
    { key: 'UCS_FIC_RECORRENTE_ALIM_DIA', label: 'UCs FIC ≥ 3', render: (row) => numberFormat(row.UCS_FIC_RECORRENTE_ALIM_DIA) },
    { key: 'QTD_RECLAMACOES_ALIM_DIA', label: 'Reclamações', render: (row) => numberFormat(row.QTD_RECLAMACOES_ALIM_DIA) },
    { key: 'COMP_FIC_ESTIMADA', label: 'Comp. FIC', render: (row) => currencyFormat(row.COMP_FIC_ESTIMADA) },
  ]

  return (
    <section className="panel">
      <div className="panel-title">
        <div>
          <h2>Suspeita falha RA</h2>
          <p>Religadores automáticos com FIC recorrente, baixa reclamação e possível falha de comunicação.</p>
        </div>
        <span className={`pill pill-${suspeitasRa?.status === 'ok' ? 'success' : 'warning'}`}>{suspeitasRa?.status || 'carregando'}</span>
      </div>
      <div className="summary-strip">
        <span><strong>{numberFormat(suspeitasRa?.resumo?.equipamentos_dia)}</strong> equipamento(s)/dia</span>
        <span><strong>{numberFormat(suspeitasRa?.resumo?.ocorrencias_detalhadas)}</strong> ocorrência(s)</span>
        <span><strong>{currencyFormat(suspeitasRa?.resumo?.comp_fic_estimado)}</strong> comp. FIC estimada</span>
        <span><strong>{numberFormat(suspeitasRa?.resumo?.ci_liquido)}</strong> FIC/CI gerado</span>
        <span><strong>{numberFormat(suspeitasRa?.resumo?.zero_reclamacao)}</strong> zero reclamação</span>
        <span><strong>{numberFormat(suspeitasRa?.resumo?.servicos)}</strong> serviço(s)</span>
        <span><strong>{numberFormat(suspeitasRa?.resumo?.interrupcoes_sem_servico)}</strong> interrupção(ões) sem serviço</span>
      </div>
      <DataTable
        columns={raColumns}
        rows={suspeitasRa?.items || []}
        sortable
        initialSort={{ key: 'SCORE_SUSPEITA_RA', direction: 'desc' }}
        empty="Sem suspeitas RA carregadas."
      />
      <p className="panel-footnote">Regra: recomenda investigação técnica; não altera IQS automaticamente.</p>
    </section>
  )
}

function IqsValidationPanel({ validacaoIqs }) {
  const iqsValidationColumns = [
    {
      key: 'status',
      label: 'Status',
      render: (row) => <span className={`pill pill-${row.severidade === 'bloqueante' ? 'warning' : row.severidade === 'atenção' ? 'info' : 'success'}`}>{row.status}</span>,
    },
    { key: 'titulo', label: 'Validação' },
    { key: 'mensagem', label: 'Mensagem' },
  ]

  return (
    <section className="panel">
      <div className="panel-title">
        <div>
          <h2>Pré-validação IQS</h2>
          <p>Checklist governado antes de gerar arquivo físico no padrão aceito pelo IQS.</p>
        </div>
        <span className={`pill pill-${validacaoIqs?.status === 'bloqueado' ? 'warning' : 'info'}`}>{validacaoIqs?.status || 'carregando'}</span>
      </div>
      <div className="summary-strip">
        <span><strong>{numberFormat(validacaoIqs?.resumo?.checks)}</strong> checks</span>
        <span><strong>{numberFormat(validacaoIqs?.resumo?.bloqueantes)}</strong> bloqueante(s)</span>
        <span><strong>{numberFormat(validacaoIqs?.resumo?.pendentes)}</strong> pendente(s)</span>
      </div>
      <DataTable
        columns={iqsValidationColumns}
        rows={validacaoIqs?.checks || []}
        sortable
        initialSort={{ key: 'status', direction: 'asc' }}
        empty="Sem validações IQS carregadas."
      />
      <p className="panel-footnote">Não gera arquivo: apenas sinaliza bloqueios e pendências físicas como UNIX/LF, encoding e datas.</p>
    </section>
  )
}

function ProdutoAlimentadorDetail({ detail, loading, error, onClose, onOpenOccurrence }) {
  const resumo = detail?.resumo || {}
  const diaColumns = [
    { key: 'dia', label: 'Dia' },
    { key: 'ocorrencias', label: 'Ocorrências', render: (row) => numberFormat(row.ocorrencias) },
    { key: 'interrupcoes_ra', label: 'RA', render: (row) => numberFormat(row.interrupcoes_ra) },
    {
      key: 'ocorrencias_longas',
      label: 'Longas/curtas',
      render: (row) => <MetricPair topLabel="Longas" topValue={numberFormat(row.ocorrencias_longas)} bottomLabel="Curtas" bottomValue={numberFormat(row.ocorrencias_curtas)} />,
      sortValue: (row) => row.ocorrencias_longas,
    },
    { key: 'ucs_operacionais', label: 'UCs OMS', render: (row) => numberFormat(row.ucs_operacionais) },
    { key: 'ucs_fic_recorrente', label: 'UCs FIC ≥ 3', render: (row) => numberFormat(row.ucs_fic_recorrente) },
    { key: 'servicos', label: 'Serviços', render: (row) => numberFormat(row.servicos) },
    { key: 'interrupcoes_sem_servico', label: 'Sem serviço', render: (row) => numberFormat(row.interrupcoes_sem_servico) },
  ]

  const ocorrenciaColumns = [
    { key: 'ocorrencia', label: 'Ocorrência' },
    { key: 'inicio', label: 'Início', render: (row) => dateTime(row.inicio) },
    { key: 'interrupcoes', label: 'Interrupções', render: (row) => numberFormat(row.interrupcoes) },
    { key: 'interrupcoes_ra', label: 'RA', render: (row) => numberFormat(row.interrupcoes_ra) },
    { key: 'equipamentos', label: 'Equipamentos' },
    {
      key: 'servicos',
      label: 'Serviços',
      render: (row) => <MetricPair topLabel="Serviços" topValue={numberFormat(row.servicos)} bottomLabel="Sem serviço" bottomValue={numberFormat(row.interrupcoes_sem_servico)} />,
      sortValue: (row) => row.servicos,
    },
    {
      key: 'chi_liquido',
      label: 'CHI/CI',
      render: (row) => <MetricPair topLabel="CHI" topValue={decimalFormat(row.chi_liquido, 2)} bottomLabel="CI" bottomValue={numberFormat(row.ci_liquido)} />,
      sortValue: (row) => row.chi_liquido,
    },
    { key: 'duracao_maxima_h', label: 'Duração máx.', render: (row) => `${decimalFormat(row.duracao_maxima_h, 2)} h` },
  ]

  const suspeitaColumns = [
    { key: 'CLASSIFICACAO', label: 'Classificação' },
    { key: 'NUM_OPER_CHV_INTRP', label: 'Equipamento' },
    { key: 'DIA_OPERACAO', label: 'Dia' },
    { key: 'SCORE_SUSPEITA_RA', label: 'Score', render: (row) => decimalFormat(row.SCORE_SUSPEITA_RA, 1) },
    { key: 'QTD_OCORRENCIAS_RA', label: 'Ocorrências RA', render: (row) => numberFormat(row.QTD_OCORRENCIAS_RA) },
    {
      key: 'QTD_SERVICOS_TOTAL',
      label: 'Serviços',
      render: (row) => <MetricPair topLabel="Serviços" topValue={numberFormat(row.QTD_SERVICOS_TOTAL)} bottomLabel="Sem serviço" bottomValue={numberFormat(row.QTD_INTERRUPCOES_SEM_SERVICO)} />,
      sortValue: (row) => row.QTD_SERVICOS_TOTAL,
    },
    { key: 'UCS_FIC_RECORRENTE_ALIM_DIA', label: 'UCs FIC ≥ 3', render: (row) => numberFormat(row.UCS_FIC_RECORRENTE_ALIM_DIA) },
    { key: 'QTD_RECLAMACOES_ALIM_DIA', label: 'Reclamações', render: (row) => numberFormat(row.QTD_RECLAMACOES_ALIM_DIA) },
    { key: 'COMP_FIC_ESTIMADA', label: 'Comp. FIC', render: (row) => currencyFormat(row.COMP_FIC_ESTIMADA) },
  ]

  return (
    <section id="produto-detalhe-alimentador" className="panel product-detail-panel">
      <div className="panel-title">
        <div>
          <h2>Detalhe do alimentador</h2>
          <p>{resumo.alimentador_exibicao || 'Selecione um alimentador para abrir a leitura operacional.'}</p>
        </div>
        <button className="secondary-button" type="button" onClick={onClose}>Fechar alimentador</button>
      </div>
      <div className="product-breadcrumb" aria-label="Trilha do drill-down">
        <a href="#produto-rankings">Rankings</a>
        <span>›</span>
        <a href="#produto-detalhe-conjunto">{resumo.conjunto_exibicao || 'Conjunto'}</a>
        <span>›</span>
        <strong>{resumo.alimentador_exibicao || 'Alimentador'}</strong>
      </div>
      {loading && <div className="alert">Carregando detalhe do alimentador...</div>}
      {error && <div className="alert">Erro no alimentador: {error}</div>}

      <div className="lens-split">
        <div className="lens-box">
          <span className="pill pill-info">Lente regulatória</span>
          <div className="metrics-grid compact">
            <Card label="DIC/CHI líquido" value={decimalFormat(resumo.chi_liquido, 2)} hint="UCs faturadas/apuráveis" tone="orange" />
            <Card label="FIC/CI líquido" value={numberFormat(resumo.ci_liquido)} hint="base regulatória" tone="purple" />
            <Card label="UCs apuráveis" value={numberFormat(resumo.ucs_apuraveis)} hint="PRODIST/DIC/FIC" tone="blue" />
          </div>
        </div>
        <div className="lens-box">
          <span className="pill pill-warning">Lente cliente/operação</span>
          <div className="metrics-grid compact">
            <Card label="Ocorrências" value={numberFormat(resumo.ocorrencias)} hint={resumo.conjunto_exibicao || 'conjunto'} tone="blue" />
            <Card label="Interrupções RA" value={numberFormat(resumo.interrupcoes_ra)} hint={`${numberFormat(resumo.equipamentos_ra)} equipamento(s)`} tone="orange" />
            <Card label="Reclamações" value={numberFormat(resumo.reclamacoes)} hint={`${numberFormat(resumo.ucs_reclamantes)} UC(s) reclamantes`} tone="green" />
          </div>
        </div>
      </div>

      <div className="summary-strip">
        <span><strong>{numberFormat(resumo.ocorrencias_longas)}</strong> ocorrência(s) longa(s)</span>
        <span><strong>{numberFormat(resumo.ocorrencias_curtas)}</strong> ocorrência(s) curta(s)</span>
        <span><strong>{numberFormat(resumo.ucs_operacionais)}</strong> UCs OMS/operação</span>
        <span><strong>{decimalFormat(resumo.duracao_maxima_h, 2)} h</strong> duração máxima</span>
        <span><strong>{numberFormat(resumo.servicos)}</strong> serviço(s) ADMS</span>
        <span><strong>{numberFormat(resumo.interrupcoes_sem_servico)}</strong> interrupção(ões) sem serviço</span>
      </div>

      <div className="product-grid product-grid-wide">
        <div className="panel panel-nested">
          <div className="panel-title">
            <div>
              <h3>Reincidência por dia</h3>
              <p>Base para identificar FIC recorrente e baixa reclamação proporcional.</p>
            </div>
          </div>
          <DataTable columns={diaColumns} rows={detail?.dias || []} sortable initialSort={{ key: 'ocorrencias', direction: 'desc' }} empty="Sem recorrência diária." />
        </div>
        <div className="panel panel-nested">
          <div className="panel-title">
            <div>
              <h3>Suspeita falha RA</h3>
              <p>Fila técnica: algoritmo recomenda investigação, não altera IQS automaticamente.</p>
            </div>
          </div>
          <DataTable columns={suspeitaColumns} rows={detail?.suspeitas_ra || []} sortable initialSort={{ key: 'SCORE_SUSPEITA_RA', direction: 'desc' }} empty="Sem suspeita RA forte para este alimentador." />
        </div>
      </div>

      <div className="panel panel-nested">
        <div className="panel-title">
          <div>
            <h3>Ocorrências do alimentador</h3>
            <p>Clique para abrir o detalhe técnico com UC, serviço e reclamação quando disponível.</p>
          </div>
        </div>
        <DataTable
          columns={ocorrenciaColumns}
          rows={detail?.ocorrencias || []}
          sortable
          initialSort={{ key: 'chi_liquido', direction: 'desc' }}
          onRowClick={(row) => onOpenOccurrence?.(row.ocorrencia)}
          rowKey={(row) => `alimentador-ocorrencia-${row.ocorrencia}`}
          empty="Sem ocorrências para este alimentador."
        />
      </div>
    </section>
  )
}

function ProdutoConjuntoDetail({ detail, loading, error, onClose, onOpenOccurrence, onOpenAlimentador }) {
  const resumo = detail?.resumo || {}
  const alimentadorColumns = [
    {
      key: 'alimentador_exibicao',
      label: 'Alimentador',
      render: (row) => <CodeLabel codigo={row.alimentador} nome={row.alimentador_nome} descricao="descrição não disponível" />,
      sortValue: (row) => row.alimentador,
    },
    { key: 'ocorrencias', label: 'Ocorrências', render: (row) => numberFormat(row.ocorrencias) },
    {
      key: 'ocorrencias_longas',
      label: 'Longas/curtas',
      render: (row) => (
        <MetricPair
          topLabel="Longas ≥ 3 min"
          topValue={numberFormat(row.ocorrencias_longas)}
          bottomLabel="Curtas < 3 min"
          bottomValue={numberFormat(row.ocorrencias_curtas)}
        />
      ),
      sortValue: (row) => row.ocorrencias_longas,
    },
    {
      key: 'chi_liquido',
      label: 'CHI/CI líquido',
      render: (row) => <MetricPair topLabel="CHI" topValue={decimalFormat(row.chi_liquido, 2)} bottomLabel="CI" bottomValue={numberFormat(row.ci_liquido)} />,
      sortValue: (row) => row.chi_liquido,
    },
    { key: 'ucs', label: 'UCs', render: (row) => numberFormat(row.ucs) },
    { key: 'duracao_maxima_h', label: 'Duração máx.', render: (row) => `${decimalFormat(row.duracao_maxima_h, 2)} h` },
  ]

  const ocorrenciaColumns = [
    { key: 'ocorrencia', label: 'Ocorrência' },
    {
      key: 'alimentador_exibicao',
      label: 'Alimentador',
      render: (row) => <CodeLabel codigo={row.alimentador} nome={row.alimentador_nome} descricao="descrição não disponível" />,
      sortValue: (row) => row.alimentador,
    },
    { key: 'inicio', label: 'Início', render: (row) => dateTime(row.inicio) },
    {
      key: 'chi_liquido',
      label: 'CHI/CI',
      render: (row) => <MetricPair topLabel="CHI" topValue={decimalFormat(row.chi_liquido, 2)} bottomLabel="CI" bottomValue={numberFormat(row.ci_liquido)} />,
      sortValue: (row) => row.chi_liquido,
    },
    { key: 'ucs', label: 'UCs', render: (row) => numberFormat(row.ucs) },
    { key: 'duracao_maxima_h', label: 'Duração máx.', render: (row) => `${decimalFormat(row.duracao_maxima_h, 2)} h` },
    { key: 'componentes', label: 'Comp./causa', render: (row) => `${row.componentes || '—'} / ${row.causas || '—'}` },
  ]

  const componenteColumns = [
    { key: 'grupo_exibicao', label: 'Grupo' },
    { key: 'componente_exibicao', label: 'Componente' },
    { key: 'causa_exibicao', label: 'Causa' },
    { key: 'ocorrencias', label: 'Ocorrências', render: (row) => numberFormat(row.ocorrencias) },
    {
      key: 'chi_liquido',
      label: 'CHI/CI',
      render: (row) => <MetricPair topLabel="CHI" topValue={decimalFormat(row.chi_liquido, 2)} bottomLabel="CI" bottomValue={numberFormat(row.ci_liquido)} />,
      sortValue: (row) => row.chi_liquido,
    },
  ]

  return (
    <section id="produto-detalhe-conjunto" className="panel product-detail-panel">
      <div className="panel-title">
        <div>
          <h2>Detalhe do conjunto</h2>
          <p>{resumo.conjunto_exibicao || 'Selecione um conjunto no ranking para abrir o drill-down intermediário.'}</p>
        </div>
        <button className="secondary-button" type="button" onClick={onClose}>Fechar detalhe</button>
      </div>
      <div className="product-breadcrumb" aria-label="Trilha do drill-down">
        <a href="#produto-rankings">Rankings</a>
        <span>›</span>
        <strong>{resumo.conjunto_exibicao || 'Conjunto'}</strong>
      </div>

      {loading && <div className="alert">Carregando detalhe do conjunto...</div>}
      {error && <div className="alert">Erro no detalhe: {error}</div>}

      <div className="metrics-grid compact">
        <Card label="Ocorrências" value={numberFormat(resumo.ocorrencias)} hint={resumo.regional_exibicao || 'regional'} tone="blue" />
        <Card label="UCs" value={numberFormat(resumo.ucs)} hint="UCs apuráveis no conjunto" tone="green" />
        <Card label="DIC/CHI líquido" value={decimalFormat(resumo.chi_liquido, 2)} hint="soma regulatória do conjunto" tone="orange" />
        <Card label="FIC/CI líquido" value={numberFormat(resumo.ci_liquido)} hint="soma regulatória do conjunto" tone="purple" />
        <Card label="DEC estimado" value={decimalFormat(resumo.dec_liquido_estimado, 2)} hint="CHI ÷ UC faturada COPEL" tone="blue" />
        <Card label="FEC estimado" value={decimalFormat(resumo.fec_liquido_estimado, 2)} hint="CI ÷ UC faturada COPEL" tone="blue" />
      </div>

      <div className="summary-strip">
        <span><strong>{numberFormat(resumo.linhas_longas)}</strong> linha(s) longa(s)</span>
        <span><strong>{numberFormat(resumo.linhas_curtas)}</strong> linha(s) curta(s)</span>
        <span><strong>{decimalFormat(resumo.chi_expurgo_dia_critico, 2)}</strong> CHI dia crítico</span>
        <span><strong>{decimalFormat(resumo.chi_expurgo_ise, 2)}</strong> CHI ISE/DISE</span>
        <span><strong>{numberFormat(resumo.denominador_copel)}</strong> UC faturada COPEL</span>
      </div>

      <div className="product-grid product-grid-wide">
        <div className="panel panel-nested">
          <div className="panel-title">
            <div>
              <h3>Alimentadores do conjunto</h3>
              <p>Prioriza alimentadores por impacto regulatório e volume de ocorrências.</p>
            </div>
          </div>
          <DataTable
            columns={alimentadorColumns}
            rows={detail?.alimentadores || []}
            sortable
            initialSort={{ key: 'chi_liquido', direction: 'desc' }}
            onRowClick={(row) => onOpenAlimentador?.(row)}
            rowKey={(row) => `alimentador-${row.alimentador}`}
            empty="Sem alimentadores para este conjunto."
          />
        </div>

        <div className="panel panel-nested">
          <div className="panel-title">
            <div>
              <h3>Grupo/componente/causa</h3>
              <p>Códigos técnicos com descrição quando a referência IQS está disponível.</p>
            </div>
          </div>
          <DataTable
            columns={componenteColumns}
            rows={detail?.componentes_causas || []}
            sortable
            initialSort={{ key: 'chi_liquido', direction: 'desc' }}
            empty="Sem composição técnica para este conjunto."
          />
        </div>
      </div>

      <div className="panel panel-nested">
        <div className="panel-title">
          <div>
            <h3>Ocorrências para investigação</h3>
            <p>Lista curta para direcionar o analista; clique na ocorrência para abrir o detalhe técnico completo.</p>
          </div>
        </div>
        <DataTable
          columns={ocorrenciaColumns}
          rows={detail?.ocorrencias || []}
          sortable
          initialSort={{ key: 'chi_liquido', direction: 'desc' }}
          onRowClick={(row) => onOpenOccurrence?.(row.ocorrencia)}
          rowKey={(row) => `ocorrencia-${row.ocorrencia}`}
          empty="Sem ocorrências para este conjunto."
        />
      </div>
    </section>
  )
}

function ProdutoPage({ visao, dicionarios, cockpit, token, onOpenOccurrence }) {
  const [tableFilter, setTableFilter] = useState('')
  const [conjuntoDetail, setConjuntoDetail] = useState(null)
  const [conjuntoDetailLoading, setConjuntoDetailLoading] = useState(false)
  const [conjuntoDetailError, setConjuntoDetailError] = useState('')
  const [alimentadorDetail, setAlimentadorDetail] = useState(null)
  const [alimentadorDetailLoading, setAlimentadorDetailLoading] = useState(false)
  const [alimentadorDetailError, setAlimentadorDetailError] = useState('')
  const paginas = visao?.paginas_react || []
  const dictionaryItems = dicionarios?.items || []
  const filteredPages = useMemo(() => {
    const term = tableFilter.trim().toLowerCase()
    if (!term) return paginas
    return paginas.filter((page) =>
      [page.codigo, page.nome, page.objetivo, page.status].some((value) =>
        String(value || '').toLowerCase().includes(term),
      ),
    )
  }, [paginas, tableFilter])

  const dictionaryTypes = useMemo(() => {
    const types = new Map()
    dictionaryItems.forEach((item) => {
      if (!types.has(item.tipo)) types.set(item.tipo, item.tipo_nome || item.tipo)
    })
    return [...types.entries()].sort((left, right) => left[1].localeCompare(right[1], 'pt-BR'))
  }, [dictionaryItems])

  const dictionaryStats = useMemo(() => {
    const labels = new Map(dictionaryTypes)
    const tipos = dicionarios?.resumo?.tipos || {}
    const rows = Object.entries(tipos)
      .map(([tipo, totalTipo]) => ({
        tipo,
        nome: labels.get(tipo) || tipo,
        total: Number(totalTipo || 0),
      }))
      .sort((left, right) => right.total - left.total || left.nome.localeCompare(right.nome, 'pt-BR'))
    const pendentes = dictionaryItems.filter((item) => item.status === 'nome_pendente' || !item.descricao_disponivel).length
    const comDescricao = dictionaryItems.filter((item) => item.descricao_disponivel).length
    return {
      rows,
      pendentes,
      comDescricao,
      cobertura: dictionaryItems.length ? comDescricao / dictionaryItems.length : 0,
    }
  }, [dicionarios, dictionaryItems, dictionaryTypes])

  const pageColumns = [
    { key: 'nome', label: 'Página' },
    { key: 'objetivo', label: 'Objetivo' },
    {
      key: 'status',
      label: 'Status',
      render: (row) => <span className={`pill pill-${statusTone[row.status] || 'info'}`}>{row.status}</span>,
    },
  ]

  const statusTone = {
    implementado: 'success',
    implementado_inicial: 'success',
    iniciada: 'warning',
    planejada: 'info',
    existente_a_reorientar: 'warning',
    existente_a_expandir: 'warning',
  }

  async function handleOpenConjunto(row) {
    if (!row?.conjunto || !token) return
    try {
      setConjuntoDetailLoading(true)
      setConjuntoDetailError('')
      setConjuntoDetail({
        status: 'carregando',
        resumo: {
          ...row,
          conjunto_exibicao: row.conjunto_exibicao,
          dec_liquido_estimado: 0,
          fec_liquido_estimado: 0,
        },
        alimentadores: [],
        ocorrencias: [],
        componentes_causas: [],
      })
      const response = await fetch(
        `${API_URL}/api/produto/detalhe-conjunto/${encodeURIComponent(row.conjunto)}?limite_alimentadores=20&limite_ocorrencias=30`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao consultar detalhe do conjunto.')
      }
      setConjuntoDetail(result)
      setAlimentadorDetail(null)
      setAlimentadorDetailError('')
    } catch (requestError) {
      setConjuntoDetailError(requestError.message)
    } finally {
      setConjuntoDetailLoading(false)
    }
  }

  async function handleOpenAlimentador(row) {
    if (!row?.alimentador || !token) return
    try {
      setAlimentadorDetailLoading(true)
      setAlimentadorDetailError('')
      setAlimentadorDetail({
        status: 'carregando',
        resumo: {
          ...row,
          alimentador_exibicao: row.alimentador_exibicao,
          conjunto: conjuntoDetail?.conjunto || row.conjunto_codigo,
        },
        dias: [],
        ocorrencias: [],
        suspeitas_ra: [],
      })
      const conjuntoParam = conjuntoDetail?.conjunto ? `&conjunto=${encodeURIComponent(conjuntoDetail.conjunto)}` : ''
      const response = await fetch(
        `${API_URL}/api/produto/detalhe-alimentador/${encodeURIComponent(row.alimentador)}?limite_ocorrencias=30${conjuntoParam}`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao consultar detalhe do alimentador.')
      }
      setAlimentadorDetail(result)
    } catch (requestError) {
      setAlimentadorDetailError(requestError.message)
    } finally {
      setAlimentadorDetailLoading(false)
    }
  }

  const conjuntoColumns = [
    { key: 'regional_exibicao', label: 'Regional' },
    {
      key: 'conjunto_exibicao',
      label: 'Conjunto',
      render: (row) => <CodeLabel codigo={row.conjunto} nome={row.conjunto_nome} descricao="descrição não disponível" />,
      sortValue: (row) => row.conjunto,
    },
    {
      key: 'ocorrencias_longas',
      label: 'Ocor. longas/curtas',
      render: (row) => (
        <MetricPair
          topLabel="Longas ≥ 3 min"
          topValue={numberFormat(row.ocorrencias_longas)}
          bottomLabel="Curtas < 3 min"
          bottomValue={numberFormat(row.ocorrencias_curtas)}
        />
      ),
      sortValue: (row) => row.ocorrencias_longas,
    },
    {
      key: 'chi_liquido',
      label: 'Líquido CHI/CI',
      render: (row) => <MetricPair topLabel="CHI" topValue={decimalFormat(row.chi_liquido, 2)} bottomLabel="CI" bottomValue={numberFormat(row.ci_liquido)} />,
      sortValue: (row) => row.chi_liquido,
    },
    {
      key: 'chi_expurgo_dia_critico',
      label: 'Expurgo dia crítico',
      render: (row) => (
        <MetricPair
          topLabel="CHI"
          topValue={decimalFormat(row.chi_expurgo_dia_critico, 2)}
          bottomLabel="CI"
          bottomValue={numberFormat(row.ci_expurgo_dia_critico)}
        />
      ),
      sortValue: (row) => row.chi_expurgo_dia_critico,
    },
    {
      key: 'chi_expurgo_ise',
      label: 'Expurgo ISE',
      render: (row) => (
        <MetricPair
          topLabel="CHI"
          topValue={decimalFormat(row.chi_expurgo_ise, 2)}
          bottomLabel="CI"
          bottomValue={numberFormat(row.ci_expurgo_ise)}
        />
      ),
      sortValue: (row) => row.chi_expurgo_ise,
    },
    {
      key: 'chi_nao_faturado',
      label: 'Não faturado',
      render: (row) => (
        <MetricPair
          topLabel="CHI"
          topValue={decimalFormat(row.chi_nao_faturado, 2)}
          bottomLabel="CI"
          bottomValue={numberFormat(row.ci_nao_faturado)}
        />
      ),
      sortValue: (row) => row.chi_nao_faturado,
    },
  ]

  return (
    <>
      <PageHero
        eyebrow="Sprint 02"
        title="Visão de Produto Governada"
        description="Base paralela para evoluir React, manter Streamlit como laboratório e orientar decisões humanas com evidências, impacto e código + descrição."
        sideLabel="Status"
        sideValue={visao?.sprint?.status || 'contrato'}
        sideContent={<MiniDatabaseStatus health={{ database: { status: visao ? 'ok' : 'carregando', tables: 0, views: 0 } }} />}
      />

      {!visao && <div className="alert">Carregando visão de produto...</div>}

      <nav className="product-nav" aria-label="Navegação da página Produto">
        <a className="product-nav-link" href="#produto-rankings">Top conjuntos</a>
        {conjuntoDetail && <a className="product-nav-link product-nav-link-active" href="#produto-detalhe-conjunto">Conjunto</a>}
        {alimentadorDetail && <a className="product-nav-link product-nav-link-active" href="#produto-detalhe-alimentador">Alimentador</a>}
        <a className="product-nav-link" href="#produto-governanca">Governança</a>
      </nav>

      <section id="produto-overview" className="metrics-grid compact">
        <Card label="Lentes" value={numberFormat(visao?.lentes?.length)} hint="regulatória + cliente/operação" tone="blue" />
        <Card label="Níveis" value={numberFormat(visao?.niveis?.length)} hint="macro, intermediário, detalhe" tone="green" />
        <Card label="Páginas" value={numberFormat(visao?.paginas_react?.length)} hint="mapa React da sprint" tone="orange" />
        <Card label="Dicionários" value={numberFormat(dicionarios?.resumo?.total_disponivel || visao?.dicionarios_humanos?.length)} hint="código + descrição" tone="purple" />
      </section>

      <section id="produto-rankings" className="product-stack product-section-anchor">
        <div className="panel">
          <div className="panel-title">
            <div>
              <h2>Top conjuntos</h2>
              <p>Ocorrências longas usam corte ≥ 3 minutos; expurgos Dia Crítico/ISE e não faturados mostram CHI e CI.</p>
            </div>
          </div>
          <DataTable
            columns={conjuntoColumns}
            rows={cockpit?.rankings?.conjunto || []}
            sortable
            initialSort={{ key: 'chi_liquido', direction: 'desc' }}
            onRowClick={handleOpenConjunto}
            rowKey={(row) => `conjunto-${row.conjunto}`}
            empty="Ranking de conjuntos indisponível."
          />
        </div>
      </section>

      {(conjuntoDetail || conjuntoDetailLoading || conjuntoDetailError) && (
        <ProdutoConjuntoDetail
          detail={conjuntoDetail}
          loading={conjuntoDetailLoading}
          error={conjuntoDetailError}
          onOpenOccurrence={onOpenOccurrence}
          onOpenAlimentador={handleOpenAlimentador}
          onClose={() => {
            setConjuntoDetail(null)
            setConjuntoDetailError('')
            setAlimentadorDetail(null)
            setAlimentadorDetailError('')
          }}
        />
      )}

      {(alimentadorDetail || alimentadorDetailLoading || alimentadorDetailError) && (
        <ProdutoAlimentadorDetail
          detail={alimentadorDetail}
          loading={alimentadorDetailLoading}
          error={alimentadorDetailError}
          onOpenOccurrence={onOpenOccurrence}
          onClose={() => {
            setAlimentadorDetail(null)
            setAlimentadorDetailError('')
          }}
        />
      )}

      <section id="produto-governanca" className="product-grid product-section-anchor">
        <div className="panel">
          <div className="panel-title">
            <div>
              <h2>Lentes de análise</h2>
              <p>Separação obrigatória entre PRODIST/faturados e visão cliente/operação.</p>
            </div>
          </div>
          <div className="product-card-list">
            {(visao?.lentes || []).map((lens) => (
              <article className="product-card" key={lens.codigo}>
                <span className="pill pill-info">{lens.nome}</span>
                <p>{lens.descricao}</p>
                <div className="tag-list">
                  {(lens.principais_metricas || []).map((metric) => (
                    <span className="pill" key={metric}>{metric}</span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">
            <div>
              <h2>Níveis de navegação</h2>
              <p>Do risco macro até ocorrência, interrupção e UC.</p>
            </div>
          </div>
          <div className="decision-steps">
            {(visao?.niveis || []).map((level, index) => (
              <span key={level.codigo}>
                <strong>{index + 1}</strong>
                <em>{level.nome}</em>
                <small>{level.descricao}</small>
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="product-grid product-grid-wide">
        <div className="panel">
          <div className="panel-title">
            <div>
              <h2>Mapa React da Sprint 01</h2>
              <p>Tabela interativa inicial: ordenação no cabeçalho e filtro por texto/código.</p>
            </div>
            <label className="product-search">
              <span>Filtrar</span>
              <input
                value={tableFilter}
                onChange={(event) => setTableFilter(event.target.value)}
                placeholder="Página, objetivo ou status"
              />
            </label>
          </div>
          <DataTable
            columns={pageColumns}
            rows={filteredPages}
            sortable
            initialSort={{ key: 'nome', direction: 'asc' }}
            empty="Nenhuma página encontrada para o filtro."
          />
        </div>

        <div className="panel">
          <div className="panel-title">
            <div>
              <h2>Decisão humana assistida</h2>
              <p>O algoritmo recomenda, mas o analista decide e justifica divergências.</p>
            </div>
          </div>
          <div className="decision-box">
            <strong>Regra de ouro</strong>
            <span>{visao?.decisao_humana?.regra_ouro || '—'}</span>
          </div>
          <div className="product-card-list product-card-list-compact">
            {(visao?.decisao_humana?.campos_obrigatorios || []).map((field) => (
              <span className="pill pill-info" key={field}>{field}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="product-grid">
        <div className="panel">
          <div className="panel-title">
            <div>
              <h2>Hierarquia elétrica humana</h2>
              <p>Conjunto e alimentador devem aparecer com número e nome.</p>
            </div>
          </div>
          <div className="product-card-list">
            {(visao?.hierarquia_eletrica || []).map((item) => (
              <article className="product-card" key={item.campo}>
                <span className="pill pill-success">{item.campo}</span>
                <strong>{item.exibicao}</strong>
                <small>{item.obrigatorio ? 'Obrigatório' : 'Quando disponível'}</small>
              </article>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">
            <div>
              <h2>Dicionários humanos</h2>
              <p>Todo código técnico precisa de nome ou descrição para o analista.</p>
            </div>
          </div>
          <div className="product-card-list">
            {(visao?.dicionarios_humanos || []).map((item) => (
              <article className="product-card" key={item.codigo}>
                <strong>{item.codigo}</strong>
                <p>{item.descricao}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Cobertura de dicionários humanos</h2>
            <p>Resumo estatístico da legibilidade dos códigos técnicos usados pelas telas operacionais.</p>
          </div>
          <span className="pill pill-info">sem lista extensa</span>
        </div>
        <div className="summary-strip">
          <span><strong>{numberFormat(dicionarios?.resumo?.total_disponivel)}</strong> códigos mapeados</span>
          <span><strong>{decimalFormat(dictionaryStats.cobertura * 100, 1)}%</strong> com descrição</span>
          <span><strong>{numberFormat(dictionaryStats.pendentes)}</strong> pendência(s) de nome</span>
          <span><strong>{numberFormat(dicionarios?.resumo?.tipos?.alimentador)}</strong> alimentador(es)</span>
          <span><strong>{numberFormat(dicionarios?.resumo?.tipos?.conjunto_eletrico)}</strong> conjunto(s)</span>
        </div>
        <div className="product-stat-layout">
          <div className="anomaly-bar-list">
            {dictionaryStats.rows.slice(0, 8).map((row) => (
              <span key={row.tipo}>
                <small>{row.nome}</small>
                <strong style={{ width: `${Math.max(8, (row.total / Math.max(dicionarios?.resumo?.total_disponivel || 1, 1)) * 100)}%` }}>{numberFormat(row.total)}</strong>
              </span>
            ))}
          </div>
          <div className="decision-box">
            <strong>Para que serve aqui?</strong>
            <span>
              Apenas medir cobertura de leitura humana. A busca detalhada por código deve ficar nas telas operacionais ou em uma tela própria de administração de dicionários.
            </span>
          </div>
        </div>
        <p className="panel-footnote">
          Regra: {dicionarios?.regras?.exibicao_humana || 'código - nome/descrição'}; nesta tela Produto entram resumos e qualidade da cobertura, não listas operacionais extensas.
        </p>
      </section>
    </>
  )
}

export default function App() {
  const [activePage, setActivePage] = useState('dashboard')
  const [token, setToken] = useState(() => localStorage.getItem('midway_token') || '')
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem('midway_user')
    return raw ? JSON.parse(raw) : null
  })
  const [health, setHealth] = useState(null)
  const [painel, setPainel] = useState([])
  const [fila, setFila] = useState([])
  const [ajustes, setAjustes] = useState([])
  const [auditoria, setAuditoria] = useState([])
  const [decFec, setDecFec] = useState(null)
  const [modelosIqs, setModelosIqs] = useState([])
  const [geracoesIqs, setGeracoesIqs] = useState([])
  const [anomaliasResumo, setAnomaliasResumo] = useState(null)
  const [anomalias, setAnomalias] = useState([])
  const [anomaliasModulos, setAnomaliasModulos] = useState([])
  const [verificacoes, setVerificacoes] = useState(null)
  const [sqlScripts, setSqlScripts] = useState([])
  const [alteracoes, setAlteracoes] = useState([])
  const [usuarios, setUsuarios] = useState([])
  const [sessoes, setSessoes] = useState([])
  const [resetSenhaEventos, setResetSenhaEventos] = useState([])
  const [perfisFuncoes, setPerfisFuncoes] = useState([])
  const [execucoes, setExecucoes] = useState([])
  const [tiposExecucao, setTiposExecucao] = useState([])
  const [produtoVisao, setProdutoVisao] = useState(null)
  const [produtoDicionarios, setProdutoDicionarios] = useState(null)
  const [produtoCockpit, setProdutoCockpit] = useState(null)
  const [produtoSuspeitasRa, setProdutoSuspeitasRa] = useState(null)
  const [produtoValidacaoIqs, setProdutoValidacaoIqs] = useState(null)
  const [analiseTecnicaResumos, setAnaliseTecnicaResumos] = useState({})
  const [loading, setLoading] = useState(true)
  const [loginLoading, setLoginLoading] = useState(false)
  const [authorizing, setAuthorizing] = useState(false)
  const [savingDecision, setSavingDecision] = useState(false)
  const [generatingIqs, setGeneratingIqs] = useState(false)
  const [runningAlgorithm, setRunningAlgorithm] = useState('')
  const [occurrenceDetail, setOccurrenceDetail] = useState(null)
  const [occurrenceLoading, setOccurrenceLoading] = useState(false)
  const [anomalyDetail, setAnomalyDetail] = useState(null)
  const [anomalyLoading, setAnomalyLoading] = useState(false)
  const [error, setError] = useState('')
  const [actionMessage, setActionMessage] = useState('')

  const clearSession = useCallback((message = '') => {
    localStorage.removeItem('midway_token')
    localStorage.removeItem('midway_user')
    setToken('')
    setUser(null)
    setActivePage('dashboard')
    setActionMessage('')
    if (message) setError(message)
  }, [])

  const load = useCallback(async (options = {}) => {
    const silent = Boolean(options.silent)
    try {
      if (!silent) setLoading(true)
      const authHeaders = token ? { Authorization: `Bearer ${token}` } : {}
      const decFecRequest = fetch(`${API_URL}/api/executivo/9282/dec-fec`).catch(() => null)
      const [healthResponse, painelResponse, decFecResponse, filaResponse, ajustesResponse, auditoriaResponse] = await Promise.all([
        fetch(`${API_URL}/api/health`),
        fetch(`${API_URL}/api/executivo/9282/painel`),
        decFecRequest,
        fetch(`${API_URL}/api/executivo/9282/fila-tecnica?limit=100`),
        fetch(`${API_URL}/api/executivo/9282/ajustes-auto?limit=100`),
        fetch(`${API_URL}/api/executivo/9282/auditoria?limit=100`),
      ])

      const responses = [healthResponse, painelResponse, filaResponse, ajustesResponse, auditoriaResponse]
      const failed = responses.find((response) => !response.ok)
      if (failed) {
        const detail = await failed.json().catch(() => null)
        throw new Error(detail?.detail || 'Falha ao consultar a API MIDWAY.')
      }

      setHealth(await healthResponse.json())
      setPainel(await painelResponse.json())
      setDecFec(decFecResponse?.ok ? await decFecResponse.json() : null)
      setFila(await filaResponse.json())
      setAjustes(await ajustesResponse.json())
      setAuditoria(await auditoriaResponse.json())

      if (token) {
        const meResponse = await fetch(`${API_URL}/api/auth/me`, { headers: authHeaders })
        if (meResponse.status === 401) {
          clearSession('Sessão expirada ou inválida. Faça login novamente.')
          return
        }
        if (!meResponse.ok) {
          const detail = await meResponse.json().catch(() => null)
          throw new Error(detail?.detail || 'Falha ao validar sessão.')
        }
        const currentUser = await meResponse.json()
        localStorage.setItem('midway_user', JSON.stringify(currentUser))
        setUser(currentUser)

        const protectedRequests = [
          fetch(`${API_URL}/api/governanca/verificacoes`, { headers: authHeaders }),
          fetch(`${API_URL}/api/governanca/sql/scripts`, { headers: authHeaders }),
          fetch(`${API_URL}/api/governanca/alteracoes`, { headers: authHeaders }),
          fetch(`${API_URL}/api/governanca/usuarios`, { headers: authHeaders }),
          fetch(`${API_URL}/api/governanca/sessoes`, { headers: authHeaders }),
          fetch(`${API_URL}/api/governanca/reset-senha`, { headers: authHeaders }),
          fetch(`${API_URL}/api/governanca/perfis`, { headers: authHeaders }),
          fetch(`${API_URL}/api/governanca/execucoes`, { headers: authHeaders }),
          fetch(`${API_URL}/api/governanca/execucoes/tipos`, { headers: authHeaders }),
          fetch(`${API_URL}/api/iqs/modelos`, { headers: authHeaders }),
          fetch(`${API_URL}/api/iqs/geracoes`, { headers: authHeaders }),
          fetch(`${API_URL}/api/anomalias`, { headers: authHeaders }),
          fetch(`${API_URL}/api/qualidade/analise-tecnica?problema=violacao_componente_causa&limit=1`, { headers: authHeaders }).catch(() => null),
          fetch(`${API_URL}/api/qualidade/analise-tecnica?problema=duracao_suspeita&limit=1`, { headers: authHeaders }).catch(() => null),
          fetch(`${API_URL}/api/qualidade/analise-tecnica?problema=ressarcimento&limit=1`, { headers: authHeaders }).catch(() => null),
          fetch(`${API_URL}/api/qualidade/analise-tecnica?problema=9282&limit=1`, { headers: authHeaders }).catch(() => null),
          fetch(`${API_URL}/api/produto/visao`, { headers: authHeaders }),
          fetch(`${API_URL}/api/produto/dicionarios?limite=10000`, { headers: authHeaders }),
          fetch(`${API_URL}/api/produto/cockpit?limite=20`, { headers: authHeaders }),
          fetch(`${API_URL}/api/produto/suspeitas-ra?limite=20`, { headers: authHeaders }),
          fetch(`${API_URL}/api/produto/validacao-iqs`, { headers: authHeaders }),
        ]
        const [
          verificacoesResponse,
          sqlResponse,
          alteracoesResponse,
          usuariosResponse,
          sessoesResponse,
          resetSenhaResponse,
          perfisResponse,
          execucoesResponse,
          tiposExecucaoResponse,
          modelosIqsResponse,
          geracoesIqsResponse,
          anomaliasResponse,
          analiseCompCausaResponse,
          analiseDuracaoResponse,
          analiseRessarcimentoResponse,
          analise9282Response,
          produtoVisaoResponse,
          produtoDicionariosResponse,
          produtoCockpitResponse,
          produtoSuspeitasRaResponse,
          produtoValidacaoIqsResponse,
        ] =
          await Promise.all(protectedRequests)
        const protectedResponses = [
          verificacoesResponse,
          sqlResponse,
          alteracoesResponse,
          usuariosResponse,
          sessoesResponse,
          resetSenhaResponse,
          perfisResponse,
          execucoesResponse,
          tiposExecucaoResponse,
          modelosIqsResponse,
          geracoesIqsResponse,
          anomaliasResponse,
          analiseCompCausaResponse,
          analiseDuracaoResponse,
          analiseRessarcimentoResponse,
          analise9282Response,
          produtoVisaoResponse,
          produtoDicionariosResponse,
          produtoCockpitResponse,
          produtoSuspeitasRaResponse,
          produtoValidacaoIqsResponse,
        ]
        if (protectedResponses.some((response) => response?.status === 401)) {
          clearSession('Sessão expirada ou inválida. Faça login novamente.')
          return
        }

        if (verificacoesResponse.ok) setVerificacoes(await verificacoesResponse.json())
        if (sqlResponse.ok) setSqlScripts(await sqlResponse.json())
        if (alteracoesResponse.ok) setAlteracoes(await alteracoesResponse.json())
        if (usuariosResponse.ok) setUsuarios(await usuariosResponse.json())
        if (sessoesResponse.ok) setSessoes(await sessoesResponse.json())
        if (resetSenhaResponse.ok) setResetSenhaEventos(await resetSenhaResponse.json())
        if (perfisResponse.ok) {
          setPerfisFuncoes(await perfisResponse.json())
        } else {
          const detail = await perfisResponse.json().catch(() => null)
          setPerfisFuncoes([])
          setError(detail?.detail || 'Falha ao carregar permissões de perfis.')
        }
        if (execucoesResponse.ok) setExecucoes(await execucoesResponse.json())
        if (tiposExecucaoResponse.ok) setTiposExecucao(await tiposExecucaoResponse.json())
        if (modelosIqsResponse.ok) setModelosIqs(await modelosIqsResponse.json())
        if (geracoesIqsResponse.ok) setGeracoesIqs(await geracoesIqsResponse.json())
        if (anomaliasResponse.ok) {
          const anomalyPayload = await anomaliasResponse.json()
          setAnomaliasResumo(anomalyPayload.resumo)
          setAnomalias(anomalyPayload.items || [])
          setAnomaliasModulos(anomalyPayload.modulos || [])
        }
        const technicalSummaries = {}
        if (analiseCompCausaResponse?.ok) technicalSummaries.violacao_componente_causa = await analiseCompCausaResponse.json()
        if (analiseDuracaoResponse?.ok) technicalSummaries.duracao_suspeita = await analiseDuracaoResponse.json()
        if (analiseRessarcimentoResponse?.ok) technicalSummaries.ressarcimento = await analiseRessarcimentoResponse.json()
        if (analise9282Response?.ok) technicalSummaries.correcao_9282 = await analise9282Response.json()
        setAnaliseTecnicaResumos(technicalSummaries)
        if (produtoVisaoResponse.ok) setProdutoVisao(await produtoVisaoResponse.json())
        if (produtoDicionariosResponse.ok) setProdutoDicionarios(await produtoDicionariosResponse.json())
        if (produtoCockpitResponse.ok) setProdutoCockpit(await produtoCockpitResponse.json())
        if (produtoSuspeitasRaResponse.ok) setProdutoSuspeitasRa(await produtoSuspeitasRaResponse.json())
        if (produtoValidacaoIqsResponse.ok) setProdutoValidacaoIqs(await produtoValidacaoIqsResponse.json())
      }
      setError('')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [clearSession, token])

  const loadExecucoes = useCallback(async () => {
    if (!token) return
    try {
      const response = await fetch(`${API_URL}/api/governanca/execucoes`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (response.status === 401) {
        clearSession('Sessão expirada ou inválida. Faça login novamente.')
        return
      }
      if (!response.ok) return
      setExecucoes(await response.json())
    } catch {
      // Mantém o último status visível; evita abrir endpoints DuckDB durante jobs ativos.
    }
  }, [clearSession, token])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!token) return undefined
    const hasActiveExecution = execucoes.some((execucao) => ['ABERTO', 'PROCESSANDO'].includes(String(execucao.status_lote || '').toUpperCase()))
    if (!hasActiveExecution) return undefined
    const timer = window.setInterval(() => {
      loadExecucoes()
    }, 10000)
    return () => window.clearInterval(timer)
  }, [execucoes, loadExecucoes, token])

  const resumo = painel[0] || {}
  const painelLoaded = painel.length > 0
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

  async function handleAutorizar() {
    try {
      setAuthorizing(true)
      setActionMessage('')
      const response = await fetch(`${API_URL}/api/executivo/9282/autorizar?anomes=${resumo.anomes || '202606'}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao autorizar alterações.')
      }
      setActionMessage(
        `Autorização concluída: ${numberFormat(result.criados)} ajuste(s), ${numberFormat(result.ignorados)} duplicado(s), ${numberFormat(result.manuais_criados)} item(ns) de fila.`,
      )
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setAuthorizing(false)
    }
  }

  async function handleAtualizarAlgoritmo(module) {
    const tipoLote = EXECUCAO_MODULO_MAP[module?.codigo]
    if (!tipoLote) {
      setActionMessage('')
      setError(`Algoritmo ${module?.nome || module?.codigo || '—'} ainda não possui executor backend mapeado.`)
      return
    }
    try {
      setRunningAlgorithm(module.codigo)
      setError('')
      setActionMessage('')
      const response = await fetch(`${API_URL}/api/governanca/execucoes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          tipo_lote: tipoLote,
          anomes: resumo.anomes || '202606',
          parametros: {
            origem_tela: 'tratativas_massa',
            modulo: module.codigo,
            algoritmo: module.nome || module.codigo,
          },
        }),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao solicitar atualização no backend.')
      }
      setActionMessage(`Execução enviada ao backend: ${tipoLote} · lote ${String(result.id_lote || '').slice(0, 8)}. A tela atualizará o status automaticamente.`)
      await loadExecucoes()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setRunningAlgorithm('')
    }
  }

  async function handleAceitarAlgoritmo(module) {
    if (module?.codigo !== 'CORRECAO_9282') {
      setActionMessage('')
      setError(`Aceite governado do algoritmo ${module?.nome || module?.codigo || '—'} ainda não possui endpoint de aprovação em lote. Atualize e visualize as evidências, mas não será enviado ao IQS por esta ação.`)
      return
    }
    setActionMessage(`Aceitando a tratativa em massa do algoritmo ${module?.nome || module?.codigo || '—'} pela rotina governada disponível.`)
    await handleAutorizar()
  }

  function handleRejeitarAlgoritmo(module) {
    setActionMessage('')
    setError(`Rejeição da tratativa em massa do algoritmo ${module?.nome || module?.codigo || '—'} ainda precisa de endpoint governado com justificativa de lote.`)
  }

  async function handleCreateAlteracao(payload) {
    try {
      setSavingDecision(true)
      setError('')
      setActionMessage('')
      const response = await fetch(`${API_URL}/api/governanca/alteracoes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao registrar proposta.')
      }
      setActionMessage(`Proposta registrada para aprovação: ${result.id_alteracao}`)
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSavingDecision(false)
    }
  }

  async function handleCreateGeracaoIqs(payload) {
    try {
      setGeneratingIqs(true)
      setError('')
      setActionMessage('')
      const response = await fetch(`${API_URL}/api/iqs/geracoes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao aprovar geração IQS.')
      }
      setActionMessage(`Geração IQS aprovada: ${result.id_geracao}`)
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setGeneratingIqs(false)
    }
  }

  async function handleOpenOccurrence(numOcorrencia) {
    if (!numOcorrencia) return
    try {
      setOccurrenceLoading(true)
      setOccurrenceDetail({ num_ocorrencia_adms: numOcorrencia })
      const response = await fetch(
        `${API_URL}/api/qualidade/ocorrencias/${encodeURIComponent(numOcorrencia)}?anomes=${resumo.anomes || '202606'}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      )
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao consultar ocorrência.')
      }
      setOccurrenceDetail(result)
    } catch (requestError) {
      setError(requestError.message)
      setOccurrenceDetail(null)
    } finally {
      setOccurrenceLoading(false)
    }
  }

  async function handleOpenAnomalyDetail(idAnomalia) {
    if (!idAnomalia) return
    try {
      setAnomalyLoading(true)
      setAnomalyDetail({ id_anomalia: idAnomalia })
      const response = await fetch(`${API_URL}/api/anomalias/${encodeURIComponent(idAnomalia)}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha ao consultar anomalia.')
      }
      setAnomalyDetail(result)
    } catch (requestError) {
      setError(requestError.message)
      setAnomalyDetail(null)
    } finally {
      setAnomalyLoading(false)
    }
  }

  async function handleRegisterAnomalyDecision(detail, decision) {
    const label = decision === 'aprovar' ? 'aprovação' : 'rejeição'
    const justificativa = window.prompt(`Justificativa para propor ${label} da sugestão:`)
    if (!justificativa) return
    await handleCreateAlteracao({
      anomes: '202606',
      modulo: 'MIDWAY_ANOMALIAS',
      entidade: 'anomalia_v7',
      id_entidade: detail.id_anomalia,
      tipo_alteracao: decision === 'aprovar' ? 'APROVACAO' : 'REJEICAO',
      status_alteracao: 'PENDENTE',
      justificativa: `${justificativa}\n\nAnomalia: ${detail.anomalia_codigo} · Sugestão: ${detail.sugestao?.acao || '—'}`,
      antes: detail.original || {},
      depois: decision === 'aprovar' ? detail.tratado_sugerido || {} : detail.original || {},
    })
  }

  async function decideAlteracao(item, decision) {
    const label = decision === 'aprovar' ? 'aprovação' : 'rejeição'
    const justificativa = window.prompt(`Justificativa da ${label}:`)
    if (!justificativa) return

    try {
      setSavingDecision(true)
      setError('')
      setActionMessage('')
      const response = await fetch(`${API_URL}/api/governanca/alteracoes/${item.id_alteracao}/${decision}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ justificativa }),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || `Falha na ${label}.`)
      }
      setActionMessage(`Proposta ${result.status.toLowerCase()}: ${result.id_alteracao}`)
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSavingDecision(false)
    }
  }

  async function handleLogin(email, senha) {
    try {
      setLoginLoading(true)
      setError('')
      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, senha }),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(result?.detail || 'Falha no login.')
      }
      localStorage.setItem('midway_token', result.access_token)
      localStorage.setItem('midway_user', JSON.stringify(result.user))
      setToken(result.access_token)
      setUser(result.user)
      setActionMessage('')
      setActivePage('dashboard')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoginLoading(false)
    }
  }

  function handleLogout() {
    if (token) {
      fetch(`${API_URL}/api/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {})
    }
    clearSession()
  }

  const pages = {
    dashboard: (
      <DashboardPage
        cards={cards}
        resumo={resumo}
        health={health}
        decFec={decFec}
        cockpit={produtoCockpit}
        modulos={anomaliasModulos}
        analiseTecnicaResumos={analiseTecnicaResumos}
        suspeitasRa={produtoSuspeitasRa}
        token={token}
        onOpenOccurrence={handleOpenOccurrence}
      />
    ),
    tratativas_massa: (
      <TratativasMassaPage
        resumo={resumo}
        modulos={anomaliasModulos}
        analiseTecnicaResumos={analiseTecnicaResumos}
        suspeitasRa={produtoSuspeitasRa}
        execucoes={execucoes}
        onRefresh={load}
        onAtualizarAlgoritmo={handleAtualizarAlgoritmo}
        onAceitarAlgoritmo={handleAceitarAlgoritmo}
        onRejeitarAlgoritmo={handleRejeitarAlgoritmo}
        accepting={authorizing}
        runningAlgorithm={runningAlgorithm}
        loading={loading}
        loaded={painelLoaded}
      />
    ),
    aprovacao: (
      <AprovacaoPage
        resumo={resumo}
        ajustes={ajustes}
        user={user}
        onAutorizar={handleAutorizar}
        actionMessage={actionMessage}
        authorizing={authorizing}
        onOpenOccurrence={handleOpenOccurrence}
      />
    ),
    ocorrencias: (
      <OcorrenciasPage
        resumo={resumo}
        fila={fila}
        token={token}
        onOpenOccurrence={handleOpenOccurrence}
      />
    ),
    alteracoes_manuais: (
      <AlteracoesPage
        alteracoes={alteracoes}
        user={user}
        onCreate={handleCreateAlteracao}
        onApprove={(item) => decideAlteracao(item, 'aprovar')}
        onReject={(item) => decideAlteracao(item, 'rejeitar')}
        savingDecision={savingDecision}
      />
    ),
    executivo: (
      <SaidaIqsPage
        modelosIqs={modelosIqs}
        geracoesIqs={geracoesIqs}
        validacaoIqs={produtoValidacaoIqs}
        user={user}
        onCreateGeracaoIqs={handleCreateGeracaoIqs}
        generatingIqs={generatingIqs}
      />
    ),
    administracao: (
      <AdministracaoPage
        usuarios={usuarios}
        sessoes={sessoes}
        resetSenhaEventos={resetSenhaEventos}
        perfisFuncoes={perfisFuncoes}
        execucoes={execucoes}
        tiposExecucao={tiposExecucao}
        auditoria={auditoria}
        sqlScripts={sqlScripts}
        verificacoes={verificacoes}
        health={health}
        user={user}
        token={token}
        onRefresh={load}
      />
    ),
  }

  if (!token || !user) {
    return <LoginPage onLogin={handleLogin} error={error} loading={loginLoading} />
  }

  return (
    <div className="app-shell">
      <Sidebar activePage={activePage} onChangePage={setActivePage} user={user} onLogout={handleLogout} />
      <main className="main">
        <header className="topbar">
          <button className="hamburger">☰</button>
          <div className="topbar-actions">
            <button className="secondary-button" onClick={load}>Atualizar</button>
            <StatusBadge health={health} />
          </div>
        </header>

        {error && <div className="alert">Erro: {error}</div>}
        {actionMessage && <div className="alert alert-success">{actionMessage}</div>}
        {loading && <div className="alert">Carregando indicadores da API...</div>}

        {pages[activePage] || pages.dashboard}
        {occurrenceDetail && (
          <OccurrenceModal
            detail={occurrenceDetail}
            loading={occurrenceLoading}
            onClose={() => setOccurrenceDetail(null)}
          />
        )}
        {anomalyDetail && (
          <AnomalyDetailModal
            detail={anomalyDetail}
            loading={anomalyLoading}
            onClose={() => setAnomalyDetail(null)}
            onRegisterDecision={handleRegisterAnomalyDecision}
          />
        )}
      </main>
    </div>
  )
}
