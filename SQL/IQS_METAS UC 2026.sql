WITH limites AS (
    SELECT
        miq.NUM_CONJTO_ANEEL_MAIQ AS cea,
        EXTRACT(YEAR FROM miq.DATA_INI_VIG_MAIQ) AS ano_ref,
        MAX(
            CASE
                WHEN miq.NUM_TIPO_INDIC_MAIQ = 13
                 AND vmai.MES_VMAI = 12
                THEN TO_NUMBER(
                         REPLACE(vmai.VAL_VMAI, ',', '.')
                         DEFAULT NULL ON CONVERSION ERROR
                     )
            END
        ) AS limite_dec,
        MAX(
            CASE
                WHEN miq.NUM_TIPO_INDIC_MAIQ = 14
                 AND vmai.MES_VMAI = 12
                THEN TO_NUMBER(
                         REPLACE(vmai.VAL_VMAI, ',', '.')
                         DEFAULT NULL ON CONVERSION ERROR
                     )
            END
        ) AS limite_fec
    FROM IQS.META_ANEEL_INDIC_QUALID_SERV miq
    JOIN IQS.VAL_META_ANEEL_INDIC_QUALID vmai
      ON vmai.NUM_META_ANEEL_VMAI = miq.NUM_SEQ_MAIQ
    WHERE miq.NUM_TIPO_INDIC_MAIQ IN (13,14)
    GROUP BY
        miq.NUM_CONJTO_ANEEL_MAIQ,
        EXTRACT(YEAR FROM miq.DATA_INI_VIG_MAIQ)
),
uc_base AS (
    SELECT
        ue.ISN_UC,
        ue.NUM_CONJTO_ANEEL_FIXO_UC AS cea,
        ue.INDIC_LOCAL_TEC_UC AS urb_rur,
        ue.COD_GRUPO_NIVEL_TENSAO_UC,
        ue.COD_NIVEL_TENSAO_UC
    FROM CIS.UC_ENERGIA ue
    WHERE ue.TIPO_SIT_UC IN ('LG','CR')
),
base AS (
    SELECT
        u.ISN_UC,
        u.cea,
        l.ano_ref,
        l.limite_dec,
        l.limite_fec,
        u.urb_rur,
        ntn.COD_GRUPO_NTFN,
        ntn.COD_NTFN,
        ntn.DESC_NTFN
    FROM uc_base u
    JOIN limites l
      ON l.cea = u.cea
    JOIN CIS.NIVEL_TENSAO_FORNECIMENTO ntn
      ON ntn.COD_GRUPO_NTFN = u.COD_GRUPO_NIVEL_TENSAO_UC
     AND ntn.COD_NTFN       = u.COD_NIVEL_TENSAO_UC
    WHERE l.ano_ref = 2026
)
SELECT
    b.ISN_UC,
    b.cea AS COD_CONJUNTO_ANEEL,
    b.ano_ref,
    b.urb_rur,
    b.COD_GRUPO_NTFN,
    b.COD_NTFN,
    b.DESC_NTFN,
    b.limite_dec AS META_DEC,
    b.limite_fec AS META_FEC,  
    /* ================= META DIC ================= */
    CASE
    /* ===== GRUPO A – AT ===== */
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('1','2','3')
     AND b.urb_rur = 'U' THEN 3
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('1','2','3')
     AND b.urb_rur = 'R' THEN 5
    /* ===== GRUPO A – MT URBANA ===== */
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'U'
     AND b.limite_dec <= 5 THEN 3
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'U'
     AND b.limite_dec <= 10 THEN 5
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'U'
     AND b.limite_dec <= 15 THEN 7
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'U'
     AND b.limite_dec <= 20 THEN 9
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'U'
     AND b.limite_dec <= 25 THEN 10
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'U' THEN 12
    /* GRUPO A – MT RURAL */
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R'
     AND b.limite_dec <= 5 THEN 8
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R'
     AND b.limite_dec <= 10 THEN 13
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R'
     AND b.limite_dec <= 15 THEN 19
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R'
     AND b.limite_dec <= 20 THEN 24
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R'
     AND b.limite_dec <= 25 THEN 28
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R'
     AND b.limite_dec <= 40 THEN 33    
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R' THEN 37
    /* ===== GRUPO B – URBANO ===== */
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_dec <= 5 THEN 4
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_dec <= 10 THEN 7
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_dec <= 15 THEN 10
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_dec <= 20 THEN 12
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_dec <= 25 THEN 14
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_dec <= 40 THEN 15
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_dec <= 50 THEN 18  
    /* URBANO – DEFAULT */
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U' THEN 21
    /* ===== GRUPO B – RURAL ===== */
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R'
     AND b.limite_dec <= 5 THEN 10
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R'
     AND b.limite_dec <= 10 THEN 16
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R'
     AND b.limite_dec <= 15 THEN 20
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R'
     AND b.limite_dec <= 20 THEN 24
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R'
     AND b.limite_dec <= 25 THEN 28
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R'
     AND b.limite_dec <= 40 THEN 33
    /* RURAL – DEFAULT */
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R' THEN 40
    END AS META_DIC,
    /* ================= META FIC ================= */
    CASE
    /* ===== GRUPO A – AT ===== */
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('1','2','3')
     AND b.urb_rur = 'U' THEN 2
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('1','2','3')
     AND b.urb_rur = 'R' THEN 4
    /* ===== GRUPO A – MT URBANA ===== */
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'U'
     AND b.limite_fec <= 5  THEN 3
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'U'
     AND b.limite_fec <= 10 THEN 4
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'U'
     AND b.limite_fec <= 15 THEN 5
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'U'
     AND b.limite_fec <= 20 THEN 6
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'U'
     AND b.limite_fec <= 25 THEN 6
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'U' THEN 7
    /* ===== GRUPO A – MT RURAL ===== */
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R'
     AND b.limite_fec <= 5  THEN 4
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R'
     AND b.limite_fec <= 10 THEN 5
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R'
     AND b.limite_fec <= 15 THEN 7
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R'
     AND b.limite_fec <= 20 THEN 8
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R'
     AND b.limite_fec <= 25 THEN 9
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R'
     AND b.limite_fec <= 40 THEN 10     
    WHEN b.COD_GRUPO_NTFN = 'A'
     AND b.COD_NTFN IN ('3a','4','S')
     AND b.urb_rur = 'R' THEN 11
    /* ===== GRUPO B – URBANO ===== */
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_fec <= 5  THEN 3
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_fec <= 10 THEN 4
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_fec <= 15 THEN 5
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_fec <= 20 THEN 6
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_fec <= 25 THEN 7
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_fec <= 40 THEN 7
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U'
     AND b.limite_fec <= 50 THEN 8       
    /* DEFAULT URBANO */
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'U' THEN 9
    /* ===== GRUPO B – RURAL ===== */
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R'
     AND b.limite_fec <= 5  THEN 4
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R'
     AND b.limite_fec <= 10 THEN 6
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R'
     AND b.limite_fec <= 15 THEN 7
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R'
     AND b.limite_fec <= 20 THEN 8
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R'
     AND b.limite_fec <= 25 THEN 9
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R'
     AND b.limite_fec <= 40 THEN 10      
    /* DEFAULT RURAL */
    WHEN b.COD_GRUPO_NTFN = 'B'
     AND b.urb_rur = 'R' THEN 12
    END AS META_FIC,  
 /* ================= META DICRI ================= */
    CASE
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('4','5') AND b.urb_rur = 'U' THEN 8
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('4','5') AND b.urb_rur = 'R' THEN 21
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'U' THEN 13
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'R' THEN 21
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('1','2','3') THEN 0.001 
    END AS META_DICRI,
    /* ================= META DISE ================= */
    CASE
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'U' THEN 24
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'R' THEN 48
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('4','5') AND b.urb_rur = 'U' THEN 24
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('4','5') AND b.urb_rur = 'R' THEN 48
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('1','2','3') THEN 0.001 
    END AS META_DISE,
    /* ================= META DMIC ================= */
    CASE 
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('1','2','3') AND b.urb_rur = 'U' THEN 2
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('1','2','3') AND b.urb_rur = 'R' THEN 4
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'U' AND b.limite_dec <= 5 THEN 3
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'U' AND b.limite_dec <= 10 THEN 5
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'U' AND b.limite_dec <= 15 THEN 6
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'U' AND b.limite_dec <= 20 THEN 7
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'U' AND b.limite_dec <= 25 THEN 8
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'U' THEN 8
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'R' AND b.limite_dec <= 5 THEN 6
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'R' AND b.limite_dec <= 10 THEN 10
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'R' AND b.limite_dec <= 15 THEN 14
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'R' AND b.limite_dec <= 20 THEN 18
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'R' AND b.limite_dec <= 25 THEN 20
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'R' AND b.limite_dec <= 40 THEN 24    
        WHEN b.COD_GRUPO_NTFN = 'A' AND b.COD_NTFN IN ('3a','4','S') AND b.urb_rur = 'R' THEN 24
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'U' AND b.limite_dec <= 5 THEN 3
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'U' AND b.limite_dec <= 10 THEN 5
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'U' AND b.limite_dec <= 15 THEN 7
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'U' AND b.limite_dec <= 20 THEN 9
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'U' AND b.limite_dec <= 25 THEN 10
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'U' AND b.limite_dec <= 40 THEN 12
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'U' AND b.limite_dec <= 50 THEN 12  
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'U' THEN 12
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'R' AND b.limite_dec <= 5 THEN 8
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'R' AND b.limite_dec <= 10 THEN 12
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'R' AND b.limite_dec <= 15 THEN 15
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'R' AND b.limite_dec <= 20 THEN 18
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'R' AND b.limite_dec <= 25 THEN 20
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'R' AND b.limite_dec <= 40 THEN 24
        WHEN b.COD_GRUPO_NTFN = 'B' AND b.urb_rur = 'R' THEN 24
    END AS META_DMIC
FROM base b;