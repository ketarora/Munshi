"""Domain errors surfaced by the API layer as 4xx, never 500."""

from __future__ import annotations


class MunshiError(RuntimeError):
    status_code = 400


class CallNotFound(MunshiError):
    status_code = 404


class ApprovalNotFound(MunshiError):
    status_code = 404


class Forbidden(MunshiError):
    status_code = 403


class ApprovalExpired(MunshiError):
    status_code = 409


class ApprovalAlreadyDecided(MunshiError):
    status_code = 409


class InvalidDecision(MunshiError):
    status_code = 422


class SecondFactorRequired(MunshiError):
    status_code = 428
