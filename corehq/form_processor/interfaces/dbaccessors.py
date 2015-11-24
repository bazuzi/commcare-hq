from abc import ABCMeta, abstractmethod

import six

from dimagi.utils.decorators.memoized import memoized

from ..utils import should_use_sql_backend


class AbstractFormAccessor(six.with_metaclass(ABCMeta)):
    """
    Contract for common methods expected on FormAccessor(SQL/Couch). All methods
    should be static or classmethods.
    """
    @abstractmethod
    def get_form(form_id):
        raise NotImplementedError

    @abstractmethod
    def get_forms_by_type(domain, type_, recent_first=False, limit=None):
        raise NotImplementedError

    @abstractmethod
    def get_with_attachments(form_id):
        raise NotImplementedError


class FormAccessors(object):
    """
    Facade for Form DB access that proxies method calls to SQL or Couch version
    """
    def __init__(self, domain=None):
        self.domain = domain

    @property
    @memoized
    def db_accessor(self):
        from corehq.form_processor.backends.couch.dbaccessors import FormAccessorCouch
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        if should_use_sql_backend(self.domain):
            return FormAccessorSQL
        else:
            return FormAccessorCouch

    def get_form(self, form_id):
        return self.db_accessor.get_form(form_id)

    def get_forms_by_type(self, type_, recent_first=False, limit=None):
        return self.db_accessor.get_forms_by_type(self.domain, type_, recent_first, limit)

    def get_with_attachments(self, form_id):
        return self.db_accessor.get_with_attachments(form_id)


class AbstractCaseAccessor(six.with_metaclass(ABCMeta)):
    """
    Contract for common methods expected on CaseAccessor(SQL/Couch). All methods
    should be static or classmethods.
    """
    @abstractmethod
    def get_case(case_id):
        raise NotImplementedError

    @abstractmethod
    def get_cases(case_ids):
        raise NotImplementedError

    @abstractmethod
    def get_case_xform_ids(case_ids):
        raise NotImplementedError

    @abstractmethod
    def get_case_ids_in_domain(domain, type=None):
        raise NotImplementedError


class CaseAccessors(object):
    """
    Facade for Case DB access that proxies method calls to SQL or Couch version
    """
    def __init__(self, domain=None):
        self.domain = domain

    @property
    @memoized
    def db_accessor(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch
        if should_use_sql_backend(self.domain):
            return CaseAccessorSQL
        else:
            return CaseAccessorCouch

    def get_case(self, case_id):
        return self.db_accessor.get_case(case_id)

    def get_cases(self, case_ids, ordered=False):
        return self.db_accessor.get_cases(case_ids, ordered=ordered)

    def get_case_xform_ids(self, case_ids):
        return self.db_accessor.get_case_xform_ids(case_ids)

    def get_case_ids_in_domain(self, type=None):
        return self.db_accessor.get_case_ids_in_domain(self.domain, type)
