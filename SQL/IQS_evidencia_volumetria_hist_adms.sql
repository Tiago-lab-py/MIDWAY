SELECT
	--to_char(DTHR_INC_REGIS_HIADMS, 'yyyymm') AS data_processamento,
	to_char(DATA_HORA_INIC_INTRP_ULT_HIADMS, 'yyyymm') AS data_itrp_inic ,
	count(*) AS contagem
FROM
	iqs.HIST_INTEGRACAO_ADMS hia
	--WHERE to_char(DATA_HORA_INIC_INTRP_ULT_HIADMS,'yyyymm') = '202605'
	--AND to_char(DTHR_INC_REGIS_HIADMS,'yyyymm') <>'202606'
GROUP BY
	to_char(DATA_HORA_INIC_INTRP_ULT_HIADMS, 'yyyymm')--,
	--to_char(DTHR_INC_REGIS_HIADMS, 'yyyymm')
ORDER BY
	1 DESC--,
	--2 DESC