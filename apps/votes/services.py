from django.db.models import Max, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from .forms import electoral_districts_for_parish
from .models import ElectoralDignity, ElectoralResultLine, ElectoralResultReport, ElectoralTable


class ElectoralReportConsistencyService:
    HIGH_TURNOUT_PERCENT = 95
    ABRUPT_CHANGE_MIN_VOTES = 50
    ABRUPT_CHANGE_PERCENT = 20

    def __init__(self, form):
        self.form = form
        self.cleaned = form.cleaned_data

    def build_alerts(self):
        alerts = []
        alerts.extend(self._negative_vote_alerts())
        total_alert = self._total_mismatch_alert()
        if total_alert:
            alerts.append(total_alert)
        turnout_alert = self._high_turnout_alert()
        if turnout_alert:
            alerts.append(turnout_alert)
        duplicate_alert = self._duplicate_report_alert()
        if duplicate_alert:
            alerts.append(duplicate_alert)
        abrupt_alert = self._abrupt_change_alert()
        if abrupt_alert:
            alerts.append(abrupt_alert)
        return alerts

    def _candidate_votes(self):
        return [
            self.cleaned.get(self.form.vote_field_name(option)) or 0
            for option in self.form.candidate_options
        ]

    def _total_votes(self):
        return sum(self._candidate_votes()) + (self.cleaned.get("blank_votes") or 0) + (
            self.cleaned.get("null_votes") or 0
        )

    def _negative_vote_alerts(self):
        alerts = []
        for field_name in ("blank_votes", "null_votes"):
            if (self.cleaned.get(field_name) or 0) < 0:
                alerts.append("Hay votos negativos en blancos o nulos.")
        if any(votes < 0 for votes in self._candidate_votes()):
            alerts.append("Hay votos negativos en candidatos.")
        return alerts

    def _total_mismatch_alert(self):
        voters_count = self.cleaned.get("voters_count")
        if voters_count is None:
            return None
        total_votes = self._total_votes()
        if total_votes != voters_count:
            return f"El total no cuadra: {total_votes} votos vs {voters_count} sufragantes."
        return None

    def _high_turnout_alert(self):
        table = self.cleaned.get("table")
        voters_count = self.cleaned.get("voters_count")
        if not table or not voters_count or not table.registered_voters:
            return None
        if voters_count > table.registered_voters:
            return "La participación supera los electores registrados de la mesa."
        turnout = voters_count * 100 / table.registered_voters
        if turnout >= self.HIGH_TURNOUT_PERCENT:
            return f"Participación muy alta: {turnout:.1f}% de la mesa."
        return None

    def _duplicate_report_alert(self):
        report = self._existing_report()
        if report is None:
            return None
        return "Ya existía un acta para esta mesa, dignidad y circunscripción; se actualizará."

    def _abrupt_change_alert(self):
        report = self._existing_report()
        if report is None:
            return None
        previous_total = sum(line.votes for line in report.lines.all())
        new_total = self._total_votes()
        difference = abs(new_total - previous_total)
        if previous_total == 0:
            return None
        percent = difference * 100 / previous_total
        if difference >= self.ABRUPT_CHANGE_MIN_VOTES and percent >= self.ABRUPT_CHANGE_PERCENT:
            return f"Cambio brusco frente al acta anterior: {difference} votos ({percent:.1f}%)."
        return None

    def _existing_report(self):
        table = self.cleaned.get("table")
        dignity = self.cleaned.get("dignity")
        district = self.form.district
        if not table or not dignity or not district:
            return None
        return (
            ElectoralResultReport.objects.filter(
                table=table,
                dignity=dignity,
                district=district,
            )
            .prefetch_related("lines")
            .first()
        )


