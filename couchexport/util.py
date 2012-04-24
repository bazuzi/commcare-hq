import functools
from inspect import isfunction
import json
from couchdbkit.ext.django.schema import StringProperty, Property
from dimagi.utils.modules import to_function
from dimagi.utils.web import json_handler

def intersect_functions(*functions):
    functions = [fn for fn in functions if fn]
    if functions:
        def function(*args):
            val = True
            for fn in functions:
                val = fn(*args)
                if not val:
                    return val
            return val
    else:
        function = None
    return function

class SerializableFunction(object):
    def __init__(self, function=None, **kwargs):
        self.functions = []
        if function:
            self.add(function, **kwargs)

    def add(self, function, **kwargs):
        self.functions.append((function, kwargs))

    def __iand__(self, other):
        self.functions.extend(other.functions)
        return self

    def __and__(self, other):
        if other is None:
            other = SerializableFunction()
        if isfunction(other):
            other = SerializableFunction(other)
        f = SerializableFunction()
        f &= self
        f &= other
        return f

    def __call__(self, *args):
        if self.functions:
            return intersect_functions(*[functools.partial(f, **kwargs) for (f, kwargs) in self.functions])(*args)
        else:
            return True

    def dumps(self):
        functions = []
        for f, kwargs in self.functions:
            for key in kwargs:
                try:
                    kwargs[key] = kwargs[key].to_dict()
                except (AttributeError, TypeError):
                    pass
            functions.append({
                'function': '%s.%s' % (f.__module__, f.__name__),
                'kwargs': kwargs
            })
        def handler(obj):
            try:
                json_handler(obj)
            except Exception:
                if isinstance(obj, SerializableFunction):
                    return {'type': 'SerializedFunction', 'dump': obj.dumps()}
                elif isfunction(obj):
                    return {'type': 'SerializedFunction', 'dump': SerializableFunction(obj).dumps()}
        return json.dumps(functions, default=handler)

    @classmethod
    def loads(cls, data):
        def object_hook(d):
            if d.get('type') == 'SerializedFunction':
                return cls.loads(d['dump'])
            else:
                return d
        functions = json.loads(data, object_hook=object_hook)
        self = cls()
        for o in functions:
            f, kwargs = o['function'], o['kwargs']
            f = to_function(f)
            self.add(f, **kwargs)
        return self

# deprecated name
FilterFunction = SerializableFunction


class SerializableFunctionProperty(Property):

    def to_python(self, value):
        if not value:
            return SerializableFunction()
        try:
            return SerializableFunction.loads(value)
        except ValueError:
            return SerializableFunction(to_function(value))

    def to_json(self, value):
        if isfunction(value):
            function = SerializableFunction(value)
        elif not value:
            function = SerializableFunction()
        else:
            function = value
        return function.dumps()
