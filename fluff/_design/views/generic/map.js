function (doc) {
    function typeOf(value) {
        // from Crockford himself: http://javascript.crockford.com/remedial.html
        var s = typeof value;
        if (s === 'object') {
            if (value) {
                if (Object.prototype.toString.call(value) == '[object Array]') {
                    s = 'array';
                }
            } else {
                s = 'null';
            }
        }
        return s;
    }

    function isArray(obj) {
        return typeOf(obj) === "array";
    }

    if (doc.base_doc === 'IndicatorDocument') {
        var key = [doc.doc_type], i;
        for (i = 0; i < doc.group_by.length; i++) {
            key.push(doc[doc.group_by[i]]);
        }
        for (var calcName in doc) {
            if (doc.hasOwnProperty(calcName)) {
                // isObject(doc[calcName])
                if (Object.prototype.toString.call(doc[calcName]) === '[object Object]') {
                    for (var emitterName in doc[calcName]) {
                        if (doc[calcName].hasOwnProperty(emitterName)) {
                            for (i = 0; i < doc[calcName][emitterName].length; i++) {
                                var value = doc[calcName][emitterName][i];
                                if (isArray(value)) {
                                    emit(key.concat([calcName, emitterName, value[0]]), value[1]);
                                } else {
                                    emit(key.concat([calcName, emitterName, value]), 1);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}