class ElectoralWatcherReportService:
    def __init__(self, form, *, watcher):
        self.form = form
        self.cleaned = form.cleaned_data
        self.watcher = watcher

    def save(self):
        report, _ = ElectoralResultReport.objects.update_or_create(
            table=self.cleaned["table"],
            dignity=self.cleaned["dignity"],
            district=self.form.district,
            defaults={
                "parish": self.cleaned["parish"],
                "venue": self.cleaned["venue"],
                "watcher": self.watcher,
                "status": ElectoralResultReport.Status.SUBMITTED,
                "voters_count": self.cleaned.get("voters_count"),
                "is_active": True,
            },
        )
        if self.cleaned.get("evidence_file"):
            report.evidence_file = self.cleaned["evidence_file"]
            report.save(update_fields=["evidence_file"])
        report.lines.all().delete()
        self._create_lines(report)
        return report

    def _create_lines(self, report):
        order = 1
        for option in self.form.candidate_options:
            ElectoralResultLine.objects.create(
                report=report,
                line_type=ElectoralResultLine.LineType.CANDIDATE,
                candidate_option=option,
                list_code=option.list_code,
                candidate_name=option.candidate_name,
                votes=self.cleaned.get(self.form.vote_field_name(option)) or 0,
                order=order,
            )
            order += 1
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.BLANK,
            list_code="BLANCOS",
            votes=self.cleaned["blank_votes"],
            order=order,
        )
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.NULL,
            list_code="NULOS",
            votes=self.cleaned["null_votes"],
            order=order + 1,
        )


class ElectoralReportDetailService:
    def __init__(self, report):
        self.report = report

    def build_context(self):
        lines = list(self.report.lines.all())
        candidate_lines = [
            line for line in lines if line.line_type == ElectoralResultLine.LineType.CANDIDATE
        ]
        blank_votes = self._line_votes(lines, ElectoralResultLine.LineType.BLANK)
        null_votes = self._line_votes(lines, ElectoralResultLine.LineType.NULL)
        valid_votes = sum(line.votes for line in candidate_lines)
        total_votes = valid_votes + blank_votes + null_votes
        return {
            "report": self.report,
            "candidate_lines": candidate_lines,
            "blank_votes": blank_votes,
            "null_votes": null_votes,
            "valid_votes": valid_votes,
            "total_votes": total_votes,
            "difference": (
                total_votes - self.report.voters_count
                if self.report.voters_count is not None
                else None
            ),
        }

    def _line_votes(self, lines, line_type):
        return sum(line.votes for line in lines if line.line_type == line_type)


