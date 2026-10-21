'use strict'

var Backbone = require('backbone')

class Users {
    static Model = Backbone.Model.extend({
        idAttribute: 'username',
        urlRoot:     '/logins/dblogin/',
    })

    static Collection = Backbone.Collection.extend({
        model: Users.Model,
        url:   Users.Model.prototype.urlRoot,
        parse: function(response) {
            return response.data
        },
    })
}

module.exports = Users
