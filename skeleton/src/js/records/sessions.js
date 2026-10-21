'use strict'

var Backbone = require('backbone')

class Sessions {
    static Model = Backbone.Model.extend({
        idAttribute: 'session_id',
        urlRoot:     '/sessions/dbcache/',
    })

    static Collection = Backbone.Collection.extend({
        model: Sessions.Model,
        url:   Sessions.Model.prototype.urlRoot,
        parse: function(response) {
            return response.data
        },
    })
}

module.exports = Sessions
