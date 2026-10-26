"""PostureEngine: calibration + two independent signal trackers + the pet state machine."""

from __future__ import annotations

from app.posture.calibration import Calibrator
from app.posture.config import PostureConfig
from app.posture.features import back_deviation, head_severity
from app.posture.models import (
    BackComponent,
    Baseline,
    CalibrationOutcome,
    Observation,
    PetState,
    PostureResult,
    SignalKind,
    SignalLevel,
    SignalStatus,
)
from app.posture.signal_tracker import SignalTracker

STATE_TITLES: dict[PetState, str] = {
    PetState.CALIBRATING: "Let's get to know you",
    PetState.THRIVING: "Thriving",
    PetState.WARNING: "Posture check",
    PetState.CRITICAL: "Time for a reset",
    PetState.UNAVAILABLE: "Tracking unavailable",
}

_BACK_MESSAGES: dict[BackComponent, str] = {
    BackComponent.LEANING_IN: (
        "You've been leaning forward for a while. Try returning to a comfortable position."
    ),
    BackComponent.HUNCHING: (
        "Your shoulders have been rounding for a while. Try gently rolling them back."
    ),
    BackComponent.SINKING: "You've been sinking into your seat for a while. Try sitting back up.",
    BackComponent.SIDE_LEAN: "You've been leaning to one side for a while. Try re-centering.",
}
HEAD_MESSAGE = "Your head has been tilted downward for a while. Take a moment to reset."
THRIVING_MESSAGE = "Looking good! Your posture is within your usual range."
DRIFTING_MESSAGE = "Noticing a small change. No worries yet."
RECOVERY_MESSAGE = "Nice recovery! Your posture is back within your usual range."
NEEDS_CALIBRATION_MESSAGE = (
    "Sit comfortably upright, then calibrate so I can learn your usual posture."
)
CALIBRATING_MESSAGE = "Hold still for a moment while I learn your comfortable position."
RECOVERY_MESSAGE_HOLD_S = 5.0
UNAVAILABLE_MESSAGE = "I can't see you clearly. Make sure your face and both shoulders are in view."


def issue_message(status: SignalStatus) -> str:
    if status.kind is SignalKind.HEAD:
        return HEAD_MESSAGE
    return _BACK_MESSAGES[status.dominant_component or BackComponent.LEANING_IN]


def next_pet_state(
    *,
    has_baseline: bool,
    calibrating: bool,
    back: SignalLevel,
    head: SignalLevel,
) -> PetState:
    """The pet state machine as one explicit, pure transition function.

    Entry conditions, in priority order:
      CALIBRATING  - calibration in progress, or no baseline yet
      UNAVAILABLE  - neither signal has a reliable measurement (past the grace period)
      CRITICAL     - any signal is critical
      WARNING      - any signal has an episode at least as long as the warning duration
      THRIVING     - otherwise (including short 'deviating' episodes)
    Recovery out of WARNING/CRITICAL happens when the trackers end their episodes, i.e.
    after the configured recovery confirmation; hysteresis lives in ``SignalTracker``.
    """
    if calibrating or not has_baseline:
        return PetState.CALIBRATING
    levels = (back, head)
    if all(level is SignalLevel.UNAVAILABLE for level in levels):
        return PetState.UNAVAILABLE
    if SignalLevel.CRITICAL in levels:
        return PetState.CRITICAL
    if SignalLevel.WARNING in levels:
        return PetState.WARNING
    return PetState.THRIVING


