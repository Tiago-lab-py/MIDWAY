import React, { useState } from 'react';

export function IqsValidationPanel({ validacaoIqs, DataTable, numberFormat }) {
  const iqsValidationColumns = [
    {
      key: 'status',
      label: 'Status',
      render: (row) => <span className={`pill pill-${row.severidade === 'bloqueante' ? 'warning' : row.severidade === 'atenção' ? 'info' : 'success'}`}>{row.status}</span>,
    },
    { key: 'titulo', label: 'Validação' },
    { key: 'mensagem', label: 'Mensagem' },
  ];

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
  );
}

export function IqsGenerationPanel({
  modelos,
  geracoes,
  user,
  token,
  onCreate,
  generating,
  title = 'Modelos de Tratamento',
  description = 'Selecione um ou vários arquivos. A justificativa será única para todo o processamento.',
  API_URL,
  hasProfile,
  DataTable,
  dateTime
}) {
  const canGenerate = hasProfile(user, ['GESTOR', 'ADM']);
  const [selected, setSelected] = useState([]);
  const [anomes, setAnomes] = useState('202607');
  const [justificativa, setJustificativa] = useState('');

  function toggleModelo(codigo) {
    setSelected((current) =>
      current.includes(codigo) ? current.filter((item) => item !== codigo) : [...current, codigo],
    );
  }

  async function submit(event) {
    event.preventDefault();
    await onCreate({ anomes, modelos: selected, justificativa });
    setSelected([]);
    setJustificativa('');
  }

  async function handleDownload(id_geracao) {
    try {
      const response = await fetch(`${API_URL}/api/iqs/geracoes/${id_geracao}/download`, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      if (!response.ok) {
        let errorDetail = 'Falha ao baixar arquivo';
        try {
          const result = await response.json();
          if (result && result.detail) {
            errorDetail = result.detail;
          }
        } catch (e) {
          // ignore parsing error
        }
        throw new Error(errorDetail);
      }
      
      let filename = `IQS_${id_geracao}.zip`;
      const disposition = response.headers.get('content-disposition');
      if (disposition && disposition.includes('attachment')) {
        const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
        const matches = filenameRegex.exec(disposition);
        if (matches != null && matches[1]) { 
          filename = matches[1].replace(/['"]/g, '');
        }
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.message);
    }
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
            {
              key: 'download',
              label: 'Baixar',
              render: (item) => {
                const status = String(item.status_geracao || '').toUpperCase();
                if (status === 'CONCLUIDA' || status === 'CONCLUIDO' || status === 'APROVADA' || status === 'APROVADO' || status === 'GERADO') {
                  return (
                    <button className="mini-button mini-button-success" onClick={() => handleDownload(item.id_geracao)}>
                      Baixar Arquivos
                    </button>
                  );
                }
                return <span className="muted">—</span>;
              }
            }
          ]}
          rows={geracoes}
        />
      </section>
    </>
  );
}

export default function SaidaIqsPage({
  modelosIqs,
  geracoesIqs,
  validacaoIqs,
  user,
  onCreateGeracaoIqs,
  generatingIqs,
  token,
  PageHero,
  DataTable,
  dateTime,
  numberFormat,
  hasProfile,
  API_URL
}) {
  return (
    <>
      <PageHero
        title="Saída IQS"
        description="Última etapa operacional: validar pré-requisitos e gerar o pacote físico no padrão aceito pelo IQS."
        sideLabel="Perfil"
        sideValue={user?.perfil}
      />

      <IqsValidationPanel 
        validacaoIqs={validacaoIqs} 
        DataTable={DataTable} 
        numberFormat={numberFormat} 
      />

      <IqsGenerationPanel
        modelos={modelosIqs}
        geracoes={geracoesIqs}
        user={user}
        token={token}
        onCreate={onCreateGeracaoIqs}
        generating={generatingIqs}
        API_URL={API_URL}
        hasProfile={hasProfile}
        DataTable={DataTable}
        dateTime={dateTime}
        title="Geração do Arquivo para IQS"
        description="Gere somente após aprovação governada das tratativas. O pacote físico deve respeitar layout, encoding, datas e quebras exigidas pelo IQS."
      />
    </>
  );
}
