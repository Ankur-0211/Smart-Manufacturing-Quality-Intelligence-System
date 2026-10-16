"""Typed errors across the intelligence interface (roadmap Section 9.1).
Domain breaches are data, never exceptions."""
from typing import Any


class IntelligenceError(Exception):
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, field: str | None = None,
                 hint: str | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field
        self.hint = hint
        self.details = details


class InvalidInputError(IntelligenceError):
    code = "INVALID_INTELLIGENCE_INPUT"


class UnknownParameterError(IntelligenceError):
    code = "UNKNOWN_PARAMETER"


class LockedParameterError(IntelligenceError):
    code = "PARAMETER_NOT_ACTIONABLE"


class UpstreamMissingError(IntelligenceError):
    code = "UPSTREAM_CONTEXT_MISSING"


class StageResultsIncompleteError(IntelligenceError):
    code = "STAGE_RESULTS_INCOMPLETE"


class ModelNotLoadedError(IntelligenceError):
    code = "MODEL_NOT_LOADED"


class ArtifactInvalidError(IntelligenceError):
    code = "MODEL_ARTIFACT_INVALID"


class FeatureSchemaMismatchError(IntelligenceError):
    code = "FEATURE_SCHEMA_MISMATCH"


class CapabilityUnavailableError(IntelligenceError):
    code = "CAPABILITY_UNAVAILABLE"


class RegistryInvalidError(IntelligenceError):
    code = "REGISTRY_INVALID"