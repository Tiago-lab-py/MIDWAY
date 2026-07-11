import React, { useCallback, useEffect, useMemo, useState } from 'react'

const API_URL = import.meta.env.VITE_MIDWAY_API_URL || 'http://127.0.0.1:8000'

const menuItems = [
  { id: 'dashboard', label: 'Dashboard', icon: 'D' },
  { id: 'executivo', label: 'Executivo 92/82', icon: 'E' },
  { id: 'fila', label: 'Fila Técnica', icon: 'F' },
  { id: 'ajustes', label: 'Ajustes IQS', icon: 'A' },
  { id: 'geracao_iqs', label: 'Geração IQS', icon: 'I' },
  { id: 'verificacao', label: 'Verificação Dados', icon: 'V' },
  { id: 'sql', label: 'SQL', icon: 'S' },
  { id: 'alteracoes', label: 'Alterações', icon: 'L' },
  { id: 'auditoria', label: 'Auditoria', icon: 'U' },
  { id: 'governanca', label: 'Governança', icon: 'G' },
  { id: 'configuracoes', label: 'Configurações', icon: 'C' },
]

function numberFormat(value) {
  return new Intl.NumberFormat('pt-BR').format(Number(value || 0))
}

function decimalFormat(value, digits = 4) {
  return new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number(value || 0))
}

