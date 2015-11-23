import json
from jsonobject.exceptions import BadValueError
from corehq.apps.reports_core.filters import DatespanFilter, ChoiceListFilter, Choice, DynamicChoiceListFilter, \
    NumericFilter
from corehq.apps.userreports.exceptions import BadSpecError
from django.utils.translation import ugettext as _
from corehq.apps.userreports.reports.filters.choice_providers import get_choices_from_data_source_column, \
    DATA_SOURCE_COLUMN, LOCATION, get_location_choices
from corehq.apps.userreports.reports.filters.values import(
    dynamic_choice_list_url,
    NONE_CHOICE,
    SHOW_ALL_CHOICE,
)
from corehq.apps.userreports.reports.filters.specs import (
    ChoiceListFilterSpec, DynamicChoiceListFilterSpec, NumericFilterSpec, DateFilterSpec
)


def _build_date_filter(spec):
    wrapped = DateFilterSpec.wrap(spec)
    return DatespanFilter(
        name=wrapped.slug,
        label=wrapped.get_display(),
    )


def _build_numeric_filter(spec):
    wrapped = NumericFilterSpec.wrap(spec)
    return NumericFilter(
        name=wrapped.slug,
        label=wrapped.get_display(),
    )


def _build_choice_list_filter(spec):
    wrapped = ChoiceListFilterSpec.wrap(spec)
    choices = [Choice(
        fc.value if fc.value is not None else NONE_CHOICE,
        fc.get_display()
    ) for fc in wrapped.choices]
    if wrapped.show_all:
        choices.insert(0, Choice(SHOW_ALL_CHOICE, _('Show all')))
    return ChoiceListFilter(
        name=wrapped.slug,
        datatype=wrapped.datatype,
        label=wrapped.display,
        choices=choices,
    )


def _build_dynamic_choice_list_filter(spec):
    wrapped = DynamicChoiceListFilterSpec.wrap(spec)
    return DynamicChoiceListFilter(
        name=wrapped.slug,
        datatype=wrapped.datatype,
        field=wrapped.field,
        label=wrapped.display,
        show_all=wrapped.show_all,
        url_generator=dynamic_choice_list_url,
        choice_provider=FilterChoiceProviderFactory.from_spec(wrapped.get_choice_provider_spec()),
    )


class ReportFilterFactory(object):
    constructor_map = {
        'date': _build_date_filter,
        'choice_list': _build_choice_list_filter,
        'dynamic_choice_list': _build_dynamic_choice_list_filter,
        'numeric': _build_numeric_filter
    }

    @classmethod
    def from_spec(cls, spec):
        cls.validate_spec(spec)
        try:
            return cls.constructor_map[spec['type']](spec)
        except (AssertionError, BadValueError) as e:
            raise BadSpecError(_('Problem creating report filter from spec: {}, message is: {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))

    @classmethod
    def validate_spec(cls, spec):
        if spec.get('type') not in cls.constructor_map:
            raise BadSpecError(
                _('Illegal report filter type: {0}, must be one of the following choice: ({1})').format(
                    spec.get('type', _('(missing from spec)')),
                    ', '.join(cls.constructor_map.keys())
                )
            )


class FilterChoiceProviderFactory(object):
    constructor_map = {
        DATA_SOURCE_COLUMN: get_choices_from_data_source_column,
        LOCATION: get_location_choices,
    }

    @classmethod
    def from_spec(cls, choice_provider_spec):
        return cls.constructor_map.get(choice_provider_spec['type'], get_choices_from_data_source_column)