class ElectoralReportDashboardService:
    DIGNITY_TABS = (
        {
            "key": "prefecture",
            "label": "Prefectura",
            "scope": ElectoralDignity.Scope.PROVINCE,
            "rule": ElectoralDignity.ParishKindRule.ALL,
            "keywords": ("prefect",),
        },
        {
            "key": "mayor",
            "label": "Alcaldía",
            "scope": ElectoralDignity.Scope.CANTON,
            "rule": ElectoralDignity.ParishKindRule.ALL,
            "keywords": ("alcald",),
        },
        {
            "key": "urban_councilors",
            "label": "Concejales urbanos",
            "scope": ElectoralDignity.Scope.DISTRICT,
            "rule": ElectoralDignity.ParishKindRule.URBAN,
            "keywords": ("concejal", "urban"),
        },
        {
            "key": "rural_councilors",
            "label": "Concejales rurales",
            "scope": ElectoralDignity.Scope.DISTRICT,
            "rule": ElectoralDignity.ParishKindRule.RURAL,
            "keywords": ("concejal", "rural"),
        },
        {
            "key": "parish_boards",
            "label": "Juntas parroquiales",
            "scope": ElectoralDignity.Scope.PARISH,
            "rule": ElectoralDignity.ParishKindRule.RURAL,
            "keywords": ("junta", "parro"),
        },
    )
    STATUS_BADGES = {
        "missing": ("Sin acta", "badge-light-secondary"),
        "partial": ("Parcial", "badge-light-warning"),
        "submitted": ("Ingresada", "badge-light-primary"),
        "observed": ("Observada", "badge-light-danger"),
        "validated": ("Validada", "badge-light-success"),
    }
    REPORT_STATUS_BADGES = {
        ElectoralResultReport.Status.DRAFT: "badge-light-secondary",
        ElectoralResultReport.Status.SUBMITTED: "badge-light-primary",
        ElectoralResultReport.Status.OBSERVED: "badge-light-danger",
        ElectoralResultReport.Status.VALIDATED: "badge-light-success",
        ElectoralResultReport.Status.REJECTED: "badge-light-dark",
    }

    def __init__(self, filters=None):
        self.filters = filters or {}

    @classmethod
    def broadcast_update(cls):
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
        except ImportError:
            return

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            "electoral_results",
            {
                "type": "electoral_results_updated",
                "payload": cls().build_payload(),
            },
        )

    def build_payload(self):
        reports = self._filtered_reports()
        lines = ElectoralResultLine.objects.filter(report__in=reports)
        expected_items = self._expected_report_items()
        operational_summary = self._build_operational_summary(reports, lines, expected_items)
        summary_rows = self._build_summary_rows(lines)
        candidate_ranking = self._build_candidate_ranking(lines)

        latest = [self._latest_report_row(report) for report in reports.order_by("-created_date")[:20]]
        return {
            "total_votes": sum(row["votes"] or 0 for row in summary_rows),
            "operational_summary": operational_summary,
            "progress_status": self._build_progress_status(reports, expected_items),
            "candidate_ranking": candidate_ranking,
            "lead_margin": self._build_lead_margin(candidate_ranking),
            "parish_summary": self._build_parish_summary(lines),
            "dignities_count": reports.values("dignity").distinct().count(),
            "lists_count": lines.values("list_code").distinct().count(),
            "summary_rows": summary_rows,
            "chart": {
                "categories": [row["label"] for row in summary_rows],
                "series": [row["votes"] or 0 for row in summary_rows],
            },
            "latest": latest,
        }

    def count_expected_reports(self):
        return len(self._expected_report_items())

    def build_dignity_tabs(self, query_params=None):
        selected_dignity = self.filters.get("dignity")
        selected_dignity_id = selected_dignity.pk if selected_dignity else None
        tabs = []
        for definition in self.DIGNITY_TABS:
            dignity = self._resolve_tab_dignity(definition)
            query = query_params.copy() if query_params is not None else None
            if query is not None:
                query.pop("page", None)
                if dignity:
                    query["dignity"] = str(dignity.pk)
                else:
                    query.pop("dignity", None)
            tabs.append(
                {
                    "key": definition["key"],
                    "label": definition["label"],
                    "dignity_id": dignity.pk if dignity else None,
                    "dignity_name": dignity.name if dignity else "",
                    "is_active": bool(dignity and dignity.pk == selected_dignity_id),
                    "is_disabled": dignity is None,
                    "query_string": query.urlencode() if query is not None else "",
                }
            )
        return tabs

    def _filtered_reports(self):
        reports = ElectoralResultReport.objects.select_related(
            "parish", "venue", "table", "dignity", "district", "watcher"
        )
        if self.filters.get("dignity"):
            reports = reports.filter(dignity=self.filters["dignity"])
        if self.filters.get("district"):
            reports = reports.filter(district=self.filters["district"])
        if self.filters.get("parish"):
            reports = reports.filter(parish=self.filters["parish"])
        if self.filters.get("venue"):
            reports = reports.filter(venue=self.filters["venue"])
        if self.filters.get("table"):
            reports = reports.filter(table=self.filters["table"])
        return reports

    def _resolve_tab_dignity(self, definition):
        dignities = ElectoralDignity.objects.filter(
            is_active=True,
            scope=definition["scope"],
            parish_kind_rule=definition["rule"],
        ).order_by("order", "name")
        for dignity in dignities:
            normalized_name = dignity.name.lower()
            if all(keyword in normalized_name for keyword in definition["keywords"]):
                return dignity
        return dignities.first()

    def _build_operational_summary(self, reports, lines, expected_items):
        line_totals = {
            row["line_type"]: row["votes"] or 0
            for row in lines.values("line_type").annotate(votes=Sum("votes"))
        }
        received_reports = reports.count()
        expected_reports = len(expected_items)
        progress_percent = (
            round(received_reports * 100 / expected_reports, 1) if expected_reports else 0
        )
        latest_update = reports.aggregate(latest=Max("modified_date"))["latest"]
        latest_update_display = "Sin actualización"
        if latest_update:
            latest_update_display = date_format(
                timezone.localtime(latest_update), "DATETIME_FORMAT"
            )
        return {
            "expected_reports": expected_reports,
            "received_reports": received_reports,
            "progress_percent": progress_percent,
            "valid_votes": line_totals.get(ElectoralResultLine.LineType.CANDIDATE, 0),
            "blank_votes": line_totals.get(ElectoralResultLine.LineType.BLANK, 0),
            "null_votes": line_totals.get(ElectoralResultLine.LineType.NULL, 0),
            "latest_update": latest_update.isoformat() if latest_update else None,
            "latest_update_display": latest_update_display,
        }

    def _build_progress_status(self, reports, expected_items):
        reports_by_key = {
            (report.table_id, report.dignity_id, report.district_id): report.status
            for report in reports
        }
        return {
            "venues": self._build_status_rows(expected_items, reports_by_key, "venue"),
            "tables": self._build_status_rows(expected_items, reports_by_key, "table"),
            "dignities": self._build_status_rows(expected_items, reports_by_key, "dignity"),
        }

    def _build_status_rows(self, expected_items, reports_by_key, scope):
        groups = {}
        for item in expected_items:
            group = groups.setdefault(
                item[f"{scope}_id"],
                {
                    "label": item[f"{scope}_label"],
                    "expected": 0,
                    "received": 0,
                    "statuses": [],
                },
            )
            group["expected"] += 1
            report_status = reports_by_key.get(item["report_key"])
            if report_status:
                group["received"] += 1
                group["statuses"].append(report_status)

        rows = []
        for group in groups.values():
            status_code = self._resolve_status_code(group)
            status_label, badge_class = self.STATUS_BADGES[status_code]
            progress_percent = (
                round(group["received"] * 100 / group["expected"], 1)
                if group["expected"]
                else 0
            )
            rows.append(
                {
                    "label": group["label"],
                    "expected": group["expected"],
                    "received": group["received"],
                    "progress_percent": progress_percent,
                    "status": status_code,
                    "status_label": status_label,
                    "status_badge_class": badge_class,
                }
            )
        status_order = {code: index for index, code in enumerate(self.STATUS_BADGES.keys())}
        return sorted(
            rows,
            key=lambda row: (status_order[row["status"]], row["label"]),
        )

    def _resolve_status_code(self, group):
        if group["received"] == 0:
            return "missing"
        if group["received"] < group["expected"]:
            return "partial"
        if any(
            status
            in {
                ElectoralResultReport.Status.OBSERVED,
                ElectoralResultReport.Status.REJECTED,
            }
            for status in group["statuses"]
        ):
            return "observed"
        if group["statuses"] and all(
            status == ElectoralResultReport.Status.VALIDATED for status in group["statuses"]
        ):
            return "validated"
        return "submitted"

    def _expected_report_items(self):
        tables = ElectoralTable.objects.filter(is_active=True).select_related(
            "venue__parish__canton__province"
        )
        if self.filters.get("parish"):
            tables = tables.filter(venue__parish=self.filters["parish"])
        if self.filters.get("venue"):
            tables = tables.filter(venue=self.filters["venue"])
        if self.filters.get("table"):
            tables = tables.filter(pk=self.filters["table"].pk)

        dignity = self.filters.get("dignity")
        district = self.filters.get("district")
        expected_items = []
        for table in tables:
            parish = table.venue.parish
            districts = electoral_districts_for_parish(parish, dignity)
            if district:
                districts = districts.filter(pk=district.pk)
            for expected_district in districts:
                expected_items.append(
                    {
                        "report_key": (
                            table.pk,
                            expected_district.dignity_id,
                            expected_district.pk,
                        ),
                        "venue_id": table.venue_id,
                        "venue_label": table.venue.name,
                        "table_id": table.pk,
                        "table_label": f"{table.number} - {table.get_gender_display()}",
                        "dignity_id": expected_district.dignity_id,
                        "dignity_label": expected_district.dignity.name,
                    }
                )
        return expected_items

    def _build_summary_rows(self, lines):
        summary_rows = list(
            lines.values("line_type", "list_code", "candidate_name")
            .annotate(votes=Sum("votes"))
            .order_by("-votes", "list_code", "candidate_name")
        )
        total_votes = sum(row["votes"] or 0 for row in summary_rows)
        for row in summary_rows:
            votes = row["votes"] or 0
            row["percent"] = round((votes * 100 / total_votes), 1) if total_votes else 0
            row["label"] = row["list_code"]
            if row["candidate_name"]:
                row["label"] = f"{row['list_code']} - {row['candidate_name']}"
        return summary_rows

    def _latest_report_row(self, report):
        updated_at = timezone.localtime(report.modified_date)
        return {
            "id": report.pk,
            "parish": report.parish.name,
            "venue": report.venue.name,
            "table": report.table.number,
            "gender": report.table.get_gender_display(),
            "dignity": report.dignity.name,
            "district": report.district.name,
            "watcher": self._user_label(report.watcher),
            "updated_at": updated_at.isoformat(),
            "updated_at_display": date_format(updated_at, "H:i"),
            "detail_url": reverse("votes:report_detail", args=[report.pk]),
            "status": report.get_status_display(),
            "status_badge_class": self.REPORT_STATUS_BADGES.get(
                report.status, "badge-light-secondary"
            ),
        }

    def _user_label(self, user):
        if user is None:
            return "Sin veedor"
        full_name = user.get_full_name()
        return full_name or user.get_username()

    def _build_candidate_ranking(self, lines):
        rows = list(
            lines.filter(line_type=ElectoralResultLine.LineType.CANDIDATE)
            .values("list_code", "candidate_name")
            .annotate(votes=Sum("votes"))
            .order_by("-votes", "list_code", "candidate_name")
        )
        total_votes = sum(row["votes"] or 0 for row in rows)
        first_votes = rows[0]["votes"] or 0 if rows else 0
        second_votes = rows[1]["votes"] or 0 if len(rows) > 1 else 0
        for index, row in enumerate(rows):
            votes = row["votes"] or 0
            percent = round((votes * 100 / total_votes), 1) if total_votes else 0
            second_percent = (
                round((second_votes * 100 / total_votes), 1) if total_votes else 0
            )
            row["rank"] = index + 1
            row["label"] = row["list_code"]
            if row["candidate_name"]:
                row["label"] = f"{row['list_code']} - {row['candidate_name']}"
            row["percent"] = percent
            row["bar_percent"] = round((votes * 100 / first_votes), 1) if first_votes else 0
            row["difference_to_second_votes"] = votes - second_votes
            row["difference_to_second_percent"] = round(percent - second_percent, 1)
            row["trend_state"] = self._ranking_trend_state(index, votes, second_votes)
        return rows

    def _build_lead_margin(self, candidate_ranking):
        if len(candidate_ranking) < 2:
            return {
                "votes": 0,
                "percent": 0,
                "leader": candidate_ranking[0]["label"] if candidate_ranking else "",
                "runner_up": "",
            }
        leader = candidate_ranking[0]
        runner_up = candidate_ranking[1]
        return {
            "votes": leader["votes"] - runner_up["votes"],
            "percent": leader["difference_to_second_percent"],
            "leader": leader["label"],
            "runner_up": runner_up["label"],
        }

    def _ranking_trend_state(self, index, votes, second_votes):
        if index == 0:
            return "Lidera"
        if index == 1:
            return "Persigue"
        if second_votes and votes >= second_votes * 0.85:
            return "Competitiva"
        return "Rezagada"

    def _build_parish_summary(self, lines):
        rows = list(
            lines.filter(line_type=ElectoralResultLine.LineType.CANDIDATE)
            .values("report__parish__name", "list_code", "candidate_name")
            .annotate(votes=Sum("votes"))
            .order_by("report__parish__name", "-votes", "list_code", "candidate_name")
        )
        grouped = {}
        for row in rows:
            parish_name = row["report__parish__name"]
            parish = grouped.setdefault(parish_name, {"parish": parish_name, "total_votes": 0, "rows": []})
            parish["total_votes"] += row["votes"] or 0
            parish["rows"].append(
                {
                    "list_code": row["list_code"],
                    "candidate_name": row["candidate_name"],
                    "label": (
                        f"{row['list_code']} - {row['candidate_name']}"
                        if row["candidate_name"]
                        else row["list_code"]
                    ),
                    "votes": row["votes"] or 0,
                }
            )
        for parish in grouped.values():
            for row in parish["rows"]:
                row["percent"] = (
                    round(row["votes"] * 100 / parish["total_votes"], 1)
                    if parish["total_votes"]
                    else 0
                )
        return list(grouped.values())