function percent(value, total) {
  if (!total) return '0%'
  return `${((Number(value || 0) / Number(total)) * 100).toFixed(1)}%`
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
        {menuItems.map((item) => (
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

function DataTable({ columns, rows, empty = 'Nenhum item encontrado.' }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={row.id_fila || row.id_ajuste || row.id_evento || `${rowIndex}`}>
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
                { key: 'DURACAO_HORA', label: 'Duração' },
                { key: 'CHI_LIQUIDO', label: 'CHI Liq.' },
                { key: 'CI_LIQUIDO', label: 'CI Liq.' },
                { key: 'CHI_BRUTO', label: 'CHI Bruto' },
                { key: 'CI_BRUTO', label: 'CI Bruto' },
                { key: 'CLASSE_TENSAO_PRODIST', label: 'Classe' },
                { key: 'GRUPO_TENSAO', label: 'Tensão' },
                { key: 'VALOR_RESSARCIMENTO', label: 'Ressarcimento' },
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
                { key: 'SCORE_VINCULO_RECLAMACAO', label: 'Score' },
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
  const [login, setLogin] = useState('admin')
  const [senha, setSenha] = useState('')

  function submit(event) {
    event.preventDefault()
    onLogin(login, senha)
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
        <h1>Entrar</h1>
        <p>Use seu usuário MIDWAY. Perfis: ADM, GESTOR ou ANALISTA.</p>
        {error && <div className="alert">Erro: {error}</div>}
        <form onSubmit={submit} className="login-form">
          <label>
            Login
            <input value={login} onChange={(event) => setLogin(event.target.value)} autoComplete="username" />
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
        <small>
          Primeiro acesso: rode `run.bat postgres_governanca` e depois `run.bat admin_bootstrap`.
        </small>
      </section>
    </div>
  )
}

function DashboardPage({ cards, resumo, health, decFec, token, onOpenOccurrence }) {
  const filaTotal = Number(resumo.fila_tecnica_total || 0)
  return (
    <>
      <PageHero
        title="Dashboard Executivo"
        description="Tratativa RA 92/82 com autorização em massa, fila técnica e auditoria PostgreSQL."
        sideLabel="ANOMES"
        sideValue={resumo.anomes}
        sideContent={<MiniDatabaseStatus health={health} />}
      />

      <section className="panel">
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

      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Painel de Ajustes de Componente/Causa</h2>
            <p>Resumo executivo das tratativas RA 92/82 para reclassificação e autorização governada.</p>
          </div>
        </div>
        <section className="metrics-grid compact">
          {cards.map((card) => (
            <Card key={card.label} {...card} />
          ))}
        </section>
        <div className="summary-chart">
          <div />
          <ul>
            <li><span className="dot green" /> Automáticos: {numberFormat(resumo.ajustes_auto_9282)}</li>
            <li><span className="dot orange" /> Fila aberta: {numberFormat(resumo.fila_aberta)}</li>
            <li><span className="dot purple" /> Conflitos: {numberFormat(resumo.fila_servico_conflito)} ({percent(resumo.fila_servico_conflito, filaTotal)})</li>
            <li><span className="dot blue" /> Reclamação: {numberFormat(resumo.fila_reclamacao)} ({percent(resumo.fila_reclamacao, filaTotal)})</li>
          </ul>
        </div>
      </section>

      <FilaPreview anomes={resumo.anomes} token={token} onOpenOccurrence={onOpenOccurrence} />
    </>
  )
}

function ExecutivoPage({ resumo, cards, onAutorizar, actionMessage, authorizing }) {
  return (
    <>
      <PageHero
        title="Executivo 92/82"
        description="Ambiente de decisão: autoriza somente a tratativa automática com evidência robusta por serviço."
        sideLabel="Autorizados"
        sideValue={numberFormat(resumo.qtd_autorizados_autorizacao)}
      />

      <section className="metrics-grid">
        {cards.map((card) => (
          <Card key={card.label} {...card} />
        ))}
      </section>

      {actionMessage && <div className="alert alert-success">{actionMessage}</div>}

      <section className="content-grid">
        <article className="panel panel-large">
          <div className="panel-title">
            <div>
              <h2>Autorização em Massa</h2>
              <p>Regra atual: `SERVICO + ROBUSTA`. Duplicidades são ignoradas pela API.</p>
            </div>
            <button className="primary-button" disabled={authorizing} onClick={onAutorizar}>
              {authorizing ? 'Autorizando...' : 'Autorizar 92/82'}
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
              <h2>Separação operacional</h2>
              <p>O Executivo decide massa; o técnico trata exceções.</p>
            </div>
          </div>
          <div className="stacked-notes">
            <span><strong>Automático</strong> Serviço robusto e par válido.</span>
            <span><strong>Manual</strong> Serviço com conflito ou reclamação.</span>
            <span><strong>Auditoria</strong> Tudo fica registrado no PostgreSQL.</span>
          </div>
        </article>
      </section>
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
          <h2>Busca Técnica 92/82</h2>
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

function FilaPage({ fila, resumo, onOpenOccurrence }) {
  return (
    <>
      <PageHero
        title="Fila Técnica"
        description="Casos problemáticos para suporte técnico: conflito de serviço ou evidência por reclamação."
        sideLabel="Abertos"
        sideValue={numberFormat(resumo.fila_aberta)}
      />
      <section className="metrics-grid compact">
        <Card label="Total na fila" value={numberFormat(resumo.fila_tecnica_total)} hint="RA 92/82" tone="orange" />
        <Card label="Conflito de serviço" value={numberFormat(resumo.fila_servico_conflito)} hint="revisão técnica prioritária" tone="purple" />
        <Card label="Por reclamação" value={numberFormat(resumo.fila_reclamacao)} hint="melhor classificação textual" tone="blue" />
        <Card label="Tratados" value={numberFormat(resumo.fila_tratada)} hint="baixados da fila" tone="green" />
      </section>
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

function AjustesPage({ ajustes, resumo, onOpenOccurrence }) {
  return (
    <>
      <PageHero
        title="Ajustes IQS"
        description="Registros automáticos RA 92/82 autorizados pelo Executivo e prontos para exportação controlada."
        sideLabel="Ajustes"
        sideValue={numberFormat(resumo.ajustes_auto_9282)}
      />
      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Ajustes Automáticos</h2>
            <p>Origem `AUTO_EXECUTIVO_9282`.</p>
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

function GeracaoIqsPage({ modelos, geracoes, user, onCreate, generating }) {
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
      <PageHero
        title="Geração IQS"
        description="Gestor aprova um pacote de modelos/arquivos com justificativa única para implantação no IQS."
        sideLabel="Modelos"
        sideValue={numberFormat(modelos.length)}
      />

      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Modelos de Tratamento</h2>
            <p>Selecione um ou vários arquivos. A justificativa será única para todo o processamento.</p>
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

function AuditoriaPage({ auditoria }) {
  return (
    <>
      <PageHero
        title="Auditoria"
        description="Evidência de autorização em massa, usuário, entidade e resumo operacional."
        sideLabel="Eventos"
        sideValue={numberFormat(auditoria.length)}
      />
      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Eventos 92/82</h2>
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

function VerificacaoPage({ verificacoes, health }) {
  const missingTables = verificacoes?.missing_tables || []
  const missingViews = verificacoes?.missing_views || []
  const missingParameters = verificacoes?.missing_parameters || []
  return (
    <>
      <PageHero
        title="Verificação dos Dados"
        description="Checagens operacionais do PostgreSQL, schema, tabelas, views e parâmetros obrigatórios."
        sideLabel="Status"
        sideValue={verificacoes?.database_ok ? 'OK' : 'Atenção'}
      />
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

function SqlPage({ scripts }) {
  return (
    <>
      <PageHero
        title="SQL Versionado"
        description="Catálogo dos scripts SQL do schema `ddcq` para revisão, aplicação controlada e auditoria."
        sideLabel="Scripts"
        sideValue={numberFormat(scripts.length)}
      />
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

function AlteracoesPage({ alteracoes, user, onCreate, onApprove, onReject, savingDecision }) {
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
      <PageHero
        title="Alterações"
        description="Fluxo governado: Analista cria proposta; Gestor aprova ou rejeita; IQS recebe somente aprovados."
        sideLabel="Registros"
        sideValue={numberFormat(alteracoes.length)}
      />

      {canCreate && (
        <section className="panel">
          <div className="panel-title">
            <div>
              <h2>Nova Proposta de Alteração</h2>
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
                <option value="EXECUTIVO_9282">Executivo 92/82</option>
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

function GovernancaPage({ usuarios, sessoes, user }) {
  return (
    <>
      <PageHero
        title="Governança"
        description="Controle de usuários, sessões, perfis e segregação de funções."
        sideLabel="Perfil"
        sideValue={user?.perfil}
      />
      <section className="content-grid">
        <article className="panel panel-large">
          <div className="panel-title">
            <div>
              <h2>Usuários</h2>
              <p>Perfis disponíveis: ADM, GESTOR e ANALISTA.</p>
            </div>
          </div>
          <DataTable
            columns={[
              { key: 'login', label: 'Login' },
              { key: 'nome', label: 'Nome' },
              { key: 'email', label: 'E-mail' },
              { key: 'perfil', label: 'Perfil', render: (item) => <span className="pill">{item.perfil}</span> },
              { key: 'status_usuario', label: 'Status' },
              { key: 'ultimo_login_em', label: 'Último login', render: (item) => dateTime(item.ultimo_login_em) },
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
              { key: 'login', label: 'Login' },
              { key: 'perfil', label: 'Perfil' },
              { key: 'expira_em', label: 'Expira', render: (item) => dateTime(item.expira_em) },
            ]}
            rows={sessoes}
          />
        </article>
      </section>
    </>
  )
}

function ConfiguracoesPage({ health }) {
  const database = health?.database || {}
  return (
    <>
      <PageHero
        title="Configurações"
        description="Estado da API, conexão PostgreSQL e variáveis utilizadas pelo frontend."
        sideLabel="API"
        sideValue={health?.status || '—'}
      />
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
  const [verificacoes, setVerificacoes] = useState(null)
  const [sqlScripts, setSqlScripts] = useState([])
  const [alteracoes, setAlteracoes] = useState([])
  const [usuarios, setUsuarios] = useState([])
  const [sessoes, setSessoes] = useState([])
  const [loading, setLoading] = useState(true)
  const [loginLoading, setLoginLoading] = useState(false)
  const [authorizing, setAuthorizing] = useState(false)
  const [savingDecision, setSavingDecision] = useState(false)
  const [generatingIqs, setGeneratingIqs] = useState(false)
  const [occurrenceDetail, setOccurrenceDetail] = useState(null)
  const [occurrenceLoading, setOccurrenceLoading] = useState(false)
  const [error, setError] = useState('')
  const [actionMessage, setActionMessage] = useState('')

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const authHeaders = token ? { Authorization: `Bearer ${token}` } : {}
      const [healthResponse, painelResponse, decFecResponse, filaResponse, ajustesResponse, auditoriaResponse] = await Promise.all([
        fetch(`${API_URL}/api/health`),
        fetch(`${API_URL}/api/executivo/9282/painel`),
        fetch(`${API_URL}/api/executivo/9282/dec-fec`),
        fetch(`${API_URL}/api/executivo/9282/fila-tecnica?limit=100`),
        fetch(`${API_URL}/api/executivo/9282/ajustes-auto?limit=100`),
        fetch(`${API_URL}/api/executivo/9282/auditoria?limit=100`),
      ])

      const responses = [healthResponse, painelResponse, decFecResponse, filaResponse, ajustesResponse, auditoriaResponse]
      const failed = responses.find((response) => !response.ok)
      if (failed) {
        const detail = await failed.json().catch(() => null)
        throw new Error(detail?.detail || 'Falha ao consultar a API MIDWAY.')
      }

      setHealth(await healthResponse.json())
      setPainel(await painelResponse.json())
      setDecFec(await decFecResponse.json())
      setFila(await filaResponse.json())
      setAjustes(await ajustesResponse.json())
      setAuditoria(await auditoriaResponse.json())

      if (token) {
        const protectedRequests = [
          fetch(`${API_URL}/api/governanca/verificacoes`, { headers: authHeaders }),
          fetch(`${API_URL}/api/governanca/sql/scripts`, { headers: authHeaders }),
          fetch(`${API_URL}/api/governanca/alteracoes`, { headers: authHeaders }),
          fetch(`${API_URL}/api/governanca/usuarios`, { headers: authHeaders }),
          fetch(`${API_URL}/api/governanca/sessoes`, { headers: authHeaders }),
          fetch(`${API_URL}/api/iqs/modelos`, { headers: authHeaders }),
          fetch(`${API_URL}/api/iqs/geracoes`, { headers: authHeaders }),
        ]
        const [
          verificacoesResponse,
          sqlResponse,
          alteracoesResponse,
          usuariosResponse,
          sessoesResponse,
          modelosIqsResponse,
          geracoesIqsResponse,
        ] =
          await Promise.all(protectedRequests)

        if (verificacoesResponse.ok) setVerificacoes(await verificacoesResponse.json())
        if (sqlResponse.ok) setSqlScripts(await sqlResponse.json())
        if (alteracoesResponse.ok) setAlteracoes(await alteracoesResponse.json())
        if (usuariosResponse.ok) setUsuarios(await usuariosResponse.json())
        if (sessoesResponse.ok) setSessoes(await sessoesResponse.json())
        if (modelosIqsResponse.ok) setModelosIqs(await modelosIqsResponse.json())
        if (geracoesIqsResponse.ok) setGeracoesIqs(await geracoesIqsResponse.json())
      }
      setError('')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    load()
  }, [load])

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
        throw new Error(result?.detail || 'Falha ao autorizar 92/82.')
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

  async function handleLogin(login, senha) {
    try {
      setLoginLoading(true)
      setError('')
      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ login, senha }),
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
    localStorage.removeItem('midway_token')
    localStorage.removeItem('midway_user')
    setToken('')
    setUser(null)
    setActivePage('dashboard')
  }

  const pages = {
    dashboard: (
      <DashboardPage
        cards={cards}
        resumo={resumo}
        health={health}
        decFec={decFec}
        token={token}
        onOpenOccurrence={handleOpenOccurrence}
      />
    ),
    executivo: (
      <ExecutivoPage
        resumo={resumo}
        cards={cards}
        onAutorizar={handleAutorizar}
        actionMessage={actionMessage}
        authorizing={authorizing}
      />
    ),
    fila: <FilaPage fila={fila} resumo={resumo} onOpenOccurrence={handleOpenOccurrence} />,
    ajustes: <AjustesPage ajustes={ajustes} resumo={resumo} onOpenOccurrence={handleOpenOccurrence} />,
    geracao_iqs: (
      <GeracaoIqsPage
        modelos={modelosIqs}
        geracoes={geracoesIqs}
        user={user}
        onCreate={handleCreateGeracaoIqs}
        generating={generatingIqs}
      />
    ),
    verificacao: <VerificacaoPage verificacoes={verificacoes} health={health} />,
    sql: <SqlPage scripts={sqlScripts} />,
    alteracoes: (
      <AlteracoesPage
        alteracoes={alteracoes}
        user={user}
        onCreate={handleCreateAlteracao}
        onApprove={(item) => decideAlteracao(item, 'aprovar')}
        onReject={(item) => decideAlteracao(item, 'rejeitar')}
        savingDecision={savingDecision}
      />
    ),
    auditoria: <AuditoriaPage auditoria={auditoria} />,
    governanca: <GovernancaPage usuarios={usuarios} sessoes={sessoes} user={user} />,
    configuracoes: <ConfiguracoesPage health={health} />,
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

        {pages[activePage]}
        {occurrenceDetail && (
          <OccurrenceModal
            detail={occurrenceDetail}
            loading={occurrenceLoading}
            onClose={() => setOccurrenceDetail(null)}
          />
        )}
      </main>
    </div>
  )
}
