"""Canonical enumerations (roadmap Section 7.2). UPPER_SNAKE values."""
from enum import StrEnum


class StageName(StrEnum):
    MATERIAL_CONDITIONING = "MATERIAL_CONDITIONING"
    PLASTICIZING = "PLASTICIZING"
    INJECTION = "INJECTION"
    PACKING = "PACKING"
    COOLING = "COOLING"
    QUALITY_INSPECTION = "QUALITY_INSPECTION"

    @property
    def sequence_index(self) -> int:
        return STAGE_ORDER.index(self) + 1


STAGE_ORDER: tuple[StageName, ...] = (
    StageName.MATERIAL_CONDITIONING,
    StageName.PLASTICIZING,
    StageName.INJECTION,
    StageName.PACKING,
    StageName.COOLING,
    StageName.QUALITY_INSPECTION,
)
# S1-S5 are executed by run_stage(); S6 by predict().
INTELLIGENCE_STAGES: tuple[StageName, ...] = STAGE_ORDER[:5]


class RunStatus(StrEnum):
    INITIALIZED = "INITIALIZED"
    MATERIAL_CONDITIONING = "MATERIAL_CONDITIONING"
    PLASTICIZING = "PLASTICIZING"
    INJECTION = "INJECTION"
    PACKING = "PACKING"
    COOLING = "COOLING"
    QUALITY_INSPECTION = "QUALITY_INSPECTION"
    FINAL_RESULT = "FINAL_RESULT"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    ABORTED = "ABORTED"


class StageSubstate(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class RiskLevel(StrEnum):
    NORMAL = "NORMAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def ordinal(self) -> int:
        return _RISK_ORDER.index(self)


_RISK_ORDER = (RiskLevel.NORMAL, RiskLevel.LOW, RiskLevel.MEDIUM,
               RiskLevel.HIGH, RiskLevel.CRITICAL)


class PredictionLabel(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class ConstraintSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AnomalyMethod(StrEnum):
    ZSCORE = "zscore"
    IQR = "iqr"
    PERCENTILE_BAND = "percentile_band"
    SPEC_LIMIT = "spec_limit"
    ISOLATION_FOREST = "isolation_forest"
    AUTOENCODER = "autoencoder"
    SPC = "spc"


class RunMode(StrEnum):
    AUTO = "auto"
    STEPWISE = "stepwise"


class SpeedFactor(StrEnum):
    HALF = "0.5x"
    ONE = "1x"
    TWO = "2x"
    INSTANT = "instant"


class InferenceBackend(StrEnum):
    REAL = "real"
    MOCK = "mock"


class SourceTier(StrEnum):
    REAL = "real"
    SYNTHETIC = "synthetic"
    AUGMENTED = "augmented"


class DataProvenance(StrEnum):
    DATASET_DERIVED = "dataset_derived"
    SPECIFICATION_DERIVED = "specification_derived"
    HEURISTIC = "heuristic"
    LEARNED = "learned"
    SYNTHETIC = "synthetic"
    UNVALIDATED = "unvalidated"


class ParameterKind(StrEnum):
    SETPOINT = "setpoint"
    LOT_ATTRIBUTE = "lot_attribute"
    PRODUCT_CONTEXT = "product_context"
    MACHINE_CONTEXT = "machine_context"


class CandidateFlag(StrEnum):
    EXTRAPOLATED = "EXTRAPOLATED"
    UNSTABLE = "UNSTABLE"
    NEAR_WINDOW_EDGE = "NEAR_WINDOW_EDGE"


class MachineType(StrEnum):
    HYDRAULIC = "HYDRAULIC"
    ELECTRIC = "ELECTRIC"
    HYBRID = "HYBRID"