from django.utils.translation import ugettext_noop
from commcarehq.apps.groups.models import Group
from commcarehq.apps.reports.filters.select import GroupFilter

class SelectCaseSharingGroupField(GroupFilter):

    def update_params(self):
        super(SelectCaseSharingGroupField, self).update_params()
        self.groups = Group.get_case_sharing_groups(self.domain)
        self.options = [dict(val=group.get_id, text=group.name) for group in self.groups]