class PostureEngine:
    """Consumes observations, returns posture results. Single-threaded, no I/O."""

    def __init__(self, config: PostureConfig | None = None, baseline: Baseline | None = None):
        self._config = config or PostureConfig()
        self._baseline = baseline
        self._calibrator: Calibrator | None = None
        self._calibration_camera = 0
        self._back = SignalTracker(SignalKind.BACK, self._config.timing, self._config.levels)
        self._head = SignalTracker(SignalKind.HEAD, self._config.timing, self._config.levels)
        self._state: PetState = PetState.CALIBRATING
        self._recovered_at: float | None = None

    @property
    def baseline(self) -> Baseline | None:
        return self._baseline

    @property
    def config(self) -> PostureConfig:
        return self._config

    @property
    def is_calibrating(self) -> bool:
        return self._calibrator is not None

    @property
    def state(self) -> PetState:
        return self._state

    def set_baseline(self, baseline: Baseline | None) -> None:
        self._baseline = baseline
        self.reset()

    def update_config(self, config: PostureConfig) -> None:
        self._config = config
        for tracker in (self._back, self._head):
            tracker.configure(config.timing, config.levels)

    def start_calibration(self, now: float, camera_index: int) -> None:
        self._calibrator = Calibrator(self._config.calibration, camera_index, now)
        self.reset()

    def cancel_calibration(self) -> None:
        self._calibrator = None

    def reset(self) -> None:
        """Forget timers and smoothing (used on pause/resume and recalibration)."""
        self._recovered_at = None
        self._back.reset()
        self._head.reset()

    def update(self, observation: Observation) -> PostureResult:
        if self._calibrator is not None:
            return self._update_calibration(observation)
        if self._baseline is None:
            return self._result(observation, self._unavailable_statuses(), PetState.CALIBRATING)

        tolerances = self._config.effective_tolerances()
        back_sev: float | None = None
        component: BackComponent | None = None
        if observation.body is not None:
            deviation = back_deviation(observation.body, self._baseline, tolerances)
            back_sev, component = deviation.severity, deviation.dominant
        head_sev: float | None = None
        if observation.head is not None:
            head_sev = head_severity(
                observation.head, self._baseline, tolerances, self._config.quality
            )

        statuses = (
            self._back.update(observation.timestamp, back_sev, component),
            self._head.update(observation.timestamp, head_sev),
        )
        state = next_pet_state(
            has_baseline=True,
            calibrating=False,
            back=statuses[0].level,
            head=statuses[1].level,
        )
        return self._result(observation, statuses, state)

    def unavailable_result(self, now: float, reason: str) -> PostureResult:
        """Result for when no frames arrive at all (e.g. camera failure)."""
        self.reset()
        self._state = PetState.UNAVAILABLE
        back, head = self._unavailable_statuses()
        return PostureResult(
            timestamp=now,
            state=PetState.UNAVAILABLE,
            tracking_available=False,
            body_valid=False,
            head_valid=False,
            back=back,
            head=head,
            active_issue=None,
            title=STATE_TITLES[PetState.UNAVAILABLE],
            message=reason,
        )

    def _update_calibration(self, observation: Observation) -> PostureResult:
        assert self._calibrator is not None
        outcome = self._calibrator.add(observation)
        progress = self._calibrator.progress
        if outcome is not None:
            self._calibrator = None
            if outcome.success:
                self._baseline = outcome.baseline
                self.reset()
        return self._result(
            observation,
            self._unavailable_statuses(),
            PetState.CALIBRATING,
            progress=progress if outcome is None else (1.0 if outcome.success else progress),
            outcome=outcome,
        )

    @staticmethod
    def _unavailable_statuses() -> tuple[SignalStatus, SignalStatus]:
        return (
            SignalStatus(SignalKind.BACK, SignalLevel.UNAVAILABLE, None, 0.0),
            SignalStatus(SignalKind.HEAD, SignalLevel.UNAVAILABLE, None, 0.0),
        )

    def _result(
        self,
        observation: Observation,
        statuses: tuple[SignalStatus, SignalStatus],
        state: PetState,
        progress: float | None = None,
        outcome: CalibrationOutcome | None = None,
    ) -> PostureResult:
        back, head = statuses
        active = max(statuses, key=lambda s: (s.level.rank, s.issue_duration_s))
        active_issue = active.kind if active.level.rank >= SignalLevel.WARNING.rank else None

        if state is PetState.CALIBRATING:
            calibrating = progress is not None and outcome is None
            message = CALIBRATING_MESSAGE if calibrating else NEEDS_CALIBRATION_MESSAGE
            if outcome is not None and not outcome.success and outcome.reason:
                message = f"Calibration didn't succeed: {outcome.reason}"
        elif state is PetState.UNAVAILABLE:
            reason = observation.body_issue or observation.head_issue
            message = f"{reason}. {UNAVAILABLE_MESSAGE}" if reason else UNAVAILABLE_MESSAGE
        elif state in (PetState.WARNING, PetState.CRITICAL):
            message = issue_message(active)
        elif self._state in (PetState.WARNING, PetState.CRITICAL) or (
            self._recovered_at is not None
            and observation.timestamp - self._recovered_at < RECOVERY_MESSAGE_HOLD_S
        ):
            if self._state in (PetState.WARNING, PetState.CRITICAL):
                self._recovered_at = observation.timestamp
            message = RECOVERY_MESSAGE
        elif any(s.level is SignalLevel.DEVIATING for s in statuses):
            message = DRIFTING_MESSAGE
        else:
            message = THRIVING_MESSAGE

        self._state = state
        return PostureResult(
            timestamp=observation.timestamp,
            state=state,
            tracking_available=observation.tracking_available,
            body_valid=observation.body is not None,
            head_valid=observation.head is not None,
            back=back,
            head=head,
            active_issue=active_issue,
            title=STATE_TITLES[state],
            message=message,
            calibration_progress=progress,
            calibration_outcome=outcome,
        )
