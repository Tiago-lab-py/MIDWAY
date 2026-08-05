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
  const [selectedWindows, setSelectedWindows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editId, setEditId] = useState(null);

  const [sortConfigDetalhe, setSortConfigDetalhe] = useState({ key: null, direction: 'asc' });
  const [filterTextDetalhe, setFilterTextDetalhe] = useState('');
  
  const [sortConfigImpacto, setSortConfigImpacto] = useState({ key: null, direction: 'asc' });
  const [filterTextImpacto, setFilterTextImpacto] = useState('');

  const handleSort = (key, currentConfig, setConfig) => {
    let direction = 'asc';
    if (currentConfig.key === key && currentConfig.direction === 'asc') {
      direction = 'desc';
    }
    setConfig({ key, direction });
  };

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

      // 1. Gráfico de CI (Recomposição)
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
      
      // 2. Gráfico de CHI (Impacto Temporal)
      const all_regions = new Set();
      serie.forEach(s => Object.keys(s.regionais || {}).forEach(r => all_regions.add(r)));
      const regions_arr = Array.from(all_regions).sort();
      
      const colors = { 'LES': '#3b82f6', 'OES': '#10b981', 'CSL': '#ef4444', 'MGA': '#f59e0b', 'NRT': '#8b5cf6', 'N/I': '#64748b' };
      const palette = ['#3b82f6', '#10b981', '#ef4444', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16'];
      
      const chiTraces = regions_arr.map((reg, i) => {
        return {
          type: 'bar',
          x: x,
          y: serie.map(s => (s.regionais || {})[reg] || 0),
          name: reg,
          marker: { color: colors[reg.toUpperCase()] || palette[i % palette.length] },
          opacity: 0.8
        };
      });
      
      chiTraces.push({
          type: 'scatter',
          x: x,
          y: serie.map(s => s.chi_acumulado || 0),
          name: 'CHI Acumulado',
          mode: 'lines+markers',
          yaxis: 'y2',
          line: { color: '#f8fafc', width: 3, dash: 'dot' },
          marker: { size: 6, color: '#f8fafc' }
      });
      
      window.Plotly.newPlot('g_chi', chiTraces, {
        template: 'plotly_dark',
        barmode: 'stack',
        hovermode: 'x unified',
        margin: {t: 30, r: 60, b: 50, l: 60},
        xaxis: { title: 'Hora', tickformat: '%d/%m %H:%M', gridcolor: 'rgba(255,255,255,0.05)', color: '#94a3b8' },
        yaxis: { title: 'CHI (UC-h) - Hora', gridcolor: 'rgba(255,255,255,0.05)', color: '#94a3b8' },
        yaxis2: { title: 'CHI Acumulado', overlaying: 'y', side: 'right', gridcolor: 'rgba(255,255,255,0.05)', color: '#94a3b8' },
        legend: {orientation: 'h', y: 1.08, x: 0, font: {color: '#cbd5e1'}},
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)'
      }, {
        displaylogo: false, responsive: true, displayModeBar: false
      });
      
    }
  }, [simulacaoAtual]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => {
      const next = { ...prev, [name]: value };
      if ((name === 'data_inicio' || name === 'data_fim') && !prev.descritivo) {
        next.descritivo = `${next.data_inicio} até ${next.data_fim}`.trim();
      }
      return next;
    });
  };

  const handleSalvarJanela = async (e) => {
    e.preventDefault();
    try {
      if (isEditing) {
        await fetch(`${API_URL}/ise/janelas/${editId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData),
        });
        setIsEditing(false);
        setEditId(null);
        alert('Janela atualizada com sucesso!');
      } else {
        await fetch(`${API_URL}/ise/janelas`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData),
        });
        alert('Janela salva com sucesso!');
      }
      setFormData({ regional: 'LESTE', data_inicio: '', data_fim: '', anomes: '202607', id_evento: '', descritivo: '' });
      carregarJanelas();
    } catch (err) {
      alert('Erro ao salvar janela.');
    }
  };

  const handleEditarJanela = (janela) => {
    if (janela.status === 'Implantada') {
      if (!window.confirm("Esta janela já está Implantada. Se você editá-la, ela voltará para o status de Simulação e precisará ser re-implantada. Deseja continuar?")) {
        return;
      }
    }
    setIsEditing(true);
    setEditId(janela.id);
    setFormData({
      regional: janela.regional,
      data_inicio: janela.data_inicio,
      data_fim: janela.data_fim,
      anomes: janela.anomes || '202607',
      id_evento: janela.id_evento || '',
      descritivo: janela.descritivo || ''
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
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

  const toggleSelection = (id) => {
    setSelectedWindows(prev => 
      prev.includes(id) ? prev.filter(wId => wId !== id) : [...prev, id]
    );
  };
  
  const handleImplantarLote = async (tipo = 'completo') => {
    if (selectedWindows.length === 0) return alert("Selecione ao menos uma janela!");
    const label = tipo === 'otimizado' ? 'OTIMIZADO' : 'COMPLETO';
    if (!window.confirm(`Tem certeza que deseja IMPLANTAR o cenário ${label} nas ${selectedWindows.length} janelas selecionadas? Elas ficarão travadas para auditoria.`)) return;
    
    try {
      await fetch(`${API_URL}/ise/implantar_lote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedWindows, tipo }),
      });
      setSelectedWindows([]);
      carregarJanelas();
      alert('Janelas implantadas com sucesso! Vá para a página de "Saída IQS" para gerar o pacote de envio do mês.');
    } catch (err) {
      alert("Erro ao implantar janelas.");
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
          carregarJanelas();
        }
      } catch (err) {
        // ignore errors during poll
      }
    }, 3000);
  };

  const handleSimular = async (janela, force = false) => {
    if (!force && janela.resultado && janela.resultado.status === 'CONCLUIDO') {
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

  let sortedTabelaDetalhe = simulacaoAtual?.tabela_detalhe_conjuntos ? [...simulacaoAtual.tabela_detalhe_conjuntos] : [];
  if (filterTextDetalhe) {
    const text = filterTextDetalhe.toLowerCase();
    sortedTabelaDetalhe = sortedTabelaDetalhe.filter(r => (r.conjunto && String(r.conjunto).toLowerCase().includes(text)) || (r.cod_conjunto && String(r.cod_conjunto).toLowerCase().includes(text)));
  }
  if (sortConfigDetalhe.key) {
    sortedTabelaDetalhe.sort((a, b) => {
      let aVal = a[sortConfigDetalhe.key] ?? '';
      let bVal = b[sortConfigDetalhe.key] ?? '';
      if (typeof aVal === 'string') aVal = aVal.toLowerCase();
      if (typeof bVal === 'string') bVal = bVal.toLowerCase();
      if (aVal < bVal) return sortConfigDetalhe.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfigDetalhe.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }

  let sortedTabelaImpacto = simulacaoAtual?.tabela_conjuntos ? [...simulacaoAtual.tabela_conjuntos] : [];
  // Para Impacto, aplica primeiro o filtro padrão (apenas alterados)
  sortedTabelaImpacto = sortedTabelaImpacto.filter(r => r.ci_antes !== r.ci_depois || r.chi_antes !== r.chi_depois);
  if (filterTextImpacto) {
    const text = filterTextImpacto.toLowerCase();
    sortedTabelaImpacto = sortedTabelaImpacto.filter(r => (r.conjunto && String(r.conjunto).toLowerCase().includes(text)));
  }
  if (sortConfigImpacto.key) {
    sortedTabelaImpacto.sort((a, b) => {
      let aVal = a[sortConfigImpacto.key] ?? '';
      let bVal = b[sortConfigImpacto.key] ?? '';
      if (typeof aVal === 'string') aVal = aVal.toLowerCase();
      if (typeof bVal === 'string') bVal = bVal.toLowerCase();
      if (aVal < bVal) return sortConfigImpacto.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfigImpacto.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }

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
            <span style={{ color: '#3b82f6' }}>1.</span> {isEditing ? 'Editar Janela' : 'Gestão de Janelas'}
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
              <div style={{ flex: 1, maxWidth: '120px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>ID Evento</label>
                <input type="number" className="ise-input" name="id_evento" value={formData.id_evento} onChange={handleChange} placeholder="Opcional" />
              </div>
              <div style={{ flex: 3 }}>
                <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>Descritivo do Evento</label>
                <input type="text" className="ise-input" name="descritivo" value={formData.descritivo} onChange={handleChange} placeholder="Ex: Ciclone Bomba" />
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
              {isEditing ? 'Atualizar Janela' : '+ Adicionar Nova Janela'}
            </button>
          </form>

          <div style={{ marginTop: '32px' }}>
            <h4 style={{ margin: '0 0 16px 0', color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>Janelas Salvas</h4>
            <div style={{ overflowX: 'auto' }}>
              <table className="ise-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr>
                    <th style={{ width: '40px', textAlign: 'center' }}>
                      <input type="checkbox" onChange={(e) => { if(e.target.checked) setSelectedWindows(janelas.map(j=>j.id)); else setSelectedWindows([]); }} checked={janelas.length>0 && selectedWindows.length === janelas.length} />
                    </th>
                    <th>ID</th>
                    <th>Reg.</th>
                    <th>Descritivo</th>
                    <th>Início</th>
                    <th>Fim</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {janelas.map((j, idx) => (
                    <tr key={idx} style={{ transition: 'background 0.2s', background: selectedWindows.includes(j.id) ? 'rgba(59, 130, 246, 0.1)' : 'transparent' }}>
                      <td style={{ textAlign: 'center' }}>
                        <input type="checkbox" checked={selectedWindows.includes(j.id)} onChange={() => toggleSelection(j.id)} />
                      </td>
                      <td style={{ color: '#94a3b8', fontWeight: 'bold' }}>{j.id_evento || '-'}</td>
                      <td><span style={{ background: 'rgba(59,130,246,0.2)', color: '#60a5fa', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold' }}>{j.regional}</span></td>
                      <td style={{ color: '#cbd5e1' }}>{j.descritivo || '-'}</td>
                      <td style={{ color: '#cbd5e1' }}>{j.data_inicio ? j.data_inicio.replace('T', ' ') : ''}</td>
                      <td style={{ color: '#cbd5e1' }}>{j.data_fim ? j.data_fim.replace('T', ' ') : ''}</td>
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
                        {j.resultado && j.resultado.status === 'CONCLUIDO' && (
                          <button 
                            onClick={(e) => { e.stopPropagation(); handleSimular(j, true); }}
                            title="Reprocessar Simulação"
                            style={{ background: 'rgba(59, 130, 246, 0.1)', color: '#60a5fa', border: '1px solid rgba(59, 130, 246, 0.5)', padding: '6px', borderRadius: '6px', cursor: 'pointer', fontWeight: '500', transition: 'all 0.2s', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                            onMouseOver={(e) => { e.currentTarget.style.background = '#3b82f6'; e.currentTarget.style.color = '#fff'; }}
                            onMouseOut={(e) => { e.currentTarget.style.background = 'rgba(59, 130, 246, 0.1)'; e.currentTarget.style.color = '#60a5fa'; }}
                          >
                            ⟳
                          </button>
                        )}
                        <button 
                          onClick={() => handleEditarJanela(j)}
                          style={{ background: 'rgba(245, 158, 11, 0.1)', color: '#fbbf24', border: '1px solid rgba(245, 158, 11, 0.5)', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontWeight: '500', transition: 'all 0.2s' }}
                          onMouseOver={(e) => { e.currentTarget.style.background = '#fbbf24'; e.currentTarget.style.color = '#fff'; }}
                          onMouseOut={(e) => { e.currentTarget.style.background = 'rgba(245, 158, 11, 0.1)'; e.currentTarget.style.color = '#fbbf24'; }}
                        >
                          Editar
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
                    <tr><td colSpan="6" style={{ textAlign: 'center', padding: '24px', color: '#64748b' }}>Nenhuma janela salva no banco de controle.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            {selectedWindows.length > 0 && (
              <div style={{ marginTop: '16px', display: 'flex', gap: '12px', padding: '16px', background: 'rgba(15, 23, 42, 0.6)', borderRadius: '8px', border: '1px solid rgba(59,130,246,0.3)', alignItems: 'center', animation: 'fadeIn 0.3s ease-out' }}>
                <span style={{ fontSize: '13px', color: '#cbd5e1', flex: 1 }}><strong>{selectedWindows.length}</strong> janela(s) selecionada(s)</span>
                
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button onClick={() => handleImplantarLote('completo')} style={{ background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', border: '1px solid rgba(59, 130, 246, 0.5)', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold', transition: 'all 0.2s' }}>
                    📦 Implantar Completo
                  </button>
                  <button onClick={() => handleImplantarLote('otimizado')} style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.5)', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold', transition: 'all 0.2s' }}>
                    ✅ Implantar Otimizado
                  </button>
                </div>
              </div>
            )}
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
                <h4 style={{ margin: '0 0 12px 0', color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>Impacto Geral do Evento</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div className="ise-metric-box">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>CI Total</span>
                      <span style={{ color: '#64748b' }}>👥</span>
                    </div>
                    <div style={{ fontSize: '28px', fontWeight: 'bold', margin: '8px 0 0 0', color: '#f8fafc' }}>
                      {(simulacaoAtual.ci_total || 0).toLocaleString()} <span style={{ fontSize: '14px', color: '#64748b' }}>UCs</span>
                    </div>
                  </div>
                  <div className="ise-metric-box">
                     <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>CHI Total</span>
                      <span style={{ color: '#64748b' }}>🕒</span>
                    </div>
                    <div style={{ fontSize: '28px', fontWeight: 'bold', margin: '8px 0 0 0', color: '#f8fafc' }}>
                      {(simulacaoAtual.chi_total || 0).toLocaleString(undefined, {maximumFractionDigits:1})} <span style={{ fontSize: '14px', color: '#64748b' }}>h</span>
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ margin: '0 0 12px 0', color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>Reclassificações ISE</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div className="ise-metric-box" style={{ background: 'rgba(16, 185, 129, 0.1)', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '11px', color: '#10b981', textTransform: 'uppercase', fontWeight: 'bold' }}>Isentado (TIPO 6)</span>
                      <span style={{ color: '#10b981' }}>✅</span>
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', margin: '8px 0 4px 0', color: '#10b981' }}>
                      {(simulacaoAtual.chi_tipo6 || 0).toLocaleString(undefined, {maximumFractionDigits:1})} <span style={{ fontSize: '12px', opacity: 0.7 }}>horas (CHI)</span>
                    </div>
                    <div style={{ fontSize: '14px', color: '#10b981', opacity: 0.8 }}>
                      {(simulacaoAtual.ci_tipo6 || 0).toLocaleString()} UCs
                    </div>
                  </div>
                  <div className="ise-metric-box" style={{ background: 'rgba(239, 68, 68, 0.1)', borderColor: 'rgba(239, 68, 68, 0.3)' }}>
                     <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '11px', color: '#ef4444', textTransform: 'uppercase', fontWeight: 'bold' }}>Gangorra (TIPO 0)</span>
                      <span style={{ color: '#ef4444' }}>⚠️</span>
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', margin: '8px 0 4px 0', color: '#ef4444' }}>
                      {(simulacaoAtual.chi_tipo0 || 0).toLocaleString(undefined, {maximumFractionDigits:1})} <span style={{ fontSize: '12px', opacity: 0.7 }}>horas (CHI)</span>
                    </div>
                    <div style={{ fontSize: '14px', color: '#ef4444', opacity: 0.8 }}>
                      {(simulacaoAtual.ci_tipo0 || 0).toLocaleString()} UCs
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '12px' }}>
                  <h4 style={{ margin: 0, color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>Simulação Financeira (DISE)</h4>
                  {simulacaoAtual.conjuntos_rebaixados > 0 && (
                    <span style={{ background: 'rgba(239,68,68,0.2)', color: '#fca5a5', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold' }}>
                      ⚠️ {simulacaoAtual.conjuntos_rebaixados} Conjunto(s) perderam Dia Crítico
                    </span>
                  )}
                  <button onClick={() => window.open(`${API_URL}/ise/janelas/${simulacaoAtual.janela?.id}/relatorio`, '_blank')} style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '4px 12px', borderRadius: '4px', fontSize: '12px', cursor: 'pointer', fontWeight: 'bold', marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    📈 Baixar Relatório HTML
                  </button>
                </div>
                
         {simulacaoAtual?.simulacao_financeira && (
        <div style={{ marginTop: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '15px' }}>
            <h4 style={{ margin: 0, color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>
              Simulação Financeira (DISE)
            </h4>
            {simulacaoAtual.conjuntos_rebaixados?.length > 0 && (
              <span style={{ background: '#451a03', color: '#fca5a5', padding: '4px 10px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold' }}>
                ⚠️ {simulacaoAtual.conjuntos_rebaixados.length} Conjunto(s) perderam Dia Crítico
              </span>
            )}
          </div>
          
          {(() => {
            const sf = simulacaoAtual.simulacao_financeira;
            const getColor = (comIse, orig) => {
              if (comIse > orig) return '#ef4444'; // Red (Piorou)
              if (comIse < orig) return '#10b981'; // Green (Melhorou)
              return '#eab308'; // Amarelo (Igual)
            };
            const ecoColor = sf.DISE_GANHO_RS < 0 ? '#ef4444' : '#10b981';
            
            return (
              <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                    <thead>
                      <tr style={{ background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <th style={{ padding: '16px 12px', textAlign: 'left', color: '#f8fafc', fontWeight: '600' }}>INDICADOR</th>
                        <th style={{ padding: '16px 12px', textAlign: 'right', color: '#f8fafc', fontWeight: '600' }}>SEM ISE (ATUAL)</th>
                        <th style={{ padding: '16px 12px', textAlign: 'right', color: '#60a5fa', fontWeight: '600' }}>COM ISE (PROJEÇÃO)</th>
                        <th style={{ padding: '16px 12px', textAlign: 'right', color: '#10b981', fontWeight: '600' }}>ISE OTIMIZADO</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '12px', color: '#94a3b8' }}>Duração (CHI) - <strong style={{color:'#cbd5e1'}}>Bruto</strong></td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#f8fafc' }}>{(sf.CHI_BRUTO_ORIGINAL || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#60a5fa', fontWeight: 'bold' }}>{(sf.CHI_BRUTO_COM_ISE || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#10b981', fontWeight: 'bold' }}>{(sf.CHI_BRUTO_ORIGINAL || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '12px', color: '#94a3b8' }}>Risco DIC</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#f8fafc' }}>R$ {(sf.DIC_ORIGINAL_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#60a5fa', fontWeight: 'bold' }}>R$ {(sf.DIC_COM_ISE_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: getColor(sf.DIC_OTIMIZADO_RS, sf.DIC_ORIGINAL_RS), fontWeight: 'bold' }}>R$ {(sf.DIC_OTIMIZADO_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '12px', color: '#94a3b8' }}>Risco FIC</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#f8fafc' }}>R$ {(sf.FIC_ORIGINAL_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#60a5fa', fontWeight: 'bold' }}>R$ {(sf.FIC_COM_ISE_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: getColor(sf.FIC_OTIMIZADO_RS, sf.FIC_ORIGINAL_RS), fontWeight: 'bold' }}>R$ {(sf.FIC_OTIMIZADO_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '12px', color: '#94a3b8' }}>Risco DMIC</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#f8fafc' }}>R$ {(sf.DMIC_ORIGINAL_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#60a5fa', fontWeight: 'bold' }}>R$ {(sf.DMIC_COM_ISE_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: getColor(sf.DMIC_OTIMIZADO_RS, sf.DMIC_ORIGINAL_RS), fontWeight: 'bold' }}>R$ {(sf.DMIC_OTIMIZADO_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr style={{ borderBottom: '2px solid rgba(255,255,255,0.1)', background: 'rgba(59, 130, 246, 0.05)' }}>
                        <td style={{ padding: '12px', color: '#60a5fa', fontWeight: 'bold' }}>Compensação Geral (Maior entre DIC/FIC/DMIC)</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#f8fafc', fontWeight: 'bold' }}>R$ {(sf.COMP_GERAL_ORIGINAL_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#60a5fa', fontWeight: 'bold' }}>R$ {(sf.COMP_GERAL_COM_ISE_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: getColor(sf.COMP_GERAL_OTIMIZADO_RS, sf.COMP_GERAL_ORIGINAL_RS), fontWeight: 'bold' }}>R$ {(sf.COMP_GERAL_OTIMIZADO_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '12px', color: '#94a3b8' }}>Risco DICRI</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#f8fafc' }}>R$ {(sf.DICRI_ORIGINAL_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#60a5fa', fontWeight: 'bold' }}>R$ {(sf.DICRI_COM_ISE_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: getColor(sf.DICRI_OTIMIZADO_RS, sf.DICRI_ORIGINAL_RS), fontWeight: 'bold' }}>R$ {(sf.DICRI_OTIMIZADO_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '12px', color: '#94a3b8' }}>Risco DISE</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#f8fafc' }}>R$ {(sf.DISE_ORIGINAL_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#60a5fa', fontWeight: 'bold' }}>R$ {(sf.DISE_COM_ISE_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: getColor(sf.DISE_OTIMIZADO_RS, sf.DISE_ORIGINAL_RS), fontWeight: 'bold' }}>R$ {(sf.DISE_OTIMIZADO_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr style={{ borderBottom: '2px solid rgba(255,255,255,0.1)', background: 'rgba(16, 185, 129, 0.05)' }}>
                        <td style={{ padding: '12px', color: '#34d399', fontWeight: 'bold' }}>Compensação Total (Geral + DICRI + DISE)</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#f8fafc', fontWeight: 'bold' }}>R$ {(sf.COMP_TOTAL_ORIGINAL_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: '#60a5fa', fontWeight: 'bold' }}>R$ {(sf.COMP_TOTAL_COM_ISE_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style={{ padding: '12px', textAlign: 'right', color: getColor(sf.COMP_TOTAL_OTIMIZADO_RS, sf.COMP_TOTAL_ORIGINAL_RS), fontWeight: 'bold' }}>R$ {(sf.COMP_TOTAL_OTIMIZADO_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                      </tr>
                      <tr style={{ background: ecoColor === '#ef4444' ? 'linear-gradient(90deg, rgba(239,68,68,0) 0%, rgba(239,68,68,0.1) 100%)' : 'linear-gradient(90deg, rgba(16,185,129,0) 0%, rgba(16,185,129,0.1) 100%)' }}>
                        <td style={{ padding: '16px 12px', color: ecoColor, fontWeight: 'bold', border: 'none' }}>ECONOMIA LÍQUIDA</td>
                        <td style={{ padding: '16px 12px', border: 'none' }}></td>
                        <td style={{ padding: '16px 12px', textAlign: 'right', color: (sf.DISE_GANHO_RS < 0 ? '#ef4444' : '#60a5fa'), fontWeight: '900', fontSize: '16px', border: 'none' }}>
                           {sf.DISE_GANHO_RS >= 0 ? '+' : '-'} R$ {Math.abs(sf.DISE_GANHO_RS).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                        </td>
                        <td style={{ padding: '16px 12px', textAlign: 'right', color: ecoColor, fontWeight: '900', fontSize: '20px', border: 'none', textShadow: `0 2px 10px ${ecoColor}40` }}>
                           {sf.DISE_GANHO_OTIMIZADO_RS >= 0 ? '+' : '-'} R$ {Math.abs(sf.DISE_GANHO_OTIMIZADO_RS || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })()}
        </div>
      )}
              </div>

              {simulacaoAtual.serie_temporal && simulacaoAtual.serie_temporal.length > 0 && (
                <div style={{ marginTop: '24px' }}>
                  <h4 style={{ margin: '0 0 12px 0', color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                    Curva de Impacto Temporal de CHI
                  </h4>
                  <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', padding: '16px', marginBottom: '24px' }}>
                    <div id="g_chi" style={{ height: '400px', width: '100%' }}></div>
                  </div>
                  
                  <h4 style={{ margin: '24px 0 12px 0', color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                    Curva de Recomposição de CI
                  </h4>
                  <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', padding: '16px' }}>
                    <div id="g_ci" style={{ height: '400px', width: '100%' }}></div>
                  </div>
                </div>
              )}

              {simulacaoAtual.tabela_detalhe_conjuntos && simulacaoAtual.tabela_detalhe_conjuntos.length > 0 && (
                <div style={{ marginTop: '32px' }}>
                  <h4 style={{ margin: '0 0 12px 0', color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                    Indicadores, Metas e Ressarcimentos por Conjunto
                  </h4>
                  <p style={{ margin: '0 0 16px 0', color: '#94a3b8', fontSize: '13px' }}>
                    Esta tabela detalha os impactos agregados por conjunto elétrico, suas metas anuais DEC/FEC e o impacto financeiro real do ressarcimento regulatório (maior valor entre DIC, FIC e DMIC + DICRI + DISE por UC).
                  </p>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px' }}>
                    <input 
                      type="text" 
                      placeholder="Filtrar por conjunto..." 
                      value={filterTextDetalhe} 
                      onChange={e => setFilterTextDetalhe(e.target.value)} 
                      style={{ padding: '8px 12px', borderRadius: '6px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(148, 163, 184, 0.2)', color: '#f1f5f9', fontSize: '13px', width: '250px' }}
                    />
                  </div>
                  <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                    <div style={{ overflowX: 'auto', maxHeight: '550px' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                        <thead style={{ position: 'sticky', top: 0, background: '#1e293b', zIndex: 2 }}>
                          <tr style={{ borderBottom: '2px solid rgba(255,255,255,0.1)' }}>
                            <th onClick={() => handleSort('conjunto', sortConfigDetalhe, setSortConfigDetalhe)} style={{ padding: '12px', textAlign: 'left', color: '#f8fafc', cursor: 'pointer' }} rowspan="2">Conjunto {sortConfigDetalhe.key === 'conjunto' ? (sortConfigDetalhe.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th style={{ padding: '12px', textAlign: 'center', color: '#f8fafc', borderBottom: '1px solid rgba(255,255,255,0.1)' }} colspan="3">CHI (h)</th>
                            <th style={{ padding: '12px', textAlign: 'center', color: '#f8fafc', borderBottom: '1px solid rgba(255,255,255,0.1)' }} colspan="3">CI (Qtd)</th>
                            <th style={{ padding: '12px', textAlign: 'center', color: '#f8fafc', borderBottom: '1px solid rgba(255,255,255,0.1)' }} colspan="2">Metas Anuais</th>
                            <th style={{ padding: '12px', textAlign: 'center', color: '#f8fafc', borderBottom: '1px solid rgba(255,255,255,0.1)' }} colspan="4">Ressarcimento Regulatório</th>
                          </tr>
                          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                            <th onClick={() => handleSort('chi_liquido', sortConfigDetalhe, setSortConfigDetalhe)} style={{ padding: '8px 12px', textAlign: 'right', color: '#cbd5e1', fontSize: '11px', cursor: 'pointer' }}>Líquido (T0) {sortConfigDetalhe.key === 'chi_liquido' ? (sortConfigDetalhe.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('chi_diacritico', sortConfigDetalhe, setSortConfigDetalhe)} style={{ padding: '8px 12px', textAlign: 'right', color: '#fbbf24', fontSize: '11px', cursor: 'pointer' }}>Dia Crítico (T1) {sortConfigDetalhe.key === 'chi_diacritico' ? (sortConfigDetalhe.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('chi_ise', sortConfigDetalhe, setSortConfigDetalhe)} style={{ padding: '8px 12px', textAlign: 'right', color: '#60a5fa', fontSize: '11px', cursor: 'pointer' }}>ISE (T6) {sortConfigDetalhe.key === 'chi_ise' ? (sortConfigDetalhe.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('ci_liquido', sortConfigDetalhe, setSortConfigDetalhe)} style={{ padding: '8px 12px', textAlign: 'right', color: '#cbd5e1', fontSize: '11px', cursor: 'pointer' }}>Líquido (T0) {sortConfigDetalhe.key === 'ci_liquido' ? (sortConfigDetalhe.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('ci_diacritico', sortConfigDetalhe, setSortConfigDetalhe)} style={{ padding: '8px 12px', textAlign: 'right', color: '#fbbf24', fontSize: '11px', cursor: 'pointer' }}>Dia Crítico (T1) {sortConfigDetalhe.key === 'ci_diacritico' ? (sortConfigDetalhe.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('ci_ise', sortConfigDetalhe, setSortConfigDetalhe)} style={{ padding: '8px 12px', textAlign: 'right', color: '#60a5fa', fontSize: '11px', cursor: 'pointer' }}>ISE (T6) {sortConfigDetalhe.key === 'ci_ise' ? (sortConfigDetalhe.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('meta_dec', sortConfigDetalhe, setSortConfigDetalhe)} style={{ padding: '8px 12px', textAlign: 'right', color: '#94a3b8', fontSize: '11px', cursor: 'pointer' }}>Meta DEC {sortConfigDetalhe.key === 'meta_dec' ? (sortConfigDetalhe.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('meta_fec', sortConfigDetalhe, setSortConfigDetalhe)} style={{ padding: '8px 12px', textAlign: 'right', color: '#94a3b8', fontSize: '11px', cursor: 'pointer' }}>Meta FEC {sortConfigDetalhe.key === 'meta_fec' ? (sortConfigDetalhe.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('comp_total_sem', sortConfigDetalhe, setSortConfigDetalhe)} style={{ padding: '8px 12px', textAlign: 'right', color: '#cbd5e1', fontSize: '11px', cursor: 'pointer' }}>Sem ISE (Atual) {sortConfigDetalhe.key === 'comp_total_sem' ? (sortConfigDetalhe.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('comp_total_com', sortConfigDetalhe, setSortConfigDetalhe)} style={{ padding: '8px 12px', textAlign: 'right', color: '#60a5fa', fontSize: '11px', cursor: 'pointer' }}>Com ISE (Simulado) {sortConfigDetalhe.key === 'comp_total_com' ? (sortConfigDetalhe.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('comp_total_otimizado', sortConfigDetalhe, setSortConfigDetalhe)} style={{ padding: '8px 12px', textAlign: 'right', color: '#a855f7', fontSize: '11px', cursor: 'pointer' }}>Otimizado (Simulado) {sortConfigDetalhe.key === 'comp_total_otimizado' ? (sortConfigDetalhe.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th style={{ padding: '8px 12px', textAlign: 'right', color: '#10b981', fontSize: '11px' }}>Economia Otimizada</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sortedTabelaDetalhe.map((r, i) => {
                            const economia = (r.comp_total_sem || 0) - (r.comp_total_otimizado || 0);
                            const ecoColor = economia > 0.01 ? '#10b981' : (economia < -0.01 ? '#ef4444' : '#94a3b8');
                            return (
                              <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent', transition: 'background 0.2s' }}>
                                <td style={{ padding: '10px 12px', color: '#e2e8f0', fontWeight: 'bold' }}>
                                  {r.conjunto} <span style={{ fontSize: '10px', color: '#64748b', fontWeight: 'normal' }}>({r.cod_conjunto})</span> {r.is_otimizado && <span style={{ color: '#10b981', marginLeft: '4px' }}>⭐</span>}
                                </td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#e2e8f0' }}>{r.chi_liquido.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#fbbf24', fontWeight: 'bold' }}>{r.chi_diacritico.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#60a5fa', fontWeight: 'bold' }}>{r.chi_ise.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#e2e8f0' }}>{r.ci_liquido.toLocaleString()}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#fbbf24', fontWeight: 'bold' }}>{r.ci_diacritico.toLocaleString()}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#60a5fa', fontWeight: 'bold' }}>{r.ci_ise.toLocaleString()}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#94a3b8', fontStyle: 'italic' }}>{r.meta_dec.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#94a3b8', fontStyle: 'italic' }}>{r.meta_fec.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#e2e8f0' }}>R$ {r.comp_total_sem.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#60a5fa', fontWeight: 'bold' }}>R$ {r.comp_total_com.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#a855f7', fontWeight: 'bold' }}>R$ {(r.comp_total_otimizado || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: ecoColor, fontWeight: 'bold' }}>
                                  {economia >= 0 ? '+' : '-'} R$ {Math.abs(economia).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
              
              {simulacaoAtual.tabela_conjuntos && simulacaoAtual.tabela_conjuntos.length > 0 && (
                <div style={{ marginTop: '32px' }}>
                  <h4 style={{ margin: '0 0 12px 0', color: '#cbd5e1', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                    Impacto por Conjunto (Apenas Alterados)
                  </h4>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px' }}>
                    <input 
                      type="text" 
                      placeholder="Filtrar por conjunto..." 
                      value={filterTextImpacto} 
                      onChange={e => setFilterTextImpacto(e.target.value)} 
                      style={{ padding: '8px 12px', borderRadius: '6px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(148, 163, 184, 0.2)', color: '#f1f5f9', fontSize: '13px', width: '250px' }}
                    />
                  </div>
                  <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                    <div style={{ overflowX: 'auto', maxHeight: '400px' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                        <thead style={{ position: 'sticky', top: 0, background: '#1e293b', zIndex: 1 }}>
                          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                            <th onClick={() => handleSort('conjunto', sortConfigImpacto, setSortConfigImpacto)} style={{ padding: '12px', textAlign: 'left', color: '#f8fafc', cursor: 'pointer' }}>Conjunto {sortConfigImpacto.key === 'conjunto' ? (sortConfigImpacto.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('protocolo', sortConfigImpacto, setSortConfigImpacto)} style={{ padding: '12px', textAlign: 'left', color: '#f8fafc', cursor: 'pointer' }}>Protocolo {sortConfigImpacto.key === 'protocolo' ? (sortConfigImpacto.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('ci_antes', sortConfigImpacto, setSortConfigImpacto)} style={{ padding: '12px', textAlign: 'right', color: '#f8fafc', cursor: 'pointer' }}>CI Antes {sortConfigImpacto.key === 'ci_antes' ? (sortConfigImpacto.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('ci_depois', sortConfigImpacto, setSortConfigImpacto)} style={{ padding: '12px', textAlign: 'right', color: '#f8fafc', cursor: 'pointer' }}>CI Depois {sortConfigImpacto.key === 'ci_depois' ? (sortConfigImpacto.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('chi_antes', sortConfigImpacto, setSortConfigImpacto)} style={{ padding: '12px', textAlign: 'right', color: '#f8fafc', cursor: 'pointer' }}>CHI Antes {sortConfigImpacto.key === 'chi_antes' ? (sortConfigImpacto.direction === 'asc' ? '↑' : '↓') : ''}</th>
                            <th onClick={() => handleSort('chi_depois', sortConfigImpacto, setSortConfigImpacto)} style={{ padding: '12px', textAlign: 'right', color: '#f8fafc', cursor: 'pointer' }}>CHI Depois {sortConfigImpacto.key === 'chi_depois' ? (sortConfigImpacto.direction === 'asc' ? '↑' : '↓') : ''}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sortedTabelaImpacto.map((r, i) => {
                            const ciCor = r.ci_depois < r.ci_antes ? '#10b981' : (r.ci_depois > r.ci_antes ? '#ef4444' : '#eab308');
                            const chiCor = r.chi_depois < r.chi_antes ? '#10b981' : (r.chi_depois > r.chi_antes ? '#ef4444' : '#eab308');
                            return (
                              <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent' }}>
                                <td style={{ padding: '10px 12px', color: '#e2e8f0', fontWeight: 'bold' }}>{r.conjunto}</td>
                                <td style={{ padding: '10px 12px', color: '#94a3b8' }}>{r.protocolo}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#cbd5e1' }}>{r.ci_antes.toLocaleString()}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: ciCor, fontWeight: 'bold' }}>{r.ci_depois.toLocaleString()}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#cbd5e1' }}>{r.chi_antes.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                                <td style={{ padding: '10px 12px', textAlign: 'right', color: chiCor, fontWeight: 'bold' }}>{r.chi_depois.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                              </tr>
                            );
                          })}
                          {sortedTabelaImpacto.length === 0 && (
                            <tr>
                              <td colSpan="6" style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>
                                Nenhuma alteração de Conjunto detectada ou compatível com o filtro.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
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
