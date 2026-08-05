import React, { useState, useEffect } from 'react';

// Componente isolado para o Módulo ISE
export default function IseSimulation() {
  const [janelas, setJanelas] = useState([]);
  const [formData, setFormData] = useState({
    anomes: '202607',
    regional: 'TODAS',
    data_inicio: '2026-07-01 00:00:00',
    data_fim: '2026-07-01 23:59:59',
  });
  const [simulacaoAtual, setSimulacaoAtual] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const API_URL = import.meta.env.VITE_MIDWAY_API_URL || 'http://127.0.0.1:8000';

  const carregarJanelas = async () => {
    try {
      const res = await fetch(`${API_URL}/ise/janelas`);
      const data = await res.json();
      setJanelas(data.janelas || []);
    } catch (err) {
      console.error('Erro ao carregar janelas', err);
    }
  };

  useEffect(() => {
    carregarJanelas();
    
    // Injeta Plotly.js para o gráfico de recomposição
    if (!document.getElementById('plotly-script')) {
      const script = document.createElement('script');
      script.id = 'plotly-script';
      script.src = 'https://cdn.plot.ly/plotly-2.35.2.min.js';
      script.async = true;
      document.body.appendChild(script);
    }
  }, []);

  useEffect(() => {
    if (simulacaoAtual?.serie_temporal && window.Plotly) {
      const serie = simulacaoAtual.serie_temporal;
      const x = serie.map(s => s.hora);
      const yBar = serie.map(s => s.ci);
      const yRec = serie.map(s => s.rec_pct !== null ? s.rec_pct : null);
      
      const peakTime = simulacaoAtual.metadados_grafico?.peak_time;
      const peakVal = simulacaoAtual.metadados_grafico?.peak_val || 0;

      let peakTimeFmt = peakTime;
      if (peakTime) {
         const d = new Date(peakTime);
         peakTimeFmt = `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
      }

      window.Plotly.newPlot('g_ci', [
        {
          type: 'bar',
          x: x, y: yBar, name: 'CI (hora)',
          opacity: 0.9,
          marker: {color: 'rgba(52, 152, 219, 0.9)'},
          hovertemplate: '%{x}<br>CI hora: %{y:,d} UC<extra></extra>'
        },
        {
          type: 'scatter',
          x: x, y: yRec, name: '% recomposição (hora/pico)',
          mode: 'lines+markers',
          yaxis: 'y2',
          connectgaps: false,
          line: {color: 'rgb(230, 81, 0)', width: 3},
          marker: {color: 'rgb(230, 81, 0)'},
          hovertemplate: '%{x}<br>CI_hora/CI_pico: %{y:.1%}<extra></extra>'
        }
      ], {
        template: 'plotly_white',
        hovermode: 'x unified',
        margin: {t: 30, r: 60, b: 50, l: 60},
        xaxis: { 
          title: 'Hora', 
          tickformat: '%d/%m %H:%M', 
          rangeslider: {visible: false},
          gridcolor: 'rgba(255,255,255,0.05)',
          zerolinecolor: 'rgba(255,255,255,0.1)',
          color: '#94a3b8'
        },
        yaxis: { 
          title: 'CI (UC)', 
          rangemode: 'tozero',
          gridcolor: 'rgba(255,255,255,0.05)',
          zerolinecolor: 'rgba(255,255,255,0.1)',
          color: '#94a3b8'
        },
        yaxis2: { 
          title: '% recomposição pós-pico', 
          overlaying: 'y', 
          side: 'right', 
          rangemode: 'tozero', 
          tickformat: '.0%',
          gridcolor: 'rgba(255,255,255,0.05)',
          zerolinecolor: 'rgba(255,255,255,0.1)',
          color: '#94a3b8'
        },
        legend: {orientation: 'h', y: 1.08, x: 0, font: {color: '#cbd5e1'}},
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        shapes: peakTime ? [
          { 
            type: 'line', x0: peakTime, x1: peakTime, y0: 0, y1: 1, yref: 'paper', 
            line: {dash: 'dot', width: 1, color: '#64748b'}
          }
        ] : [],
        annotations: peakTime ? [
          { 
            x: peakTime, y: 1, yref: 'paper', xanchor: 'left', yanchor: 'top',
            text: `Pico em ${peakTimeFmt} (${peakVal.toLocaleString()} UC)`, showarrow: false,
            font: {color: '#94a3b8'}
          }
        ] : []
      }, {
        displaylogo: false, responsive: true, displayModeBar: false
      });
    }
  }, [simulacaoAtual]);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSalvarJanela = async (e) => {
    e.preventDefault();
    try {
      await fetch(`${API_URL}/ise/janelas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      carregarJanelas();
      alert('Janela salva com sucesso!');
    } catch (err) {
      alert('Erro ao salvar janela.');
    }
  };

  const handleExcluirJanela = async (id) => {
    if (!window.confirm("Deseja realmente excluir esta janela?")) return;
    try {
      await fetch(`${API_URL}/ise/janelas/${id}`, {
        method: 'DELETE'
      });
      carregarJanelas();
    } catch (err) {
      alert('Erro ao excluir janela.');
    }
  };

  const iniciarPolling = (janela_id) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/ise/resultado/${janela_id}`);
        const data = await res.json();
        if (data.status === 'CONCLUIDO' || data.status === 'ERRO') {
          clearInterval(interval);
          setLoading(false);
          if (data.status === 'ERRO') {
            setError(data.mensagem || 'Erro na simulação em background.');
            setSimulacaoAtual(null);
          } else {
            setSimulacaoAtual(data);
          }
        }
      } catch (err) {
        // ignore errors during poll
      }
    }, 3000);
  };

  const handleSimular = async (janela) => {
    if (janela.resultado && janela.resultado.status === 'CONCLUIDO') {
      setSimulacaoAtual(janela.resultado);
      return;
    }
    
    setLoading(true);
    setError(null);
    setSimulacaoAtual(null);
    try {
      const res = await fetch(`${API_URL}/ise/simular`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(janela),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Erro ao simular');
      
      if (data.status === 'PROCESSANDO') {
        iniciarPolling(data.janela_id);
      }
    } catch (err) {
      setError(err.message || 'Erro ao simular');
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px', fontFamily: '"Inter", system-ui, sans-serif', color: '#f8fafc', animation: 'fadeIn 0.5s ease-out' }}>
      <style>
        {`
          @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
          .ise-glass-panel {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            padding: 24px;
            transition: all 0.3s ease;
          }
          .ise-glass-panel:hover {
            box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.15);
          }
          .ise-input {
            width: 100%;
            padding: 10px 14px;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            color: #f1f5f9;
            font-size: 14px;
            transition: border-color 0.2s, box-shadow 0.2s;
            box-sizing: border-box;
          }
          .ise-input:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
          }
          .ise-btn {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            color: white;
            padding: 12px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
            transition: transform 0.1s, box-shadow 0.2s;
          }
          .ise-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(37, 99, 235, 0.4);
          }
          .ise-btn:active {
            transform: translateY(1px);
          }
          .ise-btn-simular {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
          }
          .ise-btn-simular:hover {
            box-shadow: 0 4px 10px rgba(16, 185, 129, 0.3);
            transform: scale(1.02);
          }
          .ise-table th { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); color: #94a3b8; font-weight: 500; }
          .ise-table td { padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.05); }
          .ise-metric-box {
            background: rgba(15, 23, 42, 0.5);
            padding: 16px;
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 10px;
            transition: transform 0.2s;
          }
          .ise-metric-box:hover { transform: translateY(-2px); }
        `}
      </style>

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
        <div style={{ background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)', padding: '12px', borderRadius: '12px', boxShadow: '0 4px 15px rgba(59, 130, 246, 0.4)' }}>
          <span style={{ fontSize: '24px' }}>⚡</span>
        </div>
        <div>
          <h2 style={{ margin: 0, fontSize: '24px', fontWeight: '700', background: 'linear-gradient(to right, #ffffff, #94a3b8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Simulador ISE
          </h2>
          <p style={{ margin: '4px 0 0 0', color: '#94a3b8', fontSize: '14px' }}>Projeção financeira avançada com Efeito Gangorra do Dia Crítico</p>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Painel Esquerdo */}
        <div className="ise-glass-panel" style={{ flex: '1', minWidth: '350px' }}>
          <h3 style={{ margin: '0 0 20px 0', fontSize: '18px', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#3b82f6' }}>1.</span> Gestão de Janelas
          </h3>
          
          <form onSubmit={handleSalvarJanela} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', gap: '16px' }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>ANOMES</label>
                <input type="text" className="ise-input" name="anomes" value={formData.anomes} onChange={handleChange} />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>Regional</label>
                <select className="ise-input" name="regional" value={formData.regional} onChange={handleChange}>
                  <option value="TODAS">TODAS</option>
                  <option value="LESTE">LESTE</option>
                  <option value="OESTE">OESTE</option>
                  <option value="NORTE">NORTE</option>
                  <option value="SUL">SUL</option>
                  <option value="CENTRO">CENTRO</option>
                </select>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '16px' }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>Início da Janela</label>
                <input type="datetime-local" step="1" className="ise-input" name="data_inicio" value={formData.data_inicio} onChange={handleChange} required />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>Fim da Janela</label>
                <input type="datetime-local" step="1" className="ise-input" name="data_fim" value={formData.data_fim} onChange={handleChange} required />
              </div>
            </div>
            <button type="submit" className="ise-btn" style={{ marginTop: '8px' }}>
              + Adicionar Nova Janela
            </button>
          </form>

          <div style={{ marginTop: '32px' }}>
            <h4 style={{ margin: '0 0 16px 0', color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>Janelas Salvas</h4>
            <div style={{ overflowX: 'auto' }}>
              <table className="ise-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr>
                    <th>Reg.</th>
                    <th>Início</th>
                    <th>Fim</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {janelas.map((j, idx) => (
                    <tr key={idx} style={{ transition: 'background 0.2s' }}>
                      <td><span style={{ background: 'rgba(59,130,246,0.2)', color: '#60a5fa', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold' }}>{j.regional}</span></td>
                      <td style={{ color: '#cbd5e1' }}>{j.data_inicio}</td>
                      <td style={{ color: '#cbd5e1' }}>{j.data_fim}</td>
                      <td>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: j.status === 'Autorizada' ? '#34d399' : '#fbbf24', fontSize: '12px' }}>
                          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: j.status === 'Autorizada' ? '#34d399' : '#fbbf24' }}></span>
                          {j.status}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right', display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                        <button 
                          className="ise-btn-simular" 
                          onClick={() => handleSimular(j)}
                          style={{ background: j.resultado && j.resultado.status === 'CONCLUIDO' ? 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)' : '' }}
                        >
                          {j.resultado && j.resultado.status === 'CONCLUIDO' ? 'Ver Resultado' : 'Simular'}
                        </button>
                        <button 
                          onClick={() => handleExcluirJanela(j.id)}
                          style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.5)', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontWeight: '500', transition: 'all 0.2s' }}
                          onMouseOver={(e) => { e.currentTarget.style.background = '#ef4444'; e.currentTarget.style.color = '#fff'; }}
                          onMouseOut={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)'; e.currentTarget.style.color = '#ef4444'; }}
                        >
                          Excluir
                        </button>
                      </td>
                    </tr>
                  ))}
                  {janelas.length === 0 && (
                    <tr><td colSpan="5" style={{ textAlign: 'center', padding: '24px', color: '#64748b' }}>Nenhuma janela salva no banco de controle.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Painel Direito */}
        <div className="ise-glass-panel" style={{ flex: '1.2', minWidth: '400px', display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ margin: '0 0 20px 0', fontSize: '18px', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#10b981' }}>2.</span> Motor de Resultados
          </h3>
          
          {loading && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
              <div style={{ width: '40px', height: '40px', border: '3px solid rgba(59,130,246,0.3)', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: '16px' }} />
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
              <p>Processando regras financeiras em background...</p>
            </div>
          )}

          {error && (
            <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', padding: '16px', borderRadius: '8px', color: '#fca5a5', display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '24px' }}>⚠️</span>
              <div>
                <strong style={{ display: 'block' }}>Falha no processamento</strong>
                <span style={{ fontSize: '13px', opacity: 0.8 }}>{error}</span>
              </div>
            </div>
          )}
          
          {!loading && !error && !simulacaoAtual && (
             <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#64748b', textAlign: 'center', padding: '40px' }}>
               <span style={{ fontSize: '48px', opacity: 0.5, marginBottom: '16px' }}>📊</span>
               <p style={{ margin: 0, fontSize: '16px' }}>Aguardando comando de simulação.</p>
               <p style={{ fontSize: '13px', marginTop: '8px' }}>Selecione uma janela ao lado e clique em "Simular" para rodar o motor regulatório.</p>
             </div>
          )}

          {!loading && !error && simulacaoAtual && (
            <div style={{ animation: 'fadeIn 0.4s ease-out' }}>
              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ margin: '0 0 12px 0', color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>Impacto Bruto na Janela (CHI)</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div className="ise-metric-box">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>Bruto Referência</span>
                      <span style={{ color: '#64748b' }}>🕒</span>
                    </div>
                    <div style={{ fontSize: '28px', fontWeight: 'bold', margin: '8px 0 0 0', color: '#f8fafc' }}>
                      {(simulacaoAtual.resultados_ise.ISE_CHI_BRUTO_REFERENCIA || 0).toLocaleString(undefined, {maximumFractionDigits:1})} <span style={{ fontSize: '14px', color: '#64748b' }}>h</span>
                    </div>
                  </div>
                  <div className="ise-metric-box" style={{ background: 'rgba(59, 130, 246, 0.1)', borderColor: 'rgba(59, 130, 246, 0.3)' }}>
                     <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '11px', color: '#60a5fa', textTransform: 'uppercase', fontWeight: 'bold' }}>Líquido Reclassificável</span>
                      <span style={{ color: '#60a5fa' }}>⚡</span>
                    </div>
                    <div style={{ fontSize: '28px', fontWeight: 'bold', margin: '8px 0 0 0', color: '#60a5fa' }}>
                      {(simulacaoAtual.resultados_ise.ISE_CHI_LIQUIDO_RECLASSIFICAVEL || 0).toLocaleString(undefined, {maximumFractionDigits:1})} <span style={{ fontSize: '14px', opacity: 0.7 }}>h</span>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '12px' }}>
                  <h4 style={{ margin: 0, color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>Simulação Financeira (DISE)</h4>
                  {simulacaoAtual.simulacao_financeira.UCS_QUE_PERDERAM_ISENCAO_DC > 0 && (
                    <span style={{ background: 'rgba(239,68,68,0.2)', color: '#fca5a5', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold' }}>
                      ⚠️ {simulacaoAtual.simulacao_financeira.UCS_QUE_PERDERAM_ISENCAO_DC} UCs perderam Dia Crítico
                    </span>
                  )}
                </div>
                
                <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                  <table className="ise-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                    <thead>
                      <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
                        <th style={{ color: '#cbd5e1' }}>Indicador</th>
                        <th style={{ textAlign: 'right', color: '#cbd5e1' }}>Sem ISE (Atual)</th>
                        <th style={{ textAlign: 'right', color: '#34d399' }}>Com ISE (Projeção)</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td style={{ color: '#94a3b8' }}>CHI (horas)</td>
                        <td style={{ textAlign: 'right', color: '#f8fafc' }}>{simulacaoAtual.simulacao_financeira.CHI_ORIGINAL.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ textAlign: 'right', color: '#34d399', fontWeight: 'bold' }}>{simulacaoAtual.simulacao_financeira.CHI_COM_ISE.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr>
                        <td style={{ color: '#94a3b8' }}>CI (qtd)</td>
                        <td style={{ textAlign: 'right', color: '#f8fafc' }}>{simulacaoAtual.simulacao_financeira.CI_ORIGINAL.toLocaleString(undefined, {minimumFractionDigits:0, maximumFractionDigits:0})}</td>
                        <td style={{ textAlign: 'right', color: '#34d399', fontWeight: 'bold' }}>{simulacaoAtual.simulacao_financeira.CI_COM_ISE.toLocaleString(undefined, {minimumFractionDigits:0, maximumFractionDigits:0})}</td>
                      </tr>
                      <tr>
                        <td style={{ color: '#94a3b8' }}>Risco DIC</td>
                        <td style={{ textAlign: 'right', color: '#f8fafc' }}>R$ {simulacaoAtual.simulacao_financeira.DIC_ORIGINAL_RS.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ textAlign: 'right', color: '#34d399', fontWeight: 'bold' }}>R$ {simulacaoAtual.simulacao_financeira.DIC_COM_ISE_RS.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr>
                        <td style={{ color: '#94a3b8' }}>Risco FIC</td>
                        <td style={{ textAlign: 'right', color: '#f8fafc' }}>R$ {simulacaoAtual.simulacao_financeira.FIC_ORIGINAL_RS.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ textAlign: 'right', color: '#34d399', fontWeight: 'bold' }}>R$ {simulacaoAtual.simulacao_financeira.FIC_COM_ISE_RS.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr>
                        <td style={{ color: '#94a3b8' }}>Risco DMIC</td>
                        <td style={{ textAlign: 'right', color: '#f8fafc' }}>R$ {simulacaoAtual.simulacao_financeira.DMIC_ORIGINAL_RS.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ textAlign: 'right', color: '#34d399', fontWeight: 'bold' }}>R$ {simulacaoAtual.simulacao_financeira.DMIC_COM_ISE_RS.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr>
                        <td style={{ color: '#94a3b8' }}>Risco DICRI</td>
                        <td style={{ textAlign: 'right', color: '#f8fafc' }}>R$ {simulacaoAtual.simulacao_financeira.DICRI_ORIGINAL_RS.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ textAlign: 'right', color: '#34d399', fontWeight: 'bold' }}>R$ {simulacaoAtual.simulacao_financeira.DICRI_COM_ISE_RS.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr>
                        <td style={{ color: '#94a3b8' }}>Risco DISE</td>
                        <td style={{ textAlign: 'right', color: '#f8fafc' }}>R$ {simulacaoAtual.simulacao_financeira.DISE_ORIGINAL_RS.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ textAlign: 'right', color: '#34d399', fontWeight: 'bold' }}>R$ {simulacaoAtual.simulacao_financeira.DISE_COM_ISE_RS.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr style={{ background: 'linear-gradient(90deg, rgba(16,185,129,0) 0%, rgba(16,185,129,0.1) 100%)' }}>
                        <td style={{ padding: '16px 12px', color: '#10b981', fontWeight: 'bold', border: 'none' }}>ECONOMIA LÍQUIDA</td>
                        <td colSpan="2" style={{ padding: '16px 12px', textAlign: 'right', color: '#10b981', fontWeight: '900', fontSize: '20px', border: 'none', textShadow: '0 2px 10px rgba(16,185,129,0.3)' }}>
                          + R$ {simulacaoAtual.simulacao_financeira.DISE_GANHO_RS.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {simulacaoAtual.serie_temporal && simulacaoAtual.serie_temporal.length > 0 && (
                <div style={{ marginTop: '24px' }}>
                  <h4 style={{ margin: '0 0 12px 0', color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                    Curva de Recomposição de CI
                  </h4>
                  <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', padding: '16px' }}>
                    <div id="g_ci" style={{ height: '400px', width: '100%' }}></div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
