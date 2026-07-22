from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class PropostaTratamento:
    """Objeto padronizado gerado por um módulo após detecção de anomalia."""
    def __init__(
        self,
        chave_negocio: str,
        evidencias: Dict[str, Any],
        impacto: str,
        acao_sugerida: str,
        campos_iqs_afetados: Optional[List[str]] = None,
        exportacao_iqs: Optional[str] = None
    ):
        self.chave_negocio = chave_negocio
        self.evidencias = evidencias
        self.impacto = impacto
        self.acao_sugerida = acao_sugerida
        self.campos_iqs_afetados = campos_iqs_afetados or []
        self.exportacao_iqs = exportacao_iqs


class BaseModulo(ABC):
    """
    Contrato Comum de Módulo Pluggável MIDWAY.
    Espelha a documentação oficial de DOCs/modulos/README.md
    """
    
    @property
    @abstractmethod
    def codigo_modulo(self) -> str:
        """Identificador estável do módulo (ex: 'SOBREPOSICAO_UC')."""
        pass
        
    @property
    @abstractmethod
    def escopo(self) -> str:
        """Ex: 'ocorrencia', 'interrupcao', 'uc', 'equipamento'."""
        pass

    @property
    @abstractmethod
    def criterio_anomalia(self) -> str:
        """Regra objetiva de detecção descrita no contrato."""
        pass

    @property
    @abstractmethod
    def risco_falso_positivo(self) -> str:
        """Cuidados para evitar ajuste indevido."""
        pass

    @abstractmethod
    def detectar_anomalias(self) -> List[PropostaTratamento]:
        """
        Método principal que o orquestrador irá chamar.
        Deve ler as fontes de dados (DuckDB/Postgres), rodar a regra
        e retornar a lista de propostas padronizadas para serem salvas.
        """
        pass
