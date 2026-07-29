WITH
chaves_filtradas AS (
  -- 1. Filtro inicial: Seleciona apenas chaves 'RA' com exatamente 1 UC acumulada.
  SELECT
    ch.num_oper_chvp,
    ch.num_oper_alim_lig_chvp,
    ch.num_bloco_lig_chvp,
    ch.indic_posic_normal_chvp,
    (ch.qtde_uc_resid_acum_chvp + ch.qtde_uc_comerc_acum_chvp + ch.qtde_uc_indust_acum_chvp) AS uc_acumulada,
    ch.corr_carga_chvp,
    ch.deman_ativa_diver_acum_chvp,
    ch.deman_reat_diver_acum_chvp
  FROM gdg.chave_at ch
  INNER JOIN (
    SELECT DISTINCT chave.num_oper_chvp
    FROM gdg.chave_at chave
    INNER JOIN snap_user.material_manutencao_obra mat ON mat.num_seq_mmo = chave.num_mtr_chvp
    WHERE SUBSTR(mat.nome_usual_mmo, 1, 2) = 'RA' AND mat.num_visao_mmo = 3
  ) r ON ch.num_oper_chvp = r.num_oper_chvp
  WHERE ch.num_visao_chvp = 3
    AND (ch.qtde_uc_resid_acum_chvp + ch.qtde_uc_comerc_acum_chvp + ch.qtde_uc_indust_acum_chvp) = 1
),
busca_recursiva_bloco (num_oper_chvp_origem, current_bloco, profundidade) AS (
  -- 2. CTE Recursiva: Navega pelos blocos A JUSANTE (para frente) em direção ao consumidor
  -- Ponto de Partida (Anchor): O bloco imediatamente ligado à chave RA
  SELECT
    ch.num_oper_chvp AS num_oper_chvp_origem,
    ch.num_bloco_lig_chvp AS current_bloco,
    1 AS profundidade
  FROM chaves_filtradas ch
  WHERE ch.num_bloco_lig_chvp IS NOT NULL
  
  UNION ALL
  
  -- Recursão: Busca a próxima chave cujo "bloco fonte" é o bloco atual e pula para o "bloco ligado" dela
  SELECT
    br.num_oper_chvp_origem,
    ch_next.num_bloco_lig_chvp AS current_bloco,
    br.profundidade + 1
  FROM busca_recursiva_bloco br
  INNER JOIN gdg.chave_at ch_next ON br.current_bloco = ch_next.num_bloco_fonte_chvp
  WHERE ch_next.num_bloco_lig_chvp IS NOT NULL
    AND ch_next.num_visao_chvp = 3
)
-- A CLÁUSULA CYCLE VEM AQUI: Pertence à definição da CTE recursiva, antes da vírgula!
CYCLE current_bloco SET is_cycle TO 'Y' DEFAULT 'N',

dados_uc_encontrada AS (
  -- 3. Identifica a UC associada ao bloco da rede, ignorando caminhos com loop
  SELECT
    uc_data.*
  FROM (
    SELECT
      b.num_oper_chvp_origem,
      ue.isn_uc,
      ue.NUMERO_POSTO_UC,          -- Nova coluna
      ue.VAL_ENC_USO_SIS_DISTR_UC, -- Nova coluna
      ue.COD_VIP_UC,               -- Nova coluna
      ue.INDIC_LOCAL_TEC_UC,
      ue.COD_NIVEL_TENSAO_UC,
      ue.COD_GRUPO_NIVEL_TENSAO_UC,
      ue.VAL_BASE_CALC_COMPEN_UC,
      ue.TIPO_SIT_UC,
      ue.COD_ATIV_CNAE_UC,
      ue.COMPL_END_UC,
      tp.comprim_real_cabo_trprim / 1000 AS km_bloco,
      -- Rankeia os resultados pela profundidade para selecionar a primeira UC encontrada no caminho
      ROW_NUMBER() OVER(PARTITION BY b.num_oper_chvp_origem ORDER BY b.profundidade) as rn
    FROM busca_recursiva_bloco b
    INNER JOIN gdg.trecho_primario tp ON b.current_bloco = tp.num_bloco_trprim
    INNER JOIN gdg.posto_transformador pt ON pt.num_geo_trecho_prim_posto = tp.num_seq_geo
    INNER JOIN cis.uc_energia ue ON ue.numero_posto_uc = pt.num_oper_posto
    WHERE ue.tipo_sit_uc IN ('LG', 'CR') 
      AND b.is_cycle = 'N'
  ) uc_data
  WHERE uc_data.rn = 1
)
-- 4. Consulta Final: Retorna as chaves com TODOS os dados da UC
SELECT
  ch.uc_acumulada,
  uc.isn_uc,
  uc.NUMERO_POSTO_UC,          -- Nova coluna exportada
  uc.VAL_ENC_USO_SIS_DISTR_UC, -- Nova coluna exportada
  uc.COD_VIP_UC,               -- Nova coluna exportada
  uc.INDIC_LOCAL_TEC_UC,
  uc.COD_NIVEL_TENSAO_UC,
  uc.COD_GRUPO_NIVEL_TENSAO_UC,
  uc.VAL_BASE_CALC_COMPEN_UC,
  uc.TIPO_SIT_UC,
  uc.COD_ATIV_CNAE_UC,
  uc.COMPL_END_UC,
  SUBSTR(ch.num_oper_chvp, 1, 5) AS cod_operacional,
  se.sigla_se,
  a.nome_aloper,
  a.num_oper_alim_aloper,
  ch.num_oper_chvp,
  ch.indic_posic_normal_chvp,
  ch.corr_carga_chvp AS corrente,
  ROUND(SQRT(POWER(ch.deman_ativa_diver_acum_chvp, 2) + POWER(ch.deman_reat_diver_acum_chvp, 2)), 2) AS demanda_VA,
  uc.km_bloco
FROM chaves_filtradas ch
INNER JOIN snap_user.subestacao se ON SUBSTR(TO_CHAR(ch.num_oper_alim_lig_chvp), 1, 5) * 10 = se.car_se
INNER JOIN gdg.alimentador_operacional a ON ch.num_oper_alim_lig_chvp = a.num_oper_alim_aloper
LEFT JOIN dados_uc_encontrada uc ON ch.num_oper_chvp = uc.num_oper_chvp_origem
ORDER BY se.sigla_se, cod_operacional
