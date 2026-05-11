from django.utils import timezone
from django_fsm import transition

from apps.political_agenda.workflows import (
    PoliticalAgendaEventWorkflow,
    PoliticalAgendaRequestWorkflow,
)


class PoliticalAgendaRequestTransitions:
    workflow = PoliticalAgendaRequestWorkflow()

    @transition(
        field="state",
        source=workflow.PENDING,
        target=workflow.IN_REVIEW,
        permission="political_agenda.change_politicalagendarequest",
        custom=dict(
            verbose="Enviar a revisión",
            icon="time",
            color="primary",
            title="Enviar solicitud a revisión",
            text="¿Confirmas que esta solicitud pasa a revisión?",
        ),
    )
    def send_to_review(self, user=None, **kwargs):
        self.reviewed_by = user

    @transition(
        field="state",
        source=[workflow.PENDING, workflow.IN_REVIEW],
        target=workflow.APPROVED,
        permission="political_agenda.approve_politicalagendarequest",
        custom=dict(
            verbose="Aprobar",
            icon="check-circle",
            color="success",
            title="Aprobar solicitud",
            text="¿Confirmas que esta solicitud tentativa queda aprobada?",
        ),
    )
    def approve(self, user=None, **kwargs):
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.rejection_reason = ""

    @transition(
        field="state",
        source=[workflow.PENDING, workflow.IN_REVIEW],
        target=workflow.REJECTED,
        permission="political_agenda.reject_politicalagendarequest",
        custom=dict(
            verbose="Rechazar",
            icon="cross-circle",
            color="danger",
            title="Rechazar solicitud",
            text="¿Confirmas que esta solicitud queda rechazada?",
            form="apps.political_agenda.forms.RejectAgendaRequestForm",
        ),
    )
    def reject(self, user=None, rejection_reason="", **kwargs):
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.rejection_reason = rejection_reason or ""

    @transition(
        field="state",
        source=[workflow.PENDING, workflow.IN_REVIEW, workflow.APPROVED],
        target=workflow.CANCELED,
        permission="political_agenda.change_politicalagendarequest",
        custom=dict(
            verbose="Cancelar",
            icon="cross",
            color="danger",
            title="Cancelar solicitud",
            text="¿Confirmas la cancelación de esta solicitud?",
        ),
    )
    def cancel(self, **kwargs):
        """Cancel request."""


class PoliticalAgendaEventTransitions:
    workflow = PoliticalAgendaEventWorkflow()

    @transition(
        field="state",
        source=[workflow.DRAFT, workflow.RESCHEDULED],
        target=workflow.SCHEDULED,
        permission="political_agenda.schedule_politicalagendaevent",
        custom=dict(
            verbose="Agendar",
            icon="calendar-tick",
            color="success",
            title="Agendar evento",
            text="¿Confirmas que este evento bloquea formalmente la agenda del candidato?",
        ),
    )
    def schedule(self, **kwargs):
        self.validate_agenda_rules(as_scheduled=True)

    @transition(
        field="state",
        source=workflow.SCHEDULED,
        target=workflow.RESCHEDULED,
        permission="political_agenda.schedule_politicalagendaevent",
        custom=dict(
            verbose="Marcar reprogramado",
            icon="calendar-edit",
            color="warning",
            title="Reprogramar evento",
            text="El evento dejará de bloquear como AGENDADO hasta que se vuelva a agendar.",
        ),
    )
    def mark_rescheduled(self, **kwargs):
        """Scheduled -> Rescheduled."""

    @transition(
        field="state",
        source=[workflow.SCHEDULED, workflow.RESCHEDULED],
        target=workflow.CANCELED,
        permission="political_agenda.schedule_politicalagendaevent",
        custom=dict(
            verbose="Cancelar",
            icon="cross",
            color="danger",
            title="Cancelar evento",
            text="¿Confirmas la cancelación de este evento?",
        ),
    )
    def cancel(self, **kwargs):
        """Cancel event."""

    @transition(
        field="state",
        source=workflow.SCHEDULED,
        target=workflow.DONE,
        permission="political_agenda.schedule_politicalagendaevent",
        custom=dict(
            verbose="Marcar realizado",
            icon="check-square",
            color="primary",
            title="Marcar realizado",
            text="¿Confirmas que este evento fue realizado?",
        ),
    )
    def mark_done(self, **kwargs):
        """Scheduled -> Done."""
