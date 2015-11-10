import logging
from casexml.apps.case import const
from casexml.apps.case.exceptions import UsesReferrals, VersionNotSupported
from casexml.apps.case.xml import V2
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.update_strategy_base import UpdateStrategy
from django.utils.translation import ugettext as _

KNOWN_PROPERTIES_MAP = {
    'external_id': 'external_id',
    'case_type': 'type',
    'owner_id': 'owner_id',
    'opened_on': 'opened_on',
}


class SqlCaseUpdateStrategy(UpdateStrategy):
    case_implementation_class = CommCareCaseSQL

    def update_from_case_update(self, case_update, xformdoc, other_forms=None):
        if case_update.has_referrals():
            logging.error('Form {} touching case {} in domain {} is still using referrals'.format(
                xformdoc.form_id, case_update.id, getattr(xformdoc, 'domain', None))
            )
            raise UsesReferrals(_('Sorry, referrals are no longer supported!'))

        if case_update.version and case_update.version != V2:
            raise VersionNotSupported

        if xformdoc.is_deprecated:
            return

        if not self.case.case_json:
            self.case.case_json = {}

        for action in case_update.actions:
            self._apply_action(case_update, action, xformdoc)

        # override any explicit properties from the update
        if case_update.user_id:
            self.case.modified_by = case_update.user_id

        modified_on = case_update.guess_modified_on()
        if self.case.modified_on is None or modified_on > self.case.modified_on:
            self.case.modified_on = modified_on

    def _apply_action(self, case_update, action, xform):
        if action.action_type_slug == const.CASE_ACTION_CREATE:
            self._apply_create_action(case_update, action)
        elif action.action_type_slug == const.CASE_ACTION_UPDATE:
            self._apply_update_action(action)
        elif action.action_type_slug == const.CASE_ACTION_INDEX:
            self._apply_index_action(action)
        elif action.action_type_slug == const.CASE_ACTION_CLOSE:
            self._apply_close_action(case_update)
        elif action.action_type_slug == const.CASE_ACTION_ATTACHMENT:
            self._apply_attachments_action(action, xform)
        else:
            raise ValueError("Can't apply action of type %s: %s" % (
                action.action_type,
                self.case.case_id,
            ))

    def _update_known_properties(self, action):
        known_properties = action.get_known_properties()
        for k, v in KNOWN_PROPERTIES_MAP.items():
            val = known_properties.get(v, None)
            if val:
                setattr(self.case, k, val)

        self.case.case_json['name'] = known_properties.get('name', '')

    def _apply_create_action(self, case_update, create_action):
        self._update_known_properties(create_action)

        if not self.case.opened_on:
            self.case.opened_on = case_update.guess_modified_on()
        if not self.case.opened_by:
            self.case.opened_by = case_update.user_id

    def _apply_update_action(self, update_action):
        self._update_known_properties(update_action)

        for key, value in update_action.dynamic_properties.items():
            if key not in const.CASE_TAGS:
                self.case.case_json[key] = value

    def _apply_index_action(self, action):
        raise NotImplementedError()

    def _apply_attachments_action(self, attachment_action, xform=None):
        raise NotImplementedError()

    def _apply_close_action(self, case_update):
        self.case.closed = True
        self.case.closed_on = case_update.guess_modified_on()
        self.case.closed_by = case_update.user_id